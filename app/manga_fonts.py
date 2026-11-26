# -*- coding: utf-8 -*-
"""
Manga Typography & Font Management Module
=========================================
Provides specialized Manga / Comic lettering fonts with full Vietnamese diacritics support.
Replaces generic/lifeless system UI fonts (Segoe UI / Inter) with expressive manga lettering:
  - Dialogue: Patrick Hand / Comic Neue Bold (hand-lettered manga feel)
  - Shouting / Climax: Bangers (bold comic impact)
  - SFX Onomatopoeia: Bangers / Comic Neue Bold with dual-stroke outline & block extrusion
  - Narrative / Whisper: Comic Neue Regular / Patrick Hand
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Literal
from PIL import ImageFont

ROOT_DIR = Path(__file__).resolve().parents[1]
FONTS_DIR = ROOT_DIR / "app" / "ui" / "assets" / "fonts"
LEGACY_FONT_PATH = ROOT_DIR / "app" / "ui" / "assets" / "Inter-Variable.ttf"

FONT_FILES = {
    "dialogue": FONTS_DIR / "PatrickHand-Regular.ttf",
    "shout": FONTS_DIR / "Bangers-Regular.ttf",
    "sfx": FONTS_DIR / "Bangers-Regular.ttf",
    "narrative": FONTS_DIR / "ComicNeue-Regular.ttf",
    "comic_bold": FONTS_DIR / "ComicNeue-Bold.ttf",
    "whisper": FONTS_DIR / "PatrickHand-Regular.ttf"
}


def get_manga_font(
    font_type: Literal["dialogue", "shout", "sfx", "narrative", "comic_bold", "whisper"] = "dialogue",
    size: int = 24
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Loads specialized Manga lettering font with seamless fallback chain."""
    primary_path = FONT_FILES.get(font_type, FONT_FILES["dialogue"])
    
    # Priority 1: Requested manga font
    if primary_path.exists():
        try:
            return ImageFont.truetype(str(primary_path), size)
        except Exception:
            pass

    # Priority 2: Alternative manga fonts in fonts dir
    alt_manga_fonts = [
        FONTS_DIR / "PatrickHand-Regular.ttf",
        FONTS_DIR / "ComicNeue-Bold.ttf",
        FONTS_DIR / "Bangers-Regular.ttf",
        FONTS_DIR / "ComicNeue-Regular.ttf"
    ]
    for alt_path in alt_manga_fonts:
        if alt_path.exists() and alt_path != primary_path:
            try:
                return ImageFont.truetype(str(alt_path), size)
            except Exception:
                continue

    # Priority 3: Windows system fonts with comic feel (Comic Sans MS)
    win_comic_fonts = [
        Path("C:/Windows/Fonts/comicbd.ttf"),
        Path("C:/Windows/Fonts/comic.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf")
    ]
    for win_font in win_comic_fonts:
        if win_font.exists():
            try:
                return ImageFont.truetype(str(win_font), size)
            except Exception:
                continue

    # Priority 4: Legacy Inter font
    if LEGACY_FONT_PATH.exists():
        try:
            return ImageFont.truetype(str(LEGACY_FONT_PATH), size)
        except Exception:
            pass

    return ImageFont.load_default()


def get_dialogue_font(size: int = 24) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return get_manga_font("dialogue", size)


def get_shout_font(size: int = 28) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return get_manga_font("shout", size)


def get_sfx_font(size: int = 36) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return get_manga_font("sfx", size)


def get_narrative_font(size: int = 22) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return get_manga_font("narrative", size)
