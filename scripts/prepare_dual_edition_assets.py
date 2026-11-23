"""Generate dedicated 100% Full-Color and 100% Pure Black & White panel assets."""

import sys
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

sys.path.append(r"F:\AI-Office")
from app.manga_composer import apply_panel_filter, PanelFilter

SOURCE_DIR = Path(r"F:\AI-Office\data\manga\benchmarks\real_inference")
STORY_BW_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panels")
STORY_COL_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panels_color")

BW_CROPS_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panel_crops_bw")
COL_CROPS_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panel_crops_color")

BW_CROPS_DIR.mkdir(parents=True, exist_ok=True)
COL_CROPS_DIR.mkdir(parents=True, exist_ok=True)

def to_manga_monochrome(img: Image.Image) -> Image.Image:
    """Convert an image to 100% pure high-contrast manga monochrome."""
    gray = img.convert("L")
    enhanced = ImageEnhance.Contrast(gray).enhance(1.35)
    return apply_panel_filter(enhanced.convert("RGB"), PanelFilter.INK)

def prepare_assets():
    # 1. Base Source Images
    tc01_col = Image.open(SOURCE_DIR / "real_tc01_portrait.png").convert("RGB")
    tc02_col = Image.open(SOURCE_DIR / "real_tc02_full_body.png").convert("RGB")
    tc03_col = Image.open(SOURCE_DIR / "real_tc03_classroom.png").convert("RGB") # Raw full-color classroom!
    tc04_col = Image.open(SOURCE_DIR / "real_tc04_two_characters.png").convert("RGB")
    tc05_col = Image.open(SOURCE_DIR / "real_tc05_camera_angle_low.png").convert("RGB")
    tc06_bw = Image.open(SOURCE_DIR / "real_tc06_manga_bw_screentone.png").convert("RGB")
    tc07_col = Image.open(SOURCE_DIR / "real_tc07_full_color_panel.png").convert("RGB")
    tc08_col = Image.open(SOURCE_DIR / "real_tc08_four_panel_sequence.png").convert("RGB")
    adapter_col = Image.open(SOURCE_DIR / "adapter_minh_library.png").convert("RGB")

    # Story Generated Scenes (B&W and Color)
    sc_board_bw = Image.open(STORY_BW_DIR / "ch1_math_teacher_blackboard.png").convert("RGB")
    sc_phone_bw = Image.open(STORY_BW_DIR / "ch1_smartphone_news.png").convert("RGB")
    sc_glitch_bw = Image.open(STORY_BW_DIR / "ch1_glitch_photo_morph.png").convert("RGB")
    sc_hall_bw = Image.open(STORY_BW_DIR / "ch1_hallway_ending_silhouette.png").convert("RGB")

    sc_board_col = Image.open(STORY_COL_DIR / "ch1_math_teacher_blackboard_color.png").convert("RGB")
    sc_phone_col = Image.open(STORY_COL_DIR / "ch1_smartphone_news_color.png").convert("RGB")
    sc_glitch_col = Image.open(STORY_COL_DIR / "ch1_glitch_photo_morph_color.png").convert("RGB")
    sc_hall_col = Image.open(STORY_COL_DIR / "ch1_hallway_ending_silhouette_color.png").convert("RGB")

    # Dimensions
    w1, h1 = tc01_col.size
    w2, h2 = tc02_col.size
    w4, h4 = tc04_col.size
    w8, h8 = tc08_col.size
    hw8, hh8 = w8 // 2, h8 // 2
    wb_c, hb_c = sc_board_col.size
    wb_b, hb_b = sc_board_bw.size
    wp_c, hp_c = sc_phone_col.size
    wp_b, hp_b = sc_phone_bw.size
    wg_c, hg_c = sc_glitch_col.size
    wg_b, hg_b = sc_glitch_bw.size
    wh_c, hh_c = sc_hall_col.size
    wh_b, hh_b = sc_hall_bw.size

    # Build Master Dictionaries
    assets_col = {}
    assets_bw = {}

    # Full panels
    assets_col["classroom_wide"] = tc03_col
    assets_bw["classroom_wide"] = to_manga_monochrome(tc03_col)

    assets_col["two_students_talking"] = tc04_col
    assets_bw["two_students_talking"] = to_manga_monochrome(tc04_col)

    assets_col["minh_portrait_base"] = tc01_col
    assets_bw["minh_portrait_base"] = to_manga_monochrome(tc01_col)

    assets_col["minh_fullbody_base"] = tc02_col
    assets_bw["minh_fullbody_base"] = to_manga_monochrome(tc02_col)

    assets_col["minh_shock_lowangle"] = tc05_col
    assets_bw["minh_shock_lowangle"] = to_manga_monochrome(tc05_col)

    assets_col["manga_screentone_scene"] = tc07_col
    assets_bw["manga_screentone_scene"] = to_manga_monochrome(tc06_bw)

    assets_col["adapter_minh_panel"] = adapter_col
    assets_bw["adapter_minh_panel"] = to_manga_monochrome(adapter_col)

    # 4-panel sequence cuts
    assets_col["minh_expr_drowsy"] = tc08_col.crop((0, 0, hw8, hh8))
    assets_bw["minh_expr_drowsy"] = to_manga_monochrome(assets_col["minh_expr_drowsy"])

    assets_col["minh_expr_surprised"] = tc08_col.crop((hw8, 0, w8, hh8))
    assets_bw["minh_expr_surprised"] = to_manga_monochrome(assets_col["minh_expr_surprised"])

    assets_col["minh_expr_disbelief"] = tc08_col.crop((0, hh8, hw8, h8))
    assets_bw["minh_expr_disbelief"] = to_manga_monochrome(assets_col["minh_expr_disbelief"])

    assets_col["minh_expr_panic"] = tc08_col.crop((hw8, hh8, w8, h8))
    assets_bw["minh_expr_panic"] = to_manga_monochrome(assets_col["minh_expr_panic"])

    # Cinematic Minh crops
    assets_col["minh_face_medium"] = tc01_col.crop((int(w1*0.1), int(h1*0.1), int(w1*0.9), int(h1*0.75)))
    assets_bw["minh_face_medium"] = to_manga_monochrome(assets_col["minh_face_medium"])

    assets_col["minh_eyes_closeup"] = tc01_col.crop((int(w1*0.2), int(h1*0.25), int(w1*0.8), int(h1*0.55)))
    assets_bw["minh_eyes_closeup"] = to_manga_monochrome(assets_col["minh_eyes_closeup"])

    assets_col["minh_trousers_check"] = tc02_col.crop((int(w2*0.2), int(h2*0.45), int(w2*0.8), int(h2*0.95)))
    assets_bw["minh_trousers_check"] = to_manga_monochrome(assets_col["minh_trousers_check"])

    assets_col["minh_upper_uniform"] = tc02_col.crop((int(w2*0.15), int(h2*0.1), int(w2*0.85), int(h2*0.6)))
    assets_bw["minh_upper_uniform"] = to_manga_monochrome(assets_col["minh_upper_uniform"])

    # Classmates crops
    assets_col["mai_desk_focus"] = tc04_col.crop((0, int(h4*0.1), int(w4*0.55), int(h4*0.9)))
    assets_bw["mai_desk_focus"] = to_manga_monochrome(assets_col["mai_desk_focus"])

    assets_col["kenji_classmate_focus"] = tc04_col.crop((int(w4*0.45), int(h4*0.1), w4, int(h4*0.9)))
    assets_bw["kenji_classmate_focus"] = to_manga_monochrome(assets_col["kenji_classmate_focus"])

    # Math Teacher Blackboard crops
    assets_col["teacher_blackboard"] = sc_board_col
    assets_bw["teacher_blackboard"] = to_manga_monochrome(sc_board_bw)

    assets_col["teacher_face_glasses"] = sc_board_col.crop((int(wb_c*0.1), int(hb_c*0.08), int(wb_c*0.65), int(hb_c*0.55)))
    assets_bw["teacher_face_glasses"] = to_manga_monochrome(sc_board_bw.crop((int(wb_b*0.1), int(hb_b*0.08), int(wb_b*0.65), int(hb_b*0.55))))

    assets_col["teacher_pencil_skirt"] = sc_board_col.crop((int(wb_c*0.15), int(hb_c*0.45), int(wb_c*0.75), int(hb_c*0.98)))
    assets_bw["teacher_pencil_skirt"] = to_manga_monochrome(sc_board_bw.crop((int(wb_b*0.15), int(hb_b*0.45), int(wb_b*0.75), int(hb_b*0.98))))

    assets_col["teacher_chalk_writing"] = sc_board_col.crop((int(wb_c*0.3), int(hb_c*0.15), wb_c, int(hb_c*0.65)))
    assets_bw["teacher_chalk_writing"] = to_manga_monochrome(sc_board_bw.crop((int(wb_b*0.3), int(hb_b*0.15), wb_b, int(hb_b*0.65))))

    # Phone News crops
    assets_col["phone_news"] = sc_phone_col
    assets_bw["phone_news"] = to_manga_monochrome(sc_phone_bw)

    assets_col["phone_screen_archive"] = sc_phone_col.crop((int(wp_c*0.2), int(hp_c*0.2), int(wp_c*0.85), int(hp_c*0.75)))
    assets_bw["phone_screen_archive"] = to_manga_monochrome(sc_phone_bw.crop((int(wp_b*0.2), int(hp_b*0.2), int(wp_b*0.85), int(hp_b*0.75))))

    assets_col["phone_hands_tight"] = sc_phone_col.crop((int(wp_c*0.1), int(hp_c*0.35), int(wp_c*0.9), int(hp_c*0.95)))
    assets_bw["phone_hands_tight"] = to_manga_monochrome(sc_phone_bw.crop((int(wp_b*0.1), int(hp_b*0.35), int(wp_b*0.9), int(hp_b*0.95))))

    # Glitch Photo crops
    assets_col["glitch_photo"] = sc_glitch_col
    assets_bw["glitch_photo"] = to_manga_monochrome(sc_glitch_bw)

    assets_col["glitch_faces_morph"] = sc_glitch_col.crop((int(wg_c*0.2), int(hg_c*0.15), int(wg_c*0.85), int(hg_c*0.65)))
    assets_bw["glitch_faces_morph"] = to_manga_monochrome(sc_glitch_bw.crop((int(wg_b*0.2), int(hg_b*0.15), int(wg_b*0.85), int(hg_b*0.65))))

    assets_col["glitch_skirt_transform"] = sc_glitch_col.crop((int(wg_c*0.15), int(hg_c*0.4), int(wg_c*0.85), int(hg_c*0.9)))
    assets_bw["glitch_skirt_transform"] = to_manga_monochrome(sc_glitch_bw.crop((int(wg_b*0.15), int(hg_b*0.4), int(wg_b*0.85), int(hg_b*0.9))))

    # Hallway Silhouette crops
    assets_col["hallway_silhouette"] = sc_hall_col
    assets_bw["hallway_silhouette"] = to_manga_monochrome(sc_hall_bw)

    assets_col["hallway_dark_corridor"] = sc_hall_col.crop((0, 0, int(wh_c*0.7), hh_c))
    assets_bw["hallway_dark_corridor"] = to_manga_monochrome(sc_hall_bw.crop((0, 0, int(wh_b*0.7), hh_b)))

    assets_col["hallway_smile_moonlight"] = sc_hall_col.crop((int(wh_c*0.35), int(hh_c*0.15), wh_c, int(hh_c*0.65)))
    assets_bw["hallway_smile_moonlight"] = to_manga_monochrome(sc_hall_bw.crop((int(wh_b*0.35), int(hh_b*0.15), wh_b, int(hh_b*0.65))))

    # Save all assets
    for name, img in assets_col.items():
        img.save(COL_CROPS_DIR / f"{name}.png")

    for name, img in assets_bw.items():
        img.save(BW_CROPS_DIR / f"{name}.png")

    print(f"Successfully generated {len(assets_col)} Color assets in {COL_CROPS_DIR}")
    print(f"Successfully generated {len(assets_bw)} B&W assets in {BW_CROPS_DIR}")

if __name__ == "__main__":
    prepare_assets()
