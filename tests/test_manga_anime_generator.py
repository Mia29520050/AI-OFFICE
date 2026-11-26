# -*- coding: utf-8 -*-
"""
Tests for Manga Anime Prompt Generator & Storyboard CoT
======================================================
Validates 4-component prompt decomposition, character consistency anchors,
and CoT storyboard training dataset integrity.
"""

import json
import pytest
from pathlib import Path

from app.manga_anime_generator import (
    MangaAnimePromptGenerator,
    CharacterAnchor,
    generate_cot_storyboard_sample,
    MODEL_PRESETS,
    ANIME_EMOTIONS,
    DEFAULT_CHARACTERS
)


class TestMangaAnimePromptGenerator:

    def test_default_character_registry(self):
        gen = MangaAnimePromptGenerator()
        assert "minh" in gen.characters
        assert "mai" in gen.characters
        assert "huy" in gen.characters
        assert "koharu" in gen.characters

        minh = gen.characters["minh"]
        assert "[minh_protagonist]" in minh.to_anchor_prompt()
        assert "short messy black hair" in minh.to_anchor_prompt()

    def test_custom_character_registration(self):
        gen = MangaAnimePromptGenerator()
        custom_char = CharacterAnchor(
            id="char_ren",
            name="Ren",
            gender="male",
            hair_tags="spiky crimson red hair",
            eye_tags="golden eyes",
            face_tags="scar over left eyebrow",
            outfit_tags="black ninja trench coat",
            consistency_token="[ren_shinobi]"
        )
        gen.register_character(custom_char)

        assert "ren" in gen.characters
        prompt = gen.build_panel_prompt(character_names=["Ren"])
        assert "[ren_shinobi]" in prompt.full_positive_prompt
        assert "spiky crimson red hair" in prompt.full_positive_prompt

    def test_four_mandatory_components(self):
        gen = MangaAnimePromptGenerator()
        panel_prompt = gen.build_panel_prompt(
            panel_number=1,
            character_names=["Mai"],
            emotion_key="tsundere_pout",
            pose_key="leaning_forward",
            camera_key="close_up",
            background_key="japanese_classroom",
            vfx_key="focus_burst",
            model_preset="animagine_xl"
        )

        # 1. Art style component
        assert len(panel_prompt.art_style_component) > 10
        assert "screentone" in panel_prompt.art_style_component.lower()

        # 2. Locked character traits component
        assert len(panel_prompt.character_traits_component) > 10
        assert "[mai_heroine]" in panel_prompt.character_traits_component
        assert "chestnut brown hair" in panel_prompt.character_traits_component

        # 3. Emotion and pose component
        assert len(panel_prompt.emotion_and_pose_component) > 10
        assert "pouting" in panel_prompt.emotion_and_pose_component
        assert "leaning forward" in panel_prompt.emotion_and_pose_component

        # 4. Background and camera component
        assert len(panel_prompt.background_and_camera_component) > 10
        assert "close-up" in panel_prompt.background_and_camera_component
        assert "japanese high school classroom" in panel_prompt.background_and_camera_component

        # Check full combined positive & negative
        assert panel_prompt.art_style_component in panel_prompt.full_positive_prompt
        assert panel_prompt.character_traits_component in panel_prompt.full_positive_prompt
        assert panel_prompt.emotion_and_pose_component in panel_prompt.full_positive_prompt
        assert panel_prompt.background_and_camera_component in panel_prompt.full_positive_prompt
        assert "bad anatomy" in panel_prompt.full_negative_prompt

    def test_character_consistency_across_panels(self):
        gen = MangaAnimePromptGenerator()
        scene = [
            {"characters": ["Minh"], "emotion": "determined_focus", "pose": "leaning_forward"},
            {"characters": ["Minh"], "emotion": "jaw_drop_shock", "pose": "turning_around"},
            {"characters": ["Minh"], "emotion": "anime_sweatdrop", "pose": "casual_seated"},
        ]
        prompts = gen.harmonize_scene_panels("Scene test", scene, model_preset="animagine_xl")

        assert len(prompts) == 3
        # Invariant character anchor tags must be identical
        char_tag_0 = prompts[0].character_traits_component
        char_tag_1 = prompts[1].character_traits_component
        char_tag_2 = prompts[2].character_traits_component

        assert char_tag_0 == char_tag_1 == char_tag_2
        assert prompts[0].consistency_hash == prompts[1].consistency_hash == prompts[2].consistency_hash

    def test_model_presets_generation(self):
        gen = MangaAnimePromptGenerator()
        for preset_key in MODEL_PRESETS.keys():
            p = gen.build_panel_prompt(character_names=["Minh"], model_preset=preset_key)
            assert p.model_preset == preset_key
            assert len(p.full_positive_prompt) > 50
            assert len(p.full_negative_prompt) > 20

    def test_storyboard_cot_sample_generation(self):
        sample = generate_cot_storyboard_sample(
            scene_id=1,
            story_theme="Thử nghiệm phân cảnh đối thoại",
            characters=["Minh", "Mai"],
            panels_data=[
                {"characters": ["Minh"], "emotion": "determined_focus", "pose": "leaning_forward"},
                {"characters": ["Mai"], "emotion": "tsundere_pout", "pose": "arms_crossed"}
            ],
            model_preset="animagine_xl"
        )

        assert sample["id"] == "manga_storyboard_cot_00001"
        assert sample["category"] == "manga_storyboard_consistency"
        assert len(sample["messages"]) == 3

        asst_msg = sample["messages"][2]["content"]
        assert "<think>" in asst_msg
        assert "</think>" in asst_msg

        # CoT reasoning check
        think_part = asst_msg.split("</think>")[0].replace("<think>", "")
        assert "StoryDiffusion" in think_part
        assert "4 thành phần" in think_part or "Locked Traits" in think_part

        # Outside think check
        after_think = asst_msg.split("</think>")[1]
        assert "[Panel 1]" in after_think
        assert "[Panel 2]" in after_think
        assert "Positive Prompt (ComfyUI)" in after_think

    def test_v7_scene_specification_rule_of_thirds(self):
        from app.manga_anime_generator import get_vampire_knight_v7_scene_specification, COMPOSITION_LAYOUTS
        spec = get_vampire_knight_v7_scene_specification()
        assert len(spec["panels"]) == 3

        for p in spec["panels"]:
            assert "prompt_plan" in p
            assert p["composition"] in COMPOSITION_LAYOUTS
            char_zone = p["character_zone"]
            bubble_zone = p["safe_bubble_zone"]

            # Mathematical proof of zero overlap between character zone and safe bubble zone
            # char_zone = [ymin, xmin, ymax, xmax]
            # bubble_zone = [ymin, xmin, ymax, xmax]
            y_overlap = max(0.0, min(char_zone[2], bubble_zone[2]) - max(char_zone[0], bubble_zone[0]))
            x_overlap = max(0.0, min(char_zone[3], bubble_zone[3]) - max(char_zone[1], bubble_zone[1]))
            overlap_area = y_overlap * x_overlap
            assert overlap_area == 0.0, f"Panel {p['panel_number']} character zone overlaps safe bubble zone!"

            # Anti-AI-plastic prompt check
            pos_prompt = p["prompt_plan"]["full_positive_prompt"]
            neg_prompt = p["prompt_plan"]["full_negative_prompt"]
            assert "authentic 2D anime illustration" in pos_prompt
            assert "glowing neon" in neg_prompt
            assert "smooth plastic skin" in neg_prompt
            assert "fractal" in neg_prompt

    def test_dataset_file_integrity(self):
        dataset_path = Path("data/training/manga_storyboard_cot.jsonl")
        assert dataset_path.exists(), "Dataset file must exist at data/training/manga_storyboard_cot.jsonl"
        assert dataset_path.stat().st_size > 100_000, "Dataset must not be empty"

        count = 0
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                assert "id" in item
                assert "messages" in item
                assert "<think>" in item["messages"][2]["content"]
                assert "</think>" in item["messages"][2]["content"]
                count += 1

        assert count >= 300, f"Expected at least 300 samples, got {count}"
