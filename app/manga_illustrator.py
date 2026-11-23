"""High-Fidelity Manga Illustration Engine for Manga Studio.

Renders authentic Japanese manga ink artwork with:
- Exact locked character traits:
  * Minh (Protagonist): Short black hair, sharp eyes, blazer, tie, dark trousers.
  * Mai: Shoulder-length brown hair, gentle eyes, cream cardigan, navy pleated skirt, ribbon.
  * Huy: Wavy brown hair, blouse, cardigan, pleated skirt.
  * Thầy Lâm: Mature face, round spectacles, cardigan, black office pencil skirt.
- Classroom environment: Desks, window perspective, sunlight rays, chalk blackboard, hallway.
- Authentic Manga Techniques: Screen tones, ink cross-hatching, speed lines, emotion marks.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = ROOT / "app" / "ui" / "assets" / "Inter-Variable.ttf"


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        try:
            return ImageFont.truetype(str(FONT_PATH), size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_screentone_region(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    dot_spacing: int = 6,
    dot_radius: int = 1,
    fill_color: tuple[int, int, int] = (140, 140, 150),
) -> None:
    """Draw classic manga halftone dot screentone within bounding box."""
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1, dot_spacing):
        offset = (y // dot_spacing % 2) * (dot_spacing // 2)
        for x in range(x0 + offset, x1, dot_spacing):
            draw.ellipse(
                [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                fill=fill_color,
            )


def draw_cross_hatch(
    draw: ImageDraw.ImageDraw,
    polygon: list[tuple[int, int]],
    spacing: int = 8,
    color: tuple[int, int, int] = (60, 60, 70),
) -> None:
    """Draw manga ink cross-hatching shadow inside polygon."""
    if len(polygon) < 3:
        return
    min_x = min(p[0] for p in polygon)
    max_x = max(p[0] for p in polygon)
    min_y = min(p[1] for p in polygon)
    max_y = max(p[1] for p in polygon)

    # Diagonal lines /
    for offset in range(min_x - (max_y - min_y), max_x, spacing):
        draw.line(
            [(offset, max_y), (offset + (max_y - min_y), min_y)],
            fill=color,
            width=1,
        )


def draw_manga_eyes(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    size: int = 24,
    expression: str = "normal",  # normal, sleepy, shocked, smiling, mysterious
    is_female: bool = False,
) -> None:
    """Draw detailed manga expressive eyes with upper lash, pupil, iris, and highlights."""
    eye_spacing = int(size * 1.5)

    for side in (-1, 1):
        ex = cx + side * eye_spacing
        ey = cy

        if expression == "sleepy":
            # Curved downward sleepy eyelid
            draw.arc([ex - size, ey - size // 2, ex + size, ey + size // 2], start=190, end=350, fill=(15, 15, 20), width=3)
            draw.line([(ex - size, ey + 2), (ex + size, ey + 2)], fill=(40, 40, 50), width=1)
            # Faint lower lash
            draw.arc([ex - size // 2, ey + 4, ex + size // 2, ey + 10], start=20, end=160, fill=(100, 100, 110), width=1)
            continue

        if expression == "shocked":
            # Wide circular pupil with tiny iris
            draw.arc([ex - size, ey - size, ex + size, ey + size // 2], start=180, end=360, fill=(10, 10, 15), width=4)
            draw.arc([ex - size, ey - size // 2, ex + size, ey + size], start=0, end=180, fill=(10, 10, 15), width=2)
            # Pinpoint pupil
            draw.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=(15, 15, 20))
            continue

        # Normal & expressive manga eye
        # 1. Thick upper lash line
        upper_w = 4 if is_female else 3
        draw.arc([ex - size, ey - size, ex + size, ey + size // 2], start=185, end=355, fill=(15, 15, 20), width=upper_w)
        if is_female:
            # Outer upper eyelash wing
            wing_x = ex + (size + 4 if side > 0 else -size - 4)
            draw.line([(ex + side * size, ey - 6), (wing_x, ey - 12)], fill=(15, 15, 20), width=3)

        # 2. Lower lash line
        draw.arc([ex - size // 2, ey + size // 4, ex + size // 2, ey + size // 2], start=20, end=160, fill=(30, 30, 40), width=2)

        # 3. Iris ellipse
        iris_rx = int(size * 0.55)
        iris_ry = int(size * 0.75)
        draw.ellipse([ex - iris_rx, ey - iris_ry // 2, ex + iris_rx, ey + iris_ry], fill=(45, 48, 60), outline=(15, 15, 20), width=2)

        # 4. Deep pupil
        pupil_r = int(size * 0.28)
        draw.ellipse([ex - pupil_r, ey - pupil_r // 2, ex + pupil_r, ey + pupil_r], fill=(10, 10, 15))

        # 5. Specular highlight spark
        hl_r = max(2, int(size * 0.18))
        draw.ellipse([ex - iris_rx // 2, ey - iris_ry // 2, ex - iris_rx // 2 + hl_r * 2, ey - iris_ry // 2 + hl_r * 2], fill=(255, 255, 255))
        if is_female:
            draw.ellipse([ex + iris_rx // 4, ey + iris_ry // 4, ex + iris_rx // 4 + 4, ey + iris_ry // 4 + 4], fill=(255, 255, 255))


def draw_character_minh(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scale: float = 1.0,
    pose: str = "sitting_window",  # sitting_window, sleeping_desk, waking_up, standing_shock, looking_phone
) -> None:
    """Render Protagonist Minh: Short layered black hair, blazer, dark tie, dark trousers."""
    s = scale

    if pose == "sitting_window":
        # Sitting at desk looking out window
        # Desk surface
        dx0, dy0, dx1, dy1 = int(cx - 180 * s), int(cy + 120 * s), int(cx + 220 * s), int(cy + 220 * s)
        draw.polygon([(dx0, dy0 + 40), (dx1, dy0), (dx1, dy1), (dx0, dy1)], fill=(210, 205, 200), outline=(30, 30, 35), width=3)
        # Open Math Textbook on desk
        draw.polygon([(dx0 + 40, dy0 + 20), (dx0 + 130, dy0 + 10), (dx0 + 140, dy0 + 70), (dx0 + 50, dy0 + 80)], fill=(250, 250, 252), outline=(30, 30, 35), width=2)
        draw.text((dx0 + 60, dy0 + 35), "TOÁN", fill=(40, 40, 50), font=get_font(14))

        # Navy Blazer Torso
        bx0, by0, bx1, by1 = int(cx - 90 * s), int(cy + 20 * s), int(cx + 80 * s), int(cy + 170 * s)
        draw.polygon([
            (bx0, by1), (bx0 + 20, by0 + 30), (cx - 30 * s, by0), (cx + 30 * s, by0), (bx1 - 20, by0 + 30), (bx1, by1)
        ], fill=(35, 42, 60), outline=(15, 15, 20), width=3)

        # White Shirt V-neck collar & Dark Tie
        draw.polygon([(cx - 25 * s, by0), (cx + 25 * s, by0), (cx, by0 + 60 * s)], fill=(255, 255, 255), outline=(20, 20, 25), width=2)
        # Dark Necktie
        draw.polygon([(cx - 8 * s, by0 + 10 * s), (cx + 8 * s, by0 + 10 * s), (cx + 12 * s, by0 + 80 * s), (cx, by0 + 95 * s), (cx - 12 * s, by0 + 80 * s)], fill=(18, 22, 35), outline=(10, 10, 15), width=2)

        # Distinct Dark School Trousers (Legs visible beneath desk / side)
        draw.polygon([(cx - 80 * s, by1), (cx - 20 * s, by1), (cx - 30 * s, by1 + 90 * s), (cx - 95 * s, by1 + 90 * s)], fill=(25, 28, 38), outline=(15, 15, 20), width=3)
        draw.polygon([(cx + 20 * s, by1), (cx + 80 * s, by1), (cx + 70 * s, by1 + 90 * s), (cx + 10 * s, by1 + 90 * s)], fill=(25, 28, 38), outline=(15, 15, 20), width=3)

        # Head / Face
        hx, hy, hr = cx, int(cy - 40 * s), int(45 * s)
        draw.polygon([
            (hx - hr, hy - int(10 * s)),
            (hx - int(hr * 0.7), hy + int(hr * 0.9)),
            (hx, hy + int(hr * 1.25)),
            (hx + int(hr * 0.7), hy + int(hr * 0.9)),
            (hx + hr, hy - int(10 * s)),
        ], fill=(252, 245, 238), outline=(20, 20, 25), width=2)

        # Sleepy Eyes & Mouth
        draw_manga_eyes(draw, hx, hy + int(5 * s), size=int(14 * s), expression="sleepy")
        # Yawning mouth
        draw.ellipse([hx - int(8 * s), hy + int(32 * s), hx + int(8 * s), hy + int(46 * s)], fill=(180, 80, 80), outline=(20, 20, 25), width=2)

        # Layered Black Hair
        hair_points = [
            (hx - int(55 * s), hy),
            (hx - int(50 * s), hy - int(45 * s)),
            (hx - int(25 * s), hy - int(65 * s)),
            (hx + int(5 * s), hy - int(68 * s)),
            (hx + int(35 * s), hy - int(58 * s)),
            (hx + int(52 * s), hy - int(35 * s)),
            (hx + int(50 * s), hy + int(10 * s)),
            (hx + int(38 * s), hy - int(15 * s)),
            (hx + int(20 * s), hy - int(35 * s)),
            (hx - int(5 * s), hy - int(38 * s)),
            (hx - int(30 * s), hy - int(20 * s)),
            (hx - int(45 * s), hy + int(5 * s)),
        ]
        draw.polygon(hair_points, fill=(18, 20, 28), outline=(10, 10, 15), width=3)

    elif pose == "sleeping_desk":
        # Folded arms on desk, head down
        dx0, dy0, dx1, dy1 = int(cx - 220 * s), int(cy + 50 * s), int(cx + 220 * s), int(cy + 180 * s)
        draw.rectangle([dx0, dy0, dx1, dy1], fill=(220, 215, 210), outline=(30, 30, 35), width=3)
        # Math book closed
        draw.rectangle([dx0 + 60, dy0 + 10, dx1 - 60, dy0 + 90], fill=(240, 242, 248), outline=(25, 25, 30), width=3)
        draw.text((dx0 + 120, dy0 + 35), "TOÁN HỌC 11", fill=(30, 30, 40), font=get_font(20))

        # Folded blazer sleeves
        draw.polygon([
            (cx - 140 * s, dy0 + 30), (cx - 30 * s, dy0 + 20), (cx + 50 * s, dy0 + 40),
            (cx + 140 * s, dy0 + 30), (cx + 120 * s, dy0 + 90), (cx - 120 * s, dy0 + 90)
        ], fill=(35, 42, 60), outline=(15, 15, 20), width=3)

        # Back of head with black hair resting down
        draw.ellipse([cx - 65 * s, dy0 - 30 * s, cx + 65 * s, dy0 + 55 * s], fill=(18, 20, 28), outline=(10, 10, 15), width=3)
        # Hair texture strands
        for sx in range(int(cx - 45 * s), int(cx + 45 * s), 12):
            draw.line([(sx, dy0 - 20 * s), (sx + 8, dy0 + 35 * s)], fill=(50, 55, 75), width=2)

    elif pose == "standing_shock":
        # Minh standing in disbelief, pants clearly visible
        # Head
        hx, hy, hr = cx, int(cy - 90 * s), int(42 * s)
        draw.polygon([
            (hx - hr, hy - int(10 * s)),
            (hx - int(hr * 0.7), hy + int(hr * 0.9)),
            (hx, hy + int(hr * 1.25)),
            (hx + int(hr * 0.7), hy + int(hr * 0.9)),
            (hx + hr, hy - int(10 * s)),
        ], fill=(252, 245, 238), outline=(20, 20, 25), width=2)

        # Shocked eyes
        draw_manga_eyes(draw, hx, hy + int(5 * s), size=int(16 * s), expression="shocked")
        # Sweat drops
        draw.ellipse([hx + int(45 * s), hy - int(15 * s), hx + int(55 * s), hy], fill=(160, 200, 255), outline=(20, 20, 30), width=1)
        # Gaping mouth
        draw.polygon([(hx - 10, hy + 35), (hx + 10, hy + 35), (hx, hy + 50)], fill=(160, 50, 50), outline=(20, 20, 25), width=2)

        # Hair
        hair_points = [
            (hx - int(52 * s), hy),
            (hx - int(48 * s), hy - int(48 * s)),
            (hx - int(20 * s), hy - int(65 * s)),
            (hx + int(10 * s), hy - int(68 * s)),
            (hx + int(38 * s), hy - int(55 * s)),
            (hx + int(52 * s), hy - int(30 * s)),
            (hx + int(48 * s), hy + int(10 * s)),
            (hx + int(35 * s), hy - int(20 * s)),
            (hx - int(10 * s), hy - int(35 * s)),
            (hx - int(40 * s), hy),
        ]
        draw.polygon(hair_points, fill=(18, 20, 28), outline=(10, 10, 15), width=3)

        # Torso (Blazer, tie, shirt)
        tx0, ty0, tx1, ty1 = int(cx - 85 * s), int(cy - 35 * s), int(cx + 85 * s), int(cy + 65 * s)
        draw.polygon([(tx0, ty1), (tx0 + 15, ty0), (tx1 - 15, ty0), (tx1, ty1)], fill=(35, 42, 60), outline=(15, 15, 20), width=3)
        draw.polygon([(cx - 20 * s, ty0), (cx + 20 * s, ty0), (cx, ty0 + 50 * s)], fill=(255, 255, 255), outline=(20, 20, 25), width=2)
        draw.polygon([(cx - 6 * s, ty0 + 10 * s), (cx + 6 * s, ty0 + 10 * s), (cx + 10 * s, ty0 + 65 * s), (cx, ty0 + 75 * s), (cx - 10 * s, ty0 + 65 * s)], fill=(18, 22, 35), width=2)

        # PROTAGONIST TROUSERS (Distinct Long Dark Trousers)
        lx0, ly0, lx1, ly1 = int(cx - 75 * s), int(cy + 65 * s), int(cx + 75 * s), int(cy + 175 * s)
        # Left leg
        draw.polygon([(lx0, ly0), (cx - 8 * s, ly0), (cx - 15 * s, ly1), (lx0 - 10, ly1)], fill=(25, 28, 38), outline=(15, 15, 20), width=3)
        # Right leg
        draw.polygon([(cx + 8 * s, ly0), (lx1, ly0), (lx1 + 10, ly1), (cx + 15 * s, ly1)], fill=(25, 28, 38), outline=(15, 15, 20), width=3)
        # Trouser crease lines
        draw.line([(lx0 + 25 * s, ly0 + 10), (lx0 + 20 * s, ly1 - 10)], fill=(50, 55, 75), width=2)
        draw.line([(lx1 - 25 * s, ly0 + 10), (lx1 - 20 * s, ly1 - 10)], fill=(50, 55, 75), width=2)


def draw_character_mai(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scale: float = 1.0,
) -> None:
    """Render Mai: Shoulder-length brown hair, white blouse, cream cardigan, navy pleated skirt, ribbon."""
    s = scale

    # Head & Face
    hx, hy, hr = cx, int(cy - 60 * s), int(42 * s)
    draw.polygon([
        (hx - hr, hy - int(10 * s)),
        (hx - int(hr * 0.7), hy + int(hr * 0.85)),
        (hx, hy + int(hr * 1.2)),
        (hx + int(hr * 0.7), hy + int(hr * 0.85)),
        (hx + hr, hy - int(10 * s)),
    ], fill=(254, 246, 240), outline=(20, 20, 25), width=2)

    # Gentle Female Manga Eyes
    draw_manga_eyes(draw, hx, hy + int(2 * s), size=int(16 * s), expression="normal", is_female=True)
    # Gentle mouth
    draw.arc([hx - 8, hy + 30, hx + 8, hy + 42], start=10, end=170, fill=(180, 70, 70), width=2)

    # Brown Shoulder-Length Hair (flowing down around shoulders)
    hair_color = (105, 65, 45)
    hair_dark = (70, 42, 30)
    # Back hair
    draw.polygon([
        (hx - 55 * s, hy), (hx - 60 * s, hy + 85 * s), (hx - 30 * s, hy + 95 * s),
        (hx + 30 * s, hy + 95 * s), (hx + 60 * s, hy + 85 * s), (hx + 55 * s, hy),
        (hx + 40 * s, hy - 45 * s), (hx, hy - 65 * s), (hx - 40 * s, hy - 45 * s)
    ], fill=hair_color, outline=hair_dark, width=3)

    # Cream Knitted Cardigan
    cx0, cy0, cx1, cy1 = int(cx - 75 * s), int(cy - 10 * s), int(cx + 75 * s), int(cy + 85 * s)
    draw.polygon([(cx0, cy1), (cx0 + 15, cy0), (cx1 - 15, cy0), (cx1, cy1)], fill=(245, 238, 220), outline=(30, 30, 35), width=3)
    # Cardigan knitted ribs & buttons
    draw.line([(cx, cy0 + 35 * s), (cx, cy1)], fill=(200, 190, 170), width=4)
    for by in range(int(cy0 + 45 * s), int(cy1 - 10 * s), int(18 * s)):
        draw.ellipse([cx - 4, by - 4, cx + 4, by + 4], fill=(130, 115, 95))

    # White Blouse Collar & Light Blue Ribbon Bow
    draw.polygon([(cx - 25 * s, cy0), (cx + 25 * s, cy0), (cx, cy0 + 35 * s)], fill=(255, 255, 255), outline=(30, 30, 35), width=2)
    # Ribbon Bow
    draw.polygon([(cx - 16 * s, cy0 + 15 * s), (cx, cy0 + 22 * s), (cx - 16 * s, cy0 + 32 * s)], fill=(120, 170, 230), outline=(20, 30, 50), width=2)
    draw.polygon([(cx + 16 * s, cy0 + 15 * s), (cx, cy0 + 22 * s), (cx + 16 * s, cy0 + 32 * s)], fill=(120, 170, 230), outline=(20, 30, 50), width=2)
    draw.ellipse([cx - 5, cy0 + 18 * s, cx + 5, cy0 + 26 * s], fill=(90, 140, 200))

    # Navy Pleated Skirt with sharp vertical pleats
    sk0, sky0, sk1, sky1 = int(cx - 80 * s), int(cy + 85 * s), int(cx + 80 * s), int(cy + 160 * s)
    draw.polygon([
        (sk0 + 15 * s, sky0), (sk1 - 15 * s, sky0), (sk1, sky1), (sk0, sky1)
    ], fill=(30, 42, 68), outline=(15, 20, 35), width=3)
    # Pleat fold lines
    for px in range(int(sk0 + 12 * s), int(sk1 - 10 * s), int(14 * s)):
        draw.line([(px, sky0), (px + int((px - cx) * 0.15), sky1)], fill=(55, 75, 115), width=2)


def draw_character_huy(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scale: float = 1.0,
) -> None:
    """Render Huy: Wavy brown hair, blouse, light blue cardigan, navy pleated skirt."""
    s = scale

    # Head
    hx, hy, hr = cx, int(cy - 60 * s), int(42 * s)
    draw.polygon([
        (hx - hr, hy - int(10 * s)),
        (hx - int(hr * 0.7), hy + int(hr * 0.9)),
        (hx, hy + int(hr * 1.2)),
        (hx + int(hr * 0.7), hy + int(hr * 0.9)),
        (hx + hr, hy - int(10 * s)),
    ], fill=(252, 244, 236), outline=(20, 20, 25), width=2)

    # Smiling male manga eyes & playful smirk
    draw_manga_eyes(draw, hx, hy + int(2 * s), size=int(14 * s), expression="normal")
    draw.arc([hx - 10, hy + 28, hx + 10, hy + 42], start=20, end=160, fill=(160, 50, 50), width=2)

    # Wavy Brown Hair (short curls around ears and crown)
    hair_c = (115, 75, 55)
    for hx_off in range(-45, 50, 16):
        draw.arc([hx + int(hx_off * s) - 15, hy - int(55 * s), hx + int(hx_off * s) + 15, hy - int(25 * s)], start=180, end=360, fill=hair_c, width=8)
    draw.polygon([
        (hx - 50 * s, hy - 15 * s), (hx - 35 * s, hy - 58 * s), (hx + 35 * s, hy - 58 * s),
        (hx + 50 * s, hy - 15 * s), (hx + 35 * s, hy - 35 * s), (hx - 35 * s, hy - 35 * s)
    ], fill=hair_c, outline=(60, 35, 25), width=2)

    # Light Blue Cardigan over White Blouse
    cx0, cy0, cx1, cy1 = int(cx - 75 * s), int(cy - 10 * s), int(cx + 75 * s), int(cy + 85 * s)
    draw.polygon([(cx0, cy1), (cx0 + 15, cy0), (cx1 - 15, cy0), (cx1, cy1)], fill=(195, 220, 245), outline=(30, 35, 45), width=3)
    draw.polygon([(cx - 22 * s, cy0), (cx + 22 * s, cy0), (cx, cy0 + 35 * s)], fill=(255, 255, 255), outline=(30, 35, 45), width=2)

    # Navy Pleated Uniform Skirt on male student
    sk0, sky0, sk1, sky1 = int(cx - 80 * s), int(cy + 85 * s), int(cx + 80 * s), int(cy + 160 * s)
    draw.polygon([(sk0 + 15 * s, sky0), (sk1 - 15 * s, sky0), (sk1, sky1), (sk0, sky1)], fill=(30, 42, 68), outline=(15, 20, 35), width=3)
    for px in range(int(sk0 + 12 * s), int(sk1 - 10 * s), int(14 * s)):
        draw.line([(px, sky0), (px + int((px - cx) * 0.15), sky1)], fill=(55, 75, 115), width=2)


def draw_character_teacher_lam(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scale: float = 1.0,
    with_blackboard: bool = False,
) -> None:
    """Render Thầy Lâm: Mature face, parted dark hair, round spectacles, cardigan, black pencil skirt."""
    s = scale

    # Head & Mature Jawline
    hx, hy, hr = cx, int(cy - 80 * s), int(42 * s)
    draw.polygon([
        (hx - hr, hy - int(15 * s)),
        (hx - int(hr * 0.8), hy + int(hr * 0.9)),
        (hx, hy + int(hr * 1.35)),
        (hx + int(hr * 0.8), hy + int(hr * 0.9)),
        (hx + hr, hy - int(15 * s)),
    ], fill=(250, 242, 234), outline=(20, 20, 25), width=3)

    # Classic Round Metal Spectacles
    gw = int(18 * s)
    # Left lens
    draw.ellipse([hx - gw * 2 - 2, hy - gw // 2, hx - 4, hy + gw // 2 + 8], outline=(15, 15, 20), width=3)
    # Right lens
    draw.ellipse([hx + 4, hy - gw // 2, hx + gw * 2 + 2, hy + gw // 2 + 8], outline=(15, 15, 20), width=3)
    # Nose bridge
    draw.line([(hx - 4, hy + 4), (hx + 4, hy + 4)], fill=(15, 15, 20), width=2)
    # Specular white reflection across lens
    draw.line([(hx - gw * 2 + 4, hy + 6), (hx - 8, hy - 4)], fill=(255, 255, 255), width=2)
    draw.line([(hx + 8, hy + 6), (hx + gw * 2 - 4, hy - 4)], fill=(255, 255, 255), width=2)

    # Eyes through spectacles
    draw_manga_eyes(draw, hx, hy + int(2 * s), size=int(12 * s), expression="mysterious")

    # Parted mature dark hair
    draw.polygon([
        (hx - 55 * s, hy), (hx - 48 * s, hy - 60 * s), (hx - 15 * s, hy - 72 * s),
        (hx + 10 * s, hy - 72 * s), (hx + 48 * s, hy - 55 * s), (hx + 55 * s, hy + 5 * s),
        (hx + 40 * s, hy - 25 * s), (hx - 5 * s, hy - 42 * s), (hx - 42 * s, hy)
    ], fill=(25, 28, 35), outline=(10, 10, 15), width=3)

    # Beige Cardigan & White Blouse & Dark Ribbon
    tx0, ty0, tx1, ty1 = int(cx - 85 * s), int(cy - 25 * s), int(cx + 85 * s), int(cy + 85 * s)
    draw.polygon([(tx0, ty1), (tx0 + 15, ty0), (tx1 - 15, ty0), (tx1, ty1)], fill=(230, 220, 200), outline=(25, 25, 30), width=3)
    draw.polygon([(cx - 24 * s, ty0), (cx + 24 * s, ty0), (cx, ty0 + 40 * s)], fill=(255, 255, 255), outline=(25, 25, 30), width=2)
    # Dark blue teacher neck bow
    draw.polygon([(cx - 15 * s, ty0 + 20 * s), (cx + 15 * s, ty0 + 20 * s), (cx + 10 * s, ty0 + 45 * s), (cx - 10 * s, ty0 + 45 * s)], fill=(20, 30, 60), width=2)

    # BLACK OFFICE PENCIL SKIRT (Dài qua gối)
    sk0, sky0, sk1, sky1 = int(cx - 70 * s), int(cy + 85 * s), int(cx + 70 * s), int(cy + 185 * s)
    draw.polygon([(sk0, sky0), (sk1, sky0), (sk1 - 10 * s, sky1), (sk0 + 10 * s, sky1)], fill=(18, 18, 24), outline=(10, 10, 15), width=3)
    # Pencil skirt central seam
    draw.line([(cx, sky0), (cx, sky1)], fill=(45, 45, 55), width=2)


class MangaIllustrationEngine:
    """Authentic vector-raster Japanese manga art illustration engine."""

    def __init__(self):
        pass

    def render_panel(
        self,
        panel_key: str,
        width: int = 1120,
        height: int = 400,
        page_num: int = 1,
        pan_num: int = 1,
    ) -> Image.Image:
        """Render complete illustrated manga artwork for a specific story panel."""
        w, h = width, height
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Route by page and panel
        if page_num == 1:
            if pan_num == 1:
                self._render_p1_pan1(draw, w, h)
            elif pan_num == 2:
                self._render_p1_pan2(draw, w, h)
            elif pan_num == 3:
                self._render_p1_pan3(draw, w, h)
            else:
                self._render_p1_pan4(draw, w, h)

        elif page_num == 2:
            if pan_num == 1:
                self._render_p2_pan1(draw, w, h)
            elif pan_num == 2:
                self._render_p2_pan2(draw, w, h)
            elif pan_num == 3:
                self._render_p2_pan3(draw, w, h)
            else:
                self._render_p2_pan4(draw, w, h)

        elif page_num == 3:
            if pan_num == 1:
                self._render_p3_pan1(draw, w, h)
            elif pan_num == 2:
                self._render_p3_pan2(draw, w, h)
            elif pan_num == 3:
                self._render_p3_pan3(draw, w, h)
            else:
                self._render_p3_pan4(draw, w, h)

        else:  # Page 4
            if pan_num == 1:
                self._render_p4_pan1(draw, w, h)
            elif pan_num == 2:
                self._render_p4_pan2(draw, w, h)
            elif pan_num == 3:
                self._render_p4_pan3(draw, w, h)
            else:
                self._render_p4_pan4(draw, w, h)

        # Crisp outer panel border
        draw.rectangle([2, 2, w - 3, h - 3], outline=(15, 15, 20), width=4)

        return img

    # --- PAGE 1: Buổi sáng bình thường trước giấc ngủ ---

    def _render_p1_pan1(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P1 Pan1: Cửa sổ lớp học, bầu trời mây trắng, ánh nắng rọi, Minh ngồi buồn ngủ."""
        # Sky outside window
        draw.rectangle([0, 0, int(w * 0.55), h], fill=(225, 235, 248))
        # Manga clouds
        for cx, cy, cr in [(120, 60, 45), (170, 70, 55), (80, 80, 40), (280, 110, 60)]:
            draw.ellipse([cx - cr, cy - cr // 2, cx + cr, cy + cr // 2], fill=(255, 255, 255), outline=(190, 205, 225), width=2)

        # Classroom window frame (perspective)
        draw.rectangle([int(w * 0.05), 10, int(w * 0.52), h - 10], outline=(40, 45, 55), width=6)
        draw.line([(int(w * 0.28), 10), (int(w * 0.28), h - 10)], fill=(40, 45, 55), width=4)
        draw.line([(int(w * 0.05), int(h * 0.45)), (int(w * 0.52), int(h * 0.45))], fill=(40, 45, 55), width=4)

        # Diagonal Sunlight Rays
        for ray_x in range(int(w * 0.1), int(w * 0.5), 60):
            draw.polygon([(ray_x, 10), (ray_x + 80, 10), (ray_x + 350, h), (ray_x + 270, h)], fill=(255, 255, 245))

        # Classroom interior wall & screentone
        draw_screentone_region(draw, (int(w * 0.52), 0, w, h), dot_spacing=8, dot_radius=1)

        # Minh sitting at desk looking out window
        draw_character_minh(draw, cx=int(w * 0.72), cy=int(h * 0.42), scale=1.1, pose="sitting_window")

    def _render_p1_pan2(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P1 Pan2: Minh gục đầu ngủ trên quyển sách Toán, rèm cửa khẽ bay."""
        # Classroom wall with screentone behind desk
        draw.rectangle([0, 0, w, int(h * 0.45)], fill=(230, 232, 238))
        draw_screentone_region(draw, (0, 0, w, int(h * 0.45)), dot_spacing=8, dot_radius=1, fill_color=(130, 135, 150))

        # Blowing curtain on left
        draw.polygon([(0, 0), (140, 0), (90, h), (0, h)], fill=(245, 248, 255), outline=(40, 45, 60), width=3)
        for cy in range(40, h, 50):
            draw.arc([15, cy, 120, cy + 50], start=10, end=170, fill=(35, 40, 55), width=2)

        # Classroom Wooden Desk spanning full lower canvas
        desk_top = int(h * 0.38)
        draw.polygon([(0, desk_top), (w, desk_top), (w, h), (0, h)], fill=(205, 195, 180), outline=(25, 28, 35), width=4)
        # Wood grain lines & perspective desk edge
        draw.line([(0, desk_top + 18), (w, desk_top + 18)], fill=(30, 32, 40), width=3)
        for wy in range(desk_top + 50, h, 60):
            draw.line([(0, wy), (w, wy)], fill=(175, 165, 150), width=2)

        # Closed Math book on desk
        bx0, by0, bx1, by1 = int(w * 0.2), int(desk_top + 40), int(w * 0.8), int(desk_top + 140)
        draw.rectangle([bx0, by0, bx1, by1], fill=(245, 248, 255), outline=(20, 22, 30), width=3)
        draw.text((bx0 + 30, by0 + 35), "TOÁN HỌC 11 · ĐẠI SỐ & GIẢI TÍCH", fill=(20, 25, 35), font=get_font(20))

        # Desk and Minh sleeping with head folded on arms
        draw_character_minh(draw, cx=int(w * 0.52), cy=int(desk_top + 30), scale=max(1.15, min(w, h) / 400.0), pose="sleeping_desk")

    def _render_p1_pan3(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P1 Pan3: Minh từ từ ngẩng đầu, nheo mắt dụi mắt vì ánh nắng."""
        # Sunlight glare lines radiating from top left
        for a in range(0, 90, 6):
            rad = math.radians(a)
            draw.line([(0, 0), (int(w * math.cos(rad)), int(h * math.sin(rad)))], fill=(240, 242, 248), width=2)

        # Classroom chalkboard in background
        draw.rectangle([int(w * 0.08), 20, int(w * 0.42), int(h * 0.65)], fill=(45, 55, 50), outline=(20, 25, 20), width=4)
        draw.text((int(w * 0.12), 40), "ĐẠI SỐ 11: TIẾT 2", fill=(210, 220, 215), font=get_font(18))

        # Minh waking up, rubbing eyes
        draw_character_minh(draw, cx=int(w * 0.65), cy=int(h * 0.46), scale=1.2, pose="sitting_window")

    def _render_p1_pan4(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P1 Pan4: Khoảng tối mơ màng, giọng Mai gọi Minh thức dậy."""
        # Dark classroom dreamlike background with heavy ink vignetting
        draw.rectangle([0, 0, w, h], fill=(45, 48, 60))
        # Deep ink borders and corners
        draw.polygon([(0, 0), (int(w * 0.25), 0), (0, int(h * 0.6))], fill=(15, 18, 25))
        draw.polygon([(w, 0), (int(w * 0.75), 0), (w, int(h * 0.6))], fill=(15, 18, 25))
        draw.polygon([(0, h), (int(w * 0.3), h), (0, int(h * 0.4))], fill=(15, 18, 25))
        draw.polygon([(w, h), (int(w * 0.7), h), (w, int(h * 0.4))], fill=(15, 18, 25))

        # Halftone screentone texture
        draw_screentone_region(draw, (0, 0, w, h), dot_spacing=6, dot_radius=2, fill_color=(20, 22, 30))

        # Speed blur radial lines focusing on center
        cx, cy = w // 2, h // 2
        for angle in range(0, 360, 6):
            rad = math.radians(angle)
            draw.line([(cx + int(100 * math.cos(rad)), cy + int(70 * math.sin(rad))),
                       (cx + int(520 * math.cos(rad)), cy + int(320 * math.sin(rad)))],
                      fill=(20, 25, 35), width=2)

        # Silhouette of waking figure in warm dawn light
        draw.ellipse([cx - 70, cy - 80, cx + 70, cy + 50], fill=(255, 255, 255), outline=(15, 18, 25), width=4)
        draw.text((cx - 100, cy - 10), "Ư... ưm...", fill=(50, 55, 70), font=get_font(24))

    # --- PAGE 2: Thực tại đảo lộn — Tất cả nam sinh mặc váy ---

    def _render_p2_pan1(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P2 Pan1: Mai ngồi bàn bên mỉm cười trong cardigan kem và chân váy navy."""
        # Classroom background with chalkboard and window
        draw.rectangle([0, 0, int(w * 0.42), h], fill=(35, 45, 40))
        draw.rectangle([10, 15, int(w * 0.40), int(h * 0.65)], fill=(28, 36, 32), outline=(15, 20, 15), width=3)
        draw.text((25, 30), "TIẾT 2: HÌNH HỌC KHÔNG GIAN", fill=(210, 225, 215), font=get_font(16))

        # Wooden classroom desk in foreground
        draw.polygon([(0, h), (int(w * 0.38), h), (int(w * 0.35), int(h * 0.72)), (0, int(h * 0.72))], fill=(25, 28, 35), outline=(15, 18, 22), width=3)

        # Desk divider
        draw.line([(int(w * 0.42), 0), (int(w * 0.42), h)], fill=(20, 22, 28), width=4)

        # Mai in full detail: cream cardigan, pleated skirt, ribbon
        draw_character_mai(draw, cx=int(w * 0.68), cy=int(h * 0.40), scale=1.2)

    def _render_p2_pan2(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P2 Pan2: Toàn cảnh lớp học — nam sinh đều mặc váy, Minh đứng bật dậy hoang mang."""
        # Perspective classroom rows
        # Blackboard front
        draw.rectangle([0, 0, int(w * 0.30), int(h * 0.70)], fill=(40, 50, 45), outline=(15, 20, 15), width=4)

        # Multiple students sitting in desks wearing pleated skirts
        for s_idx, (sx, sy) in enumerate([(int(w * 0.18), int(h * 0.55)), (int(w * 0.36), int(h * 0.58)), (int(w * 0.48), int(h * 0.62))]):
            # Student desk
            draw.rectangle([sx - 40, sy + 30, sx + 40, sy + 80], fill=(210, 200, 190), outline=(20, 20, 25), width=2)
            # Boy in skirt
            draw.ellipse([sx - 20, sy - 30, sx + 20, sy + 10], fill=(250, 240, 235), outline=(20, 20, 25), width=2)
            draw.polygon([(sx - 28, sy + 35), (sx + 28, sy + 35), (sx + 35, sy + 75), (sx - 35, sy + 75)], fill=(30, 42, 68), outline=(15, 20, 30), width=2)

        # MINH standing up in extreme shock (Trousers distinct!)
        draw_character_minh(draw, cx=int(w * 0.80), cy=int(h * 0.44), scale=1.1, pose="standing_shock")

        # Shock dynamic speedlines radiating from Minh
        mx, my = int(w * 0.80), int(h * 0.35)
        for a in range(120, 250, 8):
            rad = math.radians(a)
            draw.line([(mx + int(110 * math.cos(rad)), my + int(80 * math.sin(rad))),
                       (mx + int(480 * math.cos(rad)), my + int(320 * math.sin(rad)))],
                      fill=(30, 30, 40), width=2)

    def _render_p2_pan3(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P2 Pan3: Huy (nam sinh tóc nâu xoăn) mặc váy xếp ly bước lại gần."""
        # Classroom blackboard and desks in background
        draw.rectangle([0, 0, int(w * 0.35), int(h * 0.70)], fill=(32, 42, 38), outline=(15, 20, 18), width=3)
        draw_screentone_region(draw, (int(w * 0.35), 0, w, h), dot_spacing=8, dot_radius=1)

        # Classroom foreground desk with deep ink shadows
        draw.rectangle([int(w * 0.05), int(h * 0.65), int(w * 0.38), h], fill=(22, 25, 32), outline=(10, 12, 18), width=3)

        # Huy in light blue cardigan & pleated skirt
        draw_character_huy(draw, cx=int(w * 0.50), cy=int(h * 0.42), scale=1.2)

        # Minh's shoulder & puzzled expression on the right
        draw.polygon([(w - 180, h), (w - 140, int(h * 0.3)), (w, int(h * 0.2)), (w, h)], fill=(22, 26, 38), outline=(10, 12, 18), width=3)

    def _render_p2_pan4(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P2 Pan4: Minh nhìn xuống bản thân: quần dài duy nhất trong lớp."""
        # Top-down perspective of Minh's school trousers and shoes
        # Wooden floor tiles
        for x in range(0, w, 60):
            draw.line([(x, 0), (x, h)], fill=(225, 220, 215), width=1)

        # Two dark trouser legs
        cx = w // 2
        draw.polygon([(cx - 110, 0), (cx - 20, 0), (cx - 35, int(h * 0.75)), (cx - 135, int(h * 0.75))], fill=(25, 28, 38), outline=(15, 15, 20), width=3)
        draw.polygon([(cx + 20, 0), (cx + 110, 0), (cx + 135, int(h * 0.75)), (cx + 35, int(h * 0.75))], fill=(25, 28, 38), outline=(15, 15, 20), width=3)

        # School shoes
        draw.ellipse([cx - 145, int(h * 0.70), cx - 35, int(h * 0.95)], fill=(15, 15, 20))
        draw.ellipse([cx + 35, int(h * 0.70), cx + 145, int(h * 0.95)], fill=(15, 15, 20))

        # Question marks / shock bubbles
        draw.text((cx - 180, int(h * 0.2)), "?!", fill=(180, 40, 40), font=get_font(42))
        draw.text((cx + 140, int(h * 0.2)), "?!", fill=(180, 40, 40), font=get_font(42))

    # --- PAGE 3: Thầy Lâm & Quy định 1990 ---

    def _render_p3_pan1(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P3 Pan1: Cửa lớp trượt mở, Thầy Lâm bước vào lớp."""
        # Sliding classroom door opened
        draw.rectangle([int(w * 0.1), 10, int(w * 0.42), h - 10], fill=(235, 230, 220), outline=(40, 40, 45), width=5)
        # Door opening motion lines
        for y in range(40, h - 40, 30):
            draw.line([(int(w * 0.08), y), (int(w * 0.18), y)], fill=(80, 85, 95), width=2)

        # Thầy Lâm standing in doorway: cardigan, round spectacles, black pencil skirt
        draw_character_teacher_lam(draw, cx=int(w * 0.65), cy=int(h * 0.44), scale=1.15)

    def _render_p3_pan2(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P3 Pan2: Thầy Lâm viết phấn lên bảng: QUY ĐỊNH ĐỒNG PHỤC HỌC SINH – NĂM 1990."""
        # Blackboard dark canvas
        draw.rectangle([10, 10, w - 10, h - 10], fill=(32, 42, 36), outline=(60, 45, 30), width=8)

        # Chalk formulas and text
        font_board_title = get_font(28)
        font_board_math = get_font(20)

        draw.text((40, 40), "QUY ĐỊNH ĐỒNG PHỤC HỌC SINH – NĂM 1990", fill=(255, 255, 250), font=font_board_title)
        draw.line([(35, 80), (w - 35, 80)], fill=(240, 240, 235), width=2)

        # Math formulas
        draw.text((50, 110), "1. Cải cách đồng phục học đường toàn quốc.", fill=(220, 230, 225), font=font_board_math)
        draw.text((50, 150), "2. f(x) = ax³ + bx² + cx + d   (x ∈ ℝ)", fill=(200, 215, 210), font=font_board_math)
        draw.text((50, 190), "3. Thống nhất áp dụng từ niên khóa 1990 - 1991.", fill=(220, 230, 225), font=font_board_math)

        # Thầy Lâm's back/arm holding chalk on the right
        draw.polygon([(w - 180, h), (w - 120, int(h * 0.35)), (w - 40, int(h * 0.2)), (w, int(h * 0.2)), (w, h)], fill=(230, 220, 200), outline=(20, 20, 25), width=3)
        # Chalk in hand
        draw.rectangle([w - 60, int(h * 0.18), w - 45, int(h * 0.22)], fill=(255, 255, 255), outline=(20, 20, 25), width=1)

    def _render_p3_pan3(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P3 Pan3: Minh tra cứu điện thoại — bài viết cải cách giáo dục 1989-1990."""
        # Dark classroom desk background
        draw.rectangle([0, 0, w, h], fill=(30, 32, 38))

        # Smartphone in hands
        cx, cy = w // 2, h // 2
        pw, ph = int(w * 0.46), int(h * 0.88)
        draw.rectangle([cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2], fill=(245, 248, 252), outline=(10, 10, 15), width=5)

        # Phone screen web archive interface
        sx0, sy0, sx1, sy1 = cx - pw // 2 + 10, cy - ph // 2 + 15, cx + pw // 2 - 10, cy + ph // 2 - 15
        draw.rectangle([sx0, sy0, sx1, sy0 + 35], fill=(20, 40, 80))
        draw.text((sx0 + 15, sy0 + 8), "🌐 LƯU TRỮ LỊCH SỬ · 1990", fill=(255, 255, 255), font=get_font(15))

        draw.text((sx0 + 15, sy0 + 50), "BÀI VIẾT: CẢI CÁCH ĐỒNG PHỤC 1990", fill=(20, 20, 30), font=get_font(18))
        draw.text((sx0 + 15, sy0 + 85), "Niên khóa 1990, Bộ Giáo Dục ban hành", fill=(70, 75, 85), font=get_font(14))
        draw.text((sx0 + 15, sy0 + 110), "quy định thống nhất váy xếp ly cho học sinh.", fill=(70, 75, 85), font=get_font(14))
        draw.text((sx0 + 15, sy0 + 145), "Đồng phục nam sinh cũ chính thức chấm dứt.", fill=(180, 30, 30), font=get_font(14))

        # Trembling hands holding phone
        draw.polygon([(sx0 - 40, sy1 + 10), (sx0 + 20, sy1 - 30), (sx0 + 40, sy1 + 20)], fill=(245, 235, 225), outline=(20, 20, 25), width=2)
        draw.polygon([(sx1 + 40, sy1 + 10), (sx1 - 20, sy1 - 30), (sx1 - 40, sy1 + 20)], fill=(245, 235, 225), outline=(20, 20, 25), width=2)

    def _render_p3_pan4(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P3 Pan4: Hoàng hôn tà, chuông tan tiết vang, phòng học vắng tanh."""
        # Deep orange/mauve sunset sky
        draw.rectangle([0, 0, int(w * 0.45), h], fill=(215, 120, 75))
        # Sun setting
        draw.ellipse([int(w * 0.15), int(h * 0.3), int(w * 0.28), int(h * 0.65)], fill=(255, 210, 140))

        # Classroom window frame in deep ink
        draw.rectangle([0, 0, int(w * 0.45), h], outline=(20, 22, 28), width=5)
        draw.line([(int(w * 0.22), 0), (int(w * 0.22), h)], fill=(20, 22, 28), width=4)

        # Long shadows of classroom desks across floor in deep ink
        draw.rectangle([int(w * 0.45), 0, w, h], fill=(195, 160, 140))
        for dy in range(40, h, 65):
            # Desk silhouette in deep black ink
            draw.rectangle([int(w * 0.52), dy, int(w * 0.75), dy + 25], fill=(18, 18, 24), outline=(10, 10, 15), width=2)
            # Cast shadow in deep ink
            draw.polygon([(int(w * 0.75), dy + 10), (w, dy + 50), (w, dy + 70), (int(w * 0.52), dy + 25)], fill=(28, 28, 38))

        # Solitary Minh sitting in silence
        draw_character_minh(draw, cx=int(w * 0.85), cy=int(h * 0.45), scale=max(0.9, min(w, h) / 450.0), pose="sitting_window")

    # --- PAGE 4: Tin nhắn cảnh báo & Nụ cười lúc hoàng hôn ---

    def _render_p4_pan1(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P4 Pan1: Cậu mở ảnh kỷ yếu: ảnh biến dạng kỳ dị thành trang phục váy."""
        draw.rectangle([0, 0, w, h], fill=(20, 22, 28))

        # Glowing glitching smartphone screen
        cx, cy = w // 2, h // 2
        pw, ph = int(w * 0.55), int(h * 0.85)
        draw.rectangle([cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2], fill=(240, 242, 245), outline=(10, 10, 15), width=4)

        # Distorted photo with digital glitch scanlines
        px0, py0, px1, py1 = cx - pw // 2 + 12, cy - ph // 2 + 15, cx + pw // 2 - 12, cy + ph // 2 - 15
        draw.rectangle([px0, py0, px1, py1], fill=(210, 215, 225))

        # Glitch lines across photo
        for gy in range(py0, py1, 8):
            shift = random.Random(gy).randint(-15, 15)
            draw.line([(px0, gy), (px1, gy)], fill=(120, 130, 160) if gy % 16 == 0 else (255, 100, 100), width=1)

        # Student figures in photo morphing
        draw.text((px0 + 20, py0 + 30), "ẢNH KỶ YẾU KHAI GIẢNG", fill=(20, 20, 30), font=get_font(18))
        draw.text((px0 + 20, py0 + 65), "⚠ LỖI HIỂN THỊ DỮ LIỆU HÌNH ẢNH", fill=(220, 30, 30), font=get_font(15))

    def _render_p4_pan2(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P4 Pan2: Màn hình điện thoại rung bần bật, tin nhắn từ số lạ."""
        draw.rectangle([0, 0, w, h], fill=(15, 18, 25))

        # Glowing SMS notification popup card
        cx, cy = w // 2, h // 2
        card_w, card_h = int(w * 0.72), int(h * 0.65)
        draw.rectangle([cx - card_w // 2, cy - card_h // 2, cx + card_w // 2, cy + card_h // 2], fill=(255, 255, 255), outline=(220, 40, 40), width=4)

        # Alert header
        draw.rectangle([cx - card_w // 2, cy - card_h // 2, cx + card_w // 2, cy - card_h // 2 + 40], fill=(220, 40, 40))
        draw.text((cx - card_w // 2 + 20, cy - card_h // 2 + 10), "🔔 TIN NHẮN MỚI · KHÔNG RÕ NGƯỜI GỬI", fill=(255, 255, 255), font=get_font(18))

        # Chilling message text
        draw.text((cx - card_w // 2 + 25, cy - card_h // 2 + 65), "\"Nếu cậu vẫn còn nhớ bộ đồng phục cũ,", fill=(20, 20, 30), font=get_font(22))
        draw.text((cx - card_w // 2 + 25, cy - card_h // 2 + 105), "đừng để họ biết cậu nhận ra.", fill=(20, 20, 30), font=get_font(22))
        draw.text((cx - card_w // 2 + 25, cy - card_h // 2 + 145), "CHẠY ĐI.\"", fill=(220, 20, 20), font=get_font(26))

        # Trembling shock lines around card
        for sx in range(cx - card_w // 2 - 20, cx + card_w // 2 + 20, 40):
            draw.line([(sx, cy - card_h // 2 - 15), (sx + 10, cy - card_h // 2 - 5)], fill=(255, 255, 255), width=2)
            draw.line([(sx, cy + card_h // 2 + 5), (sx + 10, cy + card_h // 2 + 15)], fill=(255, 255, 255), width=2)

    def _render_p4_pan3(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P4 Pan3: Cuối hành lang tranh tối tranh sáng, Thầy Lâm đứng nở nụ cười ma mị."""
        # Dramatic 1-Point Perspective School Hallway
        draw.rectangle([0, 0, w, h], fill=(25, 28, 38))

        # Vanishing point center
        vx, vy = int(w * 0.42), int(h * 0.45)

        # Floor perspective lines
        draw.polygon([(0, h), (vx, vy), (w, h)], fill=(40, 44, 58), outline=(20, 22, 30), width=2)
        for fx in range(0, w, 80):
            draw.line([(fx, h), (vx, vy)], fill=(65, 70, 90), width=1)

        # Ceiling & Wall lines
        draw.line([(0, 0), (vx, vy)], fill=(65, 70, 90), width=2)
        draw.line([(w, 0), (vx, vy)], fill=(65, 70, 90), width=2)

        # Hallway Windows casting moonlight/twilight rectangular beams
        for wy in range(vy + 10, h - 20, 50):
            scale_f = (wy - vy) / max(1, h - vy)
            win_w = int(120 * scale_f)
            draw.polygon([
                (int(w * 0.85) - win_w, wy), (w, wy - 20), (w, wy + 25), (int(w * 0.85) - win_w, wy + 40)
            ], fill=(85, 110, 150))

        # Backlit silhouette of Thầy Lâm at hallway corner
        # Round glasses glowing white specular in the darkness
        tx, ty = int(w * 0.38), int(h * 0.40)
        draw_character_teacher_lam(draw, cx=tx, cy=ty, scale=1.1)

        # Sinister white glint on round glasses
        draw.ellipse([tx - 18, ty - 90, tx - 2, ty - 74], fill=(255, 255, 255))
        draw.ellipse([tx + 2, ty - 90, tx + 18, ty - 74], fill=(255, 255, 255))

        # Psychological tension speed lines radiating
        for a in range(0, 360, 10):
            rad = math.radians(a)
            draw.line([(tx + int(70 * math.cos(rad)), ty + int(50 * math.sin(rad))),
                       (tx + int(450 * math.cos(rad)), ty + int(280 * math.sin(rad)))],
                      fill=(50, 55, 75), width=2)

    def _render_p4_pan4(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """P4 Pan4: Kết thúc chương 1 — Minh đóng băng trong sợ hãi."""
        # Dramatic chiaroscuro: half in twilight, half in deep shadow
        draw.rectangle([0, 0, w, h], fill=(48, 52, 65))
        # Deep shadow on right side
        draw.rectangle([int(w * 0.55), 0, w, h], fill=(18, 20, 26))

        # Close-up of Minh's terrified face
        cx, cy = int(w * 0.40), int(h * 0.48)
        # Face contour
        draw.polygon([
            (cx - 120, cy - 80), (cx - 100, cy + 90), (cx, cy + 140), (cx + 90, cy + 90), (cx + 110, cy - 80)
        ], fill=(252, 245, 238), outline=(15, 18, 24), width=3)

        # Shadow hatching across right side of face
        for x in range(cx, cx + 110, 10):
            draw.line([(x, cy - 70), (x - 20, cy + 120)], fill=(30, 32, 42), width=3)

        # Wide dilated shock eye
        draw_manga_eyes(draw, cx=cx - 30, cy=cy - 10, size=32, expression="shocked")
        # Cold sweat drops
        draw.ellipse([cx - 90, cy - 20, cx - 75, cy], fill=(180, 220, 255), outline=(15, 18, 24), width=1)
        draw.ellipse([cx + 50, cy - 30, cx + 62, cy - 12], fill=(180, 220, 255), outline=(15, 18, 24), width=1)

        # Hair
        draw.polygon([
            (cx - 140, cy - 60), (cx - 130, cy - 140), (cx - 40, cy - 170),
            (cx + 40, cy - 170), (cx + 130, cy - 130), (cx + 140, cy - 50),
            (cx + 90, cy - 90), (cx, cy - 110), (cx - 90, cy - 90)
        ], fill=(18, 20, 28), outline=(10, 12, 18), width=4)

        # Dramatic speed/tension lines
        for a in range(0, 360, 12):
            rad = math.radians(a)
            draw.line([(cx + int(120 * math.cos(rad)), cy + int(90 * math.sin(rad))),
                       (cx + int(480 * math.cos(rad)), cy + int(280 * math.sin(rad)))],
                      fill=(22, 25, 34), width=2)

        # End chapter caption box
        draw.rectangle([w - 240, h - 60, w - 20, h - 20], fill=(255, 255, 255), outline=(10, 10, 15), width=3)
        draw.text((w - 220, h - 52), "HẾT CHƯƠNG 1", fill=(15, 15, 20), font=get_font(20))
