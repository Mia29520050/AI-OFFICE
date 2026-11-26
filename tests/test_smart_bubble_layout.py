# -*- coding: utf-8 -*-
"""
Tests for Smart Speech Bubble Layout Engine & Anime Manga Consistency
====================================================================
Comprehensive evaluation suite verifying:
  1. Mathematical Anti-Collision & Zero Overlap Area for 2, 3, 4+ dialogue bubbles.
  2. Japanese Manga Reading Order (Right-to-Left, Top-to-Bottom flow).
  3. Face Avoidance (Focal center safety zone clearance).
  4. Dynamic Tail Pointer Direction (pointing towards speaking character).
  5. Anime Prompt Decomposition into 4 mandatory components (Style, Character, Emotion/Pose, BG/Camera).
  6. End-to-End Integration with Manga Composer pipeline.
"""

import math
from typing import List, Dict, Any
import pytest
from PIL import Image

from app.smart_bubble_layout import (
    BubbleRect,
    estimate_bubble_dimensions,
    calculate_manga_reading_score,
    calculate_character_target,
    compute_tail_pointer,
    solve_anti_collision_layout,
    layout_panel_dialogues,
    check_panel_bubble_overlap,
    optimize_speech_bubbles,
    FACE_SAFETY_ZONE,
    SAFE_PADDING_PX,
    DEFAULT_PANEL_W,
    DEFAULT_PANEL_H,
)
from app.manga_composer import (
    SpeechBubble,
    BubbleType,
    PanelConfig,
    convert_panel_plan_to_panel_config,
    render_speech_bubble_overlay,
)
from app.manga_anime_generator import (
    MangaAnimePromptGenerator,
    CharacterAnchor,
    DecomposedPanelPrompt,
    MODEL_PRESETS,
    ANIME_EMOTIONS,
    ANIME_POSES,
    CAMERA_SHOTS,
    BACKGROUND_ENVIRONMENTS,
)


# ==============================================================================
# 1. MATHEMATICAL ANTI-COLLISION & GEOMETRY TESTS
# ==============================================================================

