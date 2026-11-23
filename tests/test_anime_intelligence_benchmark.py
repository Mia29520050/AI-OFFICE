"""Unit & Empirical Tests for Anime Intelligence System Benchmark.

Validates:
1. Candidate model specifications (Anima, Anima-Ref-Adapter, Z-Anime 6B, QWEN-Anime 20B).
2. Memory constraints and feasibility gates for RTX 3050 Laptop 6GB VRAM / 12GB RAM.
3. 8 standardized test cases covering portrait, fullbody, classroom, interaction, angles, B&W, color, sequence.
4. Image quality validation (white/dark ratio, lineart edge density) via manga_validator.
5. Cross-panel continuity evaluation and visual metric scoring via manga_metrics.
6. End-to-end benchmark execution and report generation (JSON + Markdown).
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from PIL import Image

import sys
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "app"))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from run_anime_benchmark import (
    CANDIDATE_MODELS,
    BENCHMARK_TEST_CASES,
    detect_hardware,
    generate_benchmark_image,
    run_all_benchmarks,
    BENCHMARK_DIR,
    BENCHMARK_REPORT_PATH,
    BENCHMARK_SUMMARY_MD_PATH,
)
from manga_validator import validate_panel_image, PanelValidationResult
from manga_metrics import evaluate_manga_panel, compute_panel_continuity


def test_candidate_models_specifications():
    """Verify all 8 candidate architectures are defined with realistic memory budgets."""
    assert len(CANDIDATE_MODELS) == 8
    model_ids = {m.config_id for m in CANDIDATE_MODELS}

    expected_ids = {
        "Anima-Base-FP16",
        "Anima-Aesthetic-FP16",
        "Anima-Turbo-GGUF-Q4_K_M",
        "Anima-GGUF-Q4_K_M",
        "Anima-GGUF-Q5_K_M",
        "Anima-Turbo-GGUF-Q4_K_M + Anima-Ref-Adapter",
        "Z-Anime-6B",
        "QWEN-Anime-20B",
    }
    assert expected_ids.issubset(model_ids)

    # Check 6GB VRAM constraint classification
    for m in CANDIDATE_MODELS:
        if m.config_id in [
            "Anima-Turbo-GGUF-Q4_K_M",
            "Anima-GGUF-Q4_K_M",
            "Anima-Turbo-GGUF-Q4_K_M + Anima-Ref-Adapter",
            "Z-Anime-6B",
        ]:
            assert m.estimated_peak_vram_mb < 6144.0, f"{m.config_id} should fit in 6GB VRAM"
            assert m.feasibility_status == "OPTIMAL_SAFE_GPU"
            assert m.recommended_for_studio is True

        if m.config_id == "QWEN-Anime-20B":
            # 20B parameters model must be flagged as requiring cloud
            assert m.estimated_peak_vram_mb >= 6140.0
            assert m.feasibility_status == "OOM_LOCAL_CLOUD_RECOMMENDED"
            assert m.recommended_for_studio is False


def test_standardized_test_cases_integrity():
    """Verify all 8 test cases cover required scenarios and locked character traits."""
    assert len(BENCHMARK_TEST_CASES) == 8
    ids = [tc["id"] for tc in BENCHMARK_TEST_CASES]
    assert ids == list(range(1, 9))

    # Test Case 1: Portrait
    tc1 = BENCHMARK_TEST_CASES[0]
    assert "portrait" in tc1["name"].lower()
    assert "1boy" in tc1["prompt"]
    assert "navy blazer" in tc1["prompt"]

    # Test Case 4: Two characters (Minh + Mai)
    tc4 = BENCHMARK_TEST_CASES[3]
    assert "2people" in tc4["prompt"]
    assert "Mai" in tc4["description"]

    # Test Case 6: B&W Manga
    tc6 = BENCHMARK_TEST_CASES[5]
    assert tc6["art_style"] == "manga_bw"
    assert "monochrome manga" in tc6["prompt"]

    # Test Case 7: Color Manga
    tc7 = BENCHMARK_TEST_CASES[6]
    assert tc7["art_style"] == "anime_color"
    assert "cel shading" in tc7["prompt"]

    # Test Case 8: 4-Panel Sequence
    tc8 = BENCHMARK_TEST_CASES[7]
    assert tc8["width"] == 1024
    assert tc8["height"] == 1024


def test_hardware_detection_and_profiling():
    """Verify hardware detection accurately identifies GPU and memory limits."""
    gpu_name, vram_mb, ram_mb, cuda_avail = detect_hardware()
    assert "RTX 3050" in gpu_name or "NVIDIA" in gpu_name
    assert vram_mb >= 4000.0
    assert ram_mb >= 8000.0


def test_image_generation_and_qa_gates():
    """Verify benchmark image generation produces valid images passing quality gates."""
    # Test generation on TC1 (portrait) and TC6 (B&W manga)
    tc1 = BENCHMARK_TEST_CASES[0]
    img1_path = generate_benchmark_image(tc1, "Anima-Turbo-GGUF-Q4_K_M + Anima-Ref-Adapter")
    assert img1_path.exists()

    img1 = Image.open(img1_path)
    assert img1.size == (768, 1024)

    # QA validation check
    qa1: PanelValidationResult = validate_panel_image(img1, panel_id="test_tc1")
    assert qa1.is_valid is True, f"TC1 failed QA: {qa1.failure_reasons}"
    assert qa1.edge_density > 0.015
    assert qa1.dark_ratio > 0.045

    # Visual metric evaluation
    metric1 = evaluate_manga_panel(img1, is_bw=False)
    assert metric1.overall_score >= 60.0
    assert metric1.inking_sharpness >= 60.0


def test_cross_panel_continuity_metric():
    """Verify pairwise continuity computation between two consecutive benchmark frames."""
    tc1 = BENCHMARK_TEST_CASES[0]
    tc2 = BENCHMARK_TEST_CASES[1]
    p1 = generate_benchmark_image(tc1, "Anima-Turbo-GGUF-Q4_K_M + Anima-Ref-Adapter")
    p2 = generate_benchmark_image(tc2, "Anima-Turbo-GGUF-Q4_K_M + Anima-Ref-Adapter")

    img1 = Image.open(p1)
    img2 = Image.open(p2)

    cont = compute_panel_continuity(img1, img2)
    assert cont.transition_score >= 65.0
    assert cont.palette_consistency > 0.50
    assert cont.inking_consistency > 0.30


def test_full_benchmark_execution_and_reports():
    """Verify run_all_benchmarks executes all 8 cases and writes JSON + Markdown reports."""
    report = run_all_benchmarks()

    assert "metadata" in report
    assert "candidate_models" in report
    assert "benchmark_cases" in report

    assert len(report["benchmark_cases"]) == 8
    for case in report["benchmark_cases"]:
        assert case["status"] == "PASS"
        assert case["qa_valid"] is True
        assert Path(case["output_image_path"]).exists()

    # Verify JSON report on disk
    assert BENCHMARK_REPORT_PATH.exists()
    saved_json = json.loads(BENCHMARK_REPORT_PATH.read_text(encoding="utf-8"))
    assert len(saved_json["benchmark_cases"]) == 8

    # Verify Markdown summary on disk
    assert BENCHMARK_SUMMARY_MD_PATH.exists()
    md_content = BENCHMARK_SUMMARY_MD_PATH.read_text(encoding="utf-8")
    assert "Báo cáo Benchmark Thực nghiệm" in md_content
    assert "Anima-GGUF-Q4_K_M" in md_content
    assert "QWEN-Anime-20B" in md_content
    assert "TC08" in md_content or "TC 08" in md_content or "tc08" in md_content.lower()
