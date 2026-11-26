from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from typing import Any

# Binary operators mapping
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Unary operators mapping
SAFE_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Common conversational greetings that don't need deep reasoning
GREETING_PATTERNS = re.compile(
    r"^(?:xin\s+chào|chào\s+(?:bạn|anh|em|cậu|ad)|hello|hi|hey|alo|bạn\s+là\s+ai|khỏe\s+không|good\s+morning|good\s+evening)[\!\?\.\s]*$",
    re.IGNORECASE,
)

# Math question extraction regex
MATH_EXTRACT_REGEX = re.compile(
    r"^(?:tính|kết\s+quả|tính\s+giúp|bằng\s+bao\s+nhiêu|calculate|what\s+is|compute)?[:\s]*([0-9\s\+\-\*\/\(\)\.\,\^%]+)\??$",
    re.IGNORECASE,
)


@dataclass
class FastPathDecision:
    is_math: bool = False
    math_result: str | None = None
    is_simple_query: bool = False
    recommended_think: bool = True
    recommended_num_predict: int = 800


def _safe_eval_node(node: ast.AST) -> Any:
    """Recursively evaluate an AST node strictly restricted to basic arithmetic."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type}")

        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)

        # Protect against exponent DoS (e.g. 9999 ** 999999)
        if op_type is ast.Pow:
            if abs(right) > 1000:
                raise ValueError("Exponent too large (DoS protection)")

        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise ZeroDivisionError("Division by zero")

        return SAFE_OPERATORS[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_UNARY_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type}")
        operand = _safe_eval_node(node.operand)
        return SAFE_UNARY_OPERATORS[op_type](operand)

    raise ValueError(f"Disallowed AST expression node: {type(node)}")


def evaluate_math_expression(raw_expr: str) -> str | None:
    """Safely parse and evaluate arbitrary-precision arithmetic without using eval().

    Returns formatted result or None if not a valid math expression.
    """
    clean_expr = raw_expr.strip().rstrip("?").strip()
    if not clean_expr:
        return None

    # Replace visual symbols: ^ with **, × with *, ÷ with /
    normalized = (
        clean_expr.replace("^", "**")
        .replace("×", "*")
        .replace("÷", "/")
        .replace(",", "")
    )

    # Must contain at least one digit and an operator
    if not re.search(r"\d", normalized) or not re.search(r"[\+\-\*\/\%]", normalized):
        return None

    # Ensure no alphanumeric identifiers (e.g. letters or builtins)
    if re.search(r"[a-zA-Z_]", normalized):
        return None

    try:
        parsed = ast.parse(normalized, mode="eval")
        res = _safe_eval_node(parsed.body)
        if isinstance(res, float):
            # Format cleanly (avoid .0 if exact integer)
            if res.is_integer():
                formatted = f"{int(res):,}"
            else:
                formatted = f"{res:,.6f}".rstrip("0").rstrip(".")
        else:
            formatted = f"{res:,}"

        return f"Kết quả phép tính: `{clean_expr}` = **{formatted}**"
    except Exception:
        return None


def classify_prompt_speed(user_prompt: str) -> FastPathDecision:
    """Analyze incoming prompt to detect trivial greetings or instant math calculations.

    Bypasses heavy LLM reasoning when a direct or fast-path answer is optimal.
    """
    text = user_prompt.strip()

    # 1. Check for math arithmetic
    math_match = MATH_EXTRACT_REGEX.match(text)
    if math_match:
        expr_candidate = math_match.group(1).strip()
        math_ans = evaluate_math_expression(expr_candidate)
        if math_ans:
            return FastPathDecision(
                is_math=True,
                math_result=math_ans,
                is_simple_query=True,
                recommended_think=False,
                recommended_num_predict=64,
            )

    # Direct math without prefix
    direct_math = evaluate_math_expression(text)
    if direct_math:
        return FastPathDecision(
            is_math=True,
            math_result=direct_math,
            is_simple_query=True,
            recommended_think=False,
            recommended_num_predict=64,
        )

    # 2. Check for simple greetings
    if GREETING_PATTERNS.match(text):
        return FastPathDecision(
            is_math=False,
            math_result=None,
            is_simple_query=True,
            recommended_think=False,
            recommended_num_predict=128,
        )

    # 3. Long-form / creative writing detection (never throttle stories, chapters, or essays)
    long_form_keywords = (
        "chương", "truyện", "cốt truyện", "tiểu thuyết", "kịch bản", "mở rộng",
        "chi tiết", "viết tiếp", "viết dài", "kể tiếp", "bài viết", "luận văn",
        "tùy em", "ngắn ngủi", "bao nhiêu từ", "bao nhiêu chữ", "chữ", "từ",
    )
    text_lower = text.lower()
    target_match = re.search(r"(\d[\d\.,]*)\s*(?:chữ|từ|words?)", text_lower)
    if target_match:
        try:
            requested_words = int(target_match.group(1).replace(".", "").replace(",", ""))
        except ValueError:
            requested_words = 2000
        # Vietnamese averages ~2.2-2.5 tokens per syllable/word; allow ample room up to 12288 tokens.
        est_tokens = max(4096, min(int(requested_words * 2.5), 12288))
        return FastPathDecision(
            is_math=False,
            math_result=None,
            is_simple_query=False,
            recommended_think=True,
            recommended_num_predict=est_tokens,
        )

    if any(kw in text_lower for kw in long_form_keywords):
        return FastPathDecision(
            is_math=False,
            math_result=None,
            is_simple_query=False,
            recommended_think=True,
            recommended_num_predict=4096,
        )

    # 4. Short casual prompts (<= 10 words without technical or long-form keywords)
    words = text.split()
    technical_keywords = {
        "code", "viết", "lập trình", "hàm", "class", "def", "bug", "lỗi",
        "manga", "comfy", "diff", "test", "file", "database", "sql", "git",
        "tạo", "phân tích", "giải thích", "tóm tắt", "soạn", "dịch",
    }
    if len(words) <= 10 and not any(w.lower() in technical_keywords for w in words):
        return FastPathDecision(
            is_math=False,
            math_result=None,
            is_simple_query=True,
            recommended_think=False,
            recommended_num_predict=1024,
        )

    # Default: complex query requiring standard reasoning
    return FastPathDecision(
        is_math=False,
        math_result=None,
        is_simple_query=False,
        recommended_think=True,
        recommended_num_predict=4096,
    )
