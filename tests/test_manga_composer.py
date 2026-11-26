from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from manga_composer import (
    BubbleType,
    PanelFilter,
    PanelLayoutType,
    FitMode,
    SpeechBubble,
    PanelConfig,
    PageConfig,
    ComicMetadata,
    MangaComposer,
    resolve_font_path,
    get_font,
    wrap_text_to_width,
    fit_text_in_bubble,
    render_speech_bubble_overlay,
    apply_halftone_dots,
    apply_dither,
    apply_manga_ink,
    apply_speedlines_radial,
    apply_speedlines_horizontal,
    apply_color_pastel,
    apply_color_vibrant,
    apply_color_sepia,
    apply_panel_filter,
    compute_panel_rects,
    fit_image_to_rect,
    create_panel_placeholder,
    export_page_to_png,
    export_to_cbz,
    export_to_pdf,
    export_chapter,
    image_to_base64_data_url,
    convert_story_dialogue_to_speech_bubble,
    convert_story_sfx_to_speech_bubble,
    convert_panel_plan_to_panel_config,
    convert_chapter_to_page_configs,
)


def test_font_resolution_and_vietnamese_unicode():
    font_path = resolve_font_path()
    assert font_path != "", "Font path should resolve"
    assert Path(font_path).exists(), f"Resolved font file must exist: {font_path}"

    font = get_font(size=24)
    assert font is not None

    test_img = Image.new("RGB", (300, 100), "#FFFFFF")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(test_img)

    vietnamese_sample = "Chào mừng bạn đến với AI Office Manga Studio! Một thế giới manga sống động."
    lines = wrap_text_to_width(vietnamese_sample, font, max_width=200, draw=draw)
    assert len(lines) >= 2
    assert "Chào mừng" in lines[0]

    # Test fit_text_in_bubble
    fitted_font, fitted_lines, text_w, text_h = fit_text_in_bubble(
        text=vietnamese_sample,
        target_w=250,
        target_h=120,
        preferred_font_size=24,
        min_font_size=12,
    )
    assert len(fitted_lines) >= 2
    assert text_w > 0 and text_h > 0


def test_speech_bubble_types_and_overlay():
    canvas_size = (800, 1000)

    # 1. Regular speech bubble
    b_regular = SpeechBubble(
        text="Tớ sẽ không bỏ cuộc đâu!",
        bubble_type=BubbleType.REGULAR,
        x=0.5,
        y=0.4,
        tail_x=0.5,
        tail_y=0.7,
    )
    overlay_reg = render_speech_bubble_overlay(canvas_size, b_regular)
    assert overlay_reg.size == canvas_size
    assert overlay_reg.mode == "RGBA"
    # Verify non-empty alpha
    assert overlay_reg.getextrema()[3][1] > 0

    # 2. Thought bubble
    b_thought = SpeechBubble(
        text="Liệu mình có thể cứu được mọi người?",
        bubble_type=BubbleType.THOUGHT,
        x=0.3,
        y=0.3,
        tail_x=0.2,
        tail_y=0.6,
    )
    overlay_thought = render_speech_bubble_overlay(canvas_size, b_thought)
    assert overlay_thought.size == canvas_size
    assert overlay_thought.getextrema()[3][1] > 0

    # 3. Shout bubble
    b_shout = SpeechBubble(
        text="CẨN THẬN ĐẰNG SAU!",
        bubble_type=BubbleType.SHOUT,
        x=0.6,
        y=0.5,
        tail_x=0.8,
        tail_y=0.8,
    )
    overlay_shout = render_speech_bubble_overlay(canvas_size, b_shout)
    assert overlay_shout.size == canvas_size

    # 4. Whisper bubble
    b_whisper = SpeechBubble(
        text="Suỵt... khẽ thôi, họ đang tới.",
        bubble_type=BubbleType.WHISPER,
        x=0.4,
        y=0.2,
    )
    overlay_whisper = render_speech_bubble_overlay(canvas_size, b_whisper)
    assert overlay_whisper.size == canvas_size

    # 5. Caption bubble
    b_caption = SpeechBubble(
        text="Tại học viện phép thuật Lumina, ba năm trước...",
        bubble_type=BubbleType.CAPTION,
        x=0.2,
        y=0.1,
    )
    overlay_caption = render_speech_bubble_overlay(canvas_size, b_caption)
    assert overlay_caption.size == canvas_size

    # 6. SFX sound effect
    b_sfx = SpeechBubble(
        text="BÙM!",
        bubble_type=BubbleType.SFX,
        x=0.5,
        y=0.5,
        rotation=-15.0,
        text_color="#FF2222",
        stroke_color="#000000",
        stroke_width=4,
    )
    overlay_sfx = render_speech_bubble_overlay(canvas_size, b_sfx)
    assert overlay_sfx.size == canvas_size

    # 6b. Crude English SFX auto-sanitization to authentic Vietnamese manga SFX
    b_sfx_crude = SpeechBubble(
        text="CLANNNG!",
        bubble_type=BubbleType.SFX,
        x=0.5,
        y=0.5,
    )
    overlay_sfx_crude = render_speech_bubble_overlay(canvas_size, b_sfx_crude)
    assert overlay_sfx_crude.size == canvas_size
    assert overlay_sfx_crude.getextrema()[3][1] > 0

    # 7. Inverted bubble
    b_inv = SpeechBubble(
        text="Ngươi đã quá trễ rồi...",
        bubble_type=BubbleType.INVERTED,
        x=0.5,
        y=0.5,
    )
    overlay_inv = render_speech_bubble_overlay(canvas_size, b_inv)
    assert overlay_inv.size == canvas_size


