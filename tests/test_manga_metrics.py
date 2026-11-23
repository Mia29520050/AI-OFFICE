"""Unit tests for Manga & Anime Visual Quality and Continuity Metrics Engine."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
import pytest

from app.manga_metrics import (
    compute_edge_density_and_sharpness,
    compute_contrast_and_luminance,
    compute_screentone_integrity,
    compute_color_harmony,
    compute_panel_continuity,
    evaluate_manga_panel,
    evaluate_chapter_continuity,
    compare_bw_vs_color_rendering,
    PanelQualityScore,
    PanelContinuityScore,
    ChapterContinuityReport,
)


def test_edge_density_and_sharpness():
    blank = Image.new("RGB", (200, 200), "white")
    d_blank, s_blank = compute_edge_density_and_sharpness(blank)
    assert d_blank == 0.0
    assert s_blank == 0.0

    # Striped high-contrast image
    striped = Image.new("RGB", (200, 200), "white")
    for y in range(0, 200, 4):
        for x in range(200):
            striped.putpixel((x, y), (0, 0, 0))
    d_str, s_str = compute_edge_density_and_sharpness(striped)
    assert d_str > 0.05
    assert s_str > 20.0


def test_contrast_and_luminance():
    img = Image.new("RGB", (100, 100), "black")
    for x in range(50):
        for y in range(100):
            img.putpixel((x, y), (255, 255, 255))
    contrast, dark_r, white_r, mean_l, stddev_l = compute_contrast_and_luminance(img)
    assert dark_r >= 0.45
    assert white_r >= 0.45
    assert contrast > 50.0


def test_screentone_integrity():
    flat_gray = Image.new("RGB", (100, 100), (128, 128, 128))
    score_flat = compute_screentone_integrity(flat_gray)
    assert score_flat < 10.0

    # Checkerboard halftone simulation
    halftone = Image.new("RGB", (100, 100), "white")
    for y in range(100):
        for x in range(100):
            if (x + y) % 2 == 0:
                halftone.putpixel((x, y), (0, 0, 0))
    score_ht = compute_screentone_integrity(halftone)
    assert score_ht > 50.0


def test_color_harmony():
    pastel = Image.new("RGB", (100, 100), (160, 180, 220))
    score_pastel = compute_color_harmony(pastel)
    assert score_pastel >= 70.0


def test_panel_continuity():
    p1 = Image.new("RGB", (100, 100), (150, 160, 170))
    p2 = Image.new("RGB", (100, 100), (152, 162, 172))
    p_diff = Image.new("RGB", (100, 100), (10, 10, 10))

    score_similar = compute_panel_continuity(p1, p2)
    assert score_similar.palette_consistency > 0.90
    assert score_similar.transition_score > 80.0

    score_diff = compute_panel_continuity(p1, p_diff)
    assert score_diff.transition_score < score_similar.transition_score


def test_evaluate_manga_panel_and_chapter():
    p1 = Image.new("RGB", (200, 300), (240, 240, 240))
    p2 = Image.new("RGB", (200, 300), (20, 20, 20))

    res_bw = evaluate_manga_panel(p1, is_bw=True)
    assert isinstance(res_bw, PanelQualityScore)
    assert res_bw.overall_score >= 0.0

    res_color = evaluate_manga_panel(p1, is_bw=False)
    assert isinstance(res_color, PanelQualityScore)
    assert res_color.color_harmony is not None

    chap_report = evaluate_chapter_continuity([p1, p1, p2])
    assert isinstance(chap_report, ChapterContinuityReport)
    assert len(chap_report.pairwise_scores) == 2


def test_compare_bw_vs_color_rendering():
    p_bw = Image.new("RGB", (200, 300), "white")
    p_col = Image.new("RGB", (200, 300), (100, 150, 200))
    cmp = compare_bw_vs_color_rendering(p_bw, p_col)
    assert "bw_manga" in cmp
    assert "color_anime" in cmp
    assert "synthesis" in cmp
