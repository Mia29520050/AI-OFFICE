"""Unit and Integration tests for Motion Comic Studio Video Pipeline."""

import os
from pathlib import Path
import pytest
from PIL import Image

from app.motion_comic import (
    ASPECT_RESOLUTIONS,
    AspectRatio,
    MotionComicEngine,
    MotionComicResult,
    MotionConfig,
    MotionPanel,
    MotionStyle,
)


@pytest.fixture
def test_panels(tmp_path):
    img1 = tmp_path / "panel1.png"
    img2 = tmp_path / "panel2.png"
    Image.new("RGB", (600, 800), color=(180, 50, 50)).save(img1)
    Image.new("RGB", (800, 600), color=(40, 120, 200)).save(img2)

    return [
        MotionPanel(
            panel_id="p1",
            image_path=str(img1),
            text="Đòn tấn công quyết định!",
            speaker="Luffy",
            motion_style=MotionStyle.ZOOM_IN,
            sfx="boom",
        ),
        MotionPanel(
            panel_id="p2",
            image_path=str(img2),
            text="Chúng ta đã thắng rồi!",
            speaker="Zoro",
            motion_style=MotionStyle.PAN_RIGHT_TO_LEFT,
            sfx="swoosh",
        ),
    ]


@pytest.fixture
def motion_engine(tmp_path):
    return MotionComicEngine(work_dir=tmp_path / "mc_scratch")


def test_aspect_resolutions_mapping():
    assert ASPECT_RESOLUTIONS["16:9"] == (1920, 1080)
    assert ASPECT_RESOLUTIONS["9:16"] == (1080, 1920)
    assert ASPECT_RESOLUTIONS["1:1"] == (1080, 1080)
    assert ASPECT_RESOLUTIONS["4K"] == (3840, 2160)


def test_ken_burns_filter_construction(motion_engine):
    filter_zoom_in = motion_engine._build_ken_burns_filter(
        style=MotionStyle.ZOOM_IN, duration=3.0, fps=30, target_w=1920, target_h=1080
    )
    assert "zoompan=" in filter_zoom_in
    assert "1920x1080" in filter_zoom_in

    filter_pan_rtl = motion_engine._build_ken_burns_filter(
        style=MotionStyle.PAN_RIGHT_TO_LEFT, duration=3.0, fps=30, target_w=1080, target_h=1920
    )
    assert "zoompan=" in filter_pan_rtl
    assert "1080x1920" in filter_pan_rtl


@pytest.mark.asyncio
async def test_render_motion_comic_16_9(motion_engine, test_panels, tmp_path):
    cfg = MotionConfig(
        aspect_ratio="16:9",
        fps=30,
        enable_anime4k=False,  # Skip extra upscale for test speed
        min_panel_duration=2.0,
        buffer_after_speech=0.5,
    )

    out_name = "test_mc_run_16_9"
    result: MotionComicResult = await motion_engine.render_motion_comic(
        panels=test_panels,
        config=cfg,
        output_name=out_name,
    )

    assert os.path.exists(result.video_path)
    assert os.path.exists(result.srt_path)
    assert os.path.exists(result.vtt_path)
    assert result.resolution == (1920, 1080)
    assert result.panel_count == 2
    assert result.duration >= 4.0
    assert result.file_size_bytes > 5000

    # Verify SRT content
    with open(result.srt_path, encoding="utf-8") as srt_f:
        srt_content = srt_f.read()
        assert "Luffy" in srt_content
        assert "Zoro" in srt_content
        assert "-->" in srt_content


@pytest.mark.asyncio
async def test_render_motion_comic_tiktok_9_16(motion_engine, test_panels, tmp_path):
    cfg = MotionConfig(
        aspect_ratio="9:16",
        fps=30,
        enable_anime4k=False,
        min_panel_duration=2.0,
    )

    out_name = "test_mc_run_tiktok"
    result: MotionComicResult = await motion_engine.render_motion_comic(
        panels=test_panels[:1],
        config=cfg,
        output_name=out_name,
    )

    assert os.path.exists(result.video_path)
    assert result.resolution == (1080, 1920)
    assert result.panel_count == 1
