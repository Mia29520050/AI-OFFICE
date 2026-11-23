"""Unit tests for Motion Comic REST API routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import io
import base64

from app.motion_comic_routes import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_voices(client):
    res = client.get("/api/motion-comic/voices")
    assert res.status_code == 200
    data = res.json()
    assert "voices" in data
    assert len(data["voices"]) >= 5


def test_api_presets(client):
    res = client.get("/api/motion-comic/presets")
    assert res.status_code == 200
    data = res.json()
    assert "aspect_ratios" in data
    assert "motion_styles" in data
    assert "sfx_presets" in data


def test_api_render_validation_error(client):
    # Empty panels should return 400
    res = client.post("/api/motion-comic/render", json={"panels": []})
    assert res.status_code == 400


def test_api_render_with_base64_panels(client):
    # Create small 100x100 base64 PNG
    img = Image.new("RGB", (200, 200), color=(120, 40, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    payload = {
        "panels": [
            {
                "panel_id": "api_test_p1",
                "image_data": b64_data,
                "text": "Kiểm thử API thành công!",
                "speaker": "AI Tester",
                "motion_style": "zoom_in",
                "sfx": "boom",
            }
        ],
        "aspect_ratio": "16:9",
        "fps": 30,
        "enable_anime4k": False,
        "output_name": "api_render_test",
    }

    res = client.post("/api/motion-comic/render", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["resolution"] == [1920, 1080]
    assert data["panel_count"] == 1
    assert "video_url" in data
    assert "srt_url" in data
