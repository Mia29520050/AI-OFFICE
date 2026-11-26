"""Production script for MOONLIGHT CLASSROOM - Chapter 1: Thế giới đã thay đổi.

Executes the complete Manga Studio end-to-end production pipeline:
1. Series Creation (MOONLIGHT CLASSROOM)
2. Character Registry (Protagonist, Nữ sinh cùng bàn, Nam sinh tóc nâu, Thầy giáo Toán)
3. Volume 1 & Chapter 1 ('Thế giới đã thay đổi')
4. 4-Page Storyboard with 10 panels matching the exact story text
5. Panel Art generation with ResourceScheduler GPU lock & mock metadata
6. Full Page Manga Compositing with Vietnamese Unicode speech bubbles & screentone
7. Export to CBZ and multi-page PDF packages
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from fastapi.testclient import TestClient
from main import app, connect
import manga_composer

client = TestClient(app)


def produce_chapter() -> dict[str, any]:
    print("\n" + "=" * 70)
    print("PRODUCING MANGA: MOONLIGHT CLASSROOM - CHƯƠNG 1: THẾ GIỚI ĐÃ THAY ĐỔI")
    print("=" * 70)

    # 1. Series
    s_resp = client.post("/api/manga/series", json={
        "title": "MOONLIGHT CLASSROOM",
        "synopsis": "Một nam sinh thức dậy sau giấc ngủ ngắn trong lớp học và kinh hoàng nhận ra thế giới đã thay đổi: tất cả học sinh nam và thầy giáo đều mặc đồng phục váy nữ sinh theo một luật cải cách kỳ lạ từ năm 1990.",
        "genre": "Bí ẩn · Học đường · Tâm lý · Giả tưởng",
        "art_style": "bw",
        "reading_direction": "rtl"
    })
    assert s_resp.status_code == 200, s_resp.text
    series = s_resp.json()
    series_id = series["id"]
    print(f"✓ Series Created: '{series['title']}' (ID: {series_id})")

    # 2. Characters
    chars = [
        {
            "name": "Nam sinh (Nhân vật chính)",
            "identity": {
                "role": "protagonist",
                "age": 16,
                "appearance": "Áo sơ mi trắng, cà vạt xanh đậm, áo khoác đồng phục màu xanh navy và quần dài tối màu. Học sinh duy nhất còn mặc quần dài."
            },
            "personality": {
                "traits": ["Quan sát nhạy bén", "bối rối", "kiên định", "nghi ngờ thực tại"]
            },
            "speech_rules": {
                "first_person": "mình",
                "second_person": "cậu",
                "tone": "kinh ngạc, thăm dò"
            },
            "locked_traits": [
                {"trait": "outfit", "value": "áo sơ mi trắng, cà vạt xanh đậm, áo khoác xanh navy, quần dài tối màu"},
                {"trait": "hair", "value": "tóc đen ngắn"}
            ]
        },
        {
            "name": "Nữ sinh bàn bên",
            "identity": {
                "role": "supporting",
                "age": 16,
                "appearance": "Mái tóc nâu ngang vai, mặc áo blouse trắng, cardigan màu kem và chân váy xanh navy, nơ cổ màu xanh nhạt."
            },
            "personality": {
                "traits": ["Tự nhiên", "hơi ngạc nhiên", "coi đồng phục váy là hiển nhiên"]
            },
            "speech_rules": {
                "first_person": "tớ",
                "second_person": "cậu",
                "tone": "thân thiện, bình thường"
            },
            "locked_traits": [
                {"trait": "outfit", "value": "blouse trắng, cardigan kem, chân váy xanh navy, nơ xanh nhạt"},
                {"trait": "hair", "value": "tóc nâu ngang vai"}
            ]
        },
        {
            "name": "Nam sinh tóc nâu",
            "identity": {
                "role": "classmate",
                "age": 16,
                "appearance": "Mái tóc nâu hơi xoăn, ngồi bắt chéo chân, mặc áo blouse trắng, cardigan màu xanh nhạt và chân váy đồng phục nữ sinh xếp ly."
            },
            "personality": {
                "traits": ["Cởi mở", "vô tư", "ngạc nhiên vì bạn mình hỏi kỳ lạ"]
            },
            "speech_rules": {
                "first_person": "tớ",
                "second_person": "cậu",
                "tone": "vô tư, cười đùa"
            },
            "locked_traits": [
                {"trait": "outfit", "value": "áo blouse trắng, cardigan xanh nhạt, chân váy xếp ly nữ sinh"},
                {"trait": "hair", "value": "tóc nâu hơi xoăn"}
            ]
        },
        {
            "name": "Thầy giáo Toán",
            "identity": {
                "role": "teacher / mysterious observer",
                "age": 35,
                "appearance": "Người đàn ông trưởng thành, tóc đen hơi dài, đeo kính tròn. Mặc áo blouse trắng bên ngoài cardigan be, nơ xanh đậm và chân váy công sở màu đen."
            },
            "personality": {
                "traits": ["Nghiêm khắc", "điềm tĩnh", "bí ẩn", "nụ cười khó đoán"]
            },
            "speech_rules": {
                "first_person": "thầy",
                "second_person": "các em / em",
                "tone": "trang trọng, giáo viên"
            },
            "locked_traits": [
                {"trait": "outfit", "value": "blouse trắng, cardigan be, nơ xanh đậm, chân váy công sở đen"},
                {"trait": "glasses", "value": "kính tròn gọng kim loại"}
            ]
        }
    ]

    for c in chars:
        c_resp = client.post(f"/api/manga/series/{series_id}/characters", json=c)
        assert c_resp.status_code == 200, c_resp.text
        print(f"✓ Character Registered: '{c['name']}'")

    # 3. Volume & Chapter
    v_resp = client.post(f"/api/manga/series/{series_id}/volumes", json={
        "number": 1,
        "title": "Tập 1: Thực Tại Đảo Chiều"
    })
    assert v_resp.status_code == 200
    vol = v_resp.json()
    vol_id = vol["id"]

    ch_resp = client.post(f"/api/manga/series/{series_id}/chapters", json={
        "volume_id": vol_id,
        "number": 1.0,
        "title": "Chương 1: Thế giới đã thay đổi",
        "synopsis": "Một ngày học bình thường bỗng chốc đảo lộn khi một nam sinh thức dậy và phát hiện toàn bộ trường học từ nam sinh đến giáo viên đều mặc đồng phục nữ sinh theo một đạo luật năm 1990."
    })
    assert ch_resp.status_code == 200
    chapter = ch_resp.json()
    chap_id = chapter["id"]
    print(f"✓ Volume: '{vol['title']}' | Chapter: '{chapter['title']}' (ID: {chap_id})")

    # 4. Define 4 Pages and Panels matching the script
    pages_data = [
        {
            "page_number": 1,
            "layout_template": "top1_bottom2",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt_en": "manga panel, high contrast ink lines, morning sunlight shining through classroom window, peaceful high school students chatting in background, boy sitting at back desk looking outside clouds",
                    "visual_description": "Buổi sáng, ánh nắng nhẹ chiếu qua khung cửa sổ lớp học. Học sinh đang trò chuyện vui vẻ, nam sinh ngồi bàn cuối nhìn bầu trời.",
                    "bubbles": [
                        {"type": "thought", "text": "Buồn ngủ quá...", "pos_x": 0.25, "pos_y": 0.35, "width": 0.28, "height": 0.16},
                        {"type": "thought", "text": "Chợp mắt một chút chắc không sao đâu.", "pos_x": 0.70, "pos_y": 0.65, "width": 0.34, "height": 0.18}
                    ]
                },
                {
                    "panel_number": 2,
                    "prompt_en": "manga panel, close up boy resting head on arms over closed math textbook, eyes closed drifting into deep sleep, gentle shadows",
                    "visual_description": "Nam sinh gấp sách Toán, đặt hai tay lên bàn gục đầu ngủ say.",
                    "bubbles": [
                        {"type": "whisper", "text": "...Này. Dậy đi.", "pos_x": 0.65, "pos_y": 0.25, "width": 0.28, "height": 0.20}
                    ]
                },
                {
                    "panel_number": 3,
                    "prompt_en": "manga panel, boy lifting head blinking in bright sunlight, squinting eyes, waking up confused",
                    "visual_description": "Nam sinh ngẩng đầu, nheo mắt vì ánh sáng chiếu vào, đưa tay dụi mắt nhìn lên bảng.",
                    "bubbles": [
                        {"type": "regular", "text": "Đã vào tiết rồi sao...?", "pos_x": 0.35, "pos_y": 0.45, "width": 0.34, "height": 0.22}
                    ]
                }
            ]
        },
        {
            "page_number": 2,
            "layout_template": "action_5",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt_en": "manga panel, female student with shoulder length brown hair wearing white blouse, cream cardigan, navy pleated skirt and light blue necktie ribbon looking at him curiously",
                    "visual_description": "Nữ sinh bàn bên tóc nâu ngang vai, mặc áo blouse trắng, cardigan kem, chân váy xanh navy chớp mắt nhìn cậu.",
                    "bubbles": [
                        {"type": "regular", "text": "...Bạn mới à? Cậu đang mặc gì vậy?", "pos_x": 0.30, "pos_y": 0.35, "width": 0.38, "height": 0.25},
                        {"type": "regular", "text": "Hả? Đồng phục chứ gì nữa? Cậu ngủ lú rồi à?", "pos_x": 0.72, "pos_y": 0.60, "width": 0.38, "height": 0.25}
                    ]
                },
                {
                    "panel_number": 2,
                    "prompt_en": "manga panel, high school classroom view, multiple male students sitting at desks wearing female sailor cardigans and pleated skirts, boy standing up in extreme shock",
                    "visual_description": "Toàn cảnh lớp học: các nam sinh khác cũng đều mặc cardigan và váy xếp ly nữ sinh. Cậu đứng bật dậy bàng hoàng.",
                    "bubbles": [
                        {"type": "shout", "text": "CÁI QUÁI GÌ VẬY?!", "pos_x": 0.50, "pos_y": 0.25, "width": 0.44, "height": 0.28}
                    ]
                },
                {
                    "panel_number": 3,
                    "prompt_en": "manga panel, male student with wavy brown hair wearing light blue cardigan and female pleated skirt walking over, talking with puzzled smile",
                    "visual_description": "Nam sinh tóc nâu xoăn mặc váy nữ sinh bước lại gần với vẻ mặt khó hiểu.",
                    "bubbles": [
                        {"type": "regular", "text": "Cậu vẫn mặc bộ quần dài đó à? Kiểu đó ngừng sản xuất lâu rồi!", "pos_x": 0.45, "pos_y": 0.40, "width": 0.48, "height": 0.30}
                    ]
                }
            ]
        },
        {
            "page_number": 3,
            "layout_template": "top1_bottom2",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt_en": "manga panel, mature male math teacher with round glasses and longish dark hair wearing beige cardigan, navy bow tie, and black office pencil skirt writing on chalkboard",
                    "visual_description": "Thầy giáo Toán trưởng thành đeo kính tròn, mặc cardigan be, nơ xanh và chân váy công sở đen đứng viết lên bảng.",
                    "bubbles": [
                        {"type": "caption", "text": "QUY ĐỊNH ĐỒNG PHỤC HỌC SINH – NĂM 1990", "pos_x": 0.50, "pos_y": 0.20, "width": 0.60, "height": 0.16},
                        {"type": "regular", "text": "Đó là năm quy định đồng phục nữ sinh thống nhất toàn quốc được ban hành.", "pos_x": 0.40, "pos_y": 0.65, "width": 0.50, "height": 0.22}
                    ]
                },
                {
                    "panel_number": 2,
                    "prompt_en": "manga panel, student looking at smartphone screen displaying historical web archive article from 1989-1990 educational reform, trembling hands",
                    "visual_description": "Cậu tra cứu trên điện thoại, đọc bài viết về cuộc cải cách giáo dục năm 1989-1990, tim đập nhanh.",
                    "bubbles": [
                        {"type": "thought", "text": "Vậy là... thế giới này từng có đồng phục quần dài như mình đang mặc?", "pos_x": 0.50, "pos_y": 0.40, "width": 0.55, "height": 0.32}
                    ]
                },
                {
                    "panel_number": 3,
                    "prompt_en": "manga panel, school bell ringing, afternoon sun setting, students leaving empty classroom while boy sits alone in contemplation",
                    "visual_description": "Chuông tan tiết vang lên, phòng học dần vắng tanh trong ánh hoàng hôn tà.",
                    "bubbles": [
                        {"type": "sfx", "text": "REENG...", "pos_x": 0.25, "pos_y": 0.25, "width": 0.30, "height": 0.18},
                        {"type": "caption", "text": "Hoặc có lẽ, chính cậu mới là người không còn thuộc về thế giới này.", "pos_x": 0.50, "pos_y": 0.75, "width": 0.62, "height": 0.18}
                    ]
                }
            ]
        },
        {
            "page_number": 4,
            "layout_template": "drama_6",
            "panels": [
                {
                    "panel_number": 1,
                    "prompt_en": "manga panel, smartphone photo of opening ceremony glitching, faces blurring and clothes morphing into female skirts before his eyes",
                    "visual_description": "Cậu mở ảnh chụp ngày khai trường: hình ảnh bị méo mó, tất cả học sinh trong ảnh biến thành mặc váy nữ sinh.",
                    "bubbles": [
                        {"type": "thought", "text": "Không thể tin nổi... Bức ảnh đang tự thay đổi?!", "pos_x": 0.45, "pos_y": 0.35, "width": 0.50, "height": 0.28}
                    ]
                },
                {
                    "panel_number": 2,
                    "prompt_en": "manga panel, smartphone screen close up showing ominous text notification from unknown number in dark room",
                    "visual_description": "Màn hình điện thoại sáng lên với tin nhắn từ người gửi không xác định.",
                    "bubbles": [
                        {"type": "caption", "text": "TIN NHẮN MỚI · KHÔNG RÕ NGƯỜI GỬI\n'Nếu cậu vẫn còn nhớ bộ đồng phục cũ, đừng nói chuyện đó với giáo viên.'", "pos_x": 0.50, "pos_y": 0.50, "width": 0.70, "height": 0.35}
                    ]
                },
                {
                    "panel_number": 3,
                    "prompt_en": "manga panel, empty dark school hallway, sinister silhouette of male teacher in skirt and round glasses standing at hallway corner smiling quietly",
                    "visual_description": "Hành lang vắng tanh, bóng người mặc váy công sở đeo kính tròn đang đứng lặng lẽ quan sát và mỉm cười.",
                    "bubbles": [
                        {"type": "inverted", "text": "...Thầy giáo đang đứng đó?!", "pos_x": 0.35, "pos_y": 0.30, "width": 0.40, "height": 0.20},
                        {"type": "caption", "text": "HẾT CHƯƠNG 1", "pos_x": 0.50, "pos_y": 0.82, "width": 0.35, "height": 0.12}
                    ]
                }
            ]
        }
    ]

    total_panels = 0
    generated_assets = []

    for p_idx, p_info in enumerate(pages_data, 1):
        # Create Page
        page_resp = client.post(f"/api/manga/chapters/{chap_id}/pages", json={
            "page_number": p_info["page_number"],
            "layout_template": p_info["layout_template"]
        })
        assert page_resp.status_code == 200, page_resp.text
        page = page_resp.json()
        page_id = page["id"]

        print(f"\n--- Trang {p_info['page_number']}/4 (Layout: {p_info['layout_template']}) ---")

        for pan in p_info["panels"]:
            total_panels += 1
            # Create Panel
            pan_resp = client.post(f"/api/manga/pages/{page_id}/panels", json={
                "panel_number": pan["panel_number"],
                "prompt_json": {
                    "prompt_en": pan["prompt_en"],
                    "visual_description": pan["visual_description"]
                },
                "dialogue_json": pan["bubbles"]
            })
            assert pan_resp.status_code == 200
            panel_record = pan_resp.json()
            panel_id = panel_record["id"]

            # Generate Panel Art
            art_resp = client.post("/api/manga/comfy/generate-panel", json={
                "panel_id": panel_id,
                "prompt": pan["prompt_en"],
                "art_style": "manga_bw",
                "width": 768,
                "height": 1024
            })
            assert art_resp.status_code == 200, art_resp.text
            art_data = art_resp.json()
            generated_assets.append(art_data.get("asset_id"))
            print(f"  ✓ Ô tranh {pan['panel_number']}: Sinh ảnh thành công ({art_data.get('mode')}, file: {Path(art_data.get('image_path', '')).name})")

        # Composite Page
        comp_resp = client.post(f"/api/manga/composer/render-page/{page_id}", json={
            "screentone": True
        })
        assert comp_resp.status_code == 200, comp_resp.text
        comp_data = comp_resp.json()
        print(f"  ✓ Đã hoàn thiện Trang {p_info['page_number']} (Ghép thoại tiếng Việt, Inter font & Screentone B&W)")

    # 5. Export Chapter
    print("\n--- Đóng gói xuất bản Chapter ---")
    exp_resp = client.post(f"/api/manga/composer/export-chapter", json={
        "chapter_id": chap_id,
        "format": "all"
    })
    assert exp_resp.status_code == 200, exp_resp.text
    export_data = exp_resp.json()

    cbz_path = export_data.get("cbz_path")
    pdf_path = export_data.get("pdf_path")
    export_id = export_data.get("export_id")

    print(f"✓ Đóng gói CBZ: {cbz_path}")
    print(f"✓ Đóng gói PDF: {pdf_path}")
    print(f"✓ Export Record ID: {export_id}")

    # Verify CBZ integrity
    if cbz_path and Path(cbz_path).exists():
        with zipfile.ZipFile(cbz_path, "r") as z:
            names = z.namelist()
            print(f"  - Cấu trúc CBZ: {len(names)} tệp ({', '.join(names)})")
            assert "ComicInfo.xml" in names
            assert "page_001.png" in names
            assert "page_004.png" in names

    # Verify PDF integrity
    if pdf_path and Path(pdf_path).exists():
        pdf_bytes = Path(pdf_path).read_bytes()
        print(f"  - Dung lượng PDF: {len(pdf_bytes):,} bytes, Header: {pdf_bytes[:5].decode('latin1', errors='ignore')}")
        assert pdf_bytes.startswith(b"%PDF-")

    print("\n" + "=" * 70)
    print("HOÀN TẤT TOÀN BỘ SẢN XUẤT CHƯƠNG 1 THÀNH CÔNG RỰC RỠ!")
    print("=" * 70)

    return {
        "status": "SUCCESS",
        "series_id": series_id,
        "chapter_id": chap_id,
        "total_pages": len(pages_data),
        "total_panels": total_panels,
        "cbz_path": cbz_path,
        "pdf_path": pdf_path,
        "export_id": export_id
    }


if __name__ == "__main__":
    result = produce_chapter()
    print(json.dumps(result, indent=2, ensure_ascii=False))
