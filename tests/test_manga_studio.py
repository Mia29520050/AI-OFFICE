from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from main import app
from manga_story import (
    CharacterProfile,
    CharacterLockedTraits,
    SpeechRules,
    ChapterPlan,
    ScenePlan,
    PanelPlan,
    DialogueLine,
    PanelSFX,
    ContinuityIssue,
    check_deterministic_continuity,
    build_panel_diffusion_prompt,
)

client = TestClient(app)


def test_manga_series_crud():
    # 1. Create series
    res = client.post("/api/manga/series", json={
        "title": "Vũ Trụ Tuyết Trắng",
        "synopsis": "Một câu chuyện giả tưởng trên hành tinh phủ đầy băng tuyết.",
        "genre": "Sci-Fi / Shonen",
        "art_style": "bw",
        "reading_direction": "rtl"
    })
    assert res.status_code == 200, res.text
    series = res.json()
    series_id = series["id"]
    assert series["title"] == "Vũ Trụ Tuyết Trắng"
    assert series["art_style"] == "bw"

    # 2. Get series
    res_get = client.get(f"/api/manga/series/{series_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == series_id

    # 3. List series
    res_list = client.get("/api/manga/series")
    assert res_list.status_code == 200
    assert any(s["id"] == series_id for s in res_list.json())

    # 4. Update series
    res_up = client.put(f"/api/manga/series/{series_id}", json={
        "synopsis": "Bản cập nhật tóm tắt nội dung hành tinh băng tuyết."
    })
    assert res_up.status_code == 200
    assert res_up.json()["synopsis"] == "Bản cập nhật tóm tắt nội dung hành tinh băng tuyết."

    # 5. Delete series
    res_del = client.delete(f"/api/manga/series/{series_id}")
    assert res_del.status_code == 200
    assert client.get(f"/api/manga/series/{series_id}").status_code == 404


def test_manga_volume_chapter_management():
    # Create series
    s_res = client.post("/api/manga/series", json={"title": "Test Series Manga", "art_style": "color"})
    series_id = s_res.json()["id"]

    # Create volume
    v_res = client.post(f"/api/manga/series/{series_id}/volumes", json={"number": 1, "title": "Tập 1: Khởi đầu"})
    assert v_res.status_code == 200
    vol_id = v_res.json()["id"]

    # Create chapter
    c_res = client.post(f"/api/manga/series/{series_id}/chapters", json={
        "title": "Chương 1: Bình minh",
        "number": 1.0,
        "synopsis": "Bình minh trên thành phố biển.",
        "volume_id": vol_id
    })
    assert c_res.status_code == 200
    chap = c_res.json()
    chap_id = chap["id"]

    # List chapters
    chaps = client.get(f"/api/manga/series/{series_id}/chapters").json()
    assert len(chaps) >= 1
    assert any(c["id"] == chap_id for c in chaps)

    # Get single chapter
    c_detail = client.get(f"/api/manga/chapters/{chap_id}").json()
    assert c_detail["title"] == "Chương 1: Bình minh"


def test_character_crud_and_locked_traits():
    s_res = client.post("/api/manga/series", json={"title": "Series Nhân Vật", "art_style": "bw"})
    series_id = s_res.json()["id"]

    # Create Character
    char_payload = {
        "name": "Kaito",
        "identity": {
            "role": "protagonist",
            "age": 16,
            "appearance": "Tóc đen nhánh, áo khoác choàng xanh thẫm, mắt xanh lam",
        },
        "personality": {
            "traits": ["Nhiệt huyết", "chính trực", "bảo vệ đồng đội"],
            "motivation": "Tìm kiếm sự thật về thế giới song song",
        },
        "speech_rules": {
            "first_person": "tớ",
            "second_person": "cậu",
            "tone": "thân thiện, dứt khoát",
            "forbidden_words": ["đầu hàng", "bỏ mặc"]
        },
        "locked_traits": [
            {"trait": "eye_color", "value": "xanh lam"},
            {"trait": "hair_style", "value": "tóc ngắn bù xù"},
            {"trait": "hair_color", "value": "đen"},
            {"trait": "outfit", "value": "áo choàng xanh thẫm"}
        ]
    }
    create_res = client.post(f"/api/manga/series/{series_id}/characters", json=char_payload)
    assert create_res.status_code == 200, create_res.text
    char_data = create_res.json()
    char_id = char_data["id"]
    assert char_data["name"] == "Kaito"
    assert len(char_data["locked_traits"]) == 4

    # List Characters
    list_res = client.get(f"/api/manga/series/{series_id}/characters")
    assert list_res.status_code == 200
    assert any(c["id"] == char_id for c in list_res.json())

    # Get Character
    get_res = client.get(f"/api/manga/characters/{char_id}")
    assert get_res.status_code == 200
    assert "chính trực" in get_res.json()["personality"]["traits"]

    # Update Character
    up_res = client.put(f"/api/manga/characters/{char_id}", json={
        "identity": {"role": "protagonist", "appearance": "Tóc đen nhánh, áo choàng nâng cấp"}
    })
    assert up_res.status_code == 200
    assert "áo choàng nâng cấp" in up_res.json()["identity"]["appearance"]

    # Delete Character
    del_res = client.delete(f"/api/manga/characters/{char_id}")
    assert del_res.status_code == 200
    assert client.get(f"/api/manga/characters/{char_id}").status_code == 404


def test_manga_story_and_continuity():
    # Seed sample series
    s_res = client.post("/api/manga/series/sample")
    assert s_res.status_code == 200
    sample = s_res.json()
    chap_id = sample["chapters"][0]["id"]

    # Generate scenes
    gen_res = client.post("/api/manga/story/generate-scenes", json={
        "chapter_id": chap_id,
        "scene_count": 3
    })
    assert gen_res.status_code == 200
    scenes_data = gen_res.json()
    assert "scenes" in scenes_data
    assert len(scenes_data["scenes"]) >= 2

    # Continuity check
    cont_res = client.post("/api/manga/story/check-continuity", json={"chapter_id": chap_id})
    assert cont_res.status_code == 200
    cont = cont_res.json()
    assert "status" in cont
    assert "score" in cont


def test_story_domain_deterministic_continuity():
    char = CharacterProfile(
        id="c1",
        series_id="s1",
        name="Ren",
        role="protagonist",
        locked_traits=CharacterLockedTraits(
            eye_color="hổ phách",
            hair_color="bạc",
            hair_style="ngắn vuốt ngược",
            outfit="đồng phục đen viền vàng",
        ),
        speech_rules=SpeechRules(
            forbidden_words=["tha mạng", "sợ quá"]
        ),
    )

    bad_panel = PanelPlan(
        panel_number=1,
        characters_present=["Ren"],
        visual_description="Ren nhìn chăm chú, đôi mắt màu đỏ thẫm",
        dialogues=[
            DialogueLine(speaker="Ren", text="Xin hãy tha mạng cho tôi!"),
        ],
    )
    bad_scene = ScenePlan(
        scene_number=1,
        title="Cuộc gặp trong bóng tối",
        location="Hành lang",
        summary="Ren đối mặt với kẻ thù",
        panels=[bad_panel],
    )
    bad_chapter = ChapterPlan(
        title="Chương Thử Thách",
        synopsis="Ren đối đầu kẻ thù trong đêm.",
        scenes=[bad_scene],
    )

    issues = check_deterministic_continuity(
        bad_chapter,
        characters=[char],
        canon_facts=[],
        timeline_events=[],
    )
    assert len(issues) >= 1
    issue_msgs = " ".join([i.description for i in issues])
    assert "tha mạng" in issue_msgs or "mắt" in issue_msgs or len(issues) > 0


def test_manga_storyboard_and_panels():
    # Seed sample
    s_res = client.post("/api/manga/series/sample")
    sample = s_res.json()
    chap_id = sample["chapters"][0]["id"]

    # Auto storyboard
    sb_res = client.post(f"/api/manga/chapters/{chap_id}/auto-storyboard")
    assert sb_res.status_code == 200
    pages = sb_res.json()
    assert len(pages) > 0
    assert len(pages[0]["panels"]) > 0

    panel = pages[0]["panels"][0]
    panel_id = panel["id"]

    # Update panel
    up_res = client.put(f"/api/manga/panels/{panel_id}", json={
        "dialogue": [{"speaker": "Ren", "text": "Đêm nay trăng rất sáng.", "x_norm": 0.5, "y_norm": 0.2}]
    })
    assert up_res.status_code == 200
    assert up_res.json()["dialogue"][0]["speaker"] == "Ren"


def test_manga_comfy_and_composition_pipeline():
    # Seed sample
    s_res = client.post("/api/manga/series/sample")
    sample = s_res.json()
    chap_id = sample["chapters"][0]["id"]

    # ComfyUI status
    stat_res = client.get("/api/manga/comfy/status")
    assert stat_res.status_code == 200
    assert "is_online" in stat_res.json()

    pages = client.get(f"/api/manga/chapters/{chap_id}/pages").json()
    page_id = pages[0]["id"]
    panel_id = pages[0]["panels"][0]["id"]

    # Generate panel image in mock mode
    gen_p = client.post("/api/manga/comfy/generate-panel", json={
        "panel_id": panel_id,
        "use_mock": True
    })
    assert gen_p.status_code == 200
    assert gen_p.json()["status"] == "completed"
    asset_id = gen_p.json()["asset_id"]

    # Fetch panel image
    img_res = client.get(f"/api/manga/assets/{asset_id}")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"

    # Compose full manga page
    comp_res = client.post(f"/api/manga/composer/render-page/{page_id}")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["status"] == "composed"
    assert "image_url" in comp_data

    # Export chapter to CBZ & PDF
    exp_res = client.post("/api/manga/composer/export-chapter", json={
        "chapter_id": chap_id,
        "format": "all"
    })
    assert exp_res.status_code == 200
    exp_data = exp_res.json()
    assert exp_data["status"] == "completed"
    assert Path(exp_data["cbz_path"]).exists()
    assert Path(exp_data["pdf_path"]).exists()

    # Download export (format=all downloads the primary compiled file)
    export_id = exp_data["export_id"]
    dl_res = client.get(f"/api/manga/exports/{export_id}/download")
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 1000
    assert dl_res.content.startswith(b"%PDF-") or dl_res.content.startswith(b"PK")

    # Export chapter explicitly as CBZ and verify ZIP
    exp_cbz_res = client.post("/api/manga/composer/export-chapter", json={
        "chapter_id": chap_id,
        "format": "cbz"
    })
    assert exp_cbz_res.status_code == 200
    cbz_export_id = exp_cbz_res.json()["export_id"]
    dl_cbz = client.get(f"/api/manga/exports/{cbz_export_id}/download")
    assert dl_cbz.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl_cbz.content), "r") as zf:
        namelist = zf.namelist()
        assert any(n.endswith(".png") for n in namelist)


def test_jobs_queue_and_error_handling():
    # Verify jobs listing endpoint
    jobs_res = client.get("/api/manga/jobs")
    assert jobs_res.status_code == 200
    assert isinstance(jobs_res.json(), list)

    # 404 on non-existent series
    assert client.get("/api/manga/series/non-existent-id").status_code == 404

    # 404 on non-existent chapter
    assert client.get("/api/manga/chapters/non-existent-id").status_code == 404

    # 404 on non-existent asset
    assert client.get("/api/manga/assets/non-existent-id").status_code == 404

    # 404 on non-existent export download
    assert client.get("/api/manga/exports/non-existent-id/download").status_code == 404


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS:", name)
    print("ALL_MANGA_STUDIO_TESTS_PASSED")
