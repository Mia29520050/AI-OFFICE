"""Manga Composition and Export Engine for AI Office Manga Studio.

Provides panel layout framing, gutters, speech bubble overlay engine
(regular speech, thought, shout, whisper, caption, SFX), Vietnamese Unicode
text rendering, B&W screentone/halftone effects, Japanese-style color adjustments,
and multi-format export (PNG, CBZ, multi-page PDF).
"""

from __future__ import annotations

import base64
import io
import math
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any, Union

from PIL import (
    Image,
    ImageColor,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
)
from pydantic import BaseModel, Field, model_validator

import re

# ---------------------------------------------------------------------------
# Constants & Font Paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = Path(__file__).resolve().parent / "ui" / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
DEFAULT_FONT_PATH = FONTS_DIR / "PatrickHand-Regular.ttf" if (FONTS_DIR / "PatrickHand-Regular.ttf").exists() else (ASSETS_DIR / "Inter-Variable.ttf")

# System font fallbacks with complete Vietnamese diacritic coverage (Comic style prioritized)
SYSTEM_FALLBACKS = [
    "C:/Windows/Fonts/comicbd.ttf",
    "C:/Windows/Fonts/comic.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def sanitize_manga_text(text: str) -> str:
    """Remove emoji characters, non-printable symbols, outer single quotes, and tofu-causing glyphs."""
    if not text:
        return ""
    # Strip emojis and pictographs that lack glyphs in standard font files
    emoji_pattern = re.compile(
        "["
        "\U0001F000-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U00002300-\U000023FF"
        "\U00002B50-\U00002B55"
        "\U0000FE00-\U0000FE0F"
        "]+",
        flags=re.UNICODE,
    )
    cleaned = emoji_pattern.sub("", text)
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32 or ch == "\n")
    cleaned = re.sub(r" +", " ", cleaned).strip()

    # Strip matching outer single quotes ('...' or ‘...’) wrapping the entire dialogue line,
    # while preserving apostrophes inside words (e.g., don't) and inner quoted phrases.
    while len(cleaned) >= 2 and (
        (cleaned.startswith("'") and cleaned.endswith("'"))
        or (cleaned.startswith("‘") and cleaned.endswith("’"))
    ):
        inner = cleaned[1:-1].strip()
        if re.search(r"(?<!\w)['‘’]|['‘’](?!\w)", inner):
            break
        cleaned = inner

    return cleaned.strip()


def resolve_font_path(custom_path: str | None = None, font_category: str = "dialogue") -> str:
    """Find a valid font file, prioritizing authentic Manga/Comic fonts with Vietnamese coverage."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    # Check dedicated Manga Fonts directory first
    if FONTS_DIR.exists():
        if font_category in ("sfx", "shout"):
            preferred_names = ["Bangers-Regular.ttf", "ComicNeue-Bold.ttf", "PatrickHand-Regular.ttf"]
        elif font_category in ("whisper", "thought"):
            preferred_names = ["PatrickHand-Regular.ttf", "ComicNeue-Regular.ttf"]
        else:
            preferred_names = ["PatrickHand-Regular.ttf", "ComicNeue-Bold.ttf", "ComicNeue-Regular.ttf", "Bangers-Regular.ttf"]

        for name in preferred_names:
            candidate = FONTS_DIR / name
            if candidate.exists():
                return str(candidate)

    # Windows comic feel fallbacks
    for win_comic in ("C:/Windows/Fonts/comicbd.ttf", "C:/Windows/Fonts/comic.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(win_comic):
            return win_comic

    if DEFAULT_FONT_PATH.exists():
        return str(DEFAULT_FONT_PATH)

    for fallback in SYSTEM_FALLBACKS:
        if os.path.exists(fallback):
            return fallback
    return ""


def get_font(
    size: int = 20,
    font_path: str | None = None,
    font_category: str = "dialogue",
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load an ImageFont with Vietnamese Unicode support, prioritizing authentic Manga/Comic fonts."""
    # Priority: Try loading from manga_fonts module if available
    try:
        try:
            from app.manga_fonts import get_manga_font
        except ImportError:
            from manga_fonts import get_manga_font
        cat_map = {"sfx": "sfx", "shout": "shout", "thought": "whisper", "whisper": "whisper", "caption": "narrative"}
        mapped_cat = cat_map.get(font_category, "dialogue")
        return get_manga_font(mapped_cat, size=size)
    except Exception:
        pass

    fpath = resolve_font_path(font_path, font_category=font_category)
    if fpath:
        try:
            return ImageFont.truetype(fpath, size=size)
        except Exception:
            pass
    return ImageFont.load_default()



# ---------------------------------------------------------------------------
# Enums and Pydantic Schemas
# ---------------------------------------------------------------------------


class BubbleType(str, Enum):
    """Supported Speech Bubble types."""
    REGULAR = "regular"       # Classic rounded speech bubble with pointer tail
    THOUGHT = "thought"       # Cloud-like scalloped bubble with trailing circles
    SHOUT = "shout"           # Jagged dynamic starburst bubble for action/yelling
    WHISPER = "whisper"       # Dashed/dotted outline bubble for quiet dialogue
    CAPTION = "caption"       # Rectangular narrative box for narration/setting
    SFX = "sfx"               # Dynamic onomatopoeia sound effect with bold stroke
    INVERTED = "inverted"     # Dark ominous bubble (black bg, white text)


class PanelFilter(str, Enum):
    """B&W screentone / halftone and Japanese manga color filters."""
    NONE = "none"
    HALFTONE_DOTS = "halftone_dots"               # Classic manga screen dot pattern
    DITHER = "dither"                             # Floyd-Steinberg retro monochrome dither
    INK = "ink"                                   # High-contrast Japanese manga inking
    SPEEDLINES_RADIAL = "speedlines_radial"       # Action focus lines towards center
    SPEEDLINES_HORIZONTAL = "speedlines_horizontal"  # Horizontal motion speed lines
    PASTEL = "pastel"                             # Soft Japanese anime pastel color grading
    VIBRANT = "vibrant"                           # Bold Shonen high-contrast color
    SEPIA = "sepia"                               # Vintage manga paper/retro ink tone
    DE_AI_ORGANIC = "de_ai_organic"               # Organic paper grain, G-pen ink sharpening, de-plasticizer
    G_PEN_GRAIN = "g_pen_grain"                   # Hand-drawn G-pen ink lines with physical manga screentone


class PanelLayoutType(str, Enum):
    """Pre-configured Manga page panel layouts."""
    CUSTOM = "custom"                     # Custom rects supplied by user/AI
    SINGLE = "single"                     # 1 Full-page splash panel
    YONKOMA = "yonkoma"                   # 4 vertical equal panels (4-koma)
    GRID_2X2 = "grid_2x2"                 # 4 panels in 2x2 grid
    GRID_1X2 = "grid_1x2"                 # 2 vertical panels (1 column, 2 rows)
    GRID_2X1 = "grid_2x1"                 # 2 horizontal panels (2 columns, 1 row)
    TOP1_BOTTOM2 = "top1_bottom2"         # 1 wide top panel, 2 bottom panels
    TOP2_BOTTOM1 = "top2_bottom1"         # 2 top panels, 1 wide bottom panel
    THREE_ROWS = "three_rows"             # 3 horizontal strip panels
    ACTION_5 = "action_5"                 # Dynamic 5-panel shonen action layout
    DRAMA_6 = "drama_6"                   # 6 panels (2 columns x 3 rows)


class FitMode(str, Enum):
    """How panel artwork fits within its frame."""
    COVER = "cover"                       # Fill frame, center crop overflow (recommended)
    CONTAIN = "contain"                   # Fit within frame with letterboxing
    STRETCH = "stretch"                   # Direct stretch to panel size


class SpeechBubble(BaseModel):
    """Configuration for a speech bubble or SFX overlay."""
    text: str
    speaker: str = ""
    bubble_type: BubbleType = BubbleType.REGULAR
    x: float = 0.5                        # Center x (0.0-1.0 normalized or absolute px)
    y: float = 0.5                        # Center y (0.0-1.0 normalized or absolute px)
    width: float | None = None            # Width in px or normalized fraction
    height: float | None = None           # Height in px or normalized fraction
    tail_x: float | None = None           # Tail pointer target x
    tail_y: float | None = None           # Tail pointer target y
    font_size: int | None = None          # Font size in px (auto-calculated if None)
    font_path: str | None = None
    text_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 3
    padding: int = 14
    rotation: float = 0.0                 # Rotation angle in degrees (notably for SFX)
    stroke_color: str = "#000000"         # Text outline color (for SFX)
    stroke_width: int = 0                 # Text outline width
    auto_size: bool = True                # Auto-scale font or bubble bounds
    align: str = "center"                 # "center", "left", "right"

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "center_x" in data and ("x" not in data or data.get("x") is None):
                data["x"] = data["center_x"]
            if "center_y" in data and ("y" not in data or data.get("y") is None):
                data["y"] = data["center_y"]
        return data


