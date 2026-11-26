# -*- coding: utf-8 -*-
"""
Tests for Kho AI (anhkysuai.com/kho) integration and 2-image character swap workflow.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import chat_image_handler, chat_orchestrator, kho_catalog


# ---------------------------------------------------------------------------
# 1. Kho Catalog & Clean Markdown Tests
# ---------------------------------------------------------------------------

def test_search_kho_catalog_and_vietnamese_keywords():
    stats = kho_catalog.get_kho_stats()
    assert stats["total_repos"] == 1295

    res_mcp = kho_catalog.search_kho("mcp", limit=5)
    assert len(res_mcp) == 5
    assert all("github_url" in r and "description_vi" in r for r in res_mcp)

    # Vietnamese accented & unaccented search
    res_vi = kho_catalog.search_kho("trợ lý AI", limit=3)
    assert len(res_vi) > 0
    res_unaccented = kho_catalog.search_kho("tro ly AI", limit=3)
    assert len(res_unaccented) > 0

    # Exact/repo name match
    res_exact = kho_catalog.search_kho("openclaw", limit=3)
    assert any("openclaw" in r["full_name"].lower() for r in res_exact)


def test_fetch_clean_markdown_strips_noise():
    sample_html = """
    <html>
      <head>
        <title>Kho AI</title>
        <script>console.log("tracking");</script>
        <style>.ad { display: block; }</style>
      </head>
      <body>
        <nav><a href="/home">Home</a><a href="/login">Login</a></nav>
        <aside class="sidebar ad-banner">Buy now!</aside>
        <main>
          <h1>Kho AI Anhkysuai</h1>
          <p>Danh sách <a href="/kho/repo/test">repo AI</a> hữu ích.</p>
          <ul>
            <li>ComfyUI workflow</li>
            <li>MCP servers</li>
          </ul>
        </main>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    fake_resp = MagicMock()
    fake_resp.text = sample_html
    fake_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=fake_resp) as mock_get:
        md = kho_catalog.fetch_clean_markdown("https://anhkysuai.com/kho/")

    mock_get.assert_called_once()
    assert "# Kho AI Anhkysuai" in md
    assert "[repo AI](https://anhkysuai.com/kho/repo/test)" in md
    assert "- ComfyUI workflow" in md
    assert "tracking" not in md
    assert "Buy now!" not in md
    assert "Copyright 2026" not in md
    assert "Login" not in md


def test_kho_fastapi_routes():
    app = FastAPI()
    kho_catalog.register_routes(app)
    client = TestClient(app)

    resp_stats = client.get("/api/kho/stats")
    assert resp_stats.status_code == 200
    stats_data = resp_stats.json()
    assert stats_data["total_repos"] == 1295
    assert stats_data["categories_count"] > 0

    resp_search = client.get("/api/kho/search", params={"q": "awesome", "limit": 3})
    assert resp_search.status_code == 200
    search_data = resp_search.json()
    assert search_data["count"] == 3
    assert len(search_data["results"]) == 3

    resp_refresh = client.post("/api/kho/refresh")
    assert resp_refresh.status_code == 200
    refresh_data = resp_refresh.json()
    assert refresh_data["status"] == "ok"
    assert refresh_data["total_repos"] == 1295


# ---------------------------------------------------------------------------
# 2. Chat Orchestrator Kho Intent Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "msg,expected_hit,expected_query",
    [
        ("kho ai về mcp", True, "mcp"),
        ("tìm repo comfyui", True, "comfyui"),
        ("tim repo openclaw nhé", True, "openclaw"),
        ("github ai agent", True, "agent"),
        ("anhkysuai", True, ""),
        ("hôm nay trời đẹp quá", False, ""),
        ("vẽ ảnh Hu Tao", False, ""),
    ],
)
def test_detect_kho_intent(msg: str, expected_hit: bool, expected_query: str):
    hit, query = chat_orchestrator.detect_kho_intent(msg)
    assert hit is expected_hit
    assert query == expected_query


@pytest.mark.asyncio
async def test_orchestrate_chat_action_kho():
    res = await chat_orchestrator.orchestrate_chat_action("tìm repo mcp")
    assert res is not None
    assert res["handled"] is True
    assert res["action_type"] == "kho"
    assert "https://github.com/" in res["text"]
    assert len(res["artifacts"]) > 0
    assert res["artifacts"][0]["type"] == "kho_repo"


# ---------------------------------------------------------------------------
# 3. Two-Image Separated Character Swap Workflow Tests
# ---------------------------------------------------------------------------

def _make_fake_urlopen(captured_prompts: List[Dict[str, Any]]):
    def _fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        if url.endswith("/prompt"):
            body = json.loads(req.data.decode("utf-8"))
            captured_prompts.append(body["prompt"])
            resp.read.return_value = json.dumps({"prompt_id": "test-pid-123"}).encode("utf-8")
        elif "/history/" in url:
            resp.read.return_value = json.dumps({
                "test-pid-123": {
                    "outputs": {
                        "9": {
                            "images": [{"filename": "out.png", "subfolder": "", "type": "output"}]
                        }
                    }
                }
            }).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *args: None
        return resp

    return _fake_urlopen


