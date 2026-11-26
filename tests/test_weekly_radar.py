# -*- coding: utf-8 -*-
"""
tests/test_weekly_radar.py
==========================
Unit & Integration Tests for:
1. ComfyUI Image Aspect Ratios (1:1, 3:4, 16:9, 9:16) & Dimensions.
2. Output Format Conversions (PNG, WEBP, JPEG).
3. Image Options Parsing from Natural Language Chat Prompts.
4. ResearchedCharacter Aspect Ratio Integration.
5. WeeklyLoreRadar Scanning, Persistence & Queries.
6. FastAPI Radar & Image Serving Endpoints.
"""

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app.main import app
from app.chat_image_handler import (
    ASPECT_RATIOS,
    SUPPORTED_FORMATS,
    resolve_aspect_ratio,
    get_dimensions_for_aspect_ratio,
    convert_and_save_image,
    parse_image_options,
    detect_image_generation_intent,
    CHAT_IMAGES_DIR,
)
from app.character_researcher import (
    ResearchedCharacter,
    ASPECT_RATIO_PRESETS,
    get_character_researcher,
)
from app.weekly_radar import (
    WeeklyLoreRadar,
    LoreRadarEntry,
    WeeklyRadarReport,
    get_weekly_radar,
    get_weekly_radar_report,
)


# ---------------------------------------------------------------------------
# 1. Aspect Ratios & Dimension Presets
# ---------------------------------------------------------------------------

def test_aspect_ratio_presets_and_dimensions():
    required_ratios = ["1:1", "3:4", "16:9", "9:16"]
    for r in required_ratios:
        assert r in ASPECT_RATIOS, f"Missing required aspect ratio preset: {r}"
        w, h = get_dimensions_for_aspect_ratio(r)
        assert w > 0 and h > 0, f"Dimensions for {r} must be positive"
        assert w % 64 == 0, f"Width {w} for {r} should be divisible by 64 for VAE alignment"
        assert h % 64 == 0, f"Height {h} for {r} should be divisible by 64 for VAE alignment"

    # Specific preset checks
    assert get_dimensions_for_aspect_ratio("1:1") == (1024, 1024)
    assert get_dimensions_for_aspect_ratio("3:4") == (768, 1024)
    assert get_dimensions_for_aspect_ratio("16:9") == (1344, 768)
    assert get_dimensions_for_aspect_ratio("9:16") == (768, 1344)


def test_aspect_ratio_aliases():
    aliases = {
        "square": "1:1",
        "vuông": "1:1",
        "vuong": "1:1",
        "1/1": "1:1",
        "portrait": "3:4",
        "dọc": "3:4",
        "doc": "3:4",
        "3/4": "3:4",
        "landscape": "16:9",
        "ngang": "16:9",
        "16/9": "16:9",
        "widescreen": "16:9",
        "vertical": "9:16",
        "mobile": "9:16",
        "phone": "9:16",
        "9/16": "9:16",
    }
    for alias, expected in aliases.items():
        resolved = resolve_aspect_ratio(alias)
        assert resolved == expected, f"Alias '{alias}' resolved to '{resolved}', expected '{expected}'"


# ---------------------------------------------------------------------------
# 2. Image Options Extraction from Natural Prompts
# ---------------------------------------------------------------------------

def test_parse_image_options():
    cases = [
        (
            "vẽ Raiden Shogun tỉ lệ 16:9 định dạng WEBP",
            "16:9",
            "WEBP",
            "Raiden Shogun",
        ),
        (
            "tạo ảnh Hutao tỷ lệ 1:1 format jpeg",
            "1:1",
            "JPEG",
            "Hutao",
        ),
        (
            "sinh ảnh Furina khung hình 9:16 dạng jpg",
            "9:16",
            "JPEG",
            "Furina",
        ),
        (
            "hãy vẽ cho tôi bức ảnh Zhongli",
            "3:4",
            "PNG",
            "Zhongli",
        ),
        (
            "vẽ Citlali tỉ lệ vuông file png",
            "1:1",
            "PNG",
            "Citlali",
        ),
        (
            "vẽ Mavuika ngang 16:9",
            "16:9",
            "PNG",
            "Mavuika",
        ),
    ]

    for text, exp_ratio, exp_fmt, exp_subj in cases:
        cleaned, ratio, fmt = parse_image_options(text)
        assert ratio == exp_ratio, f"Failed ratio for '{text}': got {ratio}, expected {exp_ratio}"
        assert fmt == exp_fmt, f"Failed format for '{text}': got {fmt}, expected {exp_fmt}"

        is_intent, subj, _ = detect_image_generation_intent(text)
        assert is_intent is True, f"Failed intent detection for '{text}'"
        assert exp_subj.lower() in subj.lower(), f"Subject mismatch for '{text}': got '{subj}', expected '{exp_subj}'"


