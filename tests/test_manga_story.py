from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from manga_story import (
    SpeechRules,
    CharacterLockedTraits,
    CharacterProfile,
    CanonFact,
    TimelineEvent,
    DialogueLine,
    PanelSFX,
    PanelPlan,
    ScenePlan,
    ChapterPlan,
    ContinuityIssue,
    ContinuityReport,
    StoryGenerationRequest,
    StoryGenerationResponse,
    ContinuityCheckRequest,
    ContinuityCheckResponse,
    extract_json_payload,
    build_panel_diffusion_prompt,
    check_deterministic_continuity,
    generate_fallback_chapter,
    MangaStoryEngine,
    create_sample_story_data,
    generate_chapter_plan,
    run_continuity_check,
)


def test_character_profile_and_speech_rules():
    speech = SpeechRules(
        first_person="tớ",
        second_person="cậu",
        tone="thờ ơ, bí ẩn",
        forbidden_words=["tha mạng", "đại ca"]
    )
    traits = CharacterLockedTraits(
        gender="boy",
        hair_color="black",
        hair_style="messy shonen hair",
        eye_color="crimson red",
        signature_outfit="black gakuran",
        diffusion_positive_tags="1boy, messy black hair, crimson red eyes, black gakuran"
    )
    char = CharacterProfile(
        name="Kurogane Ren",
        role="protagonist",
        speech_rules=speech,
        locked_traits=traits
    )

    dumped = char.model_dump()
    assert dumped["name"] == "Kurogane Ren"
    assert dumped["speech_rules"]["first_person"] == "tớ"
    assert dumped["locked_traits"]["hair_color"] == "black"

    # Re-validate from dict
    restored = CharacterProfile.model_validate(dumped)
    assert restored.name == char.name
    assert restored.speech_rules.forbidden_words == ["tha mạng", "đại ca"]


def test_diffusion_prompt_builder():
    traits = CharacterLockedTraits(
        gender="boy",
        hair_color="black",
        eye_color="red",
        signature_outfit="gakuran",
        diffusion_positive_tags="1boy, black hair, red eyes, gakuran",
        diffusion_negative_tags="blonde hair"
    )
    char = CharacterProfile(name="Ren", locked_traits=traits)

    panel = PanelPlan(
        panel_number=1,
        camera_angle="close_up",
        visual_description="Ren draws his sword fiercely",
        characters_in_panel=["Ren"]
    )

    pos, neg = build_panel_diffusion_prompt(panel, [char], art_style="b_w")
    assert "screentone" in pos
    assert "close-up shot" in pos
    assert "1boy, black hair, red eyes, gakuran" in pos
    assert "Ren draws his sword fiercely" in pos
    assert "blonde hair" in neg
    assert "bad anatomy" in neg

    # Color style
    pos_color, _ = build_panel_diffusion_prompt(panel, [char], art_style="color")
    assert "vibrant japanese anime aesthetic" in pos_color


def test_extract_json_payload():
    # Clean json
    assert extract_json_payload('{"title": "Test"}') == {"title": "Test"}

    # Markdown wrapped
    md_raw = """
    Sau đây là kết quả phân tích:
    ```json
    {
        "title": "Chương 1",
        "valid": true
    }
    ```
    Chúc bạn vui vẻ!
    """
    parsed = extract_json_payload(md_raw)
    assert parsed["title"] == "Chương 1"
    assert parsed["valid"] is True

    # Think block wrapped (Qwen style)
    think_raw = """
    <think>
    Tôi cần tạo một dàn ý chương truyện phù hợp.
    </think>
    {
        "scenes": [],
        "count": 0
    }
    """
    assert extract_json_payload(think_raw) == {"scenes": [], "count": 0}

    # Trailing commas repair
    broken_comma = '{"items": [1, 2, ], "desc": "ok", }'
    assert extract_json_payload(broken_comma) == {"items": [1, 2], "desc": "ok"}


