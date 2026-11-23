"""Unit tests for Voice Narration and Procedural Audio Engine."""

import os
from pathlib import Path
import pytest

from app.voice_engine import (
    AudioClip,
    VoiceEngine,
    format_srt_time,
    get_audio_duration_ffmpeg,
)


@pytest.fixture
def voice_engine(tmp_path):
    return VoiceEngine(cache_dir=tmp_path / "audio_cache")


def test_available_voices(voice_engine):
    voices = voice_engine.get_available_voices()
    assert len(voices) >= 5
    locales = [v["locale"] for v in voices]
    assert "vi-VN" in locales
    assert "ja-JP" in locales
    assert "en-US" in locales


def test_format_srt_time():
    assert format_srt_time(0.0) == "00:00:00,000"
    assert format_srt_time(1.234) == "00:00:01,234"
    assert format_srt_time(65.5) == "00:01:05,500"
    assert format_srt_time(3661.05) == "01:01:01,050"


def test_generate_silence(voice_engine):
    silence = voice_engine.generate_silence(duration=1.5)
    assert silence.exists()
    assert silence.stat().st_size > 0
    duration = get_audio_duration_ffmpeg(silence)
    assert 1.4 <= duration <= 1.6


def test_generate_procedural_sfx(voice_engine):
    boom = voice_engine.generate_sfx("boom")
    assert boom.exists()
    assert boom.stat().st_size > 1000

    swoosh = voice_engine.generate_sfx("swoosh")
    assert swoosh.exists()
    assert swoosh.stat().st_size > 1000

    thump = voice_engine.generate_sfx("thump")
    assert thump.exists()
    assert thump.stat().st_size > 1000


@pytest.mark.asyncio
async def test_synthesize_speech_empty_text(voice_engine):
    clip = await voice_engine.synthesize_speech("", speaker="Narrator")
    assert clip.duration >= 0.9
    assert os.path.exists(clip.file_path)
    assert clip.speaker == "Narrator"


@pytest.mark.asyncio
async def test_synthesize_speech_offline_procedural(voice_engine):
    test_wav = voice_engine.cache_dir / "simulated_dialogue.wav"
    dur = voice_engine._generate_simulated_speech_wav("Tôi là thợ săn hải tặc Zoro", test_wav)
    assert dur > 1.0
    assert test_wav.exists()
