#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/test_scenery_enhancer.py
Build and verify the authentic Akihabara Scenery post-processing pipeline:
  1. Lift dark levels (Curves / Tone Mapping) so building architecture, windows, and panels are visible.
  2. Overlay authentic Japanese neon signage in post-processing with multi-layer bloom:
     - 「秋葉原」(Akihabara)
     - 「電気街」(Electric Town)
     - 「アニメ」(Anime)
     - 「サイバー」(Cyber)
     - 「ゲーム」(Game)
  3. Render realistic fine diagonal rain streaks.
"""

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

FONT_JP = "C:/Windows/Fonts/YuGothB.ttc"
if not Path(FONT_JP).exists():
    FONT_JP = "C:/Windows/Fonts/msgothic.ttc"


def apply_curves_and_lift_blacks(img: Image.Image, black_lift: int = 22, gamma: float = 1.12) -> Image.Image:
    """Lift black point from 0 to black_lift and apply smooth gamma curve to reveal dark structures."""
    lut = []
    for i in range(256):
        # Normalized 0..1
        norm = i / 255.0
        # Gamma adjustment for midtones
        curved = math.pow(norm, 1.0 / gamma)
        # Remap to [black_lift, 255]
        val = int(black_lift + curved * (255 - black_lift))
        lut.append(max(0, min(255, val)))

    # Apply to R, G, B channels
    if img.mode != "RGB":
        img = img.convert("RGB")
    r, g, b = img.split()
    r = r.point(lut)
    g = g.point(lut)
    b = b.point(lut)
    curved_img = Image.merge("RGB", (r, g, b))

    # Slightly enhance local contrast and sharpness
    enhancer = ImageEnhance.Sharpness(curved_img)
    return enhancer.enhance(1.25)


def add_diagonal_rain(img: Image.Image, count: int = 350, length: int = 24, angle_deg: float = -18.0) -> Image.Image:
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
        alpha = random.randint(35, 80)
        width = 1 if random.random() > 0.15 else 2
        draw.line([(x0, y0), (x1, y1)], fill=(200, 230, 255, alpha), width=width)

    # Blur rain slightly
    blurred_rain = overlay.filter(ImageFilter.GaussianBlur(radius=0.5))
    return Image.alpha_composite(img.convert("RGBA"), blurred_rain).convert("RGB")


def render_neon_vertical_sign(
    base_img: Image.Image,
    box: tuple[int, int, int, int],  # x0, y0, x1, y1
    text: str,
    glow_color: tuple[int, int, int] = (0, 240, 255),
    bg_color: tuple[int, int, int] = (10, 25, 45),
    font_size: int = 24,
) -> Image.Image:
    """Render a vertical neon signboard with authentic typography and multi-layer Gaussian bloom."""
    x0, y0, x1, y1 = box
    bw = x1 - x0
    bh = y1 - y0

    # Create signboard surface
    board = Image.new("RGBA", (bw, bh), (*bg_color, 240))
    draw = ImageDraw.Draw(board)

    # Thin neon border
    draw.rectangle([1, 1, bw - 2, bh - 2], outline=(*glow_color, 220), width=2)

    # Font setup
    font = ImageFont.truetype(FONT_JP, font_size)

    # Vertical text layout (one character per line)
    chars = list(text)
    n_chars = len(chars)
    line_spacing = (bh - 16) / max(1, n_chars)

    # Create text glow layer
    glow_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    for i, ch in enumerate(chars):
        # Bounding box of character
        bbox = font.getbbox(ch)
        cw = bbox[2] - bbox[0]
        ch_h = bbox[3] - bbox[1]

        cx = (bw - cw) // 2
        cy = int(8 + i * line_spacing + (line_spacing - ch_h) // 2)

        # Draw intense glow behind text
        glow_draw.text((cx, cy), ch, font=font, fill=(*glow_color, 255))

    # Bloom passes: Wide soft blur + tight crisp core
    wide_bloom = glow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    tight_bloom = glow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    # Composite blooms onto board
    board = Image.alpha_composite(board, wide_bloom)
    board = Image.alpha_composite(board, tight_bloom)

    # Crisp white core text on top
    core_draw = ImageDraw.Draw(board)
    for i, ch in enumerate(chars):
        bbox = font.getbbox(ch)
        cw = bbox[2] - bbox[0]
        ch_h = bbox[3] - bbox[1]
        cx = (bw - cw) // 2
        cy = int(8 + i * line_spacing + (line_spacing - ch_h) // 2)
        core_draw.text((cx, cy), ch, font=font, fill=(255, 255, 255, 255))

    # Paste back onto base image
    base_rgba = base_img.convert("RGBA")
    base_rgba.paste(board, (x0, y0), board)
    return base_rgba.convert("RGB")


def render_neon_horizontal_sign(
    base_img: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    glow_color: tuple[int, int, int] = (255, 0, 128),
    bg_color: tuple[int, int, int] = (30, 10, 25),
    font_size: int = 20,
) -> Image.Image:
    """Render a horizontal neon lightbox."""
    x0, y0, x1, y1 = box
    bw = x1 - x0
    bh = y1 - y0

    board = Image.new("RGBA", (bw, bh), (*bg_color, 240))
    draw = ImageDraw.Draw(board)
    draw.rectangle([1, 1, bw - 2, bh - 2], outline=(*glow_color, 220), width=2)

    font = ImageFont.truetype(FONT_JP, font_size)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    cx = (bw - tw) // 2
    cy = (bh - th) // 2 - bbox[1]

    glow_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.text((cx, cy), text, font=font, fill=(*glow_color, 255))

    wide_bloom = glow_layer.filter(ImageFilter.GaussianBlur(radius=5))
    tight_bloom = glow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    board = Image.alpha_composite(board, wide_bloom)
    board = Image.alpha_composite(board, tight_bloom)

    core_draw = ImageDraw.Draw(board)
    core_draw.text((cx, cy), text, font=font, fill=(255, 255, 255, 255))

    base_rgba = base_img.convert("RGBA")
    base_rgba.paste(board, (x0, y0), board)
    return base_rgba.convert("RGB")


def enhance_panel1_akihabara():
    src_path = Path("F:/AI-Office/data/manga/real_panels/panel_01_tokyo_night.png")
    out_dir = Path("F:/AI-Office/data/manga/real_panels_v3")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "p1_akihabara_v3.png"

    img = Image.open(src_path)

    # 1. Lift shadow levels so the buildings, windows, and panels are revealed
    img = apply_curves_and_lift_blacks(img, black_lift=24, gamma=1.15)

    # 2. Overlay authentic Japanese neon signs over the gibberish signboards
    # Left vertical sign 1: Akihabara (covers full vertical box from 80 to 290)
    img = render_neon_vertical_sign(
        img,
        box=(184, 80, 226, 290),
        text="秋葉原",
        glow_color=(0, 240, 255),
        bg_color=(5, 25, 45),
        font_size=30,
    )

    # Left vertical sign 2: Anime (covers from 135 to 245)
    img = render_neon_vertical_sign(
        img,
        box=(284, 135, 314, 245),
        text="アニメ",
        glow_color=(255, 0, 160),
        bg_color=(35, 5, 25),
        font_size=20,
    )

    # Right tall vertical sign top: Denki-gai (Electric Town, 25 to 215)
    img = render_neon_vertical_sign(
        img,
        box=(466, 25, 506, 215),
        text="電気街",
        glow_color=(0, 245, 255),
        bg_color=(5, 30, 50),
        font_size=32,
    )

    # Right vertical sign bottom: Cyber (225 to 320)
    img = render_neon_vertical_sign(
        img,
        box=(466, 225, 506, 320),
        text="サイバ",
        glow_color=(255, 0, 140),
        bg_color=(30, 5, 25),
        font_size=22,
    )

    # Center background tower sign 1: Game (185 to 215)
    img = render_neon_horizontal_sign(
        img,
        box=(360, 185, 408, 215),
        text="ゲーム",
        glow_color=(0, 240, 255),
        bg_color=(5, 25, 45),
        font_size=13,
    )

    # Center background tower sign 2: 24h (220 to 245)
    img = render_neon_horizontal_sign(
        img,
        box=(360, 220, 408, 245),
        text="２４Ｈ",
        glow_color=(255, 0, 120),
        bg_color=(30, 5, 20),
        font_size=12,
    )

    # 3. Add delicate rain streaks matching wet road reflections
    img = add_diagonal_rain(img, count=400, length=26, angle_deg=-18.0)

    img.save(out_path, "PNG")
    print(f"Saved enhanced Panel 1 to: {out_path}")

    # Copy to artifacts for inspection
    art_path = Path("C:/Users/Shiro/.gemini/antigravity/brain/d2888882-c5f1-463b-913f-d9262e881394/v3_p1_akihabara.png")
    img.save(art_path, "PNG")
    print(f"Copied to artifact: {art_path}")


if __name__ == "__main__":
    enhance_panel1_akihabara()
