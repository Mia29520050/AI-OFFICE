from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from task_qa import deterministic_task_qa, parse_qa_verdict  # noqa: E402


PROJECT_FILES = [
    {"path": "README.md"},
    {"path": "tools/xnu-a31/MT6765CPU.cpp"},
]
WEB_SOURCES = [
    {"url": "https://github.com/apple-oss-distributions/xnu", "title": "Apple XNU"},
    {"url": "https://developer.arm.com/documentation/den0022/latest", "title": "Arm PSCI"},
]
EVIDENCE = "Current task date: 07/11/2026. No historical date supplied."
CURRENT_DATE = "07/11/2026"


def qa(draft: str) -> list[str]:
    return deterministic_task_qa(
        draft,
        PROJECT_FILES,
        WEB_SOURCES,
        project_required=True,
        web_required=True,
        evidence_text=EVIDENCE,
        current_date=CURRENT_DATE,
    )


def test_valid_project_and_web_citations_pass() -> None:
    assert qa(
        "Ngày: 07/11/2026\n"
        "Fact [PROJECT: README.md]\n"
        "Fact [WEB: https://github.com/apple-oss-distributions/xnu]"
    ) == []


def test_missing_citations_fail_even_when_footer_would_contain_sources() -> None:
    findings = qa("The draft contains no citations.")
    assert any("Thiếu citation [PROJECT" in item for item in findings)
    assert any("Thiếu citation [WEB" in item for item in findings)


def test_unregistered_project_path_fails() -> None:
    assert any("fake.md" in item for item in qa(
        "[PROJECT: fake.md] [WEB: https://github.com/apple-oss-distributions/xnu]"
    ))


def test_unread_web_url_fails() -> None:
    assert any("example.org" in item for item in qa(
        "[PROJECT: README.md] [WEB: https://example.org/fake]"
    ))


def test_partial_fabricated_date_fails() -> None:
    assert any("không ghi ngày đầy đủ" in item for item in qa(
        "Ngày: Thứ Bảy, 0\n[PROJECT: README.md] [WEB: https://github.com/apple-oss-distributions/xnu]"
    ))


def test_historical_date_without_evidence_fails() -> None:
    assert any("24/05/2024" in item for item in qa(
        "Ngày: 24/05/2024\n[PROJECT: README.md] [WEB: https://github.com/apple-oss-distributions/xnu]"
    ))


def test_evidence_supported_historical_date_is_allowed() -> None:
    result = deterministic_task_qa(
        "Ngày: 24/05/2024\n[PROJECT: README.md] [WEB: https://github.com/apple-oss-distributions/xnu]",
        PROJECT_FILES,
        WEB_SOURCES,
        project_required=True,
        web_required=True,
        evidence_text="The repository changelog was created on 24/05/2024.",
        current_date=CURRENT_DATE,
    )
    assert result == []


def test_qa_pass_is_explicit_first_line() -> None:
    assert parse_qa_verdict("PASS\nNo findings") == ("pass", [])


def test_qa_fail_is_explicit_first_line() -> None:
    verdict, findings = parse_qa_verdict("FAIL\nMissing evidence\nWrong citation")
    assert verdict == "fail"
    assert findings == ["Missing evidence", "Wrong citation"]


def test_qa_malformed_output_fails_closed() -> None:
    verdict, findings = parse_qa_verdict("The report looks good. PASS maybe.")
    assert verdict == "fail"
    assert findings


def test_project_citation_placeholder_fails() -> None:
    findings = qa("[PROJECT: path] [WEB: https://github.com/apple-oss-distributions/xnu]")
    assert any("placeholder citation project" in item for item in findings)


def test_web_citation_placeholder_fails() -> None:
    findings = qa("[PROJECT: README.md] [WEB: URL]")
    assert any("placeholder citation web" in item for item in findings)
