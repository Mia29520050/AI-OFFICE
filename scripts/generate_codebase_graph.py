from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.codebase_graph import CodebaseGraph, DEFAULT_GRAPH_PATH


def main() -> int:
    print("=== Generating Codebase Knowledge Graph (Graphify Style) ===")
    graph = CodebaseGraph(root_dir=ROOT_DIR)
    target_dir = ROOT_DIR / "app"
    data = graph.scan_directory(target_dir)

    module_count = len(data.get("modules", {}))
    class_count = len(data.get("classes", {}))
    function_count = len(data.get("functions", {}))

    print(f"[+] Scanned: {module_count} modules, {class_count} classes, {function_count} functions.")
    saved = graph.save_graph(DEFAULT_GRAPH_PATH)
    if saved:
        print(f"[+] Graph successfully saved to: {DEFAULT_GRAPH_PATH}")
        return 0
    else:
        print(f"[-] Failed to save graph to: {DEFAULT_GRAPH_PATH}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
