from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REGISTRY = DATA / "project_registry.json"
TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".cpp", ".c", ".h", ".hpp", ".s", ".S", ".asm",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".xml", ".dts", ".dtsi",
    ".sh", ".bat", ".ps1", ".cmake", ".mk", ".config", ".rst", ".log",
}
SKIP_DIRS = {
    ".git", ".godot", ".pytest_cache", ".venv", ".venv-ota", "__pycache__",
    "node_modules", "downloads", "toolchains", "kernel-build", "xnu-audit-f6217",
}
MAX_FILE_BYTES = 350_000
MAX_CONTEXT_CHARS = 8_200


def _registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY.is_file():
        return {}
    try:
        raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in raw.get("projects", []):
        key = str(item.get("key", "")).strip()
        root_text = str(item.get("root", "")).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,50}", key) or not root_text:
            continue
        root = Path(root_text).expanduser()
        if not root.is_absolute():
            continue
        try:
            resolved = root.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        result[key] = {**item, "root_path": resolved}
    return result


def list_projects() -> list[dict[str, Any]]:
    values = []
    for key, item in _registry().items():
        root: Path = item["root_path"]
        values.append({
            "key": key,
            "name": item.get("name", key),
            "description": item.get("description", ""),
            "root": str(root),
            "default": bool(item.get("default", False)),
            "available": True,
        })
    return values


def default_project_key() -> str:
    for item in _registry().values():
        if item.get("default"):
            return str(item["key"])
    return ""


def _read_file(root: Path, relative: str) -> tuple[str, str] | None:
    rel = Path(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return None
    if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts):
        return None
    target = root.joinpath(*rel.parts)
    try:
        if target.is_symlink():
            return None
        resolved = target.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file() or resolved.suffix not in TEXT_EXTENSIONS:
            return None
        size = resolved.stat().st_size
        if size > MAX_FILE_BYTES:
            return None
        data = resolved.read_bytes()
        text = data.decode("utf-8", errors="replace")
        return text, hashlib.sha256(data).hexdigest()
    except (OSError, ValueError):
        return None


def _candidate_relative_paths(root: Path) -> list[str]:
    fixed = [
        "README.md",
        "docs/porting-plan.md",
        "docs/device-inventory.md",
        "tools/xnu-a31/MT6765CPU.cpp",
        "tools/xnu-a31/MT6765CPU.h",
        "tools/xnu-a31/secondary_psci_trampoline.s",
        "tools/xnu-a31/arm_smc.s",
        "docs/assistant-work/step18p-psci-secondary-entry-trampoline-and-sequential-memory-audit.md",
        "docs/assistant-work/step18o-dtb-reservation-analyzer-and-xnu-psci-smp-audit.md",
    ]
    paths = list(fixed)
    recent_dirs = [
        root / "docs" / "assistant-work",
        root / "docs",
        root / "reports",
        root / "tests" / "xnu-a31",
        root / "tools" / "xnu-a31",
        root / "target",
    ]
    for folder in recent_dirs:
        if not folder.is_dir():
            continue
        try:
            candidates = [
                p for p in folder.rglob("*")
                if p.is_file() and p.suffix in TEXT_EXTENSIONS
                and not any(part in SKIP_DIRS or part.startswith(".") for part in p.relative_to(root).parts)
                and p.stat().st_size <= MAX_FILE_BYTES
            ]
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            paths.extend(p.relative_to(root).as_posix() for p in candidates[:16])
        except OSError:
            continue
    seen: set[str] = set()
    return [p for p in paths if not (p in seen or seen.add(p))]


def _excerpt(text: str, query: str, limit: int) -> str:
    text = text.replace("\x00", "").strip()
    if len(text) <= limit:
        return text
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_./-]{3,}", query)[:10]]
    lines = text.splitlines()
    scored = []
    for i, line in enumerate(lines):
        lower = line.lower()
        score = sum(1 for term in terms if term in lower)
        if score:
            scored.append((score, i))
    if scored:
        chosen = sorted(i for _, i in sorted(scored, reverse=True)[:8])
        chunks = []
        used = 0
        for i in chosen:
            start, end = max(0, i - 2), min(len(lines), i + 3)
            chunk = "\n".join(lines[start:end])
            if used + len(chunk) > limit:
                break
            chunks.append(chunk)
            used += len(chunk)
        if chunks:
            return "\n...\n".join(chunks)
    return text[:limit] + "\n...[đã rút gọn]"


def build_project_context(project_key: str, query: str = "") -> dict[str, Any]:
    registry = _registry()
    item = registry.get(project_key)
    if not item:
        raise KeyError(f"Project key chưa được đăng ký hoặc thư mục không tồn tại: {project_key}")
    root: Path = item["root_path"]
    evidence: list[dict[str, str]] = []
    sections: list[str] = []
    used = 0
    max_files = 13
    for relative in _candidate_relative_paths(root):
        if len(evidence) >= 13 or used >= MAX_CONTEXT_CHARS:
            break
        loaded = _read_file(root, relative)
        if loaded is None:
            continue
        content, digest = loaded
        per_file = 620 if relative.startswith("docs/assistant-work/") else 850
        if relative.endswith(("MT6765CPU.cpp", "MT6765CPU.h", "secondary_psci_trampoline.s")):
            per_file = 900
        excerpt = _excerpt(content, query, per_file)
        if used + len(excerpt) > MAX_CONTEXT_CHARS:
            excerpt = excerpt[:max(0, MAX_CONTEXT_CHARS - used)]
        if not excerpt:
            continue
        evidence.append({
            "path": relative,
            "sha256": digest,
            "bytes": str(len(content.encode("utf-8"))),
            "kind": "project_file",
        })
        sections.append(f"[PROJECT FILE: {relative} | SHA256:{digest[:16]}]\n{excerpt}")
        used += len(excerpt)
    context = (
        f"PROJECT: {item.get('name', project_key)}\n"
        f"ROOT: {root}\n"
        f"DESCRIPTION: {item.get('description', '')}\n"
        f"READ-ONLY: true; không ghi/sửa/xóa tệp trong project.\n\n"
        + "\n\n".join(sections)
    )
    return {
        "project_key": project_key,
        "project_name": item.get("name", project_key),
        "root": str(root),
        "context": context[:MAX_CONTEXT_CHARS + 1000],
        "files": evidence,
        "files_read": len(evidence),
        "read_only": True,
    }


def register_routes(app: FastAPI) -> None:
    @app.get("/api/research/projects")
    async def research_projects() -> list[dict[str, Any]]:
        return list_projects()

    @app.get("/api/research/project-context")
    async def research_project_context(project_key: str, query: str = "") -> dict[str, Any]:
        try:
            result = build_project_context(project_key, query[:500])
            result.pop("context", None)
            return result
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @app.get("/api/research/codebase-graph")
    async def research_codebase_graph(symbol: str = "") -> dict[str, Any]:
        from app.codebase_graph import CodebaseGraph, DEFAULT_GRAPH_PATH
        graph = CodebaseGraph()
        if not DEFAULT_GRAPH_PATH.exists():
            graph.scan_directory()
            graph.save_graph()
        else:
            graph.load_graph()

        if not symbol:
            return {
                "modules_count": len(graph.modules),
                "classes_count": len(graph.classes),
                "functions_count": len(graph.functions),
                "sample_modules": list(graph.modules.keys())[:10],
            }
        return graph.query_symbol(symbol)
