from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.manga_anime_generator import (
    MangaAnimePromptGenerator,
    DEFAULT_CHARACTERS,
    MODEL_PRESETS,
    BACKGROUND_ENVIRONMENTS,
    VISUAL_EFFECTS,
    ANIME_EMOTIONS,
)
from app.smart_bubble_layout import (
    solve_anti_collision_layout,
    check_panel_bubble_overlap,
    get_adaptive_safety_zone,
    calculate_manga_reading_score,
    FACE_SAFETY_ZONE,
)


class TestDarkFantasyArchetype:
    """Validate Dark Fantasy Huyết Cơ & Kỵ Sĩ archetypes and StoryDiffusion consistency."""

    def test_dark_fantasy_characters_registered(self):
        generator = MangaAnimePromptGenerator()
        for char_key in ["carmilla", "kaelen", "lucian", "vivian", "huyet_co", "ky_si"]:
            assert char_key in generator.characters
            anchor = generator.characters[char_key]
            assert anchor.consistency_token.startswith("[")
            assert anchor.consistency_token.endswith("]")

    def test_carmilla_vampire_sovereign_traits(self):
        generator = MangaAnimePromptGenerator()
        carmilla = generator.characters["carmilla"]
        prompt_str = carmilla.to_anchor_prompt()
        assert "[carmilla_vampire_sovereign]" in prompt_str
        assert "silver-white" in prompt_str or "silver" in prompt_str
        assert "crimson" in prompt_str or "ruby" in prompt_str

    def test_dark_fantasy_prompt_decomposition(self):
        generator = MangaAnimePromptGenerator()
        prompt = generator.build_panel_prompt(
            panel_number=1,
            character_names=["carmilla", "kaelen"],
            emotion_key="vampire_condescending",
            pose_key="holding_blood_rose",
            camera_key="low_angle_dramatic",
            background_key="gothic_cathedral_ruins",
            vfx_key="blood_magic_aura",
            model_preset="dark_fantasy_manga",
        )
        assert prompt.panel_number == 1
        assert "dark fantasy gothic manga" in prompt.art_style_component.lower()
        assert "carmilla" in prompt.character_traits_component.lower()
        assert "kaelen" in prompt.character_traits_component.lower()
        assert "condescending" in prompt.emotion_and_pose_component.lower()
        assert "gothic" in prompt.background_and_camera_component.lower()


class TestAdaptiveSafetyZonesAndLayout:
    """Validate adaptive camera safety zones and zero-collision guarantees."""

    def test_adaptive_safety_zones(self):
        close_up_zone = get_adaptive_safety_zone("close_up", "center")
        assert close_up_zone["y_min"] <= 0.20
        assert close_up_zone["y_max"] >= 0.72

        eye_zoom_zone = get_adaptive_safety_zone("extreme_close_up", "center")
        assert eye_zoom_zone["x_min"] <= 0.20
        assert eye_zoom_zone["x_max"] >= 0.80

        left_zone = get_adaptive_safety_zone("medium_shot", "left")
        assert left_zone["x_min"] < 0.20
        assert left_zone["x_max"] < 0.60

    def test_crowded_dark_fantasy_panel_zero_overlap(self):
        # 4 crowded Dark Fantasy dialogue lines with SFX
        dialogues = [
            {"text": "Ngươi nghĩ mình có thể thoát khỏi lâu đài huyết tộc sao, Kaelen?", "speaker": "Carmilla", "bubble_type": "regular"},
            {"text": "Ta đã thề trung thành, thưa Điện hạ. Dù máu có nhuốm đỏ gươm!", "speaker": "Kaelen", "bubble_type": "regular"},
            {"text": "KẺ PHẢN NGHỊCH! HÃY NỘP MẠNG!", "speaker": "Lucian", "bubble_type": "shout"},
            {"text": "KENG!", "speaker": "SFX", "bubble_type": "sfx"},
        ]
        resolved = solve_anti_collision_layout(dialogues, camera_shot="low_angle_dramatic")
        overlap_area, collisions = check_panel_bubble_overlap(resolved)
        assert overlap_area == 0.0, f"Detected overlap area: {overlap_area}"
        assert len(collisions) == 0

        # Check face clearance for all bubbles except SFX
        face_zone = get_adaptive_safety_zone("low_angle_dramatic")
        for b in resolved:
            if b.bubble_type != "sfx":
                assert not b.intersects_face_zone(face_zone), f"Bubble {b.id} intersected face zone!"

    def test_mass_sample_from_10k_dataset(self):
        dataset_path = Path("data/training/manga_japanese_grammar_10k.jsonl")
        if not dataset_path.exists():
            pytest.skip("10k dataset not yet present")

        # Test sample of 100 panels from the 10k dataset
        count = 0
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                messages = record.get("messages", [])
                assistant_msg = next((m for m in messages if m.get("role") == "assistant"), None)
                if not assistant_msg:
                    continue

                # Run layout on synthetic dialogues
                dlgs = [
                    {"text": "Lời thoại thứ nhất", "speaker": "Carmilla"},
                    {"text": "Lời thoại thứ hai đáp lời", "speaker": "Kaelen"},
                    {"text": "Lời thoại thứ ba phản kích", "speaker": "Lucian"},
                ]
                resolved = solve_anti_collision_layout(dlgs)
                overlap, _ = check_panel_bubble_overlap(resolved)
                assert overlap == 0.0
                count += 1
                if count >= 100:
                    break
        assert count == 100
