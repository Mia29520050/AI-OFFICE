#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_real_anime_manga_page_v2.py
Composite the verified anime diffusion panels into a complete Manga Page V2
strictly addressing every point in the user critique:
  1. Panel 1: Pure scenery, rain reflections, zero fake text, two rectangular captions (LTR).
  2. Panel 2: Heroine battle pose with sword, starburst bubble in open top-right sky (no face/hair overlap),
              clean SFX at bottom-left, zero tofu glyphs, auto-padded.
  3. Panel 3: Heroine close-up face, zero speech bubble / thought bubble overlap on eyes or face:
              - Dialogue bubble at top center with short tail ending above hair (y=0.18)
              - Thought bubble at bottom in dark cloak area with trailing dots pointing up towards chest
              - Strict character visual consistency (silver bob, vivid crimson eyes, dark suit).
  4. Uniform gutters (20px), equal bottom panel heights, professional manga typesetting.
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


def compose_v2_page():
    data_dir = ROOT / "data" / "manga"
    panels_dir = data_dir / "real_panels_v2"

    p1_path = panels_dir / "p1_scenery.png"
    p2_path = panels_dir / "p3_sword.png"    # Action panel (bottom-left)
    p3_path = panels_dir / "p2_face.png"     # Close-up panel (bottom-right)

    assert p1_path.exists(), f"Missing {p1_path}"
    assert p2_path.exists(), f"Missing {p2_path}"
    assert p3_path.exists(), f"Missing {p3_path}"

    page_w = 1200
    page_h = 1750

    # Panel 1: Scenery (Top Panel, 1120 x 742 approx)
    # LTR Reading Order:
    # 1. Left Caption: Tokyo 02:00 AM (establishing location)
    # 2. Right Caption: Anomalous magic signal detected ahead
    # NO tails (BubbleType.CAPTION guarantees tail_x=None, tail_y=None)
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

    # Panel 2: Action sword stance (Bottom-Left Panel, 550 x 900 approx)
    # Character face is at [0.55, 0.20]. Top-right corner (x=0.82, y=0.12) is open starry sky.
    # Starburst bubble placed in open top-right sky, avoiding hair/face.
    # SFX placed in bottom-left dark cape region.
    # All emojis removed, no tofu boxes, padded starburst.
    p2_bubbles = [
        SpeechBubble(
            text="BẢO KIẾM TINH TÚ... KHAI MỞ!",
            bubble_type=BubbleType.SHOUT,
            x=0.82,
            y=0.12,
            width=0.34,
            height=0.18,
            tail_x=0.68,
            tail_y=0.19,
            reading_order=1,
            speaker="Aria",
        ),
        SpeechBubble(
            text="KEEE-ENG!",
            bubble_type=BubbleType.SHOUT,
            x=0.20,
            y=0.88,
            width=0.30,
            height=0.12,
            reading_order=2,
            speaker="SFX",
        ),
    ]

    # Panel 3: Close-up Face (Bottom-Right Panel, 550 x 900 approx)
    # Face is centered at [0.50, 0.35], mouth at [0.50, 0.50].
    # Dialogue bubble placed safely at top [x=0.50, y=0.08],
    # with a short tail ending at [0.50, 0.17] well above hair and forehead.
    # Thought bubble placed in bottom cloak area [x=0.32, y=0.88],
    # with thought bubbles trailing upward towards collar [0.38, 0.72], zero eye overlap!
    p3_bubbles = [
        SpeechBubble(
            text="Ngươi định trốn ở góc tối đó đến bao giờ, bóng ma hư vô?!",
            bubble_type=BubbleType.REGULAR,
            x=0.50,
            y=0.08,
            width=0.48,
            height=0.13,
            tail_x=0.50,
            tail_y=0.18,
            reading_order=1,
            speaker="Aria",
        ),
        SpeechBubble(
            text="(Lần này... mình nhất định không để ngươi chạy thoát!)",
            bubble_type=BubbleType.THOUGHT,
            x=0.32,
            y=0.88,
            width=0.46,
            height=0.13,
            tail_x=0.38,
            tail_y=0.72,
            reading_order=2,
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
        reading_direction="ltr",  # LTR comic reading order (Panel 1 top -> Panel 2 bot-left -> Panel 3 bot-right)
        panels=[
            PanelConfig(image_path=str(p1_path), bubbles=p1_bubbles, border_width=3),
            PanelConfig(image_path=str(p2_path), bubbles=p2_bubbles, border_width=3),
            PanelConfig(image_path=str(p3_path), bubbles=p3_bubbles, border_width=3),
        ],
    )

    composer = MangaComposer()
    print("Composing Manga Page V2...")
    composed_image = composer.compose_page(page_cfg)

    out_file = data_dir / "final_anime_manga_showcase_v2.png"
    composed_image.save(out_file, "PNG")
    print(f"Saved composed page to: {out_file}")

    art_dest = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394\final_anime_manga_showcase_v2.png")
    shutil.copyfile(out_file, art_dest)
    print(f"Copied to artifact directory: {art_dest}")


if __name__ == "__main__":
    compose_v2_page()
