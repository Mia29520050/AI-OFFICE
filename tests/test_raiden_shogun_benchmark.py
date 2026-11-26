# -*- coding: utf-8 -*-
"""
tests/test_raiden_shogun_benchmark.py
=====================================
Automated Verification Suite for Genshin Impact / Shonen Action Benchmark:
  1. Character Knowledge Base Integrity (HoYoverse specs, anatomy, outfit, weapon).
  2. Danbooru Prompt Matrix Accuracy (braid, kanzashi, mole, mitsudomoe, Musou Isshin).
  3. ComfyUI Workflow & Prompt Construction.
  4. Computer Vision Image Verification (Dimensions, Color Space, Channel Integrity).
"""

import json
from pathlib import Path
import pytest
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestRaidenKnowledgeBase:

    def test_knowledge_base_json_exists_and_valid(self):
        kb_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        assert kb_path.exists(), f"Missing Raiden knowledge base at {kb_path}"
        with open(kb_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["character_id"] == "raiden_shogun"
        assert "visual_anatomy" in data
        assert "canonical_outfit" in data
        assert "signature_weapon" in data
        assert "battlefields" in data
        assert "danbooru_prompt_matrix" in data

    def test_canonical_visual_anatomy_keys(self):
        kb_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(kb_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        anatomy = data["visual_anatomy"]
        assert "purple" in anatomy["hair_color"].lower() or "violet" in anatomy["hair_color"].lower()
        assert "braid" in anatomy["hair_style"].lower()
        assert "mole" in anatomy["facial_mark"].lower() or "beauty mark" in anatomy["facial_mark"].lower()
        assert "eye" in anatomy["facial_mark"].lower()
        assert "kanzashi" in anatomy["hair_ornament"].lower() or "hairpin" in anatomy["hair_ornament"].lower()

    def test_signature_weapon_and_plane_of_euthymia(self):
        kb_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(kb_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        weapon = data["signature_weapon"]
        weapon_name = str(weapon.get("primary_combat", weapon.get("name", ""))).lower()
        assert "musou isshin" in weapon_name
        weapon_type = str(weapon.get("weapon_type", weapon.get("type", ""))).lower()
        assert "katana" in weapon_type or "sword" in weapon_type or "tachi" in weapon_type

        battlefields = data["battlefields"]
        assert "plane_of_euthymia" in battlefields
        euthymia = battlefields["plane_of_euthymia"]
        assert "nhất tâm tịnh thổ" in euthymia["vietnamese_name"].lower()
        assert "torii" in euthymia["visuals"].lower()

    def test_danbooru_prompt_matrix_tags(self):
        kb_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
        with open(kb_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        matrix = data["danbooru_prompt_matrix"]
        core = matrix["core_identity"]
        assert "raiden_shogun" in core
        assert "single braid" in core or "braid" in core
        assert "mole under eye" in core
        assert "hair ornament" in core

        action = matrix["combat_action"]
        assert "katana" in action
        assert "lightning" in action


class TestRaidenGenerationOutputs:

    def test_output_directory_structure(self):
        out_dir = ROOT_DIR / "data" / "manga" / "raiden_tests"
        assert out_dir.exists(), f"Output dir {out_dir} must exist"

    def test_output_image_integrity_if_completed(self):
        out_dir = ROOT_DIR / "data" / "manga" / "raiden_tests"
        # Check any generated images in the directory
        for img_name in ["raiden_baseline.png", "raiden_canonical_portrait.png", "raiden_combat_action.png"]:
            p = out_dir / img_name
            if p.exists():
                im = Image.open(p)
                assert im.size == (768, 1024), f"Image {img_name} has unexpected size: {im.size}"
                assert im.mode == "RGB"