def test_panel_layouts_and_reading_direction():
    width, height = 1200, 1800

    # Test YONKOMA (4 vertical panels)
    yonkoma_rects = compute_panel_rects(
        layout_type=PanelLayoutType.YONKOMA,
        page_width=width,
        page_height=height,
        margin_x=40,
        margin_y=40,
        gutter_x=20,
        gutter_y=20,
    )
    assert len(yonkoma_rects) == 4
    for r in yonkoma_rects:
        x, y, w, h = r
        assert x >= 40 and y >= 40
        assert x + w <= width - 40 and y + h <= height - 40
        assert w > 0 and h > 0

    # Test GRID_2X2 with RTL vs LTR
    grid_rtl = compute_panel_rects(
        layout_type=PanelLayoutType.GRID_2X2,
        page_width=width,
        page_height=height,
        reading_direction="rtl",
    )
    grid_ltr = compute_panel_rects(
        layout_type=PanelLayoutType.GRID_2X2,
        page_width=width,
        page_height=height,
        reading_direction="ltr",
    )
    assert len(grid_rtl) == 4 and len(grid_ltr) == 4
    # In RTL, panel 0 is top-right, so its x should be greater than panel 1 (top-left)
    assert grid_rtl[0][0] > grid_rtl[1][0]
    # In LTR, panel 0 is top-left, so its x should be less than panel 1 (top-right)
    assert grid_ltr[0][0] < grid_ltr[1][0]

    # Test other standard layouts
    for layout in [
        PanelLayoutType.SINGLE,
        PanelLayoutType.GRID_1X2,
        PanelLayoutType.GRID_2X1,
        PanelLayoutType.TOP1_BOTTOM2,
        PanelLayoutType.TOP2_BOTTOM1,
        PanelLayoutType.THREE_ROWS,
        PanelLayoutType.ACTION_5,
        PanelLayoutType.DRAMA_6,
    ]:
        rects = compute_panel_rects(layout_type=layout, page_width=width, page_height=height)
        assert len(rects) > 0
        for r in rects:
            assert r[2] > 0 and r[3] > 0

    # Test CUSTOM layout
    custom_input = [(50, 50, 500, 400), (50, 500, 500, 400)]
    custom_rects = compute_panel_rects(
        layout_type=PanelLayoutType.CUSTOM,
        page_width=width,
        page_height=height,
        custom_rects=custom_input,
    )
    assert custom_rects == [(50, 50, 500, 400), (50, 500, 500, 400)]


def test_screentone_and_image_filters():
    base = Image.new("RGB", (200, 200), "#7F7F7F")

    # Halftone dots
    ht = apply_halftone_dots(base, grid_size=6)
    assert ht.size == (200, 200)

    # Dither
    dith = apply_dither(base, mode="floyd")
    assert dith.size == (200, 200)

    # Ink
    ink = apply_manga_ink(base, threshold=128)
    assert ink.size == (200, 200)

    # Radial speedlines
    sl_rad = apply_speedlines_radial(base, density=30)
    assert sl_rad.size == (200, 200)

    # Horizontal speedlines
    sl_hz = apply_speedlines_horizontal(base, density=20)
    assert sl_hz.size == (200, 200)

    # Color filters
    pastel = apply_color_pastel(base)
    assert pastel.size == (200, 200)

    vibrant = apply_color_vibrant(base)
    assert vibrant.size == (200, 200)

    sepia = apply_color_sepia(base)
    assert sepia.size == (200, 200)

    # De-AI organic enhancer filter
    from app.manga_composer import apply_de_ai_organic_enhancer
    de_ai = apply_de_ai_organic_enhancer(base, grain_intensity=0.08)
    assert de_ai.size == (200, 200)

    # Dispatcher apply_panel_filter
    dispatched = apply_panel_filter(base, PanelFilter.HALFTONE_DOTS, {"dot_size": 4})
    assert dispatched.size == (200, 200)

    dispatched_de_ai = apply_panel_filter(base, PanelFilter.DE_AI_ORGANIC)
    assert dispatched_de_ai.size == (200, 200)

    dispatched_gpen = apply_panel_filter(base, PanelFilter.G_PEN_GRAIN)
    assert dispatched_gpen.size == (200, 200)

    # Test manga_pipeline integration
    from app.manga_pipeline import apply_dark_fantasy_postprocessing
    dark_fantasy_out = apply_dark_fantasy_postprocessing(base)
    assert dark_fantasy_out.size == (200, 200)


