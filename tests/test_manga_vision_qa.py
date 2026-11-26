# -*- coding: utf-8 -*-
"""
tests/test_manga_vision_qa.py
=============================
Automated Test Suite for Computer Vision Quality Assurance (Vision QA):
  1. Strict Zero-Tolerance Face & Feature Clearance (IoU == 0.00, Clearance >= 25px).
  2. Exact Reproduction & Detection of V6 User Bug Reports (Kaelen Spikes & Carmilla Forehead).
  3. Validation of V7 Negative Space Rule-of-Thirds Typesetting.
  4. De-AI Cel-Shading & Specular Plasticity Scorer.
  5. Publishing Gatekeeper Verification (blocks release on collision).
"""

import math
from pathlib import Path
import pytest
import numpy as np
from PIL import Image, ImageDraw

from app.manga_vision_qa import (
    BoundingBox,
    PanelQAResult,
    MangaVisionQA,
)


class TestBoundingBoxGeometry:

    def test_box_area_and_center(self):
        box = BoundingBox(100, 100, 300, 200)
        assert box.width == 200
        assert box.height == 100
        assert box.area == 20000
        assert box.center == (200.0, 150.0)

    def test_non_overlapping_boxes_zero_iou_and_positive_distance(self):
        box_a = BoundingBox(10, 10, 50, 50)
        box_b = BoundingBox(100, 10, 140, 50)

        assert box_a.intersects(box_b) is False
        assert box_a.compute_iou(box_b) == 0.0
        assert box_a.min_distance(box_b) == 50.0

    def test_overlapping_boxes_positive_iou_and_zero_distance(self):
        box_a = BoundingBox(10, 10, 60, 60)
        box_b = BoundingBox(40, 40, 90, 90)

        assert box_a.intersects(box_b) is True
        assert box_a.compute_iou(box_b) > 0.0
        assert box_a.min_distance(box_b) == 0.0


class TestV6BugReproductionAndCatches:
    """Verifies that the Vision QA Engine reliably catches the exact V6 user bug reports."""

    def test_v6_catches_kaelen_shout_spikes_covering_face(self):
        # In V6 Panel 2 (550 x 930):
        # Kaelen's head was at: px=[108, 41, 190, 198]
        # Shout bubble was placed at x=0.70, y=0.20, width=0.58, height=0.34
        # With starburst spikes (spike_multiplier=1.30), spikes protruded into Kaelen's face!
        qa = MangaVisionQA(min_clearance_px=25)
        panel_w, panel_h = 550, 930
        panel_img = Image.new("RGB", (panel_w, panel_h), (25, 25, 30))

        kaelen_face = BoundingBox(108, 41, 190, 198)

        v6_bubbles = [
            {
                "bubble_type": "shout",
                "x": 0.70,
                "y": 0.20,
                "width": 0.58,
                "height": 0.34,
            }
        ]

        result = qa.verify_panel_typesetting(
            panel_image=panel_img,
            bubbles_config=v6_bubbles,
            panel_index=2,
            known_face_box=kaelen_face,
        )

        assert result.is_valid is False, "Vision QA MUST flag V6 Kaelen spike overlap as INVALID!"
        assert len(result.face_collisions) > 0, "Must detect face collision"
        assert len(result.errors) > 0

    def test_v6_catches_carmilla_dialogue_covering_forehead_and_eyes(self):
        # In V6 Panel 3 (550 x 930):
        # Carmilla's head was centered: [x0=190, y0=110, x1=360, y1=340]
        # Dialogue bubble was placed at x=0.50, y=0.14, width=0.64, height=0.24
        # Covering her entire forehead and eyes!
        qa = MangaVisionQA(min_clearance_px=25)
        panel_w, panel_h = 550, 930
        panel_img = Image.new("RGB", (panel_w, panel_h), (25, 25, 30))

        carmilla_face = BoundingBox(190, 110, 360, 340)

        v6_bubbles = [
            {
                "bubble_type": "regular",
                "x": 0.50,
                "y": 0.14,
                "width": 0.64,
                "height": 0.24,
            }
        ]

        result = qa.verify_panel_typesetting(
            panel_image=panel_img,
            bubbles_config=v6_bubbles,
            panel_index=3,
            known_face_box=carmilla_face,
        )

        assert result.is_valid is False, "Vision QA MUST flag V6 Carmilla forehead overlap as INVALID!"
        assert len(result.face_collisions) > 0
        assert result.face_collisions[0]["iou"] > 0.0
        assert "covers the character's face" in result.errors[0] or "violates" in result.errors[0]


