"""Comprehensive unit tests for Voice Engine (TTS/STT) and In-Game Screen Translator.

All tests run 100% offline with zero external network or GPU dependency.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.voice_engine import (
    AudioClip,
    EXPORT_AUDIO_DIR,
    TranscriptionResult,
    VOICE_PRESETS,
    VoiceEngine,
    format_srt_time,
    get_audio_duration_ffmpeg,
    register_routes as register_voice_routes,
    transcribe_audio,
)
from app.game_translator import (
    GameTranslator,
    TranslationContextMemory,
    detect_language,
    offline_fallback_translate,
    register_routes as register_translator_routes,
)


@pytest.fixture
def app_client(tmp_path):
    app = FastAPI()
    register_voice_routes(app)
    register_translator_routes(app)
    return TestClient(app)


# =========================================================================
# 1. Voice Engine (TTS, STT, Export) Tests
# =========================================================================

def test_voice_presets_contain_vi_ja_en():
    presets = list(VOICE_PRESETS.values())
    locales = [p["locale"] for p in presets]
    assert "vi-VN" in locales
    assert "ja-JP" in locales
    assert "en-US" in locales

    # Verify preset entries
    assert "vi_female" in VOICE_PRESETS
    assert "vi_male" in VOICE_PRESETS
    assert "ja_anime_female" in VOICE_PRESETS
    assert "en_narrator" in VOICE_PRESETS


@pytest.mark.asyncio
async def test_tts_synthesis_and_export(tmp_path):
    custom_cache = tmp_path / "cache"
    custom_export = tmp_path / "export"
    engine = VoiceEngine(cache_dir=custom_cache, export_dir=custom_export)

    clip = await engine.synthesize_speech(
        text="Xin chào dũng giả, chào mừng tới thế giới kiếm hiệp!",
        voice="vi-VN-NamMinhNeural",
        speaker="Lãnh chúa",
        export=True,
        export_dir=custom_export,
    )

    assert Path(clip.file_path).exists()
    assert clip.duration > 0.5
    assert clip.exported_path is not None
    assert Path(clip.exported_path).exists()
    assert Path(clip.exported_path).parent == custom_export


@pytest.mark.asyncio
async def test_tts_empty_text_returns_silence(tmp_path):
    engine = VoiceEngine(cache_dir=tmp_path / "cache")
    clip = await engine.synthesize_speech("", speaker="NPC")
    assert clip.duration >= 0.9
    assert Path(clip.file_path).exists()


def test_transcribe_audio_fallback(tmp_path):
    dummy_wav = tmp_path / "sample.wav"
    engine = VoiceEngine(cache_dir=tmp_path)
    silence = engine.generate_silence(1.2)

    res = transcribe_audio(silence, language="vi")
    assert isinstance(res, TranscriptionResult)
    assert res.language == "vi"
    assert res.duration > 0.0
    assert res.text != ""


def test_transcribe_audio_from_bytes(tmp_path):
    engine = VoiceEngine(cache_dir=tmp_path)
    silence = engine.generate_silence(1.0)
    data = silence.read_bytes()

    res = transcribe_audio(data, language="en")
    assert res.duration > 0.0
    assert res.language == "en"


def test_api_voice_presets(app_client):
    res = app_client.get("/api/voice/presets")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "presets" in data
    assert "voices" in data
    assert len(data["voices"]) >= 5


def test_api_voice_tts_and_get_audio(app_client):
    res = app_client.post(
        "/api/voice/tts",
        json={
            "text": "Kiểm thử hệ thống giọng nói AI Office",
            "voice": "vi-VN-HoaiMyNeural",
            "speaker": "AI Assistant",
            "export": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "audio_url" in data
    assert data["filename"] != ""

    # Fetch generated audio through GET endpoint
    audio_res = app_client.get(data["audio_url"])
    assert audio_res.status_code == 200
    assert len(audio_res.content) > 100


def test_api_voice_stt_json_and_upload(app_client, tmp_path):
    engine = VoiceEngine(cache_dir=tmp_path)
    wav_file = engine.generate_silence(1.0)

    # 1. JSON payload with file path
    res_json = app_client.post(
        "/api/voice/stt",
        json={"audio_path": str(wav_file), "language": "vi"},
    )
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["ok"] is True
    assert data["duration"] > 0

    # 2. Upload file payload
    with open(wav_file, "rb") as f:
        res_file = app_client.post(
            "/api/voice/stt",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert res_file.status_code == 200
    assert res_file.json()["ok"] is True


def test_api_voice_audio_not_found(app_client):
    res = app_client.get("/api/voice/audio/non_existent_audio_file.wav")
    assert res.status_code == 404


# =========================================================================
# 2. Game Translator (Language Detection, Context Memory, OCR & Translation)
# =========================================================================

def test_detect_language():
    # Japanese
    assert detect_language("こんにちは、世界！") == "ja"
    assert detect_language("ドラゴンクエストを始めます") == "ja"
    assert detect_language("勇者よ、立ち上がれ！") == "ja"

    # Chinese
    assert detect_language("大侠请留步，前方危险") == "zh"
    assert detect_language("少林武学博大精深") == "zh"

    # English
    assert detect_language("Press Start to continue") == "en"
    assert detect_language("Quest completed! 500 gold awarded.") == "en"


def test_translation_context_memory():
    mem = TranslationContextMemory(max_history=3)
    mem.update_metadata(game_title="Elden Ring", character="Ranni", tone="mystic")

    assert mem.game_title == "Elden Ring"
    assert mem.active_character == "Ranni"
    assert mem.tone == "mystic"

    # Add 4 entries to test sliding window
    for i in range(4):
        mem.add_entry(f"Original {i}", f"Dịch {i}", speaker="Ranni")

    assert len(mem.history) == 3
    assert mem.history[-1]["original_text"] == "Original 3"

    context_str = mem.get_recent_context(limit=2)
    assert "Original 2" in context_str
    assert "Original 3" in context_str

    mem.clear()
    assert len(mem.history) == 0


def test_offline_fallback_translation():
    mem = TranslationContextMemory()

    # Glossary exact match
    res_en = offline_fallback_translate("Press Start", "en", mem)
    assert "bắt đầu" in res_en.lower()

    # Japanese pattern
    res_ja = offline_fallback_translate("私と一緒に戦おう！ 勇者よ", "ja", mem)
    assert "Dũng giả" in res_ja or "Dịch" in res_ja

    # Chinese pattern
    res_zh = offline_fallback_translate("大侠请留步", "zh", mem)
    assert "Đại hiệp" in res_zh


@pytest.mark.asyncio
async def test_game_translator_translate_text_offline():
    translator = GameTranslator()
    res = await translator.translate_text(
        text="Defeat the Dragon Boss to complete the quest",
        game_title="Dark Souls",
        character="Firekeeper",
        tone="gamer",
    )

    assert res["ok"] is True
    assert res["source_lang"] == "en"
    assert res["target_lang"] == "vi"
    assert len(res["translated_text"]) > 0
    assert res["provider"] in {"ollama", "glossary_fallback"}
    assert len(translator.get_history()) == 1


@pytest.mark.asyncio
async def test_game_translator_with_mocked_ollama():
    translator = GameTranslator()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Hãy hạ gục Rồng Chúa để cứu vương quốc!"}
        mock_post.return_value = mock_resp

        res = await translator.translate_text(
            text="Defeat the Dragon Lord to save the kingdom!",
            character="King",
            game_title="Dragon Age",
        )

        assert res["ok"] is True
        assert res["translated_text"] == "Hãy hạ gục Rồng Chúa để cứu vương quốc!"
        assert res["provider"] == "ollama"


@pytest.mark.asyncio
async def test_game_translator_capture_and_translate_mocked(tmp_path):
    translator = GameTranslator()

    # Create dummy screenshot image
    dummy_img_path = tmp_path / "screen.jpg"
    img = Image.new("RGB", (640, 480), color=(20, 25, 40))
    img.save(dummy_img_path)

    with patch("app.game_translator.capture_and_crop_dialogue") as mock_cap, \
         patch("app.game_translator.extract_ocr_labels") as mock_ocr:

        mock_cap.return_value = (dummy_img_path, {"path": str(dummy_img_path)})
        mock_ocr.return_value = {
            "ok": True,
            "items": [{"text": "Press Start to Play", "x": 500, "y": 800}],
        }

        res = await translator.capture_and_translate(handle=12345, crop_box=[0, 700, 1000, 950])
        assert res["ok"] is True
        assert res["captured"] is True
        assert "Press Start" in res["original_text"]
        assert len(res["translated_text"]) > 0


# =========================================================================
# 3. Translator API Endpoints Tests
# =========================================================================

def test_api_translator_endpoints(app_client):
    # 1. Translate text
    res = app_client.post(
        "/api/translator/translate-text",
        json={
            "text": "Quest Completed! You leveled up.",
            "game_title": "Final Fantasy",
            "character": "Narrator",
            "tone": "gamer",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["translated_text"] != ""
    assert data["source_lang"] == "en"

    # 2. Get history
    hist_res = app_client.get("/api/translator/history")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["ok"] is True
    assert hist_data["total"] >= 1
    assert len(hist_data["history"]) >= 1

    # 3. Clear context
    clear_res = app_client.post("/api/translator/clear-context")
    assert clear_res.status_code == 200
    assert clear_res.json()["ok"] is True

    # 4. Verify cleared history
    hist_after = app_client.get("/api/translator/history").json()
    assert hist_after["total"] == 0


def test_api_translator_capture_endpoint_mocked(app_client, tmp_path):
    dummy_img = tmp_path / "mock_cap.jpg"
    Image.new("RGB", (400, 300), color=(10, 10, 20)).save(dummy_img)

    with patch("app.game_translator.capture_and_crop_dialogue") as mock_cap, \
         patch("app.game_translator.extract_ocr_labels") as mock_ocr:

        mock_cap.return_value = (dummy_img, {"path": str(dummy_img)})
        mock_ocr.return_value = {
            "ok": True,
            "items": [{"text": "Hello Hero", "x": 200, "y": 250}],
        }

        res = app_client.post(
            "/api/translator/capture-and-translate",
            json={"game_title": "Zelda", "character": "Navi"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["captured"] is True
        assert "Hello Hero" in data["original_text"]
