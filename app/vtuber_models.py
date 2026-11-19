from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

DEFAULT_IMPORT_CANDIDATES = [
    ("witch", "魔女 (Live2D)", Path(r"F:\Download\魔女")),
]

EXPRESSION_LABELS: dict[str, str] = {
    "xx": "⭐ Mắt sao",
    "x": "💖 Mắt tim",
    "zs1": "🎮 Cầm tay cầm",
    "zs2": "🎤 Cầm micro",
    "cw": "👻 Bé ma",
    "sq": "💢 Giận",
    "ku": "😭 Khóc",
    "h": "😱 Sốc / Mặt tối",
    "yj": "👓 Đeo kính",
    "mz": "🎩 Đội mũ",
    "fz": "🪄 Đũa phép",
    "hdj": "🎀 Nơ",
}

MOOD_TO_EXPRESSION: dict[str, str] = {
    "happy": "x",
    "excited": "xx",
    "thinking": "zs1",
    "surprised": "h",
    "panic": "ku",
}


class ModelImportRequest(BaseModel):
    path: str = Field(min_length=3, max_length=500)
    name: str = Field(default="", max_length=80)


def _safe_slug(raw: str, fallback: str = "model") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_").lower()
    return cleaned[:48] or fallback


def _find_model3_json(model_dir: Path) -> Path | None:
    files = sorted(model_dir.glob("*.model3.json"))
    return files[0] if files else None


def _copy_model_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("Thumbs.db", "*.tmp", ".DS_Store"),
    )


def ensure_default_models(models_dir: Path) -> None:
    """Copy user-supplied local Live2D model once into ignored workspace storage."""
    models_dir.mkdir(parents=True, exist_ok=True)
    for slug, _, src_dir in DEFAULT_IMPORT_CANDIDATES:
        target_dir = models_dir / slug
        if _find_model3_json(target_dir):
            continue
        if src_dir.is_dir() and _find_model3_json(src_dir):
            try:
                _copy_model_dir(src_dir, target_dir)
            except Exception:
                pass


