from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
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
    ReaderChoice,
    StoryBranch,
    BranchingProgression,
    BranchingProgressionRequest,
    BranchingProgressionResponse,
    PlotTwistSuggestion,
    CharacterConflict,
    PlotTwistAndChoiceRequest,
    PlotTwistAndChoiceResponse,
    MangaStoryEngine,
    generate_fallback_branching_progression,
    generate_fallback_plot_twists_and_choices,
    generate_story_branching,
    suggest_plot_twists_and_choices,
    create_sample_story_data,
    build_panel_diffusion_prompt,
)
from main import app

client = TestClient(app)


# ==============================================================================
# 1. Pydantic Domain Schemas & Validation Tests
# ==============================================================================

def test_reader_choice_model():
    choice = ReaderChoice(
        choice_id="choice_test_1",
        route_target="route_a",
        text="Đột kích vào trung tâm gác chuông cấm",
        intent_tone="aggressive",
        consequence_hint="Đánh động quân tuần tra nhưng cứu nguy kịp thời",
        risk_reward="Rủi ro: Cao | Thưởng: Lớn"
    )
    dumped = choice.model_dump()
    assert dumped["route_target"] == "route_a"
    assert dumped["intent_tone"] == "aggressive"

    # Validator normalizes invalid tone to "tactical"
    choice_norm = ReaderChoice(
        route_target="route_b",
        text="Lẩn trốn",
        intent_tone="unknown_tone"  # type: ignore
    )
    assert choice_norm.intent_tone == "tactical"


def test_story_branch_model_and_cleaning():
    branch = StoryBranch(
        route_id="route_a",
        route_name="Route A: Đột Kích Tiên Phong",
        branch_type="action_heroic",
        choice_trigger="Nhân vật rút kiếm tấn công",
        synopsis="Đột phá vòng vây",
        central_conflict="Áp lực thể lực",
        key_twist="Lõi quái thú chứa linh hồn người quen",
        character_impacts={"Ren": "Cấm ấn bộc phát 40%"},
        consequences=["Phá hủy hộ vệ"],
        scenes=[
            {
                "scene_number": 1,
                "title": "Khai chiến",
                "location": "Gác chuông",
                "summary": "Ren giao chiến",
                "panels": [
                    {
                        "panel_number": 1,
                        "visual_description": "Ren chém kiếm bóng tối",
                        "camera_angle": "close_up"
                    }
                ]
            }
        ],
        cliffhanger="Cánh cửa hầm mở ra",
        next_decision_prompt="Nên nhảy vào hầm hay rút lui?"
    )

    assert branch.route_id == "route_a"
    assert len(branch.scenes) == 1
    assert branch.scenes[0].title == "Khai chiến"
    assert len(branch.scenes[0].panels) == 1
    assert branch.scenes[0].panels[0].visual_description == "Ren chém kiếm bóng tối"

    # branch_type normalization
    branch_norm = StoryBranch(
        route_id="route_custom",
        route_name="Route Tùy biến",
        branch_type="invalid_type",  # type: ignore
        choice_trigger="Lựa chọn",
        synopsis="Tóm tắt"
    )
    assert branch_norm.branch_type == "action_heroic"


def test_plot_twist_and_conflict_models():
    twist = PlotTwistSuggestion(
        title="Thân Phận Kẻ Phản Bội",
        twist_type="identity-reveal",  # tests kebab-case normalization
        summary="Cố vấn học viện thực chất là gián điệp",
        impact_level="seismic",
        foreshadowing_clues=["Chiếc đồng hồ chạy chậm", "Ánh mắt lẩn tránh"],
        character_reactions={"Ren": "Bàng hoàng", "Luna": "Cảnh giác"},
        compatible_routes=["route_a", "route_b"]
    )
    assert twist.twist_type == "identity_reveal"
    assert twist.impact_level == "seismic"
    assert len(twist.foreshadowing_clues) == 2

    conflict = CharacterConflict(
        characters_involved=["Ren", "Luna"],
        conflict_type="clashing-methods",  # tests kebab-case normalization
        core_friction="Khác biệt giữa tuân thủ luật lệ và sinh tồn thực dụng",
        escalation_triggers=["Ren tự ý mở phong ấn"],
        resolution_paths=["Đấu kiếm tìm tiếng nói chung"],
        narrative_tension_score=9
    )
    assert conflict.conflict_type == "clashing_methods"
    assert conflict.narrative_tension_score == 9


# ==============================================================================
# 2. Deterministic Fallback Generation Tests
# ==============================================================================

