# -*- coding: utf-8 -*-
"""
Tests for Automated Reasoning Benchmark Module (scripts/eval_reasoning.py)
=========================================================================
Validates CoT extraction, linear fallacy detection, verification routines,
and reporting capabilities.
"""

import json
from pathlib import Path
import pytest

from scripts.eval_reasoning import (
    ReasoningCategory,
    TestCase,
    ParsedResponse,
    parse_cot_response,
    extract_numbers_from_text,
    check_linear_fallacy_in_duckweed,
    verify_number,
    verify_boolean,
    verify_big_o,
    verify_logic_roles,
    verify_crossroads_question,
    verify_paradox_denial,
    build_benchmark_test_cases,
    ReasoningEvaluator,
    generate_summary,
    export_json_report,
    export_markdown_report,
)


class TestCoTParsing:
    def test_standard_think_tags(self):
        text = "<think>\nBước 1: Ban đầu có 2 cụm bèo.\nBước 2: Cần 29 ngày.\n</think>\n\nĐáp án là 29 ngày."
        parsed = parse_cot_response(text)
        assert parsed.has_think_tag is True
        assert "Bước 1: Ban đầu có 2 cụm bèo." in parsed.think_text
        assert parsed.answer_text == "Đáp án là 29 ngày."
        assert parsed.think_word_count > 0

    def test_unclosed_think_tag(self):
        text = "<think>\nĐang suy luận dở dang thì bị ngắt..."
        parsed = parse_cot_response(text)
        assert parsed.has_think_tag is True
        assert "Đang suy luận dở dang" in parsed.think_text
        assert "Đang suy luận dở dang" in parsed.answer_text  # fallback to last thought paragraph

    def test_pseudo_think_format(self):
        text = "Suy nghĩ: Cần kiểm tra chuỗi đối xứng.\nĐáp án: Có, đây là palindrome."
        parsed = parse_cot_response(text)
        assert "Cần kiểm tra chuỗi đối xứng." in parsed.think_text
        assert "Có, đây là palindrome." in parsed.answer_text

    def test_plain_text(self):
        text = "Kết luận là 42."
        parsed = parse_cot_response(text)
        assert parsed.has_think_tag is False
        assert parsed.think_text == ""
        assert parsed.answer_text == "Kết luận là 42."


class TestNumberExtractionAndFallacy:
    def test_number_extraction(self):
        text = "Mất khoảng 29 ngày hoặc 7,5 ngày hoặc 3.75 ngày."
        nums = extract_numbers_from_text(text)
        assert 29 in nums
        assert 7.5 in nums
        assert 3.75 in nums

    def test_linear_fallacy_caught(self):
        test_case = TestCase(
            id="EXP_TEST_2_CLUSTERS",
            category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
            title="Test 2 clusters",
            prompt="2 cụm cần bao nhiêu ngày?",
            expected_value=29,
            linear_trap_values=[15],
            linear_trap_keywords=["30 chia 2"],
            verifier_type="number",
        )
        flawed_resp = ParsedResponse(
            raw_text="30 chia 2 = 15. Kết luận: 15 ngày.",
            think_text="Chia đều tuyến tính 30 / 2",
            answer_text="Kết luận: 15 ngày.",
            has_think_tag=False,
            think_word_count=5,
            think_char_count=20,
        )
        is_fallacy, reason = check_linear_fallacy_in_duckweed(flawed_resp, test_case)
        assert is_fallacy is True
        assert "15" in reason

        is_corr, ext_ans, fallacy_flag, notes = verify_number(flawed_resp, test_case)
        assert is_corr is False
        assert fallacy_flag is True
        assert ext_ans == "15"

    def test_linear_fallacy_refuted_not_flagged(self):
        test_case = TestCase(
            id="EXP_TEST_2_CLUSTERS",
            category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
            title="Test 2 clusters",
            prompt="2 cụm cần bao nhiêu ngày?",
            expected_value=29,
            linear_trap_values=[15],
            linear_trap_keywords=["30 chia 2"],
            verifier_type="number",
        )
        correct_resp = ParsedResponse(
            raw_text="<think>Không thể lấy 30 chia cho 2 = 15 vì đây là hàm mũ nhân đôi.</think> Đáp án chính xác là 29 ngày.",
            think_text="Không thể lấy 30 chia cho 2 = 15 vì đây là hàm mũ nhân đôi.",
            answer_text="Đáp án chính xác là 29 ngày.",
            has_think_tag=True,
            think_word_count=15,
            think_char_count=60,
        )
        is_corr, ext_ans, fallacy_flag, notes = verify_number(correct_resp, test_case)
        assert is_corr is True
        assert fallacy_flag is False
        assert ext_ans == "29"


