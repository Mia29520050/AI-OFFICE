#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_demo_page.py
Render a complete, high-fidelity Manga Page demonstrating:
  1. Authentic Anime Characters (Minh, Mai) with distinct facial features & expressions
  2. Perspective Classroom & Outdoor Backgrounds with Screentone and Speedlines
  3. Smart Speech Bubble Layout (Zero Overlap, RTL reading flow, Face Avoidance)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from PIL import Image, ImageDraw, ImageFont

from app.manga_illustrator import (
    MangaIllustrationEngine,
    draw_character_minh,
    draw_character_mai,
    draw_screentone_region,
    draw_manga_eyes,
    draw_cross_hatch,
    get_font,
)
from app.manga_composer import (
    MangaComposer,
    PageConfig,
    PanelConfig,
    PanelLayoutType,
    SpeechBubble,
    BubbleType,
)
from app.smart_bubble_layout import optimize_speech_bubbles


def draw_speed_lines_radial(draw: ImageDraw.ImageDraw, w: int, h: int, cx: int, cy: int, count: int = 50):
    """Draw classic intense manga focus speedlines radiating from center."""
    for i in range(count):
        angle = (2 * math.pi / count) * i
        r_inner = 120 + (i % 5) * 15
        r_outer = max(w, h) * 1.2
        x0 = int(cx + r_inner * math.cos(angle))
        y0 = int(cy + r_inner * math.sin(angle))
        x1 = int(cx + r_outer * math.cos(angle))
        y1 = int(cy + r_outer * math.sin(angle))
        line_w = 2 if (i % 3 == 0) else 1
        draw.line([(x0, y0), (x1, y1)], fill=(20, 20, 25), width=line_w)


def render_panel1_classroom(w: int, h: int) -> Image.Image:
    """Panel 1: Bối cảnh lớp học bên cửa sổ buổi sáng, bầu trời mây và Minh ngồi ngắm mây."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Sky outside window
    draw.rectangle([0, 0, int(w * 0.55), h], fill=(235, 242, 252))
    # Manga clouds
    for cx, cy, cr in [(120, 50, 40), (180, 65, 50), (90, 75, 35), (320, 90, 55)]:
        draw.ellipse([cx - cr, cy - cr // 2, cx + cr, cy + cr // 2], fill=(255, 255, 255), outline=(190, 205, 225), width=2)

    # Window frame perspective
    draw.rectangle([int(w * 0.05), 10, int(w * 0.52), h - 10], outline=(40, 45, 55), width=5)
    draw.line([(int(w * 0.28), 10), (int(w * 0.28), h - 10)], fill=(40, 45, 55), width=3)
    draw.line([(int(w * 0.05), int(h * 0.45)), (int(w * 0.52), int(h * 0.45))], fill=(40, 45, 55), width=3)

    # Diagonal Sunlight Rays
    for ray_x in range(int(w * 0.1), int(w * 0.5), 65):
        draw.polygon([(ray_x, 10), (ray_x + 70, 10), (ray_x + 320, h), (ray_x + 250, h)], fill=(255, 255, 245))

    # Classroom interior screentone
    draw_screentone_region(draw, (int(w * 0.52), 0, w, h), dot_spacing=8, dot_radius=1)

    # Chalkboard in background edge
    draw.rectangle([int(w * 0.85), 20, w, int(h * 0.6)], fill=(50, 70, 60), outline=(20, 25, 25), width=3)
    draw.text((int(w * 0.87), 40), "Tiết 1\nĐại số", fill=(220, 230, 225), font=get_font(16))

    # Character Minh sitting at desk looking out window
    draw_character_minh(draw, cx=int(w * 0.70), cy=int(h * 0.45), scale=0.95, pose="sitting_window")

    # Crisp border
    draw.rectangle([1, 1, w - 2, h - 2], outline=(15, 15, 20), width=3)
    return img


def render_panel2_mai_dialogue(w: int, h: int) -> Image.Image:
    """Panel 2: Nữ sinh Mai xuất hiện chào buổi sáng, biểu cảm tươi tắn, lớp học phía sau."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Classroom hallway background with screentone
    draw_screentone_region(draw, (0, 0, w, h), dot_spacing=7, dot_radius=1, fill_color=(190, 195, 205))

    # Classroom door frame
    draw.rectangle([20, 10, int(w * 0.35), h - 10], fill=(245, 240, 235), outline=(50, 50, 60), width=4)
    draw.line([(int(w * 0.35), 10), (int(w * 0.35), h - 10)], fill=(50, 50, 60), width=4)
    # Door glass window
    draw.rectangle([40, 30, int(w * 0.32), int(h * 0.45)], fill=(230, 240, 250), outline=(50, 50, 60), width=2)
    draw.line([(45, 35), (int(w * 0.28), int(h * 0.40))], fill=(255, 255, 255), width=2)

    # Sparkling flower effect for Mai
    for fx, fy in [(int(w * 0.25), 80), (int(w * 0.75), 70), (int(w * 0.85), int(h * 0.65))]:
        draw.text((fx, fy), "✨", fill=(240, 180, 50), font=get_font(22))

    # Character Mai in center-left position, looking gently forward
    draw_character_mai(draw, cx=int(w * 0.52), cy=int(h * 0.55), scale=1.1)

    # Blush screentone on Mai's cheeks
    draw.ellipse([int(w * 0.52 - 32), int(h * 0.55 - 42), int(w * 0.52 - 12), int(h * 0.55 - 32)], fill=(255, 190, 190))
    draw.ellipse([int(w * 0.52 + 12), int(h * 0.55 - 42), int(w * 0.52 + 32), int(h * 0.55 - 32)], fill=(255, 190, 190))

    # Crisp border
    draw.rectangle([1, 1, w - 2, h - 2], outline=(15, 15, 20), width=3)
    return img


