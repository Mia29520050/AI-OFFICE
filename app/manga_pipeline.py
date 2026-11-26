"""
app/manga_pipeline.py
Production Manga Pipeline for AI Office:
  1. Post-Processing Engine:
     - Curves & Shadow Lifting (anti-dead black)
     - Multi-layer Authentic Neon Typography (Japanese kanji/katakana signs)
     - Atmosphere & Rain Streaks
     - Character Silhouette Rim-Lighting
  2. Typesetting & Dynamic SFX Engine:
     - Dynamic Border-Breaking SFX (no tails, heavy stroke, angled)
     - Anti-collision face-avoiding dialogue bubbles
     - Caption boxes with reading flow enforcement (LTR / RTL)
  3. Character Visual Consistency Lock (Aria profile):
     - Hairstyle: silver-white bob, straight bangs
     - Eyes: vivid crimson red glowing pupils
     - Outfit: black battle suit, high collar, dark hooded cowl, cyan energy accents
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

FONT_JP = "C:/Windows/Fonts/YuGothB.ttc"
if not Path(FONT_JP).exists():
    FONT_JP = "C:/Windows/Fonts/msgothic.ttc"


def apply_curves_and_lift_blacks(
    img: Image.Image,
    black_lift: int = 24,
    gamma: float = 1.15,
    sharpness: float = 1.25,
) -> Image.Image:
    """Lift black point from 0 to black_lift and apply smooth gamma curve to reveal dark structures."""
    lut = []
    for i in range(256):
        norm = i / 255.0
        curved = math.pow(norm, 1.0 / gamma)
        val = int(black_lift + curved * (255 - black_lift))
        lut.append(max(0, min(255, val)))

    if img.mode != "RGB":
        img = img.convert("RGB")
    r, g, b = img.split()
    r = r.point(lut)
    g = g.point(lut)
    b = b.point(lut)
    curved_img = Image.merge("RGB", (r, g, b))

    if sharpness > 1.0:
        enhancer = ImageEnhance.Sharpness(curved_img)
        curved_img = enhancer.enhance(sharpness)
    return curved_img


def add_diagonal_rain(
    img: Image.Image,
    count: int = 350,
    length: int = 26,
    angle_deg: float = -18.0,
    alpha_range: tuple[int, int] = (35, 75),
) -> Image.Image:
    """Render subtle translucent diagonal rain streaks."""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    rad = math.radians(angle_deg)
    dx = math.sin(rad) * length
    dy = math.cos(rad) * length

    random.seed(42)
    for _ in range(count):
        x0 = random.randint(-50, w + 50)
        y0 = random.randint(0, h)
        x1 = x0 + dx
        y1 = y0 + dy
        alpha = random.randint(*alpha_range)
        width = 1 if random.random() > 0.15 else 2
        draw.line([(x0, y0), (x1, y1)], fill=(200, 230, 255, alpha), width=width)

    blurred_rain = overlay.filter(ImageFilter.GaussianBlur(radius=0.5))
    return Image.alpha_composite(img.convert("RGBA"), blurred_rain).convert("RGB")


def render_neon_vertical_sign(
    base_img: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    glow_color: tuple[int, int, int] = (0, 240, 255),
    bg_color: tuple[int, int, int] = (5, 25, 45),
    font_size: int = 28,
) -> Image.Image:
    """Render a vertical neon signboard with authentic typography and multi-layer Gaussian bloom."""
    x0, y0, x1, y1 = box
    bw = x1 - x0
    bh = y1 - y0

    board = Image.new("RGBA", (bw, bh), (*bg_color, 240))
    draw = ImageDraw.Draw(board)
    draw.rectangle([1, 1, bw - 2, bh - 2], outline=(*glow_color, 220), width=2)

    font = ImageFont.truetype(FONT_JP, font_size)
    chars = list(text)
    n_chars = len(chars)
    line_spacing = (bh - 16) / max(1, n_chars)

    glow_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    for i, ch in enumerate(chars):
        bbox = font.getbbox(ch)
        cw = bbox[2] - bbox[0]
        ch_h = bbox[3] - bbox[1]
        cx = (bw - cw) // 2
        cy = int(8 + i * line_spacing + (line_spacing - ch_h) // 2)
        glow_draw.text((cx, cy), ch, font=font, fill=(*glow_color, 255))

    wide_bloom = glow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    tight_bloom = glow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    board = Image.alpha_composite(board, wide_bloom)
    board = Image.alpha_composite(board, tight_bloom)

    core_draw = ImageDraw.Draw(board)
    for i, ch in enumerate(chars):
        bbox = font.getbbox(ch)
        cw = bbox[2] - bbox[0]
        ch_h = bbox[3] - bbox[1]
        cx = (bw - cw) // 2
        cy = int(8 + i * line_spacing + (line_spacing - ch_h) // 2)
        core_draw.text((cx, cy), ch, font=font, fill=(255, 255, 255, 255))

    base_rgba = base_img.convert("RGBA")
    base_rgba.paste(board, (x0, y0), board)
    return base_rgba.convert("RGB")


def apply_de_ai_organic_enhancer(
    image: Image.Image,
    grain_intensity: float = 0.08,
    gpen_contrast: float = 1.25,
    sharpness: float = 1.45,
    screentone_pitch: int = 4,
) -> Image.Image:
    """Removes smooth plastic AI surface sheen by infusing authentic manga paper grain,
    micro-dot screentone textures in midtones, and crisp G-pen ink edge enhancement.
    """
    try:
        from app.manga_composer import apply_de_ai_organic_enhancer as _composer_enhancer
        return _composer_enhancer(
            image,
            grain_intensity=grain_intensity,
            gpen_contrast=gpen_contrast,
            sharpness=sharpness,
            screentone_pitch=screentone_pitch,
        )
    except Exception:
        orig_mode = image.mode
        img = image.convert("RGB")
        try:
            import numpy as np
            arr = np.array(img, dtype=np.float32)
            h, w, c = arr.shape
            rng = np.random.RandomState(42)
            noise = rng.normal(0.0, 22.0 * grain_intensity, (h, w, 1))
            y_idx, x_idx = np.ogrid[:h, :w]
            screentone_dots = ((x_idx % screentone_pitch == 0) & (y_idx % screentone_pitch == 0)).astype(np.float32)[:, :, np.newaxis]
            luminance = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            midtones = ((luminance > 35.0) & (luminance < 225.0))[:, :, np.newaxis]
            textured = arr + noise + (screentone_dots * midtones * -12.0)
            textured = np.clip(textured, 0, 255).astype(np.uint8)
            result = Image.fromarray(textured)
        except Exception:
            result = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

        if sharpness > 1.0:
            result = ImageEnhance.Sharpness(result).enhance(sharpness)
        if gpen_contrast > 1.0:
            result = ImageEnhance.Contrast(result).enhance(gpen_contrast)
        return result.convert("RGBA") if orig_mode == "RGBA" else result


def apply_dark_fantasy_postprocessing(
    image: Image.Image,
    lift_blacks: int = 20,
    gamma: float = 1.12,
    grain_intensity: float = 0.08,
    gpen_contrast: float = 1.25,
) -> Image.Image:
    """Complete postprocessing pipeline for Dark Fantasy manga panels:
    1. Shadow lift & anti-dead-black gamma curve
    2. De-AI organic paper grain + micro-screentone + G-pen sharpening
    """
    lifted = apply_curves_and_lift_blacks(image, black_lift=lift_blacks, gamma=gamma)
    return apply_de_ai_organic_enhancer(lifted, grain_intensity=grain_intensity, gpen_contrast=gpen_contrast)
