from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from fastapi.testclient import TestClient
from main import app, connect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_official_chapter1")
client = TestClient(app)


def generate_moonlight_classroom_chapter1():
    print("=" * 70)
    print("  PRODUCING OFFICIAL CHAPTER 1: 'MOONLIGHT CLASSROOM'")
    print("  Title: 'Chương 1: Thế giới đã thay đổi'")
    print("=" * 70)

    # 1. Create Series
    series_resp = client.post("/api/manga/series", json={
        "title": "MOONLIGHT CLASSROOM",
        "synopsis": "Một buổi sáng thức dậy, nam sinh nhận ra toàn bộ thế giới học đường đã đảo lộn: tất cả nam sinh và cả thầy giáo đều mặc đồng phục váy nữ sinh theo quy định năm 1990. Chỉ duy nhất cậu còn giữ lại ký ức về thế giới cũ.",
        "genre": "Bí ẩn · Học đường · Tâm lý · Giả tưởng",
        "art_style": "bw",
        "reading_direction": "rtl"
    })
    assert series_resp.status_code == 200, series_resp.text
    series = series_resp.json()
    series_id = series["id"]
    print(f"\n[1] Series Registered: {series['title']} (ID: {series_id})")

    # 2. Create Volume 1
    vol_resp = client.post(f"/api/manga/series/{series_id}/volumes", json={
        "number": 1,
        "title": "Tập 1: Thực Tại Đảo Chiều"
    })
    assert vol_resp.status_code == 200
    volume = vol_resp.json()
    vol_id = volume["id"]
    print(f"[2] Volume Registered: {volume['title']} (ID: {vol_id})")

    # 3. Create Chapter 1
    chap_resp = client.post(f"/api/manga/series/{series_id}/chapters", json={
        "volume_id": vol_id,
        "number": 1.0,
        "title": "Chương 1: Thế giới đã thay đổi",
        "synopsis": "Lớp học buổi sáng tĩnh lặng bên cửa sổ bỗng biến thành cơn ác mộng tâm lý khi nhân vật chính nhận ra sự dị thường của toàn bộ nam sinh và thầy giáo."
    })
    assert chap_resp.status_code == 200
    chapter = chap_resp.json()
    chap_id = chapter["id"]
    print(f"[3] Chapter Registered: {chapter['title']} (ID: {chap_id})")

    # 4. Register the 4 Characters
    # Character 1: Protagonist (Nam sinh)
    char1_payload = {
        "name": "Kurogane Ren",
        "identity": {
            "role": "protagonist",
            "age": 16,
            "appearance": "Sơ mi trắng, cà vạt xanh đậm, blazer xanh navy, quần dài tối màu, tóc đen ngắn rối nhẹ"
        },
        "personality": {
            "traits": ["Quan sát sắc bén", "hoài nghi", "bình tĩnh che giấu cảm xúc"],
            "motivation": "Tìm hiểu nguồn gốc biến dạng thực tại và sinh tồn"
        },
        "speech_rules": {
            "first_person": "tớ",
            "second_person": "cậu",
            "tone": "thận trọng, thăm dò",
            "forbidden_words": ["tha mạng", "đầu hàng"]
        },
        "locked_traits": [
            {"trait": "gender", "value": "nam"},
            {"trait": "hair_color", "value": "đen"},
            {"trait": "hair_style", "value": "ngắn rối nhẹ"},
            {"trait": "outfit", "value": "sơ mi trắng, cà vạt xanh đậm, blazer xanh navy, quần dài tối màu"}
        ]
    }
    c1 = client.post(f"/api/manga/series/{series_id}/characters", json=char1_payload).json()
    print(f"[4.1] Character 1: '{c1['name']}' (Protagonist - Quần dài tối màu)")

    # Character 2: Nữ sinh cùng bàn
    char2_payload = {
        "name": "Mizuki Yuka",
        "identity": {
            "role": "heroine",
            "age": 16,
            "appearance": "Tóc nâu ngang vai, blouse trắng, cardigan kem, chân váy xanh navy, nơ xanh nhạt"
        },
        "personality": {
            "traits": ["Dịu dàng", "ngây thơ", "tuân thủ quy củ tự nhiên"],
            "motivation": "Học tập và quan tâm bạn bè cùng lớp"
        },
        "speech_rules": {
            "first_person": "mình",
            "second_person": "cậu",
            "tone": "nhẹ nhàng, thân thiện",
            "forbidden_words": ["mày", "tao"]
        },
        "locked_traits": [
            {"trait": "gender", "value": "nữ"},
            {"trait": "hair_color", "value": "nâu"},
            {"trait": "hair_style", "value": "ngang vai uốn nhẹ"},
            {"trait": "outfit", "value": "blouse trắng, cardigan kem, chân váy xanh navy, nơ xanh nhạt"}
        ]
    }
    c2 = client.post(f"/api/manga/series/{series_id}/characters", json=char2_payload).json()
    print(f"[4.2] Character 2: '{c2['name']}' (Nữ sinh cùng bàn)")

    # Character 3: Nam sinh tóc nâu xoăn
    char3_payload = {
        "name": "Tanaka Kenji",
        "identity": {
            "role": "classmate",
            "age": 16,
            "appearance": "Tóc nâu xoăn, blouse trắng, cardigan xanh nhạt, váy nữ sinh xếp ly"
        },
        "personality": {
            "traits": ["Năng nổ", "vô tư", "thấy việc mặc váy là bình thường từ xưa đến nay"],
            "motivation": "Chơi bóng rổ và nói chuyện phiếm giờ ra chơi"
        },
        "speech_rules": {
            "first_person": "tớ",
            "second_person": "cậu",
            "tone": "hào sảng, sảng khoái",
            "forbidden_words": ["nghiêm túc"]
        },
        "locked_traits": [
            {"trait": "gender", "value": "nam"},
            {"trait": "hair_color", "value": "nâu"},
            {"trait": "hair_style", "value": "xoăn tự nhiên"},
            {"trait": "outfit", "value": "blouse trắng, cardigan xanh nhạt, váy nữ sinh xếp ly"}
        ]
    }
    c3 = client.post(f"/api/manga/series/{series_id}/characters", json=char3_payload).json()
    print(f"[4.3] Character 3: '{c3['name']}' (Nam sinh tóc nâu xoăn - Váy xếp ly)")

    # Character 4: Thầy giáo Toán
    char4_payload = {
        "name": "Thầy Takahashi",
        "identity": {
            "role": "antagonist",
            "age": 38,
            "appearance": "Tóc đen hơi dài, kính tròn, áo blouse trắng, cardigan be, nơ xanh đậm, chân váy công sở đen"
        },
        "personality": {
            "traits": ["Nghiêm khắc", "lạnh lùng", "ánh mắt quan sát che giấu nụ cười kỳ dị"],
            "motivation": "Duy trì kỷ cương học viện theo quy định năm 1990"
        },
        "speech_rules": {
            "first_person": "thầy",
            "second_person": "các em",
            "tone": "trịnh trọng, đanh thép, bí hiểm",
            "forbidden_words": ["xin lỗi", "nhầm lẫn"]
        },
        "locked_traits": [
            {"trait": "gender", "value": "nam"},
            {"trait": "hair_color", "value": "đen"},
            {"trait": "hair_style", "value": "hơi dài chấm gáy"},
            {"trait": "facial_features", "value": "kính gọng tròn kim loại"},
            {"trait": "outfit", "value": "áo blouse trắng, cardigan be, nơ xanh đậm, chân váy công sở đen"}
        ]
    }
    c4 = client.post(f"/api/manga/series/{series_id}/characters", json=char4_payload).json()
    print(f"[4.4] Character 4: '{c4['name']}' (Thầy giáo Toán - Váy công sở đen)")

    # 5. Build 4 Manga Pages with Layouts and Panels
    # We will insert rows directly into SQLite to have precise 4 pages with the exact requested outline.
    pages_spec = [
        # PAGE 1: Lớp học buổi sáng yên bình, nhân vật chính gục đầu ngủ bên cửa sổ.
        {
            "page_number": 1,
            "layout_template": "top1_bottom2",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt": "wide shot, peaceful Japanese high school classroom in early morning sunlight, gentle breeze blowing white curtains, tree branches outside window, empty desks, clean lineart, screentone, monochrome manga",
                    "dialogues": [
                        {"speaker": "Người dẫn chuyện", "text": "Một buổi sáng thứ Hai êm đềm như bao ngày khác...", "x_norm": 0.25, "y_norm": 0.25, "bubble_type": "caption"}
                    ],
                    "sfx": [{"text": "XÀO XẠC...", "intensity": "soft", "x_norm": 0.75, "y_norm": 0.15}]
                },
                {
                    "panel_number": 2,
                    "prompt": "medium shot, young male high school student with messy black hair sleeping on his desk next to open window, head buried in arms, morning shadows, shonen manga aesthetic",
                    "dialogues": [
                        {"speaker": "Kurogane Ren", "text": "Ưm... buồn ngủ quá...", "x_norm": 0.35, "y_norm": 0.35, "bubble_type": "thought"}
                    ],
                    "sfx": []
                },
                {
                    "panel_number": 3,
                    "prompt": "close-up shot, classroom vintage bell speaker ringing loudly, high contrast ink lines, sound vibrations, awakening",
                    "dialogues": [
                        {"speaker": "Người dẫn chuyện", "text": "Tiếng chuông báo hiệu giờ truy bài bắt đầu vang lên...", "x_norm": 0.5, "y_norm": 0.3, "bubble_type": "caption"}
                    ],
                    "sfx": [{"text": "REENG...!", "intensity": "loud", "x_norm": 0.5, "y_norm": 0.65}]
                }
            ]
        },
        # PAGE 2: Thức giấc, phát hiện bạn nữ cùng bàn và tất cả nam sinh trong lớp đều mặc váy.
        {
            "page_number": 2,
            "layout_template": "grid_2x2",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt": "close-up, 1boy, messy black hair, dark eyes blinking in confusion, rubbing eyes, bewildered expression, waking up in classroom, manga screentone",
                    "dialogues": [
                        {"speaker": "Kurogane Ren", "text": "Đã đến giờ rồi sao...?", "x_norm": 0.35, "y_norm": 0.25, "bubble_type": "thought"}
                    ],
                    "sfx": []
                },
                {
                    "panel_number": 2,
                    "prompt": "medium shot, cute female student with shoulder-length brown hair, white blouse, cream cardigan, navy pleated skirt, light blue ribbon, smiling gently at viewer",
                    "dialogues": [
                        {"speaker": "Mizuki Yuka", "text": "Ren-kun, cậu lại thức khuya chơi game rồi ngủ gật nữa hả?", "x_norm": 0.5, "y_norm": 0.3, "bubble_type": "regular"}
                    ],
                    "sfx": []
                },
                {
                    "panel_number": 3,
                    "prompt": "wide angle perspective, classroom view, male high school students chatting normally, 1boy with curly brown hair wearing white blouse and pleated school skirt, shocking atmosphere",
                    "dialogues": [
                        {"speaker": "Tanaka Kenji", "text": "Hôm nay trời mát mẻ thật, mặc váy xếp ly thế này thông thoáng ghê!", "x_norm": 0.35, "y_norm": 0.25, "bubble_type": "regular"}
                    ],
                    "sfx": [{"text": "ỒN ÀO...", "intensity": "soft", "x_norm": 0.8, "y_norm": 0.2}]
                },
                {
                    "panel_number": 4,
                    "prompt": "extreme close-up on protagonist face, sweat drops, pupil contracting, sheer horror and disbelief, dramatic speed lines, psychological shock",
                    "dialogues": [
                        {"speaker": "Kurogane Ren", "text": "C... Cái quái gì thế này?! Mọi người... đều mặc váy sao?!", "x_norm": 0.5, "y_norm": 0.35, "bubble_type": "thought"}
                    ],
                    "sfx": [{"text": "BÀNG HOÀNG!", "intensity": "impact", "x_norm": 0.5, "y_norm": 0.75}]
                }
            ]
        },
        # PAGE 3: Thầy giáo Toán bước vào giảng bài trong trang phục váy công sở; bảng ghi 'QUY ĐỊNH ĐỒNG PHỤC HỌC SINH – NĂM 1990'.
        {
            "page_number": 3,
            "layout_template": "top1_bottom2",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt": "full shot, low angle, strict male teacher with semi-long black hair and round glasses, wearing white blouse, beige cardigan, dark blue ribbon, and black professional pencil skirt, walking into classroom carrying attendance book, dead serious expression, dramatic manga screentone",
                    "dialogues": [
                        {"speaker": "Thầy Takahashi", "text": "Tất cả trật tự! Vào chỗ ngồi mau!", "x_norm": 0.45, "y_norm": 0.2, "bubble_type": "shout"}
                    ],
                    "sfx": [{"text": "CẠCH! BỘP...", "intensity": "impact", "x_norm": 0.8, "y_norm": 0.4}]
                },
                {
                    "panel_number": 2,
                    "prompt": "medium shot, male teacher writing with white chalk on large blackboard, chalk dust floating, bold Vietnamese letters on blackboard: 'QUY ĐỊNH ĐỒNG PHỤC HỌC SINH – NĂM 1990', high contrast ink",
                    "dialogues": [
                        {"speaker": "Thầy Takahashi", "text": "Hôm nay chúng ta kiểm tra nội quy đồng phục truyền thống từ năm 1990.", "x_norm": 0.35, "y_norm": 0.25, "bubble_type": "regular"}
                    ],
                    "sfx": [{"text": "KẸT... XOẸT...", "intensity": "soft", "x_norm": 0.7, "y_norm": 0.15}]
                },
                {
                    "panel_number": 3,
                    "prompt": "over the shoulder shot from protagonist, whole class standing up bowing in unison, all boys in skirts perfectly calm, protagonist sitting frozen in dark pants trembling",
                    "dialogues": [
                        {"speaker": "Cả lớp", "text": "Chúng em chào thầy ạ!", "x_norm": 0.3, "y_norm": 0.3, "bubble_type": "shout"},
                        {"speaker": "Kurogane Ren", "text": "Không thể nào... Không một ai thấy có gì bất thường cả...", "x_norm": 0.7, "y_norm": 0.65, "bubble_type": "thought"}
                    ],
                    "sfx": [{"text": "LẠNH TOÁT...", "intensity": "soft", "x_norm": 0.8, "y_norm": 0.85}]
                }
            ]
        },
        # PAGE 4: Chiều tà, ảnh điện thoại bị biến đổi kỳ dị, nhận tin nhắn cảnh báo bí ẩn từ số lạ khi thầy giáo đứng mỉm cười cuối hành lang.
        {
            "page_number": 4,
            "layout_template": "grid_2x2",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt": "wide shot, high school classroom at sunset, blood-orange twilight pouring through windows, long deep eerie shadows, lonely empty classroom",
                    "dialogues": [
                        {"speaker": "Người dẫn chuyện", "text": "Giờ tan trường, ánh ráng chiều nhuộm đỏ dãy hành lang tĩnh mịch...", "x_norm": 0.3, "y_norm": 0.2, "bubble_type": "caption"}
                    ],
                    "sfx": [{"text": "TĨNH MỊCH...", "intensity": "soft", "x_norm": 0.8, "y_norm": 0.15}]
                },
                {
                    "panel_number": 2,
                    "prompt": "close-up, trembling hands holding modern smartphone, screen showing old class group photo from years ago, all male students in the vintage photo are wearing skirts, distorted surreal reality",
                    "dialogues": [
                        {"speaker": "Kurogane Ren", "text": "Cả ảnh chụp năm ngoái... cũng bị biến thành mặc váy từ lúc nào rồi?!", "x_norm": 0.5, "y_norm": 0.3, "bubble_type": "thought"}
                    ],
                    "sfx": [{"text": "RUN RẨY...", "intensity": "soft", "x_norm": 0.2, "y_norm": 0.7}]
                },
                {
                    "panel_number": 3,
                    "prompt": "extreme close-up on glowing smartphone screen, text message notification popup from '[UNKNOWN / SỐ LẠ]': 'ĐỪNG ĐỂ HỌ BIẾT CẬU NHẬN RA. HỌ ĐANG THEO DÕI CẬU ĐẤY.', intense ominous aura",
                    "dialogues": [
                        {"speaker": "Số Lạ", "text": "Đừng để họ biết cậu nhận ra. Họ đang theo dõi cậu đấy.", "x_norm": 0.5, "y_norm": 0.45, "bubble_type": "whisper"}
                    ],
                    "sfx": [{"text": "RÙ... RÙ...!", "intensity": "impact", "x_norm": 0.5, "y_norm": 0.8}]
                },
                {
                    "panel_number": 4,
                    "prompt": "dramatic wide cinematic perspective, end of dark hallway, male teacher Takahashi standing completely motionless under dim light, uncanny sinister smile on face, staring directly into viewer soul",
                    "dialogues": [
                        {"speaker": "Kurogane Ren", "text": "Thầy... Thầy ấy... đang nhìn mình...!", "x_norm": 0.35, "y_norm": 0.3, "bubble_type": "thought"}
                    ],
                    "sfx": [{"text": "LẠNH SỐNG LƯNG...", "intensity": "impact", "x_norm": 0.75, "y_norm": 0.85}]
                }
            ]
        }
    ]

    # Save Storyboard Pages & Panels to Database
    created_page_ids = []
    created_panel_ids = []
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with connect() as db:
        # Clear any existing pages for this chapter
        db.execute("DELETE FROM manga_storyboard_pages WHERE chapter_id = ?", (chap_id,))

        for p_spec in pages_spec:
            page_id = f"page_{chap_id[:8]}_{p_spec['page_number']}"
            db.execute("""
                INSERT INTO manga_storyboard_pages (id, chapter_id, page_number, layout_template, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'draft', ?, ?)
            """, (page_id, chap_id, p_spec["page_number"], p_spec["layout_template"], stamp, stamp))
            created_page_ids.append(page_id)

            for panel in p_spec["panels"]:
                panel_id = f"panel_{page_id}_{panel['panel_number']}"
                prompt_json = json.dumps({"positive": panel["prompt"], "negative": "bad anatomy, blurry, low quality, 3d, realistic"})
                dialogue_json = json.dumps(panel["dialogues"], ensure_ascii=False)
                sfx_json = json.dumps(panel["sfx"], ensure_ascii=False)

                db.execute("""
                    INSERT INTO manga_panels (id, page_id, panel_number, prompt_json, dialogue_json, sfx_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'planned', ?, ?)
                """, (panel_id, page_id, panel["panel_number"], prompt_json, dialogue_json, sfx_json, stamp, stamp))
                created_panel_ids.append(panel_id)

        db.commit()

    print(f"\n[5] Storyboard Initialized: {len(created_page_ids)} Pages, {len(created_panel_ids)} Panels across all 4 story arcs.")

    # 6. Generate Panel Art via ComfyUI / ResourceScheduler (Mock mode for speed and zero OOM)
    print("\n[6] Generating Panel Artwork via ResourceScheduler (asyncio.Semaphore(1) safe)...")
    t_art = time.time()
    for idx, panel_id in enumerate(created_panel_ids, 1):
        gen_res = client.post("/api/manga/comfy/generate-panel", json={
            "panel_id": panel_id,
            "use_mock": True
        })
        assert gen_res.status_code == 200, f"Panel generation failed for {panel_id}: {gen_res.text}"
        art_info = gen_res.json()
        print(f"  ✓ [{idx}/{len(created_panel_ids)}] Panel {panel_id} generated: asset_id={art_info['asset_id']}")

    print(f"  --> All {len(created_panel_ids)} panels rendered in {time.time() - t_art:.2f}s.")

    # 7. Manga Composer: Render and Composite all 4 Pages
    print("\n[7] Compositing Manga Pages with Vietnamese Typography (Inter-Variable.ttf)...")
    t_comp = time.time()
    rendered_pages = []
    for p_num, page_id in enumerate(created_page_ids, 1):
        comp_res = client.post(f"/api/manga/composer/render-page/{page_id}")
        assert comp_res.status_code == 200, f"Page composition failed for {page_id}: {comp_res.text}"
        comp_data = comp_res.json()
        rendered_pages.append(comp_data)
        print(f"  ✓ Page {p_num} Composed: {comp_data['file_path']} ({comp_data['status']})")

    print(f"  --> 4 Full Manga Pages Composed in {time.time() - t_comp:.2f}s.")

    # 8. Export Chapter to CBZ and PDF
    print("\n[8] Exporting Chapter 1 to CBZ and Multi-Page PDF Packages...")
    t_exp = time.time()
    exp_res = client.post("/api/manga/composer/export-chapter", json={
        "chapter_id": chap_id,
        "format": "all"
    })
    assert exp_res.status_code == 200, f"Export failed: {exp_res.text}"
    exp_data = exp_res.json()
    cbz_path = Path(exp_data["cbz_path"])
    pdf_path = Path(exp_data["pdf_path"])

    assert cbz_path.exists(), f"CBZ not found at {cbz_path}"
    assert pdf_path.exists(), f"PDF not found at {pdf_path}"

    cbz_size = cbz_path.stat().st_size
    pdf_size = pdf_path.stat().st_size

    # Validate CBZ package contents
    with zipfile.ZipFile(cbz_path, "r") as zf:
        namelist = zf.namelist()
        assert "ComicInfo.xml" in namelist
        page_files = [n for n in namelist if n.endswith(".png")]
        assert len(page_files) == 4, f"Expected 4 pages in CBZ, got {len(page_files)}"

        xml_bytes = zf.read("ComicInfo.xml")
        xml_root = ET.fromstring(xml_bytes)
        assert "MOONLIGHT CLASSROOM" in (xml_root.find("Series").text if xml_root.find("Series") is not None else "")
        assert "Thế giới đã thay đổi" in (xml_root.find("Title").text if xml_root.find("Title") is not None else "")

    # Validate PDF byte header
    with open(pdf_path, "rb") as f:
        assert f.read(5) == b"%PDF-"

    print(f"  ✓ CBZ Exported: {cbz_path} ({cbz_size:,} bytes, 4 pages + ComicInfo.xml)")
    print(f"  ✓ PDF Exported: {pdf_path} ({pdf_size:,} bytes, 4 pages, valid %PDF-)")
    print(f"  --> Exports completed in {time.time() - t_exp:.2f}s.")

    print("\n" + "=" * 70)
    print("  PRODUCTION OF 'MOONLIGHT CLASSROOM' CHAPTER 1 COMPLETED 100%!")
    print("=" * 70)

    return {
        "series_id": series_id,
        "series_title": series["title"],
        "chapter_id": chap_id,
        "chapter_title": chapter["title"],
        "pages_count": 4,
        "panels_count": len(created_panel_ids),
        "cbz_path": str(cbz_path),
        "cbz_size": cbz_size,
        "pdf_path": str(pdf_path),
        "pdf_size": pdf_size,
        "export_id": exp_data.get("export_id")
    }


if __name__ == "__main__":
    res = generate_moonlight_classroom_chapter1()
    print("\nRESULT SUMMARY:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
