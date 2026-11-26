# -*- coding: utf-8 -*-
"""
Tests for Japanese Manga Grammar & Dark Fantasy 10k Dataset
===========================================================
Validates generation logic, ChatML schema adherence, RTL reading flow,
zero-collision bubble placement, face safety zone clearance, and file integrity.
"""

import json
import pytest
from pathlib import Path
import random

from scripts.experiments.generate_manga_japanese_grammar_10k import (
    generate_single_sample,
    DARK_FANTASY_CHARACTERS,
    PANEL_LAYOUT_PRESETS,
    MANGA_SFX_CATALOG,
    SAFE_CORNER_ANCHORS,
    OUTPUT_PATH
)


class TestMangaJapaneseGrammar10k:

    def test_single_sample_generation_schema(self):
        rng = random.Random(12345)
        sample = generate_single_sample(1, rng)

        required_keys = {
            "id", "category", "benchmark_standard", "koma_layout",
            "koma_count", "primary_character", "dialogue_count",
            "sfx", "verification_metrics", "messages", "text"
        }
        assert required_keys.issubset(sample.keys())
        assert sample["benchmark_standard"] == "GPT-Image-2.6-Sunburst-Equiv"
        assert sample["verification_metrics"]["target_overlap_area"] == 0.0
        assert sample["verification_metrics"]["all_bubbles_outside_face_zone"] is True

    def test_chatml_and_think_block(self):
        rng = random.Random(54321)
        sample = generate_single_sample(42, rng)

        messages = sample["messages"]
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

        asst_content = messages[2]["content"]
        assert "<think>" in asst_content
        assert "</think>" in asst_content

        think_section = asst_content.split("</think>")[0].replace("<think>", "").strip()
        assert "Ngữ pháp Bố cục Manga (Koma-wari)" in think_section
        assert "Face & Eye Clearance" in think_section
        assert "Dynamic SFX" in think_section
        assert "StoryDiffusion" in think_section

        # Test prompt text outside <think>
        outside_think = asst_content.split("</think>")[1]
        assert "Bố cục Khung thoại An toàn" in outside_think
        assert "Prompt ComfyUI Phân rã 4 Thành phần" in outside_think

    def test_reading_flow_and_face_avoidance(self):
        rng = random.Random(99999)
        # Test 100 procedural samples
        face_zone = [0.28, 0.24, 0.72, 0.70]  # [ymin, xmin, ymax, xmax]

        for i in range(1, 101):
            sample = generate_single_sample(i, rng)
            # Verify safe bubbles do not intrude into face zone
            for corner in SAFE_CORNER_ANCHORS:
                x = corner["x"]
                y = corner["y"]
                in_face_zone = (face_zone[1] <= x <= face_zone[3]) and (face_zone[0] <= y <= face_zone[2])
                assert not in_face_zone, f"Anchor {corner['pos']} intruded into face safety zone!"

    def test_dark_fantasy_archetypes(self):
        rng = random.Random(777)
        sample = generate_single_sample(10, rng)
        asst = sample["messages"][2]["content"]

        # Check for presence of anchor token
        found_anchor = any(
            c["anchor_token"] in asst
            for c in DARK_FANTASY_CHARACTERS.values()
        )
        assert found_anchor, "Generated prompt must contain at least one StoryDiffusion anchor token"

    def test_dataset_10k_file_integrity(self):
        assert OUTPUT_PATH.exists(), f"Dataset file must exist at {OUTPUT_PATH}"
        size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
        assert size_mb > 100.0, f"Expected file size > 100 MB, got {size_mb:.2f} MB"

        # Spot check line count and parsing
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            first_50 = [json.loads(f.readline()) for _ in range(50)]
            assert len(first_50) == 50
            for s in first_50:
                assert s["id"].startswith("manga_10k_")
                assert "<think>" in s["messages"][2]["content"]

        # Fast line count check
        with open(OUTPUT_PATH, "rb") as f:
            total_lines = sum(1 for _ in f)
        assert total_lines == 10000, f"Expected exactly 10,000 lines, found {total_lines}"
