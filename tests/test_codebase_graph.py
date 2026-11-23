from __future__ import annotations

from pathlib import Path
from app.codebase_graph import CodebaseGraph


def test_codebase_graph_scan_and_query(tmp_path: Path):
    # Create dummy python files
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    file_a = app_dir / "service_a.py"
    file_a.write_text(
        '''
def helper_calc(val: int) -> int:
    """Calculate something."""
    return val * 2

class EngineA:
    def process(self):
        return helper_calc(10)
''',
        encoding="utf-8",
    )

    file_b = app_dir / "service_b.py"
    file_b.write_text(
        '''
from service_a import helper_calc

def main_flow():
    return helper_calc(42)
''',
        encoding="utf-8",
    )

    graph = CodebaseGraph(root_dir=tmp_path)
    data = graph.scan_directory(app_dir)

    assert len(data["modules"]) == 2
    assert len(data["classes"]) == 1
    assert len(data["functions"]) == 3

    # Query function
    res_fn = graph.query_symbol("helper_calc")
    assert len(res_fn["exact_matches"]) == 1
    assert res_fn["exact_matches"][0]["details"]["name"] == "helper_calc"
    # Callers should include EngineA.process and main_flow
    caller_names = [c["caller"] for c in res_fn["related_callers"]]
    assert "process" in caller_names or "main_flow" in caller_names

    # Save & Load test
    save_path = tmp_path / "graph.json"
    assert graph.save_graph(save_path) is True
    assert save_path.exists()

    loaded_graph = CodebaseGraph(root_dir=tmp_path)
    assert loaded_graph.load_graph(save_path) is True
    assert len(loaded_graph.functions) == 3
