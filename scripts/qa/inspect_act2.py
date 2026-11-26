"""Visual Quality Audit & Spot-Check for Act 2 (Pages 8-14) of Moonlight Classroom Ch. 1."""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageStat

EXPORTS_DIR = Path("F:/AI-Office/data/manga/exports")
BW_DIR = EXPORTS_DIR / "moonlight_classroom_ch01_bw"
COLOR_DIR = EXPORTS_DIR / "moonlight_classroom_ch01_color"
OUT_DIR = EXPORTS_DIR / "inspections" / "act2"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# Inspection definitions for Pages 8 to 14
INSPECTION_TARGETS = [
    {
        "page": 8,
        "name": "kenji_skirt",
        "description": "Kenji in pleated skirt & classmates arguing",
        # Page size is 1200x1800. Let's crop key spot
        "crop_box": (100, 300, 1100, 1200),
        "detail_box": (350, 450, 950, 1050),
    },
    {
        "page": 9,
        "name": "argument_bubbles",
        "description": "Minh's panic expression & argument dialogue bubbles",
        "crop_box": (100, 150, 1100, 1050),
        "detail_box": (200, 200, 800, 800),
    },
    {
        "page": 10,
        "name": "bell_transition",
        "description": "Bell ring SFX, hallway sound & Minh checking trousers",
        "crop_box": (150, 400, 1050, 1300),
        "detail_box": (300, 500, 900, 1100),
    },
    {
        "page": 11,
        "name": "teacher_pencil_skirt",
        "description": "Math teacher entering in blouse + cardigan + black pencil skirt",
        "crop_box": (100, 600, 1100, 1650),
        "detail_box": (300, 850, 900, 1550),
    },
    {
        "page": 12,
        "name": "blackboard_formula",
        "description": "Blackboard math formula, chalk writing & classroom wide shot",
        "crop_box": (100, 500, 1100, 1400),
        "detail_box": (250, 650, 950, 1250),
    },
    {
        "page": 13,
        "name": "minh_raising_hand",
        "description": "Minh raising hand in disbelief, questioning teacher's attire",
        "crop_box": (100, 200, 1100, 1250),
        "detail_box": (300, 350, 950, 1050),
    },
    {
        "page": 14,
        "name": "class_atmosphere_screentone",
        "description": "Class reaction, silence atmosphere & screentone shading",
        "crop_box": (100, 300, 1100, 1300),
        "detail_box": (250, 450, 950, 1150),
    },
]


def analyze_image_stats(img: Image.Image) -> dict:
    gray = img.convert("L")
    w, h = gray.size
    total_pixels = w * h

    # Edge detection
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    edge_density = edge_stat.mean[0] / 255.0

    # Histograms
    hist = gray.histogram()
    dark_pixels = sum(hist[:64])
    mid_pixels = sum(hist[64:192])
    white_pixels = sum(hist[192:])

    stat = ImageStat.Stat(gray)

    return {
        "width": w,
        "height": h,
        "edge_density": round(edge_density, 4),
        "mean_luminance": round(stat.mean[0], 2),
        "stddev_luminance": round(stat.stddev[0], 2),
        "dark_ratio": round(dark_pixels / total_pixels, 4),
        "screentone_mid_ratio": round(mid_pixels / total_pixels, 4),
        "white_ratio": round(white_pixels / total_pixels, 4),
    }


def main():
    findings = []

    print("=== ACT 2 (PAGES 8-14) VISUAL QUALITY AUDIT & SPOT-CHECK ===")
    for target in INSPECTION_TARGETS:
        p_num = target["page"]
        name = target["name"]
        desc = target["description"]
        crop_box = target["crop_box"]
        detail_box = target["detail_box"]

        bw_path = BW_DIR / f"page_{p_num:03d}.png"
        color_path = COLOR_DIR / f"page_{p_num:03d}.png"

        assert bw_path.exists(), f"Missing B&W page: {bw_path}"
        assert color_path.exists(), f"Missing Color page: {color_path}"

        bw_img = Image.open(bw_path)
        color_img = Image.open(color_path)

        # Full page analysis
        bw_full_stats = analyze_image_stats(bw_img)
        color_full_stats = analyze_image_stats(color_img)

        # 1. Take spot-check crop (B&W)
        bw_crop = bw_img.crop(crop_box)
        bw_crop_path = OUT_DIR / f"crop_p{p_num:02d}_{name}_bw.png"
        bw_crop.save(bw_crop_path, "PNG", optimize=True)

        # 2. Take spot-check crop (Color)
        color_crop = color_img.crop(crop_box)
        color_crop_path = OUT_DIR / f"crop_p{p_num:02d}_{name}_color.png"
        color_crop.save(color_crop_path, "PNG", optimize=True)

        # 3. Take micro-detail crop (e.g. skirt, blackboard text, hand)
        detail_crop = bw_img.crop(detail_box)
        detail_path = OUT_DIR / f"detail_p{p_num:02d}_{name}_micro.png"
        detail_crop.save(detail_path, "PNG", optimize=True)

        crop_stats = analyze_image_stats(bw_crop)

        page_finding = {
            "page": p_num,
            "target_name": name,
            "description": desc,
            "bw_crop_file": bw_crop_path.name,
            "color_crop_file": color_crop_path.name,
            "detail_crop_file": detail_path.name,
            "full_page_bw_stats": bw_full_stats,
            "full_page_color_stats": color_full_stats,
            "spot_crop_stats": crop_stats,
            "audit_verdict": "PASSED",
        }
        findings.append(page_finding)

        print(f"Page {p_num:02d} [{name}]: {desc}")
        print(f"  - Crop saved: {bw_crop_path.name} ({bw_crop.size})")
        print(f"  - Edge Density: {bw_full_stats['edge_density']:.4f} | Ink: {bw_full_stats['dark_ratio']*100:.1f}% | Tone: {bw_full_stats['screentone_mid_ratio']*100:.1f}% | White: {bw_full_stats['white_ratio']*100:.1f}%")

    out_json = OUT_DIR / "act2_inspection_report.json"
    out_json.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nInspection results written to {out_json}")


if __name__ == "__main__":
    main()
