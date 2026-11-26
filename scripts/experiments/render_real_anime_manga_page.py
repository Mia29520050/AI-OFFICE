#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_real_anime_manga_page.py
Generate authentic AI diffusion anime panels using Anima-Turbo GGUF via ComfyAdapter,
and composite them into a complete Manga Page using MangaComposer and SmartBubbleLayout.
"""

import asyncio
import os
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
from app.smart_bubble_layout import optimize_speech_bubbles


async def main():
    print("===================================================================")
    print(" [1/3] Initializing ComfyAdapter & Checking Model Availability...")
    print("===================================================================")
    adapter = ComfyAdapter()
    stats = await adapter.get_system_stats()
    print(f"  ComfyUI Online: {stats.is_online}")
    print(f"  Active Checkpoint / Diffusion Model: {stats.active_checkpoint}")
    print(f"  VRAM Free: {stats.vram_free_mb} MB")

    data_dir = ROOT / "data" / "manga"
    data_dir.mkdir(parents=True, exist_ok=True)
    panels_dir = data_dir / "real_panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    # Panel 1: Establishing Shot / Background (Tokyo Akihabara Night Street)
    p1_target = panels_dir / "panel_01_tokyo_night.png"
    if not p1_target.exists():
        print("  Generating Panel 1: Tokyo Night Scenery via Anima Turbo...")
        req1 = PanelArtRequest(
            panel_id="panel_01_tokyo_night",
            prompt="masterpiece, best quality, scenery, tokyo night street, akihabara, neon signs, cyberpunk city, rainy reflections on asphalt, anime aesthetic, glowing windows, cinematic lighting, wide shot",
            negative_prompt="worst quality, low quality, blurry, deformed, text, watermark",
            art_style="manga_color",
            width=768,
            height=512,
            seed=20261124,
            steps=10,
        )
        res1 = await adapter.generate_panel_art(req1)
        print(f"  ✓ Panel 1 Generated ({res1.mode}) in {res1.duration_seconds}s: {res1.image_path}")
        shutil.copyfile(res1.image_path, p1_target)
    else:
        print(f"  ✓ Panel 1 already exists: {p1_target}")

    # Panel 2: Character Close-up Emotion (Silver-haired Heroine)
    p2_target = panels_dir / "panel_02_heroine_emotion.png"
    if not p2_target.exists():
        print("  Generating Panel 2: Heroine Emotion Close-up via Anima Turbo...")
        req2 = PanelArtRequest(
            panel_id="panel_02_heroine_emotion",
            prompt="masterpiece, best quality, 1girl, solo, anime girl, silver short hair, vivid crimson red eyes, intense determined gaze, serious expression, glowing red pupils, dark starry night sky, close up face portrait",
            negative_prompt="worst quality, low quality, blurry, deformed, bad eyes, bad anatomy",
            art_style="manga_color",
            width=512,
            height=768,
            seed=20261125,
            steps=10,
        )
        res2 = await adapter.generate_panel_art(req2)
        print(f"  ✓ Panel 2 Generated ({res2.mode}) in {res2.duration_seconds}s: {res2.image_path}")
        shutil.copyfile(res2.image_path, p2_target)
    else:
        print(f"  ✓ Panel 2 already exists: {p2_target}")

    # Panel 3: Action Climax (Heroine wielding Crystal Broadsword)
    p3_target = panels_dir / "panel_03_heroine_action.png"
    # Check if we already have the previously generated panel
    existing_p3 = ROOT / "data" / "manga" / "panels" / "real_panel_01" / "panel_real_panel_01_1795505143_12345.png"
    if existing_p3.exists() and not p3_target.exists():
        shutil.copyfile(existing_p3, p3_target)
        print(f"  ✓ Panel 3 Reused from Diffusion Cache: {p3_target}")
    elif not p3_target.exists():
        print("  Generating Panel 3: Heroine Sword Action Climax via Anima Turbo...")
        req3 = PanelArtRequest(
            panel_id="panel_03_heroine_action",
            prompt="masterpiece, best quality, 1girl, solo, anime girl, silver hair, red eyes, holding sword, floating in starry night sky, magical sparkles, dramatic lighting",
            negative_prompt="worst quality, low quality, blurry, deformed, bad hands",
            art_style="manga_color",
            width=512,
            height=768,
            seed=12345,
            steps=10,
        )
        res3 = await adapter.generate_panel_art(req3)
        print(f"  ✓ Panel 3 Generated ({res3.mode}) in {res3.duration_seconds}s: {res3.image_path}")
        shutil.copyfile(res3.image_path, p3_target)
    else:
        print(f"  ✓ Panel 3 already exists: {p3_target}")

    print("===================================================================")
    print(" [2/3] Typesetting Speech Bubbles with Smart Layout & Face Avoidance...")
    print("===================================================================")

    # Panel 1: Establishing Shot (1120 x 480)
    p1_bubbles = optimize_speech_bubbles([
        SpeechBubble(
            text="Tokyo, 02:00 AM... Khu phố Akihabara chìm trong màn mưa neon tĩnh lặng.",
            bubble_type=BubbleType.CAPTION,
            x=0.22, y=0.18,
            reading_order=1,
        ),
        SpeechBubble(
            text="Tín hiệu dị thường phát ra ngay phía trước... Không thể sai được!",
            bubble_type=BubbleType.REGULAR,
            x=0.78, y=0.22,
            tail_x=0.65, tail_y=0.55,
            reading_order=2,
        )
    ], panel_w=1120, panel_h=480)

    # Panel 2: Emotion Close-Up (Right Column, 540 x 620)
    # Character face is centered around [0.35, 0.30] - [0.65, 0.70]
    p2_bubbles = optimize_speech_bubbles([
        SpeechBubble(
            text="Ngươi định trốn ở góc tối đó đến bao giờ, bóng ma hư vô?!",
            bubble_type=BubbleType.REGULAR,
            x=0.76, y=0.18,
            tail_x=0.58, tail_y=0.42,
            reading_order=1,
        ),
        SpeechBubble(
            text="(Lần này... mình nhất quyết sẽ không để ngươi chạy thoát!)",
            bubble_type=BubbleType.THOUGHT,
            x=0.24, y=0.82,
            tail_x=0.45, tail_y=0.68,
            reading_order=2,
        )
    ], panel_w=540, panel_h=620)

    # Panel 3: Action Climax (Left Column, 540 x 620)
    p3_bubbles = optimize_speech_bubbles([
        SpeechBubble(
            text="KHẮC TINH TINH TÚ... KHAI MỞ! ⚔️✨",
            bubble_type=BubbleType.SHOUT,
            x=0.72, y=0.18,
            tail_x=0.52, tail_y=0.46,
            reading_order=1,
        ),
        SpeechBubble(
            text="KEEE-ENG! ⚡",
            bubble_type=BubbleType.SHOUT,
            x=0.26, y=0.84,
            tail_x=0.38, tail_y=0.70,
            reading_order=2,
        )
    ], panel_w=540, panel_h=620)

    print("===================================================================")
    print(" [3/3] Assembling Full Manga Page with MangaComposer...")
    print("===================================================================")
    page_w = 1200
    page_h = 1700

    page_cfg = PageConfig(
        width=page_w,
        height=page_h,
        layout_type=PanelLayoutType.TOP1_BOTTOM2,
        margin_x=40,
        margin_y=40,
        gutter_x=25,
        gutter_y=25,
        panels=[
            PanelConfig(image_path=str(p1_target), bubbles=p1_bubbles, border_width=3),
            PanelConfig(image_path=str(p2_target), bubbles=p2_bubbles, border_width=3),
            PanelConfig(image_path=str(p3_target), bubbles=p3_bubbles, border_width=3),
        ]
    )

    composer = MangaComposer(default_font_path=ROOT / "app" / "ui" / "assets" / "Inter-Variable.ttf")
    final_page = composer.compose_page(page_cfg)

    output_path = data_dir / "final_anime_manga_showcase.png"
    final_page.save(output_path, "PNG")
    print(f"  ✓ Full Manga Page successfully saved: {output_path} ({page_w}x{page_h})")

    # Also copy to artifact directory for display
    artifact_dir = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394")
    artifact_dest = artifact_dir / "final_anime_manga_showcase.png"
    shutil.copyfile(output_path, artifact_dest)
    print(f"  ✓ Copied to artifacts directory: {artifact_dest}")
    print("===================================================================")


if __name__ == "__main__":
    asyncio.run(main())
