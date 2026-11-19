from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import research_tools  # noqa: E402
from research_tools import build_project_context, list_projects  # noqa: E402


def _with_temp_registry(callback):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proj = tmp_path / "sample-proj"
        (proj / "docs").mkdir(parents=True)
        (proj / "README.md").write_text("# Sample Project\nKernel bringup notes.\n", encoding="utf-8")
        (proj / "docs" / "porting-plan.md").write_text("Step 1: verify PSCI trampoline.\n", encoding="utf-8")
        reg_file = tmp_path / "registry.json"
        reg_file.write_text(json.dumps({
            "projects": [{
                "key": "sample-proj",
                "name": "Sample Project",
                "root": str(proj),
                "description": "Temp test fixture",
                "default": True,
            }]
        }), encoding="utf-8")
        orig = research_tools.REGISTRY
        research_tools.REGISTRY = reg_file
        try:
            return callback()
        finally:
            research_tools.REGISTRY = orig


def test_registered_project_reader_works_on_valid_root() -> None:
    def run():
        projects = list_projects()
        item = next(x for x in projects if x["key"] == "sample-proj")
        assert item["available"] is True
        assert Path(item["root"]).is_dir()
    _with_temp_registry(run)


def test_project_reader_returns_read_only_manifest_and_hashes() -> None:
    def run():
        result = build_project_context("sample-proj", "PSCI trampoline")
        paths = {item["path"] for item in result["files"]}
        assert result["read_only"] is True
        assert result["files_read"] >= 2
        assert "README.md" in paths
        assert "docs/porting-plan.md" in paths
        assert all(len(item["sha256"]) == 64 for item in result["files"])
    _with_temp_registry(run)


def test_unregistered_project_cannot_be_read() -> None:
    try:
        build_project_context("../", "README")
    except KeyError:
        return
    raise AssertionError("Unregistered project key unexpectedly resolved")


def test_context_is_bounded() -> None:
    def run():
        result = build_project_context("sample-proj", "PSCI CPU bringup")
        assert len(result["context"]) <= 9_200
    _with_temp_registry(run)
