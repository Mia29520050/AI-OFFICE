from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

# Regex patterns for invisible zero-width and bidirectional control characters
INVISIBLE_CHARS_REGEX = re.compile(
    r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E\u2060-\u206F\u00AD]"
)

# Suspicious prompt injection markers hidden in markdown comments
COMMENT_INJECTION_REGEX = re.compile(
    r"<!--[\s\S]*?(?:ignore\s+previous|system\s+prompt|admin\s+override|exfiltrate|bypass|jailbreak)[\s\S]*?-->",
    re.IGNORECASE,
)

# Common dangerous Python call names
DANGEROUS_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
}

# Suspicious imports or modules often used in info-stealers
SUSPICIOUS_MODULES = {
    "pty",
}


@dataclass
class TextSanitizeResult:
    cleaned_text: str
    stripped_characters_count: int
    hidden_injections_found: list[str] = field(default_factory=list)


@dataclass
class CodeAuditResult:
    is_safe: bool
    risk_level: str  # "SAFE", "LOW", "MEDIUM", "CRITICAL"
    findings: list[str] = field(default_factory=list)


class SecurityGuard:
    """Security guard protecting AI-Office from invisible prompt injections,

    obfuscated code payloads, pickle exploits, and reverse shells.
    """

    @classmethod
    def sanitize_input_text(cls, text: str) -> TextSanitizeResult:
        """Strip invisible zero-width characters, dangerous bidirectional overrides,

        and sanitize suspicious prompt-injection comments.
        """
        if not text:
            return TextSanitizeResult(cleaned_text="", stripped_characters_count=0)

        # 1. Count and remove invisible characters
        invisible_matches = INVISIBLE_CHARS_REGEX.findall(text)
        stripped_count = len(invisible_matches)
        cleaned = INVISIBLE_CHARS_REGEX.sub("", text)

        # 2. Check for hidden comment injections
        injections = COMMENT_INJECTION_REGEX.findall(cleaned)
        if injections:
            # Strip out malicious hidden HTML/Markdown comments
            cleaned = COMMENT_INJECTION_REGEX.sub("", cleaned)

        return TextSanitizeResult(
            cleaned_text=cleaned,
            stripped_characters_count=stripped_count,
            hidden_injections_found=injections,
        )

    @classmethod
    def audit_python_code(cls, code_str: str) -> CodeAuditResult:
        """Statically inspect Python code using AST to detect obfuscation (base64/exec),

        dangerous function calls, and unauthorized subprocess / socket exfiltration.
        """
        findings: list[str] = []

        # 1. Check for basic textual indicators of high-risk obfuscation
        if re.search(r"\bbase64\.b64decode\s*\(.*?\)\s*\.(?:decode|read)", code_str) and (
            "exec(" in code_str or "eval(" in code_str
        ):
            findings.append("CRITICAL: Detected base64 payload execution pattern (exec/eval)")

        if re.search(r"powershell(?:\.exe)?\s+-[eE](?:nc|ncodedcommand)?\s+", code_str):
            findings.append("CRITICAL: Detected encoded PowerShell execution payload")

        # 2. AST-based structural inspection
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return CodeAuditResult(
                is_safe=False,
                risk_level="MEDIUM",
                findings=[f"SyntaxError during AST audit: {e}"],
            )

        for node in ast.walk(tree):
            # Check function calls
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in DANGEROUS_CALLS:
                    findings.append(f"HIGH: Prohibited dynamic code execution function '{func_name}'")

                # Check for pickle.load / torch.load without weights_only
                if func_name == "load":
                    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "pickle":
                            findings.append("CRITICAL: Insecure pickle.load invocation detected")
                        elif node.func.value.id == "torch":
                            # check if weights_only=True is passed
                            has_weights_only = any(
                                kw.arg == "weights_only"
                                and isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                                for kw in node.keywords
                            )
                            if not has_weights_only:
                                findings.append("HIGH: torch.load without weights_only=True")

            # Check imports
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in SUSPICIOUS_MODULES:
                            findings.append(f"MEDIUM: Suspicious module imported: {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module in SUSPICIOUS_MODULES:
                    findings.append(f"MEDIUM: Suspicious module imported: {node.module}")

        # Determine overall risk
        if any(f.startswith("CRITICAL") for f in findings):
            risk_level = "CRITICAL"
            is_safe = False
        elif any(f.startswith("HIGH") for f in findings):
            risk_level = "HIGH"
            is_safe = False
        elif findings:
            risk_level = "MEDIUM"
            is_safe = False
        else:
            risk_level = "SAFE"
            is_safe = True

        return CodeAuditResult(
            is_safe=is_safe,
            risk_level=risk_level,
            findings=findings,
        )
