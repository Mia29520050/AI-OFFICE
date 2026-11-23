"""Image Quality Validator & QA Gate for Manga Studio.

Enforces strict quality criteria to block release of:
- Blank white panels or placeholder text cards
- Abnormal solid black voids
- Unillustrated empty frames
- Corrupted, un-decodable, or sub-resolution image assets
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
from PIL import Image, ImageFilter, ImageStat


class QAValidationError(Exception):
    """Raised when an image asset or chapter fails quality validation gates."""
    pass


@dataclass
class PanelValidationResult:
    """Detailed visual metric report for a single manga panel or page."""
    is_valid: bool
    path: str | None = None
    panel_id: str | None = None
    resolution: tuple[int, int] = (0, 0)
    mean_brightness: float = 0.0
    stddev: float = 0.0
    white_ratio: float = 0.0      # pixels >= 245
    dark_ratio: float = 0.0       # pixels < 40
    mid_ratio: float = 0.0        # 40 <= pixels < 245
    edge_density: float = 0.0     # lineart edge pixel ratio (>35 in FIND_EDGES)
    failure_reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "path": self.path,
            "panel_id": self.panel_id,
            "resolution": list(self.resolution),
            "mean_brightness": round(self.mean_brightness, 2),
            "stddev": round(self.stddev, 2),
            "white_ratio": round(self.white_ratio, 4),
            "dark_ratio": round(self.dark_ratio, 4),
            "mid_ratio": round(self.mid_ratio, 4),
            "edge_density": round(self.edge_density, 4),
            "failure_reasons": self.failure_reasons,
            "metrics": self.metrics,
        }


def validate_panel_image(
    image_or_path: Image.Image | str | Path,
    panel_id: str | None = None,
    min_width: int = 400,
    min_height: int = 200,
    max_white_ratio: float = 0.82,
    max_dark_ratio: float = 0.85,
    min_dark_ratio: float = 0.045,
    min_art_coverage: float = 0.18,
    min_stddev: float = 25.0,
    min_edge_density: float = 0.020,
    max_mean_brightness: float = 236.0,
) -> PanelValidationResult:
    """Inspect and mathematically validate that a panel has genuine manga art content.

    Blocks:
    1. Blank / near-white panels (white_ratio > max_white_ratio, or mean > max_mean_brightness)
    2. Solid black voids (dark_ratio > max_dark_ratio, or mean < 15 with low stddev)
    3. Missing lineart / illustration content (edge_density < min_edge_density)
    4. Insufficient artwork coverage (mid_ratio + dark_ratio < min_art_coverage)
    5. Insufficient dark ink density (dark_ratio < min_dark_ratio)
    6. Undersized or corrupted images
    """
    path_str = str(image_or_path) if isinstance(image_or_path, (str, Path)) else None
    failure_reasons: list[str] = []

    # 1. Load image
    img: Image.Image
    if isinstance(image_or_path, Image.Image):
        img = image_or_path
    else:
        p = Path(image_or_path)
        if not p.exists():
            return PanelValidationResult(
                is_valid=False,
                path=path_str,
                panel_id=panel_id,
                failure_reasons=[f"File does not exist: {p}"]
            )
        try:
            img = Image.open(p)
            img.load()
        except Exception as e:
            return PanelValidationResult(
                is_valid=False,
                path=path_str,
                panel_id=panel_id,
                failure_reasons=[f"Failed to decode image file ({e})"]
            )

    w, h = img.size
    total_pixels = w * h

    # 2. Check resolution
    if w < min_width or h < min_height:
        failure_reasons.append(
            f"Image dimensions {w}x{h} are below minimum required {min_width}x{min_height}"
        )

    # 3. Luminance & Pixel Distributions
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    mean_val = stat.mean[0]
    stddev_val = stat.stddev[0]

    # Count pixels by luminance category
    raw_pixels = list(gray.get_flattened_data())
    white_count = 0
    dark_count = 0
    mid_count = 0

    for p in raw_pixels:
        if p >= 245:
            white_count += 1
        elif p < 40:
            dark_count += 1
        else:
            mid_count += 1

    white_ratio = white_count / max(1, total_pixels)
    dark_ratio = dark_count / max(1, total_pixels)
    mid_ratio = mid_count / max(1, total_pixels)
    art_coverage = dark_ratio + mid_ratio

    # 4. Edge density (measures detailed lineart, hair, contours, shading)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_pixels = sum(1 for ep in edges.get_flattened_data() if ep > 35)
    edge_density = edge_pixels / max(1, total_pixels)

    # 5. Rule-based Quality Checks
    # Check A: Blank White Panel
    if white_ratio > max_white_ratio:
        failure_reasons.append(
            f"BLANK WHITE PANEL: {white_ratio*100:.1f}% pure white space exceeds maximum allowed {max_white_ratio*100:.0f}%"
        )
    if mean_val > max_mean_brightness:
        failure_reasons.append(
            f"EXCESSIVE BRIGHTNESS: Mean luminance {mean_val:.1f}/255 exceeds maximum allowed {max_mean_brightness:.1f}"
        )

    # Check B: Solid Black Void
    if dark_ratio > max_dark_ratio:
        failure_reasons.append(
            f"BLACK VOID PANEL: {dark_ratio*100:.1f}% solid dark pixels exceeds maximum allowed {max_dark_ratio*100:.0f}%"
        )
    elif mean_val < 15.0 and stddev_val < 15.0:
        failure_reasons.append(
            f"BLACK VOID PANEL: Mean luminance {mean_val:.1f}/255 is near absolute black with negligible variance ({stddev_val:.1f})"
        )

    # Check C: Missing Art Coverage & Ink Lines
    if art_coverage < min_art_coverage:
        failure_reasons.append(
            f"MISSING ARTWORK: Non-white art coverage is {art_coverage*100:.1f}%, below mandatory threshold {min_art_coverage*100:.0f}%"
        )
    if dark_ratio < min_dark_ratio:
        failure_reasons.append(
            f"INSUFFICIENT INK: Dark ink ratio is {dark_ratio*100:.2f}%, below required minimum {min_dark_ratio*100:.1f}% (missing linework/figures)"
        )

    # Check D: Lineart / Edge Density
    if edge_density < min_edge_density:
        failure_reasons.append(
            f"INSUFFICIENT LINEART: Edge density {edge_density*100:.2f}% is below required {min_edge_density*100:.1f}%, panel lacks drawn character or background illustration"
        )

    # Check E: Texture variance
    if stddev_val < min_stddev:
        failure_reasons.append(
            f"LOW VISUAL COMPLEXITY: Standard deviation {stddev_val:.1f} is below minimum {min_stddev:.1f}"
        )

    is_valid = len(failure_reasons) == 0

    return PanelValidationResult(
        is_valid=is_valid,
        path=path_str,
        panel_id=panel_id,
        resolution=(w, h),
        mean_brightness=mean_val,
        stddev=stddev_val,
        white_ratio=white_ratio,
        dark_ratio=dark_ratio,
        mid_ratio=mid_ratio,
        edge_density=edge_density,
        failure_reasons=failure_reasons,
        metrics={
            "total_pixels": total_pixels,
            "art_coverage": art_coverage,
            "white_count": white_count,
            "dark_count": dark_count,
            "mid_count": mid_count,
            "edge_pixels": edge_pixels,
        }
    )


def validate_chapter_release(
    page_images_or_paths: Sequence[Image.Image | str | Path],
    panel_images_or_paths: Sequence[Image.Image | str | Path] | None = None,
    raise_on_failure: bool = True,
) -> dict[str, Any]:
    """Validate all panels and full pages of a chapter before allowing release export.

    If any panel or page fails, raises QAValidationError (if raise_on_failure=True).
    Returns complete QA audit report dictionary.
    """
    panel_results: list[PanelValidationResult] = []
    page_results: list[PanelValidationResult] = []

    # 1. Validate Panels
    if panel_images_or_paths:
        for idx, item in enumerate(panel_images_or_paths, start=1):
            res = validate_panel_image(item, panel_id=f"panel_{idx:02d}")
            panel_results.append(res)

    # 2. Validate Pages
    for idx, item in enumerate(page_images_or_paths, start=1):
        res = validate_panel_image(
            item,
            panel_id=f"page_{idx:02d}",
            min_width=600,
            min_height=800,
            max_white_ratio=0.88,
            min_art_coverage=0.12,
            min_dark_ratio=0.025,
            min_edge_density=0.015,
            max_mean_brightness=240.0,
        )
        page_results.append(res)

    total_checked = len(panel_results) + len(page_results)
    failed_panels = [r for r in panel_results if not r.is_valid]
    failed_pages = [r for r in page_results if not r.is_valid]
    passed_count = total_checked - len(failed_panels) - len(failed_pages)

    report = {
        "status": "PASS" if not failed_panels and not failed_pages else "FAIL",
        "total_items_checked": total_checked,
        "passed_items_count": passed_count,
        "failed_panels_count": len(failed_panels),
        "failed_pages_count": len(failed_pages),
        "panel_reports": [r.to_dict() for r in panel_results],
        "page_reports": [r.to_dict() for r in page_results],
    }

    if (failed_panels or failed_pages) and raise_on_failure:
        reasons: list[str] = []
        for fp in failed_panels:
            reasons.append(f"[{fp.panel_id or fp.path}]: {'; '.join(fp.failure_reasons)}")
        for fg in failed_pages:
            reasons.append(f"[{fg.panel_id or fg.path}]: {'; '.join(fg.failure_reasons)}")
        err_msg = (
            f"QA GATE BLOCKED RELEASE: {len(failed_panels)} panels and {len(failed_pages)} pages failed visual validation!\n"
            + "\n".join(reasons)
        )
        raise QAValidationError(err_msg)

    return report
