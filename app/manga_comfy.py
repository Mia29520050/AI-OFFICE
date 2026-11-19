"""Manga Studio - ComfyUI Adapter & Resource Scheduler.

This module provides the integration layer between AI Office's Manga Studio and
ComfyUI (default http://127.0.0.1:8188). It includes:
1. Strict ResourceScheduler: asyncio.Semaphore(1) and GPU lock to protect the
   6GB VRAM / 12GB RAM hardware, serializing inference and coordinating with
   MODEL_SEMAPHORE.
2. Model Registry: local filesystem discovery across checkpoints, diffusion_models,
   LoRAs, and VAEs, with automatic detection of 2D manga/anime models.
3. Workflow Discovery: discovery and validation of ComfyUI workflows (.json),
   with production-grade built-in workflows for Manga B&W and Manga Color.
4. Intelligent Mock/Template Fallback: generates high-fidelity placeholder panel
   art assets using Pillow (screentones, speed lines, composition framing,
   metadata HUD) whenever ComfyUI is offline or lacks a 2D checkpoint.
5. Persistent Job Queue & Recovery: tracks seeds, prompts, attempts, and recovers
   interrupted jobs from SQLite across application restarts.
"""

from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import logging
import math
import os
import random
import re
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Callable

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("manga_comfy")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Path & Environment Constants
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "office.db"
DEFAULT_MANGA_DIR = DATA_DIR / "manga"

DEFAULT_COMFY_URL = os.getenv("COMFYUI_HOST", "http://127.0.0.1:8188").rstrip("/")
DEFAULT_COMFY_PATH = Path(os.getenv("COMFYUI_PATH", r"F:\AI\ComfyUI"))
DEFAULT_FONT_PATH = ROOT_DIR / "app" / "ui" / "assets" / "Inter-Variable.ttf"

# Hardware protection constants for 6GB VRAM / 12GB RAM environment
DEFAULT_GENERATION_TIMEOUT_SECS = 180.0
DEFAULT_CONNECT_TIMEOUT_SECS = 3.0


def utc_now() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class GenerationMode(str, Enum):
    REAL = "real"
    MOCK = "mock"


class MockReason(str, Enum):
    OFFLINE = "offline"
    NO_CHECKPOINT = "no_checkpoint"
    MANUAL_MOCK = "manual_mock"
    ERROR_FALLBACK = "error_fallback"


class ArtStyle(str, Enum):
    MANGA_BW = "manga_bw"
    MANGA_COLOR = "manga_color"
    ANIME = "anime"
    SKETCH = "sketch"


# ---------------------------------------------------------------------------
# Pydantic Schemas & DTOs
# ---------------------------------------------------------------------------
class ModelInfo(BaseModel):
    name: str
    category: str  # checkpoint, diffusion_model, lora, vae, text_encoder
    subfolder: str
    file_path: str
    size_bytes: int = 0
    is_2d_manga: bool = False
    recommended_for: list[str] = Field(default_factory=list)


class ModelRegistry(BaseModel):
    checkpoints: list[ModelInfo] = Field(default_factory=list)
    diffusion_models: list[ModelInfo] = Field(default_factory=list)
    loras: list[ModelInfo] = Field(default_factory=list)
    vaes: list[ModelInfo] = Field(default_factory=list)
    has_2d_manga_checkpoint: bool = False
    active_checkpoint: str | None = None
    summary: str = ""


class WorkflowInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    path: str = ""
    category: str = "general"  # manga_bw, manga_color, video_wan, general
    is_builtin: bool = False
    node_count: int = 0
    required_models: list[str] = Field(default_factory=list)
    supported_aspect_ratios: list[str] = Field(default_factory=lambda: ["1:1", "3:4", "9:16", "16:9"])


class ComfySystemStats(BaseModel):
    is_online: bool = False
    url: str = DEFAULT_COMFY_URL
    comfy_path: str = str(DEFAULT_COMFY_PATH)
    devices: list[dict[str, Any]] = Field(default_factory=list)
    vram_total_mb: float = 0.0
    vram_free_mb: float = 0.0
    ram_total_mb: float = 0.0
    ram_free_mb: float = 0.0
    active_queue_count: int = 0
    has_2d_manga_checkpoint: bool = False
    active_checkpoint: str | None = None
    recommended_mode: str = "mock"  # "real" or "mock"
    hardware_warning: str | None = None


