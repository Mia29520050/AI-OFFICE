#!/usr/bin/env python3
"""
scripts/eval_reasoning.py

Automated Reasoning Benchmark Engine for AI Office & Ollama.
Evaluates:
  1. Exponential Duckweed Puzzles (1, 2, 4, 8, 16 clusters, half/quarter lake)
     - Detects linear fallacy (e.g. dividing 30 days by clusters -> 15, 7.5 days)
  2. Logic Knight & Knave Puzzles (Truth-tellers vs Liars, Crossroads, Paradoxes)
  3. Character Counting & Tokenizer Traps (strawberry 'r', blueberry, Vietnamese diacritics)
  4. Palindrome & Algorithmic Reasoning (Two-pointer logic, string manipulation, Big-O)

Features:
  - Deep CoT parsing: extracts and analyzes content inside/outside <think> tags.
  - Linear fallacy detector: flags whether the model made linear rate assumptions.
  - Multi-endpoint support: Ollama (/api/chat, /api/generate) & AI Office backend (8765).
  - Built-in Mock Mode for fast offline validation & CI testing.
  - Rich JSON and Markdown reports with executive summaries and case-by-case audits.
"""

from __future__ import annotations

import argparse
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_AIOFFICE_HOST = "http://127.0.0.1:8765"
DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_JSON_OUT = ROOT_DIR / "data" / "benchmark_reasoning_results.json"
DEFAULT_MD_OUT = ROOT_DIR / "docs" / "BENCHMARK_REASONING_REPORT.md"


class ReasoningCategory(str, Enum):
    EXPONENTIAL_DUCKWEED = "exponential_duckweed"
    LOGIC_KNIGHT_KNAVE = "logic_knight_knave"
    CHAR_COUNTING_STRAWBERRY = "char_counting_strawberry"
    ALGORITHM_PALINDROME = "algorithm_palindrome"


@dataclass
class ParsedResponse:
    raw_text: str
    think_text: str
    answer_text: str
    has_think_tag: bool
    think_word_count: int
    think_char_count: int


@dataclass
class TestCase:
    __test__ = False
    id: str
    category: ReasoningCategory
    title: str
    prompt: str
    expected_value: Any
    linear_trap_values: List[Any] = field(default_factory=list)
    linear_trap_keywords: List[str] = field(default_factory=list)
    verifier_type: str = "number"  # number | boolean | custom | logic_roles | big_o
    custom_verifier: Optional[Callable[[ParsedResponse, TestCase], Tuple[bool, str, bool, str]]] = None


@dataclass
class TestResult:
    test_case: TestCase
    parsed_response: ParsedResponse
    is_correct: bool
    linear_fallacy_detected: bool
    extracted_answer: str
    latency_ms: float
    status: str  # PASS | FAIL | LINEAR_FALLACY | ERROR
    notes: str