def test_deterministic_fallback_branching_progression():
    sample = create_sample_story_data()
    req = BranchingProgressionRequest(
        series_title=sample["series"]["title"],
        genre=sample["series"]["genre"],
        art_style="b_w",
        premise="Ren và Luna chạm trán thực thể hắc ám thức tỉnh tại gác chuông cấm.",
        chapter_number=1,
        chapter_title="Chương 1: Đêm Trăng Đen Khai Giảng",
        current_scene_context="Cánh cửa sắt bật mở, luồng khói đen bí ẩn cuồn cuộn tràn ra sàn đá.",
        decision_prompt="Thời khắc quyết định: Đối mặt trực diện, thâm nhập trong im lặng, hay đàm phán cấm thuật?",
        characters=sample["characters"],
        canon_facts=sample["canon_facts"],
        timeline_events=sample["timeline_events"],
        branch_count=3
    )

    prog = generate_fallback_branching_progression(req)

    # 1. Progression structure
    assert isinstance(prog, BranchingProgression)
    assert prog.series_title == req.series_title
    assert prog.chapter_number == 1
    assert "thời khắc quyết định" in prog.decision_point.lower()
    assert "gác chuông" in req.premise.lower()

    # 2. Exactly 3 distinct routes: Route A, Route B, Route C
    assert len(prog.routes) == 3
    route_ids = [r.route_id for r in prog.routes]
    assert route_ids == ["route_a", "route_b", "route_c"]

    # 3. Route styles and contents
    route_a = prog.routes[0]
    route_b = prog.routes[1]
    route_c = prog.routes[2]

    assert route_a.branch_type == "action_heroic"
    assert "Đột Kích" in route_a.route_name
    assert any("Ren" in k for k in route_a.character_impacts)
    assert len(route_a.scenes) >= 1
    assert len(route_a.consequences) >= 1
    assert route_a.cliffhanger != ""

    assert route_b.branch_type == "stealth_investigation"
    assert "Bóng Tối" in route_b.route_name or "Xâm Nhập" in route_b.route_name
    assert "Shirakawa" in route_b.key_twist or "gia tộc" in route_b.key_twist.lower()

    assert route_c.branch_type == "forbidden_alliance"
    assert "Đồng Minh" in route_c.route_name
    assert len(route_c.scenes) >= 1

    # 4. Diffusion prompt auto-population on all panels
    for r in prog.routes:
        for sc in r.scenes:
            for p in sc.panels:
                assert p.diffusion_prompt_en != ""
                assert "screentone" in p.diffusion_prompt_en.lower() or "masterpiece" in p.diffusion_prompt_en.lower()
                assert p.diffusion_negative_prompt != ""

    # 5. Reader choices
    assert len(prog.reader_choices) == 3
    choice_targets = {c.route_target for c in prog.reader_choices}
    assert choice_targets == {"route_a", "route_b", "route_c"}
    for ch in prog.reader_choices:
        assert ch.text != ""
        assert ch.risk_reward != ""
        assert ch.consequence_hint != ""

    # 6. Divergence analysis
    assert "Route A" in prog.divergence_analysis
    assert "Route B" in prog.divergence_analysis
    assert "Route C" in prog.divergence_analysis


def test_deterministic_fallback_plot_twists_and_choices():
    sample = create_sample_story_data()
    req = PlotTwistAndChoiceRequest(
        series_title=sample["series"]["title"],
        genre=sample["series"]["genre"],
        current_context="Ren và Luna phát hiện mật thất dưới gác chuông",
        characters=sample["characters"],
        canon_facts=sample["canon_facts"],
        num_twists=3,
        num_conflicts=2,
        num_choices=3
    )

    resp = generate_fallback_plot_twists_and_choices(req)
    assert isinstance(resp, PlotTwistAndChoiceResponse)
    assert len(resp.plot_twists) == 3
    assert len(resp.character_conflicts) == 2
    assert len(resp.reader_choices) == 3
    assert resp.mode_used == "fallback_template"

    # Validate plot twists
    twist_types = {t.twist_type for t in resp.plot_twists}
    assert "identity_reveal" in twist_types
    assert "world_rule_inversion" in twist_types
    for t in resp.plot_twists:
        assert len(t.foreshadowing_clues) > 0
        assert len(t.character_reactions) > 0

    # Validate character conflicts
    for c in resp.character_conflicts:
        assert len(c.characters_involved) >= 2
        assert c.core_friction != ""
        assert len(c.escalation_triggers) > 0
        assert 1 <= c.narrative_tension_score <= 10


