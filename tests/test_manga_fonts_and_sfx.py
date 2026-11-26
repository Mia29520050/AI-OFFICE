# -*- coding: utf-8 -*-
"""
Tests for Manga Typography & Standardized SFX Dictionary
========================================================
Validates Vietnamese Manga / Comic font loading, Vietnamese diacritic rendering,
and conversion of crude English onomatopoeia to authentic Manga SFX.
"""

import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from app.manga_fonts import (
    get_manga_font,
    get_dialogue_font,
    get_shout_font,
    get_sfx_font,
    get_narrative_font,
    FONTS_DIR
)
from app.manga_sfx_dictionary import (
    MANGA_SFX_REGISTRY,
    sanitize_manga_sfx,
    get_sfx_display_text
)


class TestMangaFonts:

    def test_fonts_directory_and_files_exist(self):
        assert FONTS_DIR.exists()
        expected_files = [
            "PatrickHand-Regular.ttf",
            "Bangers-Regular.ttf",
            "ComicNeue-Bold.ttf",
            "ComicNeue-Regular.ttf"
        ]
        for f in expected_files:
            target = FONTS_DIR / f
            assert target.exists(), f"Missing required manga font: {f}"
            assert target.stat().st_size > 10000, f"Font file {f} is suspiciously small"

    def test_font_loading_all_roles(self):
        roles = ["dialogue", "shout", "sfx", "narrative", "comic_bold", "whisper"]
        for role in roles:
            font = get_manga_font(role, size=24)
            assert font is not None

    def test_vietnamese_diacritics_rendering(self):
        sample_text = "Huyết Cơ Carmilla: KENG! Hãy cảm nhận nhát chém ma mị của Hắc Kỵ Sĩ!"
        font = get_dialogue_font(size=24)

        img = Image.new("RGB", (600, 100), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((10, 10), sample_text, font=font)

        # Ensure text has non-zero width and height
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        assert width > 200
        assert height > 15


class TestMangaSFXDictionary:

    def test_sanitize_crude_english_clannng(self):
        # User explicitly requested eliminating "CLANNNG!" in favor of authentic SFX
        sfx_data = sanitize_manga_sfx("CLANNNG!")
        assert sfx_data["vi"] in ["KENG!", "KEEENG!"]
        assert "キィン" in sfx_data["kanji"]

        sfx_data2 = sanitize_manga_sfx("clang")
        assert sfx_data2["vi"] in ["KENG!", "KEEENG!"]

    def test_sanitize_crude_english_boom_and_slash(self):
        boom_data = sanitize_manga_sfx("BOOM!")
        assert "ẦM" in boom_data["vi"] or "ÙM" in boom_data["vi"]

        slash_data = sanitize_manga_sfx("SLASH")
        assert "XOẸT" in slash_data["vi"] or "PHẬP" in slash_data["vi"]

    def test_display_text_formatting(self):
        text_with_kanji = get_sfx_display_text("keng", style="vi_with_kanji")
        assert "KENG!" in text_with_kanji
        assert "キィン" in text_with_kanji

        text_vi_only = get_sfx_display_text("keng", style="vi_only")
        assert text_vi_only == "KENG!"

    def test_registry_color_and_aura_integrity(self):
        for key, item in MANGA_SFX_REGISTRY.items():
            assert "vi" in item
            assert "kanji" in item
            assert "stroke_color" in item
            assert "fill_color" in item
            assert "shadow_color" in item
            assert len(item["fill_color"]) == 3
            assert len(item["stroke_color"]) == 3
