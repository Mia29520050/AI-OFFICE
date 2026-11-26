# -*- coding: utf-8 -*-
"""
tests/test_manga_aesthetic_upgrade.py
=====================================
Automated Verification Suite for Manga Studio Aesthetic Upgrades:
  1. Typography Reform: Specialized Vietnamese Manga Fonts (no Segoe UI / Arial).
  2. SFX Realism: Eradication of 'CLANNNG!', enforcement of authentic Vietnamese/Japanese SFX.
  3. De-AI Organic Art: High-frequency texture entropy, Laplacian grain variance, G-pen sharpness.
  4. End-to-End Visual Audit: Composite aesthetic scoring and artifact integrity.
"""

import os
from pathlib import Path
import pytest
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from scripts.verify_manga_aesthetic_upgrade import (
    audit_manga_typography,
    audit_sfx_realism,
    compute_de_ai_metrics,
    apply_organic_screentone_grain,
    generate_side_by_side_comparison,
    run_aesthetic_verification_audit,
    REJECTED_RAW_ENGLISH_SFX,
    AUTHENTIC_VIETNAMESE_MANGA_SFX,
    FONTS_DIR,
    OUTPUT_IMAGE,
    OUTPUT_REPORT,
)
from app.manga_fonts import (
    get_manga_font,
    get_dialogue_font,
    get_shout_font,
    get_sfx_font,
    get_narrative_font,
    FONT_FILES,
)
from app.manga_sfx_dictionary import (
    sanitize_manga_sfx,
    get_sfx_display_text,
    MANGA_SFX_REGISTRY,
)


class TestTypographyReform:

    def test_specialized_manga_fonts_exist(self):
        assert FONTS_DIR.exists(), f"Fonts directory must exist at {FONTS_DIR}"
        expected_fonts = [
            "PatrickHand-Regular.ttf",
            "Bangers-Regular.ttf",
            "ComicNeue-Bold.ttf",
            "ComicNeue-Regular.ttf",
        ]
        for font_file in expected_fonts:
            p = FONTS_DIR / font_file
            assert p.exists(), f"Missing font file: {font_file}"
            assert p.stat().st_size > 5000, f"Font file {font_file} appears corrupted or empty"

    def test_font_loader_returns_manga_fonts(self):
        f_dialogue = get_dialogue_font(24)
        f_shout = get_shout_font(28)
        f_sfx = get_sfx_font(36)
        f_narrative = get_narrative_font(22)

        assert f_dialogue is not None
        assert f_shout is not None
        assert f_sfx is not None
        assert f_narrative is not None

    def test_vietnamese_diacritics_rendering(self):
        test_text = "Huyết Cơ Carmilla: 'Quỳ xuống trước mặt ta, lũ giáo sĩ ngu xuẩn!'"
        font = get_dialogue_font(24)

        canvas = Image.new("RGB", (800, 100), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 10), test_text, font=font, fill=(0, 0, 0))

        arr = np.array(canvas)
        non_white_count = np.sum(arr < 240)
        assert non_white_count > 500, "Vietnamese text rendering produced empty canvas or failed glyphs"

    def test_typography_audit_passes_100(self):
        res = audit_manga_typography()
        assert res.score == 100.0
        assert res.vietnamese_diacritic_valid is True
        assert res.is_lifeless_system_font is False


class TestSFXRealism:

    def test_crude_english_sfx_rejected(self):
        for raw in ["CLANNNG!", "CLANG!", "BAMMM!", "KEEE-ENG!", "CRUNCHHH!"]:
            assert raw in REJECTED_RAW_ENGLISH_SFX or "CLAN" in raw

            # Verify audit marks them as rejected
            res = audit_sfx_realism(raw)
            assert res.is_rejected_raw_english is True
            assert res.score == 0.0

    def test_authentic_vietnamese_sfx_accepted(self):
        for sfx in ["CHOẢNG!", "KENG!", "XOẸT!", "PHẬP!", "BENG!"]:
            assert sfx in AUTHENTIC_VIETNAMESE_MANGA_SFX

            res = audit_sfx_realism(sfx)
            assert res.is_authentic_manga_sfx is True
            assert res.is_rejected_raw_english is False
            assert res.score == 100.0

    def test_sanitize_manga_sfx_auto_maps_crude_words(self):
        # "CLANNNG!" should map to sharp blade clash ("keng" or "choang")
        mapped_data = sanitize_manga_sfx("CLANNNG!")
        assert mapped_data["vi"] in ["KENG!", "CHOẢNG!"]
        assert "kanji" in mapped_data
        assert "stroke_color" in mapped_data
        assert "fill_color" in mapped_data


class TestDeAITextureMetrics:

    def test_smooth_plastic_ai_detected(self):
        # Create perfectly flat/smooth image (simulating plastic AI skin)
        flat_img = Image.new("RGB", (300, 300), (220, 200, 190))
        metrics = compute_de_ai_metrics(flat_img)

        # Flat surface has Laplacian variance near 0.0
        assert metrics.laplacian_variance < 45.0
        assert metrics.is_plastic_ai_surface is True

    def test_organic_paper_grain_and_screentone_detected(self):
        base_img = Image.new("RGB", (300, 300), (180, 160, 150))
        # Apply organic screentone grain filter
        grained = apply_organic_screentone_grain(base_img, grain_intensity=0.08)
        metrics = compute_de_ai_metrics(grained)

        # Grain produces healthy high-frequency Laplacian variance >= 70.0
        assert metrics.laplacian_variance >= 70.0
        assert metrics.is_plastic_ai_surface is False
        assert metrics.score >= 80.0


class TestEndToEndVisualVerification:

    def test_full_aesthetic_audit_execution(self, tmp_path):
        out_img = tmp_path / "test_comparison.png"
        out_path = generate_side_by_side_comparison(out_img)
        assert out_path.exists()
        assert out_path.stat().st_size > 100000

        report = run_aesthetic_verification_audit()
        assert report.total_aesthetic_score >= 85.0
        assert "ĐẠT CHUẨN XUẤT SẮC" in report.verdict

        # Verify artifacts exist
        assert OUTPUT_IMAGE.exists()
        assert OUTPUT_REPORT.exists()