def parse_cot_response(text: str) -> ParsedResponse:
    """
    Extracts reasoning within <think>...</think> and separates it from the final answer.
    Handles unclosed tags and nested formatting gracefully.
    """
    raw = text or ""
    has_think = False
    think_text = ""
    answer_text = ""

    think_pattern = re.compile(r"<think>(.*?)(?:</think>|$)", re.DOTALL | re.IGNORECASE)
    match = think_pattern.search(raw)

    if match:
        has_think = True
        think_text = match.group(1).strip()
        # Remove matched think tag from raw text to get answer text
        answer_text = re.sub(r"<think>.*?(?:</think>|$)", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    else:
        # Check if model used markdown block or pseudo-think header
        pseudo_match = re.search(r"(?:Suy nghĩ|Thinking|Reasoning):\s*(.*?)\n\s*(?:Kết luận|Conclusion|Answer|Đáp án):", raw, re.DOTALL | re.IGNORECASE)
        if pseudo_match:
            think_text = pseudo_match.group(1).strip()
            answer_text = raw[pseudo_match.end():].strip()
        else:
            answer_text = raw.strip()

    # If answer_text is empty but think_text has content (model stopped before </think> or answered inside)
    if not answer_text and think_text:
        # Check last paragraph of think_text
        paragraphs = [p.strip() for p in think_text.split("\n\n") if p.strip()]
        if paragraphs:
            answer_text = paragraphs[-1]

    think_words = len(re.findall(r"\w+", think_text))
    think_chars = len(think_text)

    return ParsedResponse(
        raw_text=raw,
        think_text=think_text,
        answer_text=answer_text,
        has_think_tag=has_think,
        think_word_count=think_words,
        think_char_count=think_chars,
    )


def extract_numbers_from_text(text: str) -> List[float]:
    """Extracts integer and float numbers from string, handling Vietnamese commas."""
    normalized = text.replace(",", ".")
    matches = re.findall(r"(?<![a-zA-Z_])(\d+(?:\.\d+)?)(?![a-zA-Z_])", normalized)
    results = []
    for m in matches:
        try:
            val = float(m)
            results.append(int(val) if val.is_integer() else val)
        except ValueError:
            pass
    return results


def check_linear_fallacy_in_duckweed(
    response: ParsedResponse,
    test_case: TestCase
) -> Tuple[bool, str]:
    """
    Checks if model committed the linear division fallacy:
    e.g., If 1 clump takes 30 days, 2 clumps take 30/2 = 15 days, 4 clumps take 7.5 days.
    """
    answer_text = response.answer_text.lower()
    full_text = f"{response.answer_text} {response.think_text}".lower()

    # Refutation check: if text says "không phải là 15", "không lấy 30 chia", etc.
    # We should not treat refutation as fallacy
    answer_nums = extract_numbers_from_text(response.answer_text)
    
    # 1. Check if trap value is explicitly presented in the final answer
    for trap in test_case.linear_trap_values:
        if trap in answer_nums:
            # Verify it's not preceded by negation
            neg_pattern = rf"(?:không\s*phải|không\s*được|tránh|not|never)\s*(?:là\s*)?{trap}"
            if not re.search(neg_pattern, answer_text):
                return True, f"Model concluded with linear trap value: {trap}"

    # 2. Check for linear division expressions asserting the trap
    linear_assertion_patterns = [
        (r"30\s*/\s*2\s*=\s*15", "30 / 2 = 15"),
        (r"30\s*chia\s*(?:cho\s*)?2\s*(?:bằng|=)?\s*15", "30 chia 2 = 15"),
        (r"30\s*/\s*4\s*=\s*7\.?5?", "30 / 4 = 7.5"),
        (r"30\s*chia\s*(?:cho\s*)?4\s*(?:bằng|=)?\s*7\.?5?", "30 chia 4 = 7.5"),
        (r"30\s*/\s*8\s*=\s*3\.?75?", "30 / 8 = 3.75"),
        (r"30\s*chia\s*(?:cho\s*)?8\s*(?:bằng|=)?\s*3\.?75?", "30 chia 8 = 3.75"),
        (r"48\s*/\s*2\s*=\s*24", "48 / 2 = 24"),
        (r"48\s*chia\s*(?:cho\s*)?2\s*(?:bằng|=)?\s*24", "48 chia 2 = 24"),
        (r"48\s*/\s*4\s*=\s*12", "48 / 4 = 12"),
        (r"48\s*chia\s*(?:cho\s*)?4\s*(?:bằng|=)?\s*12", "48 chia 4 = 12"),
    ]
    for pat, desc in linear_assertion_patterns:
        if re.search(pat, answer_text):
            return True, f"Asserted linear calculation: {desc}"

    # 3. Check for keywords asserting inverse linear proportion in the final answer
    for kw in test_case.linear_trap_keywords:
        if kw.lower() in answer_text:
            return True, f"Found linear fallacy indicator in conclusion: '{kw}'"

    return False, ""


def verify_number(response: ParsedResponse, test_case: TestCase) -> Tuple[bool, str, bool, str]:
    """Verifies numeric answer with linear fallacy detection."""
    expected = test_case.expected_value
    is_fallacy, fallacy_reason = False, ""

    # Search numbers in answer_text first
    extracted_nums = extract_numbers_from_text(response.answer_text)
    
    # If not found in answer_text, inspect think_text
    if not extracted_nums and response.think_text:
        extracted_nums = extract_numbers_from_text(response.think_text)

    if not extracted_nums:
        if test_case.category == ReasoningCategory.EXPONENTIAL_DUCKWEED:
            is_fallacy, fallacy_reason = check_linear_fallacy_in_duckweed(response, test_case)
        return False, "None", is_fallacy, "No numeric value found in output"

    ans_str = ""
    is_correct = False

    # Check if expected is in extracted numbers
    if expected in extracted_nums:
        is_correct = True
        ans_str = str(expected)
        notes = f"Matched expected number: {expected}"
        # Successfully found the exponential answer, no fallacy
        is_fallacy = False
    else:
        # Model missed the expected answer
        ans_str = str(extracted_nums[-1])
        notes = f"Extracted {ans_str}, expected {expected}"
        if test_case.category == ReasoningCategory.EXPONENTIAL_DUCKWEED:
            is_fallacy, fallacy_reason = check_linear_fallacy_in_duckweed(response, test_case)
            if is_fallacy:
                notes += f" | {fallacy_reason}"

    return is_correct, ans_str, is_fallacy, notes


def verify_boolean(response: ParsedResponse, test_case: TestCase) -> Tuple[bool, str, bool, str]:
    """Verifies Yes/No or Có/Không responses."""
    text = response.answer_text.lower()
    if not text:
        text = response.think_text.lower()

    expected = bool(test_case.expected_value)
    has_yes = bool(re.search(r"\b(có|phải|đúng|yes|true|là palindrome|đối xứng)\b", text))
    has_no = bool(re.search(r"\b(không|sai|chưa|no|false|không phải|not a palindrome)\b", text))

    extracted = "Ambiguous"
    is_correct = False

    # Determine extracted conclusion
    if has_yes and not has_no:
        extracted = "Có/True"
        is_correct = (expected is True)
    elif has_no and not has_yes:
        extracted = "Không/False"
        is_correct = (expected is False)
    elif has_yes and has_no:
        # Disambiguate by checking phrases like "Kết luận: Có" or "Không phải là"
        if re.search(r"kết luận\s*:\s*có|đáp án\s*:\s*có|chính là palindrome|là một palindrome", text):
            extracted = "Có/True"
            is_correct = (expected is True)
        elif re.search(r"kết luận\s*:\s*không|đáp án\s*:\s*không|không phải là palindrome|không đối xứng", text):
            extracted = "Không/False"
            is_correct = (expected is False)
        else:
            extracted = "Contradictory Yes & No"
            is_correct = False

    notes = f"Extracted '{extracted}', expected {'Có/True' if expected else 'Không/False'}"
    return is_correct, extracted, False, notes


def verify_big_o(response: ParsedResponse, test_case: TestCase) -> Tuple[bool, str, bool, str]:
    """Verifies Big-O notation e.g. O(n)."""
    text = f"{response.answer_text} {response.think_text}".lower()
    expected = str(test_case.expected_value).lower()

    # Search for O(n), O(N), O(1), O(n^2), O(n log n)
    match = re.search(r"o\s*\(\s*([n0-9\^\s\*log]+)\s*\)", text)
    extracted = f"O({match.group(1).replace(' ', '')})" if match else "Unknown"

    is_correct = ("o(n)" in extracted.lower() or "o(n)" in text) and "o(n^2)" not in response.answer_text.lower()
    notes = f"Extracted '{extracted}', expected '{expected}'"
    return is_correct, extracted, False, notes


def verify_logic_roles(response: ParsedResponse, test_case: TestCase) -> Tuple[bool, str, bool, str]:
    """Verifies Truth-teller / Liar identification."""
    text = f"{response.answer_text} {response.think_text}".lower()
    expected_dict = test_case.expected_value  # e.g. {"A": "liar", "B": "knight"}

    # Patterns for A and B
    extracted_summary = []
    all_matched = True

    for person, role in expected_dict.items():
        person_pat = person.lower()
        if role in ["knight", "truth", "thật"]:
            truth_pat = rf"{person_pat}\s*(?:là|nói)\s*(?:người nói thật|hiệp sĩ|thật|knight|truth)"
            matched = bool(re.search(truth_pat, text) or f"{person_pat} là hiệp sĩ" in text or f"{person_pat} nói thật" in text)
        else:
            liar_pat = rf"{person_pat}\s*(?:là|nói)\s*(?:kẻ nói dối|kẻ gian lận|dối|liar|knave)"
            matched = bool(re.search(liar_pat, text) or f"{person_pat} là kẻ nói dối" in text or f"{person_pat} là kẻ gian lận" in text or f"{person_pat} nói dối" in text)
        
        extracted_summary.append(f"{person}:{role if matched else 'wrong'}")
        if not matched:
            all_matched = False

    summary_str = ", ".join(extracted_summary)
    notes = f"Role verification: {summary_str}"
    return all_matched, summary_str, False, notes


def verify_crossroads_question(response: ParsedResponse, test_case: TestCase) -> Tuple[bool, str, bool, str]:
    """Verifies the classic two-guard crossroads compound question."""
    text = f"{response.answer_text} {response.think_text}".lower()
    
    # Must ask about the other person: "người kia", "người còn lại", "other guard", "other person"
    has_other = bool(re.search(r"(người kia|người còn lại|người thứ hai|other person|other guard)", text))
    # Must mention path/direction: "đường", "chỉ", "road", "way", "path"
    has_path = bool(re.search(r"(đường|làng|chỉ|path|road|door)", text))
    # Must mention negation / taking opposite: "ngược lại", "opposite"
    has_opposite = bool(re.search(r"(ngược lại|đối diện|opposite|reverse|đường còn lại)", text))

    is_correct = has_other and has_path
    extracted = f"OtherMention={has_other}, PathMention={has_path}, OppositeMention={has_opposite}"
    notes = f"Crossroads logic criteria met: {is_correct} ({extracted})"
    return is_correct, extracted, False, notes


def verify_paradox_denial(response: ParsedResponse, test_case: TestCase) -> Tuple[bool, str, bool, str]:
    """Verifies that no one can say 'I am a liar' on Knight/Knave island."""
    text = f"{response.answer_text} {response.think_text}".lower()
    is_impossible = bool(re.search(r"(không thể|không ai|nghịch lý|vô lý|mâu thuẫn|impossible|paradox|contradiction|cannot)", text))
    extracted = "Impossible/Paradox" if is_impossible else "Allowed"
    notes = f"Recognized paradox impossibility: {is_impossible}"
    return is_impossible, extracted, False, notes


# ==============================================================================
# BENCHMARK TEST SUITE DEFINITION
# ==============================================================================

def build_benchmark_test_cases() -> List[TestCase]:
    cases: List[TestCase] = []

    # --------------------------------------------------------------------------
    # 1. EXPONENTIAL DUCKWEED (Hoa Bèo Hàm Mũ)
    # --------------------------------------------------------------------------
    cases.append(TestCase(
        id="EXP_DUCKWEED_01_BASE",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo 1 cụm ban đầu (Kiểm tra gốc 30 ngày)",
        prompt="Một hồ nước có 1 cụm hoa bèo, sau mỗi ngày số lượng bèo tăng gấp đôi. Sau 30 ngày bèo phủ kín mặt hồ. Hỏi nếu ban đầu có 1 cụm hoa bèo thì sau đúng bao nhiêu ngày bèo phủ kín hồ? Hãy trả lời ngắn gọn số ngày.",
        expected_value=30,
        linear_trap_values=[],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_02_CLUSTERS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo 2 cụm ban đầu (Bẫy tuyến tính 15 ngày)",
        prompt="Một hồ nước có 1 cụm hoa bèo, sau mỗi ngày số lượng bèo tăng gấp đôi. Sau 30 ngày bèo phủ kín mặt hồ. Hỏi nếu ban đầu người ta thả vào hồ 2 cụm bèo cùng loại thì sau bao nhiêu ngày bèo sẽ phủ kín hồ? Hãy suy luận trong thẻ <think> và đưa ra con số ngày chính xác ở phần kết luận.",
        expected_value=29,
        linear_trap_values=[15],
        linear_trap_keywords=["30 chia 2", "30/2 = 15", "15 ngày", "nửa thời gian", "tỉ lệ nghịch"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_04_CLUSTERS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo 4 cụm ban đầu (Bẫy tuyến tính 7.5 ngày)",
        prompt="Một hồ nước có 1 cụm hoa bèo, sau mỗi ngày số lượng bèo nở gấp đôi. Sau 30 ngày bèo phủ kín mặt hồ. Nếu ngay từ đầu hồ có sẵn 4 cụm hoa bèo thì sau bao nhiêu ngày bèo phủ kín hồ? Hãy suy luận và kết luận con số ngày.",
        expected_value=28,
        linear_trap_values=[7.5, 7, 8],
        linear_trap_keywords=["30 chia 4", "30/4", "7.5 ngày", "7,5 ngày"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_08_CLUSTERS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo 8 cụm ban đầu (Bẫy tuyến tính 3.75 ngày)",
        prompt="Một hồ nước ban đầu có 1 cụm bèo, mỗi ngày nở gấp đôi, sau 30 ngày bèo phủ kín hồ. Nếu ban đầu thả vào hồ 8 cụm bèo thì sau bao nhiêu ngày bèo phủ kín hồ? Đưa ra kết luận số ngày.",
        expected_value=27,
        linear_trap_values=[3.75, 4, 3],
        linear_trap_keywords=["30 chia 8", "30/8", "3.75 ngày", "3,75 ngày"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_16_CLUSTERS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo 16 cụm ban đầu (Bẫy tuyến tính 1.875 ngày)",
        prompt="Một hồ nước ban đầu có 1 cụm bèo, mỗi ngày nở gấp đôi, sau 30 ngày bèo phủ kín hồ. Nếu ban đầu thả vào hồ 16 cụm bèo thì sau bao nhiêu ngày bèo phủ kín toàn bộ mặt hồ? Cho biết số ngày.",
        expected_value=26,
        linear_trap_values=[1.875, 2, 1],
        linear_trap_keywords=["30 chia 16", "30/16", "1.875 ngày", "1,875"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_HALF_LAKE",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo nửa hồ (Bẫy tuyến tính 15 ngày)",
        prompt="Một cụm hoa bèo trong hồ mỗi ngày tăng gấp đôi diện tích. Sau 30 ngày bèo phủ kín toàn bộ mặt hồ. Hỏi sau bao nhiêu ngày thì bèo phủ kín đúng một nửa (1/2) hồ? Trả lời con số ngày.",
        expected_value=29,
        linear_trap_values=[15],
        linear_trap_keywords=["15 ngày", "30 chia 2", "30/2"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_QUARTER_LAKE",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa bèo một phần tư hồ (Bẫy tuyến tính 7.5 ngày)",
        prompt="Một hồ nước có bèo nhân đôi mỗi ngày, sau 30 ngày đầy hồ. Hỏi sau bao nhiêu ngày thì bèo phủ kín 1/4 diện tích hồ? Cho biết con số ngày cụ thể.",
        expected_value=28,
        linear_trap_values=[7.5, 7, 8],
        linear_trap_keywords=["7.5 ngày", "7,5 ngày", "30 chia 4", "30/4"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_48DAYS_2CLUSTERS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa súng hồ 48 ngày (Bẫy tuyến tính 24 ngày)",
        prompt="Một bông hoa súng trong hồ mỗi ngày nhân đôi kích thước, mất đúng 48 ngày để phủ kín mặt hồ. Nếu ban đầu hồ có 2 bông hoa súng cùng phát triển thì mất bao nhiêu ngày để phủ kín hồ?",
        expected_value=47,
        linear_trap_values=[24],
        linear_trap_keywords=["24 ngày", "48 chia 2", "48/2"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_48DAYS_4CLUSTERS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Hoa sen hồ 48 ngày, 4 cụm (Bẫy tuyến tính 12 ngày)",
        prompt="Một cây hoa sen mỗi ngày nhân đôi số lượng, mất 48 ngày để phủ kín hồ. Nếu ban đầu trồng 4 cây hoa sen cùng loại thì sau bao nhiêu ngày sen sẽ phủ kín hồ?",
        expected_value=46,
        linear_trap_values=[12],
        linear_trap_keywords=["12 ngày", "48 chia 4", "48/4"],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="EXP_DUCKWEED_ENGLISH_48DAYS",
        category=ReasoningCategory.EXPONENTIAL_DUCKWEED,
        title="Lily pads doubling in English (48 days, 2 patches)",
        prompt="In a lake, a patch of lily pads doubles in size every day. It takes 48 days for 1 patch to cover the entire lake. How many days would it take for 2 patches of lily pads to cover the lake? Give the final number of days.",
        expected_value=47,
        linear_trap_values=[24],
        linear_trap_keywords=["24 days", "48/2", "half the time", "divided by 2"],
        verifier_type="number",
    ))

    # --------------------------------------------------------------------------
    # 2. LOGIC KNIGHT & KNAVE (Logic Thật - Giả)
    # --------------------------------------------------------------------------
    cases.append(TestCase(
        id="LOGIC_KNAVE_BOTH_LIARS",
        category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
        title="A nói: 'Cả hai chúng tôi đều là kẻ nói dối'",
        prompt="Trên một hòn đảo chỉ có Hiệp sĩ (luôn nói thật) và Kẻ nói dối (luôn nói dối). Bạn gặp hai người A và B. Người A nói: 'Cả hai chúng tôi đều là kẻ nói dối'. Hỏi A là ai và B là ai (ai nói thật, ai nói dối)?",
        expected_value={"A": "liar", "B": "knight"},
        verifier_type="logic_roles",
    ))

    cases.append(TestCase(
        id="LOGIC_KNIGHT_DISJUNCTION",
        category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
        title="A nói: 'Tôi là kẻ nói dối hoặc B là hiệp sĩ'",
        prompt="Trên đảo chỉ có Hiệp sĩ (luôn nói thật) và Kẻ gian lận (luôn nói dối). Bạn gặp A và B. A nói: 'Tôi là kẻ gian lận hoặc B là hiệp sĩ'. Hãy suy luận xem A là ai và B là ai?",
        expected_value={"A": "knight", "B": "knight"},
        verifier_type="logic_roles",
    ))

    cases.append(TestCase(
        id="LOGIC_CROSSROADS_QUESTION",
        category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
        title="Câu đố ngã rẽ 2 người lính (1 thật, 1 dối)",
        prompt="Bạn đứng trước ngã rẽ có 2 con đường (đường vào làng và đường cụt nguy hiểm) và gặp 2 người lính. Một người luôn nói thật, một người luôn nói dối, nhưng bạn không biết ai là ai. Bạn chỉ được phép hỏi DUY NHẤT 1 câu với 1 người lính để biết đường vào làng. Bạn sẽ hỏi câu gì?",
        expected_value="ask_other_person",
        verifier_type="custom",
        custom_verifier=verify_crossroads_question,
    ))

    cases.append(TestCase(
        id="LOGIC_THREE_PERSON_CHAIN",
        category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
        title="Chuỗi 3 người A, B, C tố cáo lẫn nhau",
        prompt="Có 3 người A, B, C. Mỗi người hoặc luôn nói thật hoặc luôn nói dối. A nói: 'B nói dối'. B nói: 'C nói dối'. C nói: 'A và B đều nói dối'. Hãy xác định ai là người nói thật, ai là kẻ nói dối.",
        expected_value={"A": "liar", "B": "knight", "C": "liar"},
        verifier_type="logic_roles",
    ))

    cases.append(TestCase(
        id="LOGIC_PARADOX_SELF_CLAIM",
        category=ReasoningCategory.LOGIC_KNIGHT_KNAVE,
        title="Nghịch lý tự nhận 'Tôi là kẻ nói dối'",
        prompt="Trên đảo Hiệp sĩ (luôn nói thật) và Kẻ nói dối (luôn nói dối), có người bản địa nào có thể nói câu: 'Tôi là kẻ nói dối' không? Hãy giải thích tại sao.",
        expected_value="impossible",
        verifier_type="custom",
        custom_verifier=verify_paradox_denial,
    ))

    # --------------------------------------------------------------------------
    # 3. CHARACTER COUNTING & STRAWBERRY (Đếm Ký Tự)
    # --------------------------------------------------------------------------
    cases.append(TestCase(
        id="CHAR_STRAWBERRY_EN_R",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'r' trong 'strawberry' (Tiếng Anh)",
        prompt="How many times does the letter 'r' appear in the word 'strawberry'? Spell out the word letter by letter first, then state the exact count.",
        expected_value=3,
        linear_trap_values=[2],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_STRAWBERRY_VN_R",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'r' trong 'strawberry' (Tiếng Việt)",
        prompt="Trong từ tiếng Anh 'strawberry', chữ cái 'r' xuất hiện bao nhiêu lần? Hãy tách từng chữ cái để đếm và đưa ra kết luận số lần ở cuối.",
        expected_value=3,
        linear_trap_values=[2],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_BLUEBERRY_EN_R",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'r' trong 'blueberry'",
        prompt="How many times does the letter 'r' appear in the word 'blueberry'? Please count carefully.",
        expected_value=2,
        linear_trap_values=[1, 3],
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_APPLE_VN_P",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'p' trong 'apple'",
        prompt="Trong từ 'apple', chữ cái 'p' xuất hiện bao nhiêu lần? Trả lời số lượng.",
        expected_value=2,
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_MISSISSIPPI_EN_S",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 's' trong 'Mississippi'",
        prompt="How many letter 's' are in the word 'Mississippi'? Count them one by one.",
        expected_value=4,
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_NGHIENG_VN_N",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'n' trong từ tiếng Việt 'nghiêng'",
        prompt="Trong từ tiếng Việt 'nghiêng', chữ cái 'n' xuất hiện bao nhiêu lần? (Chú ý đếm kỹ từng vị trí ký tự). Trả lời số lần.",
        expected_value=2,
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_BUOM_BUOM_VN_U",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'ư' trong 'bươm bướm'",
        prompt="Trong cụm từ 'bươm bướm', chữ cái 'ư' xuất hiện bao nhiêu lần? Hãy đưa ra con số chính xác.",
        expected_value=2,
        verifier_type="number",
    ))

    cases.append(TestCase(
        id="CHAR_NGHIEN_CUU_VN_N",
        category=ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
        title="Đếm chữ 'n' trong cụm từ 'nghiên cứu'",
        prompt="Trong cụm từ tiếng Việt 'nghiên cứu', chữ cái 'n' xuất hiện tổng cộng bao nhiêu lần? Trả lời con số cuối cùng.",
        expected_value=2,
        verifier_type="number",
    ))

    # --------------------------------------------------------------------------
    # 4. ALGORITHM PALINDROME (Thuật Toán Palindrome & Tư Duy Logic)
    # --------------------------------------------------------------------------
    cases.append(TestCase(
        id="PALIN_RACECAR",
        category=ReasoningCategory.ALGORITHM_PALINDROME,
        title="Kiểm tra đối xứng từ đơn 'racecar'",
        prompt="Chuỗi ký tự 'racecar' có phải là chuỗi đối xứng (palindrome) không? Trả lời rõ Có hoặc Không và giải thích ngắn.",
        expected_value=True,
        verifier_type="boolean",
    ))

    cases.append(TestCase(
        id="PALIN_ANTIGRAVITY",
        category=ReasoningCategory.ALGORITHM_PALINDROME,
        title="Kiểm tra không đối xứng 'antigravity'",
        prompt="Chuỗi ký tự 'antigravity' có phải là chuỗi đối xứng (palindrome) không? Trả lời rõ Có hoặc Không.",
        expected_value=False,
        verifier_type="boolean",
    ))

    cases.append(TestCase(
        id="PALIN_PANAMA_PHRASE",
        category=ReasoningCategory.ALGORITHM_PALINDROME,
        title="Kiểm tra palindrome câu dài 'A man, a plan, a canal: Panama'",
        prompt="Khi bỏ qua dấu câu, khoảng trắng và không phân biệt chữ hoa chữ thường, chuỗi 'A man, a plan, a canal: Panama' có phải là palindrome không? Trả lời Có hoặc Không.",
        expected_value=True,
        verifier_type="boolean",
    ))

    cases.append(TestCase(
        id="PALIN_ABCDCBA_MIDDLE",
        category=ReasoningCategory.ALGORITHM_PALINDROME,
        title="Xóa ký tự giữa của chuỗi đối xứng lẻ 'abcdcba'",
        prompt="Cho chuỗi đối xứng 'abcdcba'. Nếu ta xóa đi ký tự chính giữa là 'd', chuỗi thu được 'abccba' có còn là chuỗi palindrome không? Trả lời rõ Có hoặc Không.",
        expected_value=True,
        verifier_type="boolean",
    ))

    cases.append(TestCase(
        id="PALIN_TWO_POINTER_BIG_O",
        category=ReasoningCategory.ALGORITHM_PALINDROME,
        title="Độ phức tạp thuật toán Two Pointers kiểm tra Palindrome",
        prompt="Thuật toán sử dụng hai con trỏ duyệt từ hai đầu chuỗi để kiểm tra palindrome cho chuỗi độ dài N có độ phức tạp thời gian Big-O là bao nhiêu? Hãy nêu rõ O(n), O(n^2) hay O(log n).",
        expected_value="O(n)",
        verifier_type="big_o",
    ))

    return cases


# ==============================================================================
# BENCHMARK RUNNER & MOCK ENGINE
# ==============================================================================

class ReasoningEvaluator:
    def __init__(
        self,
        host: str = DEFAULT_OLLAMA_HOST,
        model: str = DEFAULT_MODEL,
        backend: str = "ollama",
        timeout: float = 120.0,
        temperature: float = 0.0,
        mock_mode: bool = False,
        simulate_flawed: bool = False,
        verbose: bool = False,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.backend = backend
        self.timeout = timeout
        self.temperature = temperature
        self.mock_mode = mock_mode
        self.simulate_flawed = simulate_flawed
        self.verbose = verbose

    def _query_ollama(self, prompt: str) -> Tuple[str, float]:
        """Queries Ollama chat API."""
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là trợ lý AI suy luận logic thông minh và chính xác. Khi nhận bài toán suy luận, hãy suy nghĩ cẩn thận trong thẻ <think>...</think> trước khi đưa ra câu trả lời cuối cùng."
                },
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            }
        }
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data.get("message", {}).get("content", "")
                latency = (time.perf_counter() - start) * 1000.0
                return content, latency
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000.0
            return f"[ERROR: {type(e).__name__}: {e}]", latency

    def _query_aioffice(self, prompt: str) -> Tuple[str, float]:
        """Queries AI Office backend (e.g. port 8765) with fallback to Ollama."""
        url = f"{self.host}/api/chat"
        payload = {
            "prompt": prompt,
            "model": self.model,
            "temperature": self.temperature,
        }
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data.get("response") or data.get("content") or data.get("message", "")
                    return content, (time.perf_counter() - start) * 1000.0
        except Exception:
            pass
        # Fallback to Ollama if AI Office endpoint fails
        return self._query_ollama(prompt)

    def _generate_mock_response(self, test_case: TestCase, simulate_flawed: bool = False) -> Tuple[str, float]:
        """Generates realistic mock responses for testing and validation."""
        simulated_latency = 120.0  # ms

        # If simulate_flawed is requested, introduce linear fallacy and common LLM mistakes
        if simulate_flawed:
            if test_case.id == "EXP_DUCKWEED_02_CLUSTERS":
                return (
                    "Theo tính toán tỉ lệ nghịch thông thường, nếu 1 cụm bèo cần 30 ngày để đầy hồ "
                    "thì 2 cụm bèo sẽ làm việc nhanh gấp đôi, do đó thời gian là 30 chia cho 2 = 15 ngày.\n"
                    "Kết luận: Cần 15 ngày để bèo phủ kín hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_04_CLUSTERS":
                return (
                    "Hồ có 4 cụm bèo, nở nhanh gấp 4 lần. Vậy số ngày cần là 30 / 4 = 7.5 ngày.\n"
                    "Đáp án: 7.5 ngày.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_STRAWBERRY_EN_R":
                return (
                    "The word strawberry breaks into 'straw' and 'berry'. "
                    "In 'berry' there are two 'r's. So letter 'r' appears 2 times.",
                    simulated_latency
                )

        if test_case.category == ReasoningCategory.EXPONENTIAL_DUCKWEED:
            # Simulate high-level reasoning with <think>
            if test_case.id == "EXP_DUCKWEED_01_BASE":
                return (
                    "<think>\n"
                    "Đề bài cho biết 1 cụm hoa bèo ban đầu, sau mỗi ngày tăng gấp đôi.\n"
                    "Sau 30 ngày thì bèo phủ kín mặt hồ.\n"
                    "Hỏi nếu ban đầu có 1 cụm thì sau bao nhiêu ngày?\n"
                    "Rõ ràng đây chính là điều kiện gốc của bài toán, do đó số ngày vẫn là 30 ngày.\n"
                    "</think>\n\n"
                    "Kết luận: Sau đúng 30 ngày thì bèo phủ kín hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_02_CLUSTERS":
                return (
                    "<think>\n"
                    "Phân tích bài toán hoa bèo nhân đôi:\n"
                    "- 1 cụm bèo: Ngày 0 có 1 cụm. Ngày 1 có 2 cụm. Ngày 30 có 2^30 cụm (kín hồ).\n"
                    "- Nếu ban đầu có 2 cụm bèo, tức là tương đương với trạng thái của hồ vào ngày thứ 1 trong kịch bản ban đầu!\n"
                    "- Do đó, từ ngày thứ 1 đến ngày thứ 30 cần 30 - 1 = 29 ngày nữa.\n"
                    "- Lưu ý bẫy tư duy: Không được lấy 30 chia cho 2 = 15 ngày vì sự phát triển là hàm mũ nhân đôi, không phải tuyến tính.\n"
                    "</think>\n\n"
                    "Đáp án chính xác: Sau 29 ngày bèo sẽ phủ kín hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_04_CLUSTERS":
                return (
                    "<think>\n"
                    "4 cụm bèo ban đầu = 2^2 cụm, tương ứng với trạng thái của ngày thứ 2 trong quá trình nở từ 1 cụm.\n"
                    "Vậy số ngày cần để đầy hồ là 30 - 2 = 28 ngày.\n"
                    "</think>\n\n"
                    "Kết luận: Bèo sẽ phủ kín hồ sau 28 ngày.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_08_CLUSTERS":
                return (
                    "<think>\n"
                    "8 cụm bèo ban đầu = 2^3 cụm, tương ứng trạng thái ngày thứ 3.\n"
                    "Số ngày cần là: 30 - 3 = 27 ngày.\n"
                    "</think>\n\n"
                    "Kết luận: Cần 27 ngày để bèo phủ kín toàn bộ hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_16_CLUSTERS":
                return (
                    "<think>\n"
                    "16 cụm bèo ban đầu = 2^4 cụm, tương đương ngày 4.\n"
                    "Số ngày cần để kín hồ là 30 - 4 = 26 ngày.\n"
                    "</think>\n\n"
                    "Kết luận: Sau 26 ngày bèo sẽ phủ kín hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_HALF_LAKE":
                return (
                    "<think>\n"
                    "Vì số lượng bèo nhân đôi mỗi ngày, nên ngày hôm trước luôn bằng một nửa ngày hôm sau.\n"
                    "Ngày thứ 30 phủ kín hồ (100%), vậy ngày thứ 29 sẽ phủ kín 1/2 hồ.\n"
                    "</think>\n\n"
                    "Đáp án: Sau 29 ngày bèo sẽ phủ kín một nửa hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_QUARTER_LAKE":
                return (
                    "<think>\n"
                    "Ngày 30: đầy hồ (1)\n"
                    "Ngày 29: 1/2 hồ\n"
                    "Ngày 28: 1/4 hồ\n"
                    "</think>\n\n"
                    "Đáp án: Sau 28 ngày bèo sẽ phủ kín 1/4 diện tích hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_48DAYS_2CLUSTERS":
                return (
                    "<think>\n"
                    "1 bông cần 48 ngày. 2 bông ban đầu = 2^1 bông = trạng thái ngày 1.\n"
                    "Vậy cần 48 - 1 = 47 ngày.\n"
                    "</think>\n\n"
                    "Kết luận: Mất 47 ngày để phủ kín hồ.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_48DAYS_4CLUSTERS":
                return (
                    "<think>\n"
                    "1 cây cần 48 ngày. 4 cây = 2^2 cây = trạng thái ngày thứ 2.\n"
                    "Số ngày cần là 48 - 2 = 46 ngày.\n"
                    "</think>\n\n"
                    "Kết luận: Cần 46 ngày.",
                    simulated_latency
                )
            elif test_case.id == "EXP_DUCKWEED_ENGLISH_48DAYS":
                return (
                    "<think>\n"
                    "Doubling process: 1 patch takes 48 days. Starting with 2 patches is equivalent to Day 1.\n"
                    "Total days needed = 48 - 1 = 47 days.\n"
                    "</think>\n\n"
                    "Final Answer: It would take 47 days.",
                    simulated_latency
                )

        elif test_case.category == ReasoningCategory.LOGIC_KNIGHT_KNAVE:
            if test_case.id == "LOGIC_KNAVE_BOTH_LIARS":
                return (
                    "<think>\n"
                    "Giả sử A là Hiệp sĩ (nói thật):\n"
                    "Thì câu nói 'Cả hai chúng tôi đều là kẻ nói dối' phải đúng, nghĩa là A cũng là kẻ nói dối -> mâu thuẫn.\n"
                    "Do đó A chắc chắn là Kẻ nói dối.\n"
                    "Vì A là kẻ nói dối nên câu nói 'Cả hai chúng tôi đều là kẻ nói dối' là sai.\n"
                    "Điều này có nghĩa là ít nhất một người không phải kẻ nói dối. Vì A đã là kẻ nói dối, nên B phải là Hiệp sĩ (người nói thật).\n"
                    "</think>\n\n"
                    "Kết luận: A là kẻ nói dối, B là người nói thật (hiệp sĩ).",
                    simulated_latency
                )
            elif test_case.id == "LOGIC_KNIGHT_DISJUNCTION":
                return (
                    "<think>\n"
                    "A nói: 'Tôi là kẻ gian lận hoặc B là hiệp sĩ' (Mệnh đề P OR Q).\n"
                    "Giả sử A là kẻ gian lận (nói dối): thì toàn bộ mệnh đề phải sai, tức là A không phải kẻ gian lận (mâu thuẫn!).\n"
                    "Vậy A phải là Hiệp sĩ (nói thật).\n"
                    "Vì A là hiệp sĩ, mệnh đề phải đúng. Vì A không phải kẻ gian lận nên vế thứ hai 'B là hiệp sĩ' phải đúng.\n"
                    "Do đó B cũng là hiệp sĩ.\n"
                    "</think>\n\n"
                    "Kết luận: Cả A là hiệp sĩ và B là hiệp sĩ (cả hai đều nói thật).",
                    simulated_latency
                )
            elif test_case.id == "LOGIC_CROSSROADS_QUESTION":
                return (
                    "<think>\n"
                    "Đây là câu đố kinh điển về 2 người lính (1 nói thật, 1 nói dối).\n"
                    "Ta cần tạo ra một hàm phủ định kép (True x False = False; False x True = False).\n"
                    "Hỏi 1 người xem người kia sẽ chỉ đường nào.\n"
                    "</think>\n\n"
                    "Bạn nên hỏi: 'Nếu tôi hỏi người kia con đường nào vào làng, người đó sẽ chỉ con đường nào?'. Sau đó đi theo con đường ngược lại.",
                    simulated_latency
                )
            elif test_case.id == "LOGIC_THREE_PERSON_CHAIN":
                return (
                    "<think>\n"
                    "A: 'B nói dối', B: 'C nói dối', C: 'A và B đều nói dối'.\n"
                    "Nếu C nói thật -> A dối và B dối. Nhưng nếu B dối thì 'C nói dối' là sai -> C nói thật (hợp lý). Tuy nhiên nếu A dối thì 'B nói dối' là sai -> B nói thật -> mâu thuẫn với việc B dối!\n"
                    "Vậy C phải là kẻ nói dối.\n"
                    "Vì C nói dối nên phát biểu của B ('C nói dối') là ĐÚNG -> B là người nói thật.\n"
                    "Vì B nói thật nên phát biểu của A ('B nói dối') là SAI -> A là kẻ nói dối.\n"
                    "</think>\n\n"
                    "Kết luận: B nói thật, còn A là kẻ nói dối và C là kẻ nói dối.",
                    simulated_latency
                )
            elif test_case.id == "LOGIC_PARADOX_SELF_CLAIM":
                return (
                    "<think>\n"
                    "Xét câu nói 'Tôi là kẻ nói dối':\n"
                    "- Nếu người nói là Hiệp sĩ: anh ta phải nói thật, nhưng nói mình là kẻ nói dối thì mâu thuẫn.\n"
                    "- Nếu người nói là Kẻ nói dối: anh ta phải nói dối, nhưng nếu anh ta nói mình là kẻ nói dối thì anh ta đang nói thật -> mâu thuẫn.\n"
                    "</think>\n\n"
                    "Kết luận: Không thể có ai trên đảo nói câu đó vì đây là một nghịch lý logic hoàn toàn bất khả thi.",
                    simulated_latency
                )

        elif test_case.category == ReasoningCategory.CHAR_COUNTING_STRAWBERRY:
            if test_case.id in ["CHAR_STRAWBERRY_EN_R", "CHAR_STRAWBERRY_VN_R"]:
                return (
                    "<think>\n"
                    "Tách từng chữ cái của từ 'strawberry':\n"
                    "1: s\n"
                    "2: t\n"
                    "3: r (chữ r thứ nhất)\n"
                    "4: a\n"
                    "5: w\n"
                    "6: b\n"
                    "7: e\n"
                    "8: r (chữ r thứ hai)\n"
                    "9: r (chữ r thứ ba)\n"
                    "10: y\n"
                    "Tổng cộng chữ 'r' xuất hiện đúng 3 lần.\n"
                    "</think>\n\n"
                    "Kết luận: Chữ cái 'r' xuất hiện 3 lần trong từ 'strawberry'.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_BLUEBERRY_EN_R":
                return (
                    "<think>\n"
                    "b-l-u-e-b-e-r-r-y: 2 chữ 'r' ở vị trí 7 và 8.\n"
                    "</think>\n\n"
                    "The letter 'r' appears 2 times in blueberry.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_APPLE_VN_P":
                return (
                    "<think>\n"
                    "a - p - p - l - e: có 2 chữ 'p'.\n"
                    "</think>\n\n"
                    "Trong từ 'apple' có 2 chữ cái 'p'.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_MISSISSIPPI_EN_S":
                return (
                    "<think>\n"
                    "M - i - s - s - i - s - s - i - p - p - i: có 4 chữ 's'.\n"
                    "</think>\n\n"
                    "The letter 's' appears 4 times in Mississippi.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_NGHIENG_VN_N":
                return (
                    "<think>\n"
                    "Tách chữ 'nghiêng':\n"
                    "n (1) - g - h - i - ê - n (2) - g.\n"
                    "Có đúng 2 chữ cái 'n'.\n"
                    "</think>\n\n"
                    "Chữ 'n' xuất hiện 2 lần trong từ 'nghiêng'.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_BUOM_BUOM_VN_U":
                return (
                    "<think>\n"
                    "'bươm bướm':\n"
                    "- bươm: b - ư(1) - ơ - m\n"
                    "- bướm: b - ư(2) - ớ - m\n"
                    "Tổng cộng 2 chữ 'ư'.\n"
                    "</think>\n\n"
                    "Chữ 'ư' xuất hiện 2 lần trong cụm từ 'bươm bướm'.",
                    simulated_latency
                )
            elif test_case.id == "CHAR_NGHIEN_CUU_VN_N":
                return (
                    "<think>\n"
                    "'nghiên cứu':\n"
                    "- nghiên: n(1) - g - h - i - ê - n(2)\n"
                    "- cứu: c - ứ - u (không có n)\n"
                    "Tổng số chữ 'n' là 2.\n"
                    "</think>\n\n"
                    "Chữ 'n' xuất hiện 2 lần trong 'nghiên cứu'.",
                    simulated_latency
                )

        elif test_case.category == ReasoningCategory.ALGORITHM_PALINDROME:
            if test_case.id == "PALIN_RACECAR":
                return (
                    "<think>\n"
                    "racecar đảo ngược lại vẫn là racecar. r-a-c-e-c-a-r.\n"
                    "</think>\n\n"
                    "Có, chuỗi 'racecar' chính là một palindrome.",
                    simulated_latency
                )
            elif test_case.id == "PALIN_ANTIGRAVITY":
                return (
                    "<think>\n"
                    "antigravity đảo ngược là ytivargitna, khác hoàn toàn.\n"
                    "</think>\n\n"
                    "Không, chuỗi 'antigravity' không phải là palindrome.",
                    simulated_latency
                )
            elif test_case.id == "PALIN_PANAMA_PHRASE":
                return (
                    "<think>\n"
                    "Chuẩn hóa: 'amanaplanacanalpanama'.\n"
                    "Đảo ngược: 'amanaplanacanalpanama'. Trùng khớp.\n"
                    "</think>\n\n"
                    "Có, chuỗi sau khi chuẩn hóa là một palindrome hoàn chỉnh.",
                    simulated_latency
                )
            elif test_case.id == "PALIN_ABCDCBA_MIDDLE":
                return (
                    "<think>\n"
                    "abcdcba bỏ 'd' còn lại 'abccba'.\n"
                    "abccba đảo ngược là abccba.\n"
                    "</think>\n\n"
                    "Có, chuỗi 'abccba' vẫn là palindrome.",
                    simulated_latency
                )
            elif test_case.id == "PALIN_TWO_POINTER_BIG_O":
                return (
                    "<think>\n"
                    "Hai con trỏ left=0, right=n-1 di chuyển về giữa. Mỗi bước dịch 1 vị trí, duyệt tối đa N/2 lần so sánh.\n"
                    "Độ phức tạp thời gian là O(N).\n"
                    "</think>\n\n"
                    "Độ phức tạp thời gian là O(n).",
                    simulated_latency
                )

        return "<think>Suy luận cơ bản</think>\nKết luận: Không xác định", simulated_latency

    def run_single_test(self, test_case: TestCase) -> TestResult:
        """Executes a single test case against the model or mock engine."""
        if self.mock_mode:
            raw_response, latency_ms = self._generate_mock_response(test_case, self.simulate_flawed)
        else:
            if self.backend == "aioffice":
                raw_response, latency_ms = self._query_aioffice(test_case.prompt)
            else:
                raw_response, latency_ms = self._query_ollama(test_case.prompt)

        parsed = parse_cot_response(raw_response)

        # Verification step
        if test_case.custom_verifier:
            is_correct, extracted, is_fallacy, notes = test_case.custom_verifier(parsed, test_case)
        elif test_case.verifier_type == "number":
            is_correct, extracted, is_fallacy, notes = verify_number(parsed, test_case)
        elif test_case.verifier_type == "boolean":
            is_correct, extracted, is_fallacy, notes = verify_boolean(parsed, test_case)
        elif test_case.verifier_type == "big_o":
            is_correct, extracted, is_fallacy, notes = verify_big_o(parsed, test_case)
        elif test_case.verifier_type == "logic_roles":
            is_correct, extracted, is_fallacy, notes = verify_logic_roles(parsed, test_case)
        else:
            is_correct, extracted, is_fallacy, notes = False, "Unknown", False, "No verifier"

        # Determine status
        if is_correct:
            status = "PASS"
        elif is_fallacy:
            status = "LINEAR_FALLACY"
        elif "ERROR" in raw_response:
            status = "ERROR"
        else:
            status = "FAIL"

        return TestResult(
            test_case=test_case,
            parsed_response=parsed,
            is_correct=is_correct,
            linear_fallacy_detected=is_fallacy,
            extracted_answer=extracted,
            latency_ms=latency_ms,
            status=status,
            notes=notes,
        )


# ==============================================================================
# REPORT GENERATION (JSON & MARKDOWN)
# ==============================================================================

def generate_summary(results: List[TestResult], model: str, host: str, backend: str) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.is_correct)
    linear_fallacies = sum(1 for r in results if r.linear_fallacy_detected)
    with_cot = sum(1 for r in results if r.parsed_response.has_think_tag)

    total_words = sum(r.parsed_response.think_word_count for r in results)
    avg_words = total_words / max(total, 1)

    total_latency = sum(r.latency_ms for r in results)
    avg_latency = total_latency / max(total, 1)

    # Category breakdowns
    categories: Dict[str, Dict[str, Any]] = {}
    for cat in ReasoningCategory:
        cat_results = [r for r in results if r.test_case.category == cat]
        c_total = len(cat_results)
        if c_total == 0:
            continue
        c_pass = sum(1 for r in cat_results if r.is_correct)
        c_fallacies = sum(1 for r in cat_results if r.linear_fallacy_detected)
        c_cot = sum(1 for r in cat_results if r.parsed_response.has_think_tag)
        categories[cat.value] = {
            "total": c_total,
            "passed": c_pass,
            "accuracy_pct": round((c_pass / c_total) * 100.0, 1),
            "linear_fallacies": c_fallacies,
            "cot_adoption_pct": round((c_cot / c_total) * 100.0, 1),
            "avg_latency_ms": round(sum(r.latency_ms for r in cat_results) / c_total, 1),
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "host": host,
        "backend": backend,
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy_pct": round((passed / max(total, 1)) * 100.0, 1),
        "linear_fallacies_count": linear_fallacies,
        "linear_fallacy_rate_pct": round((linear_fallacies / max(total, 1)) * 100.0, 1),
        "cot_adoption_rate_pct": round((with_cot / max(total, 1)) * 100.0, 1),
        "avg_think_words": round(avg_words, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "categories": categories,
    }


def export_json_report(summary: Dict[str, Any], results: List[TestResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    serialized_results = []
    for r in results:
        serialized_results.append({
            "id": r.test_case.id,
            "category": r.test_case.category.value,
            "title": r.test_case.title,
            "prompt": r.test_case.prompt,
            "expected_value": str(r.test_case.expected_value),
            "status": r.status,
            "is_correct": r.is_correct,
            "linear_fallacy_detected": r.linear_fallacy_detected,
            "extracted_answer": r.extracted_answer,
            "latency_ms": round(r.latency_ms, 2),
            "has_think_tag": r.parsed_response.has_think_tag,
            "think_word_count": r.parsed_response.think_word_count,
            "think_text": r.parsed_response.think_text,
            "answer_text": r.parsed_response.answer_text,
            "notes": r.notes,
        })

    payload = {
        "summary": summary,
        "details": serialized_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def export_markdown_report(summary: Dict[str, Any], results: List[TestResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# BÁO CÁO ĐÁNH GIÁ NĂNG LỰC SUY LUẬN LOGIC & BẪY TƯ DUY (REASONING BENCHMARK)")
    lines.append("")
    lines.append(f"> **Thời gian đánh giá**: `{summary['timestamp']}`  ")
    lines.append(f"> **Mô hình kiểm định**: `{summary['model']}` | **Backend**: `{summary['backend']}` (`{summary['host']}`)  ")
    lines.append("")

    # Executive KPI Summary
    lines.append("## 1. TỔNG QUAN CHỈ SỐ (EXECUTIVE SUMMARY)")
    lines.append("")
    lines.append("| Chỉ số kiểm định | Giá trị đạt được | Đánh giá tiêu chuẩn |")
    lines.append("| :--- | :---: | :--- |")
    acc = summary['accuracy_pct']
    acc_badge = "🟢 Đạt xuất sắc" if acc >= 85 else ("🟡 Đạt yêu cầu" if acc >= 70 else "🔴 Cần cải thiện")
    lines.append(f"| **Độ chính xác tổng thể (Accuracy)** | **{acc}%** ({summary['passed']}/{summary['total_tests']}) | {acc_badge} |")
    
    fallacy_cnt = summary['linear_fallacies_count']
    fallacy_badge = "🟢 Không phát hiện bẫy" if fallacy_cnt == 0 else f"⚠️ Phát hiện {fallacy_cnt} ca dính bẫy tuyến tính"
    lines.append(f"| **Lỗi tư duy tuyến tính (Linear Fallacy)** | **{summary['linear_fallacy_rate_pct']}%** ({fallacy_cnt} ca) | {fallacy_badge} |")
    
    lines.append(f"| **Tỷ lệ sử dụng thẻ CoT `<think>`** | **{summary['cot_adoption_rate_pct']}%** | {'🟢 Tốt' if summary['cot_adoption_rate_pct'] >= 80 else '🟡 Trung bình'} |")
    lines.append(f"| **Độ sâu suy luận trung bình** | **{summary['avg_think_words']} từ / câu** | CoT Reasoning Trace |")
    lines.append(f"| **Độ trễ phản hồi trung bình** | **{summary['avg_latency_ms']} ms** | API Response Latency |")
    lines.append("")

    # Category Breakdown Table
    lines.append("## 2. PHÂN TÍCH CHI TIẾT THEO TỪNG NHÓM BÀI TOÁN")
    lines.append("")
    lines.append("| Nhóm bài toán (Category) | Số lượng test | Đạt (Pass) | Chính xác (%) | Lỗi tuyến tính | CoT `<think>` (%) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    cat_display_names = {
        ReasoningCategory.EXPONENTIAL_DUCKWEED.value: "🌸 Hàm mũ hoa bèo (1,2,4,8,16 cụm)",
        ReasoningCategory.LOGIC_KNIGHT_KNAVE.value: "⚔️ Logic Hiệp sĩ & Kẻ nói dối",
        ReasoningCategory.CHAR_COUNTING_STRAWBERRY.value: "🍓 Đếm ký tự Strawberry & Tokenizer",
        ReasoningCategory.ALGORITHM_PALINDROME.value: "🔄 Thuật toán Palindrome & Two Pointers",
    }

    for cat_key, cat_data in summary["categories"].items():
        name = cat_display_names.get(cat_key, cat_key)
        lines.append(
            f"| {name} | {cat_data['total']} | {cat_data['passed']} | **{cat_data['accuracy_pct']}%** | "
            f"{cat_data['linear_fallacies']} | {cat_data['cot_adoption_pct']}% |"
        )
    lines.append("")

    # Detailed Fallacy Analysis Section
    lines.append("## 3. PHÂN TÍCH CHUYÊN SÂU LỖI TƯ DUY TUYẾN TÍNH (LINEAR FALLACY AUDIT)")
    lines.append("")
    if fallacy_cnt == 0:
        lines.append("✅ **Hoàn hảo**: Mô hình đã phân biệt xuất sắc giữa quy luật hàm mũ nhân đôi $2^t$ và quy luật tỉ lệ nghịch tuyến tính $T / N$. Không có trường hợp nào bị rơi vào bẫy chia số ngày cho số lượng cụm bèo ban đầu.")
    else:
        lines.append("⚠️ **Cảnh báo bẫy tư duy**: Mô hình đã mắc phải lỗi tư duy trực giác (Intuitive Linear Heuristic) trong các bài toán hàm mũ:")
        lines.append("- Triệu chứng: Mô hình lấy 30 ngày chia cho 2 = 15 ngày, hoặc 30 chia cho 4 = 7.5 ngày.")
        lines.append("- Nguyên nhân: Sự thiếu hụt dữ liệu huấn luyện CoT có giám sát (SFT CoT) cho các dạng bài toán tăng trưởng mũ.")
        lines.append("- Khuyến nghị: Sử dụng tập dữ liệu `data/training/reasoning_cot_train.jsonl` để fine-tune LoRA cho mô hình.")
    lines.append("")

    # Detailed Test Case Results Table
    lines.append("## 4. BẢNG KẾT QUẢ TỪNG BÀI TEST CHI TIẾT")
    lines.append("")
    lines.append("| ID | Tiêu đề bài test | Kết quả | Giá trị kỳ vọng | Mô hình trả lời | Thẻ `<think>` | Ghi chú |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")

    for r in results:
        status_icon = "✅ PASS" if r.is_correct else ("⚠️ FALLACY" if r.linear_fallacy_detected else "❌ FAIL")
        think_icon = "Có" if r.parsed_response.has_think_tag else "Không"
        lines.append(
            f"| `{r.test_case.id}` | {r.test_case.title} | **{status_icon}** | `{r.test_case.expected_value}` | "
            f"`{r.extracted_answer}` | {think_icon} | {r.notes} |"
        )
    lines.append("")

    # Detailed Reasoning Traces Excerpts
    lines.append("## 5. TRÍCH XUẤT CO-THINK TRACE MẪU (SELECTED REASONING TRACES)")
    lines.append("")
    sample_tests = [r for r in results if r.parsed_response.has_think_tag][:4]
    if not sample_tests:
        sample_tests = results[:4]

    for idx, r in enumerate(sample_tests, 1):
        lines.append(f"### 5.{idx}. [{r.test_case.id}] {r.test_case.title}")
        lines.append(f"**Câu hỏi**: *{r.test_case.prompt}*")
        lines.append("")
        if r.parsed_response.think_text:
            lines.append("<details>")
            lines.append("<summary><b>Xem chuỗi suy luận nội tâm &lt;think&gt; (Click để mở)</b></summary>")
            lines.append("")
            lines.append("```text")
            lines.append(r.parsed_response.think_text)
            lines.append("```")
            lines.append("</details>")
            lines.append("")
        lines.append(f"**Kết luận mô hình xuất ra**:")
        lines.append(f"> {r.parsed_response.answer_text.strip() or r.extracted_answer}")
        lines.append("")
        lines.append(f"- **Đánh giá**: `{r.status}` | Trích xuất: `{r.extracted_answer}` | Độ trễ: `{round(r.latency_ms, 1)}ms`")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="AI Office Reasoning Benchmark Runner")
    parser.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help="Ollama API host URL")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name in Ollama")
    parser.add_argument("--backend", choices=["ollama", "aioffice"], default="ollama", help="Backend engine to test")
    parser.add_argument("--category", choices=["all", "duckweed", "logic", "strawberry", "palindrome"], default="all", help="Filter by category")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test cases")
    parser.add_argument("--timeout", type=float, default=120.0, help="Request timeout in seconds")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    parser.add_argument("--mock", action="store_true", help="Run with simulated mock responses for instant verification")
    parser.add_argument("--simulate-flawed", action="store_true", help="Simulate flawed reasoning (linear fallacy & counting error) to test detector")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUT, help="Path to save JSON benchmark output")
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUT, help="Path to save Markdown report")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output and reasoning traces")

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 AI OFFICE - AUTOMATED REASONING BENCHMARK SUITE")
    print(f"   Model: {args.model} | Backend: {args.backend} | Host: {args.host}")
    print(f"   Mode: {'MOCK SIMULATION (OFFLINE)' if args.mock else 'LIVE OLLAMA INFERENCE'}")
    print("=" * 80)

    # 1. Load test cases
    all_cases = build_benchmark_test_cases()
    
    if args.category != "all":
        cat_map = {
            "duckweed": ReasoningCategory.EXPONENTIAL_DUCKWEED,
            "logic": ReasoningCategory.LOGIC_KNIGHT_KNAVE,
            "strawberry": ReasoningCategory.CHAR_COUNTING_STRAWBERRY,
            "palindrome": ReasoningCategory.ALGORITHM_PALINDROME,
        }
        target_cat = cat_map[args.category]
        all_cases = [c for c in all_cases if c.category == target_cat]

    if args.limit:
        all_cases = all_cases[:args.limit]

    print(f"[*] Loaded {len(all_cases)} test cases to evaluate.")

    # 2. Initialize Evaluator
    evaluator = ReasoningEvaluator(
        host=args.host,
        model=args.model,
        backend=args.backend,
        timeout=args.timeout,
        temperature=args.temperature,
        mock_mode=args.mock,
        simulate_flawed=args.simulate_flawed,
        verbose=args.verbose,
    )

    # 3. Execute Benchmark
    results: List[TestResult] = []
    for idx, tc in enumerate(all_cases, 1):
        print(f"[{idx:02d}/{len(all_cases):02d}] Testing [{tc.id}] {tc.title} ... ", end="", flush=True)
        res = evaluator.run_single_test(tc)
        results.append(res)
        
        status_tag = f"[{res.status}]"
        if res.is_correct:
            print(f"\033[92m{status_tag}\033[0m ({res.extracted_answer}) in {res.latency_ms:.0f}ms")
        elif res.linear_fallacy_detected:
            print(f"\033[93m{status_tag}\033[0m (Trap hit: {res.extracted_answer}) in {res.latency_ms:.0f}ms")
        else:
            print(f"\033[91m{status_tag}\033[0m (Got: {res.extracted_answer}, Exp: {tc.expected_value}) in {res.latency_ms:.0f}ms")

        if args.verbose:
            print(f"   > Prompt: {tc.prompt}")
            if res.parsed_response.has_think_tag:
                print(f"   > Think words: {res.parsed_response.think_word_count}")
            print(f"   > Answer text: {res.parsed_response.answer_text[:120]}...")
            print("-" * 60)

    # 4. Generate Summaries & Reports
    summary = generate_summary(results, model=args.model, host=args.host, backend=args.backend)
    
    print("\n" + "=" * 80)
    print("📊 BENCHMARK SUMMARY RESULTS")
    print(f"   Total Tests Executed: {summary['total_tests']}")
    print(f"   Passed: {summary['passed']} ({summary['accuracy_pct']}%)")
    print(f"   Linear Fallacies: {summary['linear_fallacies_count']} ({summary['linear_fallacy_rate_pct']}%)")
    print(f"   CoT <think> Adoption: {summary['cot_adoption_rate_pct']}%")
    print(f"   Avg Latency: {summary['avg_latency_ms']} ms")
    print("=" * 80)

    # 5. Export Reports
    export_json_report(summary, results, args.json_output)
    print(f"[+] JSON report saved to: {args.json_output}")

    export_markdown_report(summary, results, args.md_output)
    print(f"[+] Markdown report saved to: {args.md_output}")

    return 0 if summary["accuracy_pct"] >= 70.0 else 1


if __name__ == "__main__":
    sys.exit(main())
