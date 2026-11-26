# -*- coding: utf-8 -*-
"""
tests/test_raiden_shogun_qa.py
==============================
Unit & Integration Tests for Raiden Shogun Character Fidelity & Hallucination QA
"""

import unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from app.raiden_fidelity_qa import RaidenFidelityQA, RaidenFidelityResult

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestRaidenShogunQA(unittest.TestCase):
    def setUp(self):
        self.qa = RaidenFidelityQA(min_fidelity_score=75.0)

    def test_canonical_raiden_synthetic_palette_passes(self):
        """Simulates a canonical Raiden Shogun panel with purple hair and golden accents."""
        w, h = 600, 800
        # Dark gothic/euthymia background
        img = Image.new("RGB", (w, h), (30, 20, 40))
        draw = ImageDraw.Draw(img)

        # Violet hair zone (RGB ~ [110, 50, 160])
        draw.rectangle([(150, 80), (450, 450)], fill=(120, 55, 175))

        # Face skin zone
        draw.rectangle([(220, 180), (380, 360)], fill=(245, 220, 205))

        # Right eye beauty mark (dark dot)
        draw.ellipse([(260, 260), (265, 265)], fill=(30, 20, 25))

        # Golden hairpin ornament (RGB ~ [230, 180, 40])
        draw.rectangle([(380, 100), (430, 150)], fill=(225, 185, 35))

        # Electro lightning crackles (Bright violet/cyan, RGB ~ [200, 130, 255])
        for x_step in range(50, 550, 40):
            draw.line([(x_step, 500), (x_step + 30, 530), (x_step + 10, 580)], fill=(210, 140, 255), width=4)

        res = self.qa.evaluate_panel(img)
        self.assertTrue(res.is_canonical, f"Canonical Raiden should pass! Errors: {res.detected_hallucinations}")
        self.assertGreaterEqual(res.fidelity_score, 80.0)
        self.assertLessEqual(res.hallucination_rate, 0.20)
        self.assertGreater(res.hair_violet_ratio, 0.05)

    def test_hallucinatory_blonde_character_rejected(self):
        """Simulates a severely hallucinated blonde knight character instead of Raiden."""
        w, h = 600, 800
        img = Image.new("RGB", (w, h), (40, 40, 40))
        draw = ImageDraw.Draw(img)

        # Blonde hair (RGB ~ [240, 215, 80])
        draw.rectangle([(150, 80), (450, 450)], fill=(240, 215, 80))
        # Face skin
        draw.rectangle([(220, 180), (380, 360)], fill=(245, 220, 205))

        res = self.qa.evaluate_panel(img)
        self.assertFalse(res.is_canonical)
        self.assertLess(res.fidelity_score, 60.0)
        self.assertGreaterEqual(res.hallucination_rate, 0.40)
        self.assertTrue(any("hallucination" in h.lower() or "missing" in h.lower() for h in res.detected_hallucinations))

    def test_combat_action_panel_combined_qa(self):
        """Tests verify_combat_action_panel with bubble typesetting."""
        w, h = 600, 800
        img = Image.new("RGB", (w, h), (30, 20, 40))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(100, 200), (300, 600)], fill=(120, 55, 175))  # Character on left
        draw.rectangle([(150, 250), (280, 400)], fill=(245, 220, 205))  # Face on left

        # Bubble placed safely in negative space on top right
        bubbles = [{
            "bubble_type": "shout",
            "x": 0.75,
            "y": 0.20,
            "width": 0.35,
            "height": 0.22,
            "text": "Vô Niệm, Đoạn Tuyệt!",
        }]

        res = self.qa.verify_combat_action_panel(img, bubbles)
        self.assertTrue(res["typesetting_valid"])
        self.assertEqual(len(res["face_collisions"]), 0)


if __name__ == "__main__":
    unittest.main()