def test_deterministic_continuity_checks():
    ren = CharacterProfile(
        name="Ren",
        speech_rules=SpeechRules(first_person="tớ", second_person="cậu", forbidden_words=["tha mạng"]),
        locked_traits=CharacterLockedTraits(hair_color="black")
    )
    luna = CharacterProfile(
        name="Luna",
        speech_rules=SpeechRules(first_person="tôi", second_person="bạn")
    )
    fact = CanonFact(
        title="Luật Hắc Nguyệt",
        fact="Con người không thể hồi sinh người chết",
        severity="immutable"
    )

    # 1. Test speaker not present in scene
    bad_scene_1 = ScenePlan(
        scene_number=1,
        title="Scene 1",
        location="Roof",
        summary="Roof encounter",
        characters_present=["Ren"],  # Luna is NOT here
        panels=[
            PanelPlan(
                panel_number=1,
                visual_description="Roof view",
                dialogues=[
                    DialogueLine(speaker="Luna", text="Chào Ren! Cậu ở đây làm gì?")
                ]
            )
        ]
    )
    ch1 = ChapterPlan(title="Ch 1", synopsis="Syn", scenes=[bad_scene_1])
    issues = check_deterministic_continuity(ch1, [ren, luna], [fact], [])
    assert any(i.issue_type == "location_jump" and "Luna" in i.entity_affected for i in issues)

    # 2. Test forbidden words violation
    bad_scene_2 = ScenePlan(
        scene_number=1,
        title="Scene 1",
        location="Room",
        summary="Fight",
        characters_present=["Ren"],
        panels=[
            PanelPlan(
                panel_number=1,
                visual_description="Ren kneeling",
                dialogues=[
                    DialogueLine(speaker="Ren", text="Xin hãy tha mạng cho tôi!")
                ]
            )
        ]
    )
    ch2 = ChapterPlan(title="Ch 2", synopsis="Syn", scenes=[bad_scene_2])
    issues2 = check_deterministic_continuity(ch2, [ren], [fact], [])
    assert any(i.issue_type == "speech_rule_violation" and "tha mạng" in i.description for i in issues2)

    # 3. Test locked trait appearance conflict in diffusion prompt
    bad_scene_3 = ScenePlan(
        scene_number=1,
        title="Scene 1",
        location="Street",
        summary="Walk",
        characters_present=["Ren"],
        panels=[
            PanelPlan(
                panel_number=1,
                visual_description="Ren walks",
                characters_in_panel=["Ren"],
                diffusion_prompt_en="masterpiece, 1boy, blonde hair, blue eyes"  # Ren has black hair!
            )
        ]
    )
    ch3 = ChapterPlan(title="Ch 3", synopsis="Syn", scenes=[bad_scene_3])
    issues3 = check_deterministic_continuity(ch3, [ren], [fact], [])
    assert any(i.issue_type == "appearance_conflict" for i in issues3)


def test_fallback_generator():
    data = create_sample_story_data()
    req = StoryGenerationRequest(
        series_title=data["series"]["title"],
        genre=data["series"]["genre"],
        premise="Ren và Luna điều tra gác chuông cổ",
        chapter_number=1,
        characters=data["characters"],
        canon_facts=data["canon_facts"],
        timeline_events=data["timeline_events"]
    )

    fallback = generate_fallback_chapter(req)
    assert fallback.chapter_number == 1
    assert len(fallback.scenes) >= 2
    assert len(fallback.scenes[0].panels) >= 2

    # Check that dialogues are in Vietnamese and use appropriate character names
    p1 = fallback.scenes[0].panels[0]
    assert len(p1.dialogues) > 0
    assert p1.diffusion_prompt_en != ""
    assert p1.diffusion_negative_prompt != ""


