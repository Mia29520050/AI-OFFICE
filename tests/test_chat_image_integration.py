# -*- coding: utf-8 -*-
"""
tests/test_chat_image_integration.py
====================================
End-to-end integration tests for merging Studio Sáng tạo into Chat:
1. Verifies intent detection on various phrases ('tạo ảnh Hutao', 'vẽ Raiden Shogun').
2. Verifies /api/chat image generation handling and response format.
3. Verifies /api/chat/images/{filename} static image serving.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app.main import app
from app.chat_image_handler import (
    detect_image_generation_intent,
    CHAT_IMAGES_DIR,
)


def test_intent_detection():
    # Valid positive cases
    cases = [
        ("tạo ảnh Hutao", True, "Hutao", ""),
        ("vẽ Raiden Shogun", True, "Raiden Shogun", ""),
        ("hãy vẽ cho tôi bức ảnh Hutao đang cười", True, "Hutao", "đang cười"),
        ("vẽ một cô gái anime tóc trắng", True, "một cô gái anime tóc trắng", ""),
        ("sinh ảnh Zhongli", True, "Zhongli", ""),
        ("draw anime girl with red eyes", True, "anime girl with red eyes", ""),
    ]
    for msg, expected_intent, expected_subj, expected_extra in cases:
        is_intent, subj, extra = detect_image_generation_intent(msg)
        assert is_intent == expected_intent, f"Failed intent on '{msg}'"
        assert subj.lower() == expected_subj.lower(), f"Failed subject on '{msg}': got '{subj}'"
        assert extra.lower() == expected_extra.lower(), f"Failed extra on '{msg}': got '{extra}'"

    # Negative / non-image cases
    negatives = [
        "hôm nay ngày mấy",
        "bây giờ là mấy giờ",
        "làm thế nào để tạo ảnh bằng Python",
        "tại sao không vẽ được",
        "hướng dẫn cách tạo ảnh",
    ]
    for msg in negatives:
        is_intent, _, _ = detect_image_generation_intent(msg)
        assert not is_intent, f"False positive intent on '{msg}'"


def test_chat_image_endpoint_serving():
    client = TestClient(app)
    # Ensure test file exists in CHAT_IMAGES_DIR
    test_img = CHAT_IMAGES_DIR / "test_verify.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")

    resp = client.get("/api/chat/images/test_verify.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"

    resp_404 = client.get("/api/chat/images/nonexistent_image_12345.png")
    assert resp_404.status_code == 404


from unittest.mock import patch, AsyncMock


def test_chat_post_image_generation_mocked():
    """Fast integration test for /api/chat with mocked ComfyUI."""
    client = TestClient(app)
    mock_res = {
        "success": True,
        "text": "Đã tạo ảnh cho **Hu Tao** theo yêu cầu của bạn!\n\n![Hu Tao](/api/chat/images/mock_hutao_test.png)",
        "image_url": "/api/chat/images/mock_hutao_test.png",
        "image_path": "mock_path.png",
        "character_name": "Hu Tao",
        "prompt": "hutao prompt",
    }

    with patch("app.main.handle_chat_image_generation", new=AsyncMock(return_value=mock_res)):
        payload = {
            "message": "tạo ảnh Hutao",
            "agent": "CEO",
            "attachments": [],
        }
        resp = client.post("/api/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "Hu Tao" in data["answer"]
        assert "Anima DeltaMix 2.9B" in data["model"]
        assert "/api/chat/images/mock_hutao_test.png" in data["answer"]
        assert "![Hu Tao](/api/chat/images/mock_hutao_test.png)" in data["answer"]
        assert data.get("image_url") == "/api/chat/images/mock_hutao_test.png"


def test_chat_stream_image_generation_mocked():
    """Fast integration test for /api/chat/stream with mocked ComfyUI."""
    client = TestClient(app)
    mock_res = {
        "success": True,
        "text": "Đã tạo ảnh cho **Hu Tao** theo yêu cầu của bạn!\n\n![Hu Tao](/api/chat/images/mock_hutao_stream.png)",
        "image_url": "/api/chat/images/mock_hutao_stream.png",
        "image_path": "mock_path.png",
        "character_name": "Hu Tao",
        "prompt": "hutao prompt",
    }

    with patch("app.main.handle_chat_image_generation", new=AsyncMock(return_value=mock_res)):
        payload = {
            "message": "tạo ảnh Hutao",
            "agent": "CEO",
            "attachments": [],
        }
        resp = client.post("/api/chat/stream", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "Hu Tao" in body
        assert "/api/chat/images/mock_hutao_stream.png" in body
        assert "Anima DeltaMix 2.9B" in body


@pytest.mark.skipif(os.getenv("SKIP_LIVE_COMFY") == "1", reason="Skipping live ComfyUI test")
def test_chat_post_image_generation_live():
    """Live end-to-end test verifying actual ComfyUI execution."""
    client = TestClient(app)
    payload = {
        "message": "tạo ảnh Hutao",
        "agent": "CEO",
        "attachments": [],
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "Hu Tao" in data["answer"]
    assert "Anima DeltaMix 2.9B" in data["model"]
    assert "/api/chat/images/" in data["answer"]
    assert "![Hu Tao](/api/chat/images/" in data["answer"]
