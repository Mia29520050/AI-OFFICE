# -*- coding: utf-8 -*-
"""
app/chat_orchestrator.py
========================
ChatGPT/Claude-style Action Orchestrator for AI Office.

Provides 0ms rule-first intent classification and unified execution for:
- Video Generation (`detect_video_intent` -> `app.video_generator.generate_video`)
- Long-Term Memory Teaching (`detect_memory_intent` -> `app.memory_engine.learn_fact`)
- 3D Asset Generation (`detect_3d_intent` -> `app.blender_3d.generate_3d_asset`)
- Neural Voice / TTS (`detect_tts_intent` -> `app.voice_engine.DEFAULT_VOICE_ENGINE.synthesize_speech`)

Respects 6GB VRAM / 12GB RAM hardware locks (`VRAM_SEMAPHORE` + `free_ollama`)
and mandatory `F:\\AI-Office\\Export\\` output directories.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("chat_orchestrator")

# ---------------------------------------------------------------------------
# Exclusion patterns for meta-questions / coding requests
# ---------------------------------------------------------------------------
_META_EXCLUDE_PATTERNS = (
    r"\b(?:làm\s+sao|lam\s+sao|cách\s+nào|cach\s+nao|như\s+thế\s+nào|nhu\s+the\s+nao)\b",
    r"\b(?:hướng\s+dẫn|huong\s+dan|how\s+to|explain|giải\s+thích|giai\s+thich)\b",
    r"\b(?:có\s+thể\s+.{0,25}\s+không|co\s+the\s+.{0,25}\s+khong|có\s+biết\s+.{0,25}\s+không)\b",
    r"\b(?:viết\s+code|viet\s+code|viết\s+mã|viet\s+ma|write\s+code)\b",
)

_VIDEO_TRIGGERS = (
    "chuyển ảnh thành video",
    "chuyen anh thanh video",
    "tạo motion comic",
    "tao motion comic",
    "làm motion comic",
    "lam motion comic",
    "motion comic",
    "render video",
    "tạo video",
    "tao video",
    "làm video",
    "lam video",
    "sinh video",
    "làm clip",
    "lam clip",
    "tạo clip",
    "tao clip",
    "generate video",
    "create video",
    "make video",
    "make a video",
    "make a clip",
    "animate image",
)

_MEMORY_TRIGGERS = (
    "nhớ giúp anh",
    "nho giup anh",
    "nhớ giúp em",
    "nho giup em",
    "nhớ giúp tôi",
    "nho giup toi",
    "nhớ giúp mình",
    "nho giup minh",
    "nhớ giúp",
    "nho giup",
    "nhớ giùm",
    "nho gium",
    "hãy ghi nhớ",
    "hay ghi nho",
    "ghi nhớ",
    "ghi nho",
    "học cái này",
    "hoc cai nay",
    "từ nay hãy nhớ",
    "tu nay hay nho",
    "hãy nhớ",
    "hay nho",
    "remember that",
    "remember this",
    "note that",
)

_MEMORY_QUESTION_EXCLUDE = (
    r"\b(?:có\s+nhớ|co\s+nho|nhớ\s+không|nho\s+khong|nhớ\s+gì|nho\s+gi|do\s+you\s+remember)\b",
)

_3D_TRIGGERS = (
    "tạo model 3d",
    "tao model 3d",
    "tạo mô hình 3d",
    "tao mo hinh 3d",
    "dựng mô hình 3d",
    "dung mo hinh 3d",
    "dựng model 3d",
    "dung model 3d",
    "dựng 3d",
    "dung 3d",
    "tạo 3d",
    "tao 3d",
    "xuất file 3d",
    "xuat file 3d",
    "tạo file obj",
    "tao file obj",
    "tạo file glb",
    "tao file glb",
    "blender 3d",
    "generate 3d",
    "create 3d",
    "make 3d model",
    "make 3d",
)

_TTS_TRIGGERS = (
    "đọc thành tiếng",
    "doc thanh tieng",
    "chuyển thành giọng nói",
    "chuyen thanh giong noi",
    "tạo giọng nói",
    "tao giong noi",
    "lồng tiếng",
    "long tieng",
    "đọc giúp",
    "doc giup",
    "đọc giùm",
    "doc gium",
    "đọc to",
    "doc to",
    "text to speech",
    "read aloud",
    "speak this",
    "tts",
)

_VIDEO_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    "16:9": (480, 272),
    "9:16": (272, 480),
    "1:1": (384, 384),
    "3:4": (320, 432),
    "4:3": (432, 320),
}

_3D_TYPE_KEYWORDS: Tuple[Tuple[Tuple[str, ...], str, str], ...] = (
    (("kiếm", "kiem", "sword", "blade", "katana"), "sword", "weapon"),
    (("khiên", "khien", "shield"), "shield", "weapon"),
    (("rương", "ruong", "hòm", "hom", "thùng", "thung", "crate", "chest", "box"), "crate", "prop"),
    (("cột", "cot", "trụ", "tru", "pillar", "column"), "pillar", "environment"),
    (("pha lê", "pha le", "tinh thể", "tinh the", "đá quý", "crystal", "gem"), "crystal", "prop"),
    (("mặt phẳng", "mat phang", "sàn", "san", "plane", "ground"), "plane", "environment"),
    (("khối", "khoi", "lập phương", "lap phuong", "cube"), "cube", "prop"),
)


def _is_meta_question(lower_msg: str) -> bool:
    return any(re.search(pat, lower_msg, re.IGNORECASE) for pat in _META_EXCLUDE_PATTERNS)


def _match_trigger(message: str, triggers: Tuple[str, ...]) -> Tuple[bool, str]:
    """Match any trigger phrase (case-insensitive, word/phrase boundary) and return trailing text."""
    cleaned = (message or "").strip()
    if not cleaned:
        return False, ""
    lower = cleaned.lower()

    for tw in triggers:
        pattern = rf"(?:^|\s|[.,!?;:\"'(\[])({re.escape(tw)})(?=$|\s|[.,!?;:\"'!\)\]])"
        m = re.search(pattern, lower)
        if m:
            trailing = cleaned[m.end() :].strip()
            trailing = re.sub(
                r"^(?:cho\s+(?:tôi|anh|em|mình)|giúp\s+(?:tôi|anh|em|mình)|giùm\s+(?:tôi|anh|em|mình))\b",
                "",
                trailing,
                flags=re.IGNORECASE,
            ).strip()
            trailing = re.sub(r"^[:\-–—,]+\s*", "", trailing).strip()
            return True, trailing
    return False, ""


# ---------------------------------------------------------------------------
# 1. Rule-First Intent Classifiers (0ms)
# ---------------------------------------------------------------------------
def detect_video_intent(message: str) -> Tuple[bool, str]:
    """Detect video / motion comic generation intent and extract prompt."""
    cleaned = (message or "").strip()
    if not cleaned or _is_meta_question(cleaned.lower()):
        return False, ""

    matched, trailing = _match_trigger(cleaned, _VIDEO_TRIGGERS)
    if not matched:
        return False, ""

    prompt = re.sub(r"^(?:về|ve|clip|video)\s+", "", trailing, flags=re.IGNORECASE).strip()
    prompt = re.sub(r"\s+(?:nhé|nha|đi|di)$", "", prompt, flags=re.IGNORECASE).strip()
    if not prompt:
        prompt = "Smooth cinematic anime motion scene"
    return True, prompt


def detect_memory_intent(message: str) -> Tuple[bool, str]:
    """Detect user teach/remember intent and extract the fact to store."""
    cleaned = (message or "").strip()
    if not cleaned:
        return False, ""
    lower = cleaned.lower()
    if any(re.search(pat, lower, re.IGNORECASE) for pat in _MEMORY_QUESTION_EXCLUDE):
        return False, ""

    matched, trailing = _match_trigger(cleaned, _MEMORY_TRIGGERS)
    if not matched:
        return False, ""

    fact = re.sub(r"^(?:là|rằng|la|rang|rằng là)\s+", "", trailing, flags=re.IGNORECASE).strip()
    fact = fact.strip("\"' ")
    if not fact:
        return False, ""
    return True, fact


def detect_3d_intent(message: str) -> Tuple[bool, str]:
    """Detect 3D model/asset generation intent and extract description."""
    cleaned = (message or "").strip()
    if not cleaned or _is_meta_question(cleaned.lower()):
        return False, ""

    matched, trailing = _match_trigger(cleaned, _3D_TRIGGERS)
    if not matched:
        return False, ""

    desc = re.sub(r"^(?:hình|mô hình|model|về|của)\s+", "", trailing, flags=re.IGNORECASE).strip()
    desc = re.sub(r"\s+(?:nhé|nha|đi|di)$", "", desc, flags=re.IGNORECASE).strip()
    if not desc:
        desc = cleaned
    return True, desc


def detect_tts_intent(message: str) -> Tuple[bool, str]:
    """Detect direct Text-to-Speech / read-aloud intent and extract text to speak."""
    cleaned = (message or "").strip()
    if not cleaned or _is_meta_question(cleaned.lower()):
        return False, ""

    matched, trailing = _match_trigger(cleaned, _TTS_TRIGGERS)
    if not matched:
        return False, ""

    speech_text = re.sub(
        r"^(?:câu|đoạn|văn bản|nội dung|text)(?:\s+(?:này|sau|đây))?\s*[:\-]?\s*",
        "",
        trailing,
        flags=re.IGNORECASE,
    ).strip()
    speech_text = speech_text.strip("\"' ")
    if not speech_text:
        return False, ""
    return True, speech_text


# ---------------------------------------------------------------------------
# Internal Lazy Helpers & Resource Guards
# ---------------------------------------------------------------------------
def _extract_image_attachment(attachments: Optional[List[Any]]) -> Optional[str]:
    """Return the first local image path from chat attachments if available."""
    if not attachments:
        return None
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    for att in attachments:
        candidate: Optional[str] = None
        if isinstance(att, str):
            candidate = att
        elif isinstance(att, dict):
            candidate = att.get("path") or att.get("file_path") or att.get("local_path") or att.get("url")
        else:
            candidate = (
                getattr(att, "path", None)
                or getattr(att, "file_path", None)
                or getattr(att, "local_path", None)
                or getattr(att, "url", None)
            )
        if candidate and Path(str(candidate)).suffix.lower() in image_exts:
            p = Path(str(candidate))
            if p.is_file():
                return str(p)
    return None


def _resolve_3d_params(description: str, output_format: Optional[str]) -> Tuple[str, str, str, str]:
    """Map natural-language 3D description to (name, asset_type, mod_preset, export_format)."""
    lower = description.lower()
    asset_type = "cube"
    mod_preset = "prop"
    for keywords, atype, preset in _3D_TYPE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            asset_type = atype
            mod_preset = preset
            break

    fmt = (output_format or "").strip().lower()
    if fmt not in ("obj", "glb", "both"):
        if "obj" in lower and "glb" not in lower:
            fmt = "obj"
        elif "glb" in lower and "obj" not in lower:
            fmt = "glb"
        else:
            fmt = "both"

    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", description.strip())[:24].strip("_") or asset_type
    name = f"chat_{slug}"
    return name, asset_type, mod_preset, fmt


def _learn_memory_fact(fact: str) -> Dict[str, Any]:
    """Import memory_engine lazily (supports both app.memory_engine and memory_engine)."""
    try:
        from app import memory_engine  # type: ignore
    except ImportError:
        import memory_engine  # type: ignore
    return memory_engine.learn_fact(fact, category="fact", source="chat", importance=4)


async def _run_video_with_vram_guard(
    prompt: str,
    width: int,
    height: int,
    image_path: Optional[str],
) -> Dict[str, Any]:
    """Free Ollama VRAM and execute generate_video under VRAM_SEMAPHORE when distinct."""
    try:
        from app import video_generator  # type: ignore
    except ImportError:
        import video_generator  # type: ignore

    vram_sem = None
    free_ollama_fn = None
    try:
        from app import vram_guard  # type: ignore

        vram_sem = getattr(vram_guard, "VRAM_SEMAPHORE", None)
        free_ollama_fn = getattr(vram_guard, "free_ollama", None)
    except ImportError:
        pass

    vg_sem = video_generator.get_model_semaphore()

    async def _invoke() -> Dict[str, Any]:
        if free_ollama_fn is not None:
            try:
                await free_ollama_fn()
            except Exception as exc:
                logger.debug("free_ollama skipped/failed: %s", exc)
        return await video_generator.generate_video(
            prompt=prompt,
            width=width,
            height=height,
            image_path=image_path,
        )

    if vram_sem is not None and vram_sem is not vg_sem:
        async with vram_sem:
            return await _invoke()
    return await _invoke()


# ---------------------------------------------------------------------------
# 2. Unified Action Orchestrator
# ---------------------------------------------------------------------------
async def orchestrate_chat_action(
    message: str,
    attachments: Optional[List[Any]] = None,
    aspect_ratio: Optional[str] = None,
    output_format: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Classify and execute direct chat actions (memory, video, 3D, TTS).

    Returns ``{handled, text, action_type, artifacts}`` when an action is triggered,
    or ``None`` if the message should fall through to image generation / search / LLM.
    """
    # 1) Memory teaching
    is_mem, fact = detect_memory_intent(message)
    if is_mem:
        try:
            saved = await asyncio.to_thread(_learn_memory_fact, fact)
            return {
                "handled": True,
                "action_type": "memory",
                "text": f"Đã ghi nhớ: **{fact}**",
                "artifacts": [{"type": "memory", "content": fact, "record": saved}],
            }
        except Exception as exc:
            logger.warning("Memory learn_fact failed: %s", exc)
            return {
                "handled": True,
                "action_type": "memory",
                "text": f"⚠️ Không thể lưu ghi nhớ lúc này: `{exc}`",
                "artifacts": [],
            }

    # 2) Video generation
    is_video, video_prompt = detect_video_intent(message)
    if is_video:
        width, height = _VIDEO_DIMENSIONS.get((aspect_ratio or "").strip(), (480, 272))
        image_path = _extract_image_attachment(attachments)
        try:
            meta = await _run_video_with_vram_guard(
                prompt=video_prompt,
                width=width,
                height=height,
                image_path=image_path,
            )
            video_path = Path(str(meta.get("video_path", "")))
            filename = video_path.name
            video_url = f"/api/video/file/{filename}"
            mode = meta.get("mode", "offline_fallback")
            md_text = (
                f"Đã tạo video thành công!\n\n"
                f"- **Prompt:** {video_prompt}\n"
                f"- **Kích thước:** `{meta.get('width', width)}x{meta.get('height', height)}` | **Mode:** `{mode}`\n"
                f"- **Tệp xuất:** `{video_path}`\n"
                f"- **Xem / Tải video:** [{filename}]({video_url})"
            )
            return {
                "handled": True,
                "action_type": "video",
                "text": md_text,
                "artifacts": [
                    {
                        "type": "video",
                        "filename": filename,
                        "url": video_url,
                        "path": str(video_path),
                        "mode": mode,
                    }
                ],
            }
        except Exception as exc:
            logger.error("Video generation failed: %s", exc, exc_info=True)
            return {
                "handled": True,
                "action_type": "video",
                "text": f"⚠️ Đã xảy ra lỗi khi tạo video: `{exc}`",
                "artifacts": [],
            }

    # 3) 3D asset generation
    is_3d, desc_3d = detect_3d_intent(message)
    if is_3d:
        try:
            from app import blender_3d  # type: ignore
        except ImportError:
            import blender_3d  # type: ignore

        name, asset_type, mod_preset, fmt = _resolve_3d_params(desc_3d, output_format)
        try:
            meta = await asyncio.to_thread(
                blender_3d.generate_3d_asset,
                name=name,
                asset_type=asset_type,
                export_format=fmt,
                mod_preset=mod_preset,
            )
            exported_files: Dict[str, str] = meta.get("exported_files", {})
            artifacts = [
                {
                    "type": "3d",
                    "format": ext,
                    "filename": Path(fpath).name,
                    "path": fpath,
                }
                for ext, fpath in exported_files.items()
            ]
            files_lines = "\n".join(
                f"- **{ext.upper()}:** `{fpath}`" for ext, fpath in exported_files.items()
            )
            val = meta.get("validation", {})
            val_ok = val.get("passed", True)
            md_text = (
                f"Đã tạo mô hình 3D **{asset_type}** (`{name}`)!\n\n"
                f"{files_lines}\n"
                f"- **Kiểm định topology:** `{'PASS' if val_ok else 'WARN'}`"
            )
            return {
                "handled": True,
                "action_type": "3d",
                "text": md_text,
                "artifacts": artifacts,
            }
        except Exception as exc:
            logger.error("3D generation failed: %s", exc, exc_info=True)
            return {
                "handled": True,
                "action_type": "3d",
                "text": f"⚠️ Đã xảy ra lỗi khi tạo mô hình 3D: `{exc}`",
                "artifacts": [],
            }

    # 4) Voice / TTS
    is_tts, speech_text = detect_tts_intent(message)
    if is_tts:
        try:
            from app import voice_engine  # type: ignore
        except ImportError:
            import voice_engine  # type: ignore

        try:
            clip = await voice_engine.DEFAULT_VOICE_ENGINE.synthesize_speech(
                text=speech_text,
                export=True,
            )
            audio_path = Path(str(clip.exported_path or clip.file_path))
            filename = Path(str(clip.file_path)).name
            audio_url = f"/api/voice/audio/{filename}"
            md_text = (
                f"Đã tạo giọng đọc thành công!\n\n"
                f"- **Nội dung:** {speech_text}\n"
                f"- **Thời lượng:** `{clip.duration:.2f}s`\n"
                f"- **Tệp xuất:** `{audio_path}`\n"
                f"- **Nghe / Tải audio:** [{filename}]({audio_url})"
            )
            return {
                "handled": True,
                "action_type": "tts",
                "text": md_text,
                "artifacts": [
                    {
                        "type": "audio",
                        "filename": filename,
                        "url": audio_url,
                        "path": str(audio_path),
                        "duration": clip.duration,
                    }
                ],
            }
        except Exception as exc:
            logger.error("TTS generation failed: %s", exc, exc_info=True)
            return {
                "handled": True,
                "action_type": "tts",
                "text": f"⚠️ Đã xảy ra lỗi khi tạo giọng nói: `{exc}`",
                "artifacts": [],
            }

    return None