# ==============================================================================
# 3. MangaStoryEngine & Mock LLM Flow Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_engine_offline_fallback():
    engine = MangaStoryEngine(model_manager=None)
    sample = create_sample_story_data()

    req = BranchingProgressionRequest(
        series_title="Test Series",
        premise="Test Premise",
        characters=sample["characters"]
    )
    res = await engine.generate_branching_progression(req)
    assert res.mode_used == "fallback_template"
    assert len(res.progression.routes) == 3

    twist_req = PlotTwistAndChoiceRequest(
        series_title="Test Series",
        current_context="Test Context",
        characters=sample["characters"]
    )
    twist_res = await engine.suggest_plot_twists_and_choices(twist_req)
    assert twist_res.mode_used == "fallback_template"
    assert len(twist_res.plot_twists) >= 1


@pytest.mark.asyncio
async def test_engine_with_mock_llm_success():
    mock_llm_json = {
        "series_title": "Cuộc Chiến Ánh Sáng",
        "chapter_number": 2,
        "decision_point": "Kẻ địch bao vây: Đột kích trực diện hay thâm nhập mật thất?",
        "decision_context": "Bị bao vây tại sảnh chính",
        "routes": [
            {
                "route_id": "route_a",
                "route_name": "Route A: Đột Kích Hỏa Lực",
                "branch_type": "action_heroic",
                "choice_trigger": "Mở toàn bộ kết giới",
                "synopsis": "Tấn công xuyên phá kẻ thù",
                "central_conflict": "Hao tổn ma lực",
                "key_twist": "Kẻ chỉ huy là người quen",
                "character_impacts": {"Ren": "Tự tin hơn"},
                "consequences": ["Hạ gục chỉ huy"],
                "scenes": [
                    {
                        "scene_number": 1,
                        "title": "Cú Đấm Sấm Sét",
                        "location": "Sảnh chính",
                        "time_of_day": "night",
                        "summary": "Ren chém kiếm",
                        "characters_present": ["Ren"],
                        "emotional_beat": "action",
                        "panels": [
                            {
                                "panel_number": 1,
                                "camera_angle": "close_up",
                                "visual_description": "Ren chém kiếm năng lượng",
                                "characters_in_panel": ["Ren"],
                                "diffusion_prompt_en": "masterpiece, close up, sword strike",
                                "dialogues": [{"speaker": "Ren", "text": "Biến đi!", "bubble_type": "shout"}]
                            }
                        ]
                    }
                ],
                "cliffhanger": "Tướng địch xuất hiện"
            },
            {
                "route_id": "route_b",
                "route_name": "Route B: Mật Đạo Ngầm",
                "branch_type": "stealth_investigation",
                "choice_trigger": "Rút lui xuống đường hầm",
                "synopsis": "Đi vòng sau lưng căn cứ",
                "central_conflict": "Cạm bẫy cổ xưa",
                "key_twist": "Bản đồ giả",
                "character_impacts": {"Luna": "Khám phá sự thật"},
                "consequences": ["Thu thập tin tức"],
                "scenes": [
                    {
                        "scene_number": 1,
                        "title": "Bóng Đêm Hầm Ngầm",
                        "location": "Đường hầm",
                        "time_of_day": "dark",
                        "summary": "Hai người lẩn trốn",
                        "characters_present": ["Ren", "Luna"],
                        "emotional_beat": "mystery",
                        "panels": [
                            {
                                "panel_number": 1,
                                "camera_angle": "wide_shot",
                                "visual_description": "Đi trong bóng tối",
                                "characters_in_panel": ["Ren", "Luna"],
                                "dialogues": []
                            }
                        ]
                    }
                ],
                "cliffhanger": "Cánh cửa sắt đóng sập"
            },
            {
                "route_id": "route_c",
                "route_name": "Route C: Thương Lượng Hòa Hoãn",
                "branch_type": "forbidden_alliance",
                "choice_trigger": "Gửi tín hiệu đình chiến",
                "synopsis": "Đàm phán với tướng địch",
                "central_conflict": "Nghi ngờ phản trắc",
                "key_twist": "Kẻ thù cũng muốn lật đổ hội đồng",
                "character_impacts": {},
                "consequences": ["Hiệp ước bí mật"],
                "scenes": [
                    {
                        "scene_number": 1,
                        "title": "Bàn Tròn Đình Chiến",
                        "location": "Phòng đàm phán",
                        "time_of_day": "night",
                        "summary": "Hai bên gặp mặt",
                        "characters_present": ["Ren"],
                        "emotional_beat": "tension",
                        "panels": [
                            {
                                "panel_number": 1,
                                "camera_angle": "medium_shot",
                                "visual_description": "Hai người bắt tay",
                                "characters_in_panel": ["Ren"],
                                "dialogues": []
                            }
                        ]
                    }
                ],
                "cliffhanger": "Hiệp ước được ký"
            }
        ],
        "reader_choices": [
            {"choice_id": "c1", "route_target": "route_a", "text": "Đột kích trực diện"},
            {"choice_id": "c2", "route_target": "route_b", "text": "Thâm nhập đường hầm"},
            {"choice_id": "c3", "route_target": "route_c", "text": "Thương lượng hòa hoãn"}
        ],
        "divergence_analysis": "Ba con đường với phong cách hành động, trinh thám và ngoại giao.",
        "recommended_route": "route_a"
    }

    class MockModelManager:
        async def runtime_ready(self):
            return True, "Mock Ollama ready"

        async def chat(self, messages, **kwargs):
            return json.dumps(mock_llm_json)

        def active_route(self):
            return {"model": "qwen3.5:4b-mock"}

    mock_mgr = MockModelManager()
    engine = MangaStoryEngine(model_manager=mock_mgr)

    req = BranchingProgressionRequest(
        series_title="Cuộc Chiến Ánh Sáng",
        premise="Bị bao vây tại sảnh chính",
        characters=[CharacterProfile(name="Ren"), CharacterProfile(name="Luna")]
    )
    res = await engine.generate_branching_progression(req)
    assert res.mode_used == "ollama"
    assert res.model_name == "qwen3.5:4b-mock"
    assert len(res.progression.routes) == 3
    assert res.progression.routes[0].route_name == "Route A: Đột Kích Hỏa Lực"
    # Ensure diffusion prompts auto-filled for panel without one
    assert res.progression.routes[1].scenes[0].panels[0].diffusion_prompt_en != ""