def render_panel3_shock_climax(w: int, h: int) -> Image.Image:
    """Panel 3: Cao trào kinh ngạc - Minh bật dậy với biểu cảm shocked, speed lines dữ dội."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Intense radial speed lines from Minh's head
    head_x = int(w * 0.48)
    head_y = int(h * 0.42)
    draw_speed_lines_radial(draw, w, h, head_x, head_y, count=55)

    # Dark screentone vignette at edges
    draw_screentone_region(draw, (0, 0, int(w * 0.22), h), dot_spacing=6, dot_radius=2, fill_color=(40, 40, 50))
    draw_screentone_region(draw, (int(w * 0.78), 0, w, h), dot_spacing=6, dot_radius=2, fill_color=(40, 40, 50))

    # Character Minh in standing shock pose
    draw_character_minh(draw, cx=head_x, cy=int(h * 0.52), scale=1.15, pose="standing_shock")

    # Bold SFX "RẦM!!" across the background
    draw.text((int(w * 0.12), int(h * 0.65)), "RẦM!!", fill=(25, 25, 30), font=get_font(42))
    draw.text((int(w * 0.12) - 2, int(h * 0.65) - 2), "RẦM!!", fill=(255, 60, 60), font=get_font(42))

    # Crisp border
    draw.rectangle([1, 1, w - 2, h - 2], outline=(15, 15, 20), width=4)
    return img


def main():
    print("===================================================================")
    print("🎨 RENDERING DEMO MANGA PAGE: ANIME CHARACTERS + SMART BUBBLE FLOW")
    print("===================================================================")

    page_w = 1200
    page_h = 1680

    # Create temporary images for panels
    data_dir = ROOT / "data" / "manga"
    data_dir.mkdir(parents=True, exist_ok=True)

    img_p1 = render_panel1_classroom(1120, 460)
    img_p2 = render_panel2_mai_dialogue(1120, 520)
    img_p3 = render_panel3_shock_climax(1120, 540)

    p1_path = data_dir / "demo_p1.png"
    p2_path = data_dir / "demo_p2.png"
    p3_path = data_dir / "demo_p3.png"

    img_p1.save(p1_path)
    img_p2.save(p2_path)
    img_p3.save(p3_path)
    print("  ✓ Saved 3 individual panel art assets.")

    # Define dialogues for each panel with reading order
    # Panel 1: Thought bubble
    p1_bubbles = [
        SpeechBubble(
            text="Một buổi sáng dường như quá đỗi bình yên... trước khi thực tại đảo chiều.",
            bubble_type=BubbleType.THOUGHT,
            x=0.28, y=0.22, tail_x=0.28, tail_y=0.45
        )
    ]

    # Panel 2: Mai greets Minh, Minh responds -> Smart Anti-Collision Layout
    p2_bubbles = optimize_speech_bubbles([
        SpeechBubble(
            text="Chào buổi sáng, Minh! Cậu lại ngồi thẫn thờ ngắm mây rồi à?",
            bubble_type=BubbleType.REGULAR,
            x=0.74, y=0.20, tail_x=0.62, tail_y=0.48, # Top-Right (Mai speaks first)
            reading_order=1
        ),
        SpeechBubble(
            text="À... Mai đấy à? Tớ vừa mơ một giấc mơ kỳ lạ... Mọi người đều mặc váy!",
            bubble_type=BubbleType.REGULAR,
            x=0.26, y=0.78, tail_x=0.38, tail_y=0.55, # Bottom-Left (Minh responds)
            reading_order=2
        )
    ], panel_w=1120, panel_h=520)

    # Panel 3: Shock Climax -> Shout Bubble + Mai's explanation
    p3_bubbles = optimize_speech_bubbles([
        SpeechBubble(
            text="CÁI GÌ CƠ?! Không phải mơ... Tất cả nam sinh và cả thầy Lâm đều mặc váy thật sao?!",
            bubble_type=BubbleType.SHOUT,
            x=0.74, y=0.22, tail_x=0.56, tail_y=0.44, # Top-Right shouting
            reading_order=1
        ),
        SpeechBubble(
            text="Minh bị sốt à? Đó là đồng phục bắt buộc từ năm 1990 mà, cậu làm sao thế?",
            bubble_type=BubbleType.REGULAR,
            x=0.26, y=0.78, tail_x=0.35, tail_y=0.60, # Bottom-Left
            reading_order=2
        )
    ], panel_w=1120, panel_h=540)

    # Compose into full Manga Page
    page_cfg = PageConfig(
        width=page_w,
        height=page_h,
        layout_type=PanelLayoutType.THREE_ROWS,
        margin_x=40,
        margin_y=40,
        gutter_y=25,
        panels=[
            PanelConfig(image_path=str(p1_path), bubbles=p1_bubbles, border_width=3),
            PanelConfig(image_path=str(p2_path), bubbles=p2_bubbles, border_width=3),
            PanelConfig(image_path=str(p3_path), bubbles=p3_bubbles, border_width=3),
        ]
    )

    composer = MangaComposer(default_font_path=ROOT / "app" / "ui" / "assets" / "Inter-Variable.ttf")
    final_page = composer.compose_page(page_cfg)

    # Output path
    output_png = data_dir / "demonstration_anime_manga_page.png"
    final_page.save(output_png, "PNG")
    print(f"  ✓ Full Manga Page Composed & Saved: {output_png} ({page_w}x{page_h})")
    print("===================================================================")


if __name__ == "__main__":
    main()
