#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_blood_princess_knight_showcase.py
Render a complete Dark Fantasy Manga page showcasing "Huyết Cơ và Kỵ Sĩ" (The Blood Princess and the Knight)
implementing the full Japanese Manga grammar, adaptive eye/face clearance, dynamic bleeding SFX,
and Gothic dark fantasy aesthetics.
"""

import asyncio
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app.manga_comfy import ComfyAdapter, PanelArtRequest
from app.manga_composer import (
    MangaComposer,
    PageConfig,
    PanelConfig,
    PanelLayoutType,
    SpeechBubble,
    BubbleType,
)
from app.manga_anime_generator import MangaAnimePromptGenerator


async def generate_and_compose_blood_princess_showcase():
    data_dir = ROOT / "data" / "manga"
    panels_dir = data_dir / "blood_princess_panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    adapter = ComfyAdapter()
    stats = await adapter.get_system_stats()
    print(f"ComfyUI Online: {stats.is_online}, Checkpoint: {stats.active_checkpoint}")

    # Panel 1: Gothic Castle Stained Glass & Blood Moon
    p1_path = panels_dir / "p1_blood_moon_cathedral.png"
    if not p1_path.exists():
        req1 = PanelArtRequest(
            panel_id="blood_moon_cathedral",
            prompt="masterpiece, best quality, scenery, gothic cathedral ruins, high arched windows with stained glass, red moonlight streaming through, stone pillars, dark fantasy, volumetric crimson fog, mysterious shadows, wide cinematic shot",
            negative_prompt="worst quality, low quality, blurry, modern buildings, text",
            art_style="manga_color",
            width=768,
            height=512,
            seed=20261130,
            steps=10,
        )
        res1 = await adapter.generate_panel_art(req1)
        shutil.copyfile(res1.image_path, p1_path)
        print(f"Panel 1 ready: {p1_path}")

    # Panel 2: Carmilla (The Blood Princess / Huyết Cơ)
    p2_path = panels_dir / "p2_carmilla_vampire.png"
    if not p2_path.exists():
        req2 = PanelArtRequest(
            panel_id="carmilla_vampire",
            prompt="masterpiece, best quality, 1girl, solo, anime girl, close up face portrait, silver long hair curled locks, glowing ruby red eyes, small fangs, gothic black and crimson dress, dark fantasy vampire queen, obsidian crown, arrogant confident smirk, volumetric crimson lighting, cel shading",
            negative_prompt="worst quality, low quality, blurry, deformed face, bad eyes",
            art_style="manga_color",
            width=512,
            height=768,
            seed=20261131,
            steps=10,
        )
        res2 = await adapter.generate_panel_art(req2)
        shutil.copyfile(res2.image_path, p2_path)
        print(f"Panel 2 ready: {p2_path}")

    # Panel 3: Kaelen (The Cursed Blood Knight / Hắc Kỵ Sĩ)
    p3_path = panels_dir / "p3_kaelen_knight.png"
    if not p3_path.exists():
        req3 = PanelArtRequest(
            panel_id="kaelen_knight",
            prompt="masterpiece, best quality, 1boy, solo, dark fantasy knight, 3/4 battle stance, black hair, glowing amber eyes, wearing dark steel plate armor with glowing red magic runes, tattered cape, holding heavy broadsword with both hands, crimson aura slash, dynamic fighting pose, gritty battle atmosphere, cel shading",
            negative_prompt="worst quality, low quality, blurry, deformed hands, bad anatomy",
            art_style="manga_color",
            width=512,
            height=768,
            seed=20261132,
            steps=10,
        )
        res3 = await adapter.generate_panel_art(req3)
        shutil.copyfile(res3.image_path, p3_path)
        print(f"Panel 3 ready: {p3_path}")

    # Composition
    page_w = 1200
    page_h = 1750

    # Panel 1: Establishing Narration
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

    # Panel 2: Blood Knight Action Stance (Bottom-Left)
    p2_bubbles = [
        SpeechBubble(
            text="DÙ THÂN XÁC NÀY CÓ HÓA THÀNH QUỶ DỮ... THANH KIẾM NÀY VẪN SẼ KHÔNG PHẢN BỘI LỜI THỀ!",
            bubble_type=BubbleType.SHOUT,
            x=0.76,
            y=0.14,
            width=0.42,
            height=0.20,
            font_size=20,
            tail_x=0.60,
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
            text_color="#FF3333",
            stroke_color="#000000",
            stroke_width=8,
            rotation=-12.0,
            reading_order=2,
            speaker="SFX",
        ),
    ]

    # Panel 3: Vampire Sovereign Carmilla (Bottom-Right)
    p3_bubbles = [
        SpeechBubble(
            text="Thật ngoan cường làm sao... Nhưng dòng máu trong tim ngươi giờ đây đã thuộc về ta, hỡi Kỵ sĩ của ta!",
            bubble_type=BubbleType.REGULAR,
            x=0.50,
            y=0.08,
            width=0.50,
            height=0.14,
            tail_x=0.50,
            tail_y=0.17,
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
            PanelConfig(image_path=str(p3_path), bubbles=p2_bubbles, border_width=3),
            PanelConfig(image_path=str(p2_path), bubbles=p3_bubbles, border_width=3),
        ],
    )

    composer = MangaComposer()
    print("Composing Blood Princess & Knight Manga Page...")
    composed_page = composer.compose_page(page_cfg)

    out_file = data_dir / "blood_princess_and_knight_showcase.png"
    composed_page.save(out_file, "PNG")
    print(f"Saved showcase page to: {out_file}")

    art_dest = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394\blood_princess_and_knight_showcase.png")
    shutil.copyfile(out_file, art_dest)
    print(f"Copied to artifact directory: {art_dest}")


if __name__ == "__main__":
    asyncio.run(generate_and_compose_blood_princess_showcase())
