from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from manga_benchmark import (
    MINH_REFERENCE_SPEC,
    BENCHMARK_TEST_CASES,
    BenchmarkTestCase,
    CharacterBenchmarkSpec,
    get_benchmark_spec_dict,
    export_benchmark_specs_to_json,
)
from manga_story import CharacterProfile, CharacterLockedTraits, SpeechRules


def test_minh_reference_character_spec():
    spec = MINH_REFERENCE_SPEC
    assert spec.name == "Minh"
    assert spec.age == 16
    assert spec.gender == "1boy"
    assert "black" in spec.physical_locked_traits["hair_color"]
    assert "amber" in spec.physical_locked_traits["eye_color"]
    assert "navy blue blazer" in spec.costume_locked_traits["blazer"]
    assert "charcoal" in spec.costume_locked_traits["trousers"]
    assert "minh_character" in spec.trigger_tags
    assert "skirt" in spec.negative_prompt

    # Test conversion to manga_story.CharacterProfile
    profile = CharacterProfile(
        name=spec.name,
        role="protagonist",
        locked_traits=CharacterLockedTraits(
            gender="boy",
            hair_color=spec.physical_locked_traits["hair_color"],
            hair_style=spec.physical_locked_traits["hair_style"],
            eye_color=spec.physical_locked_traits["eye_color"],
            signature_outfit="navy blue blazer, white shirt, dark tie, charcoal trousers",
            diffusion_positive_tags=spec.trigger_tags,
            diffusion_negative_tags=spec.negative_prompt
        ),
        speech_rules=SpeechRules(
            first_person="tớ",
            second_person="cậu",
            tone="thận trọng, kiên định"
        )
    )
    assert profile.name == "Minh"
    assert profile.locked_traits.hair_color == "black"
    assert "minh_character" in profile.locked_traits.diffusion_positive_tags


def test_eight_benchmark_test_cases_integrity():
    assert len(BENCHMARK_TEST_CASES) == 8, f"Expected exactly 8 benchmark test cases, found {len(BENCHMARK_TEST_CASES)}"

    expected_ids = [
        "tc1_portrait",
        "tc2_fullbody",
        "tc3_classroom",
        "tc4_two_characters",
        "tc5_camera_angles",
        "tc6_bw_manga",
        "tc7_color_anime",
        "tc8_four_panel_sequence"
    ]

    found_ids = [tc.test_id for tc in BENCHMARK_TEST_CASES]
    assert found_ids == expected_ids, f"Test IDs mismatch: {found_ids} != {expected_ids}"

    # Verify each case has required fields and resolution
    for tc in BENCHMARK_TEST_CASES:
        assert tc.title != ""
        assert tc.evaluation_focus != ""
        assert "minh_character" in tc.prompt_positive or "minh_character" in tc.prompt_positive.lower()
        assert tc.prompt_negative != ""
        assert len(tc.recommended_resolution) == 2
        width, height = tc.recommended_resolution
        assert width >= 512 and height >= 512
        assert len(tc.pass_criteria) >= 3

    # Check specific test cases
    # TC1: Portrait
    tc1 = BENCHMARK_TEST_CASES[0]
    assert tc1.category == "portrait"
    assert "amber eyes" in tc1.prompt_positive

    # TC2: Full body
    tc2 = BENCHMARK_TEST_CASES[1]
    assert tc2.category == "fullbody"
    assert "full body shot" in tc2.prompt_positive
    assert "trouser" in tc2.prompt_positive

    # TC3: Classroom
    tc3 = BENCHMARK_TEST_CASES[2]
    assert tc3.category == "classroom_environment"
    assert "classroom" in tc3.prompt_positive

    # TC4: Two characters
    tc4 = BENCHMARK_TEST_CASES[3]
    assert tc4.category == "multi_character"
    assert "mai_character" in tc4.prompt_positive

    # TC5: Camera angles
    tc5 = BENCHMARK_TEST_CASES[4]
    assert tc5.category == "camera_angles"
    assert "low-angle" in tc5.prompt_positive

    # TC6: B&W Manga
    tc6 = BENCHMARK_TEST_CASES[5]
    assert tc6.category == "bw_manga"
    assert tc6.art_style == "manga_bw"
    assert "screentone" in tc6.prompt_positive

    # TC7: Color Anime
    tc7 = BENCHMARK_TEST_CASES[6]
    assert tc7.category == "color_anime"
    assert tc7.art_style == "anime_color"
    assert "cel-shading" in tc7.prompt_positive

    # TC8: 4-Panel Sequence
    tc8 = BENCHMARK_TEST_CASES[7]
    assert tc8.category == "sequential_continuity"
    assert tc8.sequential_panels is not None
    assert len(tc8.sequential_panels) == 4


def test_export_and_json_loading(tmp_path):
    target_file = tmp_path / "test_benchmark_prompts.json"
    exported_path = export_benchmark_specs_to_json(target_file)
    assert exported_path.exists()

    with open(exported_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert "benchmark_metadata" in loaded
    assert loaded["benchmark_metadata"]["total_test_cases"] == 8
    assert len(loaded["test_cases"]) == 8

    # Verify standard benchmark file in data/manga/benchmarks/
    default_file = Path(r"F:\AI-Office\data\manga\benchmarks\benchmark_prompts.json")
    assert default_file.exists(), "Default benchmark prompts JSON must exist on disk"
    with open(default_file, "r", encoding="utf-8") as f:
        default_loaded = json.load(f)
    assert default_loaded["benchmark_metadata"]["total_test_cases"] == 8