def test_image_fitting_and_placeholder():
    src = Image.new("RGB", (400, 200), "#336699")

    cover = fit_image_to_rect(src, (200, 200), fit_mode=FitMode.COVER)
    assert cover.size == (200, 200)

    contain = fit_image_to_rect(src, (200, 200), fit_mode=FitMode.CONTAIN)
    assert contain.size == (200, 200)

    stretch = fit_image_to_rect(src, (200, 200), fit_mode=FitMode.STRETCH)
    assert stretch.size == (200, 200)

    placeholder = create_panel_placeholder(width=300, height=200, panel_index=1, prompt="Lớp học ánh trăng")
    assert placeholder.size == (300, 200)


def test_composer_page_composition_and_data_url():
    composer = MangaComposer()

    p1 = PanelConfig(
        id="p1",
        description="Nhân vật chính bước vào thư viện",
        bubbles=[
            SpeechBubble(text="Nơi này yên tĩnh thật...", bubble_type=BubbleType.REGULAR, x=0.5, y=0.3),
            SpeechBubble(text="XOẠCH!", bubble_type=BubbleType.SFX, x=0.5, y=0.7),
        ],
    )
    p2 = PanelConfig(
        id="p2",
        description="Một cuốn sách bí ẩn phát sáng",
        bubbles=[
            SpeechBubble(text="Cái gì thế kia?", bubble_type=BubbleType.THOUGHT, x=0.5, y=0.4),
        ],
    )

    page_cfg = PageConfig(
        page_number=1,
        width=800,
        height=1200,
        layout_type=PanelLayoutType.GRID_1X2,
        panels=[p1, p2],
    )

    composed_img = composer.compose_page(page_cfg)
    assert composed_img.size == (800, 1200)
    assert composed_img.mode == "RGB"

    data_url = image_to_base64_data_url(composed_img)
    assert data_url.startswith("data:image/png;base64,")
    assert len(data_url) > 100


def test_multi_format_exports_png_cbz_pdf():
    composer = MangaComposer()

    page1_cfg = PageConfig(
        page_number=1,
        width=600,
        height=900,
        layout_type=PanelLayoutType.SINGLE,
        panels=[PanelConfig(id="1", description="Trang bìa chương")],
    )
    page2_cfg = PageConfig(
        page_number=2,
        width=600,
        height=900,
        layout_type=PanelLayoutType.GRID_1X2,
        panels=[PanelConfig(id="2"), PanelConfig(id="3")],
    )

    img1 = composer.compose_page(page1_cfg)
    img2 = composer.compose_page(page2_cfg)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Test PNG Export
        png_out = tmp_path / "page_001.png"
        res_png = export_page_to_png(img1, png_out)
        assert res_png.is_file()
        assert res_png.stat().st_size > 0
        with Image.open(res_png) as loaded:
            assert loaded.size == (600, 900)

        # 2. Test CBZ Export
        cbz_out = tmp_path / "chapter_01.cbz"
        meta = ComicMetadata(
            title="Cuộc Phiêu Lưu Kì Thú",
            series="Lumina Chronicles",
            issue_or_chapter="1",
            summary="Chương mở đầu",
            language="vi",
        )
        res_cbz = export_to_cbz([img1, img2], cbz_out, metadata=meta)
        assert res_cbz.is_file()
        assert res_cbz.stat().st_size > 0

        # Verify ZIP contents
        with zipfile.ZipFile(res_cbz, "r") as zf:
            file_list = zf.namelist()
            assert "page_001.png" in file_list
            assert "page_002.png" in file_list
            assert "ComicInfo.xml" in file_list

            xml_data = zf.read("ComicInfo.xml").decode("utf-8")
            assert "Cuộc Phiêu Lưu Kì Thú" in xml_data
            assert "Lumina Chronicles" in xml_data
            assert "YesAndRightToLeft" in xml_data

        # 3. Test PDF Export
        pdf_out = tmp_path / "chapter_01.pdf"
        res_pdf = export_to_pdf([img1, img2], pdf_out, dpi=150)
        assert res_pdf.is_file()
        assert res_pdf.stat().st_size > 0
        pdf_bytes = res_pdf.read_bytes()
        assert pdf_bytes.startswith(b"%PDF-")

        # 4. Test Combined export_chapter
        export_dict = export_chapter(
            pages=[img1, img2],
            output_dir=tmp_path / "exports",
            base_name="chapter_1",
            export_png=True,
            export_cbz=True,
            export_pdf=True,
            metadata=meta,
        )
        assert len(export_dict["files"]["png_pages"]) == 2
        assert export_dict["files"]["cbz"] is not None and Path(export_dict["files"]["cbz"]).is_file()
        assert export_dict["files"]["pdf"] is not None and Path(export_dict["files"]["pdf"]).is_file()