class PanelArtRequest(BaseModel):
    panel_id: str = Field(..., description="Unique identifier for the manga panel")
    page_id: str = Field(default="", description="Parent storyboard page identifier")
    chapter_id: str = Field(default="", description="Parent chapter identifier")
    series_id: str = Field(default="", description="Parent manga series identifier")
    prompt: str = Field(..., min_length=1, max_length=5000, description="Positive prompt describing character, action, angle")
    negative_prompt: str = Field(
        default="low quality, bad anatomy, deformed, blurry, bad hands, speech bubble, text, watermark, signature",
        max_length=2000,
    )
    seed: int = Field(default=-1, description="-1 for random seed, or specific integer for deterministic reproduction")
    width: int = Field(default=768, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    steps: int = Field(default=20, ge=1, le=80)
    cfg_scale: float = Field(default=7.0, ge=1.0, le=20.0)
    sampler_name: str = Field(default="euler_ancestral")
    scheduler: str = Field(default="normal")
    art_style: str = Field(default="manga_bw", description="manga_bw or manga_color")
    workflow_id: str | None = Field(default=None)
    model_name: str | None = Field(default=None)
    character_refs: list[dict[str, Any]] = Field(default_factory=list)
    force_mock: bool = Field(default=False, description="Explicitly force intelligent mock generation")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PanelArtResult(BaseModel):
    job_id: str
    panel_id: str
    status: str
    mode: str  # real or mock
    mock_reason: str | None = None
    image_path: str
    relative_path: str
    width: int
    height: int
    seed: int
    checksum: str
    file_size: int
    duration_seconds: float
    prompt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtJob(BaseModel):
    id: str
    panel_id: str
    series_id: str = ""
    chapter_id: str = ""
    page_id: str = ""
    status: str = JobStatus.PENDING.value
    mode: str = GenerationMode.MOCK.value
    mock_reason: str = ""
    attempt: int = 1
    max_attempts: int = 3
    seed: int = 0
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 768
    height: int = 1024
    art_style: str = "manga_bw"
    model_name: str = ""
    workflow_id: str = ""
    input_json: str = "{}"
    output_asset_path: str = ""
    checksum: str = ""
    file_size: int = 0
    error_text: str = ""
    duration_seconds: float = 0.0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# Strict ResourceScheduler (GPU Lock & Concurrency Control)
# ---------------------------------------------------------------------------
class ResourceScheduler:
    """Strict resource scheduler to protect 6GB VRAM / 12GB RAM hardware.

    Ensures that only ONE GPU-intensive generation runs at any time,
    serializing execution and preventing CUDA Out-Of-Memory (OOM) or RAM thrashing.
    Supports optional coordination with an external semaphore (e.g. MODEL_SEMAPHORE).
    """

    def __init__(
        self,
        max_concurrent: int = 1,
        external_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._external_semaphore = external_semaphore
        self._thread_lock = threading.Lock()
        self._active_job_id: str | None = None
        self._active_start_time: float = 0.0
        self._lock_count: int = 0
        self._cancelled_jobs: set[str] = set()

    @property
    def is_locked(self) -> bool:
        return self._active_job_id is not None or self._semaphore.locked()

    @property
    def active_job_id(self) -> str | None:
        return self._active_job_id

    def cancel_job(self, job_id: str) -> None:
        with self._thread_lock:
            self._cancelled_jobs.add(job_id)

    def is_job_cancelled(self, job_id: str) -> bool:
        with self._thread_lock:
            return job_id in self._cancelled_jobs

    @asynccontextmanager
    async def acquire(
        self, job_id: str, timeout_secs: float = DEFAULT_GENERATION_TIMEOUT_SECS
    ) -> AsyncGenerator[None, None]:
        """Acquire the GPU lock with timeout and multi-semaphore coordination."""
        start_wait = time.monotonic()
        external_acquired = False
        local_acquired = False

        try:
            # 1. Coordinate with external semaphore (e.g. MODEL_SEMAPHORE) if present
            if self._external_semaphore is not None:
                try:
                    await asyncio.wait_for(
                        self._external_semaphore.acquire(),
                        timeout=max(5.0, timeout_secs - (time.monotonic() - start_wait)),
                    )
                    external_acquired = True
                except asyncio.TimeoutError:
                    raise TimeoutError(f"ResourceScheduler: LLM/GPU lock acquisition timed out for job {job_id}")

            # 2. Acquire local concurrency semaphore (1)
            remaining_time = max(5.0, timeout_secs - (time.monotonic() - start_wait))
            try:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining_time)
                local_acquired = True
            except asyncio.TimeoutError:
                raise TimeoutError(f"ResourceScheduler: Local GPU semaphore acquisition timed out for job {job_id}")

            with self._thread_lock:
                self._active_job_id = job_id
                self._active_start_time = time.monotonic()
                self._lock_count += 1
                logger.info("ResourceScheduler acquired GPU lock for job %s (active count=%d)", job_id, self._lock_count)

            yield

        finally:
            with self._thread_lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None
                self._cancelled_jobs.discard(job_id)

            if local_acquired:
                self._semaphore.release()
            if external_acquired and self._external_semaphore is not None:
                self._external_semaphore.release()

            # Encourage clean memory state after GPU heavy tasks
            gc.collect()


# ---------------------------------------------------------------------------
# Model Registry Manager
# ---------------------------------------------------------------------------
class ModelRegistryManager:
    """Discovers and inspects models in ComfyUI directory and live API."""

    _2D_MANGA_PATTERNS = [
        r"animagine",
        r"manga",
        r"anime",
        r"illustrious",
        r"counterfeit",
        r"anything",
        r"meinamix",
        r"pastelmix",
        r"pony",
        r"comic",
        r"lineart",
        r"novelai",
        r"darkas",
    ]

    def __init__(self, comfy_path: Path = DEFAULT_COMFY_PATH) -> None:
        self.comfy_path = comfy_path
        self.models_dir = comfy_path / "models"

    def scan_local_models(self) -> ModelRegistry:
        """Scan disk in F:\\AI\\ComfyUI\\models for installed checkpoints, diffusions, and LoRAs."""
        checkpoints: list[ModelInfo] = []
        diffusion_models: list[ModelInfo] = []
        loras: list[ModelInfo] = []
        vaes: list[ModelInfo] = []

        if self.models_dir.exists():
            # Checkpoints
            ckpt_dir = self.models_dir / "checkpoints"
            if ckpt_dir.exists():
                for p in ckpt_dir.glob("**/*"):
                    if p.is_file() and p.suffix.lower() in {".safetensors", ".ckpt", ".bin", ".pt"}:
                        is_2d = self._is_2d_manga_model(p.name)
                        checkpoints.append(
                            ModelInfo(
                                name=p.name,
                                category="checkpoint",
                                subfolder=str(p.parent.relative_to(ckpt_dir)),
                                file_path=str(p),
                                size_bytes=p.stat().st_size,
                                is_2d_manga=is_2d,
                                recommended_for=["manga_bw", "manga_color"] if is_2d else ["general"],
                            )
                        )

            # Diffusion models (e.g. Wan, SD3, FLUX)
            diff_dir = self.models_dir / "diffusion_models"
            if diff_dir.exists():
                for p in diff_dir.glob("**/*"):
                    if p.is_file() and p.suffix.lower() in {".safetensors", ".ckpt", ".bin"}:
                        is_2d = self._is_2d_manga_model(p.name)
                        diffusion_models.append(
                            ModelInfo(
                                name=p.name,
                                category="diffusion_model",
                                subfolder=str(p.parent.relative_to(diff_dir)),
                                file_path=str(p),
                                size_bytes=p.stat().st_size,
                                is_2d_manga=is_2d,
                                recommended_for=["video_wan"] if "wan" in p.name.lower() else ["general"],
                            )
                        )

            # LoRAs
            lora_dir = self.models_dir / "loras"
            if lora_dir.exists():
                for p in lora_dir.glob("**/*"):
                    if p.is_file() and p.suffix.lower() in {".safetensors", ".pt"}:
                        is_2d = self._is_2d_manga_model(p.name)
                        loras.append(
                            ModelInfo(
                                name=p.name,
                                category="lora",
                                subfolder=str(p.parent.relative_to(lora_dir)),
                                file_path=str(p),
                                size_bytes=p.stat().st_size,
                                is_2d_manga=is_2d,
                                recommended_for=["manga_screentone"] if "screentone" in p.name.lower() else ["general"],
                            )
                        )

            # VAEs
            vae_dir = self.models_dir / "vae"
            if vae_dir.exists():
                for p in vae_dir.glob("**/*"):
                    if p.is_file() and p.suffix.lower() in {".safetensors", ".pt", ".bin"}:
                        vaes.append(
                            ModelInfo(
                                name=p.name,
                                category="vae",
                                subfolder=str(p.parent.relative_to(vae_dir)),
                                file_path=str(p),
                                size_bytes=p.stat().st_size,
                                is_2d_manga=False,
                                recommended_for=["general"],
                            )
                        )

        has_2d = any(c.is_2d_manga for c in checkpoints)
        active_ckpt = next((c.name for c in checkpoints if c.is_2d_manga), None)
        if not active_ckpt and checkpoints:
            active_ckpt = checkpoints[0].name

        summary = (
            f"Found {len(checkpoints)} checkpoints (2D manga: {sum(1 for c in checkpoints if c.is_2d_manga)}), "
            f"{len(diffusion_models)} diffusion models, {len(loras)} LoRAs."
        )

        return ModelRegistry(
            checkpoints=checkpoints,
            diffusion_models=diffusion_models,
            loras=loras,
            vaes=vaes,
            has_2d_manga_checkpoint=has_2d,
            active_checkpoint=active_ckpt,
            summary=summary,
        )

    def _is_2d_manga_model(self, filename: str) -> bool:
        fn_lower = filename.lower()
        return any(re.search(pat, fn_lower) for pat in self._2D_MANGA_PATTERNS)


# ---------------------------------------------------------------------------
# Workflow Discovery & Built-in Templates
# ---------------------------------------------------------------------------
class WorkflowDiscovery:
    """Discovers, parses and builds prompt payloads for ComfyUI workflows."""

    def __init__(
        self,
        comfy_path: Path = DEFAULT_COMFY_PATH,
        manga_dir: Path = DEFAULT_MANGA_DIR,
    ) -> None:
        self.comfy_path = comfy_path
        self.manga_dir = manga_dir
        self.user_workflows_dir = comfy_path / "user" / "default" / "workflows"
        self.manga_workflows_dir = manga_dir / "workflows"

    def list_workflows(self) -> list[WorkflowInfo]:
        """Scan disk and return all available workflows plus built-in production templates."""
        workflows: list[WorkflowInfo] = []

        # 1. Built-in production workflows
        workflows.extend(self._get_builtin_workflows())

        # 2. ComfyUI user workflows
        if self.user_workflows_dir.exists():
            for p in self.user_workflows_dir.glob("*.json"):
                info = self._parse_workflow_file(p, is_builtin=False)
                if info:
                    workflows.append(info)

        # 3. Manga studio custom workflows
        if self.manga_workflows_dir.exists():
            for p in self.manga_workflows_dir.glob("*.json"):
                info = self._parse_workflow_file(p, is_builtin=False)
                if info:
                    workflows.append(info)

        return workflows

    def _get_builtin_workflows(self) -> list[WorkflowInfo]:
        return [
            WorkflowInfo(
                id="builtin_manga_bw",
                name="Standard Manga B&W (2D Screentone)",
                description="Optimized black & white manga generation with dynamic ink shading, speed lines, and screentones.",
                category="manga_bw",
                is_builtin=True,
                node_count=7,
                required_models=["CheckpointLoaderSimple", "EmptyLatentImage", "KSampler"],
                supported_aspect_ratios=["3:4", "1:1", "9:16", "16:9"],
            ),
            WorkflowInfo(
                id="builtin_manga_color",
                name="Japanese Color Manga (Cel-Shaded)",
                description="High-contrast Japanese colored manga style with rich palette and clean anime lineart.",
                category="manga_color",
                is_builtin=True,
                node_count=7,
                required_models=["CheckpointLoaderSimple", "EmptyLatentImage", "KSampler"],
                supported_aspect_ratios=["3:4", "1:1", "9:16", "16:9"],
            ),
            WorkflowInfo(
                id="builtin_wan_video_preview",
                name="Wan 1.3B Low-VRAM Video Frame",
                description="Text-to-video single-frame preview for Wan 1.3B diffusion model on low-VRAM machines.",
                category="video_wan",
                is_builtin=True,
                node_count=12,
                required_models=["wan_1.3B_exp_e14.safetensors"],
                supported_aspect_ratios=["16:9"],
            ),
        ]

    def _parse_workflow_file(self, path: Path, is_builtin: bool = False) -> WorkflowInfo | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            name = path.stem.replace("_", " ").title()
            node_count = 0
            category = "general"

            if isinstance(raw, dict):
                if "nodes" in raw and isinstance(raw["nodes"], list):
                    node_count = len(raw["nodes"])
                elif any(isinstance(v, dict) and "class_type" in v for v in raw.values()):
                    node_count = len(raw)

            fn_lower = path.name.lower()
            if "wan" in fn_lower or "video" in fn_lower:
                category = "video_wan"
            elif "manga" in fn_lower and "color" in fn_lower:
                category = "manga_color"
            elif "manga" in fn_lower:
                category = "manga_bw"

            return WorkflowInfo(
                id=f"file_{path.stem}",
                name=name,
                description=f"Local workflow loaded from {path.name}",
                path=str(path),
                category=category,
                is_builtin=is_builtin,
                node_count=node_count,
            )
        except Exception as e:
            logger.warning("Failed to parse workflow file %s: %s", path, e)
            return None

    def build_prompt_graph(
        self,
        request: PanelArtRequest,
        model_name: str,
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        """Construct standard ComfyUI API prompt graph."""
        pos_prompt = request.prompt
        if request.art_style == "manga_bw":
            pos_prompt = f"monochrome, manga lineart, comic screentone, high contrast, clean lines, masterpiece, {pos_prompt}"
        elif request.art_style == "manga_color":
            pos_prompt = f"colored manga, vibrant anime illustration, cel shading, detailed background, masterpiece, {pos_prompt}"

        neg_prompt = request.negative_prompt

        # Standard 7-node standard SD1.5 / SDXL generation pipeline
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model_name},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": pos_prompt, "clip": ["1", 1]},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": neg_prompt, "clip": ["1", 1]},
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": request.width,
                    "height": request.height,
                    "batch_size": 1,
                },
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": request.seed,
                    "steps": request.steps,
                    "cfg": request.cfg_scale,
                    "sampler_name": request.sampler_name,
                    "scheduler": request.scheduler,
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"manga_panel_{request.panel_id}",
                    "images": ["6", 0],
                },
            },
        }