class TestSpecialVerifiers:
    def test_boolean_verifier(self):
        tc = TestCase(
            id="PALIN_TEST",
            category=ReasoningCategory.ALGORITHM_PALINDROME,
            title="Palindrome test",
            prompt="",
            expected_value=True,
            verifier_type="boolean",
        )
        resp_yes = ParsedResponse(raw_text="Có, chuỗi này là palindrome.", think_text="", answer_text="Có, chuỗi này là palindrome.", has_think_tag=False, think_word_count=0, think_char_count=0)
        is_corr, ext, _, _ = verify_boolean(resp_yes, tc)
        assert is_corr is True
        assert "Có" in ext

        resp_no = ParsedResponse(raw_text="Không, chuỗi này không đối xứng.", think_text="", answer_text="Không, chuỗi này không đối xứng.", has_think_tag=False, think_word_count=0, think_char_count=0)
        is_corr, ext, _, _ = verify_boolean(resp_no, tc)
        assert is_corr is False

    def test_big_o_verifier(self):
        tc = TestCase(
            id="BIG_O_TEST",
            category=ReasoningCategory.ALGORITHM_PALINDROME,
            title="Big O test",
            prompt="",
            expected_value="O(n)",
            verifier_type="big_o",
        )
        resp = ParsedResponse(raw_text="Độ phức tạp là O(N).", think_text="", answer_text="Độ phức tạp là O(N).", has_think_tag=False, think_word_count=0, think_char_count=0)
        is_corr, ext, _, _ = verify_big_o(resp, tc)
        assert is_corr is True
        assert "o(n)" in ext.lower()

    def test_logic_roles_verifier(self):
        tc = TestCase(
            id="LOGIC_ROLES_TEST",
            category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
            title="Roles test",
            prompt="",
            expected_value={"A": "liar", "B": "knight"},
            verifier_type="logic_roles",
        )
        resp = ParsedResponse(raw_text="A là kẻ nói dối, B là người nói thật.", think_text="", answer_text="A là kẻ nói dối, B là người nói thật.", has_think_tag=False, think_word_count=0, think_char_count=0)
        is_corr, ext, _, _ = verify_logic_roles(resp, tc)
        assert is_corr is True
        assert "A:liar" in ext
        assert "B:knight" in ext

    def test_crossroads_verifier(self):
        tc = TestCase(
            id="CROSSROADS_TEST",
            category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
            title="Crossroads",
            prompt="",
            expected_value="ask_other",
        )
        resp = ParsedResponse(raw_text="Hỏi: 'Người kia sẽ chỉ con đường nào vào làng?' rồi đi đường ngược lại.", think_text="", answer_text="Hỏi: 'Người kia sẽ chỉ con đường nào vào làng?' rồi đi đường ngược lại.", has_think_tag=False, think_word_count=0, think_char_count=0)
        is_corr, ext, _, _ = verify_crossroads_question(resp, tc)
        assert is_corr is True


class TestBenchmarkEngineIntegration:
    def test_all_cases_loaded(self):
        cases = build_benchmark_test_cases()
        assert len(cases) >= 28
        categories = {c.category for c in cases}
        assert ReasoningCategory.EXPONENTIAL_DUCKWEED in categories
        assert ReasoningCategory.LOGIC_KNIGHT_KNAVE in categories
        assert ReasoningCategory.CHAR_COUNTING_STRAWBERRY in categories
        assert ReasoningCategory.ALGORITHM_PALINDROME in categories

    def test_mock_benchmark_execution_and_reports(self, tmp_path):
        json_out = tmp_path / "test_benchmark.json"
        md_out = tmp_path / "test_report.md"

        evaluator = ReasoningEvaluator(mock_mode=True, simulate_flawed=True)
        cases = build_benchmark_test_cases()[:6]

        results = [evaluator.run_single_test(tc) for tc in cases]
        assert len(results) == 6

        summary = generate_summary(results, model="mock-model", host="http://localhost", backend="mock")
        assert summary["total_tests"] == 6
        assert "accuracy_pct" in summary
        assert "linear_fallacies_count" in summary

        # Check export
        export_json_report(summary, results, json_out)
        assert json_out.exists()
        with open(json_out, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["details"]) == 6

        export_markdown_report(summary, results, md_out)
        assert md_out.exists()
        content = md_out.read_text(encoding="utf-8")
        assert "BÁO CÁO ĐÁNH GIÁ NĂNG LỰC SUY LUẬN LOGIC" in content
        assert "EXECUTIVE SUMMARY" in content
