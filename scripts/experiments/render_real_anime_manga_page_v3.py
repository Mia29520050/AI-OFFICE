#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_real_anime_manga_page_v3.py
Compose Manga Page V3 implementing all architectural best practices:
  1. Panel 1: Akihabara street with authentic Japanese neon typography (秋葉原, アニメ, 電気街, サイバ, ゲーム, 24H),
              shadow curves lifting building details, realistic diagonal rain streaks, and clean LTR captions.
  2. Panel 2: Heroine battle pose with sleek energy katana, fully articulated arm and hand grip,
              clean natural torso anatomy, cyan rim lighting separating cloak from starry sky.
  3. Panel 2 SFX: "KEEE-ENG!" rendered as dynamic border-breaking SFX (no tail, large font 56pt, yellow with black stroke, angled).
  4. Panel 2 Shout: "BẢO KIẾM TINH TÚ... KHAI MỞ!" in bold starburst at top-right open sky with prominent text.
  5. Panel 3: Heroine close-up face portrait kept 100% clean, removing redundant bottom thought bubble.
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


def compose_v3_page():
    data_dir = ROOT / "data" / "manga"
    v3_dir = data_dir / "real_panels_v3"
    v2_dir = data_dir / "real_panels_v2"

    p1_path = v3_dir / "p1_akihabara_v3.png"
    p2_path = v3_dir / "p2_sword_v3.png"
    p3_path = v2_dir / "p2_face.png"

    assert p1_path.exists(), f"Missing {p1_path}"
    assert p2_path.exists(), f"Missing {p2_path}"
    assert p3_path.exists(), f"Missing {p3_path}"

    page_w = 1200
    page_h = 1750

    # Panel 1: Akihabara Scenery (Top Panel, 1120 x 742 approx)
    # 2 Rectangular Captions (LTR Reading flow: Location establishment -> Anomaly detection)
    p1_bubbles = [
        SpeechBubble(
            text="Tokyo, 02:00 AM... Khu phố Akihabara tĩnh lặng dưới ánh neon.",
            bubble_type=BubbleType.CAPTION,
            x=0.24,
            y=0.12,
            width=0.38,
            height=0.12,
            reading_order=1,
            speaker="Narrator",
        ),
        SpeechBubble(
            text="Tín hiệu ma thuật dị thường phát ra ngay phía trước...",
            bubble_type=BubbleType.CAPTION,
            x=0.76,
            y=0.12,
            width=0.36,
            height=0.12,
            reading_order=2,
            speaker="Narrator",
        ),
    ]

    # Panel 2: Heroine Battle Stance with Sleek Katana (Bottom-Left Panel, 550 x 900 approx)
    # 1. Shout Bubble: "BẢO KIẾM TINH TÚ... KHAI MỞ!" placed at top-right open starry sky (x=0.80, y=0.13)
    #    with punchy bold text and short pointer towards speaker.
    # 2. Dynamic SFX: "KEEE-ENG!" rendered with BubbleType.SFX (no tail, bold yellow 56pt, heavy 8px black stroke,
    #    rotated -12 deg, overlapping bottom-left border for dynamic motion effect!)
    p2_bubbles = [
        SpeechBubble(
            text="BẢO KIẾM TINH TÚ... KHAI MỞ!",
            bubble_type=BubbleType.SHOUT,
            x=0.79,
            y=0.13,
            width=0.36,
            height=0.19,
            font_size=20,
            tail_x=0.64,
            tail_y=0.19,
            reading_order=1,
            speaker="Aria",
        ),
        SpeechBubble(
            text="KEEE-ENG!",
            bubble_type=BubbleType.SFX,
            x=0.22,
            y=0.94,
            font_size=58,
            text_color="#FFE500",
            stroke_color="#000000",
            stroke_width=8,
            rotation=-14.0,
            reading_order=2,
            speaker="SFX",
        ),
    ]

    # Panel 3: Heroine Close-up Portrait (Bottom-Right Panel, 550 x 900 approx)
    # Kept clean and focused on Aria's expression. Redundant bottom thought bubble removed.
    # Dialogue callout positioned safely above head in dark sky with short tail ending at y=0.16.
    p3_bubbles = [
        SpeechBubble(
            text="Ngươi định trốn ở góc tối đó đến bao giờ, bóng ma hư vô?!",
            bubble_type=BubbleType.REGULAR,
            x=0.50,
            y=0.08,
            width=0.48,
            height=0.13,
            tail_x=0.50,
            tail_y=0.16,
            reading_order=1,
            speaker="Aria",
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
    print("Composing Manga Page V3...")
    composed_image = composer.compose_page(page_cfg)

    out_file = data_dir / "final_anime_manga_showcase_v3.png"
    composed_image.save(out_file, "PNG")
    print(f"Saved composed page V3 to: {out_file}")

    art_dest = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394\final_anime_manga_showcase_v3.png")
    shutil.copyfile(out_file, art_dest)
    print(f"Copied to artifact directory: {art_dest}")


if __name__ == "__main__":
    compose_v3_page()