def _read_vtube_labels(model_dir: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    for vfile in sorted(model_dir.glob("*.vtube.json")):
        try:
            data = json.loads(vfile.read_text(encoding="utf-8"))
            for hk in data.get("Hotkeys", []):
                fname = str(hk.get("File", "")).strip()
                hname = str(hk.get("Name", "")).strip()
                if fname.endswith(".exp3.json") and hname:
                    exp_id = fname[:-len(".exp3.json")]
                    labels[exp_id] = hname
        except Exception:
            pass
    return labels


def _describe_model_dir(model_dir: Path) -> dict[str, Any] | None:
    m3_path = _find_model3_json(model_dir)
    if not m3_path:
        return None
    slug = model_dir.name
    vtube_labels = _read_vtube_labels(model_dir)
    display_name = m3_path.name[:-len(".model3.json")]
    for vfile in sorted(model_dir.glob("*.vtube.json")):
        try:
            vname = str(json.loads(vfile.read_text(encoding="utf-8")).get("Name", "")).strip()
            if vname:
                display_name = vname
                break
        except Exception:
            pass

    expressions = []
    for p in sorted(model_dir.glob("*.exp3.json")):
        exp_id = p.name[:-len(".exp3.json")]
        label = EXPRESSION_LABELS.get(exp_id) or vtube_labels.get(exp_id) or exp_id
        expressions.append({"id": exp_id, "label": label, "file": p.name})

    motions = [p.name for p in sorted(model_dir.glob("*.motion3.json"))]
    return {
        "id": slug,
        "name": f"{display_name} (Live2D)",
        "kind": "live2d",
        "model_url": f"/api/vtuber/model-files/{slug}/manifest.model3.json",
        "expressions": expressions,
        "mood_map": {
            mood: exp for mood, exp in MOOD_TO_EXPRESSION.items()
            if any(e["id"] == exp for e in expressions)
        },
        "motions": motions,
    }


def _build_enriched_manifest(model_dir: Path) -> dict[str, Any]:
    m3_path = _find_model3_json(model_dir)
    if not m3_path:
        raise HTTPException(404, "Không tìm thấy tệp .model3.json trong thư mục model.")
    data = json.loads(m3_path.read_text(encoding="utf-8"))
    refs = data.setdefault("FileReferences", {})

    existing_exp = {str(e.get("Name", "")) for e in refs.get("Expressions", []) if isinstance(e, dict)}
    exp_list = list(refs.get("Expressions", [])) if isinstance(refs.get("Expressions"), list) else []
    for p in sorted(model_dir.glob("*.exp3.json")):
        exp_id = p.name[:-len(".exp3.json")]
        if exp_id not in existing_exp:
            exp_list.append({"Name": exp_id, "File": p.name})
    if exp_list:
        refs["Expressions"] = exp_list

    if not refs.get("Motions"):
        motion_files = sorted(model_dir.glob("*.motion3.json"))
        if motion_files:
            refs["Motions"] = {"Idle": [{"File": motion_files[0].name}]}

    return data


def register_routes(app: FastAPI, data_dir: Path) -> None:
    models_dir = data_dir / "vtuber_models"
    ensure_default_models(models_dir)

    @app.get("/api/vtuber/models")
    def api_vtuber_models() -> dict[str, Any]:
        models: list[dict[str, Any]] = []
        if models_dir.is_dir():
            for child in sorted(models_dir.iterdir()):
                if not child.is_dir():
                    continue
                desc = _describe_model_dir(child)
                if desc:
                    models.append(desc)
        models.append({
            "id": "svg-fallback",
            "name": "Avatar SVG nhẹ (dự phòng)",
            "kind": "svg",
            "model_url": "",
            "expressions": [],
            "mood_map": {},
            "motions": [],
        })
        return {"models": models}

    @app.post("/api/vtuber/models/import")
    def api_vtuber_model_import(req: ModelImportRequest) -> dict[str, Any]:
        raw_path = req.path.strip().strip('"')
        if raw_path.startswith("\\\\"):
            raise HTTPException(400, "Không hỗ trợ đường dẫn mạng UNC.")
        src_dir = Path(raw_path)
        if not src_dir.is_dir():
            raise HTTPException(404, f"Không tìm thấy thư mục model: {src_dir}")
        m3 = _find_model3_json(src_dir)
        if not m3:
            raise HTTPException(400, "Thư mục này không chứa tệp .model3.json hợp lệ.")
        base_name = req.name.strip() or m3.name[:-len(".model3.json")]
        slug = _safe_slug(base_name, fallback="custom_live2d")
        if slug == "svg-fallback":
            slug = "custom_live2d"
        dst_dir = models_dir / slug
        if dst_dir.exists() and (dst_dir.resolve() != src_dir.resolve()):
            idx = 2
            while (models_dir / f"{slug}_{idx}").exists():
                idx += 1
            slug = f"{slug}_{idx}"
            dst_dir = models_dir / slug
        _copy_model_dir(src_dir, dst_dir)
        desc = _describe_model_dir(dst_dir)
        if not desc:
            raise HTTPException(500, "Không đọc được thông tin model sau khi nạp.")
        return {"ok": True, "model": desc}

    @app.get("/api/vtuber/model-files/{model_id}/{file_path:path}")
    def api_vtuber_model_file(model_id: str, file_path: str):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", model_id):
            raise HTTPException(400, "Mã model không hợp lệ.")
        model_dir = (models_dir / model_id).resolve()
        if not model_dir.is_dir() or not model_dir.is_relative_to(models_dir.resolve()):
            raise HTTPException(404, "Không tìm thấy model Live2D.")
        if file_path == "manifest.model3.json":
            return JSONResponse(
                _build_enriched_manifest(model_dir),
                headers={"Cache-Control": "no-cache"},
            )
        target = (model_dir / file_path).resolve()
        if not target.is_relative_to(model_dir) or not target.is_file():
            raise HTTPException(404, "Không tìm thấy tài nguyên model.")
        return FileResponse(target, headers={"Cache-Control": "public, max-age=86400"})
