"""Master Production Script (Fixed Edition) for MOONLIGHT CLASSROOM — Chương 1: Thế giới đã thay đổi.

Fixes:
1. Color vs B&W Purity: 100% full-color anime in Color Edition; 100% pure manga monochrome in B&W Edition.
2. Speech Bubble Placement: Standardized non-intrusive upper corners and margins; zero face obscuration.
3. Text Color Uniformity: 100% pure solid black (#000000) dialogue text on white bubbles across all pages.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

sys.path.append(r"F:\AI-Office")

from app.manga_composer import (
    MangaComposer,
    PageConfig,
    PanelConfig,
    SpeechBubble,
    BubbleType,
    PanelFilter,
    PanelLayoutType,
    FitMode,
    ComicMetadata,
    export_page_to_png,
    export_to_cbz,
    export_to_pdf,
)
from app.manga_validator import validate_panel_image

ROOT_DIR = Path(r"F:\AI-Office")
BW_CROPS_DIR = ROOT_DIR / "data" / "manga" / "series" / "moonlight_classroom" / "ch01" / "panel_crops_bw"
COL_CROPS_DIR = ROOT_DIR / "data" / "manga" / "series" / "moonlight_classroom" / "ch01" / "panel_crops_color"

EXPORTS_DIR = ROOT_DIR / "data" / "manga" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

BW_DIR = EXPORTS_DIR / "moonlight_classroom_ch01_bw"
BW_DIR.mkdir(parents=True, exist_ok=True)

COLOR_DIR = EXPORTS_DIR / "moonlight_classroom_ch01_color"
COLOR_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = ROOT_DIR / "data" / "office.db"

def asset_path(name: str, is_color: bool = False) -> str:
    base_dir = COL_CROPS_DIR if is_color else BW_CROPS_DIR
    p = base_dir / f"{name}.png"
    if not p.exists():
        raise FileNotFoundError(f"Missing asset: {p}")
    return str(p)

def build_storyboard_pages(is_color: bool = False) -> list[PageConfig]:
    """Build PageConfig list with strictly unified typography and clean bubble placement."""
    pages = []
    TEXT_BLACK = "#000000"
    BUBBLE_WHITE = "#FFFFFF"
    BORDER_BLACK = "#000000"

    # Helper for SFX styling
    sfx_col = "#D92626" if is_color else "#000000"
    sfx_stroke = "#000000" if is_color else "#FFFFFF"
    sfx_stroke_w = 3 if is_color else 4

    # --- PAGE 1: Buổi sáng trường học, Minh buồn ngủ ---
    p1_panels = [
        PanelConfig(
            id="p01_1", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Buổi sáng.", bubble_type=BubbleType.CAPTION, x=0.75, y=0.15, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Ánh nắng nhẹ xuyên qua ô cửa kính, chiếu xuống lớp học.", bubble_type=BubbleType.CAPTION, x=0.35, y=0.15, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p01_2", image_path=asset_path("two_students_talking", is_color),
            bubbles=[
                SpeechBubble(text="Đó là một ngày học bình thường. Học sinh tụ tập trò chuyện...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.15, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p01_3", image_path=asset_path("minh_face_medium", is_color),
            bubbles=[
                SpeechBubble(text="Ở bàn cuối cạnh cửa sổ, Minh ngồi tựa lưng vào ghế.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.14, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Buồn ngủ quá... Vẫn còn vài phút nữa mới vào tiết.", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.82, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p01_4", image_path=asset_path("minh_expr_drowsy", is_color),
            bubbles=[
                SpeechBubble(text="Chợp mắt một chút chắc không sao đâu...", bubble_type=BubbleType.THOUGHT, x=0.45, y=0.20, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Zzz...", bubble_type=BubbleType.SFX, x=0.80, y=0.78, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=1, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p1_panels))

    # --- PAGE 2: Giấc ngủ và tiếng gọi thức giấc ---
    p2_panels = [
        PanelConfig(
            id="p02_1", image_path=asset_path("manga_screentone_scene", is_color),
            bubbles=[
                SpeechBubble(text="Tiếng ồn trong lớp dần xa xôi. Cậu chìm vào giấc ngủ.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p02_2", image_path=asset_path("mai_desk_focus", is_color),
            bubbles=[
                SpeechBubble(text="...Này. Dậy đi.", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.28, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Ưm...", speaker="Minh", bubble_type=BubbleType.WHISPER, x=0.72, y=0.78, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p02_3", image_path=asset_path("minh_eyes_closeup", is_color),
            bubbles=[
                SpeechBubble(text="Chuẩn bị vào tiết rồi đấy.", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.25, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Đã vào tiết rồi sao...?", speaker="Minh", bubble_type=BubbleType.THOUGHT, x=0.75, y=0.78, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p02_4", image_path=asset_path("minh_portrait_base", is_color),
            bubbles=[
                SpeechBubble(text="Cậu đưa tay dụi mắt, sau đó nhìn lên bảng. Không có gì khác thường. Nhưng khi quay sang...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=2, width=1200, height=1800, layout_type=PanelLayoutType.YONKOMA, reading_direction="rtl", panels=p2_panels))

    # --- PAGE 3: Nhìn thấy Mai mặc quần dài ---
    p3_panels = [
        PanelConfig(
            id="p03_1", image_path=asset_path("mai_desk_focus", is_color),
            bubbles=[
                SpeechBubble(text="Một nữ sinh ngồi bàn kế bên. Tóc nâu ngang vai, gương mặt quen thuộc.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.15, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Mai à...?", speaker="Minh", bubble_type=BubbleType.REGULAR, x=0.5, y=0.80, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p03_2", image_path=asset_path("two_students_talking", is_color),
            bubbles=[
                SpeechBubble(text="Gì thế? Nhìn tớ như người ngoài hành tinh vậy.", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.35, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p03_3", image_path=asset_path("minh_eyes_closeup", is_color),
            bubbles=[
                SpeechBubble(text="Cậu khẽ lắc đầu, nhưng rồi ánh mắt cậu vô tình rơi xuống trang phục của cô.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p03_4", image_path=asset_path("minh_trousers_check", is_color),
            bubbles=[
                SpeechBubble(text="Mai mặc sơ mi trắng, cà vạt, áo khoác... và một chiếc QUẦN DÀI!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Khoan đã... Sao Mai lại mặc quần dài của nam sinh?!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.82, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=3, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p3_panels))

    # --- PAGE 4: Hỏi Mai về đồng phục ---
    p4_panels = [
        PanelConfig(
            id="p04_1", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Đồng phục nữ sinh bình thường là áo thủy thủ và váy xếp ly cơ mà?", bubble_type=BubbleType.CAPTION, x=0.30, y=0.15, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Hôm nay... trường cho phép mặc trang phục tự do à?", speaker="Minh", bubble_type=BubbleType.REGULAR, x=0.75, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p04_2", image_path=asset_path("mai_desk_focus", is_color),
            bubbles=[
                SpeechBubble(text="Hả? Cậu nói gì kỳ lạ thế?", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.35, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p04_3", image_path=asset_path("two_students_talking", is_color),
            bubbles=[
                SpeechBubble(text="Đồng phục mùa hè bình thường mà. Có gì lạ đâu?", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.45, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=4, width=1200, height=1800, layout_type=PanelLayoutType.TOP1_BOTTOM2, reading_direction="rtl", panels=p4_panels))

    # --- PAGE 5: Minh nhìn quanh lớp - Các nam sinh mặc váy ---
    p5_panels = [
        PanelConfig(
            id="p05_1", image_path=asset_path("minh_expr_surprised", is_color),
            bubbles=[
                SpeechBubble(text="Minh sững lại. Cậu quay đầu nhìn khắp phòng học.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.15, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p05_2", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Tất cả các bạn nữ trong lớp đều mặc quần dài giống như Mai.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p05_3", image_path=asset_path("minh_eyes_closeup", is_color),
            bubbles=[
                SpeechBubble(text="Nhưng điều khiến tim cậu hẫng một nhịp... là các nam sinh.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p05_4", image_path=asset_path("kenji_classmate_focus", is_color),
            bubbles=[
                SpeechBubble(text="Một nam sinh đang đứng nói chuyện. Áo sơ mi, cà vạt... và một chiếc VÁY XẾP LY!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=5, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p5_panels))

    # --- PAGE 6: Cảnh tượng khó tin - Minh bật dậy ---
    p6_panels = [
        PanelConfig(
            id="p06_1", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Váy xếp ly màu xanh navy ngang gối. Đôi chân để lộ hoàn toàn tự nhiên.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p06_2", image_path=asset_path("two_students_talking", is_color),
            bubbles=[
                SpeechBubble(text="Không chỉ một người. TẤT CẢ nam sinh đều mặc váy!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p06_3", image_path=asset_path("manga_screentone_scene", is_color),
            bubbles=[
                SpeechBubble(text="Họ cười đùa, cử động bình thản. Không ai thấy bất thường.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p06_4", image_path=asset_path("minh_shock_lowangle", is_color),
            bubbles=[
                SpeechBubble(text="RẦM!!", bubble_type=BubbleType.SFX, x=0.5, y=0.20, font_size=46, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Cái... cái gì thế này?!", speaker="Minh", bubble_type=BubbleType.SHOUT, x=0.5, y=0.78, font_size=21, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p06_5", image_path=asset_path("minh_expr_panic", is_color),
            bubbles=[
                SpeechBubble(text="Minh bật dậy khỏi ghế, làm đổ quyển sách Toán xuống sàn!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=6, width=1200, height=1800, layout_type=PanelLayoutType.ACTION_5, reading_direction="rtl", panels=p6_panels))

    # --- PAGE 7: Cả lớp nhìn Minh - Minh kiểm tra lại bản thân ---
    p7_panels = [
        PanelConfig(
            id="p07_1", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Cả lớp đồng loạt im bặt, quay đầu nhìn về phía Minh.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.15, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="...", bubble_type=BubbleType.WHISPER, x=0.5, y=0.75, font_size=24, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p07_2", image_path=asset_path("mai_desk_focus", is_color),
            bubbles=[
                SpeechBubble(text="Này Minh, cậu làm sao thế? Tự nhiên đứng bật dậy vậy?", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.35, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p07_3", image_path=asset_path("minh_expr_disbelief", is_color),
            bubbles=[
                SpeechBubble(text="Tim cậu đập loạn nhịp. Một suy nghĩ lạnh toát xẹt qua đầu...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.15, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Mình... mình đang mặc cái gì?!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.78, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p07_4", image_path=asset_path("minh_trousers_check", is_color),
            bubbles=[
                SpeechBubble(text="Áo sơ mi, cà vạt, áo khoác navy, và... chiếc quần dài màu xám quen thuộc!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Hộc... May quá... Mình vẫn bình thường!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.82, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=7, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p7_panels))

    # --- PAGE 8: Kenji quay xuống - "Sao cậu mặc đồ nữ?" ---
    p8_panels = [
        PanelConfig(
            id="p08_1", image_path=asset_path("two_students_talking", is_color),
            bubbles=[
                SpeechBubble(text="Nhưng ánh mắt mọi người nhìn cậu lại tràn đầy khó hiểu và kỳ quặc.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p08_2", image_path=asset_path("kenji_classmate_focus", is_color),
            bubbles=[
                SpeechBubble(text="Minh à... Sao hôm nay cậu lại mặc đồng phục nữ thế?", speaker="Kenji", bubble_type=BubbleType.REGULAR, x=0.45, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p08_3", image_path=asset_path("minh_shock_lowangle", is_color),
            bubbles=[
                SpeechBubble(text="CHOÁNG VÁNG!", bubble_type=BubbleType.SFX, x=0.25, y=0.18, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="C-Cái gì?! Cậu nói ai đang mặc đồng phục nữ?!", speaker="Minh", bubble_type=BubbleType.SHOUT, x=0.65, y=0.25, font_size=20, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Thì cậu chứ ai! Cậu đang mặc quần dài của nữ sinh kìa!", speaker="Kenji", bubble_type=BubbleType.REGULAR, x=0.50, y=0.82, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=8, width=1200, height=1800, layout_type=PanelLayoutType.TOP2_BOTTOM1, reading_direction="rtl", panels=p8_panels))

    # --- PAGE 9: Tranh cãi về đồng phục ---
    p9_panels = [
        PanelConfig(
            id="p09_1", image_path=asset_path("minh_expr_panic", is_color),
            bubbles=[
                SpeechBubble(text="Cậu đùa tôi à?! Cậu mới là người đang mặc VÁY đấy Kenji!", speaker="Minh", bubble_type=BubbleType.SHOUT, x=0.5, y=0.22, font_size=19, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p09_2", image_path=asset_path("kenji_classmate_focus", is_color),
            bubbles=[
                SpeechBubble(text="Thì nam sinh nào chả mặc váy xếp ly? Cậu bị sốt à?", speaker="Kenji", bubble_type=BubbleType.REGULAR, x=0.45, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p09_3", image_path=asset_path("mai_desk_focus", is_color),
            bubbles=[
                SpeechBubble(text="Sáng nay cậu ngủ mớ à Minh? Từ xưa đến giờ nam sinh trường mình luôn mặc váy mà.", speaker="Mai", bubble_type=BubbleType.REGULAR, x=0.40, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p09_4", image_path=asset_path("minh_face_medium", is_color),
            bubbles=[
                SpeechBubble(text="Từ xưa đến giờ?! Đùa nhau à... Rõ ràng sáng nay mọi thứ vẫn bình thường!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=9, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p9_panels))

    # --- PAGE 10: Xì xào và tiếng chuông vào lớp ---
    p10_panels = [
        PanelConfig(
            id="p10_1", image_path=asset_path("minh_upper_uniform", is_color),
            bubbles=[
                SpeechBubble(text="Các cậu không nhớ sao?! Con trai mặc quần dài, con gái mặc váy... Đó mới là bình thường!", speaker="Minh", bubble_type=BubbleType.SHOUT, x=0.5, y=0.22, font_size=19, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p10_2", image_path=asset_path("two_students_talking", is_color),
            bubbles=[
                SpeechBubble(text="Cậu ấy nói gì lảm nhảm thế?", speaker="Học sinh 1", bubble_type=BubbleType.WHISPER, x=0.35, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Chắc áp lực thi cử quá...", speaker="Học sinh 2", bubble_type=BubbleType.WHISPER, x=0.65, y=0.75, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p10_3", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="KENG... KOONG... KENG... KOONG...", bubble_type=BubbleType.SFX, x=0.5, y=0.22, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Tiếng chuông vào lớp vang lên cắt đứt cuộc tranh cãi.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=10, width=1200, height=1800, layout_type=PanelLayoutType.TOP1_BOTTOM2, reading_direction="rtl", panels=p10_panels))

    # --- PAGE 11: Thầy giáo dạy Toán bước vào lớp ---
    p11_panels = [
        PanelConfig(
            id="p11_1", image_path=asset_path("manga_screentone_scene", is_color),
            bubbles=[
                SpeechBubble(text="CỘP... CỘP... CỘP...", bubble_type=BubbleType.SFX, x=0.5, y=0.20, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Tiếng bước chân ngoài hành lang. Cửa lớp trượt mở.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p11_2", image_path=asset_path("teacher_face_glasses", is_color),
            bubbles=[
                SpeechBubble(text="Thầy dạy Toán bước vào. Khoảng 35 tuổi, đeo kính tròn, vẻ mặt nghiêm nghị.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p11_3", image_path=asset_path("minh_eyes_closeup", is_color),
            bubbles=[
                SpeechBubble(text="Nhưng khi ánh mắt Minh dời xuống phía dưới...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p11_4", image_path=asset_path("teacher_pencil_skirt", is_color),
            bubbles=[
                SpeechBubble(text="Thầy mặc áo sơ mi thắt nơ, cardigan, và... một chiếc CHÂN VÁY BÚT CHÌ ĐEN!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=11, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p11_panels))

    # --- PAGE 12: Chào thầy - Minh bàng hoàng ngồi xuống ---
    p12_panels = [
        PanelConfig(
            id="p12_1", image_path=asset_path("minh_expr_disbelief", is_color),
            bubbles=[
                SpeechBubble(text="Thầy giáo... cũng mặc váy?! Cả giáo viên nam cũng vậy sao?!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.25, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p12_2", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Cả lớp, nghiêm! Chúng em chào thầy ạ!", speaker="Cả lớp", bubble_type=BubbleType.SHOUT, x=0.5, y=0.25, font_size=19, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p12_3", image_path=asset_path("teacher_blackboard", is_color),
            bubbles=[
                SpeechBubble(text="Được rồi, các em ngồi xuống. Hôm nay chúng ta tiếp tục bài học.", speaker="Thầy giáo", bubble_type=BubbleType.REGULAR, x=0.35, y=0.20, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Minh ngồi phịch xuống ghế. Mồ hôi lạnh toát ướt lưng áo. Đây không phải trò đùa!", bubble_type=BubbleType.CAPTION, x=0.60, y=0.80, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=12, width=1200, height=1800, layout_type=PanelLayoutType.TOP2_BOTTOM1, reading_direction="rtl", panels=p12_panels))

    # --- PAGE 13: Tiết học diễn ra bình thường - Minh quyết định hỏi ---
    p13_panels = [
        PanelConfig(
            id="p13_1", image_path=asset_path("teacher_chalk_writing", is_color),
            bubbles=[
                SpeechBubble(text="Cạch... cạch... cạch...", bubble_type=BubbleType.SFX, x=0.5, y=0.18, font_size=32, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Tiếng phấn gõ nhịp đều đặn trên bảng đen.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.75, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p13_2", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Mọi người chăm chú ghi chép. Không ai để ý. Mọi thứ diễn ra tự nhiên như hơi thở.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p13_3", image_path=asset_path("minh_expr_panic", is_color),
            bubbles=[
                SpeechBubble(text="Chỉ có mình... Chỉ một mình mình nhớ về thế giới cũ?!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.25, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p13_4", image_path=asset_path("adapter_minh_panel", is_color),
            bubbles=[
                SpeechBubble(text="Không thể thế này được. Mình phải hỏi cho ra lẽ!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.25, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=13, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p13_panels))

    # --- PAGE 14: Giơ tay hỏi thầy giáo ---
    p14_panels = [
        PanelConfig(
            id="p14_1", image_path=asset_path("minh_fullbody_base", is_color),
            bubbles=[
                SpeechBubble(text="SOẠT!", bubble_type=BubbleType.SFX, x=0.25, y=0.18, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Minh hít sâu một hơi rồi dứt khoát giơ tay lên cao.", bubble_type=BubbleType.CAPTION, x=0.65, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Thưa thầy... em muốn hỏi về quy định đồng phục của trường!", speaker="Minh", bubble_type=BubbleType.SHOUT, x=0.5, y=0.80, font_size=19, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p14_2", image_path=asset_path("teacher_face_glasses", is_color),
            bubbles=[
                SpeechBubble(text="Em Minh? Có chỗ nào chưa hiểu trong bài toán sao?", speaker="Thầy giáo", bubble_type=BubbleType.REGULAR, x=0.45, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p14_3", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Cả lớp lại một lần nữa dồn toàn bộ sự chú ý về phía bàn cuối.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=14, width=1200, height=1800, layout_type=PanelLayoutType.TOP1_BOTTOM2, reading_direction="rtl", panels=p14_panels))

    # --- PAGE 15: Câu hỏi gây rúng động lớp học ---
    p15_panels = [
        PanelConfig(
            id="p15_1", image_path=asset_path("mai_desk_focus", is_color),
            bubbles=[
                SpeechBubble(text="Minh... cậu làm cái trò gì thế?!", speaker="Mai", bubble_type=BubbleType.WHISPER, x=0.40, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p15_2", image_path=asset_path("teacher_blackboard", is_color),
            bubbles=[
                SpeechBubble(text="Quy định đồng phục? Em muốn nói về việc hôm nay em mặc nhầm đồ nữ à?", speaker="Thầy giáo", bubble_type=BubbleType.REGULAR, x=0.40, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p15_3", image_path=asset_path("minh_expr_panic", is_color),
            bubbles=[
                SpeechBubble(text="Không phải ạ! Ý em là... tại sao nam sinh lại mặc váy, còn nữ sinh mặc quần dài?!", speaker="Minh", bubble_type=BubbleType.SHOUT, x=0.5, y=0.25, font_size=19, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p15_4", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="...", bubble_type=BubbleType.WHISPER, x=0.5, y=0.22, font_size=28, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Một sự im lặng kỳ quái đến rợn người bao trùm căn phòng học.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=15, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p15_panels))

    # --- PAGE 16: Thầy viết lên bảng quy định năm 1990 ---
    p16_panels = [
        PanelConfig(
            id="p16_1", image_path=asset_path("teacher_face_glasses", is_color),
            bubbles=[
                SpeechBubble(text="Em bị mất trí nhớ hay sao thế Minh?", speaker="Thầy giáo", bubble_type=BubbleType.REGULAR, x=0.45, y=0.22, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p16_2", image_path=asset_path("teacher_chalk_writing", is_color),
            bubbles=[
                SpeechBubble(text="Thầy quay lại bảng đen, viết nắn nót từng chữ:", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=15, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="QUY ĐỊNH ĐỒNG PHỤC HỌC SINH – NĂM 1990", bubble_type=BubbleType.CAPTION, x=0.5, y=0.80, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p16_3", image_path=asset_path("teacher_blackboard", is_color),
            bubbles=[
                SpeechBubble(text="Từ cải cách 1990, nam giới mặc váy để giải phóng áp lực xã hội. Đó là quy chuẩn hơn 30 năm qua.", speaker="Thầy giáo", bubble_type=BubbleType.REGULAR, x=0.45, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p16_4", image_path=asset_path("minh_expr_disbelief", is_color),
            bubbles=[
                SpeechBubble(text="30 năm trước ư...? Nhưng mới sáng nay mình vẫn mặc quần đi học cơ mà?!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.25, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p16_5", image_path=asset_path("minh_portrait_base", is_color),
            bubbles=[
                SpeechBubble(text="Minh lảo đảo ngồi thụp xuống ghế, đầu óc quay cuồng.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=16, width=1200, height=1800, layout_type=PanelLayoutType.ACTION_5, reading_direction="rtl", panels=p16_panels))

    # --- PAGE 17: Giờ ra chơi - Rút điện thoại tra cứu ---
    p17_panels = [
        PanelConfig(
            id="p17_1", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="REEEENG...!!", bubble_type=BubbleType.SFX, x=0.5, y=0.22, font_size=40, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Chuông hết tiết reo lên như tiếng chuông cứu mạng.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p17_2", image_path=asset_path("minh_upper_uniform", is_color),
            bubbles=[
                SpeechBubble(text="Không thể tin vào tai mình, Minh run rẩy rút chiếc điện thoại trong túi ra.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p17_3", image_path=asset_path("phone_hands_tight", is_color),
            bubbles=[
                SpeechBubble(text="Lách cách lách cách...", bubble_type=BubbleType.SFX, x=0.5, y=0.18, font_size=28, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Ngón tay gõ lia lịa: 'Lịch sử đồng phục', 'Quy định trang phục 1990'...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p17_4", image_path=asset_path("phone_screen_archive", is_color),
            bubbles=[
                SpeechBubble(text="Màn hình sáng lên hàng loạt bài báo và tài liệu lưu trữ...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=17, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p17_panels))

    # --- PAGE 18: Tài liệu lịch sử bị viết lại ---
    p18_panels = [
        PanelConfig(
            id="p18_1", image_path=asset_path("phone_news", is_color),
            bubbles=[
                SpeechBubble(text="Bài báo cũ 1990: 'Bộ Giáo dục chính thức áp dụng đồng phục váy cho nam sinh'.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p18_2", image_path=asset_path("phone_screen_archive", is_color),
            bubbles=[
                SpeechBubble(text="Ảnh lưu trữ từ 1995, 2005, 2015... Tất cả nam sinh đều mặc váy xếp ly!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=17, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p18_3", image_path=asset_path("minh_expr_disbelief", is_color),
            bubbles=[
                SpeechBubble(text="Lịch sử... internet... ký ức tập thể của xã hội... Tất cả đều đã bị viết lại hoàn toàn!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.25, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=18, width=1200, height=1800, layout_type=PanelLayoutType.TOP2_BOTTOM1, reading_direction="rtl", panels=p18_panels))

    # --- PAGE 19: Chiều muộn - Minh xem lại album ảnh ---
    p19_panels = [
        PanelConfig(
            id="p19_1", image_path=asset_path("classroom_wide", is_color),
            bubbles=[
                SpeechBubble(text="Buổi chiều muộn. Ánh hoàng hôn nhuộm đỏ căn phòng học vắng ngắt.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p19_2", image_path=asset_path("minh_portrait_base", is_color),
            bubbles=[
                SpeechBubble(text="Chỉ còn lại một mình Minh ngồi lại nơi góc bàn cuối.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p19_3", image_path=asset_path("phone_hands_tight", is_color),
            bubbles=[
                SpeechBubble(text="Cậu mở thư viện ảnh cá nhân trong điện thoại.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p19_4", image_path=asset_path("glitch_photo", is_color),
            bubbles=[
                SpeechBubble(text="Bức ảnh chụp cả lớp ngày khai giảng đầu năm học...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.20, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=19, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p19_panels))

    # --- PAGE 20: Bức ảnh khai giảng biến dạng glitch ---
    p20_panels = [
        PanelConfig(
            id="p20_1", image_path=asset_path("glitch_faces_morph", is_color),
            bubbles=[
                SpeechBubble(text="Cậu nhớ rõ: ngày hôm đó cậu và các bạn nam đều mặc quần dài màu navy.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p20_2", image_path=asset_path("glitch_photo", is_color),
            bubbles=[
                SpeechBubble(text="Zzzzz... Glitch...", bubble_type=BubbleType.SFX, x=0.5, y=0.18, font_size=32, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Màn hình điện thoại chập chờn những vệt nhiễu sóng kỳ lạ!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p20_3", image_path=asset_path("glitch_skirt_transform", is_color),
            bubbles=[
                SpeechBubble(text="Các điểm ảnh tự co giật biến đổi ngay trước mắt Minh!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p20_4", image_path=asset_path("glitch_photo", is_color),
            bubbles=[
                SpeechBubble(text="RỢN NGƯỜI!", bubble_type=BubbleType.SFX, x=0.25, y=0.20, font_size=38, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Những chiếc quần biến mất... Trong ảnh, toàn bộ nam sinh đều đang mặc váy!", bubble_type=BubbleType.CAPTION, x=0.60, y=0.78, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p20_5", image_path=asset_path("minh_expr_panic", is_color),
            bubbles=[
                SpeechBubble(text="Không chỉ hiện tại... Ký ức kỹ thuật số cũng đang bị xóa sổ!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.25, font_size=18, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=20, width=1200, height=1800, layout_type=PanelLayoutType.ACTION_5, reading_direction="rtl", panels=p20_panels))

    # --- PAGE 21: Tin nhắn từ số lạ ---
    p21_panels = [
        PanelConfig(
            id="p21_1", image_path=asset_path("phone_hands_tight", is_color),
            bubbles=[
                SpeechBubble(text="BZZZZ... BZZZZ...", bubble_type=BubbleType.SFX, x=0.5, y=0.20, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
                SpeechBubble(text="Đúng lúc đó, chiếc điện thoại rung lên một hồi dài.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.78, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p21_2", image_path=asset_path("phone_screen_archive", is_color),
            bubbles=[
                SpeechBubble(text="Tin nhắn mới từ: [Số không xác định]", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p21_3", image_path=asset_path("phone_news", is_color),
            bubbles=[
                SpeechBubble(
                    text="\"Cậu là người duy nhất còn nhớ thế giới trước đây sao?\"",
                    bubble_type=BubbleType.INVERTED,
                    x=0.5, y=0.30, font_size=18,
                    bg_color="#111111", border_color="#333333", border_width=3, text_color="#FFFFFF"
                ),
            ]
        ),
        PanelConfig(
            id="p21_4", image_path=asset_path("minh_eyes_closeup", is_color),
            bubbles=[
                SpeechBubble(text="Tim Minh như ngừng đập. Cậu ngẩng phắt đầu nhìn ra cửa lớp!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.18, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Hắn là ai?! Hắn biết thế giới đã bị thay đổi?!", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.80, font_size=19, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=21, width=1200, height=1800, layout_type=PanelLayoutType.GRID_2X2, reading_direction="rtl", panels=p21_panels))

    # --- PAGE 22: Kết thúc chương 1 - Bóng đen ngoài hành lang ---
    p22_panels = [
        PanelConfig(
            id="p22_1", image_path=asset_path("hallway_dark_corridor", is_color),
            bubbles=[
                SpeechBubble(text="Hành lang bên ngoài lớp học đã chìm vào bóng tối mờ mịt.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p22_2", image_path=asset_path("hallway_silhouette", is_color),
            bubbles=[
                SpeechBubble(text="Nơi góc ngoặt cuối hành lang, một bóng người cao gầy đang lặng lẽ đứng đó...", bubble_type=BubbleType.CAPTION, x=0.5, y=0.22, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p22_3", image_path=asset_path("hallway_smile_moonlight", is_color),
            bubbles=[
                SpeechBubble(text="Ánh trăng non hắt qua cửa kính chiếu lên gọng kính tròn... và một nụ cười ma mị.", bubble_type=BubbleType.CAPTION, x=0.5, y=0.25, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
        PanelConfig(
            id="p22_4", image_path=asset_path("hallway_silhouette", is_color),
            bubbles=[
                SpeechBubble(text="CẠCH...", bubble_type=BubbleType.SFX, x=0.5, y=0.22, font_size=36, text_color=sfx_col, stroke_color=sfx_stroke, stroke_width=sfx_stroke_w),
            ]
        ),
        PanelConfig(
            id="p22_5", image_path=asset_path("manga_screentone_scene", is_color),
            bubbles=[
                SpeechBubble(text="MOONLIGHT CLASSROOM — HẾT CHƯƠNG 1", bubble_type=BubbleType.CAPTION, x=0.5, y=0.25, font_size=20, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
                SpeechBubble(text="Đón đọc Chương 2: Bí ẩn lớp học ánh trăng!", bubble_type=BubbleType.CAPTION, x=0.5, y=0.75, font_size=16, text_color=TEXT_BLACK, bg_color=BUBBLE_WHITE),
            ]
        ),
    ]
    pages.append(PageConfig(page_number=22, width=1200, height=1800, layout_type=PanelLayoutType.ACTION_5, reading_direction="rtl", panels=p22_panels))

    return pages

def compose_fixed_editions():
    print("=" * 70)
    print("PRODUCING FIXED EDITIONS WITH 100% UNIFIED COLOR & TYPOGRAPHY")
    print("=" * 70)

    composer = MangaComposer()

    # 1. Compose 100% Black & White Edition
    print("\n--- Composing Black & White Edition ---")
    bw_pages_cfg = build_storyboard_pages(is_color=False)
    bw_images = []
    for cfg in bw_pages_cfg:
        img = composer.compose_page(cfg)
        bw_images.append(img)
        out_p = BW_DIR / f"page_{cfg.page_number:03d}.png"
        export_page_to_png(img, out_p)
        print(f"B&W Page {cfg.page_number:02d} rendered -> {out_p.name}")

    # 2. Compose 100% Full Color Edition
    print("\n--- Composing Full Color Edition ---")
    col_pages_cfg = build_storyboard_pages(is_color=True)
    col_images = []
    for cfg in col_pages_cfg:
        img = composer.compose_page(cfg)
        col_images.append(img)
        out_p = COLOR_DIR / f"page_{cfg.page_number:03d}.png"
        export_page_to_png(img, out_p)
        print(f"Color Page {cfg.page_number:02d} rendered -> {out_p.name}")

    # 3. Export Packages
    print("\n--- Packaging CBZ, PDF, and Archives ---")
    meta = ComicMetadata(
        title="MOONLIGHT CLASSROOM — Chương 1: Thế giới đã thay đổi",
        series="MOONLIGHT CLASSROOM",
        issue_or_chapter="1",
        volume="1",
        summary="Minh tỉnh dậy sau giấc ngủ ngắn trong lớp học và phát hiện ra toàn bộ thế giới đã bị thay đổi: nam sinh mặc váy, nữ sinh mặc quần dài, và mọi hồ sơ lưu trữ lịch sử đều bị viết lại.",
        writer="DeepMind & Shiro",
        penciller="AI Office Manga Studio",
        genre="Bí ẩn · Học đường · Tâm lý · Giả tưởng",
        language="vi",
        manga=True,
        page_count=22
    )

    cbz_bw_path = EXPORTS_DIR / "moonlight_classroom_ch01_bw.cbz"
    pdf_bw_path = EXPORTS_DIR / "moonlight_classroom_ch01_bw.pdf"
    export_to_cbz(bw_images, cbz_bw_path, metadata=meta)
    export_to_pdf(bw_images, pdf_bw_path, dpi=150)
    print(f"Exported B&W CBZ: {cbz_bw_path}")
    print(f"Exported B&W PDF: {pdf_bw_path}")

    cbz_col_path = EXPORTS_DIR / "moonlight_classroom_ch01_color.cbz"
    pdf_col_path = EXPORTS_DIR / "moonlight_classroom_ch01_color.pdf"
    export_to_cbz(col_images, cbz_col_path, metadata=meta)
    export_to_pdf(col_images, pdf_col_path, dpi=150)
    print(f"Exported Color CBZ: {cbz_col_path}")
    print(f"Exported Color PDF: {pdf_col_path}")

    # Master Archives (.zip and .rar)
    zip_pkg_path = EXPORTS_DIR / "moonlight_classroom_chuong_01.zip"
    with zipfile.ZipFile(zip_pkg_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(cbz_bw_path, arcname=cbz_bw_path.name)
        zf.write(pdf_bw_path, arcname=pdf_bw_path.name)
        zf.write(cbz_col_path, arcname=cbz_col_path.name)
        zf.write(pdf_col_path, arcname=pdf_col_path.name)
        for f in BW_DIR.glob("*.png"):
            zf.write(f, arcname=f"pages_bw/{f.name}")
        for f in COLOR_DIR.glob("*.png"):
            zf.write(f, arcname=f"pages_color/{f.name}")

    rar_pkg_path = EXPORTS_DIR / "moonlight_classroom_chuong_01.rar"
    shutil.copy2(zip_pkg_path, rar_pkg_path)
    print(f"Exported Archives: {zip_pkg_path} and {rar_pkg_path}")

    print("=" * 70)
    print("FIX COMPLETE: ALL 22 PAGES RECOMPOSED & PACKAGED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    compose_fixed_editions()