# ---------------------------------------------------------------------------
# 3. Format Conversion: PNG, WEBP, JPEG
# ---------------------------------------------------------------------------

def test_format_conversions(tmp_path):
    # Create base PNG test image
    base_img_path = tmp_path / "sample_test.png"
    im = Image.new("RGBA", (128, 128), color=(255, 100, 50, 255))
    im.save(base_img_path, format="PNG")
    assert base_img_path.exists()

    # Convert to WEBP
    webp_path = convert_and_save_image(base_img_path, target_format="WEBP")
    assert webp_path.exists()
    assert webp_path.suffix.lower() == ".webp"
    with Image.open(webp_path) as check_webp:
        assert check_webp.format == "WEBP"
        assert check_webp.size == (128, 128)

    # Convert to JPEG
    jpeg_path = convert_and_save_image(base_img_path, target_format="JPEG")
    assert jpeg_path.exists()
    assert jpeg_path.suffix.lower() == ".jpg"
    with Image.open(jpeg_path) as check_jpeg:
        assert check_jpeg.format == "JPEG"
        assert check_jpeg.size == (128, 128)

    # Convert to PNG (idempotent / same extension)
    png_path = convert_and_save_image(base_img_path, target_format="PNG")
    assert png_path == base_img_path


# ---------------------------------------------------------------------------
# 4. Character Researcher Aspect Ratio & Formats Integration
# ---------------------------------------------------------------------------

def test_character_researcher_aspect_ratio_integration():
    char = ResearchedCharacter(
        character_id="test_citlali",
        display_name="Citlali",
        franchise="Genshin Impact",
        summary="Test summary",
        hair_tags="pink hair",
        eye_tags="teal eyes",
        face_tags="cute face",
        outfit_tags="sleepwear",
        accessories_tags="sleep mask",
        weapon_tags="cryo talisman",
        arena_tags="night-wind cavern",
        danbooru_prompt="citlali (genshin impact), 1girl, pink hair, teal eyes",
        recommended_aspect_ratio="3:4",
        supported_aspect_ratios=["1:1", "3:4", "16:9", "9:16"],
        preferred_format="WEBP"
    )

    # Test dimension resolution
    assert char.get_dimensions("1:1") == (1024, 1024)
    assert char.get_dimensions("16:9") == (1344, 768)
    assert char.get_dimensions("9:16") == (768, 1344)
    assert char.get_dimensions() == (768, 1024)

    # Test prompt adaptation
    widescreen_prompt = char.adapt_prompt_for_aspect_ratio("16:9")
    assert "16:9" in widescreen_prompt
    assert "cinematic widescreen" in widescreen_prompt

    vertical_prompt = char.adapt_prompt_for_aspect_ratio("9:16")
    assert "9:16" in vertical_prompt
    assert "full body" in vertical_prompt

    square_prompt = char.adapt_prompt_for_aspect_ratio("1:1")
    assert "1:1" in square_prompt
    assert "square aspect ratio" in square_prompt


# ---------------------------------------------------------------------------
# 5. WeeklyLoreRadar Engine & Scanning
# ---------------------------------------------------------------------------

def test_weekly_radar_scan_and_storage(tmp_path):
    radar = WeeklyLoreRadar(radar_dir=tmp_path)
    report = radar.scan_and_update(force_refresh=True)

    assert isinstance(report, WeeklyRadarReport)
    assert report.total_entries > 0
    assert len(report.characters) >= 4
    assert len(report.outfits) >= 2
    assert len(report.anime_spotlight) >= 2

    # Check disk files
    latest_json = tmp_path / "weekly_radar_latest.json"
    latest_md = tmp_path / "weekly_radar_latest.md"
    assert latest_json.exists(), "weekly_radar_latest.json was not created"
    assert latest_md.exists(), "weekly_radar_latest.md was not created"

    # Verify JSON content
    data = json.loads(latest_json.read_text(encoding="utf-8"))
    assert "week_id" in data
    assert "characters" in data
    assert "outfits" in data
    assert "anime_spotlight" in data