@pytest.mark.anyio
async def test_story_engine_offline_execution():
    engine = MangaStoryEngine(model_manager=None)
    data = create_sample_story_data()
    req = StoryGenerationRequest(
        series_title=data["series"]["title"],
        premise="Bí ẩn gác chuông",
        characters=data["characters"]
    )

    res = await engine.generate_chapter(req)
    assert res.mode_used == "fallback_template"
    assert res.chapter_plan.title != ""
    assert len(res.chapter_plan.scenes) > 0

    # Continuity check
    check_req = ContinuityCheckRequest(
        chapter_plan=res.chapter_plan,
        characters=data["characters"],
        canon_facts=data["canon_facts"],
        timeline_events=data["timeline_events"]
    )
    chk_res = await engine.check_continuity(check_req)
    assert chk_res.report.is_consistent is True
    assert chk_res.report.score >= 80


@pytest.mark.anyio
async def test_story_engine_with_mock_llm():
    class MockModelManager:
        def __init__(self):
            self.calls = []

        async def runtime_ready(self):
            return True, ""

        def active_route(self):
            return {"mode": "local", "model": "qwen3.5:4b"}

        async def chat(self, messages, json_mode=False, num_predict=800, temperature=0.25):
            self.calls.append(messages)
            # Return valid ChapterPlan JSON
            sample_chapter = {
                "chapter_number": 2,
                "title": "Chương 2: Lưỡi Kiếm Ngân Nguyệt",
                "synopsis": "Luna kích hoạt kiếm quang đánh lui quái vật bóng tối.",
                "central_conflict": "Quái thú bóng tối bao vây gác chuông",
                "climax": "Luna tung chiêu kiếm ánh sáng thanh tẩy",
                "cliffhanger_or_ending": "Vết nứt không gian thứ hai xuất hiện",
                "estimated_pages": 4,
                "canon_references_used": ["Hiệu Ứng Trăng Đỏ"],
                "character_arcs_progressed": ["Shirakawa Luna"],
                "scenes": [
                    {
                        "scene_number": 1,
                        "title": "Giao Chiến",
                        "location": "Gác chuông",
                        "time_of_day": "night",
                        "summary": "Luna một mình cản đường quái thú.",
                        "characters_present": ["Shirakawa Luna"],
                        "emotional_beat": "action",
                        "conflict": "Quái thú quá nhanh",
                        "outcome": "Luna đẩy lùi đợt tấn công đầu tiên",
                        "panels": [
                            {
                                "panel_number": 1,
                                "layout_hint": "wide",
                                "camera_angle": "medium_shot",
                                "visual_description": "Luna vung kiếm ánh sáng",
                                "characters_in_panel": ["Shirakawa Luna"],
                                "diffusion_prompt_en": "1girl, silver hair, glowing sword, dynamic action",
                                "diffusion_negative_prompt": "bad anatomy",
                                "dialogues": [
                                    {
                                        "speaker": "Shirakawa Luna",
                                        "text": "Lũ quái vật bóng tối, đừng hòng bước qua đây!",
                                        "bubble_type": "shout",
                                        "emotion": "determined"
                                    }
                                ],
                                "sfx": [{"text": "XOẸT!", "meaning": "Kiếm quang chém qua không khí"}],
                                "focus_element": "Lưỡi kiếm phát sáng"
                            }
                        ]
                    }
                ]
            }
            return json.dumps(sample_chapter, ensure_ascii=False)

    mock_mgr = MockModelManager()
    engine = MangaStoryEngine(model_manager=mock_mgr)

    data = create_sample_story_data()
    req = StoryGenerationRequest(
        series_title="Moonlight Classroom",
        premise="Luna chiến đấu",
        chapter_number=2,
        characters=data["characters"]
    )

    resp = await engine.generate_chapter(req)
    assert resp.mode_used == "ollama"
    assert resp.chapter_plan.title == "Chương 2: Lưỡi Kiếm Ngân Nguyệt"
    assert resp.chapter_plan.chapter_number == 2
    assert len(resp.chapter_plan.scenes) == 1
    assert resp.chapter_plan.scenes[0].panels[0].dialogues[0].speaker == "Shirakawa Luna"
    assert len(mock_mgr.calls) == 1