class PanelConfig(BaseModel):
    """Configuration for a single manga panel."""
    id: str = ""
    image_path: str | None = None
    image_data: str | None = None         # Base64 string or data URL
    rect: tuple[float, float, float, float] | list[float] | None = None  # [x, y, w, h]
    fit_mode: FitMode = FitMode.COVER
    border_width: int = 3
    border_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    filter: PanelFilter = PanelFilter.NONE
    filter_params: dict[str, Any] = Field(default_factory=dict)
    prompt: str | None = None
    description: str | None = None
    bubbles: list[SpeechBubble] = Field(default_factory=list)
    auto_layout_bubbles: bool = False


class PageConfig(BaseModel):
    """Configuration for a complete manga page."""
    page_number: int = 1
    width: int = 1200
    height: int = 1800
    margin_x: int = 40
    margin_y: int = 40
    gutter_x: int = 16
    gutter_y: int = 16
    background_color: str = "#FFFFFF"
    layout_type: PanelLayoutType = PanelLayoutType.CUSTOM
    reading_direction: str = "rtl"        # "rtl" (Japanese manga) or "ltr"
    panels: list[PanelConfig] = Field(default_factory=list)
    page_bubbles: list[SpeechBubble] = Field(default_factory=list)
    auto_layout_bubbles: bool = False


class ComicMetadata(BaseModel):
    """Metadata embedded into CBZ (ComicInfo.xml) and export packages."""
    title: str = "AI Office Manga"
    series: str = "AI Office Manga"
    issue_or_chapter: str = "1"
    volume: str = "1"
    summary: str = ""
    writer: str = "AI Office Story Studio"
    penciller: str = "AI Office ComfyUI"
    genre: str = "Manga"
    language: str = "vi"
    manga: bool = True                    # Indicates Right-To-Left reading order
    page_count: int = 1


# ---------------------------------------------------------------------------
# Text Wrapping and Auto-Fitting Engine (Vietnamese Unicode)
# ---------------------------------------------------------------------------