@pytest.mark.asyncio
async def test_engine_llm_failure_graceful_recovery():
    class BrokenModelManager:
        async def runtime_ready(self):
            return True, "Mock ready"

        async def chat(self, messages, **kwargs):
            return "This is not valid JSON and cannot be parsed at all!"

        def active_route(self):
            return {"model": "qwen3.5:4b"}

    broken_mgr = BrokenModelManager()
    engine = MangaStoryEngine(model_manager=broken_mgr)

    req = BranchingProgressionRequest(
        series_title="Fallback Series",
        premise="Test Premise",
        characters=[CharacterProfile(name="Ren")]
    )
    res = await engine.generate_branching_progression(req)
    # Recovers cleanly to fallback template
    assert res.mode_used == "fallback_template"
    assert len(res.progression.routes) == 3
    assert "Fallback due to" in str(res.raw_model_response)


# ==============================================================================
# 4. FastAPI Endpoints Integration Tests (/api/manga/story/...)
# ==============================================================================

def test_api_story_branching_standalone():
    payload = {
        "series_title": "Học Viện Thần Kiếm",
        "genre": "Shonen Fantasy",
        "art_style": "bw",
        "premise": "Thời khắc sinh tử tại đền thờ thần kiếm cổ.",
        "chapter_number": 3,
        "chapter_title": "Chương 3: Lưỡi Kiếm Ngủ Vùi",
        "decision_prompt": "Nhân vật chính nên rút thần kiếm hay phong ấn nó mãi mãi?",
        "branch_count": 3
    }
    res = client.post("/api/manga/story/branching", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "progression" in data
    prog = data["progression"]
    assert len(prog["routes"]) == 3
    assert [r["route_id"] for r in prog["routes"]] == ["route_a", "route_b", "route_c"]
    assert len(prog["reader_choices"]) == 3


def test_api_story_branching_with_chapter_id():
    # First seed a sample series to get a real chapter_id
    sample_res = client.post("/api/manga/series/sample")
    assert sample_res.status_code == 200
    sample_data = sample_res.json()
    chap_id = sample_data["chapters"][0]["id"]

    res = client.post("/api/manga/story/branching", json={
        "chapter_id": chap_id,
        "decision_prompt": "Tình huống rẽ nhánh từ dữ liệu chapter DB:"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "progression" in data
    assert len(data["progression"]["routes"]) == 3


def test_api_story_suggest_twists_and_choices():
    payload = {
        "series_title": "Học Viện Thần Kiếm",
        "genre": "Shonen Fantasy",
        "current_context": "Nhân vật chính phát hiện người cố vấn từng rút thanh thần kiếm 20 năm trước.",
        "num_twists": 3,
        "num_conflicts": 2,
        "num_choices": 3
    }
    res = client.post("/api/manga/story/suggest-twists-and-choices", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "plot_twists" in data
    assert len(data["plot_twists"]) == 3
    assert "character_conflicts" in data
    assert len(data["character_conflicts"]) == 2
    assert "reader_choices" in data
    assert len(data["reader_choices"]) == 3


def test_api_story_routes_template():
    res = client.get("/api/manga/story/routes-template")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert "sample_branching" in data
    assert "sample_twists" in data
    assert len(data["sample_branching"]["routes"]) == 3
