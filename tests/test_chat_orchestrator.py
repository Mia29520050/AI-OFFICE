# -*- coding: utf-8 -*-
"""Unit tests for app/chat_orchestrator.py (mocked / offline-safe)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import chat_orchestrator


# ---------------------------------------------------------------------------
# 1. Rule-First Intent Classifiers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "msg, expected_hit, expected_substr",
    [
        ("tạo video cô gái anime dưới mưa", True, "cô gái anime dưới mưa"),
        ("làm clip ngắn về cảnh hoàng hôn", True, "ngắn về cảnh hoàng hôn"),
        ("render video Raiden Shogun", True, "Raiden Shogun"),
        ("chuyển ảnh thành video giúp anh", True, "Smooth cinematic"),
        ("làm motion comic cảnh chiến đấu", True, "cảnh chiến đấu"),
        ("làm sao để tạo video bằng AI?", False, ""),
        ("hướng dẫn render video trong app", False, ""),
        ("xin chào bạn", False, ""),
    ],
)
def test_detect_video_intent(msg: str, expected_hit: bool, expected_substr: str):
    hit, prompt = chat_orchestrator.detect_video_intent(msg)
    assert hit is expected_hit
    if expected_hit:
        assert expected_substr.lower() in prompt.lower()
    else:
        assert prompt == ""


@pytest.mark.parametrize(
    "msg, expected_hit, expected_fact",
    [
        ("nhớ giúp anh thích uống cà phê sữa đá", True, "thích uống cà phê sữa đá"),
        ("ghi nhớ: tôi dùng GPU RTX 3060 6GB", True, "tôi dùng GPU RTX 3060 6GB"),
        ("học cái này giúp tôi: dự án nằm ở F:\\AI-Office", True, "dự án nằm ở F:\\AI-Office"),
        ("bạn có nhớ tôi thích gì không?", False, ""),
        ("nhớ giúp", False, ""),
    ],
)
def test_detect_memory_intent(msg: str, expected_hit: bool, expected_fact: str):
    hit, fact = chat_orchestrator.detect_memory_intent(msg)
    assert hit is expected_hit
    assert fact == expected_fact


@pytest.mark.parametrize(
    "msg, expected_hit",
    [
        ("tạo model 3d thanh kiếm katana", True),
        ("dựng 3d cái rương gỗ", True),
        ("create 3d crystal", True),
        ("cách tạo model 3d trong blender như thế nào?", False),
    ],
)
def test_detect_3d_intent(msg: str, expected_hit: bool):
    hit, _ = chat_orchestrator.detect_3d_intent(msg)
    assert hit is expected_hit


@pytest.mark.parametrize(
    "msg, expected_hit, expected_text",
    [
        ("đọc to câu này: Xin chào buổi sáng", True, "Xin chào buổi sáng"),
        ("lồng tiếng giúp tôi: Chúng ta xuất phát thôi!", True, "Chúng ta xuất phát thôi!"),
        ("tts Hello world", True, "Hello world"),
        ("làm sao để dùng tts?", False, ""),
    ],
)
def test_detect_tts_intent(msg: str, expected_hit: bool, expected_text: str):
    hit, text = chat_orchestrator.detect_tts_intent(msg)
    assert hit is expected_hit
    assert text == expected_text


# ---------------------------------------------------------------------------
# 2. Orchestration Execution (Mocked / Offline-Safe)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_orchestrate_video_calls_vram_guard_and_returns_link(tmp_path):
    fake_video = tmp_path / "Export" / "Video" / "demo_clip.mp4"
    fake_video.parent.mkdir(parents=True, exist_ok=True)
    fake_video.write_bytes(b"mp4")

    mock_generate_video = AsyncMock(
        return_value={
            "video_path": str(fake_video),
            "width": 480,
            "height": 272,
            "mode": "offline_fallback",
        }
    )
    mock_free_ollama = AsyncMock(return_value=True)

    with (
        patch("app.video_generator.generate_video", mock_generate_video),
        patch("app.vram_guard.free_ollama", mock_free_ollama),
    ):
        res = await chat_orchestrator.orchestrate_chat_action(
            "tạo video anime cyberpunk",
            aspect_ratio="16:9",
        )

    assert res is not None
    assert res["handled"] is True
    assert res["action_type"] == "video"
    assert "/api/video/file/demo_clip.mp4" in res["text"]
    assert res["artifacts"][0]["url"] == "/api/video/file/demo_clip.mp4"
    mock_free_ollama.assert_awaited_once()
    mock_generate_video.assert_awaited_once()
    _, kwargs = mock_generate_video.call_args
    assert kwargs["width"] == 480
    assert kwargs["height"] == 272


@pytest.mark.asyncio
async def test_orchestrate_memory_calls_learn_fact():
    fake_memory_mod = SimpleNamespace(
        learn_fact=MagicMock(return_value={"id": 1, "content": "thích matcha"})
    )
    with patch.dict(sys.modules, {"app.memory_engine": fake_memory_mod}):
        # Ensure `from app import memory_engine` resolves to fake_memory_mod
        import app as app_pkg

        with patch.object(app_pkg, "memory_engine", fake_memory_mod, create=True):
            res = await chat_orchestrator.orchestrate_chat_action("nhớ giúp anh thích matcha")

    assert res is not None
    assert res["handled"] is True
    assert res["action_type"] == "memory"
    assert "thích matcha" in res["text"]
    fake_memory_mod.learn_fact.assert_called_once_with(
        "thích matcha", category="fact", source="chat", importance=4
    )


@pytest.mark.asyncio
async def test_orchestrate_3d_calls_blender_3d(tmp_path):
    fake_glb = tmp_path / "chat_sword.glb"
    fake_glb.write_bytes(b"glTF")
    mock_gen_3d = MagicMock(
        return_value={
            "name": "chat_sword",
            "asset_type": "sword",
            "exported_files": {"glb": str(fake_glb)},
            "validation": {"passed": True},
        }
    )

    with patch("app.blender_3d.generate_3d_asset", mock_gen_3d):
        res = await chat_orchestrator.orchestrate_chat_action(
            "tạo model 3d thanh kiếm ánh sáng",
            output_format="glb",
        )

    assert res is not None
    assert res["handled"] is True
    assert res["action_type"] == "3d"
    assert "sword" in res["text"]
    assert res["artifacts"][0]["filename"] == "chat_sword.glb"
    mock_gen_3d.assert_called_once()
    _, kwargs = mock_gen_3d.call_args
    assert kwargs["asset_type"] == "sword"
    assert kwargs["export_format"] == "glb"


@pytest.mark.asyncio
async def test_orchestrate_tts_calls_voice_engine(tmp_path):
    fake_mp3 = tmp_path / "tts_demo.mp3"
    fake_mp3.write_bytes(b"ID3")
    fake_clip = SimpleNamespace(
        file_path=str(fake_mp3),
        exported_path=str(fake_mp3),
        duration=2.35,
    )
    mock_synth = AsyncMock(return_value=fake_clip)

    with patch("app.voice_engine.DEFAULT_VOICE_ENGINE.synthesize_speech", mock_synth):
        res = await chat_orchestrator.orchestrate_chat_action(
            "đọc to giúp tôi: Chào mừng đến với AI Office"
        )

    assert res is not None
    assert res["handled"] is True
    assert res["action_type"] == "tts"
    assert "/api/voice/audio/tts_demo.mp3" in res["text"]
    assert res["artifacts"][0]["duration"] == pytest.approx(2.35)
    mock_synth.assert_awaited_once_with(
        text="Chào mừng đến với AI Office",
        export=True,
    )


@pytest.mark.asyncio
async def test_orchestrate_fallthrough_returns_none():
    res = await chat_orchestrator.orchestrate_chat_action(
        "Giải thích định lý Pythagoras giúp tôi"
    )
    assert res is None
