# -*- coding: utf-8 -*-
"""
tests/test_library_and_chat_images.py
=====================================
Tests for Media & File Library and Chat Images Serving.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app.main import app
from app.library_service import list_library_items, delete_library_item


def test_library_items_api():
    client = TestClient(app)
    resp = client.get("/api/library/items")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["count"] > 0
    items = data["items"]
    # Check item schema
    item = items[0]
    for key in ["id", "name", "title", "category", "type", "media_type", "url"]:
        assert key in item, f"Key {key} missing from library item"


def test_library_filter_generated():
    client = TestClient(app)
    resp = client.get("/api/library/items?filter=generated")
    assert resp.status_code == 200
    data = resp.json()
    for it in data["items"]:
        assert it["category"] == "generated"


def test_chat_images_serving_across_folders():
    client = TestClient(app)
    # Test Hu Tao generated image
    resp_hutao = client.get("/api/chat/images/chat_20261124_203955_0642d4f1.png")
    assert resp_hutao.status_code == 200
    assert resp_hutao.headers["content-type"] == "image/png"
    assert len(resp_hutao.content) > 100_000

    # Test mock_hutao_stream image (which the user had in chat)
    resp_stream = client.get("/api/chat/images/mock_hutao_stream.png")
    assert resp_stream.status_code == 200
    assert resp_stream.headers["content-type"] == "image/png"

    # Test Raiden image across folders (in raiden_tests or genshin_panels)
    resp_raiden = client.get("/api/chat/images/raiden_combat_action.png")
    assert resp_raiden.status_code == 200
    assert resp_raiden.headers["content-type"] == "image/png"


def test_nonexistent_image_404():
    client = TestClient(app)
    resp = client.get("/api/chat/images/totally_fake_image_9999.png")
    assert resp.status_code == 404
