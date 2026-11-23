from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH_PATH = ROOT_DIR / "data" / "codebase_graph.json"


@dataclass
class FunctionNode:
    name: str
    file: str
    line: int
    args: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    docstring: str = ""


@dataclass
class ClassNode:
    name: str
    file: str
    line: int
    methods: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    docstring: str = ""


@dataclass
class ModuleNode:
    path: str
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


class CodebaseGraph:
    """Deterministic Codebase Knowledge Graph inspired by Graphify.

    Parses the codebase AST on CPU, requiring 0 VRAM and 0 API cost.
    """

    def __init__(self, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir
        self.modules: dict[str, ModuleNode] = {}
        self.classes: dict[str, ClassNode] = {}
        self.functions: dict[str, FunctionNode] = {}

    def scan_directory(self, target_dir: Path | None = None) -> dict[str, Any]:
        """Scan Python files and construct structural knowledge graph."""
        scan_root = target_dir or (self.root_dir / "app")
        if not scan_root.exists():
            return {}

        self.modules.clear()
        self.classes.clear()
        self.functions.clear()

        for py_path in scan_root.rglob("*.py"):
            rel_path = py_path.relative_to(self.root_dir).as_posix()
            try:
                code_content = py_path.read_text(encoding="utf-8")
                tree = ast.parse(code_content, filename=rel_path)
            except Exception:
                continue

            mod_node = ModuleNode(path=rel_path)

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            mod_node.imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        mod_node.imports.append(node.module)

                elif isinstance(node, ast.ClassDef):
                    cls_name = f"{rel_path}:{node.name}"
                    bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                    methods: list[str] = []
                    for m in node.body:
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append(m.name)
                            # Also register class method in functions map for direct querying
                            method_key = f"{rel_path}:{node.name}.{m.name}"
                            m_args = [a.arg for a in m.args.args]
                            m_calls: list[str] = []
                            for sub in ast.walk(m):
                                if isinstance(sub, ast.Call):
                                    if isinstance(sub.func, ast.Name):
                                        m_calls.append(sub.func.id)
                                    elif isinstance(sub.func, ast.Attribute):
                                        m_calls.append(sub.func.attr)
                            m_doc = ast.get_docstring(m) or ""
                            self.functions[method_key] = FunctionNode(
                                name=f"{node.name}.{m.name}",
                                file=rel_path,
                                line=m.lineno,
                                args=m_args,
                                calls=list(set(m_calls)),
                                docstring=m_doc.strip().split("\n")[0] if m_doc else "",
                            )

                    doc = ast.get_docstring(node) or ""
                    self.classes[cls_name] = ClassNode(
                        name=node.name,
                        file=rel_path,
                        line=node.lineno,
                        methods=methods,
                        bases=bases,
                        docstring=doc.strip().split("\n")[0] if doc else "",
                    )
                    mod_node.classes.append(node.name)

                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn_name = f"{rel_path}:{node.name}"
                    args = [a.arg for a in node.args.args]
                    calls: list[str] = []
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call):
                            if isinstance(sub.func, ast.Name):
                                calls.append(sub.func.id)
                            elif isinstance(sub.func, ast.Attribute):
                                calls.append(sub.func.attr)

                    doc = ast.get_docstring(node) or ""
                    self.functions[fn_name] = FunctionNode(
                        name=node.name,
                        file=rel_path,
                        line=node.lineno,
                        args=args,
                        calls=list(set(calls)),
                        docstring=doc.strip().split("\n")[0] if doc else "",
                    )
                    mod_node.functions.append(node.name)

            self.modules[rel_path] = mod_node

        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": "1.0.0",
            "modules": {k: asdict(v) for k, v in self.modules.items()},
            "classes": {k: asdict(v) for k, v in self.classes.items()},
            "functions": {k: asdict(v) for k, v in self.functions.items()},
        }

    def save_graph(self, output_path: Path = DEFAULT_GRAPH_PATH) -> bool:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            data = self.to_dict()
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False

    def load_graph(self, input_path: Path = DEFAULT_GRAPH_PATH) -> bool:
        if not input_path.exists():
            return False
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
            self.modules = {k: ModuleNode(**v) for k, v in data.get("modules", {}).items()}
            self.classes = {k: ClassNode(**v) for k, v in data.get("classes", {}).items()}
            self.functions = {k: FunctionNode(**v) for k, v in data.get("functions", {}).items()}
            return True
        except Exception:
            return False

    def query_symbol(self, symbol_name: str) -> dict[str, Any]:
        """Look up functions, classes, or modules matching symbol_name."""
        results: dict[str, Any] = {"exact_matches": [], "related_callers": []}

        # Search classes
        for key, cls in self.classes.items():
            if symbol_name.lower() in cls.name.lower():
                results["exact_matches"].append({"type": "class", "id": key, "details": asdict(cls)})

        # Search functions
        for key, fn in self.functions.items():
            if symbol_name.lower() in fn.name.lower():
                results["exact_matches"].append({"type": "function", "id": key, "details": asdict(fn)})

        # Search callers
        for key, fn in self.functions.items():
            if symbol_name in fn.calls:
                results["related_callers"].append({"caller": fn.name, "file": fn.file, "line": fn.line})

        return results
