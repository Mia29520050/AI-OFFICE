# -*- coding: utf-8 -*-
"""
Tests for Synthetic Reasoning CoT Dataset Module
================================================
Validates data generation, mathematical correctness, ChatML schema adherence,
and <think> reasoning structure.
"""

import json
import pytest
from pathlib import Path
from scripts.experiments.generate_reasoning_data import (
    generate_dataset,
    format_chatml_text,
    LilypadExponentialGenerator,
    LetterDecompositionGenerator,
    KnightsAndKnavesGenerator,
    CognitiveTrapMathGenerator
)
import random


class TestReasoningDatasetGeneration:

    def test_schema_conformance(self):
        samples = generate_dataset(num_samples=20, seed=123)
        assert len(samples) == 20

        required_keys = {"id", "category", "difficulty", "messages", "text"}
        for s in samples:
            assert required_keys.issubset(s.keys())
            assert isinstance(s["messages"], list)
            assert len(s["messages"]) == 3

            roles = [m["role"] for m in s["messages"]]
            assert roles == ["system", "user", "assistant"]

            asst_content = s["messages"][2]["content"]
            assert "<think>" in asst_content
            assert "</think>" in asst_content

            # Verify think tag is properly closed and there's a final answer
            think_part = asst_content.split("</think>")[0].replace("<think>", "").strip()
            answer_part = asst_content.split("</think>")[1].strip()

            assert len(think_part) > 50, "Thinking block should have substantive depth"
            assert len(answer_part) > 10, "Final answer outside <think> must not be empty"

            # Check ChatML text structure
            text = s["text"]
            assert "<|im_start|>system" in text
            assert "<|im_start|>user" in text
            assert "<|im_start|>assistant" in text
            assert text.count("<|im_end|>") == 3

    def test_lilypad_exponential_math(self):
        rng = random.Random(42)
        gen = LilypadExponentialGenerator(rng)
        samples = [gen.generate() for _ in range(30)]

        for s in samples:
            assert s["category"] == "exponential_growth_lilypad"
            asst = s["messages"][2]["content"]
            assert "<think>" in asst
            assert "</think>" in asst

    def test_letter_decomposition_counting(self):
        rng = random.Random(999)
        gen = LetterDecompositionGenerator(rng)

        # Test strawberry 'r' specifically
        strawberry_sample = gen._gen_en("strawberry", "r")
        asst = strawberry_sample["messages"][2]["content"]
        assert "3" in asst
        assert "Position 3" in asst
        assert "Position 8" in asst
        assert "Position 9" in asst

        # Test zero count
        zero_sample = gen._gen_en("strawberry", "z")
        asst_zero = zero_sample["messages"][2]["content"]
        assert "0" in asst_zero

    def test_knights_and_knaves_logic(self):
        rng = random.Random(555)
        gen = KnightsAndKnavesGenerator(rng)
        samples = [gen.generate() for _ in range(25)]

        for s in samples:
            assert s["category"] == "logic_truth_liar"
            asst = s["messages"][2]["content"]
            asst_lower = asst.lower()
            assert any(term in asst_lower for term in ["mâu thuẫn", "contradiction", "nhất quán", "hợp lệ", "nghiệm"])

    def test_cognitive_traps_math(self):
        rng = random.Random(777)
        gen = CognitiveTrapMathGenerator(rng)
        samples = [gen.generate() for _ in range(25)]

        for s in samples:
            assert s["category"] == "cognitive_traps_math"
            asst = s["messages"][2]["content"]
            assert "<think>" in asst

    def test_output_file_integrity(self):
        dataset_path = Path("data/training/reasoning_cot_train.jsonl")
        assert dataset_path.exists(), "Dataset file must exist at data/training/reasoning_cot_train.jsonl"
        assert dataset_path.stat().st_size > 100_000, "Dataset file must not be empty"

        # Validate line-by-line json parsing
        count = 0
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                assert "id" in item
                assert "messages" in item
                assert "<think>" in item["messages"][2]["content"]
                count += 1

        assert count >= 1000, f"Expected at least 1000 samples, got {count}"
