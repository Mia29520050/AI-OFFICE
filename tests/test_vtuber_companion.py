from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import game_agent  # noqa: E402
import game_playbooks  # noqa: E402
import vtuber_companion  # noqa: E402
from grounded_search import SearchResult  # noqa: E402
from vtuber_models import MOOD_TO_EXPRESSION  # noqa: E402


def test_detect_screen_context_variants() -> None:
    assert vtuber_companion.detect_screen_context("NAVI vs FaZe - BLAST Premier CS2 - YouTube", "", "chrome.exe") == "youtube_cs2"
    assert vtuber_companion.detect_screen_context("Counter-Strike 2", "Mirage 11-9", "cs2.exe") == "gaming_cs2"
    assert vtuber_companion.detect_screen_context("app/vtuber_companion.py - Visual Studio Code", "def tick():", "Code.exe") == "coding"
    assert vtuber_companion.detect_screen_context("Elden Ring", "HP Stamina", "eldenring.exe") == "gaming"
    assert vtuber_companion.detect_screen_context("Tin tức công nghệ - Google Chrome", "", "chrome.exe") == "browsing"
    assert vtuber_companion.detect_screen_context("Desktop", "", "explorer.exe") == "general"


def test_parse_cs2_and_win_probability_offline_and_online(monkeypatch) -> None:
    parsed = vtuber_companion.parse_cs2_match_state(
        "NAVI vs FaZe - Map Mirage - BLAST Premier CS2",
        "12-10 | Full Buy | $4800",
    )
    assert parsed["is_cs2"] is True
    assert parsed["team_a"] == "NAVI"
    assert parsed["team_b"] == "FaZe"
    assert parsed["score_a"] == 12
    assert parsed["score_b"] == 10
    assert parsed["map_name"] == "Mirage"
    assert parsed["match_point"] is True

    offline = vtuber_companion.estimate_cs2_win_probability(parsed, use_web=False)
    assert offline["source"] == "heuristic_offline"
    assert offline["team_a_prob"] > offline["team_b_prob"]
    assert offline["team_a_prob"] + offline["team_b_prob"] == 100

    # Online grounded_search mock
    def fake_search(query: str, max_results: int = 2, timeout: float = 4.0):
        return [
            SearchResult(
                index=1,
                title="HLTV Matchup",
                url="https://www.hltv.org/matches/1",
                snippet="NAVI favorite on Mirage with 5 win streak",
                compressed_text="NAVI favorite on Mirage with 5 win streak",
                domain="www.hltv.org",
            )
        ]

    monkeypatch.setattr(vtuber_companion, "execute_web_search", fake_search)
    online = vtuber_companion.estimate_cs2_win_probability(parsed, use_web=True)
    assert online["source"] == "grounded_search+heuristic"
    assert online["team_a_prob"] >= offline["team_a_prob"]
    assert len(online["search_snippets"]) == 1


def test_mood_to_expression_mapping_and_ollama_fallback() -> None:
    mood, expr = vtuber_companion.select_mood_for_context(
        "youtube_cs2",
        {"team_a": "G2", "team_b": "Vitality", "score_a": 12, "score_b": 12},
    )
    assert mood == "panic"
    assert expr == MOOD_TO_EXPRESSION["panic"]

    # Ollama success
    async def fake_ollama(messages, **kwargs):
        return "G2 với Vitality căng như dây đàn luôn Master ơi!"

    text, src = asyncio.run(
        vtuber_companion.generate_vtuber_commentary(
            vtuber_name="Mina AI",
            context="youtube_cs2",
            window_title="G2 vs Vitality - CS2",
            ocr_text="12-12 Inferno",
            cs2_analysis={"team_a": "G2", "team_b": "Vitality", "score_a": 12, "score_b": 12, "map_name": "Inferno", "team_a_prob": 50, "team_b_prob": 50},
            ollama_chat_fn=fake_ollama,
        )
    )
    assert src == "ollama"
    assert "G2" in text

    # Ollama failure -> fallback
    async def broken_ollama(messages, **kwargs):
        raise RuntimeError("Ollama offline")

    fb_text, fb_src = asyncio.run(
        vtuber_companion.generate_vtuber_commentary(
            vtuber_name="Mina AI",
            context="coding",
            window_title="main.py - VSCode",
            ocr_text="pytest",
            ollama_chat_fn=broken_ollama,
        )
    )
    assert fb_src == "fallback"
    assert len(fb_text) > 5


