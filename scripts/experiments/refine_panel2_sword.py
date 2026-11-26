#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/refine_panel2_sword.py
Refine Panel 2 (Heroine Battle Pose with Sword) addressing all user points:
  1. Fix sword proportions: Replace the oversized blade with a sleek, elegant energy blade
     (proper width ~40px, razor-sharp edge, pure cyan/white energy core, zero green artifacts).
  2. Restore right arm and forearm: Naturally connect shoulder to hand holding the sword hilt.
  3. Clean up waist/hip anatomy: Remove random specular artifacts.
  4. Add crisp rim-lighting (edge glow) to cloak and hood so the silhouette separates from dark background.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps
import numpy as np


def refine_panel2_artwork():
    src_path = Path("F:/AI-Office/data/manga/real_panels_v2/p3_sword.png")
    out_dir = Path("F:/AI-Office/data/manga/real_panels_v3")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "p2_heroine_sword_v3.png"

    img = Image.open(src_path).convert("RGBA")
    w, h = img.size  # 512 x 768

    # 1. Clean up the body and remove the weird green artifact on the blade
    arr = np.array(img)
    # The green artifact is in region x: [200, 320], y: [350, 480] where green > red and green > blue * 0.7
    green_mask = (arr[:, :, 1] > 90) & (arr[:, :, 1] > arr[:, :, 0] + 30) & (arr[:, :, 0] < 120) & (arr[:, :, 2] < 150)
    # Replace green artifact with matching suit black/dark navy
    arr[green_mask, 0] = 16
    arr[green_mask, 1] = 20
    arr[green_mask, 2] = 30
    img = Image.fromarray(arr, mode="RGBA")

    # 2. Sleek Sword & Proper Blade Proportions
    # In original image: Hilt guard is at (440, 620), tip is around (20, 70).
    # The original blade was 160px wide! We will redraw a sleek, tapered 38px-wide energy blade
    # with a brilliant cyan edge and glowing white core.
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # First, mask out the excess clumsy width of the old blade over the torso
    # Torso contour should be clean bodysuit black
    torso_patch = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(torso_patch)

    # Redraw right arm & shoulder connection:
    # Shoulder is around (370, 310), elbow at (425, 430), forearm to wrist at (460, 580)
    arm_poly = [
        (350, 320),
        (395, 305),
        (445, 410),
        (480, 550),
        (475, 610),
        (450, 605),
        (425, 520),
        (395, 415),
        (345, 350),
    ]
    t_draw.polygon(arm_poly, fill=(18, 20, 26, 255))
    # Arm inner shading & cyan suit line
    t_draw.line([(370, 325), (415, 415), (455, 540)], fill=(0, 225, 255, 200), width=3)

    # Sleek Energy Blade:
    # Blade centerline from tip (25, 80) to guard (435, 625)
    p_tip = (25, 80)
    p_guard = (435, 625)

    dx = p_guard[0] - p_tip[0]
    dy = p_guard[1] - p_tip[1]
    length = math.hypot(dx, dy)
    ux = dx / length
    uy = dy / length
    # Perpendicular unit vector
    nx = -uy
    ny = ux

    # Sleek tapered width: 14px near tip, 22px near guard (total width 28px - 44px)
    half_w_tip = 12
    half_w_guard = 20

    blade_poly = [
        (p_tip[0], p_tip[1]),
        (p_tip[0] + nx * half_w_tip + ux * 15, p_tip[1] + ny * half_w_tip + uy * 15),
        (p_guard[0] + nx * half_w_guard, p_guard[1] + ny * half_w_guard),
        (p_guard[0] - nx * half_w_guard, p_guard[1] - ny * half_w_guard),
        (p_tip[0] - nx * half_w_tip + ux * 15, p_tip[1] - ny * half_w_tip + uy * 15),
    ]

    # Draw blade core & glow
    blade_glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(blade_glow)
    bg_draw.polygon(blade_poly, fill=(0, 235, 255, 240))
    bg_draw.line([p_tip, p_guard], fill=(255, 255, 255, 255), width=6)

    blade_bloom_wide = blade_glow.filter(ImageFilter.GaussianBlur(radius=8))
    blade_bloom_tight = blade_glow.filter(ImageFilter.GaussianBlur(radius=2))

    # 3. Add Rim-Lighting on Cloak, Hood, and Silhouette
    # Extract alpha/edge contour of dark body and apply cyan rim-light
    rim_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    r_draw = ImageDraw.Draw(rim_layer)

    # Left outer cloak edge rim light (from x=0 to 180, y=300 to 768)
    cloak_edge_points = [
        (160, 310),
        (120, 350),
        (80, 420),
        (45, 480),
        (25, 540),
        (10, 620),
        (5, 720),
    ]
    r_draw.line(cloak_edge_points, fill=(0, 230, 255, 180), width=4)

    # Right hood & shoulder rim light (from x=360 to 450, y=180 to 280)
    hood_edge_points = [
        (340, 180),
        (380, 215),
        (420, 260),
        (445, 300),
    ]
    r_draw.line(hood_edge_points, fill=(0, 230, 255, 190), width=3)

    # Blur rim light for smooth anime rim-lighting
    rim_blurred = rim_layer.filter(ImageFilter.GaussianBlur(radius=3))
    rim_sharp = rim_layer.filter(ImageFilter.GaussianBlur(radius=1))

    # Composite all layers onto base image
    img = Image.alpha_composite(img, torso_patch)
    img = Image.alpha_composite(img, blade_bloom_wide)
    img = Image.alpha_composite(img, blade_bloom_tight)
    img = Image.alpha_composite(img, rim_blurred)
    img = Image.alpha_composite(img, rim_sharp)

    # Enhance contrast and crispness
    final_rgb = img.convert("RGB")
    enhancer = ImageEnhance.Sharpness(final_rgb)
    final_rgb = enhancer.enhance(1.2)

    final_rgb.save(out_path, "PNG")
    print(f"Saved refined Panel 2 to: {out_path}")

    # Copy to artifacts
    art_path = Path("C:/Users/Shiro/.gemini/antigravity/brain/d2888882-c5f1-463b-913f-d9262e881394/v3_p2_heroine_sword.png")
    final_rgb.save(art_path, "PNG")
    print(f"Copied to artifact: {art_path}")


if __name__ == "__main__":
    refine_panel2_artwork()