# ---------------------------------------------------------------------------
# Intelligent Mock / Template Engine (Pillow-Based)
# ---------------------------------------------------------------------------
class MockPanelGenerator:
    """Generates authentic manga placeholder art when ComfyUI is offline or lacks 2D models.

    Renders authentic manga aesthetic elements:
    - Halftone / screentone dot patterns (in B&W mode)
    - Dynamic radial speed lines (shusen)
    - Stylized compositional silhouette framing
    - Japanese color anime gradient & vignette (in Color mode)
    - Crisp manga panel border
    - Clean metadata overlay HUD with Vietnamese Unicode support
    """

    def __init__(self, font_path: Path = DEFAULT_FONT_PATH) -> None:
        self.font_path = font_path

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if self.font_path.exists():
            try:
                return ImageFont.truetype(str(self.font_path), size)
            except Exception:
                pass
        return ImageFont.load_default()

    def generate(
        self,
        request: PanelArtRequest,
        output_path: Path,
        reason: MockReason,
    ) -> tuple[Path, str, int]:
        """Generate a valid PNG manga draft panel asset and save to disk."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        w, h = request.width, request.height

        is_bw = request.art_style != "manga_color"
        bg_color = (248, 248, 250) if is_bw else (235, 240, 248)

        # 1. Base Canvas
        img = Image.new("RGB", (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # 2. Authentic Manga Textures & Framing
        if is_bw:
            self._render_bw_screentone_and_lines(draw, w, h, request.seed)
        else:
            self._render_color_anime_gradient(draw, w, h, request.seed)

        # 3. Silhouette / Rule-of-Thirds Composition Motif
        self._render_composition_motif(draw, w, h, is_bw, request.seed)

        # 4. Manga Panel Border & Gutters
        gutter = 14
        border_width = 4
        border_color = (18, 18, 24)
        draw.rectangle(
            [gutter, gutter, w - gutter, h - gutter],
            outline=border_color,
            width=border_width,
        )

        # 5. Metadata Overlay HUD
        self._render_overlay_hud(draw, w, h, request, reason, is_bw)

        # 6. Save image to disk
        img.save(str(output_path), format="PNG", optimize=True)

        # 7. Checksum & size
        data_bytes = output_path.read_bytes()
        checksum = hashlib.sha256(data_bytes).hexdigest()
        file_size = len(data_bytes)

        logger.info(
            "Generated mock manga panel: %s (%dx%d, %d bytes, checksum=%s)",
            output_path.name,
            w,
            h,
            file_size,
            checksum[:8],
        )
        return output_path, checksum, file_size

    def _render_bw_screentone_and_lines(
        self, draw: ImageDraw.ImageDraw, w: int, h: int, seed: int
    ) -> None:
        """Render screentone halftone dots and manga speed lines."""
        rng = random.Random(seed)

        # Halftone screentone dots in background
        dot_spacing = 16
        dot_color = (214, 216, 222)
        for y in range(24, h - 24, dot_spacing):
            offset_x = (y // dot_spacing % 2) * (dot_spacing // 2)
            for x in range(24 + offset_x, w - 24, dot_spacing):
                draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=dot_color)

        # Dynamic Manga Speed Lines (radiating from edges toward focal center)
        cx, cy = w // 2, int(h * 0.42)
        line_color = (200, 204, 212)
        num_lines = 48
        for i in range(num_lines):
            angle = (2 * math.pi / num_lines) * i + rng.uniform(-0.04, 0.04)
            r_inner = rng.uniform(min(w, h) * 0.22, min(w, h) * 0.35)
            r_outer = max(w, h) * 0.9
            x1 = cx + math.cos(angle) * r_inner
            y1 = cy + math.sin(angle) * r_inner
            x2 = cx + math.cos(angle) * r_outer
            y2 = cy + math.sin(angle) * r_outer
            draw.line([(x1, y1), (x2, y2)], fill=line_color, width=1)

    def _render_color_anime_gradient(
        self, draw: ImageDraw.ImageDraw, w: int, h: int, seed: int
    ) -> None:
        """Render soft Japanese twilight anime gradient."""
        # Simple vertical gradient simulation
        top_color = (58, 74, 107)  # Dusk indigo
        mid_color = (154, 107, 126)  # Warm mauve
        bot_color = (214, 165, 120)  # Sunset amber

        for y in range(0, h, 2):
            t = y / max(1, h)
            if t < 0.5:
                sub_t = t * 2.0
                r = int(top_color[0] + (mid_color[0] - top_color[0]) * sub_t)
                g = int(top_color[1] + (mid_color[1] - top_color[1]) * sub_t)
                b = int(top_color[2] + (mid_color[2] - top_color[2]) * sub_t)
            else:
                sub_t = (t - 0.5) * 2.0
                r = int(mid_color[0] + (bot_color[0] - mid_color[0]) * sub_t)
                g = int(mid_color[1] + (bot_color[1] - mid_color[1]) * sub_t)
                b = int(mid_color[2] + (bot_color[2] - mid_color[2]) * sub_t)
            draw.line([(0, y), (w, y)], fill=(r, g, b), width=2)

    def _render_composition_motif(
        self, draw: ImageDraw.ImageDraw, w: int, h: int, is_bw: bool, seed: int
    ) -> None:
        """Render compositional manga silhouette / focus motif."""
        cx, cy = w // 2, int(h * 0.44)
        sil_color = (32, 34, 42) if is_bw else (28, 32, 48)

        # Tasteful manga character head/shoulder silhouette
        head_radius = int(min(w, h) * 0.12)
        head_y = cy - head_radius
        draw.ellipse(
            [cx - head_radius, head_y - head_radius, cx + head_radius, head_y + head_radius],
            fill=sil_color,
            outline=(255, 255, 255) if is_bw else (220, 220, 240),
            width=2,
        )

        # Torso / shoulders
        shoulder_w = int(head_radius * 2.6)
        shoulder_top = head_y + int(head_radius * 0.8)
        shoulder_bot = cy + int(head_radius * 2.2)
        draw.polygon(
            [
                (cx - shoulder_w // 2, shoulder_bot),
                (cx - head_radius, shoulder_top),
                (cx + head_radius, shoulder_top),
                (cx + shoulder_w // 2, shoulder_bot),
            ],
            fill=sil_color,
        )

        # Rule of thirds subtle reference crosshair
        cross_color = (180, 184, 195) if is_bw else (200, 200, 220)
        draw.line([(cx - 15, cy), (cx + 15, cy)], fill=cross_color, width=1)
        draw.line([(cx, cy - 15), (cx, cy + 15)], fill=cross_color, width=1)

    def _render_overlay_hud(
        self,
        draw: ImageDraw.ImageDraw,
        w: int,
        h: int,
        request: PanelArtRequest,
        reason: MockReason,
        is_bw: bool,
    ) -> None:
        """Render informative HUD badge and prompt card."""
        font_sm = self._get_font(13)
        font_md = self._get_font(15)
        font_lg = self._get_font(18)

        # 1. Header Badges
        # Studio Tag
        draw.rectangle([24, 24, 220, 52], fill=(20, 22, 28))
        draw.text((34, 30), "MANGA STUDIO DRAFT", fill=(255, 255, 255), font=font_md)

        # Mock Reason Badge
        reason_label = {
            MockReason.OFFLINE: "COMFYUI OFFLINE",
            MockReason.NO_CHECKPOINT: "NO 2D CHECKPOINT",
            MockReason.MANUAL_MOCK: "MOCK PREVIEW",
            MockReason.ERROR_FALLBACK: "FALLBACK SAFEGUARD",
        }.get(reason, "MOCK ASSET")

        badge_bg = (180, 83, 9) if reason == MockReason.OFFLINE else (67, 56, 202)
        draw.rectangle([w - 240, 24, w - 24, 52], fill=badge_bg)
        draw.text((w - 228, 30), f"⚡ {reason_label}", fill=(255, 255, 255), font=font_md)

        # 2. Bottom Information Card
        card_h = min(220, int(h * 0.28))
        card_top = h - card_h - 24
        card_rect = [24, card_top, w - 24, h - 24]

        card_bg = (245, 246, 248) if is_bw else (24, 28, 40)
        card_border = (60, 64, 75)
        card_text_color = (25, 28, 36) if is_bw else (240, 242, 248)
        card_sub_color = (100, 105, 120) if is_bw else (170, 175, 195)

        draw.rectangle(card_rect, fill=card_bg, outline=card_border, width=2)

        # Panel Identity line
        panel_line = f"Panel #{request.panel_id}   •   Seed: {request.seed}   •   Style: {request.art_style.upper()}"
        draw.text((36, card_top + 14), panel_line, fill=card_text_color, font=font_lg)

        dims_line = f"Resolution: {w}x{h} px   •   Status: Valid Asset   •   Engine: Intelligent Mock"
        draw.text((36, card_top + 40), dims_line, fill=card_sub_color, font=font_sm)

        # Reason Explanatory notice
        notice = "Notice: Generating with authentic Manga Studio vector/screentone fallback so pipeline never crashes."
        if reason == MockReason.NO_CHECKPOINT:
            notice = "Notice: No 2D Manga checkpoint found in F:\\AI\\ComfyUI\\models\\checkpoints. Using preview draft."
        draw.text((36, card_top + 62), notice, fill=(200, 50, 50) if is_bw else (255, 160, 160), font=font_sm)

        # Prompt Excerpt with simple word wrapping
        draw.line([(36, card_top + 88), (w - 36, card_top + 88)], fill=(210, 214, 224), width=1)
        draw.text((36, card_top + 96), "Prompt:", fill=card_text_color, font=font_md)

        words = request.prompt.split()
        lines: list[str] = []
        cur_line = ""
        max_chars = max(40, int((w - 80) / 9.5))
        for word in words:
            if len(cur_line) + len(word) + 1 <= max_chars:
                cur_line = f"{cur_line} {word}".strip()
            else:
                lines.append(cur_line)
                cur_line = word
                if len(lines) >= 3:
                    break
        if cur_line and len(lines) < 3:
            lines.append(cur_line)

        y_offset = card_top + 120
        for l in lines[:3]:
            draw.text((36, y_offset), l, fill=card_sub_color, font=font_sm)
            y_offset += 20


# ---------------------------------------------------------------------------
# ComfyUI HTTP Client
# ---------------------------------------------------------------------------
class ComfyUIClient:
    """Asynchronous client communicating directly with ComfyUI REST API."""

    def __init__(self, base_url: str = DEFAULT_COMFY_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_system_stats(self, timeout: float = DEFAULT_CONNECT_TIMEOUT_SECS) -> dict[str, Any] | None:
        """Call GET /system_stats to verify server health and hardware state."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(f"{self.base_url}/system_stats")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return None

    async def get_object_info(self, timeout: float = DEFAULT_CONNECT_TIMEOUT_SECS) -> dict[str, Any] | None:
        """Call GET /object_info to retrieve available nodes and inputs."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(f"{self.base_url}/object_info")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return None

    async def queue_prompt(
        self, prompt_graph: dict[str, Any], client_id: str, timeout: float = 10.0
    ) -> str:
        """Call POST /prompt to submit a prompt graph to ComfyUI."""
        payload = {"prompt": prompt_graph, "client_id": client_id}
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(f"{self.base_url}/prompt", json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"ComfyUI prompt submission failed ({res.status_code}): {res.text[:300]}")
            data = res.json()
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"ComfyUI did not return prompt_id: {data}")
            return prompt_id

    async def get_history(self, prompt_id: str, timeout: float = 5.0) -> dict[str, Any] | None:
        """Call GET /history/{prompt_id} to check job completion and output files."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(f"{self.base_url}/history/{prompt_id}")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return None

    async def interrupt(self) -> bool:
        """Call POST /interrupt to abort the currently running prompt."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.post(f"{self.base_url}/interrupt")
                return res.status_code == 200
        except Exception:
            return False

    async def free_memory(self, unload_models: bool = False) -> bool:
        """Call POST /free to release cached memory in ComfyUI."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.post(
                    f"{self.base_url}/free",
                    json={"unload_models": unload_models, "free_memory": True},
                )
                return res.status_code == 200
        except Exception:
            return False

    async def download_image(
        self, filename: str, subfolder: str = "", folder_type: str = "output"
    ) -> bytes:
        """Download output image from ComfyUI /view."""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(f"{self.base_url}/view", params=params)
            if res.status_code != 200:
                raise RuntimeError(f"Failed to download image from ComfyUI: {res.status_code}")
            return res.content


