from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
import pytest
from app.fast_calc import evaluate_math_expression, classify_prompt_speed
from app.model_provider import ModelProviderManager


def test_large_digit_multiplication():
    # 12-digit multiplication as requested by user
    expr = "123456789012 * 987654321098"
    res = evaluate_math_expression(expr)
    assert res is not None
    # 123456789012 * 987654321098 = 121,932,631,136,585,886,175,176
    assert "121,932,631,136,585,886,175,176" in res


def test_large_digit_addition_and_division():
    expr = "(1000000000000 + 2000000000000) / 3"
    res = evaluate_math_expression(expr)
    assert res is not None
    assert "1,000,000,000,000" in res


def test_calculator_security_rejects_code_injection():
    malicious_inputs = [
        "__import__('os').system('calc')",
        "eval('1 + 1')",
        "open('/etc/passwd').read()",
        "import sys; sys.exit(0)",
        "x = 5; x + 2",
    ]
    for bad in malicious_inputs:
        assert evaluate_math_expression(bad) is None


def test_calculator_dos_protection():
    # Excessive exponent that could freeze CPU
    dos_expr = "9999 ** 999999"
    assert evaluate_math_expression(dos_expr) is None


def test_calculator_zero_division():
    zero_div = "123456789 / 0"
    assert evaluate_math_expression(zero_div) is None


def test_classify_prompt_speed_greetings():
    decision = classify_prompt_speed("Xin chào bạn nhé")
    assert decision.is_simple_query is True
    assert decision.recommended_think is False
    assert decision.is_math is False


def test_classify_prompt_speed_math_query():
    decision = classify_prompt_speed("Tính giúp: 500000000000 * 2")
    assert decision.is_math is True
    assert decision.math_result is not None
    assert "1,000,000,000,000" in decision.math_result
    assert decision.recommended_think is False


def test_classify_prompt_speed_complex_code():
    decision = classify_prompt_speed("Hãy viết một module Python refactor lại database SQLite trong AI-Office")
    assert decision.is_simple_query is False
    assert decision.recommended_think is True
    assert decision.is_math is False


@pytest.mark.asyncio
async def test_model_provider_chat_instant_math():
    manager = ModelProviderManager(db_getter=MagicMock(), semaphore=asyncio.Semaphore(1))
    # Math question should return directly without contacting Ollama
    res = await manager.chat([{"role": "user", "content": "123456789012 * 987654321098"}])
    assert "121,932,631,136,585,886,175,176" in res


def test_classify_prompt_speed_long_form_chapter():
    decision = classify_prompt_speed("Chương 1 viết khoảng 5000 chữ")
    assert decision.is_simple_query is False
    assert decision.recommended_num_predict >= 8192


def test_classify_prompt_speed_story_continuation():
    for prompt in ("Tùy em", "Sao ngắn ngủi vậy", "Viết tiếp đi"):
        decision = classify_prompt_speed(prompt)
        assert decision.is_simple_query is False
        assert decision.recommended_num_predict >= 4096


def test_local_options_anti_repetition():
    opts = ModelProviderManager._build_local_options(ctx_size=8192, num_predict=8192, temperature=0.25, json_mode=False)
    assert opts["repeat_penalty"] >= 1.15
    assert opts["repeat_last_n"] >= 256
    assert opts["temperature"] == 0.65