def test_story_bridge_conversions():
    sample_dialogue = {
        "speaker": "Minh",
        "text": "Đừng lo, tớ ở đây rồi!",
        "bubble_type": "regular",
        "position_hint": "top-left",
    }
    b1 = convert_story_dialogue_to_speech_bubble(sample_dialogue)
    assert b1.text == "Đừng lo, tớ ở đây rồi!"
    assert b1.bubble_type == BubbleType.REGULAR
    assert b1.x < 0.5  # top-left x is ~0.25

    sample_sfx = {"text": "RẦM!", "intensity": "high"}
    b2 = convert_story_sfx_to_speech_bubble(sample_sfx)
    assert b2.text == "RẦM!"
    assert b2.bubble_type == BubbleType.SFX
    assert b2.stroke_width > 0

    sample_panel = {
        "panel_number": 1,
        "diffusion_prompt_en": "1boy reading book, library, moonlight",
        "visual_description": "Cậu bé đọc sách bên cửa sổ",
        "dialogues": [sample_dialogue],
        "sfx": [sample_sfx],
    }
    p_cfg = convert_panel_plan_to_panel_config(sample_panel)
    assert p_cfg.prompt == "1boy reading book, library, moonlight"
    assert len(p_cfg.bubbles) == 2

    sample_chapter = {
        "title": "Chương 1",
        "scenes": [
            {
                "scene_number": 1,
                "panels": [sample_panel, sample_panel],
            }
        ],
    }
    pages = convert_chapter_to_page_configs(
        sample_chapter,
        layout_type=PanelLayoutType.GRID_1X2,
        panels_per_page=2,
    )
    assert len(pages) == 1
    assert len(pages[0].panels) == 2


def test_sanitize_outer_single_quotes_and_thought_tail_clearance():
    from manga_composer import sanitize_manga_text

    # 1. Outer single quotes stripped cleanly
    assert sanitize_manga_text("'Chúng ta nhất định không thể dừng lại ở đây!'") == "Chúng ta nhất định không thể dừng lại ở đây!"
    assert sanitize_manga_text("‘Suy nghĩ này thật đáng sợ...’") == "Suy nghĩ này thật đáng sợ..."
    # Preserve apostrophe inside English words while stripping outer quotes
    assert sanitize_manga_text("'It's time to move!'") == "It's time to move!"
    # Preserve distinct inner quoted segments
    assert sanitize_manga_text("'Một' và 'hai'") == "'Một' và 'hai'"

    # Dialogue converter cleans outer quotes automatically
    dlg_bubble = convert_story_dialogue_to_speech_bubble({
        "speaker": "Elara",
        "text": "'Tôi sẽ bảo vệ nơi này!'",
        "bubble_type": "speech",
    })
    assert dlg_bubble.text == "Tôi sẽ bảo vệ nơi này!"

    # 2. Thought bubble trail must NOT stick to bottom edge of panel frame
    canvas_size = (800, 1000)
    panel_rect = (40, 50, 500, 400)  # bottom edge at y = 450
    b_thought_low = SpeechBubble(
        text="Liệu có kịp không?",
        bubble_type=BubbleType.THOUGHT,
        x=0.5,
        y=0.72,
        width=0.45,
        height=0.22,
        tail_x=0.5,
        tail_y=0.99,  # Pointing straight at bottom frame border
    )
    overlay = render_speech_bubble_overlay(canvas_size, b_thought_low, panel_rect=panel_rect)
    alpha = overlay.split()[3]
    # Inspect bottom 18px clearance inside panel (y = 432..450): no trail dots should bleed/stick there
    bottom_strip = alpha.crop((40, 432, 540, 450))
    assert bottom_strip.getextrema()[1] == 0, "Thought bubble tail dots should stay clear of bottom panel border"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS:", name)
    print("ALL_MANGA_COMPOSER_TESTS_PASSED")
