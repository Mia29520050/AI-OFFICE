# -*- coding: utf-8 -*-
"""
tests/test_raiden_shogun_knowledge_base.py
==========================================
Unit tests for Genshin Impact / Raiden Shogun Character Knowledge Base:
  1. JSON Schema & Required Canonical Fields Verification.
  2. Markdown Character Sheet & Anti-Hallucination Anchors.
  3. Registration in Manga Anime Generator (DEFAULT_CHARACTERS & MODEL_PRESETS).
  4. Benchmark 3-Tier Test Specification & Prompt Matrix.
"""

import json
from pathlib import Path
import pytest

from app.manga_anime_generator import (
    DEFAULT_CHARACTERS,
    MODEL_PRESETS,
    MangaAnimePromptGenerator,
    get_raiden_shogun_genshin_scene_specification,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestRaidenShogunKnowledgeBase:

    def test_json_file_exists_and_parses(self):
        json_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        assert json_path.exists(), "raiden_shogun_genshin.json must exist in data/characters/"

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["character_id"] == "raiden_shogun"
        assert "Genshin Impact" in data["origin"]
        assert "Electro" in data["element"]

    def test_visual_anatomy_anchors(self):
        json_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        anatomy = data["visual_anatomy"]
        # Mandatory canonical anchors
        assert "braid" in anatomy["hair_style"].lower()
        assert "purple" in anatomy["hair_color"].lower()
        assert "mole" in anatomy["facial_mark"].lower() or "beauty mark" in anatomy["facial_mark"].lower()
        assert "right eye" in anatomy["facial_mark"].lower()
        assert "kanzashi" in anatomy["hair_ornament"].lower() or "hairpin" in anatomy["hair_ornament"].lower()

    def test_canonical_outfit_and_weapons(self):
        json_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        outfit = data["canonical_outfit"]
        assert "kimono" in outfit["kimono"].lower()
        assert "single" in outfit["shoulder_armor"].lower() and "left" in outfit["shoulder_armor"].lower()
        assert "mitsudomoe" in outfit["waist_obi"].lower()
        assert "thighhigh" in outfit["legwear"].lower() or "thigh-high" in outfit["legwear"].lower()

        weapon = data["signature_weapon"]
        assert "musou isshin" in weapon["primary_combat"].lower()
        assert "katana" in weapon["weapon_type"].lower() or "tachi" in weapon["weapon_type"].lower()
        assert "lightning" in weapon["blade_visuals"].lower()

    def test_battlefields_plane_of_euthymia(self):
        json_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        battlefields = data["battlefields"]
        assert "plane_of_euthymia" in battlefields
        euthymia = battlefields["plane_of_euthymia"]
        assert "Nhất Tâm Tịnh Thổ" in euthymia["vietnamese_name"]
        assert "torii" in euthymia["visuals"].lower()
        assert "red" in euthymia["visuals"].lower() or "crimson" in euthymia["visuals"].lower()

    def test_danbooru_prompt_matrix_and_anti_hallucination(self):
        json_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        matrix = data["danbooru_prompt_matrix"]
        assert "mole_under_eye" in matrix["canonical_tags"]
        assert "single_braid" in matrix["canonical_tags"]
        assert "musou isshin" in matrix["combat_action"].lower()
        assert "plane_of_euthymia" in matrix["plane_of_euthymia_env"].lower()

        # Negative prompt must shield against blonde hair, western knight armor, and 3D cgi
        neg = matrix["negative_anti_hallucination"].lower()
        assert "blonde" in neg
        assert "western" in neg or "knight" in neg
        assert "3d render" in neg or "cgi" in neg

    def test_markdown_character_sheet_files_exist(self):
        sheet_data = ROOT_DIR / "data" / "characters" / "raiden_shogun_character_sheet.md"
        sheet_docs = ROOT_DIR / "docs" / "RAIDEN_SHOGUN_CHARACTER_SHEET.md"
        assert sheet_data.exists(), "data/characters/raiden_shogun_character_sheet.md must exist"
        assert sheet_docs.exists(), "docs/RAIDEN_SHOGUN_CHARACTER_SHEET.md must exist"

        content = sheet_data.read_text(encoding="utf-8")
        assert "Nhất Tâm Tịnh Thổ" in content
        assert "Musou Isshin" in content
        assert "mole_under_eye" in content
        assert "Danbooru" in content

    def test_character_anchor_registered_in_generator(self):
        assert "raiden_shogun" in DEFAULT_CHARACTERS
        assert "raiden" in DEFAULT_CHARACTERS
        assert "ei" in DEFAULT_CHARACTERS
        assert "loi_than" in DEFAULT_CHARACTERS

        anchor = DEFAULT_CHARACTERS["raiden_shogun"]
        assert anchor.gender == "female"
        assert "braid" in anchor.hair_tags
        assert "mole" in anchor.face_tags
        assert "kimono" in anchor.outfit_tags
        assert "musou isshin" in anchor.accessories_tags

        prompt_str = anchor.to_anchor_prompt()
        assert "[raiden_shogun_genshin]" in prompt_str
        assert "braid" in prompt_str

    def test_genshin_shonen_action_preset_registered(self):
        assert "genshin_shonen_action" in MODEL_PRESETS
        preset = MODEL_PRESETS["genshin_shonen_action"]
        assert "shonen manga action" in preset["style_prefix"].lower()
        assert "lightning" in preset["style_prefix"].lower()

    def test_scene_specification_benchmark_cases(self):
        spec = get_raiden_shogun_genshin_scene_specification()
        assert spec["character_id"] == "raiden_shogun"
        assert "benchmark_test_cases" in spec or "benchmark_tests" in spec

        # Verify test cases
        tests = spec.get("benchmark_test_cases") or spec.get("benchmark_tests")
        assert len(tests) >= 3
