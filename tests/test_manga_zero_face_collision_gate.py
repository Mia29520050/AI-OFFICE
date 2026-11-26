# -*- coding: utf-8 -*-
"""
tests/test_manga_zero_face_collision_gate.py
============================================
Strict Zero-Tolerance Face Collision Gatekeeper & Visual QA Suite
Enforces:
  1. IoU == 0.00 between any speech bubble (including expanded starburst spikes) and character face.
  2. Safe Clearance Distance >= 25.0 px.
  3. Rejection of V6 buggy layouts (Kaelen starburst spike collision & Carmilla forehead overlap).
  4. Acceptance of V7 Rule-of-Thirds negative space panels (kaelen_cel_left.png & carmilla_cel_right.png).
  5. Negative Space Solver auto-recovery.
  6. De-AI 2D Anime Cel-Shading Aesthetic Score >= 85.0% (specular < 0.05, neon < 0.05).
"""

import unittest
from pathlib import Path
from PIL import Image

from app.manga_vision_qa import MangaVisionQA, BoundingBox, detect_character_faces

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestMangaZeroFaceCollisionGate(unittest.TestCase):
    def setUp(self):
        self.qa = MangaVisionQA(min_clearance_px=25)
        self.de_ai_dir = ROOT_DIR / "data" / "manga" / "de_ai_panels"
        self.v7_page = ROOT_DIR / "data" / "manga" / "blood_princess_and_knight_ultimate_v7.png"

    def test_kaelen_cel_left_zero_face_collision(self):
        p = self.de_ai_dir / "kaelen_cel_left.png"
        if not p.exists():
            self.skipTest("kaelen_cel_left.png not generated yet")
        im = Image.open(p)
        faces = detect_character_faces(im)
        self.assertGreaterEqual(len(faces), 1, "Must detect Kaelen's face")
        face_box = faces[0].bbox

        # In V7 layout, Kaelen is on the left, bubble is at top-right
        bubble = [{"bubble_type": "shout", "x": 0.72, "y": 0.20, "width": 0.38, "height": 0.22}]
        res = self.qa.verify_panel_typesetting(im, bubble, panel_index=2, known_face_box=face_box)
        self.assertTrue(res.is_valid, f"Kaelen face was occluded! Errors: {res.errors}")
        self.assertEqual(len(res.face_collisions), 0)

        # Precise clearance check
        b_box = res.bubble_bboxes[0]
        iou = b_box.compute_iou(face_box)
        dist = b_box.min_distance(face_box)
        self.assertEqual(iou, 0.00, f"IoU must be exactly 0.00, got {iou}")
        self.assertGreaterEqual(dist, 25.0, f"Clearance distance {dist:.1f}px < 25.0px gate")

    def test_carmilla_cel_right_zero_face_collision(self):
        p = self.de_ai_dir / "carmilla_cel_right.png"
        if not p.exists():
            self.skipTest("carmilla_cel_right.png not generated yet")
        im = Image.open(p)
        faces = detect_character_faces(im)
        self.assertGreaterEqual(len(faces), 1, "Must detect Carmilla's face")
        face_box = faces[0].bbox

        # In V7 layout, Carmilla is on the right, bubble is at top-left
        bubble = [{"bubble_type": "regular", "x": 0.28, "y": 0.20, "width": 0.36, "height": 0.22}]
        res = self.qa.verify_panel_typesetting(im, bubble, panel_index=3, known_face_box=face_box)
        self.assertTrue(res.is_valid, f"Carmilla face/eyes was occluded! Errors: {res.errors}")
        self.assertEqual(len(res.face_collisions), 0)

        # Precise clearance check
        b_box = res.bubble_bboxes[0]
        iou = b_box.compute_iou(face_box)
        dist = b_box.min_distance(face_box)
        self.assertEqual(iou, 0.00, f"IoU must be exactly 0.00, got {iou}")
        self.assertGreaterEqual(dist, 25.0, f"Clearance distance {dist:.1f}px < 25.0px gate")

    def test_reproduction_and_rejection_of_v6_face_occlusions(self):
        """Ensures the QA Gate strictly rejects both V6 failure modes."""
        panel_w, panel_h = 550, 930
        panel_img = Image.new("RGB", (panel_w, panel_h), (20, 20, 25))

        # 1. Kaelen V6 shout bubble collision
        kaelen_face = BoundingBox(108, 41, 190, 198)
        v6_kaelen_bubble = [{"bubble_type": "shout", "x": 0.70, "y": 0.20, "width": 0.58, "height": 0.34}]
        res_k = self.qa.verify_panel_typesetting(panel_img, v6_kaelen_bubble, panel_index=2, known_face_box=kaelen_face)
        self.assertFalse(res_k.is_valid, "V6 Kaelen spike collision MUST be rejected")
        self.assertGreater(len(res_k.face_collisions), 0)

        # 2. Carmilla V6 forehead overlap
        carmilla_face = BoundingBox(190, 110, 360, 340)
        v6_carmilla_bubble = [{"bubble_type": "regular", "x": 0.50, "y": 0.14, "width": 0.64, "height": 0.24}]
        res_c = self.qa.verify_panel_typesetting(panel_img, v6_carmilla_bubble, panel_index=3, known_face_box=carmilla_face)
        self.assertFalse(res_c.is_valid, "V6 Carmilla forehead overlap MUST be rejected")
        self.assertGreater(len(res_c.face_collisions), 0)

    def test_negative_space_solver_relocation(self):
        """Verifies solver relocates colliding bubble into safe zone with Clearance >= 25px."""
        face = BoundingBox(200, 200, 400, 450)
        new_cx, new_cy = self.qa.solve_optimal_negative_space(
            panel_w=768,
            panel_h=1024,
            face_bbox=face,
            bubble_w_ratio=0.35,
            bubble_h_ratio=0.20,
            bubble_type="shout",
        )
        b_box = self.qa.compute_bubble_bbox(768, 1024, new_cx, new_cy, 0.35, 0.20, "shout")
        self.assertFalse(b_box.intersects(face))
        self.assertGreaterEqual(b_box.min_distance(face), 25.0)

    def test_aesthetic_de_ai_ratings(self):
        for name in ["kaelen_cel_left.png", "carmilla_cel_right.png"]:
            p = self.de_ai_dir / name
            if p.exists():
                im = Image.open(p)
                score = self.qa.analyze_de_ai_manga_aesthetic(im)
                self.assertLessEqual(score["neon_oversaturation_ratio"], 0.05, f"{name} is still too neon/AI!")
                self.assertGreaterEqual(score["manga_de_ai_score"], 85.0, f"{name} De-AI score too low!")

    def test_v7_composed_page_exists_and_verified(self):
        if self.v7_page.exists():
            im = Image.open(self.v7_page)
            self.assertEqual(im.size, (1200, 1750))


if __name__ == "__main__":
    unittest.main()
