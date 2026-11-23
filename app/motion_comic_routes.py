"""FastAPI REST API routes for Motion Comic and Animation Video Studio."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, Body, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

try:
    from app.anime4k_upscaler import Anime4KUpscaler
    from app.motion_comic import (
        OUTPUT_DIR,
        TEMP_DIR,
        AspectRatio,
        MotionComicEngine,
        MotionComicResult,
        MotionConfig,
        MotionPanel,
        MotionStyle,
    )
    from app.voice_engine import VoiceEngine, VOICE_PRESETS
except ImportError:
    from anime4k_upscaler import Anime4KUpscaler
    from motion_comic import (
        OUTPUT_DIR,
        TEMP_DIR,
        AspectRatio,
        MotionComicEngine,
        MotionComicResult,
        MotionConfig,
        MotionPanel,
        MotionStyle,
    )
    from voice_engine import VoiceEngine, VOICE_PRESETS

logger = logging.getLogger("motion_comic_routes")

router = APIRouter(prefix="/api/motion-comic", tags=["Motion Comic Studio"])
engine = MotionComicEngine()
voice_engine = VoiceEngine()
upscaler = Anime4KUpscaler()

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "office.db"


class MotionPanelInput(BaseModel):
    panel_id: str = Field(default_factory=lambda: f"p_{uuid.uuid4().hex[:6]}")
    image_path: Optional[str] = None
    image_data: Optional[str] = None     # Base64 string if client uploads directly
    text: str = ""
    speaker: str = ""
    motion_style: str = "zoom_in"
    duration: Optional[float] = None
    sfx: Optional[str] = None
    voice_id: Optional[str] = None


class MotionRenderRequest(BaseModel):
    panels: List[MotionPanelInput]
    aspect_ratio: str = "16:9"
    fps: int = 30
    voice_id: str = "vi-VN-HoaiMyNeural"
    enable_tts: bool = True
    enable_sfx: bool = True
    enable_anime4k: bool = True
    fit_mode: str = "blur_bg"
    bgm_path: Optional[str] = None
    output_name: Optional[str] = None


class ChapterRenderRequest(BaseModel):
    chapter_id: str
    aspect_ratio: str = "16:9"
    voice_id: str = "vi-VN-HoaiMyNeural"
    enable_anime4k: bool = True
    fit_mode: str = "blur_bg"


@router.get("/voices")
def get_voices():
    """List available TTS voice presets for dialogue dubbing."""
    return {"voices": list(VOICE_PRESETS.values())}


@router.get("/presets")
def get_presets():
    """List available aspect ratios, motion styles, and sound effects."""
    return {
        "aspect_ratios": [
            {"id": "16:9", "name": "YouTube / TV Widescreen (1920x1080)"},
            {"id": "9:16", "name": "TikTok / YouTube Shorts / Reels (1080x1920)"},
            {"id": "1:1", "name": "Square Post (1080x1080)"},
            {"id": "4K", "name": "Ultra HD 4K (3840x2160)"},
        ],
        "motion_styles": [
            {"id": "zoom_in", "name": "Zoom In (Kịch tính, hướng vào nhân vật)"},
            {"id": "zoom_out", "name": "Zoom Out (Toàn cảnh không gian)"},
            {"id": "pan_ltr", "name": "Pan Trái sang Phải (Điện ảnh)"},
            {"id": "pan_rtl", "name": "Pan Phải sang Trái (Chuẩn đọc Manga)"},
            {"id": "pan_ttb", "name": "Pan Trên xuống Dưới (Webtoon)"},
            {"id": "action_shake", "name": "Rung lắc hành động (Impact Shake)"},
            {"id": "static", "name": "Tĩnh lặng nhẹ nhàng (Ambient Drift)"},
        ],
        "sfx_presets": [
            {"id": "boom", "name": "Bộc phá / Va chạm mạnh (Cinematic Boom)"},
            {"id": "swoosh", "name": "Lướt kiếm / Tốc biến (Anime Swoosh)"},
            {"id": "thump", "name": "Nhịp tim / Hồi hộp (Tension Thump)"},
        ],
    }


@router.post("/render")
async def render_motion_comic(req: MotionRenderRequest):
    """Render a custom list of panels into a complete Motion Comic video."""
    if not req.panels:
        raise HTTPException(status_code=400, detail="Danh sách panel không được để trống.")

    temp_images_to_clean: list[Path] = []
    engine_panels: list[MotionPanel] = []

    try:
        for idx, p in enumerate(req.panels):
            img_path = p.image_path
            # If base64 supplied, save to temp png
            if p.image_data and not (img_path and os.path.exists(img_path)):
                import base64
                data_str = p.image_data
                if "," in data_str:
                    data_str = data_str.split(",", 1)[1]
                raw_bytes = base64.b64decode(data_str)
                tmp_p = TEMP_DIR / f"upload_{uuid.uuid4().hex[:8]}_{idx}.png"
                with open(tmp_p, "wb") as f:
                    f.write(raw_bytes)
                img_path = str(tmp_p)
                temp_images_to_clean.append(tmp_p)

            if not img_path or not os.path.exists(img_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Panel {p.panel_id} không tìm thấy đường dẫn ảnh: {img_path}",
                )

            motion = MotionStyle(p.motion_style) if p.motion_style in MotionStyle.__members__.values() else MotionStyle.ZOOM_IN
            engine_panels.append(
                MotionPanel(
                    panel_id=p.panel_id,
                    image_path=img_path,
                    text=p.text,
                    speaker=p.speaker,
                    motion_style=motion,
                    duration=p.duration,
                    sfx=p.sfx,
                    voice_id=p.voice_id,
                )
            )

        cfg = MotionConfig(
            aspect_ratio=req.aspect_ratio,
            fps=req.fps,
            voice_id=req.voice_id,
            enable_tts=req.enable_tts,
            enable_sfx=req.enable_sfx,
            enable_anime4k=req.enable_anime4k,
            fit_mode=req.fit_mode,
            bgm_path=req.bgm_path,
        )

        res: MotionComicResult = await engine.render_motion_comic(
            panels=engine_panels,
            config=cfg,
            output_name=req.output_name,
        )

        video_filename = Path(res.video_path).name
        srt_filename = Path(res.srt_path).name
        vtt_filename = Path(res.vtt_path).name

        return {
            "success": True,
            "job_id": res.job_id,
            "duration": round(res.duration, 2),
            "panel_count": res.panel_count,
            "resolution": res.resolution,
            "file_size": res.file_size_bytes,
            "video_url": f"/api/motion-comic/video/{video_filename}",
            "srt_url": f"/api/motion-comic/subtitles/{srt_filename}",
            "vtt_url": f"/api/motion-comic/subtitles/{vtt_filename}",
        }

    finally:
        for tmp in temp_images_to_clean:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass


@router.post("/render-from-chapter")
async def render_from_chapter(req: ChapterRenderRequest):
    """Automatically render an entire Manga Chapter from database into Motion Comic video."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database không tồn tại.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 1. Fetch chapter
        ch = conn.execute("SELECT * FROM manga_chapters WHERE id = ?", (req.chapter_id,)).fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy chapter id: {req.chapter_id}")

        # 2. Fetch panels belonging to chapter
        rows = conn.execute(
            "SELECT * FROM manga_panels WHERE chapter_id = ? ORDER BY page_number ASC, panel_index ASC",
            (req.chapter_id,),
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=400, detail="Chapter này chưa có panels nào được khởi tạo.")

        engine_panels: list[MotionPanel] = []
        for r in rows:
            img_path = r["image_path"] if "image_path" in r.keys() else None
            if not img_path or not os.path.exists(img_path):
                # Fallback to asset if exists
                continue

            # Parse dialogue / bubbles
            text = ""
            speaker = ""
            if "bubbles_json" in r.keys() and r["bubbles_json"]:
                try:
                    bubbles = json.loads(r["bubbles_json"])
                    if bubbles:
                        text = " ".join([b.get("text", "") for b in bubbles if b.get("text")])
                        speaker = bubbles[0].get("speaker", "")
                except Exception:
                    pass

            motion_choices = [MotionStyle.ZOOM_IN, MotionStyle.PAN_RIGHT_TO_LEFT, MotionStyle.ZOOM_OUT]
            style = motion_choices[len(engine_panels) % len(motion_choices)]

            engine_panels.append(
                MotionPanel(
                    panel_id=r["id"],
                    image_path=img_path,
                    text=text,
                    speaker=speaker,
                    motion_style=style,
                    sfx="boom" if "!" in text else None,
                )
            )

        if not engine_panels:
            raise HTTPException(status_code=400, detail="Không có panels hợp lệ có ảnh trên đĩa để dựng video.")

        cfg = MotionConfig(
            aspect_ratio=req.aspect_ratio,
            voice_id=req.voice_id,
            enable_anime4k=req.enable_anime4k,
            fit_mode=req.fit_mode,
        )

        res: MotionComicResult = await engine.render_motion_comic(
            panels=engine_panels,
            config=cfg,
            output_name=f"chapter_{ch['number']}_{uuid.uuid4().hex[:6]}",
        )

        video_filename = Path(res.video_path).name
        srt_filename = Path(res.srt_path).name
        vtt_filename = Path(res.vtt_path).name

        return {
            "success": True,
            "chapter_id": req.chapter_id,
            "chapter_title": ch["title"] if "title" in ch.keys() else f"Chapter {ch['number']}",
            "job_id": res.job_id,
            "duration": round(res.duration, 2),
            "panel_count": res.panel_count,
            "resolution": res.resolution,
            "file_size": res.file_size_bytes,
            "video_url": f"/api/motion-comic/video/{video_filename}",
            "srt_url": f"/api/motion-comic/subtitles/{srt_filename}",
            "vtt_url": f"/api/motion-comic/subtitles/{vtt_filename}",
        }

    finally:
        conn.close()


@router.get("/video/{filename}")
def stream_video(filename: str):
    """Stream rendered Motion Comic MP4 video file."""
    # Security check: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = OUTPUT_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File video không tồn tại.")
    return FileResponse(target, media_type="video/mp4", filename=filename)


@router.get("/subtitles/{filename}")
def get_subtitles(filename: str):
    """Download or stream SRT/VTT subtitle files."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = OUTPUT_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File phụ đề không tồn tại.")

    media = "text/vtt" if filename.endswith(".vtt") else "application/x-subrip"
    return FileResponse(target, media_type=media, filename=filename)


def register_routes(app: FastAPI) -> None:
    """Register motion comic router to main FastAPI app."""
    app.include_router(router)
