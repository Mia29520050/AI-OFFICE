# -*- coding: utf-8 -*-
"""
app/chat_image_handler.py
=========================
Autonomous Chat-to-Image Generation Handler for AI Office.

Merges Creative Studio (ComfyUI Anima DeltaMix 2.9B) seamlessly into the Chat interface:
1. Detects image generation intent from natural language chat messages (e.g., 'tạo ảnh Hutao', 'vẽ Raiden Shogun').
2. Autonomously researches canonical character visual traits (via AutonomousCharacterResearcher).
3. Executes local ComfyUI workflow using fp8 VRAM staging.
4. Saves output to data/manga/chat_generated/ and returns rich markdown with embedded images.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import shutil
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.character_researcher import auto_research_character, get_character_researcher

logger = logging.getLogger("chat_image_handler")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent.parent
CHAT_IMAGES_DIR = ROOT_DIR / "data" / "manga" / "chat_generated"
CHAT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_IMAGES_DIR = ROOT_DIR / "Export" / "Images"
EXPORT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = ROOT_DIR / "data" / "office.db"


def resolve_comfy_dir() -> Path:
    """Resolves ComfyUI directory, supporting F:\\AI-Office\\engine\\ComfyUI."""
    env_val = os.environ.get("COMFYUI_PATH", "").strip()
    if env_val:
        return Path(env_val)
    engine_dir = ROOT_DIR / "engine" / "ComfyUI"
    if engine_dir.exists():
        return engine_dir
    return Path(r"F:\AI-Office\engine\ComfyUI")


COMFY_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
COMFY_DIR = resolve_comfy_dir()
_VENV_PY = COMFY_DIR / ".venv" / "Scripts" / "python.exe"
_FALLBACK_PY = Path(r"F:\AI-Office\engine\ComfyUI\.venv\Scripts\python.exe")
COMFY_PYTHON = _VENV_PY if _VENV_PY.exists() else _FALLBACK_PY
MODEL_NAME = "2.9V8.safetensors"
CLIP_NAME = "qwen_3_06b_base.safetensors"
VAE_NAME = "qwen_image_vae.safetensors"

# ---------------------------------------------------------------------------
# Aspect Ratios & Output Formats
# ---------------------------------------------------------------------------

ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    "1:1": (1024, 1024),
    "3:4": (768, 1024),
    "4:3": (1024, 768),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}

SUPPORTED_FORMATS: List[str] = ["PNG", "WEBP", "JPEG", "JPG"]

ASPECT_RATIO_ALIASES: Dict[str, str] = {
    "1:1": "1:1",
    "1/1": "1:1",
    "square": "1:1",
    "vuong": "1:1",
    "vuông": "1:1",
    "3:4": "3:4",
    "3/4": "3:4",
    "portrait": "3:4",
    "doc": "3:4",
    "dọc": "3:4",
    "4:3": "4:3",
    "4/3": "4:3",
    "16:9": "16:9",
    "16/9": "16:9",
    "landscape": "16:9",
    "ngang": "16:9",
    "widescreen": "16:9",
    "wallpaper": "16:9",
    "9:16": "9:16",
    "9/16": "9:16",
    "vertical": "9:16",
    "mobile": "9:16",
    "phone": "9:16",
    "story": "9:16",
}


def resolve_aspect_ratio(ratio_str: Optional[str]) -> str:
    """Normalizes an aspect ratio string to canonical preset e.g. '1:1', '3:4', '16:9', '9:16'."""
    if not ratio_str:
        return "3:4"
    cleaned = ratio_str.strip().lower()
    return ASPECT_RATIO_ALIASES.get(cleaned, cleaned if cleaned in ASPECT_RATIOS else "3:4")


def get_dimensions_for_aspect_ratio(aspect_ratio: Optional[str]) -> Tuple[int, int]:
    """Returns (width, height) for the requested aspect ratio."""
    key = resolve_aspect_ratio(aspect_ratio)
    return ASPECT_RATIOS.get(key, (768, 1024))


def convert_and_save_image(
    image_path: Path,
    target_format: str = "PNG",
    quality: int = 95
) -> Path:
    """
    Converts and saves an image to the requested format (PNG, WEBP, JPEG).
    Returns the path to the newly saved or existing file.
    """
    norm_fmt = (target_format or "PNG").upper().strip()
    if norm_fmt in ("JPG", "JPEG"):
        target_ext = ".jpg"
        pil_fmt = "JPEG"
    elif norm_fmt == "WEBP":
        target_ext = ".webp"
        pil_fmt = "WEBP"
    else:
        target_ext = ".png"
        pil_fmt = "PNG"

    if image_path.suffix.lower() == target_ext.lower():
        return image_path

    out_path = image_path.with_suffix(target_ext)
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            if pil_fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            img.save(out_path, format=pil_fmt, quality=quality)
        return out_path
    except Exception as e:
        logger.warning(f"[ChatImage] Format conversion to {norm_fmt} failed: {e}; keeping original {image_path.name}")
        return image_path


def parse_image_options(message: str) -> Tuple[str, str, str]:
    """
    Extracts aspect ratio and output format keywords from a prompt message,
    and returns: (cleaned_message, aspect_ratio, output_format)
    """
    ratio = "3:4"
    fmt = "PNG"
    cleaned = message

    # Detect aspect ratio
    ar_pattern = r"(?:(?:tỉ|tỷ)\s*lệ|khung\s*hình|ratio|aspect\s*ratio)?\s*[:=]?\s*\b(1:1|3:4|4:3|16:9|9:16|1/1|3/4|4/3|16/9|9/16|square|vuông|vuong|portrait|dọc|doc|landscape|ngang|vertical|widescreen|wallpaper|mobile)\b"
    m_ar = re.search(ar_pattern, cleaned, flags=re.IGNORECASE)
    if m_ar:
        raw_val = m_ar.group(1).replace("/", ":")
        ratio = resolve_aspect_ratio(raw_val)
        cleaned = cleaned[:m_ar.start()] + " " + cleaned[m_ar.end():]

    # Detect output format
    fmt_pattern = r"(?:(?:định\s*dạng|format|dạng|đuôi|file)\s*[:=]?\s*)?\b(png|webp|jpeg|jpg)\b"
    m_fmt = re.search(fmt_pattern, cleaned, flags=re.IGNORECASE)
    if m_fmt:
        raw_fmt = m_fmt.group(1).upper()
        if raw_fmt == "JPG":
            raw_fmt = "JPEG"
        fmt = raw_fmt
        cleaned = cleaned[:m_fmt.start()] + " " + cleaned[m_fmt.end():]

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, ratio, fmt

# ---------------------------------------------------------------------------
# 1. Intent Detection
# ---------------------------------------------------------------------------

GEN_PATTERNS = [
    r"^(?:hãy\s+)?(?:tạo|vẽ|sinh|render|generate|draw|paint|make)\s+(?:cho\s+(?:tôi|anh|em|mình)\s+)?(?:bức\s+)?(?:ảnh|hình|tranh|nhân\s+vật)?\s*(.+)$",
    r"^(?:tạo|vẽ|sinh|draw|generate)\s+(.+)$",
]

EXCLUDE_PATTERNS = [
    r"làm\s+thế\s+nào",
    r"cách\s+(?:nào|tạo|vẽ)",
    r"tại\s+sao",
    r"hướng\s+dẫn",
    r"như\s+thế\s+nào",
    r"có\s+thể\s+vẽ\s+không",
    r"có\s+biết\s+vẽ\s+không",
    r"viết\s+mã",
    r"code",
]


def detect_image_generation_intent(message: str) -> Tuple[bool, str, str]:
    """
    Detects if the user wants to generate an image and extracts the target subject/prompt.
    Returns: (is_image_intent, subject, extra_details)
    """
    cleaned = message.strip()
    lower = cleaned.lower()

    # If it's a generic meta question about drawing, do not trigger image generation
    if any(re.search(pat, lower) for pat in EXCLUDE_PATTERNS):
        return False, "", ""

    # Check for direct image keywords (longest first)
    trigger_words = [
        "hãy vẽ cho tôi", "hay ve cho toi", "tạo cho tôi", "tao cho toi",
        "vẽ cho tôi", "ve cho toi", "vẽ nhân vật", "ve nhan vat",
        "đổi nhân vật trong ảnh thành", "doi nhan vat trong anh thanh",
        "thay nhân vật trong ảnh thành", "thay nhan vat trong anh thanh",
        "đổi nhân vật thành", "doi nhan vat thanh",
        "thay nhân vật thành", "thay nhan vat thanh",
        "thay bằng nhân vật", "thay bang nhan vat",
        "biến thành nhân vật", "bien thanh nhan vat",
        "tạo hình ảnh", "tao hinh anh", "tạo ảnh", "tao anh",
        "vẽ ảnh", "ve anh", "sinh ảnh", "sinh anh",
        "vẽ hình", "ve hinh", "tạo hình", "tao hinh",
        "vẽ tranh", "ve tranh", "generate image", "draw an image",
        "create image", "draw me", "draw a", "draw", "paint",
        "hãy vẽ", "hay ve", "vẽ", "ve"
    ]

    has_trigger = False
    matched_tw = ""
    for tw in trigger_words:
        # Match as word or prefix
        pattern = rf"(?:^|\s){re.escape(tw)}(?:\s+|$)"
        m = re.search(pattern, lower)
        if m:
            has_trigger = True
            matched_tw = tw
            # Extract subject after matched word
            start_pos = m.end()
            subject_raw = cleaned[start_pos:].strip()
            break

    if not has_trigger:
        return False, "", ""

    # Clean leading particles
    subject_raw = re.sub(
        r"^(?:cho\s+(?:tôi|anh|em|mình)\s+)?(?:bức\s+)?(?:ảnh|hình|tranh|nhân\s+vật)?\s*(?:về\s+)?",
        "",
        subject_raw,
        flags=re.IGNORECASE
    ).strip()
    subject_raw = re.sub(r"^:\s*", "", subject_raw).strip()

    if not subject_raw:
        return False, "", ""

    # Split subject and extra context if present (e.g. "Hutao đang cười tươi")
    # Prioritize explicit outfit/action connectors before generic franchise 'trong <game>'
    split_words = [
        " trong trang phục ", " trong bo ", " trong bộ ", " mặc trang phục ",
        " đang ", " voi ", " với ", " mặc ", " mac ", " trong ", " ở ", " tai ", " tại ",
    ]
    subject_raw = re.sub(r"\s+(?:đi|nhé|nha|giúp\s+(?:anh|em|tôi))$", "", subject_raw, flags=re.IGNORECASE).strip()
    subject = subject_raw
    extra = ""
    for sw in split_words:
        if sw in subject_raw.lower():
            parts = re.split(re.escape(sw), subject_raw, flags=re.IGNORECASE, maxsplit=1)
            candidate_subj = parts[0].strip()
            candidate_extra = sw.strip() + " " + parts[1].strip()
            # If user wrote "<char> trong genshin impact" with nothing else, strip franchise from subject;
            # otherwise keep splitting properly.
            if sw == " trong " and re.match(r"^(?:genshin\s+impact|honkai|star\s+rail|wuthering\s+waves)\b", parts[1].strip(), re.IGNORECASE):
                subject = candidate_subj
                extra = ""
            else:
                subject = candidate_subj
                extra = candidate_extra
            break

    # Clean trailing franchise tag from subject when custom outfit was already split out
    subject = re.sub(r"\s+trong\s+(?:genshin\s+impact|honkai\s+star\s+rail|zenless\s+zone\s+zero)$", "", subject, flags=re.IGNORECASE).strip()

    # Clean any embedded aspect ratio or format directives from extracted subject & extra
    subj_clean, _, _ = parse_image_options(subject)
    extra_clean, _, _ = parse_image_options(extra)

    return True, subj_clean, extra_clean


# ---------------------------------------------------------------------------
# 2. ComfyUI Workflow Execution
# ---------------------------------------------------------------------------

def is_comfy_online() -> bool:
    """Checks if ComfyUI is listening."""
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


async def ensure_comfy_online(timeout_secs: int = 90) -> bool:
    """Ensures ComfyUI is launched and listening via EngineManager Job Object."""
    if is_comfy_online():
        return True
    from app.engines import get_engines
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: get_engines().ensure_comfy(wait_secs=timeout_secs))


async def run_comfy_workflow(
    positive_prompt: str,
    negative_prompt: str,
    prefix: str = "ChatGen",
    seed: int = -1,
    width: int = 768,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 4.5,
    timeout_secs: int = 240,
    ref_image_name: Optional[str] = None,
    denoise: float = 1.0,
    ref_strength: float = 0.75,
    ref_guidance: float = 2.5,
    aspect_ratio: Optional[str] = None,
    output_format: str = "PNG",
) -> Path:
    """Submits workflow to ComfyUI and polls until image is downloaded.
    Supports AnimaRefAdapter + VAEEncode Img2Img height & identity locking when ref_image_name is provided.
    Supports aspect ratios (1:1, 3:4, 16:9, 9:16) and output format conversion (PNG, WEBP, JPEG).
    """
    if aspect_ratio:
        width, height = get_dimensions_for_aspect_ratio(aspect_ratio)

    if seed < 0:
        seed = random.randint(100_000, 999_999_999)

    workflow: dict[str, Any] = {
        "1": {
            "inputs": {
                "unet_name": MODEL_NAME,
                "weight_dtype": "fp8_e4m3fn"
            },
            "class_type": "UNETLoader"
        },
        "2": {
            "inputs": {
                "clip_name": CLIP_NAME,
                "type": "stable_diffusion",
                "device": "default"
            },
            "class_type": "CLIPLoader"
        },
        "3": {
            "inputs": {
                "vae_name": VAE_NAME
            },
            "class_type": "VAELoader"
        },
        "4": {
            "inputs": {
                "text": positive_prompt,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "5": {
            "inputs": {
                "text": negative_prompt,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
    }

    if ref_image_name:
        # Height & Face Locking Pipeline via AnimaRefAdapter + Img2Img
        workflow["10"] = {"class_type": "LoadImage", "inputs": {"image": ref_image_name}}
        workflow["11"] = {
            "class_type": "AnimaRefAdapter",
            "inputs": {
                "model": ["1", 0],
                "vae": ["3", 0],
                "image": ["10", 0],
                "lora_name": "anima_ref_adapter_v2_r64.safetensors",
                "ref_guidance": ref_guidance,
                "correction": "apg",
                "strength": ref_strength,
                "ref_end": 0.55,
                "ref_megapixels": 0.75,
            },
        }
        workflow["12"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["3", 0]}}
        workflow["7"] = {
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": denoise if denoise < 1.0 else 0.84,
                "model": ["11", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["12", 0]
            },
            "class_type": "KSampler"
        }
    else:
        # Standard Text-to-Image Generation
        workflow["6"] = {
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        }
        workflow["7"] = {
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0]
            },
            "class_type": "KSampler"
        }

    workflow["8"] = {
        "inputs": {
            "samples": ["7", 0],
            "vae": ["3", 0]
        },
        "class_type": "VAEDecode"
    }
    workflow["9"] = {
        "inputs": {
            "filename_prefix": prefix,
            "images": ["8", 0]
        },
        "class_type": "SaveImage"
    }

    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=payload, headers={"Content-Type": "application/json"})

    loop = asyncio.get_running_loop()

    def _submit() -> str:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode())
            return res["prompt_id"]

    prompt_id = await loop.run_in_executor(None, _submit)
    logger.info(f"[ChatImage] Submitted prompt_id: {prompt_id}")

    t0 = time.time()
    while time.time() - t0 < timeout_secs:
        await asyncio.sleep(2)
        try:
            def _check_history() -> Optional[dict]:
                h_req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}")
                with urllib.request.urlopen(h_req, timeout=5) as resp:
                    hist = json.loads(resp.read().decode())
                    return hist.get(prompt_id)

            item = await loop.run_in_executor(None, _check_history)
            if item:
                outputs = item.get("outputs", {})
                if "9" in outputs and "images" in outputs["9"]:
                    img_info = outputs["9"]["images"][0]
                    params = urllib.parse.urlencode({
                        "filename": img_info["filename"],
                        "subfolder": img_info.get("subfolder", ""),
                        "type": img_info.get("type", "output")
                    })
                    view_url = f"{COMFY_URL}/view?{params}"
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    file_id = uuid.uuid4().hex[:8]
                    out_filename = f"chat_{timestamp}_{file_id}.png"
                    out_path = CHAT_IMAGES_DIR / out_filename

                    def _download():
                        urllib.request.urlretrieve(view_url, str(out_path))

                    await loop.run_in_executor(None, _download)
                    logger.info(f"[ChatImage] Downloaded image to {out_path}")

                    norm_out_fmt = (output_format or "PNG").upper().strip()
                    if norm_out_fmt not in ("PNG", ""):
                        converted_path = convert_and_save_image(out_path, target_format=norm_out_fmt)
                        logger.info(f"[ChatImage] Converted image to format {norm_out_fmt}: {converted_path}")
                        return converted_path

                    return out_path
        except Exception as e:
            logger.debug(f"[ChatImage] Polling exception: {e}")

    raise TimeoutError(f"Image generation timed out after {timeout_secs}s")


# ---------------------------------------------------------------------------
# 3. High-Level Chat Handler & User Reference Resolution
# ---------------------------------------------------------------------------

def _stage_ref_image_for_comfy(ref_url_or_name: str) -> Optional[str]:
    """
    Resolves a user profile reference URL (e.g. '/api/chat/images/user_asset_xxx.png')
    or filename to a local file and stages it into ComfyUI's input/ directory if available.
    Returns the ComfyUI LoadImage filename if found, else None.
    """
    raw = (ref_url_or_name or "").strip()
    if not raw:
        return None
    filename = Path(urllib.parse.urlparse(raw).path).name
    if not filename:
        return None

    comfy_input_dir = COMFY_DIR / "input"
    candidate_paths = [
        comfy_input_dir / filename,
        ROOT_DIR / "data" / "characters" / filename,
        CHAT_IMAGES_DIR / filename,
        EXPORT_IMAGES_DIR / filename,
    ]
    if Path(raw).is_file():
        candidate_paths.insert(0, Path(raw))

    found_path = next((p for p in candidate_paths if p.is_file()), None)
    if not found_path:
        return None

    if comfy_input_dir.parent.exists():
        try:
            comfy_input_dir.mkdir(parents=True, exist_ok=True)
            dest = comfy_input_dir / filename
            if found_path.resolve() != dest.resolve():
                shutil.copy2(found_path, dest)
        except Exception as exc:
            logger.warning(f"[ChatImage] Could not stage ref image to {comfy_input_dir}: {exc}")

    return filename


def resolve_user_profile_ref_image(
    db_path: Optional[Path] = None,
    explicit_ref: Optional[str] = None,
    prefer: str = "body",
) -> Optional[str]:
    """
    Reads `face_ref_url` and `body_ref_url` from `user_profile` table (or uses `explicit_ref`)
    to lock pose/height/face in `run_comfy_workflow` via AnimaRefAdapter.
    """
    if explicit_ref:
        staged = _stage_ref_image_for_comfy(explicit_ref)
        if staged:
            return staged
        return Path(explicit_ref).name

    target_db = db_path or DB_PATH
    if not target_db.is_file():
        return None

    try:
        conn = sqlite3.connect(str(target_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT face_ref_url, body_ref_url FROM user_profile WHERE id='default'"
        ).fetchone()
        conn.close()
        if not row:
            return None

        face_url = (row["face_ref_url"] or "").strip()
        body_url = (row["body_ref_url"] or "").strip()
        ordered = [body_url, face_url] if prefer == "body" else [face_url, body_url]
        for ref_url in ordered:
            if ref_url:
                staged = _stage_ref_image_for_comfy(ref_url)
                if staged:
                    return staged
    except Exception as exc:
        logger.debug(f"[ChatImage] Failed reading user_profile refs: {exc}")

    return None


async def handle_chat_image_generation(
    user_message: str,
    conversation_id: str = "",
    aspect_ratio: Optional[str] = None,
    output_format: Optional[str] = None,
    ref_image_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes full pipeline:
    1. Extracts character / prompt & options (aspect ratio, format)
    2. Researches character knowledge
    3. Builds prompt & executes ComfyUI
    4. Formats markdown output with embedded image and technical specs
    """
    cleaned_input, detected_ratio, detected_fmt = parse_image_options(user_message)
    is_intent, subject, extra = detect_image_generation_intent(cleaned_input if cleaned_input else user_message)
    if not is_intent or not subject:
        is_intent, subject, extra = detect_image_generation_intent(user_message)
    if not is_intent or not subject:
        return {
            "success": False,
            "error": "Không nhận diện được chủ đề cần tạo ảnh."
        }

    chosen_ratio = resolve_aspect_ratio(aspect_ratio or detected_ratio)
    chosen_format = (output_format or detected_fmt or "PNG").upper()
    if chosen_format == "JPG":
        chosen_format = "JPEG"
    width, height = get_dimensions_for_aspect_ratio(chosen_ratio)

    logger.info(f"[ChatImage] Request received: subject='{subject}', extra='{extra}', ratio='{chosen_ratio}' ({width}x{height}), format='{chosen_format}'")

    # 1. Autonomous research / knowledge lookup
    char_info = auto_research_character(subject)
    canonical_names = {
        "hutao": "Hu Tao",
        "hu tao": "Hu Tao",
        "raiden": "Raiden Shogun",
        "raiden shogun": "Raiden Shogun",
        "ei": "Raiden Shogun (Ei)",
        "zhongli": "Zhongli",
        "furina": "Furina",
        "nahida": "Nahida",
        "aether": "Aether (Genshin Impact)",
    }
    subj_norm = subject.lower().strip()
    display_name = canonical_names.get(subj_norm) or (char_info.display_name if char_info.display_name and char_info.display_name != subj_norm else subject.title())

    # 2. Build Danbooru positive & negative prompts
    is_custom_outfit = bool(extra and any(k in extra.lower() for k in ["trang phục", "mặc", "outfit", "costume", "cosplay", "clothes", "màu", "whispers"]))
    custom_outfit_prompt = ""
    known_outfit_specs = {
        "whispers of stars and smoke": (
            "wearing Citlali Whispers of Stars and Smoke sleepwear outfit, "
            "short pastel lavender nightgown dress with white lace hem and dark purple zig-zag and white wave patterns, "
            "open knee-length purple ombre shawl overcoat with ruffled white neckline, "
            "dark purple chest bow with bright teal jewel and gold necklace, "
            "pale pink bows with teal accents on overcoat hem, "
            "white Citlalin sleeping mask pushed up on left side of head with cute folded ears and dark purple ruffled edge, "
            "lavender leg warmers, indoor slippers"
        ),
    }
    extra_lower = (extra or "").lower()
    matched_known_outfit = next((spec for key, spec in known_outfit_specs.items() if key in extra_lower), "")

    if extra:
        # Try local Ollama to translate Vietnamese/crossover outfit instructions into clean English anime tags
        try:
            ollama_prompt = (
                f"Convert this anime illustration request into concise English Danbooru/anime visual tags ONLY (comma-separated, no explanation).\n"
                f"Character core traits: {char_info.hair_tags}, {char_info.eye_tags}, {char_info.face_tags}\n"
                f"Requested outfit / action / scene: {extra}\n"
                + (f"Known outfit design details (include all visual items): {matched_known_outfit}\n" if matched_known_outfit else "")
                + f"Keep the character's original hair, eyes, and gender ({'1boy, male' if '1boy' in char_info.danbooru_prompt else 'character'})."
            )
            req_body = json.dumps({
                "model": os.environ.get("AI_OFFICE_LOCAL_MODEL", "qwen3.5:4b"),
                "messages": [{"role": "user", "content": ollama_prompt}],
                "stream": False,
                "think": False,
                "options": {"num_predict": 220, "temperature": 0.25},
            }).encode("utf-8")
            req_obj = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=req_body,
                headers={"Content-Type": "application/json"},
            )
            def _ask_ollama() -> str:
                with urllib.request.urlopen(req_obj, timeout=120) as r:
                    return str(json.loads(r.read().decode("utf-8")).get("message", {}).get("content", "")).strip()

            loop = asyncio.get_running_loop()
            custom_outfit_prompt = await loop.run_in_executor(None, _ask_ollama)
            # Immediately unload Ollama from VRAM so ComfyUI has maximum headroom on 6GB GPUs
            try:
                unload_req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=json.dumps({"model": os.environ.get("AI_OFFICE_LOCAL_MODEL", "qwen3.5:4b"), "keep_alive": 0}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                await loop.run_in_executor(None, lambda: urllib.request.urlopen(unload_req, timeout=5).read())
            except Exception:
                pass
        except Exception as llm_exc:
            logger.warning(f"[ChatImage] Ollama prompt expansion failed/skipped: {llm_exc}")

    if is_custom_outfit:
        gender_hint = "1boy, solo" if "1boy" in char_info.danbooru_prompt else "solo"
        # Use physical traits + outfit details without repeating default costume priors; force full-body framing
        outfit_clause = ", ".join(filter(None, [matched_known_outfit, custom_outfit_prompt])) or extra
        positive_components = [
            f"{gender_hint}, full body shot, standing pose, looking at viewer",
            f"young anime boy with {char_info.hair_tags}, {char_info.eye_tags}, {char_info.face_tags}",
            outfit_clause,
            "masterpiece, best quality, vibrant anime illustration, crisp cel shading, sharp details, expressive eyes, cozy celestial night room background"
        ]
    else:
        positive_components = [
            char_info.danbooru_prompt or f"{subject}, solo, anime aesthetic",
            "masterpiece, best quality, sharp details, vibrant colors, expressive eyes, dynamic lighting, professional illustration"
        ]
        if custom_outfit_prompt or extra:
            positive_components.append(custom_outfit_prompt or extra)

    positive_prompt = ", ".join(filter(None, positive_components))
    negative_prompt = (
        char_info.negative_prompt
        or "photorealistic, 3d, realistic, deformed hands, bad anatomy, missing fingers, extra fingers, blurry, low quality, bad eyes, disfigured, text, watermark"
    )
    if is_custom_outfit and "aether" in subj_norm:
        negative_prompt = f"brown crop top, traveler scarf, midriff, armor, close-up portrait, {negative_prompt}"
    if "1boy" in positive_prompt.lower() and "1girl" not in positive_prompt.lower():
        negative_prompt = f"1girl, female, breasts, {negative_prompt}"

    # Append aspect-ratio composition nuance if not present
    ratio_tags = {
        "1:1": "square aspect ratio, 1:1 framing, centered portrait composition",
        "3:4": "portrait aspect ratio, 3:4 framing, vertical character composition",
        "4:3": "landscape aspect ratio, 4:3 framing, cinematic composition",
        "16:9": "widescreen aspect ratio, 16:9 framing, panoramic landscape composition, cinematic vista",
        "9:16": "tall vertical aspect ratio, 9:16 framing, mobile wallpaper, full body composition",
    }
    if chosen_ratio in ratio_tags and ratio_tags[chosen_ratio] not in positive_prompt:
        positive_prompt = f"{positive_prompt}, {ratio_tags[chosen_ratio]}"

    # 3. Check ComfyUI server availability (Auto-start if offline, 90s cold-start timeout)
    if not await ensure_comfy_online(timeout_secs=90):
        logger.warning("[ChatImage] ComfyUI server is offline and failed to start!")
        return {
            "success": False,
            "text": (
                f"Đã ghi nhận yêu cầu tạo ảnh cho **{display_name}**!\n\n"
                f"⚠️ **Thông báo:** Hệ thống Studio Sáng tạo (ComfyUI) tại cổng `127.0.0.1:8188` hiện chưa thể khởi động tự động. "
                f"Vui lòng kiểm tra tiến trình ComfyUI để hoàn tất sinh ảnh."
            )
        }

    # Resolve optional height/face reference from user_profile (Mobile Settings) or explicit param
    effective_ref = resolve_user_profile_ref_image(explicit_ref=ref_image_name)

    # 4. Generate Image (free Ollama VRAM first to prevent 6GB OOM)
    try:
        from app.vram_guard import free_ollama
        await free_ollama()
    except Exception:
        pass
    try:
        prefix = f"Chat_{re.sub(r'[^a-zA-Z0-9]+', '', display_name)[:12]}"
        image_path = await run_comfy_workflow(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            prefix=prefix,
            width=width,
            height=height,
            steps=25,
            cfg=4.5,
            timeout_secs=240,
            ref_image_name=effective_ref,
            aspect_ratio=chosen_ratio,
            output_format=chosen_format,
        )
    except Exception as e:
        logger.error(f"[ChatImage] Generation error: {e}", exc_info=True)
        return {
            "success": False,
            "text": f"Đã xảy ra lỗi khi tạo ảnh cho **{display_name}**: `{e}`. Vui lòng thử lại!"
        }

    # 5. Build presentation text
    filename = image_path.name
    image_url = f"/api/chat/images/{filename}"

    # Auto-classify & move output directly into F:\AI-Office\Export\Images\<Category>\
    try:
        franchise_raw = getattr(char_info, "franchise", "") or ""
        lower_all = f"{franchise_raw} {display_name}".lower()
        if "genshin" in lower_all or any(k in lower_all for k in ("citlali", "aether", "raiden", "hutao", "hu tao", "furina", "mavuika", "chasca")):
            category_dir = "Genshin_Impact"
        elif any(k in lower_all for k in ("manga", "comic", "panel")):
            category_dir = "Manga_Art"
        elif display_name and display_name != "Custom":
            category_dir = re.sub(r"[^a-zA-Z0-9_-]+", "_", display_name).strip("_")[:32] or "Characters"
        else:
            category_dir = "General"

        target_export_dir = EXPORT_IMAGES_DIR / category_dir
        target_export_dir.mkdir(parents=True, exist_ok=True)
        export_dest = target_export_dir / filename
        shutil.move(str(image_path), str(export_dest))
        image_path = export_dest
    except Exception as move_err:
        logger.warning(f"[ChatImage] Failed to classify/move to Export/Images: {move_err}")

    # Traits description
    hair_desc = char_info.hair_tags or "Tóc chuẩn thiết kế gốc"
    eye_desc = char_info.eye_tags or "Mắt anime sắc nét"
    outfit_desc = char_info.outfit_tags or "Trang phục đặc trưng"
    weapon_desc = char_info.weapon_tags or "Hiệu ứng chiến đấu"
    ref_line = f"- **Khóa dáng/mặt (Ref):** `{effective_ref}`\n" if effective_ref else ""

    markdown_text = (
        f"Đã tạo ảnh cho **{display_name}** theo yêu cầu của bạn!\n\n"
        f"**Thông số cấu hình:**\n"
        f"- **Tỉ lệ khung hình:** `{chosen_ratio}` ({width}×{height})\n"
        f"- **Định dạng file:** `{chosen_format}`\n"
        f"{ref_line}\n"
        f"**Đặc điểm ngoại hình chuẩn canonical:**\n"
        f"- **Tóc:** {hair_desc}\n"
        f"- **Mắt:** {eye_desc}\n"
        f"- **Trang phục:** {outfit_desc}\n"
        f"- **Hiệu ứng/Đồng hành:** {weapon_desc}\n\n"
        f"![{display_name}]({image_url})"
    )

    return {
        "success": True,
        "text": markdown_text,
        "image_url": image_url,
        "image_path": str(image_path),
        "character_name": display_name,
        "prompt": positive_prompt,
        "aspect_ratio": chosen_ratio,
        "dimensions": [width, height],
        "format": chosen_format,
        "ref_image_name": effective_ref,
    }
