"""LowVRAM Video Generation (Wan 1.3B) & De-AI Film Polish Pipeline (Muc 12).

Features:
- Integrates ComfyUI ``Wan 1.3B LowVRAM`` workflow
  (``NSFW_Wan_1.3B_e14_LowVRAM.json`` / ``wan_1.3B_exp_e14.safetensors``).
- Enforces 6GB VRAM lock via ``MODEL_SEMAPHORE`` (reusing ``app.main.MODEL_SEMAPHORE``
  when ``app.main`` is loaded, or a local ``asyncio.Semaphore(1)`` fallback).
- Graceful offline/headless fallback using ``app/motion_comic.py`` (when an input
  image is supplied) or ``imageio_ffmpeg`` procedural video synthesis.
- De-AI Film Polish filtergraph via FFmpeg:
  * Smooth motion interpolation (``minterpolate``)
  * Subtle organic film grain (``noise``)
  * Cinematic color balance & reduced AI plastic saturation (``eq`` + ``colorbalance``)
- Saves all MP4 outputs into ``F:\\AI-Office\\Export\\Video\\``.
- Exposes FastAPI routes via ``register_routes(app)``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import imageio_ffmpeg
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:
    from app.motion_comic import (
        MotionComicEngine,
        MotionConfig,
        MotionPanel,
        MotionStyle,
    )
except ImportError:
    from motion_comic import (  # type: ignore
        MotionComicEngine,
        MotionConfig,
        MotionPanel,
        MotionStyle,
    )

logger = logging.getLogger("video_generator")

ROOT_DIR = Path(__file__).resolve().parents[1]
EXPORT_VIDEO_DIR = Path(
    os.environ.get("AI_OFFICE_EXPORT_VIDEO_DIR", str(ROOT_DIR / "Export" / "Video"))
)
EXPORT_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

COMFY_URL = os.getenv("COMFYUI_HOST", os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")).rstrip("/")
WAN_WORKFLOW_PATH = Path(
    os.getenv(
        "WAN_WORKFLOW_PATH",
        r"F:\AI-Office\engine\ComfyUI\user\default\workflows\NSFW_Wan_1.3B_e14_LowVRAM.json",
    )
)
WAN_MODEL_PATH = Path(
    os.getenv(
        "WAN_MODEL_PATH",
        r"F:\AI-Office\engine\ComfyUI\models\diffusion_models\wan_1.3B_exp_e14.safetensors",
    )
)
WAN_CLIP_NAME = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
WAN_VAE_NAME = "wan_2.1_vae.safetensors"
WAN_UNET_NAME = "wan_1.3B_exp_e14.safetensors"

DEFAULT_NEGATIVE_PROMPT = (
    "overexposed, static, blurred details, subtitles, style, artwork, painting, "
    "still, overall gray, worst quality, low quality, JPEG compression residue, "
    "ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, "
    "deformed, disfigured, fused fingers, chaotic background, plastic AI skin"
)

DE_AI_PRESETS: Dict[str, Dict[str, Any]] = {
    "subtle": {
        "target_fps": 24,
        "motion_smooth": True,
        "grain_strength": 4,
        "saturation": 0.92,
        "contrast": 1.03,
        "gamma": 0.99,
        "warmth": 0.02,
        "cool_shadows": 0.02,
    },
    "cinematic": {
        "target_fps": 24,
        "motion_smooth": True,
        "grain_strength": 7,
        "saturation": 0.86,
        "contrast": 1.06,
        "gamma": 0.97,
        "warmth": 0.03,
        "cool_shadows": 0.03,
    },
    "heavy": {
        "target_fps": 30,
        "motion_smooth": True,
        "grain_strength": 11,
        "saturation": 0.80,
        "contrast": 1.08,
        "gamma": 0.96,
        "warmth": 0.04,
        "cool_shadows": 0.04,
    },
}

_FALLBACK_SEMAPHORE: Optional[asyncio.Semaphore] = None


def get_model_semaphore() -> asyncio.Semaphore:
    """Return shared ``MODEL_SEMAPHORE`` (6GB VRAM lock) from ``app.main`` if loaded."""
    main_mod = sys.modules.get("app.main")
    if main_mod is not None and hasattr(main_mod, "MODEL_SEMAPHORE"):
        return main_mod.MODEL_SEMAPHORE
    global _FALLBACK_SEMAPHORE
    if _FALLBACK_SEMAPHORE is None:
        _FALLBACK_SEMAPHORE = asyncio.Semaphore(1)
    return _FALLBACK_SEMAPHORE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_stem(name: str, prefix: str = "video") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", (name or "").strip()).strip("_")
    return cleaned or f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# ComfyUI Wan 1.3B LowVRAM Helpers
# ---------------------------------------------------------------------------
def inspect_wan_workflow(workflow_path: Optional[Path] = None) -> Dict[str, Any]:
    """Inspect Wan 1.3B LowVRAM workflow JSON (UTF-8 BOM safe) and model presence."""
    wf_path = workflow_path or WAN_WORKFLOW_PATH
    info: Dict[str, Any] = {
        "workflow_path": str(wf_path),
        "workflow_exists": wf_path.is_file(),
        "model_path": str(WAN_MODEL_PATH),
        "model_exists": WAN_MODEL_PATH.is_file(),
        "node_count": 0,
        "unet_name": WAN_UNET_NAME,
    }
    if wf_path.is_file():
        try:
            data = json.loads(wf_path.read_text(encoding="utf-8-sig"))
            nodes = data.get("nodes", []) if isinstance(data, dict) else []
            info["node_count"] = len(nodes)
            for node in nodes:
                if node.get("type") == "UNETLoader" and node.get("widgets_values"):
                    info["unet_name"] = node["widgets_values"][0]
        except Exception as exc:
            info["parse_error"] = str(exc)
    return info


def is_comfy_online(comfy_url: Optional[str] = None, timeout: float = 2.0) -> bool:
    """Check if local ComfyUI server is reachable."""
    base = (comfy_url or COMFY_URL).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/system_stats", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def build_wan_comfy_prompt(
    prompt: str,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    width: int = 480,
    height: int = 272,
    frames: int = 9,
    fps: int = 16,
    steps: int = 30,
    cfg: float = 6.0,
    seed: Optional[int] = None,
    filename_prefix: str = "video/Wan13B",
) -> Dict[str, Any]:
    """Build ComfyUI API-format prompt graph matching ``NSFW_Wan_1.3B_e14_LowVRAM.json``."""
    actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
    # Wan latent requires dimensions divisible by 16
    w = max(64, (int(width) // 16) * 16)
    h = max(64, (int(height) // 16) * 16)
    length = max(5, int(frames))

    return {
        "38": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": WAN_CLIP_NAME,
                "type": "wan",
                "device": "default",
            },
        },
        "39": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": WAN_VAE_NAME},
        },
        "37": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": WAN_UNET_NAME,
                "weight_dtype": "default",
            },
        },
        "48": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["37", 0], "shift": 8.0},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["38", 0]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["38", 0]},
        },
        "40": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {
                "width": w,
                "height": h,
                "length": length,
                "batch_size": 1,
            },
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": actual_seed,
                "steps": int(steps),
                "cfg": float(cfg),
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["48", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["40", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["39", 0]},
        },
        "49": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["8", 0], "fps": int(fps)},
        },
        "50": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["49", 0],
                "filename_prefix": filename_prefix,
                "format": "auto",
                "codec": "auto",
            },
        },
    }


def _submit_comfy_wan_prompt(
    prompt_graph: Dict[str, Any],
    out_path: Path,
    comfy_url: Optional[str] = None,
    timeout_secs: float = 300.0,
) -> Path:
    """Submit Wan 1.3B prompt to ComfyUI and download the resulting MP4."""
    base = (comfy_url or COMFY_URL).rstrip("/")
    client_id = uuid.uuid4().hex
    payload = json.dumps({"prompt": prompt_graph, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
    prompt_id = resp_data["prompt_id"]

    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        with urllib.request.urlopen(f"{base}/history/{prompt_id}", timeout=10) as h_resp:
            history = json.loads(h_resp.read().decode("utf-8"))
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_out in outputs.values():
                for key in ("videos", "gifs", "images"):
                    items = node_out.get(key) or []
                    for item in items:
                        filename = item.get("filename")
                        if not filename:
                            continue
                        params = urllib.parse.urlencode({
                            "filename": filename,
                            "subfolder": item.get("subfolder", ""),
                            "type": item.get("type", "output"),
                        })
                        with urllib.request.urlopen(f"{base}/view?{params}", timeout=30) as v_resp:
                            out_path.parent.mkdir(parents=True, exist_ok=True)
                            out_path.write_bytes(v_resp.read())
                        return out_path
            raise RuntimeError("ComfyUI finished Wan job but returned no video output.")
        time.sleep(1.5)

    raise TimeoutError(f"ComfyUI Wan 1.3B generation timed out after {timeout_secs}s")


# ---------------------------------------------------------------------------
# De-AI Film Polish (FFmpeg)
# ---------------------------------------------------------------------------
def build_de_ai_filtergraph(
    target_fps: int = 24,
    motion_smooth: bool = True,
    grain_strength: int = 6,
    saturation: float = 0.88,
    contrast: float = 1.05,
    gamma: float = 0.98,
    warmth: float = 0.03,
    cool_shadows: float = 0.03,
) -> str:
    """Build FFmpeg ``-vf`` filtergraph for De-AI Film Polish.

    Combines:
    1. Motion smoothing (``minterpolate``) to eliminate AI frame jitter
    2. Subtle organic film grain (``noise``) to break synthetic smoothness
    3. Cinematic color balance & saturation reduction (``eq`` + ``colorbalance``)
    """
    filters: List[str] = []

    if motion_smooth:
        fps_val = max(12, min(60, int(target_fps)))
        filters.append(
            f"minterpolate=fps={fps_val}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        )

    sat = max(0.3, min(1.5, float(saturation)))
    con = max(0.5, min(1.5, float(contrast)))
    gam = max(0.5, min(1.5, float(gamma)))
    filters.append(f"eq=saturation={sat:.2f}:contrast={con:.2f}:gamma={gam:.2f}")

    w = max(-0.2, min(0.2, float(warmth)))
    c = max(-0.2, min(0.2, float(cool_shadows)))
    filters.append(f"colorbalance=rs={w:.2f}:bs={-w:.2f}:rm={-c:.2f}:bm={c:.2f}")

    if grain_strength > 0:
        g = max(1, min(30, int(grain_strength)))
        filters.append(f"noise=alls={g}:allf=t+u")

    filters.append("format=yuv420p")
    return ",".join(filters)


def de_ai_enhance_video(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    preset: str = "cinematic",
    target_fps: Optional[int] = None,
    motion_smooth: Optional[bool] = None,
    grain_strength: Optional[int] = None,
    saturation: Optional[float] = None,
    contrast: Optional[float] = None,
) -> Dict[str, Any]:
    """Apply De-AI Film Polish to an MP4 video and save to ``Export/Video/``."""
    src = Path(input_path)
    if not src.is_file():
        raise FileNotFoundError(f"Input video not found: {src}")

    cfg = dict(DE_AI_PRESETS.get(preset, DE_AI_PRESETS["cinematic"]))
    if target_fps is not None:
        cfg["target_fps"] = target_fps
    if motion_smooth is not None:
        cfg["motion_smooth"] = motion_smooth
    if grain_strength is not None:
        cfg["grain_strength"] = grain_strength
    if saturation is not None:
        cfg["saturation"] = saturation
    if contrast is not None:
        cfg["contrast"] = contrast

    if output_path is not None:
        dst = Path(output_path)
    else:
        dst = EXPORT_VIDEO_DIR / f"{src.stem}_deai_{uuid.uuid4().hex[:6]}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)

    vf = build_de_ai_filtergraph(
        target_fps=cfg["target_fps"],
        motion_smooth=cfg["motion_smooth"],
        grain_strength=cfg["grain_strength"],
        saturation=cfg["saturation"],
        contrast=cfg["contrast"],
        gamma=cfg["gamma"],
        warmth=cfg["warmth"],
        cool_shadows=cfg["cool_shadows"],
    )

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    from app.proc_utils import run_hidden
    proc = run_hidden(cmd, capture_output=True, text=True, timeout=180, check=False)
    if proc.returncode != 0 or not dst.is_file():
        raise RuntimeError(f"FFmpeg De-AI enhancement failed: {proc.stderr[-800:]}")

    return {
        "input_path": str(src),
        "output_path": str(dst),
        "preset": preset,
        "filtergraph": vf,
        "file_size_bytes": dst.stat().st_size,
    }


# ---------------------------------------------------------------------------
# Offline / MotionComic Synthesis Fallback
# ---------------------------------------------------------------------------
def _generate_offline_mp4(
    out_path: Path,
    width: int = 480,
    height: int = 272,
    duration_secs: float = 2.0,
    fps: int = 16,
    image_path: Optional[str] = None,
) -> Path:
    """Generate a valid MP4 offline via MotionComicEngine (if image given) or ffmpeg."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if image_path and Path(image_path).is_file():
        engine = MotionComicEngine()
        panel = MotionPanel(
            panel_id="wan_fallback",
            image_path=str(image_path),
            motion_style=MotionStyle.ZOOM_IN,
            duration=max(1.5, float(duration_secs)),
        )
        cfg = MotionConfig(
            aspect_ratio="16:9",
            fps=max(16, int(fps)),
            enable_tts=False,
            enable_sfx=False,
            enable_anime4k=False,
            use_nvenc=False,
        )
        res = engine.render(panels=[panel], config=cfg, output_filename=out_path.stem)
        rendered = Path(res.video_path)
        if rendered.resolve() != out_path.resolve():
            out_path.write_bytes(rendered.read_bytes())
        return out_path

    w = max(64, (int(width) // 2) * 2)
    h = max(64, (int(height) // 2) * 2)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={w}x{h}:rate={max(12, int(fps))}:duration={max(1.0, duration_secs):.2f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    from app.proc_utils import run_hidden
    proc = run_hidden(cmd, capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode != 0 or not out_path.is_file():
        raise RuntimeError(f"Offline MP4 synthesis failed: {proc.stderr[-600:]}")
    return out_path


# ---------------------------------------------------------------------------
# High-Level Video Generation Orchestrator (VRAM-locked)
# ---------------------------------------------------------------------------
async def generate_video(
    prompt: str,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    width: int = 480,
    height: int = 272,
    frames: int = 17,
    fps: int = 16,
    steps: int = 30,
    cfg: float = 6.0,
    seed: Optional[int] = None,
    image_path: Optional[str] = None,
    apply_de_ai: bool = True,
    de_ai_preset: str = "cinematic",
    motion_smooth: bool = True,
    output_name: Optional[str] = None,
    use_comfy: bool = True,
    export_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a video using Wan 1.3B LowVRAM (with 6GB VRAM lock) or offline fallback,
    then optionally apply De-AI Film Polish.
    """
    out_dir = export_dir or EXPORT_VIDEO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(output_name or "", prefix="wan13b")
    raw_path = out_dir / f"{stem}_raw.mp4"
    final_path = out_dir / f"{stem}.mp4"

    sem = get_model_semaphore()
    mode = "offline_fallback"
    comfy_prompt_graph = build_wan_comfy_prompt(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        frames=frames,
        fps=fps,
        steps=steps,
        cfg=cfg,
        seed=seed,
        filename_prefix=f"video/{stem}",
    )

    async with sem:
        if use_comfy and is_comfy_online():
            try:
                await asyncio.to_thread(_submit_comfy_wan_prompt, comfy_prompt_graph, raw_path)
                mode = "comfy_wan_1.3b"
            except Exception as exc:
                logger.warning("ComfyUI Wan 1.3B failed, falling back offline: %s", exc)
                duration = max(1.5, frames / max(1, fps))
                await asyncio.to_thread(
                    _generate_offline_mp4, raw_path, width, height, duration, fps, image_path
                )
        else:
            duration = max(1.5, frames / max(1, fps))
            await asyncio.to_thread(
                _generate_offline_mp4, raw_path, width, height, duration, fps, image_path
            )

    de_ai_info: Optional[Dict[str, Any]] = None
    if apply_de_ai:
        de_ai_info = await asyncio.to_thread(
            de_ai_enhance_video,
            raw_path,
            final_path,
            de_ai_preset,
            None,
            motion_smooth,
        )
    else:
        final_path.write_bytes(raw_path.read_bytes())

    metadata = {
        "name": stem,
        "mode": mode,
        "prompt": prompt,
        "width": width,
        "height": height,
        "frames": frames,
        "fps": fps,
        "raw_video_path": str(raw_path),
        "video_path": str(final_path),
        "file_size_bytes": final_path.stat().st_size,
        "de_ai_applied": apply_de_ai,
        "de_ai_info": de_ai_info,
        "created_at": _utc_now(),
    }
    meta_path = out_dir / f"{stem}_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metadata["metadata_path"] = str(meta_path)
    return metadata


# ---------------------------------------------------------------------------
# FastAPI Routes
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/video", tags=["LowVRAM Video & De-AI Polish"])


class GenerateVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT
    width: int = Field(default=480, ge=64, le=1920)
    height: int = Field(default=272, ge=64, le=1080)
    frames: int = Field(default=17, ge=5, le=121)
    fps: int = Field(default=16, ge=8, le=60)
    steps: int = Field(default=30, ge=1, le=100)
    cfg: float = Field(default=6.0, ge=1.0, le=20.0)
    seed: Optional[int] = None
    image_path: Optional[str] = None
    apply_de_ai: bool = True
    de_ai_preset: str = "cinematic"
    motion_smooth: bool = True
    output_name: Optional[str] = None
    use_comfy: bool = True


class DeAIEnhanceRequest(BaseModel):
    input_path: str
    preset: str = "cinematic"
    target_fps: Optional[int] = Field(default=None, ge=12, le=60)
    motion_smooth: Optional[bool] = None
    grain_strength: Optional[int] = Field(default=None, ge=0, le=30)
    saturation: Optional[float] = Field(default=None, ge=0.3, le=1.5)
    contrast: Optional[float] = Field(default=None, ge=0.5, le=1.5)
    output_name: Optional[str] = None


@router.get("/status")
def get_video_status() -> Dict[str, Any]:
    """Return ComfyUI Wan 1.3B, FFmpeg, VRAM semaphore, and export directory status."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    wan_info = inspect_wan_workflow()
    sem = get_model_semaphore()
    return {
        "comfy_online": is_comfy_online(),
        "comfy_url": COMFY_URL,
        "wan_workflow_available": wan_info["workflow_exists"],
        "wan_model_available": wan_info["model_exists"],
        "wan_info": wan_info,
        "ffmpeg_available": bool(ffmpeg_exe and Path(ffmpeg_exe).is_file()),
        "ffmpeg_path": ffmpeg_exe,
        "export_dir": str(EXPORT_VIDEO_DIR),
        "vram_lock_locked": sem.locked(),
        "de_ai_presets": list(DE_AI_PRESETS.keys()),
    }


@router.get("/exports")
def list_video_exports() -> Dict[str, Any]:
    """List exported MP4 videos in F:\\AI-Office\\Export\\Video\\."""
    EXPORT_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    for p in sorted(EXPORT_VIDEO_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        stat = p.stat()
        items.append({
            "filename": p.name,
            "path": str(p),
            "format": p.suffix.lstrip(".").lower(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"export_dir": str(EXPORT_VIDEO_DIR), "count": len(items), "files": items}


@router.post("/generate")
async def api_generate_video(req: GenerateVideoRequest) -> Dict[str, Any]:
    """Generate a video via Wan 1.3B LowVRAM (or offline fallback) + De-AI Film Polish."""
    try:
        res = await generate_video(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            width=req.width,
            height=req.height,
            frames=req.frames,
            fps=req.fps,
            steps=req.steps,
            cfg=req.cfg,
            seed=req.seed,
            image_path=req.image_path,
            apply_de_ai=req.apply_de_ai,
            de_ai_preset=req.de_ai_preset,
            motion_smooth=req.motion_smooth,
            output_name=req.output_name,
            use_comfy=req.use_comfy,
        )
        return {"success": True, **res}
    except Exception as exc:
        logger.exception("Video generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/de-ai-enhance")
async def api_de_ai_enhance(req: DeAIEnhanceRequest) -> Dict[str, Any]:
    """Apply De-AI Film Polish to an existing MP4 video."""
    try:
        out_path: Optional[Path] = None
        if req.output_name:
            out_path = EXPORT_VIDEO_DIR / f"{_safe_stem(req.output_name, 'deai')}.mp4"
        res = await asyncio.to_thread(
            de_ai_enhance_video,
            req.input_path,
            out_path,
            req.preset,
            req.target_fps,
            req.motion_smooth,
            req.grain_strength,
            req.saturation,
            req.contrast,
        )
        return {"success": True, **res}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("De-AI enhancement failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/file/{filename}")
def serve_video_file(filename: str):
    """Serve an exported MP4 video file from F:\\AI-Office\\Export\\Video\\."""
    safe_name = os.path.basename(filename)
    file_path = EXPORT_VIDEO_DIR / safe_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Video file not found: {safe_name}")
    return FileResponse(file_path, media_type="video/mp4", filename=safe_name)


def register_routes(app: FastAPI) -> None:
    """Register LowVRAM Video & De-AI Polish routes on FastAPI app."""
    app.include_router(router)