class TestBubbleGeometryAndAntiCollision:
    """Mathematical verification of zero overlap and padding between bubbles."""

    def test_bubble_rect_bounds_and_intersection(self):
        """Verify bounding box properties and geometric intersection calculations."""
        # Box A: center (0.3, 0.3), w=0.2, h=0.2 -> bounds [0.2, 0.4] x [0.2, 0.4]
        box_a = BubbleRect("a", "Text A", x=0.3, y=0.3, w=0.2, h=0.2)
        assert pytest.approx(box_a.left) == 0.2
        assert pytest.approx(box_a.right) == 0.4
        assert pytest.approx(box_a.top) == 0.2
        assert pytest.approx(box_a.bottom) == 0.4

        # Box B: completely separate [0.6, 0.8] x [0.6, 0.8]
        box_b = BubbleRect("b", "Text B", x=0.7, y=0.7, w=0.2, h=0.2)
        assert not box_a.intersects(box_b)
        assert box_a.intersection_area(box_b) == 0.0

        # Box C: partially overlaps Box A [0.3, 0.5] x [0.3, 0.5]
        box_c = BubbleRect("c", "Text C", x=0.4, y=0.4, w=0.2, h=0.2)
        assert box_a.intersects(box_c)
        # Overlap in x: [0.3, 0.4] -> length 0.1; overlap in y: [0.3, 0.4] -> length 0.1
        assert pytest.approx(box_a.intersection_area(box_c)) == 0.01

    def test_two_bubbles_zero_overlap(self):
        """Two dialogue lines in a panel must have exactly 0 overlap area."""
        dialogues = [
            {"text": "Koharu, chuẩn bị xong tài liệu chưa?", "speaker": "Minh"},
            {"text": "Dạ em đã kiểm tra xong toàn bộ mã nguồn rồi ạ!", "speaker": "Koharu"},
        ]
        layout = layout_panel_dialogues(dialogues, panel_w=800, panel_h=600)
        assert len(layout) == 2

        # Convert to BubbleRect to measure intersection area
        boxes = [
            BubbleRect(
                id=f"b_{i}",
                text=item["text"],
                x=item["x"],
                y=item["y"],
                w=item["width"],
                h=item["height"],
            )
            for i, item in enumerate(layout)
        ]

        total_overlap_area, colliding_pairs = check_panel_bubble_overlap(boxes)
        assert total_overlap_area == 0.0, f"Overlap detected between 2 bubbles: {total_overlap_area} px^2 ({colliding_pairs})"
        assert len(colliding_pairs) == 0

    def test_three_bubbles_zero_overlap(self):
        """Three dialogue lines in a panel must have exactly 0 overlap area."""
        dialogues = [
            {"text": "Cậu thấy kiến trúc này thế nào?", "speaker": "Minh"},
            {"text": "Khá ấn tượng đấy, nhưng phần bộ nhớ còn tối ưu được.", "speaker": "Huy"},
            {"text": "Để em chạy thử nghiệm benchmark ngay nhé!", "speaker": "Koharu"},
        ]
        layout = layout_panel_dialogues(dialogues, panel_w=800, panel_h=600)
        assert len(layout) == 3

        boxes = [
            BubbleRect(
                id=f"b_{i}",
                text=item["text"],
                x=item["x"],
                y=item["y"],
                w=item["width"],
                h=item["height"],
            )
            for i, item in enumerate(layout)
        ]

        total_overlap_area, colliding_pairs = check_panel_bubble_overlap(boxes)
        assert total_overlap_area == 0.0, f"Overlap detected among 3 bubbles: {total_overlap_area} px^2 ({colliding_pairs})"
        assert len(colliding_pairs) == 0

    def test_four_bubbles_crowded_zero_overlap(self):
        """Crowded panel with 4 speech bubbles must achieve 0 overlap area."""
        dialogues = [
            {"text": "Hôm nay chúng ta cần hoàn thành Manga Studio!", "speaker": "Minh"},
            {"text": "Em đã chuẩn bị sẵn model Animagine XL rồi!", "speaker": "Mai"},
            {"text": "Tớ sẽ kiểm tra phần bong bóng thoại chống đè chữ.", "speaker": "Huy"},
            {"text": "Tuyệt vời, tất cả cùng bắt đầu thôi nào!", "speaker": "Koharu"},
        ]
        layout = layout_panel_dialogues(dialogues, panel_w=900, panel_h=700)
        assert len(layout) == 4

        boxes = [
            BubbleRect(
                id=f"b_{i}",
                text=item["text"],
                x=item["x"],
                y=item["y"],
                w=item["width"],
                h=item["height"],
            )
            for i, item in enumerate(layout)
        ]

        total_overlap_area, colliding_pairs = check_panel_bubble_overlap(boxes)
        assert total_overlap_area == 0.0, f"Overlap detected among 4 bubbles: {total_overlap_area} px^2 ({colliding_pairs})"
        assert len(colliding_pairs) == 0

    def test_boundary_clamping(self):
        """All bubbles must strictly remain within the panel boundaries [0.0, 1.0]."""
        dialogues = [
            {"text": "Câu thoại số một rất dài để kiểm tra độ rộng tối đa của bong bóng thoại...", "speaker": "Minh"},
            {"text": "Câu thoại số hai ở góc", "speaker": "Mai"},
            {"text": "Câu thoại số ba ở góc dưới", "speaker": "Huy"},
        ]
        layout = layout_panel_dialogues(dialogues, panel_w=800, panel_h=600)
        for item in layout:
            left = item["x"] - item["width"] / 2.0
            right = item["x"] + item["width"] / 2.0
            top = item["y"] - item["height"] / 2.0
            bottom = item["y"] + item["height"] / 2.0

            assert left >= 0.0, f"Bubble left edge {left} escaped panel left boundary"
            assert right <= 1.0, f"Bubble right edge {right} escaped panel right boundary"
            assert top >= 0.0, f"Bubble top edge {top} escaped panel top boundary"
            assert bottom <= 1.0, f"Bubble bottom edge {bottom} escaped panel bottom boundary"


# ==============================================================================
# 2. JAPANESE MANGA READING ORDER (RTL FLOW) TESTS
# ==============================================================================