# ---------------------------------------------------------------------------
# ComfyAdapter Core Class
# ---------------------------------------------------------------------------
class ComfyAdapter:
    """Primary facade coordinating ComfyUI inference, mock fallbacks, and job queues."""

    def __init__(
        self,
        base_url: str = DEFAULT_COMFY_URL,
        comfy_path: Path = DEFAULT_COMFY_PATH,
        manga_dir: Path = DEFAULT_MANGA_DIR,
        db_path: Path | str = DEFAULT_DB_PATH,
        db_getter: Callable[[], sqlite3.Connection] | None = None,
        external_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.comfy_path = comfy_path
        self.manga_dir = manga_dir
        self.db_path = Path(db_path)
        self._db_getter = db_getter

        # Sub-components
        self.client = ComfyUIClient(self.base_url)
        self.scheduler = ResourceScheduler(
            max_concurrent=1, external_semaphore=external_semaphore
        )
        self.model_manager = ModelRegistryManager(self.comfy_path)
        self.workflow_discovery = WorkflowDiscovery(self.comfy_path, self.manga_dir)
        self.mock_generator = MockPanelGenerator(DEFAULT_FONT_PATH)

        # Client identifier for ComfyUI websocket/queue
        self.client_id = f"aioffice_manga_{uuid.uuid4().hex[:8]}"

        # Initialize SQLite tables
        self.ensure_tables()

    def get_db(self) -> sqlite3.Connection:
        if self._db_getter is not None:
            return self._db_getter()
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_tables(self) -> None:
        """Create manga_art_jobs and manga_assets tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.get_db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS manga_art_jobs (
                    id TEXT PRIMARY KEY,
                    panel_id TEXT NOT NULL,
                    series_id TEXT NOT NULL DEFAULT '',
                    chapter_id TEXT NOT NULL DEFAULT '',
                    page_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    mock_reason TEXT NOT NULL DEFAULT '',
                    attempt INTEGER NOT NULL DEFAULT 1,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    seed INTEGER NOT NULL,
                    prompt TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    width INTEGER NOT NULL DEFAULT 768,
                    height INTEGER NOT NULL DEFAULT 1024,
                    art_style TEXT NOT NULL DEFAULT 'manga_bw',
                    model_name TEXT NOT NULL DEFAULT '',
                    workflow_id TEXT NOT NULL DEFAULT '',
                    input_json TEXT NOT NULL DEFAULT '{}',
                    output_asset_path TEXT NOT NULL DEFAULT '',
                    checksum TEXT NOT NULL DEFAULT '',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    error_text TEXT NOT NULL DEFAULT '',
                    duration_seconds REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_manga_art_jobs_panel ON manga_art_jobs(panel_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_manga_art_jobs_status ON manga_art_jobs(status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_manga_art_jobs_chapter ON manga_art_jobs(chapter_id)")

            db.execute(
                """CREATE TABLE IF NOT EXISTS manga_assets (
                    id TEXT PRIMARY KEY,
                    series_id TEXT NOT NULL DEFAULT '',
                    owner_type TEXT NOT NULL DEFAULT 'panel',
                    owner_id TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    checksum TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_manga_assets_owner ON manga_assets(owner_type, owner_id)")

    async def get_system_stats(self) -> ComfySystemStats:
        """Inspect ComfyUI status, VRAM, and model readiness."""
        raw_stats = await self.client.get_system_stats()
        models = self.model_manager.scan_local_models()

        if not raw_stats:
            return ComfySystemStats(
                is_online=False,
                url=self.base_url,
                comfy_path=str(self.comfy_path),
                devices=[],
                has_2d_manga_checkpoint=models.has_2d_manga_checkpoint,
                active_checkpoint=models.active_checkpoint,
                recommended_mode="mock",
                hardware_warning="ComfyUI is offline. Intelligent Mock mode will generate placeholder panel art safely.",
            )

        devices = raw_stats.get("devices", [])
        vram_total_mb = 0.0
        vram_free_mb = 0.0
        if devices:
            d0 = devices[0]
            vram_total_mb = round(d0.get("vram_total", 0) / (1024 * 1024), 1)
            vram_free_mb = round(d0.get("vram_free", 0) / (1024 * 1024), 1)

        warning = None
        if vram_total_mb > 0 and vram_total_mb < 7000:
            warning = f"Detected {vram_total_mb}MB VRAM. Strict ResourceScheduler lock is active to protect hardware."

        rec_mode = "real" if models.has_2d_manga_checkpoint else "mock"

        return ComfySystemStats(
            is_online=True,
            url=self.base_url,
            comfy_path=str(self.comfy_path),
            devices=devices,
            vram_total_mb=vram_total_mb,
            vram_free_mb=vram_free_mb,
            has_2d_manga_checkpoint=models.has_2d_manga_checkpoint,
            active_checkpoint=models.active_checkpoint,
            recommended_mode=rec_mode,
            hardware_warning=warning,
        )

    def get_model_registry(self) -> ModelRegistry:
        return self.model_manager.scan_local_models()

    def discover_workflows(self) -> list[WorkflowInfo]:
        return self.workflow_discovery.list_workflows()

    # -----------------------------------------------------------------------
    # Job CRUD & Persistence
    # -----------------------------------------------------------------------
    def create_job(self, request: PanelArtRequest) -> ArtJob:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        seed = request.seed if request.seed >= 0 else random.randint(100_000, 999_999_999)

        job = ArtJob(
            id=job_id,
            panel_id=request.panel_id,
            series_id=request.series_id,
            chapter_id=request.chapter_id,
            page_id=request.page_id,
            status=JobStatus.PENDING.value,
            mode=GenerationMode.MOCK.value if request.force_mock else GenerationMode.REAL.value,
            seed=seed,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            art_style=request.art_style,
            model_name=request.model_name or "",
            workflow_id=request.workflow_id or "builtin_manga_bw",
            input_json=json.dumps(request.model_dump(), ensure_ascii=False),
        )

        with self.get_db() as db:
            db.execute(
                """INSERT INTO manga_art_jobs(
                    id, panel_id, series_id, chapter_id, page_id, status, mode, mock_reason,
                    attempt, max_attempts, seed, prompt, negative_prompt, width, height,
                    art_style, model_name, workflow_id, input_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.id,
                    job.panel_id,
                    job.series_id,
                    job.chapter_id,
                    job.page_id,
                    job.status,
                    job.mode,
                    job.mock_reason,
                    job.attempt,
                    job.max_attempts,
                    job.seed,
                    job.prompt,
                    job.negative_prompt,
                    job.width,
                    job.height,
                    job.art_style,
                    job.model_name,
                    job.workflow_id,
                    job.input_json,
                    job.created_at,
                    job.updated_at,
                ),
            )
            db.commit()
        return job

    def update_job(self, job_id: str, **kwargs: Any) -> ArtJob | None:
        kwargs["updated_at"] = utc_now()
        fields = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values()) + [job_id]

        with self.get_db() as db:
            db.execute(f"UPDATE manga_art_jobs SET {fields} WHERE id=?", values)
            db.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> ArtJob | None:
        with self.get_db() as db:
            row = db.execute("SELECT * FROM manga_art_jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            return ArtJob(**dict(row))

    def list_jobs(
        self,
        series_id: str | None = None,
        chapter_id: str | None = None,
        panel_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ArtJob]:
        query = "SELECT * FROM manga_art_jobs WHERE 1=1"
        params: list[Any] = []
        if series_id:
            query += " AND series_id=?"
            params.append(series_id)
        if chapter_id:
            query += " AND chapter_id=?"
            params.append(chapter_id)
        if panel_id:
            query += " AND panel_id=?"
            params.append(panel_id)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.get_db() as db:
            rows = db.execute(query, params).fetchall()
            return [ArtJob(**dict(r)) for r in rows]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an existing job and signal ComfyUI if running."""
        self.scheduler.cancel_job(job_id)
        job = self.get_job(job_id)
        if not job or job.status in {JobStatus.COMPLETED.value, JobStatus.CANCELLED.value}:
            return False

        if self.scheduler.active_job_id == job_id:
            asyncio.create_task(self.client.interrupt())

        self.update_job(
            job_id,
            status=JobStatus.CANCELLED.value,
            error_text="Job cancelled by user request.",
        )
        return True

    def recover_interrupted_jobs(self) -> list[ArtJob]:
        """Detect and recover jobs left in 'running' or 'pending' state across restarts."""
        recovered: list[ArtJob] = []
        with self.get_db() as db:
            rows = db.execute(
                "SELECT * FROM manga_art_jobs WHERE status IN (?, ?)",
                (JobStatus.RUNNING.value, JobStatus.PENDING.value),
            ).fetchall()
            for row in rows:
                job_id = row["id"]
                logger.warning("Recovering interrupted art job %s (previous status: %s)", job_id, row["status"])
                db.execute(
                    """UPDATE manga_art_jobs
                       SET status=?, error_text=?, updated_at=?
                       WHERE id=?""",
                    (
                        JobStatus.INTERRUPTED.value,
                        "Interrupted by application restart or process termination.",
                        utc_now(),
                        job_id,
                    ),
                )
            db.commit()
        for row in rows:
            rec = self.get_job(row["id"])
            if rec:
                recovered.append(rec)
        return recovered

    # -----------------------------------------------------------------------
    # Panel Art Generation Pipeline
    # -----------------------------------------------------------------------
    def _determine_target_path(self, request: PanelArtRequest, seed: int) -> Path:
        """Resolve panel asset output path on F: drive."""
        if request.series_id and request.chapter_id:
            target_dir = (
                self.manga_dir
                / "projects"
                / request.series_id
                / "chapters"
                / request.chapter_id
                / "panels"
                / request.panel_id
            )
        else:
            target_dir = self.manga_dir / "panels" / request.panel_id

        target_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        filename = f"panel_{request.panel_id}_{ts}_{seed}.png"
        return target_dir / filename

    async def generate_panel_art(self, request: PanelArtRequest) -> PanelArtResult:
        """Execute panel art generation protected by ResourceScheduler.

        If ComfyUI is online and has a 2D manga checkpoint, generates via diffusion.
        If ComfyUI is offline or has no 2D checkpoint or fails, seamlessly and safely
        falls back to MockPanelGenerator so the pipeline NEVER crashes!
        """
        # 1. Normalize seed and initialize job
        if request.seed < 0:
            request.seed = random.randint(100_000, 999_999_999)

        job = self.create_job(request)
        target_path = self._determine_target_path(request, request.seed)
        start_time = time.monotonic()

        # 2. Acquire strict ResourceScheduler lock (Semaphore 1)
        async with self.scheduler.acquire(job.id):
            self.update_job(job.id, status=JobStatus.RUNNING.value)

            stats = await self.get_system_stats()
            should_mock = (
                request.force_mock
                or (not stats.is_online)
                or (not stats.has_2d_manga_checkpoint)
            )

            mock_reason = MockReason.MANUAL_MOCK
            if not stats.is_online:
                mock_reason = MockReason.OFFLINE
            elif not stats.has_2d_manga_checkpoint:
                mock_reason = MockReason.NO_CHECKPOINT

            # A. REAL GENERATION PATH
            if not should_mock:
                try:
                    logger.info("Executing real ComfyUI generation for panel %s", request.panel_id)
                    model_to_use = request.model_name or stats.active_checkpoint or "sd15_manga.safetensors"
                    prompt_graph = self.workflow_discovery.build_prompt_graph(
                        request, model_to_use, request.workflow_id
                    )

                    prompt_id = await self.client.queue_prompt(prompt_graph, self.client_id)
                    output_bytes = await self._poll_and_download(prompt_id, job.id)

                    target_path.write_bytes(output_bytes)
                    checksum = hashlib.sha256(output_bytes).hexdigest()
                    file_size = len(output_bytes)
                    duration = round(time.monotonic() - start_time, 2)

                    self._register_asset(request, target_path, checksum)

                    self.update_job(
                        job.id,
                        status=JobStatus.COMPLETED.value,
                        mode=GenerationMode.REAL.value,
                        output_asset_path=str(target_path),
                        checksum=checksum,
                        file_size=file_size,
                        duration_seconds=duration,
                    )

                    # Trigger VRAM cleanup after real run
                    await self.client.free_memory(unload_models=False)

                    return PanelArtResult(
                        job_id=job.id,
                        panel_id=request.panel_id,
                        status=JobStatus.COMPLETED.value,
                        mode=GenerationMode.REAL.value,
                        image_path=str(target_path),
                        relative_path=str(target_path.relative_to(self.manga_dir.parent)),
                        width=request.width,
                        height=request.height,
                        seed=request.seed,
                        checksum=checksum,
                        file_size=file_size,
                        duration_seconds=duration,
                        prompt=request.prompt,
                        metadata=request.metadata,
                    )
                except Exception as e:
                    logger.error(
                        "Real ComfyUI generation failed for job %s: %s. Falling back to intelligent Mock engine.",
                        job.id,
                        e,
                    )
                    mock_reason = MockReason.ERROR_FALLBACK

            # B. INTELLIGENT MOCK FALLBACK PATH (Offline / No Model / Error)
            logger.info(
                "Generating intelligent Mock panel art asset for %s (reason: %s)",
                request.panel_id,
                mock_reason.value,
            )
            saved_path, checksum, file_size = self.mock_generator.generate(
                request, target_path, mock_reason
            )
            duration = round(time.monotonic() - start_time, 2)

            self._register_asset(request, saved_path, checksum)

            self.update_job(
                job.id,
                status=JobStatus.COMPLETED.value,
                mode=GenerationMode.MOCK.value,
                mock_reason=mock_reason.value,
                output_asset_path=str(saved_path),
                checksum=checksum,
                file_size=file_size,
                duration_seconds=duration,
            )

            return PanelArtResult(
                job_id=job.id,
                panel_id=request.panel_id,
                status=JobStatus.COMPLETED.value,
                mode=GenerationMode.MOCK.value,
                mock_reason=mock_reason.value,
                image_path=str(saved_path),
                relative_path=str(saved_path.relative_to(self.manga_dir.parent)),
                width=request.width,
                height=request.height,
                seed=request.seed,
                checksum=checksum,
                file_size=file_size,
                duration_seconds=duration,
                prompt=request.prompt,
                metadata=request.metadata,
            )

    async def _poll_and_download(self, prompt_id: str, job_id: str) -> bytes:
        """Poll ComfyUI history until completion and download resulting image."""
        start = time.monotonic()
        while time.monotonic() - start < DEFAULT_GENERATION_TIMEOUT_SECS:
            if self.scheduler.is_job_cancelled(job_id):
                await self.client.interrupt()
                raise RuntimeError(f"Art job {job_id} was cancelled.")

            history = await self.client.get_history(prompt_id)
            if history and prompt_id in history:
                prompt_output = history[prompt_id]
                outputs = prompt_output.get("outputs", {})
                for node_id, node_out in outputs.items():
                    images = node_out.get("images", [])
                    if images:
                        img_info = images[0]
                        filename = img_info["filename"]
                        subfolder = img_info.get("subfolder", "")
                        folder_type = img_info.get("type", "output")
                        return await self.client.download_image(filename, subfolder, folder_type)

            await asyncio.sleep(1.2)

        raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {DEFAULT_GENERATION_TIMEOUT_SECS}s")

    def _register_asset(self, request: PanelArtRequest, file_path: Path, checksum: str) -> None:
        """Record generated asset in manga_assets table."""
        asset_id = f"asset_{uuid.uuid4().hex[:12]}"
        meta = {
            "panel_id": request.panel_id,
            "chapter_id": request.chapter_id,
            "series_id": request.series_id,
            "seed": request.seed,
            "style": request.art_style,
            "width": request.width,
            "height": request.height,
        }
        with self.get_db() as db:
            db.execute(
                """INSERT INTO manga_assets(
                    id, series_id, owner_type, owner_id, file_path, metadata_json, checksum, created_at
                ) VALUES (?, ?, 'panel', ?, ?, ?, ?, ?)""",
                (
                    asset_id,
                    request.series_id,
                    request.panel_id,
                    str(file_path),
                    json.dumps(meta, ensure_ascii=False),
                    checksum,
                    utc_now(),
                ),
            )
            db.commit()

    async def retry_job(self, job_id: str, new_seed: bool = False) -> PanelArtResult:
        """Retry a failed or interrupted job."""
        job = self.get_job(job_id)
        if not job:
            raise HTTPException(404, f"Job {job_id} not found.")

        req_dict = json.loads(job.input_json)
        if new_seed:
            req_dict["seed"] = random.randint(100_000, 999_999_999)
        else:
            req_dict["seed"] = job.seed

        self.update_job(job_id, attempt=job.attempt + 1)
        req = PanelArtRequest(**req_dict)
        return await self.generate_panel_art(req)


# ---------------------------------------------------------------------------
# Global / Singleton Instance
# ---------------------------------------------------------------------------
_GLOBAL_ADAPTER: ComfyAdapter | None = None


def get_comfy_adapter(
    external_semaphore: asyncio.Semaphore | None = None,
    db_getter: Callable[[], sqlite3.Connection] | None = None,
) -> ComfyAdapter:
    """Retrieve or initialize the global ComfyAdapter instance."""
    global _GLOBAL_ADAPTER
    if _GLOBAL_ADAPTER is None:
        _GLOBAL_ADAPTER = ComfyAdapter(
            external_semaphore=external_semaphore,
            db_getter=db_getter,
        )
    return _GLOBAL_ADAPTER


# ---------------------------------------------------------------------------
# FastAPI Router Registration
# ---------------------------------------------------------------------------
def register_comfy_routes(
    app: FastAPI, adapter: ComfyAdapter | None = None
) -> APIRouter:
    """Register ComfyUI adapter and panel art generation endpoints on FastAPI."""
    router = APIRouter(prefix="/api/manga/comfy", tags=["Manga ComfyUI Adapter"])
    adp = adapter or get_comfy_adapter()

    @router.get("/status", response_model=ComfySystemStats)
    async def get_status() -> ComfySystemStats:
        return await adp.get_system_stats()

    @router.get("/models", response_model=ModelRegistry)
    async def get_models() -> ModelRegistry:
        return adp.get_model_registry()

    @router.get("/workflows", response_model=list[WorkflowInfo])
    async def get_workflows() -> list[WorkflowInfo]:
        return adp.discover_workflows()

    @router.post("/generate", response_model=PanelArtResult)
    async def generate_panel(request: PanelArtRequest) -> PanelArtResult:
        return await adp.generate_panel_art(request)

    @router.post("/jobs", response_model=ArtJob)
    async def submit_job(request: PanelArtRequest) -> ArtJob:
        job = adp.create_job(request)
        asyncio.create_task(adp.generate_panel_art(request))
        return job

    @router.get("/jobs", response_model=list[ArtJob])
    async def list_jobs(
        series_id: str | None = Query(default=None),
        chapter_id: str | None = Query(default=None),
        panel_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[ArtJob]:
        return adp.list_jobs(
            series_id=series_id,
            chapter_id=chapter_id,
            panel_id=panel_id,
            status=status,
            limit=limit,
        )

    @router.get("/jobs/{job_id}", response_model=ArtJob)
    async def get_job(job_id: str) -> ArtJob:
        job = adp.get_job(job_id)
        if not job:
            raise HTTPException(404, f"Job {job_id} not found.")
        return job

    @router.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        success = adp.cancel_job(job_id)
        return {"success": success, "job_id": job_id}

    @router.post("/jobs/{job_id}/retry", response_model=PanelArtResult)
    async def retry_job(
        job_id: str, new_seed: bool = Query(default=False)
    ) -> PanelArtResult:
        return await adp.retry_job(job_id, new_seed=new_seed)

    @router.post("/recover", response_model=list[ArtJob])
    async def recover_interrupted() -> list[ArtJob]:
        return adp.recover_interrupted_jobs()

    @router.post("/free-memory")
    async def free_memory() -> dict[str, Any]:
        comfy_ok = await adp.client.free_memory(unload_models=False)
        gc.collect()
        return {"success": True, "comfy_free_called": comfy_ok}

    app.include_router(router)
    return router
