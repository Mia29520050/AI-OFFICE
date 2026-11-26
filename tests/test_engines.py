"""Tests for EngineManager (Windows Job Object, lazy start, shutdown)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.engines import EngineManager


def test_engine_manager_init_and_shutdown():
    em = EngineManager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    em.procs["test_engine"] = mock_proc

    em.shutdown()
    mock_proc.terminate.assert_called_once()
    assert em.procs == {}


def test_engine_manager_ensure_skips_when_alive():
    em = EngineManager()
    with patch.object(em, "_alive", return_value=True):
        ok = em.ensure("ollama", ["ollama", "serve"], ".", "http://127.0.0.1:11434/api/tags")
        assert ok is True
        assert "ollama" not in em.procs