class TestMangaReadingOrderFlow:
    """Verifies standard Japanese manga reading flow (Right-to-Left, Top-to-Bottom)."""

    def test_reading_score_properties(self):
        """Top-Right coordinate must have lowest reading score; Bottom-Left highest."""
        top_right_score = calculate_manga_reading_score(x=0.8, y=0.2)
        top_left_score = calculate_manga_reading_score(x=0.2, y=0.2)
        bottom_right_score = calculate_manga_reading_score(x=0.8, y=0.8)
        bottom_left_score = calculate_manga_reading_score(x=0.2, y=0.8)

        # In Japanese manga: Top-Right (earliest) < Top-Left < Bottom-Right < Bottom-Left (latest)
        assert top_right_score < top_left_score, "Top-Right should be read before Top-Left"
        assert top_left_score < bottom_right_score, "Top row should be read before Bottom row"
        assert bottom_right_score < bottom_left_score, "Bottom-Right should be read before Bottom-Left"

    def test_two_dialogue_reading_order(self):
        """Dialogue 1 must be positioned to be read before Dialogue 2 in manga flow."""
        dialogues = [
            {"text": "Cậu có chắc là phương án này sẽ chạy được không?", "speaker": "Minh"},
            {"text": "Hoàn toàn chắc chắn, tớ đã test kỹ rồi!", "speaker": "Huy"},
        ]
        layout = layout_panel_dialogues(dialogues)
        b1, b2 = layout[0], layout[1]

        score1 = calculate_manga_reading_score(b1["x"], b1["y"])
        score2 = calculate_manga_reading_score(b2["x"], b2["y"])

        assert score1 <= score2, (
            f"Line 1 (score={score1:.3f}, x={b1['x']}, y={b1['y']}) must be read before "
            f"Line 2 (score={score2:.3f}, x={b2['x']}, y={b2['y']})"
        )

        # Specifically: Line 1 should be higher up, or on same row but further to the right
        if abs(b1["y"] - b2["y"]) < 0.15:
            assert b1["x"] > b2["x"], "If on the same horizontal level, Line 1 must be on the Right in RTL manga"
        else:
            assert b1["y"] < b2["y"], "Line 1 must be higher than Line 2"

    def test_three_dialogue_reading_order_cascade(self):
        """Monotonic reading progression for 3 speech bubbles."""
        dialogues = [
            {"text": "Chào buổi sáng mọi người!", "speaker": "Mai"},
            {"text": "Chào Mai! Cậu đến sớm thế?", "speaker": "Minh"},
            {"text": "Tớ phải đến sớm để nộp bản thảo manga chứ!", "speaker": "Mai"},
        ]
        layout = layout_panel_dialogues(dialogues)
        scores = [calculate_manga_reading_score(b["x"], b["y"]) for b in layout]

        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1], (
                f"Bubble {i} (score {scores[i]:.2f}) is read after Bubble {i+1} (score {scores[i+1]:.2f})"
            )


# ==============================================================================
# 3. FACE AVOIDANCE & TAIL DIRECTION TESTS
# ==============================================================================

class TestFaceAvoidanceAndTailDirection:
    """Verifies that character face focal zone is kept clear and tail pointers point inward."""

    def test_face_safety_zone_clearance(self):
        """Bubbles must not cover the central character focal zone."""
        dialogues = [
            {"text": "Biểu cảm của nhân vật rất quan trọng!", "speaker": "Koharu"},
            {"text": "Đúng vậy, mặt nhân vật không được bị che khuất.", "speaker": "Minh"},
        ]
        # Custom face zone in center
        custom_face = {"x_min": 0.30, "x_max": 0.70, "y_min": 0.25, "y_max": 0.65}
        boxes = solve_anti_collision_layout(dialogues, face_zone=custom_face)

        for b in boxes:
            assert not b.intersects_face_zone(custom_face), (
                f"Bubble '{b.text}' at ({b.x}, {b.y}) intruded into face safety zone"
            )

    def test_tail_pointer_direction(self):
        """Tail pointer must extend from bubble towards the character mouth position."""
        # Bubble at top-right (x=0.76, y=0.18), speaker at center (x=0.5, y=0.52)
        tx, ty = compute_tail_pointer(bubble_x=0.76, bubble_y=0.18, char_x=0.50, char_y=0.52)
        # Tail should point leftwards (tx < bubble_x) and downwards (ty > bubble_y)
        assert tx < 0.76, f"Tail x={tx} should point left towards center"
        assert ty > 0.18, f"Tail y={ty} should point down towards center"

        # Bubble at top-left (x=0.24, y=0.18), speaker at center
        tx_left, ty_left = compute_tail_pointer(bubble_x=0.24, bubble_y=0.18, char_x=0.50, char_y=0.52)
        assert tx_left > 0.24, f"Tail x={tx_left} should point right towards center"
        assert ty_left > 0.18, f"Tail y={ty_left} should point down towards center"


# ==============================================================================
# 4. ANIME PROMPT 4-COMPONENT DECOMPOSITION TESTS
# ==============================================================================

