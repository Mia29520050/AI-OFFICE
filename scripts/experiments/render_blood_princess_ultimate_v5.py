#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_blood_princess_ultimate_v5.py
Render the Ultimate Manga Masterpiece Edition (V5) combining all aesthetic reforms:
  1. Authentic Manga Typography: Patrick Hand for dialogue, Comic Neue Bold for narration captions.
  2. Authentic Manga SFX: "CHOẢNG!" with 3D extruded block shadow, dual stroke, and blood sparks.
  3. De-AI Organic Filter: G-pen ink sharpening, organic paper grain, subtle screentone, zero plastic sheen.
  4. Top-tier Gothic Dark Fantasy Artwork: Cathedral Blood Moon, Kaelen the Cursed Knight, Carmilla the Blood Princess.
"""

import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app.manga_composer import (
    MangaComposer,
    PageConfig,
    PanelConfig,
    PanelLayoutType,
    SpeechBubble,
    BubbleType,
    PanelFilter,
)
from app.manga_fonts import FONT_FILES

def render_ultimate_v5():
    data_dir = ROOT / "data" / "manga"
    p1_path = data_dir / "blood_princess_panels" / "p1_blood_moon_cathedral.png"
    p2_path = data_dir / "test_cfg_comparison" / "knight_gothic_777888.png"
    p3_path = data_dir / "test_cfg_comparison" / "carmilla_cfg_1.5.png"

    assert p1_path.exists(), f"Missing {p1_path}"
    assert p2_path.exists(), f"Missing {p2_path}"
    assert p3_path.exists(), f"Missing {p3_path}"

    page_w = 1200
    page_h = 1750

    font_dialogue = str(FONT_FILES["dialogue"])
    font_narrative = str(FONT_FILES["comic_bold"])
    font_sfx = str(FONT_FILES["sfx"])

    print(f"Using Dialogue Font: {font_dialogue}")
    print(f"Using Narrative Font: {font_narrative}")
    print(f"Using SFX Font: {font_sfx}")

    # Panel 1: Establishing Gothic Cathedral
    p1_bubbles = [
        SpeechBubble(
            text="Thánh Điện Tàn Tích... Dưới vầng trăng máu đỏ rực, phong ấn ngàn năm đã vỡ vụn.",
            bubble_type=BubbleType.CAPTION,
            x=0.25,
            y=0.12,
            width=0.42,
            height=0.12,
            font_path=font_narrative,
            font_size=18,
            reading_order=1,
            speaker="Narrator",
        ),
        SpeechBubble(
            text="Khế ước huyết thệ hắc ám bắt đầu trỗi dậy...",
            bubble_type=BubbleType.CAPTION,
            x=0.75,
            y=0.12,
            width=0.36,
            height=0.12,
            font_path=font_narrative,
            font_size=18,
            reading_order=2,
            speaker="Narrator",
        ),
    ]

    # Panel 2: Blood Knight Kaelen (Bottom-Left)
    p2_bubbles = [
        SpeechBubble(
            text="DÙ THÂN XÁC NÀY CÓ HÓA THÀNH QUỶ DỮ... THANH KIẾM NÀY VẪN SẼ KHÔNG PHẢN BỘI LỜI THỀ!",
            bubble_type=BubbleType.SHOUT,
            x=0.78,
            y=0.14,
            width=0.40,
            height=0.20,
            font_path=font_dialogue,
            font_size=20,
            tail_x=0.62,
            tail_y=0.22,
            reading_order=1,
            speaker="Kaelen",
        ),
        SpeechBubble(
            text="CHOẢNG!",  # Replaced crude English "CLANNNG!" with authentic Manga sound!
            bubble_type=BubbleType.SFX,
            x=0.18,
            y=0.94,
            font_path=font_sfx,
            font_size=64,
            text_color="#FF2A2A",
            stroke_color="#000000",
            stroke_width=8,
            rotation=-14.0,
            reading_order=2,
            speaker="SFX",
        ),
    ]

    # Panel 3: Blood Princess Carmilla (Bottom-Right)
    p3_bubbles = [
        SpeechBubble(
            text="Thật ngoan cường làm sao... Nhưng dòng máu trong tim ngươi giờ đây đã thuộc về ta, hỡi Kỵ sĩ của ta!",
            bubble_type=BubbleType.REGULAR,
            x=0.50,
            y=0.08,
            width=0.50,
            height=0.13,
            font_path=font_dialogue,
            font_size=20,
            tail_x=0.50,
            tail_y=0.16,
            reading_order=1,
            speaker="Carmilla",
        ),
    ]

    page_cfg = PageConfig(
        width=page_w,
        height=page_h,
        layout_type=PanelLayoutType.TOP1_BOTTOM2,
        margin_x=40,
        margin_y=40,
        gutter_x=20,
        gutter_y=20,
        reading_direction="ltr",
        panels=[
            PanelConfig(
                image_path=str(p1_path),
                bubbles=p1_bubbles,
                border_width=3,
                filter_type=PanelFilter.DE_AI_ORGANIC,
            ),
            PanelConfig(
                image_path=str(p2_path),
                bubbles=p2_bubbles,
                border_width=3,
                filter_type=PanelFilter.DE_AI_ORGANIC,
            ),
            PanelConfig(
                image_path=str(p3_path),
                bubbles=p3_bubbles,
                border_width=3,
                filter_type=PanelFilter.DE_AI_ORGANIC,
            ),
        ],
    )

    composer = MangaComposer(default_font_path=font_dialogue)
    print("Composing Blood Princess & Knight Ultimate Edition V5...")
    composed_page = composer.compose_page(page_cfg)

    out_file = data_dir / "blood_princess_and_knight_ultimate_v5.png"
    composed_page.save(out_file, "PNG")
    print(f"Saved Ultimate V5 Page to: {out_file}")

    art_dest = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394\blood_princess_and_knight_ultimate_v5.png")
    shutil.copyfile(out_file, art_dest)
    print(f"Copied to artifact directory: {art_dest}")


if __name__ == "__main__":
    render_ultimate_v5()
