from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.setup_claude_ollama import (
    check_ollama_alive,
    get_available_models,
    set_active_office_model,
)


def test_check_ollama_alive_success():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert check_ollama_alive() is True


def test_check_ollama_alive_offline():
    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        assert check_ollama_alive() is False


def test_get_available_models():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen2.5-coder:7b"}, {"name": "claude-office"}]},
        )
        models = get_available_models()
        assert "qwen2.5-coder:7b" in models
        assert "claude-office" in models


def test_set_active_office_model(tmp_path: Path):
    db_file = tmp_path / "office.db"
    conn = sqlite3.connect(str(db_file))
    with conn:
        conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES('model_config', ?)",
            (json.dumps({"local_model": "old-model"}),),
        )
    conn.close()

    assert set_active_office_model("claude-office", db_file) is True

    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key = 'model_config'")
    val = json.loads(cur.fetchone()[0])
    conn.close()
    assert val["local_model"] == "claude-office"
