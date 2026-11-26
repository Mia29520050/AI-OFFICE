"""SQLite WAL-backed Job Queue with timeout, progress tracking, and cancellation."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException

from app.config import DATA_DIR
from app.vram_guard import get_system_health

DB_PATH = DATA_DIR / "office.db"
_RUNNING_TASKS: dict[str, asyncio.Task[Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL;")
    return db


def ensure_jobs_table() -> None:
    with _connect() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                result TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        db.commit()


def create_job(kind: str, title: str) -> str:
    ensure_jobs_table()
    job_id = uuid.uuid4().hex[:12]
    stamp = _now()
    with _connect() as db:
        db.execute(
            "INSERT INTO jobs (id, kind, title, status, progress, created_at, updated_at) VALUES (?, ?, ?, 'queued', 0, ?, ?)",
            (job_id, kind, title, stamp, stamp),
        )
        db.commit()
    return job_id


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _connect() as db:
        db.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))
        db.commit()


def get_job(job_id: str) -> dict[str, Any] | None:
    ensure_jobs_table()
    with _connect() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_jobs(limit: int = 30) -> list[dict[str, Any]]:
    ensure_jobs_table()
    with _connect() as db:
        rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def cancel_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    task = _RUNNING_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    update_job(job_id, status="cancelled", error="Cancelled by user")
    return True


async def submit_async_job(
    kind: str,
    title: str,
    coro_fn: Callable[[], Awaitable[Any]],
    timeout_secs: float = 300.0,
) -> str:
    """Queue an async job with timeout protection and SQLite status tracking."""
    job_id = create_job(kind, title)

    async def _runner() -> None:
        update_job(job_id, status="running", progress=10)
        try:
            res = await asyncio.wait_for(coro_fn(), timeout=timeout_secs)
            res_str = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
            update_job(job_id, status="completed", progress=100, result=res_str)
        except asyncio.CancelledError:
            update_job(job_id, status="cancelled", error="Cancelled by user")
        except asyncio.TimeoutError:
            update_job(job_id, status="failed", error=f"Job timed out after {timeout_secs}s")
        except Exception as exc:
            update_job(job_id, status="failed", error=str(exc))
        finally:
            _RUNNING_TASKS.pop(job_id, None)

    _RUNNING_TASKS[job_id] = asyncio.create_task(_runner())
    return job_id


def register_routes(app: FastAPI) -> None:
    @app.get("/api/health/resources")
    async def api_health_resources() -> dict[str, Any]:
        return await get_system_health()

    @app.get("/api/jobs")
    async def api_list_jobs(limit: int = 30) -> dict[str, Any]:
        return {"jobs": list_jobs(limit=limit)}

    @app.get("/api/jobs/{job_id}")
    async def api_get_job(job_id: str) -> dict[str, Any]:
        job = get_job(job_id)
        if not job:
            raise HTTPException(404, "Không tìm thấy job.")
        return job

    @app.post("/api/jobs/{job_id}/cancel")
    async def api_cancel_job(job_id: str) -> dict[str, Any]:
        if not cancel_job(job_id):
            raise HTTPException(404, "Không tìm thấy job để hủy.")
        return {"cancelled": True, "job_id": job_id}