def test_weekly_radar_queries():
    radar = get_weekly_radar()
    report = radar.get_latest_report()
    assert report.total_entries > 0

    # Search for Citlali
    citlali_matches = radar.search_radar("Citlali")
    assert len(citlali_matches) > 0
    citlali_entry = citlali_matches[0]
    assert "Citlali" in citlali_entry.name
    assert citlali_entry.outfit_name == "Whispers of Stars and Smoke"

    # Search for outfit
    outfit_matches = radar.search_radar("Whispers of Stars and Smoke", category="outfit")
    assert len(outfit_matches) > 0
    assert outfit_matches[0].category == "outfit"

    # Search for anime
    anime_matches = radar.get_anime_spotlight()
    assert any("Frieren" in a.name for a in anime_matches)
    assert any("Solo Leveling" in a.franchise for a in anime_matches)

    # Get character by ID
    char_entry = radar.get_character_radar("citlali")
    assert char_entry is not None
    assert char_entry.id == "citlali"


def test_weekly_radar_markdown_digest():
    radar = get_weekly_radar()
    report = radar.get_latest_report()
    md = radar.generate_markdown_report(report)

    assert "# 📡" in md
    assert "Citlali" in md
    assert "Whispers of Stars and Smoke" in md
    assert "16:9" in md
    assert "PNG" in md
    assert "WEBP" in md


# ---------------------------------------------------------------------------
# 6. Static Image Serving with Multi-Format Support
# ---------------------------------------------------------------------------

def test_chat_images_serving_multiformat():
    client = TestClient(app)

    # 1. PNG Image
    png_file = CHAT_IMAGES_DIR / "test_format_check.png"
    im_png = Image.new("RGB", (64, 64), color=(0, 255, 0))
    im_png.save(png_file, format="PNG")

    resp_png = client.get("/api/chat/images/test_format_check.png")
    assert resp_png.status_code == 200
    assert resp_png.headers["content-type"] == "image/png"

    # 2. WEBP Image
    webp_file = CHAT_IMAGES_DIR / "test_format_check.webp"
    im_webp = Image.new("RGB", (64, 64), color=(0, 0, 255))
    im_webp.save(webp_file, format="WEBP")

    resp_webp = client.get("/api/chat/images/test_format_check.webp")
    assert resp_webp.status_code == 200
    assert resp_webp.headers["content-type"] == "image/webp"

    # 3. JPEG Image
    jpg_file = CHAT_IMAGES_DIR / "test_format_check.jpg"
    im_jpg = Image.new("RGB", (64, 64), color=(255, 0, 0))
    im_jpg.save(jpg_file, format="JPEG")

    resp_jpg = client.get("/api/chat/images/test_format_check.jpg")
    assert resp_jpg.status_code == 200
    assert resp_jpg.headers["content-type"] == "image/jpeg"


# ---------------------------------------------------------------------------
# 7. FastAPI Radar Endpoints
# ---------------------------------------------------------------------------

def test_radar_api_endpoints():
    client = TestClient(app)

    # GET /api/radar/weekly
    resp_weekly = client.get("/api/radar/weekly")
    assert resp_weekly.status_code == 200
    data_weekly = resp_weekly.json()
    assert "week_id" in data_weekly
    assert "characters" in data_weekly
    assert data_weekly["total_entries"] > 0

    # POST /api/radar/scan
    resp_scan = client.post("/api/radar/scan")
    assert resp_scan.status_code == 200
    data_scan = resp_scan.json()
    assert data_scan["status"] == "ok"
    assert "report" in data_scan

    # GET /api/radar/search?q=citlali
    resp_search = client.get("/api/radar/search?q=citlali")
    assert resp_search.status_code == 200
    data_search = resp_search.json()
    assert data_search["count"] > 0
    assert any("Citlali" in r["name"] for r in data_search["results"])

    # GET /api/radar/outfits
    resp_outfits = client.get("/api/radar/outfits")
    assert resp_outfits.status_code == 200
    data_outfits = resp_outfits.json()
    assert data_outfits["count"] > 0
    assert any("Whispers of Stars and Smoke" in o["name"] for o in data_outfits["outfits"])

    # GET /api/radar/characters/citlali
    resp_char = client.get("/api/radar/characters/citlali")
    assert resp_char.status_code == 200
    data_char = resp_char.json()
    assert data_char["id"] == "citlali"
    assert data_char["name"] == "Citlali"

    # GET /api/radar/characters/non_existent
    resp_404 = client.get("/api/radar/characters/non_existent_character_999")
    assert resp_404.status_code == 404


