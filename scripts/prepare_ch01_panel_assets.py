"""Prepare individual cropped and enhanced panel assets for Moonlight Classroom Chapter 1."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageEnhance, ImageFilter
from app.manga_composer import apply_panel_filter, PanelFilter

SOURCE_DIR = Path(r"F:\AI-Office\data\manga\benchmarks\real_inference")
STORY_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panels")
PANEL_ASSET_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panel_crops")
PANEL_ASSET_DIR.mkdir(parents=True, exist_ok=True)

def generate_crops():
    # Load primary source images
    tc01_portrait = Image.open(SOURCE_DIR / "real_tc01_portrait.png")
    tc02_fullbody = Image.open(SOURCE_DIR / "real_tc02_full_body.png")
    tc03_classroom = Image.open(SOURCE_DIR / "real_tc03_classroom.png")
    tc04_twochar = Image.open(SOURCE_DIR / "real_tc04_two_characters.png")
    tc05_lowangle = Image.open(SOURCE_DIR / "real_tc05_camera_angle_low.png")
    tc06_screentone = Image.open(SOURCE_DIR / "real_tc06_manga_bw_screentone.png")
    tc07_color = Image.open(SOURCE_DIR / "real_tc07_full_color_panel.png")
    tc08_seq = Image.open(SOURCE_DIR / "real_tc08_four_panel_sequence.png")
    adapter_minh = Image.open(SOURCE_DIR / "adapter_minh_library.png")

    # Newly generated scenes
    sc_blackboard = Image.open(STORY_DIR / "ch1_math_teacher_blackboard.png")
    sc_phone = Image.open(STORY_DIR / "ch1_smartphone_news.png")
    sc_glitch = Image.open(STORY_DIR / "ch1_glitch_photo_morph.png")
    sc_hallway = Image.open(STORY_DIR / "ch1_hallway_ending_silhouette.png")

    assets = {}

    # 1. Base full panels
    assets["minh_portrait_base"] = tc01_portrait
    assets["minh_fullbody_base"] = tc02_fullbody
    assets["classroom_wide"] = apply_panel_filter(tc03_classroom, PanelFilter.INK)
    assets["two_students_talking"] = tc04_twochar
    assets["minh_shock_lowangle"] = tc05_lowangle
    assets["manga_screentone_scene"] = tc06_screentone
    assets["color_anime_panel"] = tc07_color
    assets["adapter_minh_panel"] = adapter_minh
    assets["teacher_blackboard"] = sc_blackboard
    assets["phone_news"] = sc_phone
    assets["glitch_photo"] = sc_glitch
    assets["hallway_silhouette"] = sc_hallway

    # 2. Slices from tc08 sequence (4 expressions of Minh)
    w8, h8 = tc08_seq.size
    hw8, hh8 = w8 // 2, h8 // 2
    assets["minh_expr_drowsy"] = tc08_seq.crop((0, 0, hw8, hh8))
    assets["minh_expr_surprised"] = tc08_seq.crop((hw8, 0, w8, hh8))
    assets["minh_expr_disbelief"] = tc08_seq.crop((0, hh8, hw8, h8))
    assets["minh_expr_panic"] = tc08_seq.crop((hw8, hh8, w8, h8))

    # 3. Cinematic crops
    # Minh close up eyes
    w1, h1 = tc01_portrait.size
    assets["minh_eyes_closeup"] = tc01_portrait.crop((int(w1*0.2), int(h1*0.25), int(w1*0.8), int(h1*0.55)))
    assets["minh_face_medium"] = tc01_portrait.crop((int(w1*0.1), int(h1*0.1), int(w1*0.9), int(h1*0.75)))

    # Minh uniform & trousers check
    w2, h2 = tc02_fullbody.size
    assets["minh_trousers_check"] = tc02_fullbody.crop((int(w2*0.2), int(h2*0.45), int(w2*0.8), int(h2*0.95)))
    assets["minh_upper_uniform"] = tc02_fullbody.crop((int(w2*0.15), int(h2*0.1), int(w2*0.85), int(h2*0.6)))

    # Mai desk neighbor focus
    w4, h4 = tc04_twochar.size
    assets["mai_desk_focus"] = tc04_twochar.crop((0, int(h4*0.1), int(w4*0.55), int(h4*0.9)))
    assets["kenji_classmate_focus"] = tc04_twochar.crop((int(w4*0.45), int(h4*0.1), w4, int(h4*0.9)))

    # Teacher blackboard details
    wb, hb = sc_blackboard.size
    assets["teacher_chalk_writing"] = sc_blackboard.crop((int(wb*0.3), int(hb*0.15), wb, int(hb*0.65)))
    assets["teacher_face_glasses"] = sc_blackboard.crop((int(wb*0.1), int(hb*0.08), int(wb*0.65), int(hb*0.55)))
    assets["teacher_pencil_skirt"] = sc_blackboard.crop((int(wb*0.15), int(hb*0.45), int(wb*0.75), int(hb*0.98)))

    # Smartphone news details
    wp, hp = sc_phone.size
    assets["phone_screen_archive"] = sc_phone.crop((int(wp*0.2), int(hp*0.2), int(wp*0.85), int(hp*0.75)))
    assets["phone_hands_tight"] = sc_phone.crop((int(wp*0.1), int(hp*0.35), int(wp*0.9), int(hp*0.95)))

    # Glitch details
    wg, hg = sc_glitch.size
    assets["glitch_faces_morph"] = sc_glitch.crop((int(wg*0.2), int(hg*0.15), int(wg*0.85), int(hg*0.65)))
    assets["glitch_skirt_transform"] = sc_glitch.crop((int(wg*0.15), int(hg*0.4), int(wg*0.85), int(hg*0.9)))

    # Hallway silhouette details
    wh, hh = sc_hallway.size
    assets["hallway_dark_corridor"] = sc_hallway.crop((0, 0, int(wh*0.7), hh))
    assets["hallway_smile_moonlight"] = sc_hallway.crop((int(wh*0.35), int(hh*0.15), wh, int(hh*0.65)))

    # Save all assets
    saved_paths = {}
    for name, img in assets.items():
        out_path = PANEL_ASSET_DIR / f"{name}.png"
        img.save(out_path)
        saved_paths[name] = str(out_path)

    print(f"Generated {len(saved_paths)} dedicated panel assets in {PANEL_ASSET_DIR}")
    return saved_paths

if __name__ == "__main__":
    generate_crops()
