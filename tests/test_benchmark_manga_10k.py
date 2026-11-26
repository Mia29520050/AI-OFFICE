# -*- coding: utf-8 -*-
"""
Tests for 10,000 Manga Benchmark Engine & Comparative Evaluator
================================================================
Validates evaluation calculations, reading order ranking, face clearance checking,
Dark Fantasy archetype detection, and export capabilities.
"""

import json
from pathlib import Path
import pytest

from scripts.benchmarks.benchmark_manga_10k import (
    evaluate_single_case,
    run_10k_benchmark,
    export_json_report,
    export_markdown_report,
    GPT_SUNBURST_BASELINES,
    CaseEvalResult,
    Benchmark10kSummary,
)


class TestBenchmarkEvaluatorLogic:
    def test_evaluate_single_case_valid_layout(self):
        item = {
            "id": "test_case_001",
            "category": "dark_fantasy_climax",
            "dialogues": [
                {"text": "Ngươi dám bước vào thánh địa của ta sao, Kỵ sĩ?", "speaker": "Carmilla"},
                {"text": "Ta đến đây để lấy lại thanh Huyết Kiếm!", "speaker": "Albrecht"},
            ],
            "prompt": "masterpiece, authentic japanese manga, screentone, 1girl carmilla, silver hair, glowing red eyes, vampire princess gothic dress, smug expression, looking down, gothic castle ruins, blood moon, dramatic low angle",
        }
        res = evaluate_single_case(item)
        assert res.case_id == "test_case_001"
        assert res.num_bubbles == 2
        assert res.is_collision_free is True
        assert res.overlap_area_px2 == 0.0
        assert res.is_reading_order_valid is True
        assert res.is_face_cleared is True
        assert res.is_prompt_decomposed is True
        assert res.has_dark_fantasy_archetype is True

    def test_dark_fantasy_markers_detection(self):
        item_dark = {
            "id": "dark_01",
            "prompt": "manga screentone, 1boy albrecht, black obsidian armor, vampire knight, holding crimson blood sword, intense glare, gothic ruins",
        }
        res_dark = evaluate_single_case(item_dark)
        assert res_dark.has_dark_fantasy_archetype is True

        item_slice_of_life = {
            "id": "sol_01",
            "prompt": "manga screentone, 1girl koharu, pastel hoodie, smiling gently, sunny classroom window, medium shot",
        }
        res_sol = evaluate_single_case(item_slice_of_life)
        assert res_sol.has_dark_fantasy_archetype is False

    def test_gpt_sunburst_baselines_present(self):
        assert "zero_collision_rate_pct" in GPT_SUNBURST_BASELINES
        assert "average_overlap_area_px2" in GPT_SUNBURST_BASELINES
        assert "reading_order_compliance_pct" in GPT_SUNBURST_BASELINES
        assert "face_clearance_rate_pct" in GPT_SUNBURST_BASELINES
        assert GPT_SUNBURST_BASELINES["average_overlap_area_px2"] > 0.0

    def test_mock_dataset_execution_and_exports(self, tmp_path):
        # Create a small mock dataset
        mock_file = tmp_path / "mock_10k_sample.jsonl"
        cases = []
        for i in range(20):
            cases.append({
                "id": f"sample_{i:04d}",
                "category": "gothic_encounter" if i % 2 == 0 else "knight_duel",
                "dialogues": [
                    {"text": f"Lời thoại thứ nhất của cảnh {i}", "speaker": "Carmilla"},
                    {"text": f"Lời thoại thứ hai của cảnh {i}", "speaker": "Albrecht"},
                ],
                "prompt": f"monochrome manga screentone, 1girl carmilla silver hair red eyes vampire dress, 1boy albrecht knight armor crimson blood sword, intense stare, gothic hall, dramatic close-up {i}",
            })

        with open(mock_file, "w", encoding="utf-8") as f:
            for c in cases:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        # Run benchmark on mock
        summary, results = run_10k_benchmark(dataset_path=mock_file)
        assert summary.total_evaluated == 20
        assert summary.collision_free_pct == 100.0
        assert summary.total_overlap_area_px2 == 0.0
        assert summary.reading_order_compliant_pct == 100.0
        assert summary.face_clearance_pct == 100.0
        assert summary.dark_fantasy_archetype_pct == 100.0

        # Export test
        json_out = tmp_path / "report.json"
        md_out = tmp_path / "report.md"
        export_json_report(summary, results, json_out)
        export_markdown_report(summary, md_out)

        assert json_out.exists()
        assert md_out.exists()

        content = md_out.read_text(encoding="utf-8")
        assert "GPT-IMAGE-2.6 SUNBURST" in content
        assert "0.0 px²" in content