# ---------------------------------------------------------------------------
# 8. Phase 2: Engine Junctions, 90s Timeout, User Profile Refs, Startup & Mobile UI
# ---------------------------------------------------------------------------

def test_engine_junctions_and_comfy_dir_resolution():
    from app.chat_image_handler import resolve_comfy_dir

    engine_dir = ROOT / "engine"
    comfy_junction = engine_dir / "ComfyUI"
    moss_junction = engine_dir / "MOSS-Image"

    assert comfy_junction.exists(), "F:\\AI-Office\\engine\\ComfyUI junction missing"
    assert (comfy_junction / "main.py").exists(), "ComfyUI main.py not reachable through junction"
    assert moss_junction.exists(), "F:\\AI-Office\\engine\\MOSS-Image junction missing"

    old_env = os.environ.pop("COMFYUI_PATH", None)
    try:
        resolved = resolve_comfy_dir()
        assert resolved == comfy_junction
    finally:
        if old_env is not None:
            os.environ["COMFYUI_PATH"] = old_env


def test_ensure_comfy_online_timeout_90s():
    import inspect
    from app.chat_image_handler import ensure_comfy_online

    sig = inspect.signature(ensure_comfy_online)
    assert sig.parameters["timeout_secs"].default == 90


def test_user_profile_ref_image_resolution(tmp_path):
    import sqlite3
    from app.chat_image_handler import resolve_user_profile_ref_image

    # Create sample reference image in data/characters/
    chars_dir = ROOT / "data" / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    ref_filename = "test_user_body_ref_temp.png"
    ref_file = chars_dir / ref_filename
    Image.new("RGB", (64, 64), color=(120, 80, 200)).save(ref_file, format="PNG")

    # Create temp SQLite DB with user_profile
    db_file = tmp_path / "test_profile.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("""CREATE TABLE user_profile (
        id TEXT PRIMARY KEY,
        face_ref_url TEXT,
        body_ref_url TEXT
    )""")
    conn.execute(
        "INSERT INTO user_profile (id, face_ref_url, body_ref_url) VALUES ('default', '', ?)",
        (f"/api/chat/images/{ref_filename}",),
    )
    conn.commit()
    conn.close()

    try:
        resolved_name = resolve_user_profile_ref_image(db_path=db_file)
        assert resolved_name == ref_filename
    finally:
        if ref_file.exists():
            ref_file.unlink()
        staged = ROOT / "engine" / "ComfyUI" / "input" / ref_filename
        if staged.exists():
            staged.unlink()


def test_weekly_radar_startup_freshness_check(tmp_path):
    from app.weekly_radar import check_and_refresh_weekly_radar

    radar = WeeklyLoreRadar(radar_dir=tmp_path)
    first_res = check_and_refresh_weekly_radar(max_age_days=7, radar=radar)
    assert first_res["refreshed"] is True
    assert first_res["total_entries"] > 0

    second_res = check_and_refresh_weekly_radar(max_age_days=7, radar=radar)
    assert second_res["refreshed"] is False
    assert second_res["cached"] is True


def test_mobile_ui_ratio_format_and_radar():
    client = TestClient(app)
    resp = client.get("/mobile")
    assert resp.status_code == 200
    html = resp.text

    for ratio in ["1:1", "3:4", "16:9", "9:16"]:
        assert f'data-img-ratio="{ratio}"' in html
    for fmt in ["PNG", "WEBP", "JPEG"]:
        assert f'data-img-format="{fmt}"' in html

    assert 'id="page-radar"' in html
    assert 'id="btn-drawer-radar"' in html
    assert '/api/radar/weekly' in html
    assert '/api/radar/scan' in html
