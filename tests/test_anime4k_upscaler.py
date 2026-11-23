"""Unit tests for Anime4K Zero-VRAM Line-Art & Upscaling Engine."""

import pytest
from PIL import Image
import numpy as np

from app.anime4k_upscaler import Anime4KUpscaler


@pytest.fixture
def upscaler():
    return Anime4KUpscaler()


@pytest.fixture
def sample_manga_panel():
    # Create high-contrast test panel with black lines on white canvas
    img = Image.new("RGB", (300, 400), color=(255, 255, 255))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Draw dark manga ink borders and character silhouettes
    draw.rectangle([20, 20, 280, 380], outline=(0, 0, 0), width=4)
    draw.line([50, 150, 250, 150], fill=(0, 0, 0), width=3)
    draw.ellipse([100, 80, 200, 180], outline=(0, 0, 0), width=4)
    return img


def test_restore_lineart_preserves_dimensions(upscaler, sample_manga_panel):
    restored = upscaler.restore_lineart(sample_manga_panel, darkness=1.3, sharpness=1.5)
    assert restored.size == sample_manga_panel.size
    assert restored.mode == "RGB"


def test_restore_lineart_darkens_edges(upscaler, sample_manga_panel):
    orig_np = np.asarray(sample_manga_panel, dtype=np.float32)
    restored = upscaler.restore_lineart(sample_manga_panel, darkness=1.4)
    restored_np = np.asarray(restored, dtype=np.float32)

    # Edge regions should have lower luminance (darker) in restored image
    assert restored_np.mean() <= orig_np.mean()


def test_upscale_panel_2x(upscaler, sample_manga_panel):
    upscaled = upscaler.upscale_panel(sample_manga_panel, scale=2.0, enhance_lines=True)
    assert upscaled.size == (600, 800)
    assert upscaled.mode == "RGB"


def test_upscale_to_target_contain(upscaler, sample_manga_panel):
    target = upscaler.upscale_to_target(sample_manga_panel, target_w=1920, target_h=1080, fit_mode="contain")
    assert target.size == (1920, 1080)


def test_upscale_to_target_blur_bg(upscaler, sample_manga_panel):
    target = upscaler.upscale_to_target(sample_manga_panel, target_w=1920, target_h=1080, fit_mode="blur_bg")
    assert target.size == (1920, 1080)


def test_upscale_to_target_tiktok_vertical(upscaler, sample_manga_panel):
    # 9:16 vertical resolution
    target = upscaler.upscale_to_target(sample_manga_panel, target_w=1080, target_h=1920, fit_mode="blur_bg")
    assert target.size == (1080, 1920)