class TestV7NegativeSpaceZeroIoU:
    """Verifies that the reformed V7 typesetting guarantees 100% face clearance."""

    def test_v7_kaelen_negative_space_typesetting_passes_strictly(self):
        qa = MangaVisionQA(min_clearance_px=25)
        panel_w, panel_h = 550, 930
        panel_img = Image.new("RGB", (panel_w, panel_h), (25, 25, 30))

        # Kaelen in Rule-of-Thirds bottom-left: head at [x0=80, y0=300, x1=200, y1=450]
        kaelen_face = BoundingBox(80, 300, 200, 450)

        # V7 Reformed typeset: Compact high-impact shout at Top-Right open sky
        # (x=0.76, y=0.14, width=0.36, height=0.18)
        v7_bubbles = [
            {
                "bubble_type": "shout",
                "x": 0.76,
                "y": 0.14,
                "width": 0.36,
                "height": 0.18,
            }
        ]

        result = qa.verify_panel_typesetting(
            panel_image=panel_img,
            bubbles_config=v7_bubbles,
            panel_index=2,
            known_face_box=kaelen_face,
        )

        assert result.is_valid is True, "V7 Kaelen placement must pass Vision QA with zero errors"
        assert len(result.face_collisions) == 0
        b_box = result.bubble_bboxes[0]
        dist = b_box.min_distance(kaelen_face)
        assert dist >= 25.0, f"Clearance distance must be >= 25px, got {dist:.1f}px"

    def test_v7_carmilla_negative_space_typesetting_passes_strictly(self):
        qa = MangaVisionQA(min_clearance_px=25)
        panel_w, panel_h = 550, 930
        panel_img = Image.new("RGB", (panel_w, panel_h), (25, 25, 30))

        # Carmilla in Rule-of-Thirds right side: head at [x0=340, y0=240, x1=480, y1=420]
        carmilla_face = BoundingBox(340, 240, 480, 420)

        # V7 Reformed typeset: Dialogue placed in open negative space Top-Left
        # (x=0.25, y=0.15, width=0.38, height=0.18)
        v7_bubbles = [
            {
                "bubble_type": "regular",
                "x": 0.25,
                "y": 0.15,
                "width": 0.38,
                "height": 0.18,
            }
        ]

        result = qa.verify_panel_typesetting(
            panel_image=panel_img,
            bubbles_config=v7_bubbles,
            panel_index=3,
            known_face_box=carmilla_face,
        )

        assert result.is_valid is True, "V7 Carmilla placement must pass Vision QA"
        assert len(result.face_collisions) == 0
        b_box = result.bubble_bboxes[0]
        dist = b_box.min_distance(carmilla_face)
        assert dist >= 25.0, f"Clearance distance must be >= 25px, got {dist:.1f}px"


class TestDeAIAestheticScorer:

    def test_plastic_neon_ai_surface_gets_low_score(self):
        qa = MangaVisionQA()
        w, h = 400, 400
        # Create image with high specular sheen (bright white) and oversaturated neon gradients
        img = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Specular white gradient spot
        draw.ellipse([100, 100, 300, 300], fill=(255, 255, 255))
        # Oversaturated neon border
        draw.rectangle([0, 0, w, 80], fill=(255, 0, 240))

        stats = qa.analyze_de_ai_manga_aesthetic(img)
        assert stats["is_authentic_manga"] is False
        assert stats["manga_de_ai_score"] < 75.0
        assert stats["specular_sheen_ratio"] > 0.05 or stats["neon_oversaturation_ratio"] > 0.05

    def test_authentic_2d_manga_illustration_gets_high_score(self):
        qa = MangaVisionQA()
        w, h = 400, 400
        # Create matte muted dark fantasy palette with solid ink lines
        img = Image.new("RGB", (w, h), (35, 30, 32))
        draw = ImageDraw.Draw(img)
        # Solid ink lines
        for y in range(20, h, 20):
            draw.line([(20, y), (w - 20, y)], fill=(12, 10, 12), width=3)
        # Muted crimson accent
        draw.ellipse([150, 150, 250, 250], fill=(160, 25, 35))

        stats = qa.analyze_de_ai_manga_aesthetic(img)
        assert stats["is_authentic_manga"] is True
        assert stats["manga_de_ai_score"] >= 75.0
        assert stats["specular_sheen_ratio"] < 0.05


class TestNegativeSpaceSolver:

    def test_solver_avoids_face_and_maximizes_clearance(self):
        qa = MangaVisionQA(min_clearance_px=25)
        panel_w, panel_h = 600, 800
        # Face is in mid-center [200, 300, 400, 500]
        face_box = BoundingBox(200, 300, 400, 500)

        cx_ratio, cy_ratio = qa.solve_optimal_negative_space(
            panel_w=panel_w,
            panel_h=panel_h,
            face_bbox=face_box,
            bubble_w_ratio=0.35,
            bubble_h_ratio=0.20,
            bubble_type="regular",
        )

        # Resulting bubble must not intersect face
        b_box = qa.compute_bubble_bbox(
            panel_w=panel_w,
            panel_h=panel_h,
            bx_ratio=cx_ratio,
            by_ratio=cy_ratio,
            bw_ratio=0.35,
            bh_ratio=0.20,
            bubble_type="regular",
        )

        assert b_box.intersects(face_box) is False
        assert b_box.min_distance(face_box) >= 25.0