def wrap_text_to_width(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Break Vietnamese Unicode text into lines that fit within max_width."""
    words = text.strip().split()
    if not words:
        return []

    lines: list[str] = []
    current_line: list[str] = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Single word wider than line, keep it anyway
                lines.append(word)
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def fit_text_in_bubble(
    text: str,
    target_w: int,
    target_h: int,
    font_path: str | None = None,
    preferred_font_size: int | None = None,
    min_font_size: int = 11,
    max_font_size: int = 36,
    padding: int = 14,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int]:
    """Calculate the best font size and wrapped lines to fit inside a bubble."""
    avail_w = max(10, target_w - 2 * padding)
    avail_h = max(10, target_h - 2 * padding)

    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)

    start_size = preferred_font_size if preferred_font_size else max_font_size
    best_font = get_font(start_size, font_path)
    best_lines: list[str] = [text]
    best_size = start_size

    # Search downward from start_size until text fits
    for size in range(start_size, min_font_size - 1, -1):
        f = get_font(size, font_path)
        lines = wrap_text_to_width(text, f, avail_w, draw)
        if not lines:
            continue

        line_h = int(size * 1.3)
        total_h = len(lines) * line_h

        # Verify max line width
        max_lw = 0
        for l in lines:
            bb = draw.textbbox((0, 0), l, font=f)
            max_lw = max(max_lw, bb[2] - bb[0])

        if total_h <= avail_h and max_lw <= avail_w:
            return f, lines, max_lw, total_h
        best_font = f
        best_lines = lines
        best_size = size

    # Return minimum font size if constrained
    min_f = get_font(min_font_size, font_path)
    lines = wrap_text_to_width(text, min_f, avail_w, draw)
    line_h = int(min_font_size * 1.3)
    return min_f, lines, avail_w, len(lines) * line_h


# ---------------------------------------------------------------------------
# Speech Bubble Shapes & Tail Geometry
# ---------------------------------------------------------------------------


def _calculate_tail_triangle(
    bx: float,
    by: float,
    bw: float,
    bh: float,
    tx: float,
    ty: float,
    tail_base_width: float = 24.0,
) -> list[tuple[float, float]]:
    """Compute 3 vertices for a pointer tail seamlessly connected to the bubble."""
    cx = bx + bw / 2.0
    cy = by + bh / 2.0
    dx = tx - cx
    dy = ty - cy
    dist = math.hypot(dx, dy)
    if dist < 1e-4:
        return []

    # Normal vector perpendicular to tail ray
    nx = -dy / dist
    ny = dx / dist

    # Anchor on the perimeter of the bubble box
    # Intersect ray with bubble bounding box
    rx = bw / 2.0
    ry = bh / 2.0
    if dist < max(rx, ry) * 0.75:
        return []  # Tail tip is inside or too close to bubble body

    scale_x = abs(rx / dx) if abs(dx) > 1e-4 else 1e5
    scale_y = abs(ry / dy) if abs(dy) > 1e-4 else 1e5
    scale = min(scale_x, scale_y) * 0.92  # slightly inset into bubble body
    if scale >= 0.98:
        return []

    ax = cx + dx * scale
    ay = cy + dy * scale

    half_w = tail_base_width / 2.0
    p1 = (ax + nx * half_w, ay + ny * half_w)
    p2 = (ax - nx * half_w, ay - ny * half_w)
    p3 = (tx, ty)
    return [p1, p2, p3]


def _make_starburst_polygon(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    num_points: int = 18,
    inner_ratio: float = 0.72,
    tail_tip: tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    """Generate dynamic sharp vertices for a shout / action starburst bubble."""
    points: list[tuple[float, float]] = []
    tail_idx = -1
    tail_ang = None

    if tail_tip:
        tail_ang = math.atan2(tail_tip[1] - cy, tail_tip[0] - cx)
        best_diff = 100.0
        for i in range(num_points * 2):
            if i % 2 == 1:
                ang = i * (math.pi / num_points)
                diff = abs(math.atan2(math.sin(ang - tail_ang), math.cos(ang - tail_ang)))
                if diff < best_diff:
                    best_diff = diff
                    tail_idx = i

    for i in range(num_points * 2):
        ang = i * (math.pi / num_points)
        if i == tail_idx and tail_tip:
            points.append(tail_tip)
        else:
            is_outer = (i % 2 == 1)
            scale = 1.05 if is_outer else inner_ratio
            px = cx + rx * scale * math.cos(ang)
            py = cy + ry * scale * math.sin(ang)
            points.append((px, py))

    return points


def _make_thought_cloud_lobes(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    num_lobes: int = 12,
) -> list[tuple[float, float, float]]:
    """Generate circle centers and radii for thought bubble cloud scallops."""
    lobes: list[tuple[float, float, float]] = []
    lobe_r = min(rx, ry) * 0.38
    for i in range(num_lobes):
        ang = i * (2.0 * math.pi / num_lobes)
        lx = cx + rx * 0.95 * math.cos(ang)
        ly = cy + ry * 0.95 * math.sin(ang)
        lobes.append((lx, ly, lobe_r))
    return lobes


# ---------------------------------------------------------------------------
# Bubble Overlay Rendering Engine
# ---------------------------------------------------------------------------


def render_speech_bubble_overlay(
    canvas_size: tuple[int, int],
    bubble: SpeechBubble,
    panel_rect: tuple[int, int, int, int] | None = None,
    default_font_path: str | None = None,
) -> Image.Image:
    """Render a single speech bubble onto a transparent RGBA overlay canvas."""
    cw, ch = canvas_size
    overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    # Determine coordinate reference (panel-relative or absolute page)
    if panel_rect is not None:
        px, py, pw, ph = panel_rect
        bx = px + bubble.x * pw if 0.0 <= bubble.x <= 1.0 else px + bubble.x
        by = py + bubble.y * ph if 0.0 <= bubble.y <= 1.0 else py + bubble.y
        bw = bubble.width * pw if (bubble.width and 0.0 < bubble.width <= 1.0) else (bubble.width or 220)
        bh = bubble.height * ph if (bubble.height and 0.0 < bubble.height <= 1.0) else (bubble.height or 110)
        tx = px + bubble.tail_x * pw if (bubble.tail_x is not None and 0.0 <= bubble.tail_x <= 1.0) else bubble.tail_x
        ty = py + bubble.tail_y * ph if (bubble.tail_y is not None and 0.0 <= bubble.tail_y <= 1.0) else bubble.tail_y
    else:
        bx = bubble.x * cw if 0.0 <= bubble.x <= 1.0 else bubble.x
        by = bubble.y * ch if 0.0 <= bubble.y <= 1.0 else bubble.y
        bw = bubble.width * cw if (bubble.width and 0.0 < bubble.width <= 1.0) else (bubble.width or 220)
        bh = bubble.height * ch if (bubble.height and 0.0 < bubble.height <= 1.0) else (bubble.height or 110)
        tx = bubble.tail_x * cw if (bubble.tail_x is not None and 0.0 <= bubble.tail_x <= 1.0) else bubble.tail_x
        ty = bubble.tail_y * ch if (bubble.tail_y is not None and 0.0 <= bubble.tail_y <= 1.0) else bubble.tail_y

    font_path = bubble.font_path or default_font_path
    clean_text = sanitize_manga_text(bubble.text)

    # Special handler: SFX (Sound Effects)
    if bubble.bubble_type == BubbleType.SFX:
        _render_sfx_text(
            overlay=overlay,
            text=clean_text,
            cx=bx,
            cy=by,
            font_size=bubble.font_size or 46,
            font_path=font_path,
            text_color=bubble.text_color,
            stroke_color=bubble.stroke_color,
            stroke_width=bubble.stroke_width or 6,
            rotation=bubble.rotation,
        )
        return overlay

    # For burst/shout bubbles, inner text area is limited by starburst valley ratio (~0.68)
    is_shout = (bubble.bubble_type == BubbleType.SHOUT)
    target_inner_w = int(bw * 0.65) if is_shout else int(bw)
    target_inner_h = int(bh * 0.65) if is_shout else int(bh)

    # Auto-fit text within bubble boundaries
    font, lines, text_w, text_h = fit_text_in_bubble(
        text=clean_text,
        target_w=target_inner_w,
        target_h=target_inner_h,
        font_path=font_path,
        preferred_font_size=bubble.font_size,
        padding=bubble.padding,
    )

    # Dynamic auto-sizing of bubble if requested
    if bubble.auto_size and (bubble.width is None or bubble.height is None):
        if is_shout:
            bw = max(bw, int((text_w + bubble.padding * 2 + 30) / 0.65))
            bh = max(bh, int((text_h + bubble.padding * 2 + 24) / 0.65))
        else:
            bw = max(bw, text_w + bubble.padding * 2 + 20)
            bh = max(bh, text_h + bubble.padding * 2 + 16)

    # Top-left corner from center coordinates
    x0 = int(bx - bw / 2.0)
    y0 = int(by - bh / 2.0)
    x1 = int(bx + bw / 2.0)
    y1 = int(by + bh / 2.0)

    # Colors
    is_inverted = (bubble.bubble_type == BubbleType.INVERTED)
    bg_color = (0, 0, 0, 245) if is_inverted else ImageColor.getrgb(bubble.bg_color)
    border_color = (255, 255, 255, 255) if is_inverted else ImageColor.getrgb(bubble.border_color)
    text_color = "#FFFFFF" if is_inverted else bubble.text_color
    border_w = max(1, bubble.border_width)

    # Masks for seamless border composition
    mask = Image.new("L", (cw, ch), 0)
    mask_draw = ImageDraw.Draw(mask)

    tail_tip = (tx, ty) if (tx is not None and ty is not None) else None

    # Draw shapes onto mask
    if bubble.bubble_type in (BubbleType.REGULAR, BubbleType.INVERTED):
        # Rounded rectangle body
        radius = min(int(bw * 0.28), int(bh * 0.28), 35)
        mask_draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=255)
        # Tail
        if tail_tip:
            tail_poly = _calculate_tail_triangle(x0, y0, bw, bh, tail_tip[0], tail_tip[1])
            if tail_poly:
                mask_draw.polygon(tail_poly, fill=255)

    elif bubble.bubble_type == BubbleType.THOUGHT:
        # Ellipse base
        mask_draw.ellipse([x0, y0, x1, y1], fill=255)
        # Cloud lobes
        lobes = _make_thought_cloud_lobes(bx, by, bw / 2.0, bh / 2.0, num_lobes=12)
        for lx, ly, lr in lobes:
            mask_draw.ellipse([lx - lr, ly - lr, lx + lr, ly + lr], fill=255)

    elif bubble.bubble_type == BubbleType.SHOUT:
        # Jagged starburst polygon
        points = _make_starburst_polygon(
            cx=bx, cy=by, rx=bw / 2.0, ry=bh / 2.0,
            num_points=16, inner_ratio=0.74, tail_tip=tail_tip
        )
        mask_draw.polygon(points, fill=255)

    elif bubble.bubble_type == BubbleType.CAPTION:
        # Crisp narrative box
        mask_draw.rectangle([x0, y0, x1, y1], fill=255)

    elif bubble.bubble_type == BubbleType.WHISPER:
        # Oval or rounded rect
        mask_draw.rounded_rectangle([x0, y0, x1, y1], radius=20, fill=255)

    # Composite border + fill using morphological dilation (ImageFilter.MaxFilter)
    # This guarantees 0 overlapping lines between tail and body
    if bubble.bubble_type == BubbleType.WHISPER:
        # Whisper: drawn with dashed border
        fill_img = Image.new("RGBA", (cw, ch), (*bg_color[:3], 240))
        overlay.paste(fill_img, (0, 0), mask)
        ov_draw = ImageDraw.Draw(overlay)
        # Dashed border
        _draw_dashed_rect(ov_draw, x0, y0, x1, y1, radius=20, color=border_color, width=border_w)
    else:
        # Standard dilated border technique
        filter_size = border_w * 2 + 1
        border_mask = mask.filter(ImageFilter.MaxFilter(filter_size))
        # Clear edges to avoid boundary bleeding / black artifacts
        b_draw = ImageDraw.Draw(border_mask)
        b_draw.rectangle([0, 0, cw - 1, ch - 1], outline=0, width=border_w + 1)

        border_img = Image.new("RGBA", (cw, ch), (*border_color[:3], 255))
        fill_img = Image.new("RGBA", (cw, ch), (*bg_color[:3], 255))
        overlay.paste(border_img, (0, 0), border_mask)
        overlay.paste(fill_img, (0, 0), mask)

    # For thought bubbles, draw trailing circles toward speaker outside bubble boundary
    if bubble.bubble_type == BubbleType.THOUGHT and tail_tip:
        _draw_thought_trail(
            overlay, bx, by, bw, bh, tail_tip[0], tail_tip[1],
            bg_color, border_color, border_w, panel_rect=panel_rect,
        )

    # Render wrapped text inside bubble
    text_draw = ImageDraw.Draw(overlay)
    line_h = int(font.size * 1.3)
    start_y = int(by - (len(lines) * line_h) / 2.0)

    for i, line in enumerate(lines):
        bbox = text_draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        if bubble.align == "left":
            lx = x0 + bubble.padding
        elif bubble.align == "right":
            lx = x1 - bubble.padding - lw
        else:  # Center
            lx = int(bx - lw / 2.0)
        ly = start_y + i * line_h
        text_draw.text((lx, ly), line, font=font, fill=text_color)

    return overlay


def _render_sfx_text(
    overlay: Image.Image,
    text: str,
    cx: float,
    cy: float,
    font_size: int = 46,
    font_path: str | None = None,
    text_color: str | tuple | None = None,
    stroke_color: str | tuple | None = None,
    stroke_width: int = 6,
    rotation: float = 0.0,
    with_energy_aura: bool = True,
) -> None:
    """Render manga sound effect (SFX) with 3D block extrusion, dual stroke outline,
    dynamic rotation, and blood lightning / energy aura accents.
    Automatically maps crude English onomatopoeia to authentic Vietnamese Manga SFX.
    """
    # 1. Map crude English sounds ("CLANNNG!", "BOOM!") to authentic Vietnamese Manga SFX
    try:
        try:
            from app.manga_sfx_dictionary import sanitize_manga_sfx
        except ImportError:
            from manga_sfx_dictionary import sanitize_manga_sfx
        sfx_meta = sanitize_manga_sfx(text)
        if not sfx_meta:
            # If silence or unrecognized non-SFX, do not draw violent blade clash
            return
        display_text = sfx_meta.get("vi", text.strip().upper())
        sfx_fill = sfx_meta.get("fill_color", (230, 30, 40))
        sfx_shadow = sfx_meta.get("shadow_color", (30, 0, 10))
        sfx_stroke = sfx_meta.get("stroke_color", (255, 255, 255))
        aura_type = sfx_meta.get("aura", "sparks")
    except Exception:
        display_text = text.strip().upper()
        sfx_fill = (230, 30, 40)
        sfx_shadow = (30, 0, 10)
        sfx_stroke = (255, 255, 255)
        aura_type = "sparks"

    # Color overrides if explicitly provided and not basic black/yellow defaults
    if text_color and text_color not in ("#000000", "#FFE600", (0, 0, 0)):
        if isinstance(text_color, str) and text_color.startswith("#"):
            try:
                sfx_fill = ImageColor.getrgb(text_color)
            except Exception:
                pass
        elif isinstance(text_color, (tuple, list)):
            sfx_fill = tuple(text_color[:3])

    if stroke_color and stroke_color not in ("#000000", (0, 0, 0)):
        if isinstance(stroke_color, str) and stroke_color.startswith("#"):
            try:
                sfx_stroke = ImageColor.getrgb(stroke_color)
            except Exception:
                pass
        elif isinstance(stroke_color, (tuple, list)):
            sfx_stroke = tuple(stroke_color[:3])

    # Load authentic manga SFX font (Bangers / Comic Neue Bold)
    font = get_font(font_size, font_path, font_category="sfx")
    outer_w = max(4, stroke_width + 4)

    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), display_text, font=font, stroke_width=outer_w)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad = outer_w * 2 + 50
    sfx_img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    sfx_draw = ImageDraw.Draw(sfx_img)

    text_x = pad - bbox[0]
    text_y = pad - bbox[1]

    # 1. 3D Extruded Block Shadow (diagonally down-right extrusion for tactile depth)
    extrusion_steps = max(4, min(10, font_size // 6))
    for step in range(extrusion_steps, 0, -2):
        sfx_draw.text(
            (text_x + step, text_y + step),
            display_text,
            font=font,
            fill=(*sfx_shadow, 240) if len(sfx_shadow) == 3 else sfx_shadow,
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 255),
        )

    # 2. Dual Stroke: Outer Highlighting Stroke (crisp white or bright contour)
    sfx_draw.text(
        (text_x, text_y),
        display_text,
        font=font,
        fill=(*sfx_stroke, 255) if len(sfx_stroke) == 3 else sfx_stroke,
        stroke_width=outer_w,
        stroke_fill=(*sfx_stroke, 255) if len(sfx_stroke) == 3 else sfx_stroke,
    )

    # 3. Dual Stroke: Inner Heavy Black Stroke + Crimson/Amber Body Fill
    sfx_draw.text(
        (text_x, text_y),
        display_text,
        font=font,
        fill=(*sfx_fill, 255) if len(sfx_fill) == 3 else sfx_fill,
        stroke_width=stroke_width,
        stroke_fill=(0, 0, 0, 255),
    )

    # 4. SFX text rendering: Clean 3D block extrusion, outer halo, and bold core fill.
    # (Removed clumsy zigzag wire overlay to preserve pristine manga typography)

    # 5. Dynamic Rotation
    eff_rotation = rotation if abs(rotation) > 0.1 else -12.0
    sfx_img = sfx_img.rotate(eff_rotation, resample=Image.Resampling.BICUBIC, expand=True)

    # 6. Paste centered at (cx, cy)
    left = int(cx - sfx_img.width / 2.0)
    top = int(cy - sfx_img.height / 2.0)
    overlay.paste(sfx_img, (left, top), sfx_img)


def _draw_thought_trail(
    overlay: Image.Image,
    bx: float,
    by: float,
    bw: float,
    bh: float,
    tx: float,
    ty: float,
    bg_color: tuple,
    border_color: tuple,
    border_w: int,
    panel_rect: tuple[int, int, int, int] | None = None,
) -> None:
    """Draw 3 decreasing circles trailing towards speaker for thought bubbles,
    strictly outside bubble body and safely inset from panel/frame borders."""
    draw = ImageDraw.Draw(overlay)
    cw, ch = overlay.size
    if panel_rect is not None:
        rx, ry, rw, rh = panel_rect
    else:
        rx, ry, rw, rh = 0, 0, cw, ch

    side_margin = max(14.0, border_w + 10.0)
    bottom_margin = max(24.0, border_w + 20.0)
    safe_x0 = rx + side_margin
    safe_y0 = ry + side_margin
    safe_x1 = rx + rw - side_margin
    safe_y1 = ry + rh - bottom_margin

    if safe_x1 <= safe_x0 or safe_y1 <= safe_y0:
        return

    def _max_ray_t(ux_v: float, uy_v: float) -> float:
        ts: list[float] = []
        if ux_v > 1e-6:
            ts.append((safe_x1 - bx) / ux_v)
        elif ux_v < -1e-6:
            ts.append((safe_x0 - bx) / ux_v)
        if uy_v > 1e-6:
            ts.append((safe_y1 - by) / uy_v)
        elif uy_v < -1e-6:
            ts.append((safe_y0 - by) / uy_v)
        pos_ts = [t for t in ts if t > 0]
        return min(pos_ts) if pos_ts else 0.0

    def _edge_start_d(ux_v: float, uy_v: float) -> float:
        a = bw / 2.0
        b = bh / 2.0
        lobe_pad = min(a, b) * 0.25
        denom = math.sqrt((b * ux_v) ** 2 + (a * uy_v) ** 2)
        r_edge = ((a * b) / denom if denom > 0 else a) + lobe_pad
        return r_edge + 6.0

    dx = tx - bx
    dy = ty - by
    dist = math.hypot(dx, dy)
    if dist < 5.0:
        return
    ux = dx / dist
    uy = dy / dist

    start_d = _edge_start_d(ux, uy)
    max_t = _max_ray_t(ux, uy)

    # If the target direction runs too close to the bottom or outer panel edge,
    # gently redirect the trail inward toward the upper-center interior of the panel.
    if max_t - start_d < 18.0:
        alt_dx = (rx + rw * 0.5) - bx
        alt_dy = (ry + rh * 0.45) - by
        if by > ry + rh * 0.55 and alt_dy > -12.0:
            alt_dy = -max(24.0, bh * 0.35)
        alt_dist = math.hypot(alt_dx, alt_dy)
        if alt_dist >= 5.0:
            alt_ux = alt_dx / alt_dist
            alt_uy = alt_dy / alt_dist
            alt_start = _edge_start_d(alt_ux, alt_uy)
            alt_max_t = _max_ray_t(alt_ux, alt_uy)
            if alt_max_t - alt_start > max_t - start_d:
                ux, uy = alt_ux, alt_uy
                start_d, max_t = alt_start, alt_max_t
                dist = min(alt_dist, alt_max_t)

    end_d = min(dist - 6.0, max_t - 6.0)
    if end_d <= start_d + 8.0:
        end_d = min(max_t - 4.0, start_d + 24.0)
    if end_d <= start_d:
        return

    fractions = [0.15, 0.50, 0.85]
    radii = [10, 7, 4]
    for frac, r in zip(fractions, radii):
        cur_d = start_d + (end_d - start_d) * frac
        dot_x = max(safe_x0 + r, min(safe_x1 - r, bx + ux * cur_d))
        dot_y = max(safe_y0 + r, min(safe_y1 - r, by + uy * cur_d))
        # Outer border
        draw.ellipse([dot_x - r, dot_y - r, dot_x + r, dot_y + r], fill=border_color)
        # Inner fill
        ir = max(1, r - border_w)
        draw.ellipse([dot_x - ir, dot_y - ir, dot_x + ir, dot_y + ir], fill=bg_color)


def _draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    radius: int,
    color: tuple,
    width: int,
    dash_len: int = 8,
    gap_len: int = 6,
) -> None:
    """Draw dashed border for whisper dialogue bubbles."""
    perimeter_segments = [
        ((x0 + radius, y0), (x1 - radius, y0)),
        ((x1, y0 + radius), (x1, y1 - radius)),
        ((x1 - radius, y1), (x0 + radius, y1)),
        ((x0, y1 - radius), (x0, y0 + radius)),
    ]
    for (sx, sy), (ex, ey) in perimeter_segments:
        length = math.hypot(ex - sx, ey - sy)
        if length < 1:
            continue
        dx = (ex - sx) / length
        dy = (ey - sy) / length
        curr = 0.0
        drawing = True
        while curr < length:
            step = dash_len if drawing else gap_len
            next_curr = min(length, curr + step)
            if drawing:
                draw.line(
                    [(sx + dx * curr, sy + dy * curr), (sx + dx * next_curr, sy + dy * next_curr)],
                    fill=color,
                    width=width,
                )
            curr = next_curr
            drawing = not drawing


# ---------------------------------------------------------------------------
# B&W Screentone, Halftone & Japanese Color Filters
# ---------------------------------------------------------------------------


def apply_halftone_dots(
    image: Image.Image,
    grid_size: int = 8,
    dot_scale: float = 0.707,
) -> Image.Image:
    """Convert an image to classic Japanese manga dot screentone."""
    gray = ImageOps.grayscale(image)
    gw, gh = gray.size

    # Fast downsampling to get average luminance for each cell
    small_w = max(1, gw // grid_size)
    small_h = max(1, gh // grid_size)
    small = gray.resize((small_w, small_h), Image.Resampling.BILINEAR)
    pixels = small.load()

    dot_img = Image.new("L", (gw, gh), 255)
    draw = ImageDraw.Draw(dot_img)
    max_r = grid_size * dot_scale

    for sy in range(small_h):
        cy = sy * grid_size + grid_size / 2.0
        for sx in range(small_w):
            lum = pixels[sx, sy]
            if lum < 248:  # Don't draw dots in pure white areas
                r = (1.0 - (lum / 255.0)) * max_r
                if r > 0.4:
                    cx = sx * grid_size + grid_size / 2.0
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)

    # Return RGB image with screentone
    return dot_img.convert("RGB")


def apply_dither(image: Image.Image, mode: str = "floyd") -> Image.Image:
    """Apply retro 1-bit monochrome dithering (Floyd-Steinberg)."""
    gray = ImageOps.grayscale(image)
    dithered = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    return dithered.convert("RGB")


def apply_manga_ink(
    image: Image.Image,
    contrast: float = 2.2,
    threshold: int = 128,
) -> Image.Image:
    """High-contrast Japanese manga inking with edge definition."""
    gray = ImageOps.grayscale(image)
    boosted = ImageEnhance.Contrast(gray).enhance(contrast)
    # Binary thresholding for ink lines
    ink = boosted.point(lambda p: 255 if p > threshold else 0)
    return ink.convert("RGB")


def apply_speedlines_radial(
    image: Image.Image,
    center: tuple[int, int] | None = None,
    inner_radius: int = 60,
    density: int = 70,
    line_color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Overlay dynamic shonen action radial speedlines."""
    w, h = image.size
    cx = center[0] if center else w / 2.0
    cy = center[1] if center else h / 2.0
    max_r = math.hypot(w, h)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = random.Random(42)

    for _ in range(density):
        ang = rng.uniform(0, 2 * math.pi)
        start_r = rng.uniform(inner_radius, inner_radius * 1.6)
        x1 = cx + start_r * math.cos(ang)
        y1 = cy + start_r * math.sin(ang)
        x2 = cx + max_r * math.cos(ang)
        y2 = cy + max_r * math.sin(ang)
        line_w = rng.randint(1, 3)
        alpha = rng.randint(180, 255)
        draw.line([(x1, y1), (x2, y2)], fill=(*line_color, alpha), width=line_w)

    base = image.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


def apply_speedlines_horizontal(
    image: Image.Image,
    density: int = 50,
    line_color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Overlay horizontal motion speedlines for fast action sequences."""
    w, h = image.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = random.Random(42)

    for _ in range(density):
        y = rng.randint(0, h)
        length = rng.randint(w // 4, w)
        start_x = rng.choice([0, w - length, rng.randint(0, w - length)])
        line_w = rng.randint(1, 2)
        alpha = rng.randint(140, 240)
        draw.line([(start_x, y), (start_x + length, y)], fill=(*line_color, alpha), width=line_w)

    base = image.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


def apply_color_pastel(image: Image.Image) -> Image.Image:
    """Japanese modern anime/manga pastel color adjustment."""
    rgb = image.convert("RGB")
    # Soften saturation slightly, boost brightness and gentle contrast
    soft_color = ImageEnhance.Color(rgb).enhance(0.88)
    soft_bright = ImageEnhance.Brightness(soft_color).enhance(1.06)
    enhanced = ImageEnhance.Contrast(soft_bright).enhance(1.08)
    return enhanced


def apply_color_vibrant(image: Image.Image) -> Image.Image:
    """Shonen action bold vibrant color grading."""
    rgb = image.convert("RGB")
    vibrant = ImageEnhance.Color(rgb).enhance(1.35)
    contrasted = ImageEnhance.Contrast(vibrant).enhance(1.18)
    sharp = ImageEnhance.Sharpness(contrasted).enhance(1.2)
    return sharp


def apply_color_sepia(image: Image.Image) -> Image.Image:
    """Vintage manga pulp paper and sepia ink color tone."""
    gray = ImageOps.grayscale(image)
    # Colorize: deep ink black (#1b1411), warm ivory white (#faf5e8), warm sepia mid (#c8a882)
    sepia = ImageOps.colorize(gray, black="#1b1411", white="#faf5e8", mid="#c8a882")
    return sepia


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
    orig_mode = image.mode
    img = image.convert("RGB")
    try:
        import numpy as np
        arr = np.array(img, dtype=np.float32)
        h, w, c = arr.shape
        rng = np.random.RandomState(42)

        # 1. High-frequency organic paper grain noise
        noise = rng.normal(0.0, 22.0 * grain_intensity, (h, w, 1))

        # 2. Authentic manga dot screentone simulation in midtones (to break AI plastic gradients)
        y_idx, x_idx = np.ogrid[:h, :w]
        screentone_dots = ((x_idx % screentone_pitch == 0) & (y_idx % screentone_pitch == 0)).astype(np.float32)[:, :, np.newaxis]
        luminance = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        midtones = ((luminance > 35.0) & (luminance < 225.0))[:, :, np.newaxis]

        textured = arr + noise + (screentone_dots * midtones * -12.0)
        textured = np.clip(textured, 0, 255).astype(np.uint8)
        result = Image.fromarray(textured)
    except Exception:
        # Fallback without numpy: PIL filter grain & high-pass simulation
        result = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

    # 3. G-pen edge sharpness & Chiaroscuro dynamic contrast boost
    if sharpness > 1.0:
        result = ImageEnhance.Sharpness(result).enhance(sharpness)
    if gpen_contrast > 1.0:
        result = ImageEnhance.Contrast(result).enhance(gpen_contrast)

    if orig_mode == "RGBA":
        result = result.convert("RGBA")
    return result


def apply_panel_filter(
    image: Image.Image,
    filter_type: PanelFilter | str,
    params: dict[str, Any] | None = None,
) -> Image.Image:
    """Route and apply the requested manga filter to an image."""
    p = params or {}
    f_str = filter_type.value if isinstance(filter_type, PanelFilter) else str(filter_type)

    if f_str == PanelFilter.HALFTONE_DOTS.value:
        grid_size = p.get("grid_size", 8)
        return apply_halftone_dots(image, grid_size=grid_size)
    elif f_str == PanelFilter.DITHER.value:
        return apply_dither(image)
    elif f_str == PanelFilter.INK.value:
        contrast = p.get("contrast", 2.2)
        threshold = p.get("threshold", 128)
        return apply_manga_ink(image, contrast=contrast, threshold=threshold)
    elif f_str == PanelFilter.SPEEDLINES_RADIAL.value:
        inner_r = p.get("inner_radius", 60)
        density = p.get("density", 70)
        return apply_speedlines_radial(image, inner_radius=inner_r, density=density)
    elif f_str == PanelFilter.SPEEDLINES_HORIZONTAL.value:
        density = p.get("density", 50)
        return apply_speedlines_horizontal(image, density=density)
    elif f_str == PanelFilter.PASTEL.value:
        return apply_color_pastel(image)
    elif f_str == PanelFilter.VIBRANT.value:
        return apply_color_vibrant(image)
    elif f_str == PanelFilter.SEPIA.value:
        return apply_color_sepia(image)
    elif f_str in (PanelFilter.DE_AI_ORGANIC.value, PanelFilter.G_PEN_GRAIN.value):
        grain_intensity = p.get("grain_intensity", 0.08)
        contrast = p.get("contrast", 1.25)
        sharpness = p.get("sharpness", 1.45)
        screentone_pitch = p.get("screentone_pitch", 4)
        return apply_de_ai_organic_enhancer(
            image,
            grain_intensity=grain_intensity,
            gpen_contrast=contrast,
            sharpness=sharpness,
            screentone_pitch=screentone_pitch,
        )
    return image


# ---------------------------------------------------------------------------
# Panel Layout & Gutters Framing Engine
# ---------------------------------------------------------------------------


def compute_panel_rects(
    layout_type: PanelLayoutType | str,
    page_width: int,
    page_height: int,
    margin_x: int = 40,
    margin_y: int = 40,
    gutter_x: int = 16,
    gutter_y: int = 16,
    reading_direction: str = "rtl",
    custom_rects: list[tuple[float, float, float, float]] | None = None,
) -> list[tuple[int, int, int, int]]:
    """Compute exact pixel [x, y, w, h] bounding boxes for panel layouts."""
    l_str = layout_type.value if isinstance(layout_type, PanelLayoutType) else str(layout_type)

    avail_w = page_width - 2 * margin_x
    avail_h = page_height - 2 * margin_y
    is_rtl = (reading_direction.lower() == "rtl")

    # Custom rects
    if l_str == PanelLayoutType.CUSTOM.value:
        if custom_rects:
            rects: list[tuple[int, int, int, int]] = []
            for r in custom_rects:
                rx, ry, rw, rh = r
                if 0.0 <= rx <= 1.0 and 0.0 <= rw <= 1.0:
                    px = int(rx * page_width)
                    py = int(ry * page_height)
                    pw = int(rw * page_width)
                    ph = int(rh * page_height)
                else:
                    px, py, pw, ph = int(rx), int(ry), int(rw), int(rh)
                rects.append((px, py, pw, ph))
            return rects
        # Default fallback to single splash
        return [(margin_x, margin_y, avail_w, avail_h)]

    # Single Splash
    if l_str == PanelLayoutType.SINGLE.value:
        return [(margin_x, margin_y, avail_w, avail_h)]

    # Yonkoma (4-koma: 4 vertical panels)
    if l_str == PanelLayoutType.YONKOMA.value:
        ph = int((avail_h - 3 * gutter_y) / 4)
        return [
            (margin_x, int(margin_y + i * (ph + gutter_y)), avail_w, ph)
            for i in range(4)
        ]

    # Grid 2x2 (4 panels)
    if l_str == PanelLayoutType.GRID_2X2.value:
        pw = int((avail_w - gutter_x) / 2)
        ph = int((avail_h - gutter_y) / 2)
        col_right = margin_x + pw + gutter_x
        col_left = margin_x
        c0 = col_right if is_rtl else col_left
        c1 = col_left if is_rtl else col_right
        return [
            (c0, margin_y, pw, ph),
            (c1, margin_y, pw, ph),
            (c0, margin_y + ph + gutter_y, pw, ph),
            (c1, margin_y + ph + gutter_y, pw, ph),
        ]

    # Grid 1x2 (1 column, 2 vertical panels)
    if l_str == PanelLayoutType.GRID_1X2.value:
        ph = int((avail_h - gutter_y) / 2)
        return [
            (margin_x, margin_y, avail_w, ph),
            (margin_x, margin_y + ph + gutter_y, avail_w, ph),
        ]

    # Grid 2x1 (2 horizontal panels)
    if l_str == PanelLayoutType.GRID_2X1.value:
        pw = int((avail_w - gutter_x) / 2)
        c0 = margin_x + pw + gutter_x if is_rtl else margin_x
        c1 = margin_x if is_rtl else margin_x + pw + gutter_x
        return [
            (c0, margin_y, pw, avail_h),
            (c1, margin_y, pw, avail_h),
        ]

    # Top 1, Bottom 2
    if l_str == PanelLayoutType.TOP1_BOTTOM2.value:
        top_h = int(avail_h * 0.45)
        bot_h = avail_h - top_h - gutter_y
        pw = int((avail_w - gutter_x) / 2)
        c0 = margin_x + pw + gutter_x if is_rtl else margin_x
        c1 = margin_x if is_rtl else margin_x + pw + gutter_x
        return [
            (margin_x, margin_y, avail_w, top_h),
            (c0, margin_y + top_h + gutter_y, pw, bot_h),
            (c1, margin_y + top_h + gutter_y, pw, bot_h),
        ]

    # Top 2, Bottom 1
    if l_str == PanelLayoutType.TOP2_BOTTOM1.value:
        top_h = int(avail_h * 0.52)
        bot_h = avail_h - top_h - gutter_y
        pw = int((avail_w - gutter_x) / 2)
        c0 = margin_x + pw + gutter_x if is_rtl else margin_x
        c1 = margin_x if is_rtl else margin_x + pw + gutter_x
        return [
            (c0, margin_y, pw, top_h),
            (c1, margin_y, pw, top_h),
            (margin_x, margin_y + top_h + gutter_y, avail_w, bot_h),
        ]

    # Three Rows
    if l_str == PanelLayoutType.THREE_ROWS.value:
        ph = int((avail_h - 2 * gutter_y) / 3)
        return [
            (margin_x, int(margin_y + i * (ph + gutter_y)), avail_w, ph)
            for i in range(3)
        ]

    # Action 5: dynamic shonen layout
    if l_str == PanelLayoutType.ACTION_5.value:
        h1 = int(avail_h * 0.30)
        h2 = int(avail_h * 0.35)
        h3 = avail_h - h1 - h2 - 2 * gutter_y
        w2a = int((avail_w - gutter_x) * 0.58)
        w2b = avail_w - gutter_x - w2a
        c2a = margin_x + w2b + gutter_x if is_rtl else margin_x
        c2b = margin_x if is_rtl else margin_x + w2a + gutter_x
        w3a = int((avail_w - gutter_x) * 0.42)
        w3b = avail_w - gutter_x - w3a
        c3a = margin_x + w3b + gutter_x if is_rtl else margin_x
        c3b = margin_x if is_rtl else margin_x + w3a + gutter_x
        y2 = margin_y + h1 + gutter_y
        y3 = y2 + h2 + gutter_y
        return [
            (margin_x, margin_y, avail_w, h1),
            (c2a, y2, w2a, h2),
            (c2b, y2, w2b, h2),
            (c3a, y3, w3a, h3),
            (c3b, y3, w3b, h3),
        ]

    # Drama 6: 3 rows x 2 cols
    if l_str == PanelLayoutType.DRAMA_6.value:
        pw = int((avail_w - gutter_x) / 2)
        ph = int((avail_h - 2 * gutter_y) / 3)
        c0 = margin_x + pw + gutter_x if is_rtl else margin_x
        c1 = margin_x if is_rtl else margin_x + pw + gutter_x
        rects = []
        for r in range(3):
            ry = int(margin_y + r * (ph + gutter_y))
            rects.append((c0, ry, pw, ph))
            rects.append((c1, ry, pw, ph))
        return rects

    # Default fallback
    return [(margin_x, margin_y, avail_w, avail_h)]


def fit_image_to_rect(
    src: Image.Image,
    target_size: tuple[int, int],
    fit_mode: FitMode = FitMode.COVER,
    bg_color: str = "#FFFFFF",
) -> Image.Image:
    """Scale and crop an image to target (width, height) using cover/contain/stretch."""
    tw, th = target_size
    if tw <= 0 or th <= 0:
        return Image.new("RGB", (1, 1), bg_color)

    sw, sh = src.size
    if fit_mode == FitMode.STRETCH:
        return src.resize((tw, th), Image.Resampling.LANCZOS)

    src_ratio = sw / max(1, sh)
    tgt_ratio = tw / max(1, th)

    if fit_mode == FitMode.COVER:
        if src_ratio > tgt_ratio:
            new_h = th
            new_w = max(tw, int(th * src_ratio))
        else:
            new_w = tw
            new_h = max(th, int(tw / src_ratio))
        resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))

    elif fit_mode == FitMode.CONTAIN:
        if src_ratio > tgt_ratio:
            new_w = tw
            new_h = max(1, int(tw / src_ratio))
        else:
            new_h = th
            new_w = max(1, int(th * src_ratio))
        resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
        bg = ImageColor.getrgb(bg_color)
        out = Image.new("RGB", (tw, th), bg)
        left = (tw - new_w) // 2
        top = (th - new_h) // 2
        out.paste(resized, (left, top))
        return out

    return src


def create_panel_placeholder(
    width: int,
    height: int,
    panel_index: int = 1,
    prompt: str = "",
    font_path: str | None = None,
) -> Image.Image:
    """Generate a clean manga storyboard sketch placeholder canvas."""
    img = Image.new("RGB", (width, height), (248, 248, 250))
    draw = ImageDraw.Draw(img)

    # Subtle inner diagonal cross sketch
    draw.line([(0, 0), (width, height)], fill=(235, 235, 240), width=1)
    draw.line([(0, height), (width, 0)], fill=(235, 235, 240), width=1)

    # Panel index badge
    badge_text = f"Panel {panel_index}"
    f_badge = get_font(max(16, min(width, height) // 14), font_path)
    bbox = draw.textbbox((0, 0), badge_text, font=f_badge)
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    bx = (width - bw) // 2
    by = (height - bh) // 2 - 10
    draw.text((bx, by), badge_text, font=f_badge, fill=(120, 120, 130))

    if prompt:
        short_prompt = prompt if len(prompt) < 45 else prompt[:42] + "..."
        f_p = get_font(max(11, min(width, height) // 24), font_path)
        p_bbox = draw.textbbox((0, 0), short_prompt, font=f_p)
        pw = p_bbox[2] - p_bbox[0]
        draw.text(((width - pw) // 2, by + bh + 12), short_prompt, font=f_p, fill=(160, 160, 170))

    return img


# ---------------------------------------------------------------------------
# Core Manga Composer Engine
# ---------------------------------------------------------------------------


class MangaComposer:
    """Orchestrates panel rendering, layout framing, filters, bubbles, and multi-format export."""

    def __init__(self, default_font_path: str | None = None):
        self.default_font_path = resolve_font_path(default_font_path)

    def load_panel_image(
        self,
        panel: PanelConfig,
        target_size: tuple[int, int],
        panel_index: int = 1,
    ) -> Image.Image:
        """Load image from path, base64 data URL, or generate placeholder."""
        w, h = target_size
        img: Image.Image | None = None

        # 1. Load from file path
        if panel.image_path and os.path.exists(panel.image_path):
            try:
                img = Image.open(panel.image_path).convert("RGB")
            except Exception:
                img = None

        # 2. Load from base64 data URL
        elif panel.image_data:
            try:
                data_str = panel.image_data
                if "," in data_str:
                    data_str = data_str.split(",", 1)[1]
                raw_bytes = base64.b64decode(data_str)
                img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            except Exception:
                img = None

        # 3. Fallback placeholder
        if img is None:
            img = create_panel_placeholder(
                width=w,
                height=h,
                panel_index=panel_index,
                prompt=panel.prompt or panel.description or "",
                font_path=self.default_font_path,
            )

        # Scale to frame
        fitted = fit_image_to_rect(img, target_size, fit_mode=panel.fit_mode, bg_color=panel.bg_color)

        # Apply filter if specified
        if panel.filter != PanelFilter.NONE:
            fitted = apply_panel_filter(fitted, panel.filter, panel.filter_params)

        return fitted

    def compose_page(self, config: PageConfig) -> Image.Image:
        """Compose a full manga page with framed panels, gutters, and speech bubbles."""
        page = Image.new("RGBA", (config.width, config.height), config.background_color)
        draw = ImageDraw.Draw(page)

        # Compute panel bounding boxes
        custom_rects = None
        if config.layout_type == PanelLayoutType.CUSTOM:
            custom_rects = [p.rect for p in config.panels if p.rect is not None]

        panel_rects = compute_panel_rects(
            layout_type=config.layout_type,
            page_width=config.width,
            page_height=config.height,
            margin_x=config.margin_x,
            margin_y=config.margin_y,
            gutter_x=config.gutter_x,
            gutter_y=config.gutter_y,
            reading_direction=config.reading_direction,
            custom_rects=custom_rects,
        )

        all_bubbles: list[tuple[SpeechBubble, tuple[int, int, int, int] | None]] = []

        # Render each panel into its frame
        for i, rect in enumerate(panel_rects):
            px, py, pw, ph = rect
            p_config = config.panels[i] if i < len(config.panels) else PanelConfig()

            # Render panel artwork
            panel_img = self.load_panel_image(p_config, (pw, ph), panel_index=i + 1)
            page.paste(panel_img, (px, py))

            # Draw panel border
            bw = p_config.border_width
            if bw > 0:
                b_color = ImageColor.getrgb(p_config.border_color)
                # Outer rectangle border
                for w_off in range(bw):
                    draw.rectangle(
                        [px + w_off, py + w_off, px + pw - 1 - w_off, py + ph - 1 - w_off],
                        outline=b_color,
                    )

            # Vision QA & Anti-Collision Face Avoidance check before rendering speech bubbles
            auto_optimize = getattr(p_config, "auto_layout_bubbles", False) or getattr(config, "auto_layout_bubbles", False)
            if p_config.bubbles and auto_optimize:
                try:
                    try:
                        from app.manga_vision_qa import MangaVisionQA
                    except ImportError:
                        from manga_vision_qa import MangaVisionQA

                    qa = MangaVisionQA(min_clearance_px=25)
                    qa_result = qa.verify_panel_typesetting(
                        panel_image=panel_img,
                        bubbles_config=p_config.bubbles,
                        panel_index=i + 1,
                    )

                    # If face collision detected, automatically resolve to optimal negative space
                    if not qa_result.is_valid and qa_result.face_bbox is not None:
                        for col in qa_result.face_collisions:
                            b_idx = col["bubble_index"]
                            if 0 <= b_idx < len(p_config.bubbles):
                                b = p_config.bubbles[b_idx]
                                bw_ratio = getattr(b, "width", None) or 0.35
                                bh_ratio = getattr(b, "height", None) or 0.20
                                b_type = getattr(b, "bubble_type", "regular")
                                b_type_str = b_type.value if hasattr(b_type, "value") else str(b_type)

                                new_x, new_y = qa.solve_optimal_negative_space(
                                    panel_w=pw,
                                    panel_h=ph,
                                    face_bbox=qa_result.face_bbox,
                                    bubble_w_ratio=bw_ratio,
                                    bubble_h_ratio=bh_ratio,
                                    bubble_type=b_type_str,
                                )
                                b.x = new_x
                                b.y = new_y
                                # Point tail towards mouth if not caption
                                if b_type_str != "caption":
                                    mouth_x = qa_result.face_bbox.center[0] / float(pw)
                                    mouth_y = (qa_result.face_bbox.y0 + qa_result.face_bbox.height * 0.85) / float(ph)
                                    b.tail_x = round(mouth_x, 3)
                                    b.tail_y = round(mouth_y, 3)
                except Exception:
                    pass

                # Also run multi-bubble anti-collision packing if multiple bubbles
                if len(p_config.bubbles) > 1:
                    try:
                        try:
                            from app.smart_bubble_layout import optimize_speech_bubbles
                        except ImportError:
                            from smart_bubble_layout import optimize_speech_bubbles
                        p_config.bubbles = optimize_speech_bubbles(
                            p_config.bubbles,
                            panel_w=pw,
                            panel_h=ph,
                            reading_direction=config.reading_direction,
                            panel_image=panel_img,
                        )
                    except Exception:
                        pass
            for bubble in p_config.bubbles:
                all_bubbles.append((bubble, rect))

        # Queue page-level speech bubbles
        for bubble in config.page_bubbles:
            all_bubbles.append((bubble, None))

        # Render and composite speech bubbles on top
        for bubble, rect in all_bubbles:
            bubble_overlay = render_speech_bubble_overlay(
                canvas_size=(config.width, config.height),
                bubble=bubble,
                panel_rect=rect,
                default_font_path=self.default_font_path,
            )
            page.alpha_composite(bubble_overlay)

        return page.convert("RGB")


# ---------------------------------------------------------------------------
# Multi-Format Export Engine (PNG, CBZ, Multi-Page PDF)
# ---------------------------------------------------------------------------


def export_page_to_png(page_image: Image.Image, output_path: str | Path) -> Path:
    """Export a single rendered manga page to PNG."""
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    page_image.save(out_p, format="PNG", optimize=True)
    return out_p


def _build_comic_info_xml(metadata: ComicMetadata | dict[str, Any] | None) -> str:
    """Generate standard ComicInfo.xml for comic book readers."""
    if metadata is None:
        meta = ComicMetadata()
    elif isinstance(metadata, dict):
        meta = ComicMetadata(**metadata)
    else:
        meta = metadata

    root = ET.Element("ComicInfo")
    ET.SubElement(root, "Title").text = meta.title
    ET.SubElement(root, "Series").text = meta.series
    ET.SubElement(root, "Number").text = meta.issue_or_chapter
    ET.SubElement(root, "Volume").text = meta.volume
    ET.SubElement(root, "Summary").text = meta.summary
    ET.SubElement(root, "Writer").text = meta.writer
    ET.SubElement(root, "Penciller").text = meta.penciller
    ET.SubElement(root, "Genre").text = meta.genre
    ET.SubElement(root, "PageCount").text = str(meta.page_count)
    ET.SubElement(root, "LanguageISO").text = meta.language
    if meta.manga:
        ET.SubElement(root, "Manga").text = "YesAndRightToLeft"

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def export_to_cbz(
    pages: list[Image.Image] | list[str | Path],
    output_path: str | Path,
    metadata: ComicMetadata | dict[str, Any] | None = None,
) -> Path:
    """Export a sequence of manga pages into a CBZ (Comic Book Zip) archive."""
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    page_images: list[Image.Image] = []
    for item in pages:
        if isinstance(item, Image.Image):
            page_images.append(item)
        else:
            page_images.append(Image.open(item))

    # Update page count in metadata
    if metadata is None:
        meta = ComicMetadata(page_count=len(page_images))
    elif isinstance(metadata, dict):
        meta = ComicMetadata(**{**metadata, "page_count": len(page_images)})
    else:
        meta = metadata
        meta.page_count = len(page_images)

    with zipfile.ZipFile(out_p, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write ComicInfo.xml metadata
        xml_content = _build_comic_info_xml(meta)
        zf.writestr("ComicInfo.xml", xml_content)

        # Write sequential page images
        for idx, page in enumerate(page_images, start=1):
            buf = io.BytesIO()
            page.convert("RGB").save(buf, format="PNG")
            zf.writestr(f"page_{idx:03d}.png", buf.getvalue())

    return out_p


def export_to_pdf(
    pages: list[Image.Image] | list[str | Path],
    output_path: str | Path,
    dpi: int = 150,
) -> Path:
    """Export a sequence of manga pages to a multi-page PDF document."""
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if not pages:
        raise ValueError("Cannot export empty pages list to PDF.")

    rgb_pages: list[Image.Image] = []
    for item in pages:
        if isinstance(item, Image.Image):
            rgb_pages.append(item.convert("RGB"))
        else:
            rgb_pages.append(Image.open(item).convert("RGB"))

    first_page = rgb_pages[0]
    other_pages = rgb_pages[1:] if len(rgb_pages) > 1 else []

    first_page.save(
        out_p,
        format="PDF",
        save_all=True,
        append_images=other_pages,
        resolution=float(dpi),
    )

    return out_p


def export_chapter(
    pages: list[Image.Image] | list[PageConfig],
    output_dir: str | Path,
    base_name: str = "chapter_01",
    export_png: bool = True,
    export_cbz: bool = True,
    export_pdf: bool = True,
    metadata: ComicMetadata | dict[str, Any] | None = None,
    dpi: int = 150,
    validate_quality: bool = False,
) -> dict[str, Any]:
    """Batch export an entire manga chapter to PNG pages, CBZ, and multi-page PDF."""
    out_d = Path(output_dir).resolve() / base_name
    out_d.mkdir(parents=True, exist_ok=True)

    composer = MangaComposer()
    rendered_pages: list[Image.Image] = []

    for item in pages:
        if isinstance(item, PageConfig):
            rendered_pages.append(composer.compose_page(item))
        elif isinstance(item, Image.Image):
            rendered_pages.append(item)
        else:
            rendered_pages.append(Image.open(item))

    # Strict QA Gate: Validate visual content before release
    qa_report = None
    if validate_quality:
        from manga_validator import validate_chapter_release
        qa_report = validate_chapter_release(rendered_pages, raise_on_failure=True)

    results: dict[str, Any] = {
        "output_dir": str(out_d),
        "page_count": len(rendered_pages),
        "qa_report": qa_report,
        "files": {},
    }

    # 1. Export PNG pages
    if export_png:
        png_paths: list[str] = []
        for idx, p in enumerate(rendered_pages, start=1):
            p_path = out_d / f"page_{idx:03d}.png"
            export_page_to_png(p, p_path)
            png_paths.append(str(p_path))
        results["files"]["png_pages"] = png_paths

    # 2. Export CBZ
    if export_cbz:
        cbz_path = out_d / f"{base_name}.cbz"
        export_to_cbz(rendered_pages, cbz_path, metadata=metadata)
        results["files"]["cbz"] = str(cbz_path)

    # 3. Export PDF
    if export_pdf:
        pdf_path = out_d / f"{base_name}.pdf"
        export_to_pdf(rendered_pages, pdf_path, dpi=dpi)
        results["files"]["pdf"] = str(pdf_path)

    return results


def image_to_base64_data_url(img: Image.Image, format: str = "PNG") -> str:
    """Helper to convert PIL Image to base64 data URL for UI rendering."""
    buf = io.BytesIO()
    img.save(buf, format=format)
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    mime = "image/png" if format.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"


# ---------------------------------------------------------------------------
# Story Studio Bridge Utilities (manga_story.py integration)
# ---------------------------------------------------------------------------

POSITION_HINTS_MAP: dict[str, tuple[float, float, float, float]] = {
    # hint -> (x, y, tail_x, tail_y)
    "top-left": (0.28, 0.22, 0.28, 0.52),
    "top": (0.50, 0.20, 0.50, 0.48),
    "top-right": (0.72, 0.22, 0.72, 0.52),
    "center-left": (0.26, 0.50, 0.26, 0.78),
    "center": (0.50, 0.50, 0.50, 0.75),
    "center-right": (0.74, 0.50, 0.74, 0.78),
    "bottom-left": (0.28, 0.78, 0.28, 0.48),
    "bottom": (0.50, 0.80, 0.50, 0.52),
    "bottom-right": (0.72, 0.78, 0.72, 0.48),
}

BUBBLE_TYPE_MAP: dict[str, BubbleType] = {
    "speech": BubbleType.REGULAR,
    "regular": BubbleType.REGULAR,
    "thought": BubbleType.THOUGHT,
    "shout": BubbleType.SHOUT,
    "action": BubbleType.SHOUT,
    "whisper": BubbleType.WHISPER,
    "caption": BubbleType.CAPTION,
    "narration": BubbleType.CAPTION,
    "sfx": BubbleType.SFX,
    "inverted": BubbleType.INVERTED,
}


def convert_story_dialogue_to_speech_bubble(
    dialogue: Any,
    override_font_size: int | None = None,
) -> SpeechBubble:
    """Convert DialogueLine from manga_story.py or dict into SpeechBubble."""
    if hasattr(dialogue, "model_dump"):
        data = dialogue.model_dump()
    elif isinstance(dialogue, dict):
        data = dialogue
    else:
        data = getattr(dialogue, "__dict__", {})

    raw_type = str(data.get("bubble_type", "regular")).lower()
    bubble_type = BUBBLE_TYPE_MAP.get(raw_type, BubbleType.REGULAR)

    pos_hint = str(data.get("position_hint", "top-left")).lower().strip()
    x, y, tx, ty = POSITION_HINTS_MAP.get(pos_hint, (0.5, 0.3, 0.5, 0.6))

    text = sanitize_manga_text(str(data.get("text", "")).strip())

    return SpeechBubble(
        text=text,
        bubble_type=bubble_type,
        x=x,
        y=y,
        tail_x=tx,
        tail_y=ty,
        font_size=override_font_size,
    )


def convert_story_sfx_to_speech_bubble(
    sfx: Any,
    override_rotation: float = -12.0,
) -> SpeechBubble:
    """Convert PanelSFX from manga_story.py or dict into SpeechBubble."""
    if hasattr(sfx, "model_dump"):
        data = sfx.model_dump()
    elif isinstance(sfx, dict):
        data = sfx
    else:
        data = getattr(sfx, "__dict__", {})

    text = str(data.get("text", "BÙM!")).strip()
    return SpeechBubble(
        text=text,
        bubble_type=BubbleType.SFX,
        x=0.5,
        y=0.35,
        font_size=46,
        rotation=override_rotation,
        text_color="#FF3333",
        stroke_color="#000000",
        stroke_width=6,
    )


def convert_panel_plan_to_panel_config(
    panel_plan: Any,
    image_path: str | None = None,
    image_data: str | None = None,
    filter_type: PanelFilter = PanelFilter.NONE,
) -> PanelConfig:
    """Convert PanelPlan from manga_story.py into PanelConfig."""
    if hasattr(panel_plan, "model_dump"):
        data = panel_plan.model_dump()
    elif isinstance(panel_plan, dict):
        data = panel_plan
    else:
        data = getattr(panel_plan, "__dict__", {})

    bubbles: list[SpeechBubble] = []

    # Map dialogue lines using Smart Bubble Layout (RTL flow, Anti-Collision, Face Avoidance)
    dlgs = data.get("dialogues", [])
    if dlgs:
        try:
            try:
                from app.smart_bubble_layout import layout_panel_dialogues
            except ImportError:
                from smart_bubble_layout import layout_panel_dialogues
            smart_layouts = layout_panel_dialogues(dlgs)
            for item in smart_layouts:
                raw_type = str(item.get("bubble_type", "regular")).lower()
                btype = BUBBLE_TYPE_MAP.get(raw_type, BubbleType.REGULAR)
                bubbles.append(SpeechBubble(
                    text=sanitize_manga_text(item["text"]),
                    bubble_type=btype,
                    x=item["x"],
                    y=item["y"],
                    width=item.get("width"),
                    height=item.get("height"),
                    tail_x=item.get("tail_x"),
                    tail_y=item.get("tail_y"),
                ))
        except Exception:
            for dlg in dlgs:
                bubbles.append(convert_story_dialogue_to_speech_bubble(dlg))

    # Map SFX
    for sfx_item in data.get("sfx", []):
        bubbles.append(convert_story_sfx_to_speech_bubble(sfx_item))

    return PanelConfig(
        id=str(data.get("panel_number", "")),
        prompt=data.get("diffusion_prompt_en", ""),
        description=data.get("visual_description", ""),
        image_path=image_path,
        image_data=image_data,
        filter=filter_type,
        bubbles=bubbles,
    )


def convert_chapter_to_page_configs(
    chapter_plan: Any,
    layout_type: PanelLayoutType = PanelLayoutType.YONKOMA,
    panels_per_page: int = 4,
    page_width: int = 1200,
    page_height: int = 1800,
    reading_direction: str = "rtl",
) -> list[PageConfig]:
    """Convert an entire ChapterPlan into a sequence of PageConfigs."""
    if hasattr(chapter_plan, "model_dump"):
        data = chapter_plan.model_dump()
    elif isinstance(chapter_plan, dict):
        data = chapter_plan
    else:
        data = getattr(chapter_plan, "__dict__", {})

    # Gather all panel plans across scenes
    all_panels: list[Any] = []
    scenes = data.get("scenes", [])
    if scenes:
        for sc in scenes:
            all_panels.extend(sc.get("panels", []))
    elif "panels" in data:
        all_panels.extend(data["panels"])

    pages: list[PageConfig] = []
    panel_configs = [convert_panel_plan_to_panel_config(p) for p in all_panels]

    # Chunk panels per page
    step = max(1, panels_per_page)
    for p_idx, i in enumerate(range(0, len(panel_configs), step), start=1):
        chunk = panel_configs[i : i + step]
        pages.append(
            PageConfig(
                page_number=p_idx,
                width=page_width,
                height=page_height,
                layout_type=layout_type,
                reading_direction=reading_direction,
                panels=chunk,
            )
        )

    return pages
