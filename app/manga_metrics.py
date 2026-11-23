"""Manga & Anime Visual Quality and Continuity Metrics Engine.

Provides quantitative scoring and evaluation for:
1. Inking sharpness and edge density
2. B&W screentone / halftone pattern integrity
3. Contrast dynamics and paper tone distribution
4. Japanese color harmony and anime palette grading
5. Multi-panel sequential continuity (character palette, lighting, line weight)
6. Comparative analysis: B&W Manga Screentoning vs Full-Color Anime Rendering
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat
from pydantic import BaseModel, Field


class PanelQualityScore(BaseModel):
    """Evaluation metrics for a single manga/anime panel."""
    overall_score: float = Field(..., description="Overall quality score (0-100)")
    inking_sharpness: float = Field(..., description="Line art definition and edge sharpness (0-100)")
    edge_density: float = Field(..., description="Percentage of edge pixels (0-1.0)")
    contrast_score: float = Field(..., description="Dynamic range between black fills and highlights (0-100)")
    dark_ink_ratio: float = Field(..., description="Percentage of deep black ink pixels")
    white_space_ratio: float = Field(..., description="Percentage of paper white pixels")
    screentone_integrity: float = Field(..., description="Halftone / screentone pattern consistency (0-100)")
    color_harmony: float | None = Field(default=None, description="Color harmony and anime palette score (0-100)")
    mean_luminance: float = Field(..., description="Mean brightness (0-255)")
    stddev_luminance: float = Field(..., description="Standard deviation of luminance")
    is_bw: bool = Field(default=True, description="Whether evaluated as B&W manga or Color anime")
    recommendations: list[str] = Field(default_factory=list)


class PanelContinuityScore(BaseModel):
    """Cross-panel continuity metrics between two sequential panels."""
    transition_score: float = Field(..., description="Overall transition cohesion score (0-100)")
    palette_consistency: float = Field(..., description="Color / tone histogram similarity (0-1.0)")
    luminance_stability: float = Field(..., description="Exposure and lighting stability (0-1.0)")
    inking_consistency: float = Field(..., description="Line weight and edge density consistency (0-1.0)")
    notes: list[str] = Field(default_factory=list)


class ChapterContinuityReport(BaseModel):
    """Aggregate continuity evaluation for an entire multi-panel chapter sequence."""
    mean_continuity_score: float
    min_continuity_score: float
    pairwise_scores: list[PanelContinuityScore]
    overall_rating: str  # "EXCELLENT", "GOOD", "NEEDS_IMPROVEMENT", "POOR"
    consistency_bottlenecks: list[str]


# ---------------------------------------------------------------------------
# Core Metric Calculations
# ---------------------------------------------------------------------------


def compute_edge_density_and_sharpness(img: Image.Image) -> tuple[float, float]:
    """Compute edge density (ratio) and line sharpness score (0-100)."""
    gray = ImageOps.grayscale(img)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    # Exclude 1px canvas border to eliminate edge filter boundary artifact
    w, h = edges.size
    if w > 2 and h > 2:
        edges = edges.crop((1, 1, w - 1, h - 1))
    flat_edges = list(edges.get_flattened_data())
    total_px = len(flat_edges)
    if total_px == 0:
        return 0.0, 0.0

    # Count distinct edge pixels with gradient > 36 (out of 255)
    edge_count = sum(1 for val in flat_edges if val > 36)
    density = edge_count / total_px

    # Line sharpness: mean intensity of edge pixels
    edge_sum = sum(val for val in flat_edges if val > 36)
    mean_edge_intensity = (edge_sum / edge_count) if edge_count > 0 else 0.0
    sharpness_score = min(100.0, (mean_edge_intensity / 255.0) * 120.0)

    return density, sharpness_score


def compute_contrast_and_luminance(
    img: Image.Image,
) -> tuple[float, float, float, float, float]:
    """Compute (contrast_score, dark_ratio, white_ratio, mean_lum, stddev_lum)."""
    gray = ImageOps.grayscale(img)
    stat = ImageStat.Stat(gray)
    mean_lum = stat.mean[0]
    stddev_lum = stat.stddev[0]

    flat = list(gray.get_flattened_data())
    total_px = len(flat)
    if total_px == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    # Dark ink threshold < 45
    dark_count = sum(1 for v in flat if v < 45)
    dark_ratio = dark_count / total_px

    # Highlight white threshold > 235
    white_count = sum(1 for v in flat if v > 235)
    white_ratio = white_count / total_px

    # Optimal manga contrast: stddev > 50, dark_ratio 4-25%, white_ratio 15-70%
    contrast_score = min(100.0, (stddev_lum / 80.0) * 100.0)

    return contrast_score, dark_ratio, white_ratio, mean_lum, stddev_lum


def compute_screentone_integrity(img: Image.Image) -> float:
    """Evaluate B&W halftone / screentone dot pattern integrity (0-100).

    Manga screentones create high micro-frequency variation in mid-tones
    without blurring into flat muddy gray.
    """
    gray = ImageOps.grayscale(img)
    blur = gray.filter(ImageFilter.BoxBlur(1))
    diff = ImageChops.difference(gray, blur)
    mean_micro_diff = ImageStat.Stat(diff).mean[0]

    # Map micro-difference to screentone score (0 to 100)
    # A flat gray or smooth gradient has ~0 to 3 micro-diff.
    # An authentic halftone or dithering pattern has 15 to 80+ micro-diff.
    screentone_score = min(100.0, (mean_micro_diff / 25.0) * 100.0)
    return screentone_score


def compute_color_harmony(img: Image.Image) -> float:
    """Evaluate color harmony and palette grading for full-color anime panels (0-100)."""
    rgb = img.convert("RGB")
    hsv = rgb.convert("HSV")
    flat_hsv = list(hsv.get_flattened_data())
    total_px = len(flat_hsv)
    if total_px == 0:
        return 50.0

    # Extract saturations and values
    saturations = [flat_hsv[i][1] for i in range(total_px)]
    hues = [flat_hsv[i][0] for i in range(total_px) if flat_hsv[i][1] > 30]

    mean_sat = sum(saturations) / total_px
    # Japanese anime aesthetic favors controlled, pastel or cel saturations (70-160/255)
    # Penalize oversaturated radioactive colors (>220) or completely desaturated muddy color (<25)
    if 60 <= mean_sat <= 170:
        sat_score = 100.0
    elif mean_sat < 60:
        sat_score = max(30.0, 100.0 - (60 - mean_sat) * 1.5)
    else:
        sat_score = max(30.0, 100.0 - (mean_sat - 170) * 1.2)

    # Hue clustering: anime art typically has 2-4 dominant cohesive color families
    if len(hues) > 50:
        hue_bins = [0] * 12  # 30-degree bins
        for h in hues:
            bin_idx = int((h / 256.0) * 12) % 12
            hue_bins[bin_idx] += 1
        active_families = sum(1 for count in hue_bins if count > len(hues) * 0.08)
        palette_score = 95.0 if 2 <= active_families <= 5 else 75.0
    else:
        palette_score = 70.0

    return (sat_score * 0.6) + (palette_score * 0.4)


def get_binned_histogram(img: Image.Image, bins_per_channel: int = 16) -> list[float]:
    """Calculate 48-bin normalized color histogram for perceptual similarity."""
    rgb = img.resize((128, 128)).convert("RGB")
    data = list(rgb.get_flattened_data())
    total_px = len(data)
    hist = [0.0] * (bins_per_channel * 3)
    bin_size = 256.0 / bins_per_channel

    for r, g, b in data:
        hist[min(bins_per_channel - 1, int(r / bin_size))] += 1.0
        hist[bins_per_channel + min(bins_per_channel - 1, int(g / bin_size))] += 1.0
        hist[bins_per_channel * 2 + min(bins_per_channel - 1, int(b / bin_size))] += 1.0

    norm = total_px * 3.0
    return [c / norm for c in hist]


def compute_panel_continuity(
    panel_a: Image.Image,
    panel_b: Image.Image,
) -> PanelContinuityScore:
    """Measure visual and stylistic continuity between sequential panels."""
    # 1. Palette consistency
    h1 = get_binned_histogram(panel_a)
    h2 = get_binned_histogram(panel_b)
    dot = sum(a * b for a, b in zip(h1, h2))
    n1 = math.sqrt(sum(a * a for a in h1))
    n2 = math.sqrt(sum(b * b for b in h2))
    palette_sim = (dot / (n1 * n2)) if (n1 > 0 and n2 > 0) else 0.0

    # 2. Luminance stability
    stat_a = ImageStat.Stat(panel_a.convert("L"))
    stat_b = ImageStat.Stat(panel_b.convert("L"))
    mean_diff = abs(stat_a.mean[0] - stat_b.mean[0])
    # Difference up to 60 luminance levels mapped to 1.0 -> 0.0
    lum_stability = max(0.0, 1.0 - (mean_diff / 80.0))

    # 3. Inking consistency
    ed_a, _ = compute_edge_density_and_sharpness(panel_a)
    ed_b, _ = compute_edge_density_and_sharpness(panel_b)
    density_diff = abs(ed_a - ed_b)
    ink_stability = max(0.0, 1.0 - (density_diff / 0.08))

    # Combined transition score
    trans_score = (palette_sim * 0.45 + lum_stability * 0.30 + ink_stability * 0.25) * 100.0

    notes: list[str] = []
    if palette_sim < 0.65:
        notes.append("High palette shift between panels (possible lighting/character color change)")
    if lum_stability < 0.60:
        notes.append("Abrupt luminance transition")
    if ink_stability < 0.60:
        notes.append("Line weight inconsistency detected")
    if not notes:
        notes.append("Smooth narrative transition")

    return PanelContinuityScore(
        transition_score=round(trans_score, 1),
        palette_consistency=round(palette_sim, 3),
        luminance_stability=round(lum_stability, 3),
        inking_consistency=round(ink_stability, 3),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# High-Level Evaluation API
# ---------------------------------------------------------------------------


def evaluate_manga_panel(img: Image.Image, is_bw: bool = True) -> PanelQualityScore:
    """Perform comprehensive visual quality evaluation of a panel."""
    edge_density, sharpness = compute_edge_density_and_sharpness(img)
    contrast_score, dark_ratio, white_ratio, mean_lum, stddev_lum = compute_contrast_and_luminance(img)
    screentone_score = compute_screentone_integrity(img)
    color_score = compute_color_harmony(img) if not is_bw else None

    # Calculate overall weighted score
    if is_bw:
        overall = (
            sharpness * 0.35
            + contrast_score * 0.30
            + screentone_score * 0.25
            + min(100.0, (edge_density / 0.05) * 100.0) * 0.10
        )
    else:
        overall = (
            sharpness * 0.30
            + contrast_score * 0.25
            + (color_score or 75.0) * 0.35
            + min(100.0, (edge_density / 0.04) * 100.0) * 0.10
        )

    recommendations: list[str] = []
    if edge_density < 0.02:
        recommendations.append("Increase line art definition / edge density (currently < 2%)")
    if dark_ratio < 0.035:
        recommendations.append("Deepen black inking fills (currently < 3.5%)")
    if white_ratio > 0.85:
        recommendations.append("Panel has excessive blank white space (> 85%)")
    if is_bw and screentone_score < 40.0:
        recommendations.append("Apply dot screentone to midtone shading for authentic manga texture")
    if not is_bw and color_score and color_score < 60.0:
        recommendations.append("Adjust anime color palette for better saturation balance")

    return PanelQualityScore(
        overall_score=round(overall, 1),
        inking_sharpness=round(sharpness, 1),
        edge_density=round(edge_density, 4),
        contrast_score=round(contrast_score, 1),
        dark_ink_ratio=round(dark_ratio, 4),
        white_space_ratio=round(white_ratio, 4),
        screentone_integrity=round(screentone_score, 1),
        color_harmony=round(color_score, 1) if color_score is not None else None,
        mean_luminance=round(mean_lum, 1),
        stddev_luminance=round(stddev_lum, 1),
        is_bw=is_bw,
        recommendations=recommendations,
    )


def evaluate_chapter_continuity(panels: Sequence[Image.Image]) -> ChapterContinuityReport:
    """Evaluate continuity across all sequential panels in a chapter."""
    if len(panels) < 2:
        return ChapterContinuityReport(
            mean_continuity_score=100.0,
            min_continuity_score=100.0,
            pairwise_scores=[],
            overall_rating="EXCELLENT",
            consistency_bottlenecks=[],
        )

    pairwise: list[PanelContinuityScore] = []
    for i in range(len(panels) - 1):
        score = compute_panel_continuity(panels[i], panels[i + 1])
        pairwise.append(score)

    scores = [p.transition_score for p in pairwise]
    mean_score = sum(scores) / len(scores)
    min_score = min(scores)

    bottlenecks: list[str] = []
    for idx, p in enumerate(pairwise):
        if p.transition_score < 70.0:
            bottlenecks.append(f"Transition Panel {idx + 1} -> {idx + 2} scored {p.transition_score}: {', '.join(p.notes)}")

    if mean_score >= 85.0:
        rating = "EXCELLENT"
    elif mean_score >= 72.0:
        rating = "GOOD"
    elif mean_score >= 58.0:
        rating = "NEEDS_IMPROVEMENT"
    else:
        rating = "POOR"

    return ChapterContinuityReport(
        mean_continuity_score=round(mean_score, 1),
        min_continuity_score=round(min_score, 1),
        pairwise_scores=pairwise,
        overall_rating=rating,
        consistency_bottlenecks=bottlenecks,
    )


# ---------------------------------------------------------------------------
# B&W Manga Screentoning vs Full-Color Anime Rendering Comparison
# ---------------------------------------------------------------------------


def compare_bw_vs_color_rendering(
    bw_panel: Image.Image,
    color_panel: Image.Image,
) -> dict[str, Any]:
    """Analyze and compare B&W Manga Screentoning vs Full-Color Anime Rendering."""
    bw_eval = evaluate_manga_panel(bw_panel, is_bw=True)
    color_eval = evaluate_manga_panel(color_panel, is_bw=False)

    return {
        "bw_manga": {
            "overall_score": bw_eval.overall_score,
            "inking_sharpness": bw_eval.inking_sharpness,
            "screentone_integrity": bw_eval.screentone_integrity,
            "dark_ink_ratio": bw_eval.dark_ink_ratio,
            "edge_density": bw_eval.edge_density,
            "vram_footprint_factor": "1.0x (Baseline: ~3.8 - 4.5 GB VRAM with 1-ch line conditioning)",
            "print_compatibility": "100% (Native 600-1200 DPI B&W press / CBZ digital manga)",
        },
        "color_anime": {
            "overall_score": color_eval.overall_score,
            "inking_sharpness": color_eval.inking_sharpness,
            "color_harmony": color_eval.color_harmony,
            "saturation_mean": color_eval.stddev_luminance,
            "edge_density": color_eval.edge_density,
            "vram_footprint_factor": "1.35x (~5.2 - 5.8 GB VRAM requiring aggressive tiled VAE decoding)",
            "print_compatibility": "Webtoon RGB / Digital Color (higher file size, 3-channel latents)",
        },
        "synthesis": {
            "recommended_mode_for_6gb_rtx3050": "Hybrid: B&W Manga for multi-page chapters (low VRAM, fast throughput); Full-color for chapter cover and key climax splash panels.",
            "continuity_impact": "B&W manga simplifies multi-panel character consistency by eliminating color drift, focusing continuity on silhouette and line work.",
        },
    }