class TestAnimePromptDecomposition:
    """Verifies the 4 mandatory anime prompt components and character consistency anchors."""

    def test_prompt_contains_all_four_components(self):
        """Prompt generator must cleanly decompose each panel into 4 distinct components."""
        generator = MangaAnimePromptGenerator()
        prompt_obj = generator.build_panel_prompt(
            panel_number=1,
            character_names=["koharu"],
            emotion_key="tsundere_pout",
            pose_key="arms_crossed",
            camera_key="medium_shot",
            background_key="japanese_classroom",
            vfx_key="screentone_hatch",
            model_preset="animagine_xl",
        )

        assert isinstance(prompt_obj, DecomposedPanelPrompt)

        # Component 1: Art Style / Medium
        assert "monochrome" in prompt_obj.art_style_component.lower()
        assert "screentone" in prompt_obj.art_style_component.lower()

        # Component 2: Locked Character Traits
        assert "koharu" in prompt_obj.character_traits_component.lower()
        assert "lavender" in prompt_obj.character_traits_component.lower()
        assert "[koharu_mascot]" in prompt_obj.character_traits_component

        # Component 3: Emotion & Pose
        assert "pouting" in prompt_obj.emotion_and_pose_component.lower()
        assert "arms crossed" in prompt_obj.emotion_and_pose_component.lower()

        # Component 4: Background & Camera
        assert "medium shot" in prompt_obj.background_and_camera_component.lower()
        assert "classroom" in prompt_obj.background_and_camera_component.lower()

    def test_character_consistency_across_panels(self):
        """Locked character traits must stay 100% identical across panels (StoryDiffusion)."""
        generator = MangaAnimePromptGenerator()
        p1 = generator.build_panel_prompt(
            panel_number=1,
            character_names=["minh"],
            emotion_key="determined_focus",
            camera_key="close_up",
        )
        p2 = generator.build_panel_prompt(
            panel_number=2,
            character_names=["minh"],
            emotion_key="jaw_drop_shock",
            camera_key="extreme_close_up",
        )

        # Even though emotion and camera change, character anchor traits MUST be identical
        assert p1.character_traits_component == p2.character_traits_component
        assert "[minh_protagonist]" in p1.character_traits_component
        assert "[minh_protagonist]" in p2.character_traits_component

    def test_negative_prompt_guards(self):
        """Negative prompt must contain essential anime anti-distortion tokens."""
        generator = MangaAnimePromptGenerator()
        prompt_obj = generator.build_panel_prompt(panel_number=1, model_preset="animagine_xl")
        neg = prompt_obj.full_negative_prompt.lower()

        assert "bad anatomy" in neg
        assert "blurry" in neg
        assert "bad hands" in neg
        assert "photorealistic" in neg


# ==============================================================================
# 5. END-TO-END INTEGRATION WITH MANGA COMPOSER TESTS
# ==============================================================================

class TestEndToEndMangaComposerIntegration:
    """Verifies that smart bubble layout integrates seamlessly with manga_composer.py."""

    def test_convert_panel_plan_uses_smart_layout(self):
        """convert_panel_plan_to_panel_config must automatically apply anti-collision layout."""
        panel_plan = {
            "id": "panel_01",
            "dialogues": [
                {"text": "Này cậu, nhìn kìa!", "speaker": "Minh", "position_hint": "auto"},
                {"text": "Cái gì thế? Để tớ xem!", "speaker": "Mai", "position_hint": "auto"},
            ]
        }
        p_config = convert_panel_plan_to_panel_config(panel_plan)
        assert len(p_config.bubbles) == 2

        b1, b2 = p_config.bubbles[0], p_config.bubbles[1]
        # In Japanese manga: b1 should be Top-Right (x=0.76, y=0.18), b2 on the left (x <= 0.24)
        assert b1.x == 0.76
        assert b2.x < b1.x
        assert b2.x <= 0.24

    def test_render_speech_bubble_overlay_pil_execution(self):
        """Verify that smart laid-out bubbles render onto an actual PIL image with zero crashes."""
        base_img = Image.new("RGB", (800, 600), color=(240, 240, 240))

        dialogues = [
            {"text": "Xin chào thế giới manga!", "speaker": "Koharu"},
            {"text": "Thuật toán Smart Bubble Layout hoạt động hoàn hảo!", "speaker": "Minh"},
        ]
        smart_bubbles_data = layout_panel_dialogues(dialogues, panel_w=800, panel_h=600)

        speech_bubbles = [
            SpeechBubble(
                text=b["text"],
                x=b["x"],
                y=b["y"],
                tail_x=b["tail_x"],
                tail_y=b["tail_y"],
                bubble_type=BubbleType.REGULAR,
            )
            for b in smart_bubbles_data
        ]

        for sb in speech_bubbles:
            overlay = render_speech_bubble_overlay((800, 600), sb)
            assert overlay is not None
            assert overlay.size == (800, 600)
            base_img.paste(overlay, (0, 0), overlay)

        assert base_img.size == (800, 600)

    def test_optimize_speech_bubbles_function(self):
        """optimize_speech_bubbles directly relocates colliding SpeechBubble objects."""
        # Two bubbles created at identical colliding positions
        colliding_bubbles = [
            SpeechBubble(text="Hộp thoại một", x=0.5, y=0.5),
            SpeechBubble(text="Hộp thoại hai đè lên nhau", x=0.5, y=0.5),
        ]
        optimized = optimize_speech_bubbles(colliding_bubbles, panel_w=800, panel_h=600)
        assert len(optimized) == 2
        # After optimization, x or y must be displaced so they do not overlap
        assert (optimized[0].x != optimized[1].x) or (optimized[0].y != optimized[1].y)
