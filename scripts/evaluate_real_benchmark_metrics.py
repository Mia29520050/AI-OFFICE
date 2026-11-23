"""Evaluate visual quality and continuity metrics for the 8 real generated benchmark images."""

import json
from pathlib import Path
from PIL import Image

import sys
sys.path.insert(0, r"F:\AI-Office\app")
sys.path.insert(0, r"F:\AI-Office")

from manga_validator import validate_panel_image
from manga_metrics import evaluate_manga_panel, compute_panel_continuity, ChapterContinuityReport

TELEMETRY_JSON = Path(r"F:\AI-Office\data\manga\benchmarks\real_hardware_telemetry.json")

def process():
    with open(TELEMETRY_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data["test_cases"]
    loaded_images = []

    for tc in test_cases:
        img_path = Path(tc["output_image_path"])
        if not img_path.exists():
            print(f"File not found: {img_path}")
            continue

        # 1. QA Validation
        qa_res = validate_panel_image(img_path)
        tc["qa_validation"] = {
            "is_valid": qa_res.is_valid,
            "resolution": list(qa_res.resolution),
            "mean_brightness": round(qa_res.mean_brightness, 2),
            "stddev": round(qa_res.stddev, 2),
            "white_ratio": round(qa_res.white_ratio, 4),
            "dark_ratio": round(qa_res.dark_ratio, 4),
            "edge_density": round(qa_res.edge_density, 4),
            "failure_reasons": qa_res.failure_reasons
        }

        # 2. Quality Metrics
        with Image.open(img_path) as im:
            loaded_images.append((tc["id"], tc["slug"], im.copy(), tc["art_style"]))
            is_bw = (tc["art_style"] == "manga_bw")
            q_score = evaluate_manga_panel(im, is_bw=is_bw)
            tc["quality_metrics"] = {
                "overall_score": q_score.overall_score,
                "inking_sharpness": q_score.inking_sharpness,
                "edge_density": q_score.edge_density,
                "contrast_score": q_score.contrast_score,
                "screentone_integrity": q_score.screentone_integrity,
                "color_harmony": q_score.color_harmony,
                "mean_luminance": round(q_score.mean_luminance, 2),
                "stddev_luminance": round(q_score.stddev_luminance, 2),
                "recommendations": q_score.recommendations
            }

    # 3. Pairwise Continuity across panels
    continuity_pairs = []
    total_continuity = 0.0
    for i in range(len(loaded_images) - 1):
        id_a, slug_a, img_a, style_a = loaded_images[i]
        id_b, slug_b, img_b, style_b = loaded_images[i+1]
        c_score = compute_panel_continuity(img_a, img_b)
        pair_info = {
            "pair": f"TC{id_a}_{slug_a} -> TC{id_b}_{slug_b}",
            "transition_score": c_score.transition_score,
            "palette_consistency": c_score.palette_consistency,
            "luminance_stability": c_score.luminance_stability,
            "inking_consistency": c_score.inking_consistency,
            "notes": c_score.notes
        }
        continuity_pairs.append(pair_info)
        total_continuity += c_score.transition_score

    mean_continuity = round(total_continuity / len(continuity_pairs), 2) if continuity_pairs else 0.0

    # Specifically calculate Minh identity continuity across solo Minh panels (TC1, TC2, TC3, TC5)
    minh_panels = [img for (id_, slug, img, style) in loaded_images if id_ in [1, 2, 3, 5]]
    minh_pairwise = []
    minh_total = 0.0
    for i in range(len(minh_panels) - 1):
        c_score = compute_panel_continuity(minh_panels[i], minh_panels[i+1])
        minh_pairwise.append(c_score.transition_score)
        minh_total += c_score.transition_score
    minh_continuity = round(minh_total / len(minh_pairwise), 2) if minh_pairwise else 0.0

    data["overall_continuity_score"] = mean_continuity
    data["minh_character_continuity_score"] = minh_continuity
    data["continuity_pairs"] = continuity_pairs

    with open(TELEMETRY_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Metrics evaluated successfully!")
    print(f"Overall Cross-Case Continuity: {mean_continuity}/100")
    print(f"Minh Character Consistency (TC1->TC2->TC3->TC5): {minh_continuity}/100")
    for tc in test_cases:
        qm = tc["quality_metrics"]
        qa = tc["qa_validation"]
        print(f"TC{tc['id']} ({tc['slug']}): QA Valid={qa['is_valid']}, Quality Score={qm['overall_score']}, Inking={qm['inking_sharpness']}, Contrast={qm['contrast_score']}")

if __name__ == "__main__":
    process()
