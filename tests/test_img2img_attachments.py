# -*- coding: utf-8 -*-
"""
Unit & integration tests for chat image attachment staging -> ComfyUI Img2Img (VAEEncode).
Covers the exact frontend payload format from app/ui/index.html -> app/main.py -> app/chat_image_handler.py.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import chat_image_handler, main


RAW_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
RAW_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
RAW_WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32


def _make_comfy_urlopen(captured_prompts: List[Dict[str, Any]]):
    def _fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        if url.endswith("/prompt"):
            body = json.loads(req.data.decode("utf-8"))
            captured_prompts.append(body["prompt"])
            resp.read.return_value = json.dumps({"prompt_id": "pid-img2img-1"}).encode("utf-8")
        elif "/history/" in url:
            resp.read.return_value = json.dumps({
                "pid-img2img-1": {
                    "outputs": {
                        "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
                    }
                }
            }).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *args: None
        return resp

    return _fake_urlopen


def test_save_attached_images_pydantic_chat_attachment_frontend_format(tmp_path: Path, monkeypatch):
    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "input").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", comfy_dir)

    b64_jpeg = base64.b64encode(RAW_JPEG).decode("ascii")
    att = main.ChatAttachment(
        name="pose_ref.jpg",
        media_type="image/jpeg",
        content="",
        data_base64=b64_jpeg,
    )

    staged = chat_image_handler._save_attached_images_for_comfy([att])
    assert staged is not None
    assert staged.startswith("chat_init_") and staged.endswith(".jpg")
    assert (comfy_dir / "input" / staged).read_bytes() == RAW_JPEG


@pytest.mark.parametrize(
    "payload_factory,expected_bytes,expected_ext",
    [
        (lambda tmp: "data:image/png;base64," + base64.b64encode(RAW_PNG).decode("ascii"), RAW_PNG, ".png"),
        (lambda tmp: base64.b64encode(RAW_PNG).decode("ascii"), RAW_PNG, ".png"),
        (
            lambda tmp: {
                "name": "clip.webp",
                "media_type": "image/webp",
                "content": "",
                "data_base64": base64.b64encode(RAW_WEBP).decode("ascii"),
            },
            RAW_WEBP,
            ".webp",
        ),
        (
            lambda tmp: {"data_url": "data:image/jpeg;base64," + base64.b64encode(RAW_JPEG).decode("ascii")},
            RAW_JPEG,
            ".jpg",
        ),
        (
            lambda tmp: {"base64": base64.b64encode(RAW_PNG).decode("ascii")},
            RAW_PNG,
            ".png",
        ),
        (
            lambda tmp: {"path": str(_write_tmp_img(tmp / "local_init.png", RAW_PNG))},
            RAW_PNG,
            ".png",
        ),
    ],
)
def test_save_attached_images_all_formats(tmp_path: Path, monkeypatch, payload_factory, expected_bytes, expected_ext):
    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "input").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", comfy_dir)

    payload = payload_factory(tmp_path)
    staged = chat_image_handler._save_attached_images_for_comfy([payload])
    assert staged is not None
    assert staged.endswith(expected_ext)
    assert (comfy_dir / "input" / staged).read_bytes() == expected_bytes


def _write_tmp_img(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_save_attached_images_api_uploaded_asset_and_skips_text(tmp_path: Path, monkeypatch):
    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "input").mkdir(parents=True, exist_ok=True)
    export_dir = tmp_path / "Export" / "Images"
    nested_dir = export_dir / "Genshin_Impact"
    nested_dir.mkdir(parents=True, exist_ok=True)
    asset_file = nested_dir / "user_asset_1234.png"
    asset_file.write_bytes(RAW_PNG)

    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", comfy_dir)
    monkeypatch.setattr(chat_image_handler, "EXPORT_IMAGES_DIR", export_dir)

    text_att = main.ChatAttachment(
        name="notes.txt",
        media_type="text/plain",
        content="test",  # valid 4-char base64 if not guarded!
        data_base64="",
    )
    api_att = {"url": "/api/chat/images/user_asset_1234.png"}

    staged = chat_image_handler._save_attached_images_for_comfy([text_att, api_att])
    assert staged == "user_asset_1234.png"
    assert (comfy_dir / "input" / "user_asset_1234.png").read_bytes() == RAW_PNG


@pytest.mark.asyncio
async def test_handle_chat_image_generation_triggers_vae_encode_and_denoise(tmp_path: Path, monkeypatch):
    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "input").mkdir(parents=True, exist_ok=True)
    chat_dir = tmp_path / "chat_gen"
    chat_dir.mkdir(parents=True, exist_ok=True)
    export_dir = tmp_path / "Export" / "Images"
    export_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(chat_image_handler, "COMFY_DIR", comfy_dir)
    monkeypatch.setattr(chat_image_handler, "CHAT_IMAGES_DIR", chat_dir)
    monkeypatch.setattr(chat_image_handler, "EXPORT_IMAGES_DIR", export_dir)

    captured_prompts: List[Dict[str, Any]] = []

    def _fake_urlretrieve(url: str, filename: str):
        Path(filename).write_bytes(RAW_PNG)

    att = main.ChatAttachment(
        name="sketch.png",
        media_type="image/png",
        content="",
        data_base64=base64.b64encode(RAW_PNG).decode("ascii"),
    )

    with patch.object(chat_image_handler, "ensure_comfy_online", return_value=True), \
         patch.object(chat_image_handler, "resolve_user_profile_ref_image", return_value=None), \
         patch("urllib.request.urlopen", side_effect=_make_comfy_urlopen(captured_prompts)), \
         patch("urllib.request.urlretrieve", side_effect=_fake_urlretrieve), \
         patch("asyncio.sleep", return_value=None):
        res = await chat_image_handler.handle_chat_image_generation(
            user_message="Vẽ ảnh Hu Tao",
            attached_images=[att],
        )

    assert res["success"] is True
    assert res["init_image_name"] is not None
    assert (comfy_dir / "input" / res["init_image_name"]).is_file()
    assert len(captured_prompts) == 1

    wf = captured_prompts[0]
    assert wf["10"]["class_type"] == "LoadImage"
    assert wf["10"]["inputs"]["image"] == res["init_image_name"]
    assert wf["12"]["class_type"] == "VAEEncode"
    assert wf["12"]["inputs"]["pixels"] == ["10", 0]
    assert "6" not in wf  # No EmptyLatentImage
    assert wf["7"]["inputs"]["latent_image"] == ["12", 0]
    assert 0.48 <= wf["7"]["inputs"]["denoise"] <= 0.55


def test_chat_stream_endpoint_passes_frontend_attachment_to_img2img(tmp_path: Path, monkeypatch):
    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "input").mkdir(parents=True, exist_ok=True)
    chat_dir = tmp_path / "chat_gen"
    chat_dir.mkdir(parents=True, exist_ok=True)
    export_dir = tmp_path / "Export" / "Images"
    export_dir.mkdir(parents=True, exist_ok=True)

    main_cih = sys.modules[main.handle_chat_image_generation.__module__]
    monkeypatch.setattr(main, "DB", tmp_path / "office.db")
    main.init_db()
    monkeypatch.setattr(main_cih, "COMFY_DIR", comfy_dir)
    monkeypatch.setattr(main_cih, "CHAT_IMAGES_DIR", chat_dir)
    monkeypatch.setattr(main_cih, "EXPORT_IMAGES_DIR", export_dir)

    captured_prompts: List[Dict[str, Any]] = []

    def _fake_urlretrieve(url: str, filename: str):
        Path(filename).write_bytes(RAW_PNG)

    async def _fake_orchestrate(**kwargs):
        return None

    client = TestClient(main.app)
    frontend_payload = {
        "message": "Vẽ ảnh Hu Tao",
        "agent": "CEO",
        "attachments": [
            {
                "name": "pose.png",
                "media_type": "image/png",
                "content": "",
                "data_base64": base64.b64encode(RAW_PNG).decode("ascii"),
            }
        ],
        "conversation_id": "",
        "aspect_ratio": "3:4",
        "output_format": "PNG",
    }

    with patch.object(main, "orchestrate_chat_action", side_effect=_fake_orchestrate), \
         patch.object(main_cih, "ensure_comfy_online", return_value=True), \
         patch.object(main_cih, "resolve_user_profile_ref_image", return_value=None), \
         patch("urllib.request.urlopen", side_effect=_make_comfy_urlopen(captured_prompts)), \
         patch("urllib.request.urlretrieve", side_effect=_fake_urlretrieve), \
         patch("asyncio.sleep", return_value=None):
        resp = client.post("/api/chat/stream", json=frontend_payload)

    assert resp.status_code == 200
    assert '"error"' not in resp.text, resp.text
    assert len(captured_prompts) == 1, resp.text
    wf = captured_prompts[0]
    assert wf["10"]["class_type"] == "LoadImage"
    assert wf["12"]["class_type"] == "VAEEncode"
    assert wf["7"]["inputs"]["latent_image"] == ["12", 0]
    assert 0.48 <= wf["7"]["inputs"]["denoise"] <= 0.55
