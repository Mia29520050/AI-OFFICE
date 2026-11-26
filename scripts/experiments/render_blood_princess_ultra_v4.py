#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_blood_princess_ultra_v4.py
Render the Ultra Quality Manga Page (Post-2020 Anime Aesthetic Edition)
featuring:
  1. Panel 1: Gothic Cathedral Ruins with crimson moonlight and volumetric fog.
  2. Panel 2: The Cursed Blood Knight (Kaelen) with segmented dark plate armor,
     glowing crimson chest sigil, firm two-handed sword grip, and dramatic rim light.
  3. Panel 3: The Blood Princess (Carmilla) with obsidian jewel crown, silver layered hair,
     delicate ruby eyes, subtle vampire fangs, and soft atmospheric backlighting.
  4. Typesetting: LTR narrative captions, starburst shout in open space, border-breaking SFX "CLANNNG!",
     and zero eye/face collision.
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
)


def compose_ultra_v4():
    data_dir = ROOT / "data" / "manga"
    p1_path = data_dir / "blood_princess_panels" / "p1_blood_moon_cathedral.png"
    p2_path = data_dir / "test_cfg_comparison" / "knight_gothic_777888.png"
    p3_path = data_dir / "test_cfg_comparison" / "carmilla_cfg_1.5.png"

    assert p1_path.exists(), f"Missing {p1_path}"
    assert p2_path.exists(), f"Missing {p2_path}"
    assert p3_path.exists(), f"Missing {p3_path}"

    page_w = 1200
    page_h = 1750

    # Panel 1: Establishing Gothic Cathedral
    p1_bubbles = [
        SpeechBubble(
            text="Thánh Điện Tàn Tích... Dưới vầng trăng máu đỏ rực, phong ấn ngàn năm đã vỡ vụn.",
            bubble_type=BubbleType.CAPTION,
            x=0.25,
            y=0.12,
            width=0.42,
            height=0.12,
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
            font_size=20,
            tail_x=0.62,
            tail_y=0.22,
            reading_order=1,
            speaker="Kaelen",
        ),
        SpeechBubble(
            text="CLANNNG!",
            bubble_type=BubbleType.SFX,
            x=0.18,
            y=0.94,
            font_size=58,
            text_color="#FF2A2A",
            stroke_color="#000000",
            stroke_width=8,
            rotation=-12.0,
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
            PanelConfig(image_path=str(p1_path), bubbles=p1_bubbles, border_width=3),
            PanelConfig(image_path=str(p2_path), bubbles=p2_bubbles, border_width=3),
            PanelConfig(image_path=str(p3_path), bubbles=p3_bubbles, border_width=3),
        ],
    )

    composer = MangaComposer()
    print("Composing Blood Princess & Knight Ultra Edition V4...")
    composed_page = composer.compose_page(page_cfg)

    out_file = data_dir / "blood_princess_and_knight_ultra_v4.png"
    composed_page.save(out_file, "PNG")
    print(f"Saved Ultra Showcase Page to: {out_file}")

    art_dest = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394\blood_princess_and_knight_ultra_v4.png")
    shutil.copyfile(out_file, art_dest)
    print(f"Copied to artifact directory: {art_dest}")


if __name__ == "__main__":
    compose_ultra_v4()
