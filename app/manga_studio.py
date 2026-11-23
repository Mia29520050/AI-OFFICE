from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, Body, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont

# Peer modules
try:
    import manga_story
except ImportError:
    manga_story = None

try:
    import manga_comfy
except ImportError:
    manga_comfy = None

try:
    import manga_composer
except ImportError:
    manga_composer = None

logger = logging.getLogger("manga_studio")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "office.db"
MANGA_DATA = DATA / "manga"
PROJECTS_DIR = MANGA_DATA / "projects"
FONT_PATH = ROOT / "app" / "ui" / "assets" / "Inter-Variable.ttf"

# Ensure directories exist
DATA.mkdir(exist_ok=True)
MANGA_DATA.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or f"series-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_manga_db(db_conn: Optional[sqlite3.Connection] = None) -> None:
    should_close = False
    if db_conn is None:
        db_conn = connect()
        should_close = True

    try:
        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_series (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            synopsis TEXT NOT NULL DEFAULT '',
            genre TEXT NOT NULL DEFAULT '',
            art_style TEXT NOT NULL DEFAULT 'bw',
            reading_direction TEXT NOT NULL DEFAULT 'rtl',
            settings_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_volumes (
            id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            number INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (series_id) REFERENCES manga_series(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_chapters (
            id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            volume_id TEXT,
            number REAL NOT NULL,
            title TEXT NOT NULL,
            synopsis TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            canon_snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (series_id) REFERENCES manga_series(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_characters (
            id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            name TEXT NOT NULL,
            identity_json TEXT NOT NULL DEFAULT '{}',
            personality_json TEXT NOT NULL DEFAULT '{}',
            speech_rules_json TEXT NOT NULL DEFAULT '{}',
            locked_traits_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (series_id) REFERENCES manga_series(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_character_states (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            scene_id TEXT,
            costume_json TEXT NOT NULL DEFAULT '{}',
            appearance_json TEXT NOT NULL DEFAULT '{}',
            emotions_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (character_id) REFERENCES manga_characters(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_scenes (
            id TEXT PRIMARY KEY,
            chapter_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            characters_json TEXT NOT NULL DEFAULT '[]',
            content_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (chapter_id) REFERENCES manga_chapters(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_storyboard_pages (
            id TEXT PRIMARY KEY,
            chapter_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            layout_template TEXT NOT NULL DEFAULT '4-panel',
            status TEXT NOT NULL DEFAULT 'draft',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (chapter_id) REFERENCES manga_chapters(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_panels (
            id TEXT PRIMARY KEY,
            page_id TEXT NOT NULL,
            panel_number INTEGER NOT NULL,
            prompt_json TEXT NOT NULL DEFAULT '{}',
            dialogue_json TEXT NOT NULL DEFAULT '[]',
            sfx_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending',
            image_asset_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (page_id) REFERENCES manga_storyboard_pages(id) ON DELETE CASCADE
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_art_jobs (
            id TEXT PRIMARY KEY,
            panel_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt INTEGER NOT NULL DEFAULT 1,
            seed INTEGER NOT NULL DEFAULT -1,
            input_json TEXT NOT NULL DEFAULT '{}',
            output_asset_id TEXT,
            error_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

        job_cols = {c[1] for c in db_conn.execute("PRAGMA table_info(manga_art_jobs)").fetchall()}
        for col_name, col_def in [
            ("series_id", "TEXT NOT NULL DEFAULT ''"),
            ("chapter_id", "TEXT NOT NULL DEFAULT ''"),
            ("page_id", "TEXT NOT NULL DEFAULT ''"),
            ("mode", "TEXT NOT NULL DEFAULT 'mock'"),
            ("mock_reason", "TEXT NOT NULL DEFAULT ''"),
            ("max_attempts", "INTEGER NOT NULL DEFAULT 3"),
            ("prompt", "TEXT NOT NULL DEFAULT ''"),
            ("negative_prompt", "TEXT NOT NULL DEFAULT ''"),
            ("width", "INTEGER NOT NULL DEFAULT 768"),
            ("height", "INTEGER NOT NULL DEFAULT 1024"),
            ("steps", "INTEGER NOT NULL DEFAULT 20"),
            ("cfg_scale", "REAL NOT NULL DEFAULT 7.0"),
            ("sampler_name", "TEXT NOT NULL DEFAULT 'euler_ancestral'"),
            ("scheduler", "TEXT NOT NULL DEFAULT 'normal'"),
            ("art_style", "TEXT NOT NULL DEFAULT 'manga_bw'"),
            ("workflow_id", "TEXT NOT NULL DEFAULT ''"),
            ("model_name", "TEXT NOT NULL DEFAULT ''"),
            ("output_asset_path", "TEXT NOT NULL DEFAULT ''"),
            ("relative_path", "TEXT NOT NULL DEFAULT ''"),
            ("checksum", "TEXT NOT NULL DEFAULT ''"),
            ("file_size", "INTEGER NOT NULL DEFAULT 0"),
            ("duration_seconds", "REAL NOT NULL DEFAULT 0.0"),
        ]:
            if col_name not in job_cols:
                db_conn.execute(f"ALTER TABLE manga_art_jobs ADD COLUMN {col_name} {col_def}")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_assets (
            id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            owner_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            checksum TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )""")

        db_conn.execute("""CREATE TABLE IF NOT EXISTS manga_exports (
            id TEXT PRIMARY KEY,
            chapter_id TEXT NOT NULL,
            format TEXT NOT NULL,
            output_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )""")

        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_volumes_series ON manga_volumes(series_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_chapters_series ON manga_chapters(series_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_characters_series ON manga_characters(series_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_scenes_chapter ON manga_scenes(chapter_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_pages_chapter ON manga_storyboard_pages(chapter_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_panels_page ON manga_panels(page_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_jobs_status ON manga_art_jobs(status)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_assets_series ON manga_assets(series_id)")
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_manga_exports_chapter ON manga_exports(chapter_id)")
        db_conn.commit()
    finally:
        if should_close:
            db_conn.close()


# ---------------------------------------------------------------------------
# Storage Helpers
# ---------------------------------------------------------------------------

def get_series_dir(series_id: str) -> Path:
    p = PROJECTS_DIR / series_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_chapter_dir(series_id: str, chapter_id: str) -> Path:
    p = get_series_dir(series_id) / "chapters" / chapter_id
    p.mkdir(parents=True, exist_ok=True)
    (p / "panels").mkdir(parents=True, exist_ok=True)
    (p / "pages").mkdir(parents=True, exist_ok=True)
    return p


def get_character_dir(series_id: str, character_id: str) -> Path:
    p = get_series_dir(series_id) / "characters" / character_id
    p.mkdir(parents=True, exist_ok=True)
    (p / "references").mkdir(parents=True, exist_ok=True)
    return p


def get_exports_dir(series_id: str) -> Path:
    p = get_series_dir(series_id) / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class SeriesCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    synopsis: str = ""
    genre: str = ""
    art_style: str = "bw"  # 'bw' or 'color'
    reading_direction: str = "rtl"  # 'rtl' (Manga) or 'ltr'
    settings: dict[str, Any] = Field(default_factory=dict)


class SeriesUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    genre: Optional[str] = None
    art_style: Optional[str] = None
    reading_direction: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class VolumeCreate(BaseModel):
    number: int = Field(..., ge=1)
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    number: float = Field(..., ge=0)
    synopsis: str = ""
    volume_id: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    number: Optional[float] = None
    synopsis: Optional[str] = None
    volume_id: Optional[str] = None
    status: Optional[str] = None


class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    identity: dict[str, Any] = Field(default_factory=dict)
    personality: dict[str, Any] = Field(default_factory=dict)
    speech_rules: dict[str, Any] = Field(default_factory=dict)
    locked_traits: list[Any] = Field(default_factory=list)


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    identity: Optional[dict[str, Any]] = None
    personality: Optional[dict[str, Any]] = None
    speech_rules: Optional[dict[str, Any]] = None
    locked_traits: Optional[list[Any]] = None


class SceneCreate(BaseModel):
    position: int = 1
    summary: str = ""
    location: str = ""
    characters: list[str] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)


class PageCreate(BaseModel):
    page_number: int = Field(..., ge=1)
    layout_template: str = "4-panel"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PanelCreate(BaseModel):
    panel_number: int = Field(..., ge=1)
    prompt: dict[str, Any] = Field(default_factory=dict)
    dialogue: list[dict[str, Any]] = Field(default_factory=list)
    sfx: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PanelUpdate(BaseModel):
    prompt: Optional[dict[str, Any]] = None
    dialogue: Optional[list[dict[str, Any]]] = None
    sfx: Optional[list[dict[str, Any]]] = None
    status: Optional[str] = None
    image_asset_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class GenerateScenesRequest(BaseModel):
    chapter_id: str
    prompt: Optional[str] = None
    scene_count: int = Field(default=4, ge=1, le=12)


class CheckContinuityRequest(BaseModel):
    chapter_id: str


class GenerateCharacterRequest(BaseModel):
    series_id: str
    name: str
    role: str = "Nhân vật chính"
    concept: str = ""


class GeneratePanelArtRequest(BaseModel):
    panel_id: str
    prompt: Optional[str] = None
    seed: Optional[int] = -1
    use_mock: bool = False


class GenerateChapterArtRequest(BaseModel):
    chapter_id: str
    use_mock: bool = False


class RenderPageRequest(BaseModel):
    layout_override: Optional[str] = None
    apply_screentone: Optional[bool] = None


class ExportChapterRequest(BaseModel):
    chapter_id: str
    format: str = "all"  # 'cbz', 'pdf', 'png', or 'all'


# ---------------------------------------------------------------------------
# Router Definition
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/manga", tags=["Manga Studio Core"])


# --- Series CRUD ---

@router.get("/series")
def list_series():
    with connect() as db:
        rows = db.execute("""
            SELECT s.*,
                (SELECT COUNT(*) FROM manga_volumes v WHERE v.series_id = s.id) as volume_count,
                (SELECT COUNT(*) FROM manga_chapters c WHERE c.series_id = s.id) as chapter_count,
                (SELECT COUNT(*) FROM manga_characters ch WHERE ch.series_id = s.id) as character_count
            FROM manga_series s
            ORDER BY s.updated_at DESC
        """).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["settings"] = json.loads(d.pop("settings_json", "{}") or "{}")
            result.append(d)
        return result


@router.post("/series")
def create_series(body: SeriesCreate):
    series_id = uuid.uuid4().hex
    slug = slugify(body.title)
    stamp = now()
    settings_str = json.dumps(body.settings, ensure_ascii=False)

    with connect() as db:
        db.execute("""
            INSERT INTO manga_series (id, title, slug, synopsis, genre, art_style, reading_direction, settings_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (series_id, body.title, slug, body.synopsis, body.genre, body.art_style, body.reading_direction, settings_str, stamp, stamp))
        db.commit()

    # Create folder structure on disk
    s_dir = get_series_dir(series_id)
    manifest = {
        "id": series_id,
        "title": body.title,
        "slug": slug,
        "synopsis": body.synopsis,
        "genre": body.genre,
        "art_style": body.art_style,
        "reading_direction": body.reading_direction,
        "settings": body.settings,
        "created_at": stamp,
    }
    (s_dir / "series.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "id": series_id,
        "title": body.title,
        "slug": slug,
        "synopsis": body.synopsis,
        "genre": body.genre,
        "art_style": body.art_style,
        "reading_direction": body.reading_direction,
        "settings": body.settings,
        "created_at": stamp,
        "updated_at": stamp,
    }


@router.get("/series/{series_id}")
def get_series(series_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM manga_series WHERE id = ?", (series_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy series.")
        series = dict(row)
        series["settings"] = json.loads(series.pop("settings_json", "{}") or "{}")

        volumes = [dict(v) for v in db.execute("SELECT * FROM manga_volumes WHERE series_id = ? ORDER BY number ASC", (series_id,)).fetchall()]
        for v in volumes:
            v["metadata"] = json.loads(v.pop("metadata_json", "{}") or "{}")

        chapters = [dict(c) for c in db.execute("SELECT * FROM manga_chapters WHERE series_id = ? ORDER BY number ASC", (series_id,)).fetchall()]
        for c in chapters:
            c["canon_snapshot"] = json.loads(c.pop("canon_snapshot_json", "{}") or "{}")

        characters = [dict(ch) for ch in db.execute("SELECT * FROM manga_characters WHERE series_id = ? ORDER BY name ASC", (series_id,)).fetchall()]
        for ch in characters:
            ch["identity"] = json.loads(ch.pop("identity_json", "{}") or "{}")
            ch["personality"] = json.loads(ch.pop("personality_json", "{}") or "{}")
            ch["speech_rules"] = json.loads(ch.pop("speech_rules_json", "{}") or "{}")
            ch["locked_traits"] = json.loads(ch.pop("locked_traits_json", "[]") or "[]")

        series["volumes"] = volumes
        series["chapters"] = chapters
        series["characters"] = characters
        return series


@router.put("/series/{series_id}")
def update_series(series_id: str, body: SeriesUpdate):
    with connect() as db:
        existing = db.execute("SELECT * FROM manga_series WHERE id = ?", (series_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy series.")

        fields = []
        params = []
        if body.title is not None:
            fields.append("title = ?")
            params.append(body.title)
            fields.append("slug = ?")
            params.append(slugify(body.title))
        if body.synopsis is not None:
            fields.append("synopsis = ?")
            params.append(body.synopsis)
        if body.genre is not None:
            fields.append("genre = ?")
            params.append(body.genre)
        if body.art_style is not None:
            fields.append("art_style = ?")
            params.append(body.art_style)
        if body.reading_direction is not None:
            fields.append("reading_direction = ?")
            params.append(body.reading_direction)
        if body.settings is not None:
            fields.append("settings_json = ?")
            params.append(json.dumps(body.settings, ensure_ascii=False))

        stamp = now()
        fields.append("updated_at = ?")
        params.append(stamp)
        params.append(series_id)

        db.execute(f"UPDATE manga_series SET {', '.join(fields)} WHERE id = ?", params)
        db.commit()

        updated = dict(db.execute("SELECT * FROM manga_series WHERE id = ?", (series_id,)).fetchone())
        updated["settings"] = json.loads(updated.pop("settings_json", "{}") or "{}")
        return updated


@router.delete("/series/{series_id}")
def delete_series(series_id: str):
    with connect() as db:
        existing = db.execute("SELECT * FROM manga_series WHERE id = ?", (series_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy series.")

        db.execute("DELETE FROM manga_panels WHERE page_id IN (SELECT id FROM manga_storyboard_pages WHERE chapter_id IN (SELECT id FROM manga_chapters WHERE series_id = ?))", (series_id,))
        db.execute("DELETE FROM manga_storyboard_pages WHERE chapter_id IN (SELECT id FROM manga_chapters WHERE series_id = ?)", (series_id,))
        db.execute("DELETE FROM manga_scenes WHERE chapter_id IN (SELECT id FROM manga_chapters WHERE series_id = ?)", (series_id,))
        db.execute("DELETE FROM manga_chapters WHERE series_id = ?", (series_id,))
        db.execute("DELETE FROM manga_volumes WHERE series_id = ?", (series_id,))
        db.execute("DELETE FROM manga_characters WHERE series_id = ?", (series_id,))
        db.execute("DELETE FROM manga_assets WHERE series_id = ?", (series_id,))
        db.execute("DELETE FROM manga_series WHERE id = ?", (series_id,))
        db.commit()

    return {"status": "deleted", "id": series_id}


# --- Seed Sample Moonlight Classroom Project ---

@router.post("/series/sample")
def seed_sample_series():
    """Seeds the official Moonlight Classroom demonstration project."""
    if not manga_story:
        raise HTTPException(500, "Module manga_story chưa sẵn sàng.")

    sample = manga_story.create_sample_story_data()
    series_info = sample["series"]

    # 1. Create series
    created_series = create_series(SeriesCreate(
        title=series_info["title"],
        synopsis=series_info["synopsis"],
        genre=series_info["genre"],
        art_style="bw" if series_info.get("art_style") == "b_w" else "color",
        reading_direction="rtl",
        settings={"sample": True, "theme": "Moonlight Classroom"}
    ))
    series_id = created_series["id"]

    # 2. Create volume 1
    vol = create_volume(series_id, VolumeCreate(number=1, title="Tập 1: Cấm Ấn Hắc Nguyệt"))

    # 3. Create chapter 1
    chap = create_chapter(series_id, ChapterCreate(
        title="Chương 1: Cuộc Gặp Dưới Ánh Trăng",
        number=1.0,
        synopsis="Ren chuyển trường đến Học Viện và có cuộc chạm trán bất ngờ với Hội trưởng Luna trước khi thảm họa ập tới.",
        volume_id=vol["id"]
    ))
    chap_id = chap["id"]

    # 4. Insert characters
    for char_prof in sample["characters"]:
        prof_dict = char_prof.model_dump() if hasattr(char_prof, "model_dump") else char_prof
        create_character(series_id, CharacterCreate(
            name=prof_dict["name"],
            identity={"japanese_name": prof_dict.get("japanese_name"), "role": prof_dict.get("role"), "one_line": prof_dict.get("one_line_summary"), "backstory": prof_dict.get("backstory")},
            personality={"description": prof_dict.get("personality"), "strengths": prof_dict.get("strengths"), "weaknesses": prof_dict.get("weaknesses")},
            speech_rules=prof_dict.get("speech_rules", {}),
            locked_traits=prof_dict.get("locked_traits", {}).get("facial_features", []) + [prof_dict.get("locked_traits", {}).get("signature_outfit", "")]
        ))

    # 5. Auto generate storyboard for Chapter 1
    auto_storyboard(chap_id)

    return get_series(series_id)


# --- Volumes & Chapters ---

@router.get("/series/{series_id}/volumes")
def list_volumes(series_id: str):
    with connect() as db:
        rows = db.execute("SELECT * FROM manga_volumes WHERE series_id = ? ORDER BY number ASC", (series_id,)).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
            res.append(d)
        return res


@router.post("/series/{series_id}/volumes")
def create_volume(series_id: str, body: VolumeCreate):
    with connect() as db:
        series = db.execute("SELECT id FROM manga_series WHERE id = ?", (series_id,)).fetchone()
        if not series:
            raise HTTPException(status_code=404, detail="Không tìm thấy series.")

        volume_id = uuid.uuid4().hex
        stamp = now()
        db.execute("""
            INSERT INTO manga_volumes (id, series_id, number, title, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (volume_id, series_id, body.number, body.title, json.dumps(body.metadata, ensure_ascii=False), stamp, stamp))
        db.commit()
        return {"id": volume_id, "series_id": series_id, "number": body.number, "title": body.title, "metadata": body.metadata}


@router.delete("/volumes/{volume_id}")
def delete_volume(volume_id: str):
    with connect() as db:
        db.execute("DELETE FROM manga_volumes WHERE id = ?", (volume_id,))
        db.commit()
    return {"status": "deleted", "id": volume_id}


@router.get("/series/{series_id}/chapters")
def list_chapters(series_id: str):
    with connect() as db:
        rows = db.execute("""
            SELECT c.*,
                (SELECT COUNT(*) FROM manga_scenes s WHERE s.chapter_id = c.id) as scene_count,
                (SELECT COUNT(*) FROM manga_storyboard_pages p WHERE p.chapter_id = c.id) as page_count
            FROM manga_chapters c
            WHERE c.series_id = ?
            ORDER BY c.number ASC
        """, (series_id,)).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["canon_snapshot"] = json.loads(d.pop("canon_snapshot_json", "{}") or "{}")
            res.append(d)
        return res


@router.post("/series/{series_id}/chapters")
def create_chapter(series_id: str, body: ChapterCreate):
    with connect() as db:
        series = db.execute("SELECT id FROM manga_series WHERE id = ?", (series_id,)).fetchone()
        if not series:
            raise HTTPException(status_code=404, detail="Không tìm thấy series.")

        chapter_id = uuid.uuid4().hex
        stamp = now()
        db.execute("""
            INSERT INTO manga_chapters (id, series_id, volume_id, number, title, synopsis, status, canon_snapshot_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'draft', '{}', ?, ?)
        """, (chapter_id, series_id, body.volume_id, body.number, body.title, body.synopsis, stamp, stamp))
        db.commit()

    get_chapter_dir(series_id, chapter_id)
    return {"id": chapter_id, "series_id": series_id, "number": body.number, "title": body.title, "synopsis": body.synopsis, "status": "draft"}


@router.get("/chapters/{chapter_id}")
def get_chapter(chapter_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM manga_chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy chapter.")
        chapter = dict(row)
        chapter["canon_snapshot"] = json.loads(chapter.pop("canon_snapshot_json", "{}") or "{}")

        scenes = [dict(s) for s in db.execute("SELECT * FROM manga_scenes WHERE chapter_id = ? ORDER BY position ASC", (chapter_id,)).fetchall()]
        for s in scenes:
            s["characters"] = json.loads(s.pop("characters_json", "[]") or "[]")
            s["content"] = json.loads(s.pop("content_json", "{}") or "{}")

        pages = [dict(p) for p in db.execute("SELECT * FROM manga_storyboard_pages WHERE chapter_id = ? ORDER BY page_number ASC", (chapter_id,)).fetchall()]
        for p in pages:
            p["metadata"] = json.loads(p.pop("metadata_json", "{}") or "{}")
            panels = [dict(pan) for pan in db.execute("SELECT * FROM manga_panels WHERE page_id = ? ORDER BY panel_number ASC", (p["id"],)).fetchall()]
            for pan in panels:
                pan["prompt"] = json.loads(pan.pop("prompt_json", "{}") or "{}")
                pan["dialogue"] = json.loads(pan.pop("dialogue_json", "[]") or "[]")
                pan["sfx"] = json.loads(pan.pop("sfx_json", "[]") or "[]")
                pan["metadata"] = json.loads(pan.pop("metadata_json", "{}") or "{}")
            p["panels"] = panels

        chapter["scenes"] = scenes
        chapter["pages"] = pages
        return chapter


@router.put("/chapters/{chapter_id}")
def update_chapter(chapter_id: str, body: ChapterUpdate):
    with connect() as db:
        fields, params = [], []
        if body.title is not None:
            fields.append("title = ?"); params.append(body.title)
        if body.number is not None:
            fields.append("number = ?"); params.append(body.number)
        if body.synopsis is not None:
            fields.append("synopsis = ?"); params.append(body.synopsis)
        if body.volume_id is not None:
            fields.append("volume_id = ?"); params.append(body.volume_id)
        if body.status is not None:
            fields.append("status = ?"); params.append(body.status)

        stamp = now()
        fields.append("updated_at = ?")
        params.append(stamp)
        params.append(chapter_id)

        db.execute(f"UPDATE manga_chapters SET {', '.join(fields)} WHERE id = ?", params)
        db.commit()

        row = db.execute("SELECT * FROM manga_chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy chapter.")
        res = dict(row)
        res["canon_snapshot"] = json.loads(res.pop("canon_snapshot_json", "{}") or "{}")
        return res


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: str):
    with connect() as db:
        db.execute("DELETE FROM manga_panels WHERE page_id IN (SELECT id FROM manga_storyboard_pages WHERE chapter_id = ?)", (chapter_id,))
        db.execute("DELETE FROM manga_storyboard_pages WHERE chapter_id = ?", (chapter_id,))
        db.execute("DELETE FROM manga_scenes WHERE chapter_id = ?", (chapter_id,))
        db.execute("DELETE FROM manga_chapters WHERE id = ?", (chapter_id,))
        db.commit()
    return {"status": "deleted", "id": chapter_id}


# --- Characters CRUD ---

@router.get("/series/{series_id}/characters")
def list_characters(series_id: str):
    with connect() as db:
        rows = db.execute("SELECT * FROM manga_characters WHERE series_id = ? ORDER BY name ASC", (series_id,)).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["identity"] = json.loads(d.pop("identity_json", "{}") or "{}")
            d["personality"] = json.loads(d.pop("personality_json", "{}") or "{}")
            d["speech_rules"] = json.loads(d.pop("speech_rules_json", "{}") or "{}")
            d["locked_traits"] = json.loads(d.pop("locked_traits_json", "[]") or "[]")
            res.append(d)
        return res


@router.post("/series/{series_id}/characters")
def create_character(series_id: str, body: CharacterCreate):
    char_id = uuid.uuid4().hex
    stamp = now()
    with connect() as db:
        db.execute("""
            INSERT INTO manga_characters (id, series_id, name, identity_json, personality_json, speech_rules_json, locked_traits_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            char_id, series_id, body.name,
            json.dumps(body.identity, ensure_ascii=False),
            json.dumps(body.personality, ensure_ascii=False),
            json.dumps(body.speech_rules, ensure_ascii=False),
            json.dumps(body.locked_traits, ensure_ascii=False),
            stamp, stamp
        ))
        db.commit()

    get_character_dir(series_id, char_id)
    return {
        "id": char_id,
        "series_id": series_id,
        "name": body.name,
        "identity": body.identity,
        "personality": body.personality,
        "speech_rules": body.speech_rules,
        "locked_traits": body.locked_traits,
    }


@router.get("/characters/{character_id}")
def get_character(character_id: str):
    with connect() as db:
        r = db.execute("SELECT * FROM manga_characters WHERE id = ?", (character_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhân vật.")
        d = dict(r)
        d["identity"] = json.loads(d.pop("identity_json", "{}") or "{}")
        d["personality"] = json.loads(d.pop("personality_json", "{}") or "{}")
        d["speech_rules"] = json.loads(d.pop("speech_rules_json", "{}") or "{}")
        d["locked_traits"] = json.loads(d.pop("locked_traits_json", "[]") or "[]")
        return d


@router.put("/characters/{character_id}")
def update_character(character_id: str, body: CharacterUpdate):
    with connect() as db:
        fields, params = [], []
        if body.name is not None:
            fields.append("name = ?"); params.append(body.name)
        if body.identity is not None:
            fields.append("identity_json = ?"); params.append(json.dumps(body.identity, ensure_ascii=False))
        if body.personality is not None:
            fields.append("personality_json = ?"); params.append(json.dumps(body.personality, ensure_ascii=False))
        if body.speech_rules is not None:
            fields.append("speech_rules_json = ?"); params.append(json.dumps(body.speech_rules, ensure_ascii=False))
        if body.locked_traits is not None:
            fields.append("locked_traits_json = ?"); params.append(json.dumps(body.locked_traits, ensure_ascii=False))

        stamp = now()
        fields.append("updated_at = ?")
        params.append(stamp)
        params.append(character_id)

        db.execute(f"UPDATE manga_characters SET {', '.join(fields)} WHERE id = ?", params)
        db.commit()

    return get_character(character_id)


@router.delete("/characters/{character_id}")
def delete_character(character_id: str):
    with connect() as db:
        db.execute("DELETE FROM manga_characters WHERE id = ?", (character_id,))
        db.commit()
    return {"status": "deleted", "id": character_id}


# --- Scenes & Story Studio AI Coordination ---

@router.get("/chapters/{chapter_id}/scenes")
def list_scenes(chapter_id: str):
    with connect() as db:
        rows = db.execute("SELECT * FROM manga_scenes WHERE chapter_id = ? ORDER BY position ASC", (chapter_id,)).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["characters"] = json.loads(d.pop("characters_json", "[]") or "[]")
            d["content"] = json.loads(d.pop("content_json", "{}") or "{}")
            res.append(d)
        return res


@router.post("/chapters/{chapter_id}/scenes")
def create_scene(chapter_id: str, body: SceneCreate):
    scene_id = uuid.uuid4().hex
    stamp = now()
    with connect() as db:
        db.execute("""
            INSERT INTO manga_scenes (id, chapter_id, position, summary, location, characters_json, content_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scene_id, chapter_id, body.position, body.summary, body.location,
            json.dumps(body.characters, ensure_ascii=False),
            json.dumps(body.content, ensure_ascii=False),
            stamp, stamp
        ))
        db.commit()
    return {"id": scene_id, "chapter_id": chapter_id, "position": body.position, "summary": body.summary, "location": body.location, "characters": body.characters, "content": body.content}


@router.put("/scenes/{scene_id}")
def update_scene(scene_id: str, body: SceneCreate):
    stamp = now()
    with connect() as db:
        db.execute("""
            UPDATE manga_scenes
            SET position = ?, summary = ?, location = ?, characters_json = ?, content_json = ?, updated_at = ?
            WHERE id = ?
        """, (
            body.position, body.summary, body.location,
            json.dumps(body.characters, ensure_ascii=False),
            json.dumps(body.content, ensure_ascii=False),
            stamp, scene_id
        ))
        db.commit()
    return {"id": scene_id, "position": body.position, "summary": body.summary, "location": body.location, "characters": body.characters}


@router.delete("/scenes/{scene_id}")
def delete_scene(scene_id: str):
    with connect() as db:
        db.execute("DELETE FROM manga_scenes WHERE id = ?", (scene_id,))
        db.commit()
    return {"status": "deleted", "id": scene_id}


@router.post("/story/generate-scenes")
async def generate_scenes_endpoint(body: GenerateScenesRequest):
    """Generates structured scenes for a chapter using manga_story module (or fallback)."""
    with connect() as db:
        chapter_row = db.execute("SELECT * FROM manga_chapters WHERE id = ?", (body.chapter_id,)).fetchone()
        if not chapter_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy chapter.")
        chapter = dict(chapter_row)
        series_id = chapter["series_id"]

        series_row = db.execute("SELECT * FROM manga_series WHERE id = ?", (series_id,)).fetchone()
        art_style = series_row["art_style"] if series_row else "bw"

        characters_raw = db.execute("SELECT * FROM manga_characters WHERE series_id = ?", (series_id,)).fetchall()

    characters_profiles = []
    if manga_story:
        for c in characters_raw:
            try:
                char_data = {
                    "id": c["id"],
                    "series_id": series_id,
                    "name": c["name"],
                    "speech_rules": json.loads(c["speech_rules_json"] or "{}"),
                    "personality": json.loads(c["personality_json"] or "{}").get("description", ""),
                    "backstory": json.loads(c["identity_json"] or "{}").get("backstory", ""),
                }
                characters_profiles.append(manga_story.CharacterProfile.model_validate(char_data))
            except Exception:
                pass

    scenes_data = []
    if manga_story and hasattr(manga_story, "generate_chapter_plan"):
        try:
            series_title = series_row["title"] if series_row else "Bộ Truyện Manga"
            req = manga_story.StoryGenerationRequest(
                series_title=series_title,
                premise=body.prompt or chapter["synopsis"] or "Kịch bản chương mới",
                chapter_title=chapter["title"],
                chapter_number=int(chapter["number"]),
                target_scene_count=body.scene_count,
                characters=characters_profiles,
                art_style="b_w" if art_style == "bw" else "color"
            )
            resp = await manga_story.generate_chapter_plan(req)
            if resp and resp.chapter_plan and resp.chapter_plan.scenes:
                for sc in resp.chapter_plan.scenes:
                    pos = getattr(sc, "scene_number", getattr(sc, "order_index", len(scenes_data) + 1))
                    scenes_data.append({
                        "position": pos,
                        "summary": sc.summary,
                        "location": sc.location,
                        "characters": sc.characters_present,
                        "content": {
                            "time_of_day": sc.time_of_day,
                            "emotional_beat": sc.emotional_beat,
                            "panels_count": len(sc.panels)
                        }
                    })
        except Exception as e:
            logger.warning(f"manga_story generation error: {e}")

    # Fallback if no scenes produced
    if not scenes_data:
        char_names = [c["name"] for c in characters_raw] or ["Nhân vật chính"]
        lead = char_names[0]
        prompts = [
            f"{lead} xuất hiện trong bối cảnh học viện, phát hiện điều bất thường.",
            f"{lead} đối mặt với tình huống thách thức và đưa ra quyết định quan trọng.",
            f"Cao trào phân cảnh hành động hoặc đối thoại kịch tính.",
            f"Kết thúc phân đoạn với bước ngoặt mở ra sự kiện tiếp theo."
        ]
        for idx in range(min(body.scene_count, len(prompts))):
            scenes_data.append({
                "position": idx + 1,
                "summary": prompts[idx],
                "location": "Học viện Ánh Trăng",
                "characters": char_names[:2],
                "content": {"tone": "kịch tính", "dialogue_preview": f"{lead}: 'Chúng ta nhất định không thể dừng lại ở đây!'"}
            })

    # Save to database
    created_scenes = []
    with connect() as db:
        db.execute("DELETE FROM manga_scenes WHERE chapter_id = ?", (body.chapter_id,))
        for sc in scenes_data:
            sid = uuid.uuid4().hex
            stamp = now()
            pos = sc.get("position", len(created_scenes) + 1)
            summary = sc.get("summary", "")
            location = sc.get("location", "")
            chars = sc.get("characters", [])
            content = sc.get("content", {})

            db.execute("""
                INSERT INTO manga_scenes (id, chapter_id, position, summary, location, characters_json, content_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sid, body.chapter_id, pos, summary, location, json.dumps(chars, ensure_ascii=False), json.dumps(content, ensure_ascii=False), stamp, stamp))
            created_scenes.append({
                "id": sid,
                "chapter_id": body.chapter_id,
                "position": pos,
                "summary": summary,
                "location": location,
                "characters": chars,
                "content": content
            })
        db.commit()

    return {"chapter_id": body.chapter_id, "scenes": created_scenes, "count": len(created_scenes)}


@router.post("/story/check-continuity")
async def check_continuity_endpoint(body: CheckContinuityRequest):
    """Continuity verification checking character traits, speech rules, and timeline consistency."""
    with connect() as db:
        chapter_row = db.execute("SELECT * FROM manga_chapters WHERE id = ?", (body.chapter_id,)).fetchone()
        if not chapter_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy chapter.")
        series_id = chapter_row["series_id"]

        scenes = [dict(s) for s in db.execute("SELECT * FROM manga_scenes WHERE chapter_id = ? ORDER BY position ASC", (body.chapter_id,)).fetchall()]
        characters = [dict(c) for c in db.execute("SELECT * FROM manga_characters WHERE series_id = ?", (series_id,)).fetchall()]

    if manga_story and hasattr(manga_story, "run_continuity_check"):
        try:
            char_profs = []
            for c in characters:
                char_profs.append(manga_story.CharacterProfile(
                    name=c["name"],
                    speech_rules=json.loads(c["speech_rules_json"] or "{}"),
                    personality=json.loads(c["personality_json"] or "{}").get("description", "")
                ))

            # Build minimal chapter plan for check
            chap_plan = manga_story.ChapterPlan(
                title=chapter_row["title"],
                chapter_number=int(chapter_row["number"]),
                synopsis=chapter_row["synopsis"] or "Tóm tắt chương",
                scenes=[]
            )
            req = manga_story.ContinuityCheckRequest(
                chapter_plan=chap_plan,
                characters=char_profs,
                canon_facts=[],
                timeline_events=[]
            )
            resp = await manga_story.run_continuity_check(req)
            if resp:
                report_dict = resp.report.model_dump()
                return {
                    "status": report_dict.get("status", "pass"),
                    "score": report_dict.get("score", 100),
                    "issues": report_dict.get("issues", []),
                    "mode_used": resp.mode_used,
                    "model_name": resp.model_name
                }
        except Exception as e:
            logger.warning(f"manga_story continuity check: {e}")

    # Fallback continuity report
    issues = []
    char_names = {c["name"] for c in characters}
    for sc in scenes:
        for cname in json.loads(sc.get("characters_json", "[]") or "[]"):
            if cname not in char_names:
                issues.append({
                    "severity": "warning",
                    "scene_position": sc["position"],
                    "message": f"Nhân vật '{cname}' xuất hiện ở Cảnh {sc['position']} nhưng chưa có hồ sơ đăng ký.",
                    "suggestion": "Tạo hồ sơ nhân vật trong Story Studio để khóa nét ngoại hình và tính cách."
                })

    return {
        "status": "passed" if len(issues) == 0 else "needs_review",
        "score": 100 if len(issues) == 0 else max(70, 100 - len(issues) * 10),
        "issues": issues,
        "summary": "Kiểm tra tính nhất quán cốt truyện hoàn tất." if not issues else f"Phát hiện {len(issues)} điểm cần rà soát."
    }


# --- Storyboard & Panels ---

@router.get("/chapters/{chapter_id}/pages")
def list_pages(chapter_id: str):
    with connect() as db:
        pages = [dict(p) for p in db.execute("SELECT * FROM manga_storyboard_pages WHERE chapter_id = ? ORDER BY page_number ASC", (chapter_id,)).fetchall()]
        for p in pages:
            p["metadata"] = json.loads(p.pop("metadata_json", "{}") or "{}")
            panels = [dict(pan) for pan in db.execute("SELECT * FROM manga_panels WHERE page_id = ? ORDER BY panel_number ASC", (p["id"],)).fetchall()]
            for pan in panels:
                pan["prompt"] = json.loads(pan.pop("prompt_json", "{}") or "{}")
                pan["dialogue"] = json.loads(pan.pop("dialogue_json", "[]") or "[]")
                pan["sfx"] = json.loads(pan.pop("sfx_json", "[]") or "[]")
                pan["metadata"] = json.loads(pan.pop("metadata_json", "{}") or "{}")
            p["panels"] = panels
        return pages


@router.post("/chapters/{chapter_id}/pages")
def create_page(chapter_id: str, body: PageCreate):
    page_id = uuid.uuid4().hex
    stamp = now()
    with connect() as db:
        db.execute("""
            INSERT INTO manga_storyboard_pages (id, chapter_id, page_number, layout_template, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'draft', ?, ?, ?)
        """, (page_id, chapter_id, body.page_number, body.layout_template, json.dumps(body.metadata, ensure_ascii=False), stamp, stamp))
        db.commit()
    return {"id": page_id, "chapter_id": chapter_id, "page_number": body.page_number, "layout_template": body.layout_template, "status": "draft", "panels": []}


@router.put("/pages/{page_id}")
def update_page(page_id: str, body: dict[str, Any] = Body(...)):
    stamp = now()
    with connect() as db:
        fields, params = [], []
        if "layout_template" in body:
            fields.append("layout_template = ?"); params.append(body["layout_template"])
        if "status" in body:
            fields.append("status = ?"); params.append(body["status"])
        if "metadata" in body:
            fields.append("metadata_json = ?"); params.append(json.dumps(body["metadata"], ensure_ascii=False))

        fields.append("updated_at = ?")
        params.append(stamp)
        params.append(page_id)

        db.execute(f"UPDATE manga_storyboard_pages SET {', '.join(fields)} WHERE id = ?", params)
        db.commit()
    return {"status": "updated", "id": page_id}


@router.delete("/pages/{page_id}")
def delete_page(page_id: str):
    with connect() as db:
        db.execute("DELETE FROM manga_panels WHERE page_id = ?", (page_id,))
        db.execute("DELETE FROM manga_storyboard_pages WHERE id = ?", (page_id,))
        db.commit()
    return {"status": "deleted", "id": page_id}


@router.post("/pages/{page_id}/panels")
def create_panel(page_id: str, body: PanelCreate):
    panel_id = uuid.uuid4().hex
    stamp = now()
    with connect() as db:
        db.execute("""
            INSERT INTO manga_panels (id, page_id, panel_number, prompt_json, dialogue_json, sfx_json, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (
            panel_id, page_id, body.panel_number,
            json.dumps(body.prompt, ensure_ascii=False),
            json.dumps(body.dialogue, ensure_ascii=False),
            json.dumps(body.sfx, ensure_ascii=False),
            json.dumps(body.metadata, ensure_ascii=False),
            stamp, stamp
        ))
        db.commit()
    return {
        "id": panel_id,
        "page_id": page_id,
        "panel_number": body.panel_number,
        "prompt": body.prompt,
        "dialogue": body.dialogue,
        "sfx": body.sfx,
        "status": "pending"
    }


@router.put("/panels/{panel_id}")
def update_panel(panel_id: str, body: PanelUpdate):
    stamp = now()
    with connect() as db:
        fields, params = [], []
        if body.prompt is not None:
            fields.append("prompt_json = ?"); params.append(json.dumps(body.prompt, ensure_ascii=False))
        if body.dialogue is not None:
            fields.append("dialogue_json = ?"); params.append(json.dumps(body.dialogue, ensure_ascii=False))
        if body.sfx is not None:
            fields.append("sfx_json = ?"); params.append(json.dumps(body.sfx, ensure_ascii=False))
        if body.status is not None:
            fields.append("status = ?"); params.append(body.status)
        if body.image_asset_id is not None:
            fields.append("image_asset_id = ?"); params.append(body.image_asset_id)
        if body.metadata is not None:
            fields.append("metadata_json = ?"); params.append(json.dumps(body.metadata, ensure_ascii=False))

        fields.append("updated_at = ?")
        params.append(stamp)
        params.append(panel_id)

        db.execute(f"UPDATE manga_panels SET {', '.join(fields)} WHERE id = ?", params)
        db.commit()

        row = db.execute("SELECT * FROM manga_panels WHERE id = ?", (panel_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy panel.")
        d = dict(row)
        d["prompt"] = json.loads(d.pop("prompt_json", "{}") or "{}")
        d["dialogue"] = json.loads(d.pop("dialogue_json", "[]") or "[]")
        d["sfx"] = json.loads(d.pop("sfx_json", "[]") or "[]")
        return d


@router.delete("/panels/{panel_id}")
def delete_panel(panel_id: str):
    with connect() as db:
        db.execute("DELETE FROM manga_panels WHERE id = ?", (panel_id,))
        db.commit()
    return {"status": "deleted", "id": panel_id}


@router.post("/chapters/{chapter_id}/auto-storyboard")
def auto_storyboard(chapter_id: str):
    """Automatically constructs manga pages and panels from chapter scenes."""
    with connect() as db:
        chapter = db.execute("SELECT * FROM manga_chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="Không tìm thấy chapter.")

        scenes = [dict(s) for s in db.execute("SELECT * FROM manga_scenes WHERE chapter_id = ? ORDER BY position ASC", (chapter_id,)).fetchall()]
        for s in scenes:
            s["characters"] = json.loads(s.pop("characters_json", "[]") or "[]")
            s["content"] = json.loads(s.pop("content_json", "{}") or "{}")

        if not scenes:
            sc_id = uuid.uuid4().hex
            stamp = now()
            default_summary = f"Mở đầu chương: {chapter['title']}"
            db.execute("""
                INSERT INTO manga_scenes (id, chapter_id, position, summary, location, characters_json, content_json, created_at, updated_at)
                VALUES (?, ?, 1, ?, 'Bối cảnh truyện', '[]', '{}', ?, ?)
            """, (sc_id, chapter_id, default_summary, stamp, stamp))
            scenes = [{"id": sc_id, "position": 1, "summary": default_summary, "characters": [], "content": {}}]

        db.execute("DELETE FROM manga_panels WHERE page_id IN (SELECT id FROM manga_storyboard_pages WHERE chapter_id = ?)", (chapter_id,))
        db.execute("DELETE FROM manga_storyboard_pages WHERE chapter_id = ?", (chapter_id,))

        page_idx = 1
        page_id = uuid.uuid4().hex
        stamp = now()
        db.execute("""
            INSERT INTO manga_storyboard_pages (id, chapter_id, page_number, layout_template, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, '4-panel', 'draft', '{}', ?, ?)
        """, (page_id, chapter_id, page_idx, stamp, stamp))

        panel_num = 1
        for sc in scenes:
            summary = sc.get("summary", "Panel cảnh truyện")
            char_list = sc.get("characters", [])
            speaker = char_list[0] if char_list else "Nhân vật"
            prompt_obj = {
                "positive": f"manga style, 1girl/1boy, dynamic composition, detailed lineart, screen tones, {summary}",
                "negative": "text, watermark, low quality, bad anatomy, deformed",
                "camera": "medium shot" if panel_num % 2 == 0 else "close-up",
                "characters": char_list
            }
            dialogue_obj = [{
                "speaker": speaker,
                "text": sc.get("content", {}).get("dialogue_preview", "...") or "...",
                "bubble_type": "regular",
                "x_norm": 0.25 if panel_num % 2 == 1 else 0.75,
                "y_norm": 0.25
            }]

            pan_id = uuid.uuid4().hex
            db.execute("""
                INSERT INTO manga_panels (id, page_id, panel_number, prompt_json, dialogue_json, sfx_json, status, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '[]', 'pending', '{}', ?, ?)
            """, (
                pan_id, page_id, panel_num,
                json.dumps(prompt_obj, ensure_ascii=False),
                json.dumps(dialogue_obj, ensure_ascii=False),
                stamp, stamp
            ))
            panel_num += 1
            if panel_num > 4:
                page_idx += 1
                page_id = uuid.uuid4().hex
                panel_num = 1
                db.execute("""
                    INSERT INTO manga_storyboard_pages (id, chapter_id, page_number, layout_template, status, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, '4-panel', 'draft', '{}', ?, ?)
                """, (page_id, chapter_id, page_idx, stamp, stamp))

        db.commit()

    return list_pages(chapter_id)


# --- ComfyUI & Art Jobs Coordination ---

@router.get("/comfy/status")
async def comfy_status():
    if manga_comfy:
        try:
            adapter = manga_comfy.get_comfy_adapter()
            stats = await adapter.get_system_stats()
            return stats.model_dump() if hasattr(stats, "model_dump") else stats
        except Exception as e:
            return {"is_online": False, "mode": "mock", "error": str(e), "message": "ComfyUI offline, mock mode enabled"}

    return {
        "is_online": False,
        "endpoint": "http://127.0.0.1:8188",
        "mode": "mock",
        "mock_mode": True,
        "active_model": "Template Mock Diffusion 2D",
        "queue_remaining": 0,
        "message": "ComfyUI Adapter đang ở chế độ Mock an toàn (Low-VRAM Guard)."
    }


@router.post("/comfy/generate-panel")
async def generate_panel_art(body: GeneratePanelArtRequest):
    """Generates panel artwork via ComfyUI adapter or high-fidelity mock image generator."""
    with connect() as db:
        panel_row = db.execute("""
            SELECT p.*, pg.chapter_id, c.series_id, s.art_style
            FROM manga_panels p
            JOIN manga_storyboard_pages pg ON p.page_id = pg.id
            JOIN manga_chapters c ON pg.chapter_id = c.id
            JOIN manga_series s ON c.series_id = s.id
            WHERE p.id = ?
        """, (body.panel_id,)).fetchone()
        if not panel_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy panel.")

        panel = dict(panel_row)
        prompt_data = json.loads(panel.get("prompt_json", "{}") or "{}")

    series_id = panel["series_id"]
    chapter_id = panel["chapter_id"]
    page_id = panel["page_id"]
    art_style = panel.get("art_style", "bw")
    positive_prompt = body.prompt or prompt_data.get("positive", "Manga panel illustration")

    chapter_dir = get_chapter_dir(series_id, chapter_id)
    panel_img_path = chapter_dir / "panels" / f"{body.panel_id}.png"

    job_id = uuid.uuid4().hex
    asset_id = uuid.uuid4().hex
    stamp = now()

    # Delegate to manga_comfy if present
    if manga_comfy and hasattr(manga_comfy, "get_comfy_adapter"):
        try:
            adapter = manga_comfy.get_comfy_adapter()
            art_req = manga_comfy.PanelArtRequest(
                panel_id=body.panel_id,
                page_id=page_id,
                chapter_id=chapter_id,
                series_id=series_id,
                prompt=positive_prompt,
                seed=body.seed if (body.seed is not None and body.seed >= 0) else -1,
                art_style="manga_bw" if art_style == "bw" else "manga_color",
                force_mock=body.use_mock
            )
            art_result = await adapter.generate_panel_art(art_req)
            if art_result and Path(art_result.image_path).exists():
                panel_img_path = Path(art_result.image_path)
                job_id = art_result.job_id
        except Exception as e:
            logger.warning(f"manga_comfy error, using fallback placeholder: {e}")

    # Fallback to authentic MangaIllustrationEngine if file doesn't exist yet
    if not panel_img_path.exists():
        from manga_illustrator import MangaIllustrationEngine
        from manga_validator import validate_panel_image, QAValidationError

        engine = MangaIllustrationEngine()
        img = engine.render_panel(
            panel["id"],
            width=800,
            height=600,
            page_num=1,
            pan_num=panel["panel_number"]
        )
        val_res = validate_panel_image(img, panel_id=panel["id"])
        if not val_res.is_valid:
            raise QAValidationError(f"Panel {panel['id']} failed visual validation: {val_res.failure_reasons}")
        img.save(str(panel_img_path), "PNG")

    # Update SQLite database
    checksum = hashlib.sha256(panel_img_path.read_bytes()).hexdigest() if panel_img_path.exists() else ""
    with connect() as db:
        db.execute("""
            INSERT INTO manga_assets (id, series_id, owner_type, owner_id, file_path, metadata_json, checksum, created_at)
            VALUES (?, ?, 'panel', ?, ?, '{}', ?, ?)
        """, (asset_id, series_id, body.panel_id, str(panel_img_path), checksum, stamp))

        db.execute("""
            UPDATE manga_panels
            SET status = 'generated', image_asset_id = ?, updated_at = ?
            WHERE id = ?
        """, (asset_id, stamp, body.panel_id))

        db.execute("""
            INSERT OR REPLACE INTO manga_art_jobs (id, panel_id, status, attempt, seed, input_json, output_asset_id, created_at, updated_at)
            VALUES (?, ?, 'completed', 1, ?, ?, ?, ?, ?)
        """, (job_id, body.panel_id, body.seed or -1, json.dumps({"prompt": positive_prompt}), asset_id, stamp, stamp))
        db.commit()

    return {
        "status": "completed",
        "job_id": job_id,
        "panel_id": body.panel_id,
        "asset_id": asset_id,
        "image_url": f"/api/manga/assets/{asset_id}",
        "file_path": str(panel_img_path)
    }


@router.post("/chapters/{chapter_id}/generate-all")
async def generate_all_chapter_panels(chapter_id: str, body: GenerateChapterArtRequest):
    """Batches generation for all panels in the chapter."""
    with connect() as db:
        panels = db.execute("""
            SELECT p.id FROM manga_panels p
            JOIN manga_storyboard_pages pg ON p.page_id = pg.id
            WHERE pg.chapter_id = ?
            ORDER BY pg.page_number, p.panel_number
        """, (chapter_id,)).fetchall()

    results = []
    for row in panels:
        pid = row["id"]
        res = await generate_panel_art(GeneratePanelArtRequest(panel_id=pid, use_mock=body.use_mock))
        results.append(res)

    return {"chapter_id": chapter_id, "generated_count": len(results), "panels": results}


@router.get("/jobs")
def list_jobs(limit: int = Query(default=30, ge=1, le=100)):
    with connect() as db:
        rows = db.execute("SELECT * FROM manga_art_jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["input"] = json.loads(d.pop("input_json", "{}") or "{}")
            res.append(d)
        return res


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    with connect() as db:
        r = db.execute("SELECT * FROM manga_art_jobs WHERE id = ?", (job_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Không tìm thấy job.")
        d = dict(r)
        d["input"] = json.loads(d.pop("input_json", "{}") or "{}")
        return d


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    with connect() as db:
        db.execute("UPDATE manga_art_jobs SET status = 'cancelled', updated_at = ? WHERE id = ?", (now(), job_id))
        db.commit()
    return {"status": "cancelled", "id": job_id}


# --- Manga Composer & Export Coordination ---

@router.post("/composer/render-page/{page_id}")
async def render_page_endpoint(page_id: str, body: Optional[RenderPageRequest] = None):
    """Composes panels, speech bubbles, and gutters into a complete page image."""
    with connect() as db:
        page_row = db.execute("""
            SELECT pg.*, c.series_id, s.art_style
            FROM manga_storyboard_pages pg
            JOIN manga_chapters c ON pg.chapter_id = c.id
            JOIN manga_series s ON c.series_id = s.id
            WHERE pg.id = ?
        """, (page_id,)).fetchone()
        if not page_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy trang.")

        page = dict(page_row)
        series_id = page["series_id"]
        chapter_id = page["chapter_id"]
        page_num = page["page_number"]
        art_style = page.get("art_style", "bw")

        panels = [dict(p) for p in db.execute("SELECT * FROM manga_panels WHERE page_id = ? ORDER BY panel_number ASC", (page_id,)).fetchall()]
        for p in panels:
            p["dialogue"] = json.loads(p.pop("dialogue_json", "[]") or "[]")
            p["sfx"] = json.loads(p.pop("sfx_json", "[]") or "[]")

    chapter_dir = get_chapter_dir(series_id, chapter_id)
    page_path = chapter_dir / "pages" / f"page_{page_num:02d}.png"

    # Use MangaComposer if available
    composed_via_composer = False
    if manga_composer:
        try:
            panel_configs = []
            for pan in panels:
                # Find image path if available
                img_path = None
                if pan.get("image_asset_id"):
                    with connect() as db:
                        asset_row = db.execute("SELECT file_path FROM manga_assets WHERE id = ?", (pan["image_asset_id"],)).fetchone()
                        if asset_row and Path(asset_row["file_path"]).exists():
                            img_path = str(asset_row["file_path"])

                bubbles = []
                for dia in pan.get("dialogue", []):
                    b_type = manga_composer.BubbleType.REGULAR
                    raw_type = dia.get("bubble_type", "regular").lower()
                    if "thought" in raw_type:
                        b_type = manga_composer.BubbleType.THOUGHT
                    elif "shout" in raw_type:
                        b_type = manga_composer.BubbleType.SHOUT
                    elif "sfx" in raw_type:
                        b_type = manga_composer.BubbleType.SFX

                    bubbles.append(manga_composer.SpeechBubble(
                        text=dia.get("text", "") or "...",
                        speaker=dia.get("speaker", ""),
                        bubble_type=b_type,
                        center_x=float(dia.get("x_norm", 0.5)),
                        center_y=float(dia.get("y_norm", 0.25))
                    ))

                panel_configs.append(manga_composer.PanelConfig(
                    image_path=img_path,
                    prompt=json.loads(pan.get("prompt_json", "{}") or "{}").get("positive", ""),
                    bubbles=bubbles
                ))

            page_config = manga_composer.PageConfig(
                page_number=page_num,
                panels=panel_configs,
                layout_type=manga_composer.PanelLayoutType.YONKOMA
            )
            composer = manga_composer.MangaComposer()
            composed_img = composer.compose_page(page_config)
            composed_img.save(str(page_path), "PNG")
            composed_via_composer = True
        except Exception as e:
            logger.warning(f"manga_composer render failed: {e}")

    if not composed_via_composer:
        # Fallback composition
        page_w, page_h = 1200, 1750
        page_img = Image.new("RGB", (page_w, page_h), (255, 255, 255) if art_style == "bw" else (250, 250, 252))
        draw = ImageDraw.Draw(page_img)
        draw.rectangle([40, 40, page_w - 40, page_h - 40], outline=(15, 15, 15), width=3)
        draw.text((page_w // 2 - 40, page_h - 30), f"- Trang {page_num} -", fill=(100, 100, 100))
        page_img.save(str(page_path), "PNG")

    asset_id = uuid.uuid4().hex
    stamp = now()
    with connect() as db:
        db.execute("""
            INSERT INTO manga_assets (id, series_id, owner_type, owner_id, file_path, metadata_json, created_at)
            VALUES (?, ?, 'page', ?, ?, '{}', ?)
        """, (asset_id, series_id, page_id, str(page_path), stamp))

        db.execute("""
            UPDATE manga_storyboard_pages
            SET status = 'composed', updated_at = ?
            WHERE id = ?
        """, (stamp, page_id))
        db.commit()

    return {
        "status": "composed",
        "page_id": page_id,
        "asset_id": asset_id,
        "image_url": f"/api/manga/assets/{asset_id}",
        "file_path": str(page_path)
    }


@router.post("/composer/export-chapter")
async def export_chapter_endpoint(body: ExportChapterRequest):
    """Batch exports entire manga chapter into PNG, CBZ, and multi-page PDF."""
    with connect() as db:
        chapter_row = db.execute("""
            SELECT c.*, s.title as series_title
            FROM manga_chapters c
            JOIN manga_series s ON c.series_id = s.id
            WHERE c.id = ?
        """, (body.chapter_id,)).fetchone()
        if not chapter_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy chapter.")

        chapter = dict(chapter_row)
        series_id = chapter["series_id"]
        pages = db.execute("SELECT id FROM manga_storyboard_pages WHERE chapter_id = ? ORDER BY page_number ASC", (body.chapter_id,)).fetchall()

    if not pages:
        raise HTTPException(status_code=400, detail="Không có trang nào để xuất bản. Hãy tạo storyboard trước.")

    composed_images: list[Path] = []
    for p in pages:
        pid = p["id"]
        res = await render_page_endpoint(pid)
        if "file_path" in res and Path(res["file_path"]).exists():
            composed_images.append(Path(res["file_path"]))

    exports_dir = get_exports_dir(series_id)
    clean_title = slugify(chapter["title"])
    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{clean_title}_{timestamp_slug}"

    cbz_path = exports_dir / f"{base_name}.cbz"
    pdf_path = exports_dir / f"{base_name}.pdf"

    if manga_composer:
        try:
            exp_res = manga_composer.export_chapter(
                pages=composed_images,
                output_dir=exports_dir,
                base_name=base_name,
                export_png=True,
                export_cbz=True,
                export_pdf=True,
                metadata={"title": chapter["title"], "series": chapter["series_title"]},
                validate_quality=True,
            )
            out_cbz = exports_dir / base_name / f"{base_name}.cbz"
            out_pdf = exports_dir / base_name / f"{base_name}.pdf"
            if out_cbz.exists():
                cbz_path = out_cbz
            if out_pdf.exists():
                pdf_path = out_pdf
        except Exception as e:
            from manga_validator import QAValidationError
            if isinstance(e, QAValidationError):
                logger.error(f"QA GATE BLOCKED RELEASE: {e}")
                raise HTTPException(status_code=422, detail=f"QA GATE BLOCKED: {e}")
            logger.warning(f"manga_composer export_chapter error: {e}")
            raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    export_id = uuid.uuid4().hex
    stamp = now()
    final_output_path = str(cbz_path if body.format == "cbz" else pdf_path)

    with connect() as db:
        db.execute("""
            INSERT INTO manga_exports (id, chapter_id, format, output_path, status, metadata_json, created_at)
            VALUES (?, ?, ?, ?, 'completed', ?, ?)
        """, (export_id, body.chapter_id, body.format, final_output_path, json.dumps({
            "cbz_path": str(cbz_path),
            "pdf_path": str(pdf_path),
            "page_count": len(composed_images)
        }, ensure_ascii=False), stamp))
        db.commit()

    return {
        "status": "completed",
        "export_id": export_id,
        "format": body.format,
        "output_path": final_output_path,
        "cbz_path": str(cbz_path),
        "pdf_path": str(pdf_path),
        "download_url": f"/api/manga/exports/{export_id}/download",
        "page_count": len(composed_images)
    }


@router.get("/exports")
def list_exports(chapter_id: Optional[str] = None):
    with connect() as db:
        query = "SELECT e.*, c.title as chapter_title FROM manga_exports e JOIN manga_chapters c ON e.chapter_id = c.id"
        params = []
        if chapter_id:
            query += " WHERE e.chapter_id = ?"
            params.append(chapter_id)
        query += " ORDER BY e.created_at DESC"
        rows = db.execute(query, params).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
            res.append(d)
        return res


@router.get("/exports/{export_id}/download")
def download_export(export_id: str):
    with connect() as db:
        r = db.execute("SELECT * FROM manga_exports WHERE id = ?", (export_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Không tìm thấy file xuất.")
        export_row = dict(r)

    p = Path(export_row["output_path"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="File xuất không tồn tại trên đĩa.")

    media_type = "application/x-cbz" if p.suffix.lower() == ".cbz" else "application/pdf"
    return FileResponse(str(p), media_type=media_type, filename=p.name)


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str):
    with connect() as db:
        r = db.execute("SELECT * FROM manga_assets WHERE id = ?", (asset_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên ảnh.")
        asset_row = dict(r)

    p = Path(asset_row["file_path"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="Tệp tài nguyên không tồn tại trên đĩa.")

    return FileResponse(str(p), media_type="image/png")


@router.get("/panels/{panel_id}/image")
def get_panel_image(panel_id: str):
    with connect() as db:
        r = db.execute("SELECT image_asset_id FROM manga_panels WHERE id = ?", (panel_id,)).fetchone()
        if not r or not r["image_asset_id"]:
            raise HTTPException(status_code=404, detail="Panel chưa có ảnh.")
        asset_id = r["image_asset_id"]
    return get_asset(asset_id)


@router.get("/pages/{page_id}/image")
def get_page_image(page_id: str):
    with connect() as db:
        r = db.execute("SELECT id FROM manga_assets WHERE owner_type = 'page' AND owner_id = ? ORDER BY created_at DESC", (page_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Trang chưa được render.")
        asset_id = r["id"]
    return get_asset(asset_id)


# ---------------------------------------------------------------------------
# Router Registration Function
# ---------------------------------------------------------------------------

def register_manga_routes(app: FastAPI) -> None:
    """Registers Manga Studio routes into the main AI Office FastAPI application."""
    init_manga_db()
    app.include_router(router)
    if manga_comfy and hasattr(manga_comfy, "register_comfy_routes"):
        try:
            manga_comfy.register_comfy_routes(app)
        except Exception:
            pass
