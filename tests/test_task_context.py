from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from task_context import compose_task_evidence, select_web_pages  # noqa: E402


def test_web_evidence_is_not_cut_off_by_large_repository_context() -> None:
    project = "[PROJECT FILE: README.md]\\n" + ("project details " * 500)
    web = "[WEB SOURCE: https://developer.arm.com/spec]\\nARM_OFFICIAL_EVIDENCE " + ("PSCI CPU_ON_64 " * 100)
    result = compose_task_evidence("07/11/2026", project, web)
    assert len(result) <= 7_200
    assert "[PROJECT FILE: README.md]" in result
    assert "ARM_OFFICIAL_EVIDENCE" in result
    assert "PSCI CPU_ON_64" in result


def test_project_only_context_keeps_project_evidence() -> None:
    project = "[PROJECT FILE: README.md] kernel facts " * 500
    result = compose_task_evidence("07/11/2026", project, "")
    assert "PROJECT EVIDENCE" in result
    assert "[PROJECT FILE: README.md]" in result
    assert "WEB EVIDENCE: Browser was not used" in result


def test_web_only_context_keeps_web_evidence() -> None:
    web = "[WEB SOURCE: https://example.com] source facts " * 500
    result = compose_task_evidence("07/11/2026", "", web)
    assert "WEB SOURCE" in result
    assert "PROJECT EVIDENCE: No repository" in result


def test_primary_arm_and_apple_sources_are_selected_first() -> None:
    pages = [
        {"url": "https://blog.example.org/post", "http_status": 200, "text": "blog"},
        {"url": "https://support.arm.com/documentation/den0022/latest/", "http_status": 200, "text": "PSCI"},
        {"url": "https://github.com/apple-oss-distributions/xnu", "http_status": 200, "text": "XNU"},
        {"url": "https://unixnu.com/xnu/source-and-patches", "http_status": 200, "text": "patches"},
    ]
    selected = select_web_pages(pages, max_pages=3)
    assert "arm.com" in selected[0]["url"]
    assert "apple-oss-distributions/xnu" in selected[1]["url"]
    assert len(selected) == 3
