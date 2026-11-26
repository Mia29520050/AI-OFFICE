"""Tests for VRAM Guard, SQLite WAL Job Queue, Config, and Resource Health Monitor."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import COMFY_DIR, DATA_DIR, ENGINE_DIR, EXPORT_DIR, ROOT_DIR
from app.job_queue import cancel_job, create_job, get_job, list_jobs, submit_async_job, update_job
from app.main import app
from app.vram_guard import free_comfy, free_ollama, get_system_health, run_heavy


def test_centralized_config_paths():
    assert ROOT_DIR.exists()
    assert ENGINE_DIR == ROOT_DIR / "engine"
    assert EXPORT_DIR == ROOT_DIR / "Export"
    assert DATA_DIR == ROOT_DIR / "data"
    assert COMFY_DIR == ENGINE_DIR / "ComfyUI"


@pytest.mark.asyncio
async def test_vram_guard_cross_unload():
    ran = []

    async def dummy_task():
        ran.append("ok")
        return 42

    with patch("app.vram_guard.free_ollama", new_callable=AsyncMock, return_value=True) as m_ollama, \
         patch("app.vram_guard.free_comfy", new_callable=AsyncMock, return_value=True) as m_comfy:
        res1 = await run_heavy("comfy", dummy_task)
        assert res1 == 42
        m_ollama.assert_awaited_once()
        m_comfy.assert_not_awaited()

        m_ollama.reset_mock()
        res2 = await run_heavy("llm", dummy_task)
        assert res2 == 42
        m_comfy.assert_awaited_once()
        m_ollama.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_queue_lifecycle_and_cancel():
    jid = create_job("video", "Test Wan 1.3B")
    job = get_job(jid)
    assert job is not None
    assert job["status"] == "queued"

    update_job(jid, status="running", progress=50)
    assert get_job(jid)["progress"] == 50

    assert cancel_job(jid) is True
    assert get_job(jid)["status"] == "cancelled"
    assert any(j["id"] == jid for j in list_jobs(10))


@pytest.mark.asyncio
async def test_submit_async_job_timeout():
    async def slow():
        await asyncio.sleep(2.0)
        return "done"

    jid = await submit_async_job("3d", "Slow Blender", slow, timeout_secs=0.05)
    await asyncio.sleep(0.15)
    job = get_job(jid)
    assert job is not None
    assert job["status"] == "failed"
    assert "timed out" in job["error"].lower()


def test_health_and_jobs_endpoints():
    client = TestClient(app)
    r_health = client.get("/api/health/resources")
    assert r_health.status_code == 200
    data = r_health.json()
    assert "vram" in data and "ram" in data and "engines" in data

    r_jobs = client.get("/api/jobs")
    assert r_jobs.status_code == 200
    assert "jobs" in r_jobs.json()
