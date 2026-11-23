from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File

logger = logging.getLogger("ai_office.manga_koharu")

DEFAULT_KOHARU_URL = "http://127.0.0.1:7878"


@dataclass
class KoharuHealthStatus:
    is_online: bool
    version: str = "unknown"
    device: str = "cpu"
    vram_usage_mb: float = 0.0
    models_loaded: list[str] = field(default_factory=list)


class KoharuSidecarClient:
    """Client communicating with the headless Koharu Rust sidecar process.

    Protects 6GB VRAM hardware by serializing GPU usage via ResourceScheduler.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_KOHARU_URL,
        scheduler: Any | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.scheduler = scheduler
        self.timeout = timeout_seconds

    async def get_health(self) -> KoharuHealthStatus:
        """Query health and VRAM status of the Koharu sidecar."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/health")
                if res.status_code == 200:
                    data = res.json()
                    return KoharuHealthStatus(
                        is_online=True,
                        version=data.get("version", "1.0.0"),
                        device=data.get("device", "cuda"),
                        vram_usage_mb=float(data.get("vram_usage_mb", 0.0)),
                        models_loaded=data.get("models_loaded", []),
                    )
        except Exception:
            pass

        return KoharuHealthStatus(is_online=False)

    async def detect_bubbles(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """Detect speech bubbles and text regions in manga page."""
        health = await self.get_health()
        if not health.is_online:
            logger.info("Koharu sidecar is offline; returning empty detection result.")
            return []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            files = {"file": ("page.png", image_bytes, "image/png")}
            res = await client.post(f"{self.base_url}/api/detect", files=files)
            res.raise_for_status()
            data = res.json()
            return data.get("boxes", [])

    async def inpaint(self, image_bytes: bytes, mask_bytes: bytes) -> bytes:
        """Perform LaMa inpainting to remove text while preserving line art & screentones.

        Protected by ResourceScheduler to prevent VRAM collision with ComfyUI.
        """
        health = await self.get_health()
        if not health.is_online:
            logger.info("Koharu sidecar is offline; fallback to returning original image.")
            return image_bytes

        # If scheduler is present, acquire lock to guard 6GB VRAM
        lock_ctx = (
            self.scheduler.acquire("koharu_inpaint")
            if (self.scheduler and hasattr(self.scheduler, "acquire"))
            else asyncio.sleep(0)
        )

        async with lock_ctx:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                files = {
                    "image": ("page.png", image_bytes, "image/png"),
                    "mask": ("mask.png", mask_bytes, "image/png"),
                }
                res = await client.post(f"{self.base_url}/api/inpaint", files=files)
                res.raise_for_status()
                return res.content

    async def ocr(self, image_bytes: bytes, lang: str = "ja") -> list[dict[str, Any]]:
        """Run OCR on detected manga speech bubbles."""
        health = await self.get_health()
        if not health.is_online:
            return []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            files = {"file": ("bubble.png", image_bytes, "image/png")}
            res = await client.post(
                f"{self.base_url}/api/ocr",
                files=files,
                data={"lang": lang},
            )
            res.raise_for_status()
            data = res.json()
            return data.get("texts", [])


def register_routes(app: FastAPI, scheduler: Any | None = None) -> None:
    client = KoharuSidecarClient(scheduler=scheduler)

    @app.get("/api/manga/koharu/status")
    async def koharu_status() -> dict[str, Any]:
        status = await client.get_health()
        return {
            "is_online": status.is_online,
            "version": status.version,
            "device": status.device,
            "vram_usage_mb": status.vram_usage_mb,
            "models_loaded": status.models_loaded,
        }

    @app.post("/api/manga/koharu/detect")
    async def koharu_detect(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        boxes = await client.detect_bubbles(content)
        return {"boxes": boxes, "count": len(boxes)}