def test_companion_tick_cooldown_and_routes(monkeypatch, tmp_path: Path) -> None:
    dummy_img = tmp_path / "screen.jpg"
    dummy_img.write_bytes(b"fakejpeg")

    monkeypatch.setattr(
        vtuber_companion.computer,
        "active_window",
        lambda: {"found": True, "title": "Spirit vs MOUZ - Nuke - YouTube CS2", "process_name": "chrome.exe"},
    )
    monkeypatch.setattr(
        vtuber_companion.computer,
        "capture_screen",
        lambda max_width=640, quality=55: {"path": str(dummy_img), "width": 640, "height": 360},
    )
    monkeypatch.setattr(
        vtuber_companion,
        "extract_ocr_labels",
        lambda path, max_items=18: {"items": [{"text": "Spirit 10-7 MOUZ"}, {"text": "Nuke"}]},
    )

    app = FastAPI()
    vtuber_companion.register_routes(app)
    client = TestClient(app)

    # Reset manager state cleanly
    vtuber_companion.COMPANION_MANAGER._last_comment_at = 0.0
    vtuber_companion.COMPANION_MANAGER._last_signature = ""

    r_start = client.post("/api/vtuber/companion/start", json={"cooldown_s": 30.0, "interval_s": 60.0})
    assert r_start.status_code == 200
    assert r_start.json()["active"] is True

    r_tick1 = client.post("/api/vtuber/companion/tick", json={"force": False})
    assert r_tick1.status_code == 200
    d1 = r_tick1.json()
    assert d1["skipped_comment"] is False
    assert d1["context"] == "youtube_cs2"
    assert d1["expression"] in MOOD_TO_EXPRESSION.values()
    assert d1["cs2_analysis"]["team_a"] == "Spirit"

    # Second tick within cooldown should skip commentary generation
    r_tick2 = client.post("/api/vtuber/companion/tick", json={"force": False})
    assert r_tick2.status_code == 200
    assert r_tick2.json()["skipped_comment"] is True

    r_status = client.get("/api/vtuber/companion/status")
    assert r_status.status_code == 200
    assert r_status.json()["cooldown_remaining_s"] > 0

    r_cs2 = client.post(
        "/api/vtuber/companion/analyze-cs2",
        json={"title": "Vitality vs G2 - Dust 2", "score_a": 11, "score_b": 8, "economy_a": "full_buy", "economy_b": "eco"},
    )
    assert r_cs2.status_code == 200
    cs2_data = r_cs2.json()
    assert cs2_data["ok"] is True
    assert cs2_data["analysis"]["team_a_prob"] > cs2_data["analysis"]["team_b_prob"]
    assert cs2_data["expression"] == MOOD_TO_EXPRESSION[cs2_data["mood"]]

    r_stop = client.post("/api/vtuber/companion/stop")
    assert r_stop.status_code == 200
    assert r_stop.json()["active"] is False


def test_detect_game_profile_genres_and_f12_kill_switch() -> None:
    fps = game_playbooks.detect_game_profile("Counter-Strike 2", [{"text": "AMMO 30/90"}, {"text": "HP 100"}])
    assert fps["genre"] == "fps"
    assert "r" in fps["recommended_keys"]

    moba = game_playbooks.detect_game_profile("League of Legends", [{"text": "GOLD 3200"}, {"text": "KDA 4/1/6"}])
    assert moba["genre"] == "moba"
    assert "q/w/e/r" in moba["controls_map"]

    rpg = game_playbooks.detect_game_profile("Elden Ring", [{"text": "STAMINA"}, {"text": "BOSS"}])
    assert rpg["genre"] == "rpg"
    assert "space" in rpg["recommended_keys"]

    vn = game_playbooks.detect_game_profile("Steins;Gate", [{"text": "AUTO"}, {"text": "BACKLOG"}, {"text": "SAVE"}])
    assert vn["genre"] == "visual_novel"
    assert "space/enter" in vn["controls_map"]

    gacha = game_playbooks.detect_game_profile("Honkai: Star Rail", [{"text": "WARP"}, {"text": "ULTIMATE"}])
    assert gacha["genre"] == "gacha"
    assert "1/2/3/4/5/0" in gacha["controls_map"]

    generic = game_playbooks.detect_game_profile("Untitled Window", [])
    assert generic["genre"] == "generic"

    # Verify game_agent exposes detect_game_profile & keeps F12 kill-switch
    assert hasattr(game_agent, "detect_game_profile")
    assert hasattr(game_agent, "is_f12_pressed")
    assert "game_profile" in game_agent.GAME_MANAGER.snapshot_state()