@pytest.mark.asyncio
async def test_run_comfy_workflow_dual_image_separation(tmp_path: Path, monkeypatch):
    captured_prompts: List[Dict[str, Any]] = []
    monkeypatch.setattr(chat_image_handler, "CHAT_IMAGES_DIR", tmp_path)
    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", tmp_path / "ComfyUI")

    def _fake_urlretrieve(url: str, filename: str):
        Path(filename).write_bytes(b"\x89PNG\r\n\x1a\nfake")

    with patch("urllib.request.urlopen", side_effect=_make_fake_urlopen(captured_prompts)), \
         patch("urllib.request.urlretrieve", side_effect=_fake_urlretrieve), \
         patch("asyncio.sleep", return_value=None):
        out_path = await chat_image_handler.run_comfy_workflow(
            positive_prompt="1girl, Hu Tao, anime",
            negative_prompt="bad quality",
            init_image_name="pose_source.png",
            ref_image_name="hutao_identity.png",
        )

    assert out_path.is_file()
    assert len(captured_prompts) == 1
    wf = captured_prompts[0]

    # Branch 1: init_image_name -> LoadImage("10") -> VAEEncode("12") -> KSampler("7").latent_image
    assert wf["10"]["class_type"] == "LoadImage"
    assert wf["10"]["inputs"]["image"] == "pose_source.png"
    assert wf["12"]["class_type"] == "VAEEncode"
    assert wf["12"]["inputs"]["pixels"] == ["10", 0]
    assert wf["7"]["inputs"]["latent_image"] == ["12", 0]

    # Branch 2: ref_image_name -> LoadImage("13") -> AnimaRefAdapter("11") -> KSampler("7").model
    assert wf["13"]["class_type"] == "LoadImage"
    assert wf["13"]["inputs"]["image"] == "hutao_identity.png"
    assert wf["11"]["class_type"] == "AnimaRefAdapter"
    assert wf["11"]["inputs"]["image"] == ["13", 0]
    assert wf["7"]["inputs"]["model"] == ["11", 0]


@pytest.mark.asyncio
async def test_run_comfy_workflow_init_only_img2img(tmp_path: Path, monkeypatch):
    captured_prompts: List[Dict[str, Any]] = []
    monkeypatch.setattr(chat_image_handler, "CHAT_IMAGES_DIR", tmp_path)
    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", tmp_path / "ComfyUI")

    def _fake_urlretrieve(url: str, filename: str):
        Path(filename).write_bytes(b"\x89PNG\r\n\x1a\nfake")

    with patch("urllib.request.urlopen", side_effect=_make_fake_urlopen(captured_prompts)), \
         patch("urllib.request.urlretrieve", side_effect=_fake_urlretrieve), \
         patch("asyncio.sleep", return_value=None):
        await chat_image_handler.run_comfy_workflow(
            positive_prompt="1girl, anime",
            negative_prompt="bad quality",
            init_image_name="pose_only.png",
            ref_image_name=None,
        )

    wf = captured_prompts[0]
    assert wf["10"]["class_type"] == "LoadImage"
    assert wf["10"]["inputs"]["image"] == "pose_only.png"
    assert wf["12"]["class_type"] == "VAEEncode"
    assert wf["12"]["inputs"]["pixels"] == ["10", 0]
    assert "11" not in wf  # No AnimaRefAdapter
    assert wf["7"]["inputs"]["model"] == ["1", 0]
    assert wf["7"]["inputs"]["latent_image"] == ["12", 0]


@pytest.mark.asyncio
async def test_handle_chat_image_generation_with_attached_images_and_ref(tmp_path: Path, monkeypatch):
    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "input").mkdir(parents=True, exist_ok=True)
    export_dir = tmp_path / "Export" / "Images"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Create a ref image in comfy input
    (comfy_dir / "input" / "hutao_ref.png").write_bytes(b"ref-bytes")

    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", comfy_dir)
    monkeypatch.setattr(chat_image_handler, "EXPORT_IMAGES_DIR", export_dir)

    raw_png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    data_uri = "data:image/png;base64," + base64.b64encode(raw_png).decode("ascii")

    generated_file = tmp_path / "gen_out.png"
    generated_file.write_bytes(raw_png)

    captured_kwargs: Dict[str, Any] = {}

    async def _fake_run_comfy(**kwargs):
        captured_kwargs.update(kwargs)
        return generated_file

    with patch.object(chat_image_handler, "ensure_comfy_online", return_value=True), \
         patch.object(chat_image_handler, "run_comfy_workflow", side_effect=_fake_run_comfy):
        res = await chat_image_handler.handle_chat_image_generation(
            user_message="Đổi nhân vật trong ảnh thành Hu Tao",
            ref_image_name="hutao_ref.png",
            attached_images=[data_uri],
        )

    assert res["success"] is True
    assert res["ref_image_name"] == "hutao_ref.png"
    assert res["init_image_name"] is not None
    assert res["init_image_name"].startswith("chat_init_")
    assert (comfy_dir / "input" / res["init_image_name"]).read_bytes() == raw_png
    assert captured_kwargs["init_image_name"] == res["init_image_name"]
    assert captured_kwargs["ref_image_name"] == "hutao_ref.png"
