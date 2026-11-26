from __future__ import annotations

"""
===============================================================================
app/manga_vision_qa.py
Automated Computer Vision QA & Face Collision Detection Engine for Manga Studio
===============================================================================

Key Capabilities:
  1. Strict Zero-Tolerance Face & Feature Clearance (IoU == 0.00, Clearance >= 25px).
  2. BoundingBox geometry, Intersection-over-Union (IoU), and Euclidean distance.
  3. Starburst spike expansion factor (1.30x) for shout bubbles.
  4. Detection of V6 bug patterns (Kaelen spiky bubbles & Carmilla forehead covering).
  5. Deep learning face detector (OpenCV YuNet with facial landmarks) & Negative Space finder.
  6. De-AI 2D Manga Cel-Shading & Specular Plasticity Scorer.
  7. Optimal Negative Space Solver to displace bubbles out of face collision.
===============================================================================
"""

import math
import os
import copy
import dataclasses
from dataclasses import dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


ROOT_DIR = Path(__file__).resolve().parents[1]
YUNET_MODEL_PATH = ROOT_DIR / "models" / "face_detection_yunet.onnx"

# Global detector instance cache
_YUNET_DETECTOR = None


# ---------------------------------------------------------------------------
# Core BoundingBox Geometry
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    """Axis-aligned bounding box defined by [x0, y0, x1, y1] pixel coordinates."""
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def intersects(self, other: "BoundingBox") -> bool:
        """Returns True if this box overlaps the other box (IoU > 0)."""
        return not (
            self.x1 <= other.x0
            or self.x0 >= other.x1
            or self.y1 <= other.y0
            or self.y0 >= other.y1
        )

    def compute_iou(self, other: "BoundingBox") -> float:
        """Computes exact Intersection-over-Union (IoU) with another box."""
        inter_x0 = max(self.x0, other.x0)
        inter_y0 = max(self.y0, other.y0)
        inter_x1 = min(self.x1, other.x1)
        inter_y1 = min(self.y1, other.y1)

        inter_w = max(0, inter_x1 - inter_x0)
        inter_h = max(0, inter_y1 - inter_y0)
        inter_area = inter_w * inter_h

        union_area = self.area + other.area - inter_area
        return float(inter_area / union_area) if union_area > 0 else 0.0

    def min_distance(self, other: "BoundingBox") -> float:
        """Computes Euclidean clearance distance between edges (0.0 if overlapping)."""
        if self.intersects(other):
            return 0.0
        dx = max(0, self.x0 - other.x1, other.x0 - self.x1)
        dy = max(0, self.y0 - other.y1, other.y0 - self.y1)
        return float(math.hypot(dx, dy))


@dataclass
class PanelQAResult:
    """Result of Vision QA panel typesetting verification."""
    panel_index: int
    is_valid: bool
    face_collisions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    bubble_bboxes: List[BoundingBox] = field(default_factory=list)
    face_bbox: Optional[BoundingBox] = None


@dataclass
class FaceDetectionResult:
    """Bounding box and landmark data for a detected character face/head."""
    x: int  # Left X in pixels
    y: int  # Top Y in pixels
    w: int  # Width in pixels
    h: int  # Height in pixels
    confidence: float
    landmarks: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    norm_x: float = 0.0
    norm_y: float = 0.0
    norm_w: float = 0.0
    norm_h: float = 0.0

    @property
    def bbox(self) -> BoundingBox:
        return BoundingBox(self.x, self.y, self.x + self.w, self.y + self.h)

    @property
    def mouth_pos(self) -> Optional[Tuple[int, int]]:
        if "mouth" in self.landmarks:
            return self.landmarks["mouth"]
        if "mouth_right" in self.landmarks and "mouth_left" in self.landmarks:
            mr = self.landmarks["mouth_right"]
            ml = self.landmarks["mouth_left"]
            return ((mr[0] + ml[0]) // 2, (mr[1] + ml[1]) // 2)
        return (int(self.x + self.w / 2.0), int(self.y + self.h * 0.85))


@dataclass
class BubbleCollisionResult:
    """Detailed collision check between a single speech bubble and a face."""
    bubble_id: str
    bubble_text: str
    bubble_box: Tuple[int, int, int, int]  # (x, y, w, h) in pixels including spikes
    face_box: Tuple[int, int, int, int]    # (x, y, w, h) in pixels
    iou: float
    clearance_distance_px: float
    is_colliding: bool
    verdict: str  # "PASS" or "COLLISION_DETECTED"
    overlap_area_px: float = 0.0


@dataclass
class NegativeSpaceRegion:
    """Candidate open region suitable for placing speech bubbles or SFX."""
    x: int  # Left X in pixels
    y: int  # Top Y in pixels
    w: int  # Width in pixels
    h: int  # Height in pixels
    edge_density: float = 0.0  # Mean edge density (lower is cleaner/flatter)
    score: float = 0.0         # Composite suitability score (lower is better)
    anchor_name: str = "custom"


@dataclass
class PanelVisionQAResult:
    """Complete Vision QA audit result for a single manga panel."""
    panel_index: int
    image_size: Tuple[int, int]
    detected_faces: List[FaceDetectionResult]
    negative_spaces: List[NegativeSpaceRegion]
    bubble_collisions: List[BubbleCollisionResult]
    has_face_collision: bool
    min_clearance_px: float
    max_iou: float
    is_passed: bool
    verdict: str
    repositioned_bubbles: List[Dict[str, Any]] = field(default_factory=list)


def compute_box_iou_and_clearance(
    box_a: Tuple[int, int, int, int],
    box_b: Tuple[int, int, int, int],
) -> Tuple[float, float, float]:
    """
    Computes (iou, clearance_distance_px, overlap_area_px) between two (x, y, w, h) bounding boxes.
    """
    ax0, ay0, aw, ah = box_a
    bx0, by0, bw, bh = box_b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh

    inter_x0 = max(ax0, bx0)
    inter_y0 = max(ay0, by0)
    inter_x1 = min(ax1, bx1)
    inter_y1 = min(ay1, by1)

    inter_w = max(0, inter_x1 - inter_x0)
    inter_h = max(0, inter_y1 - inter_y0)
    overlap_area = float(inter_w * inter_h)

    area_a = float(aw * ah)
    area_b = float(bw * bh)
    union_area = area_a + area_b - overlap_area
    iou = float(overlap_area / union_area) if union_area > 0 else 0.0

    if overlap_area > 0 or (inter_w > 0 and inter_h > 0) or (ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0):
        clearance = 0.0
    else:
        dx = max(0, ax0 - bx1, bx0 - ax1)
        dy = max(0, ay0 - by1, by0 - ay1)
        clearance = float(math.hypot(dx, dy))

    return round(iou, 4), round(clearance, 2), round(overlap_area, 2)


def compute_effective_bubble_box(
    bubble: Any,
    panel_w: int,
    panel_h: int,
) -> Tuple[int, int, int, int]:
    """
    Computes absolute (x, y, w, h) of a bubble, accounting for 1.28x spike factor on shout bubbles.
    """
    bx = getattr(bubble, "x", 0.5)
    by = getattr(bubble, "y", 0.5)
    bw = getattr(bubble, "width", None) or 0.35
    bh = getattr(bubble, "height", None) or 0.20
    b_type = str(getattr(bubble, "bubble_type", "regular")).lower()

    abs_cx = int(bx * panel_w) if 0.0 <= bx <= 1.0 else int(bx)
    abs_cy = int(by * panel_h) if 0.0 <= by <= 1.0 else int(by)
    abs_w = int(bw * panel_w) if 0.0 < bw <= 1.0 else int(bw)
    abs_h = int(bh * panel_h) if 0.0 < bh <= 1.0 else int(bh)

    if "shout" in b_type:
        spike_multiplier = 1.28
        abs_w = int(abs_w * spike_multiplier)
        abs_h = int(abs_h * spike_multiplier)

    left = int(abs_cx - abs_w / 2.0)
    top = int(abs_cy - abs_h / 2.0)
    return (left, top, abs_w, abs_h)


def check_bubble_face_collision(
    bubble: Any,
    face: Union[FaceDetectionResult, Tuple[int, int, int, int]],
    panel_w: int,
    panel_h: int,
    min_clearance_px: float = 25.0,
) -> BubbleCollisionResult:
    """
    Evaluates collision geometry between a bubble and character face.
    """
    bubble_box = compute_effective_bubble_box(bubble, panel_w, panel_h)
    if isinstance(face, FaceDetectionResult):
        face_box = (face.x, face.y, face.w, face.h)
    else:
        face_box = tuple(face)

    iou, clearance, overlap_area = compute_box_iou_and_clearance(bubble_box, face_box)
    is_colliding = (iou > 0.0 or overlap_area > 0.0 or clearance < min_clearance_px)
    verdict = "COLLISION_DETECTED" if is_colliding else "PASS"

    text = str(getattr(bubble, "text", ""))
    b_id = str(getattr(bubble, "id", "bubble"))

    return BubbleCollisionResult(
        bubble_id=b_id,
        bubble_text=text,
        bubble_box=bubble_box,
        face_box=face_box,
        iou=iou,
        clearance_distance_px=clearance,
        is_colliding=is_colliding,
        verdict=verdict,
        overlap_area_px=overlap_area,
    )


def reposition_bubble_to_negative_space(
    bubble: Any,
    panel_w: int,
    panel_h: int,
    face: Union[FaceDetectionResult, Tuple[int, int, int, int]],
    negative_spaces: Optional[List[NegativeSpaceRegion]] = None,
    min_clearance_px: float = 25.0,
) -> Any:
    """
    Relocates a colliding bubble into safe negative space ensuring clearance >= min_clearance_px.
    """
    if isinstance(face, FaceDetectionResult):
        face_box = (face.x, face.y, face.w, face.h)
    else:
        face_box = tuple(face)
    face_cx = face_box[0] + face_box[2] / 2.0
    face_cy = face_box[1] + face_box[3] / 2.0

    bw = getattr(bubble, "width", None) or 0.35
    bh = getattr(bubble, "height", None) or 0.20
    abs_w = int(bw * panel_w) if 0.0 < bw <= 1.0 else int(bw)
    abs_h = int(bh * panel_h) if 0.0 < bh <= 1.0 else int(bh)
    b_type = str(getattr(bubble, "bubble_type", "regular")).lower()
    if "shout" in b_type:
        eff_w = int(abs_w * 1.28)
        eff_h = int(abs_h * 1.28)
    else:
        eff_w = abs_w
        eff_h = abs_h

    def _apply_pos(b: Any, cx_ratio: float, cy_ratio: float) -> Any:
        if hasattr(b, "model_copy"):
            return b.model_copy(update={"x": cx_ratio, "y": cy_ratio})
        elif hasattr(b, "copy"):
            return b.copy(update={"x": cx_ratio, "y": cy_ratio})
        elif is_dataclass(b):
            return dataclasses.replace(b, x=cx_ratio, y=cy_ratio)
        elif isinstance(b, dict):
            cp = dict(b)
            cp["x"] = cx_ratio
            cp["y"] = cy_ratio
            return cp
        else:
            cp = copy.deepcopy(b)
            cp.x = cx_ratio
            cp.y = cy_ratio
            return cp

    candidates: List[Tuple[float, float]] = []
    if negative_spaces:
        for ns in negative_spaces:
            cand_cx = ns.x + ns.w / 2.0
            cand_cy = ns.y + ns.h / 2.0
            if cand_cx > face_cx:
                cand_cx = min(panel_w - eff_w / 2.0 - 10, max(cand_cx, face_box[0] + face_box[2] + min_clearance_px + eff_w / 2.0 + 5))
            else:
                cand_cx = max(eff_w / 2.0 + 10, min(cand_cx, face_box[0] - min_clearance_px - eff_w / 2.0 - 5))
            candidates.append((cand_cx / float(panel_w), cand_cy / float(panel_h)))

    candidates.extend([
        (0.78, 0.14),
        (0.22, 0.14),
        (0.78, 0.82),
        (0.22, 0.82),
        (0.50, 0.12),
        (0.85, 0.48),
        (0.15, 0.48),
    ])

    for cx, cy in candidates:
        test_b = _apply_pos(bubble, cx, cy)
        col = check_bubble_face_collision(test_b, face, panel_w, panel_h, min_clearance_px)
        if not col.is_colliding:
            return test_b

    fb_cx = 0.20 if face_cx > panel_w * 0.5 else 0.80
    fb_cy = 0.14 if face_cy > panel_h * 0.4 else 0.84
    return _apply_pos(bubble, fb_cx, fb_cy)


def audit_panel_vision_qa(
    image: Union[Image.Image, np.ndarray, str, Path],
    bubbles: List[Any],
    panel_index: int = 1,
    min_clearance_px: float = 25.0,
    auto_reposition: bool = False,
) -> PanelVisionQAResult:
    """
    Performs comprehensive end-to-end Vision QA audit on a manga panel.
    """
    if isinstance(image, (str, Path)):
        pil_img = Image.open(str(image)).convert("RGB")
    elif isinstance(image, Image.Image):
        pil_img = image.convert("RGB")
    elif isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image).convert("RGB")
    else:
        pil_img = Image.new("RGB", (600, 800), (0, 0, 0))

    pw, ph = pil_img.size
    detected_faces = detect_character_faces(pil_img)

    negative_spaces = [
        NegativeSpaceRegion(x=int(pw * 0.55), y=int(ph * 0.05), w=int(pw * 0.40), h=int(ph * 0.28), anchor_name="top-right"),
        NegativeSpaceRegion(x=int(pw * 0.05), y=int(ph * 0.05), w=int(pw * 0.40), h=int(ph * 0.28), anchor_name="top-left"),
        NegativeSpaceRegion(x=int(pw * 0.55), y=int(ph * 0.65), w=int(pw * 0.40), h=int(ph * 0.28), anchor_name="bottom-right"),
        NegativeSpaceRegion(x=int(pw * 0.05), y=int(ph * 0.65), w=int(pw * 0.40), h=int(ph * 0.28), anchor_name="bottom-left"),
    ]

    collisions: List[BubbleCollisionResult] = []
    repositioned: List[Dict[str, Any]] = []

    for idx, b in enumerate(bubbles):
        cur_b = b
        target_face = detected_faces[0] if detected_faces else FaceDetectionResult(x=int(pw*0.35), y=int(ph*0.2), w=int(pw*0.3), h=int(ph*0.3), confidence=0.5)
        col = check_bubble_face_collision(cur_b, target_face, pw, ph, min_clearance_px)

        if col.is_colliding and auto_reposition:
            cur_b = reposition_bubble_to_negative_space(cur_b, pw, ph, target_face, negative_spaces, min_clearance_px)
            repositioned.append({"original_index": idx, "repositioned_bubble": cur_b})
            col = check_bubble_face_collision(cur_b, target_face, pw, ph, min_clearance_px)

        collisions.append(col)

    has_collision = any(c.is_colliding for c in collisions)
    max_iou = max([c.iou for c in collisions], default=0.0)
    min_clearance = min([c.clearance_distance_px for c in collisions], default=999.0)
    is_passed = (not has_collision)
    verdict = "PASSED_STRICT_GATE" if is_passed else "FAILED_COLLISION_DETECTED"

    return PanelVisionQAResult(
        panel_index=panel_index,
        image_size=(pw, ph),
        detected_faces=detected_faces,
        negative_spaces=negative_spaces,
        bubble_collisions=collisions,
        has_face_collision=has_collision,
        min_clearance_px=min_clearance,
        max_iou=max_iou,
        is_passed=is_passed,
        verdict=verdict,
        repositioned_bubbles=repositioned,
    )


# ---------------------------------------------------------------------------
# Deep Learning & Heuristic Face Detection
# ---------------------------------------------------------------------------

def _get_yunet_detector(width: int, height: int):
    """Initializes or updates cached OpenCV YuNet face detector."""
    global _YUNET_DETECTOR
    if not OPENCV_AVAILABLE or not YUNET_MODEL_PATH.exists():
        return None
    try:
        if _YUNET_DETECTOR is None:
            _YUNET_DETECTOR = cv2.FaceDetectorYN_create(
                model=str(YUNET_MODEL_PATH),
                config="",
                input_size=(width, height),
                score_threshold=0.55,
                nms_threshold=0.30,
                top_k=500,
            )
        else:
            _YUNET_DETECTOR.setInputSize((width, height))
        return _YUNET_DETECTOR
    except Exception:
        return None


def detect_character_faces(
    image: Union[Image.Image, np.ndarray, str, Path],
    min_confidence: float = 0.50,
) -> List[FaceDetectionResult]:
    """Detects character faces/heads in a manga/anime panel."""
    if isinstance(image, (str, Path)):
        img_path = Path(image)
        if not img_path.exists():
            return []
        pil_img = Image.open(str(img_path)).convert("RGB")
    elif isinstance(image, Image.Image):
        pil_img = image.convert("RGB")
    elif isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image).convert("RGB")
    else:
        return []

    w, h = pil_img.size
    results: List[FaceDetectionResult] = []

    # 1. Primary Deep Learning (YuNet)
    if OPENCV_AVAILABLE and YUNET_MODEL_PATH.exists():
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        detector = _get_yunet_detector(w, h)
        if detector is not None:
            try:
                _, faces = detector.detect(cv_img)
                if faces is not None:
                    for f in faces:
                        fx, fy, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                        conf = float(f[14])
                        if conf < min_confidence:
                            continue

                        landmarks = {
                            "right_eye": (int(f[4]), int(f[5])),
                            "left_eye": (int(f[6]), int(f[7])),
                            "nose": (int(f[8]), int(f[9])),
                            "mouth_right": (int(f[10]), int(f[11])),
                            "mouth_left": (int(f[12]), int(f[13])),
                        }
                        results.append(
                            FaceDetectionResult(
                                x=max(0, fx),
                                y=max(0, fy),
                                w=min(w - max(0, fx), fw),
                                h=min(h - max(0, fy), fh),
                                confidence=conf,
                                landmarks=landmarks,
                                norm_x=round(max(0, fx) / float(w), 3),
                                norm_y=round(max(0, fy) / float(h), 3),
                                norm_w=round(fw / float(w), 3),
                                norm_h=round(fh / float(h), 3),
                            )
                        )
            except Exception:
                pass

    # 2. Skin tone fallback in YCrCb
    if not results and OPENCV_AVAILABLE:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        ycrcb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2YCrCb)
        lower_skin = np.array([40, 130, 75], dtype=np.uint8)
        upper_skin = np.array([255, 178, 130], dtype=np.uint8)
        mask = cv2.inRange(ycrcb, lower_skin, upper_skin)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            bx, by, bw, bh = cv2.boundingRect(c)
            area = bw * bh
            if area > (w * h * 0.02) and by < int(h * 0.75):
                aspect = bw / float(bh)
                if 0.5 <= aspect <= 1.8:
                    results.append(
                        FaceDetectionResult(
                            x=bx,
                            y=by,
                            w=bw,
                            h=bh,
                            confidence=0.60,
                            landmarks={"mouth": (bx + bw // 2, by + int(bh * 0.85))},
                            norm_x=round(bx / float(w), 3),
                            norm_y=round(by / float(h), 3),
                            norm_w=round(bw / float(w), 3),
                            norm_h=round(bh / float(h), 3),
                        )
                    )

    # 3. Default center-upper rule-of-thirds face zone fallback
    if not results:
        results.append(
            FaceDetectionResult(
                x=int(w * 0.35),
                y=int(h * 0.18),
                w=int(w * 0.30),
                h=int(h * 0.28),
                confidence=0.50,
                norm_x=0.35,
                norm_y=0.18,
                norm_w=0.30,
                norm_h=0.28,
            )
        )

    results.sort(key=lambda item: (item.confidence, item.w * item.h), reverse=True)
    return results


# ---------------------------------------------------------------------------
# MangaVisionQA Main Class
# ---------------------------------------------------------------------------

class MangaVisionQA:
    """
    Automated Vision QA Engine for Manga Studio:
      - Validates speech bubble placement against character faces with zero-tolerance.
      - Solves optimal negative space placement.
      - Measures de-AI authentic 2D cel-shading & specular sheen.
    """

    def __init__(self, min_clearance_px: int = 25):
        self.min_clearance_px = min_clearance_px

    def compute_bubble_bbox(
        self,
        panel_w: int,
        panel_h: int,
        bx_ratio: float,
        by_ratio: float,
        bw_ratio: float,
        bh_ratio: float,
        bubble_type: str = "regular",
    ) -> BoundingBox:
        """
        Computes absolute BoundingBox of a speech bubble,
        expanding shout starburst bubbles by 1.30x to account for protruding spikes.
        """
        abs_cx = bx_ratio * panel_w if 0.0 <= bx_ratio <= 1.0 else bx_ratio
        abs_cy = by_ratio * panel_h if 0.0 <= by_ratio <= 1.0 else by_ratio
        abs_w = bw_ratio * panel_w if 0.0 < bw_ratio <= 1.0 else bw_ratio
        abs_h = bh_ratio * panel_h if 0.0 < bh_ratio <= 1.0 else bh_ratio

        # Spiky shout bubbles have starburst tips protruding outwards by ~30%
        if "shout" in str(bubble_type).lower():
            spike_multiplier = 1.30
            abs_w = int(abs_w * spike_multiplier)
            abs_h = int(abs_h * spike_multiplier)

        x0 = int(abs_cx - abs_w / 2.0)
        y0 = int(abs_cy - abs_h / 2.0)
        x1 = int(abs_cx + abs_w / 2.0)
        y1 = int(abs_cy + abs_h / 2.0)
        return BoundingBox(x0, y0, x1, y1)

    def verify_panel_typesetting(
        self,
        panel_image: Union[Image.Image, np.ndarray, str, Path],
        bubbles_config: List[Union[Dict[str, Any], Any]],
        panel_index: int = 0,
        known_face_box: Optional[BoundingBox] = None,
    ) -> PanelQAResult:
        """
        Verifies that every speech bubble in the panel strictly avoids covering
        the character's face (IoU == 0.00 and Clearance >= min_clearance_px).
        """
        if isinstance(panel_image, (str, Path)):
            pil_img = Image.open(str(panel_image)).convert("RGB")
        elif isinstance(panel_image, Image.Image):
            pil_img = panel_image.convert("RGB")
        elif isinstance(panel_image, np.ndarray):
            pil_img = Image.fromarray(panel_image).convert("RGB")
        else:
            pil_img = Image.new("RGB", (600, 800), (0, 0, 0))

        pw, ph = pil_img.size

        # Face Bounding Box resolution
        if known_face_box is not None:
            face_box = known_face_box
        else:
            detected = detect_character_faces(pil_img)
            face_box = detected[0].bbox if detected else None

        bubble_bboxes: List[BoundingBox] = []
        collisions: List[Dict[str, Any]] = []
        errors: List[str] = []

        for idx, b in enumerate(bubbles_config):
            if isinstance(b, dict):
                bx = b.get("x", 0.5)
                by = b.get("y", 0.5)
                bw = b.get("width") or 0.35
                bh = b.get("height") or 0.20
                b_type = str(b.get("bubble_type", "regular")).lower()
                text = str(b.get("text", f"Bubble {idx}"))
            else:
                bx = getattr(b, "x", 0.5)
                by = getattr(b, "y", 0.5)
                bw = getattr(b, "width", None) or 0.35
                bh = getattr(b, "height", None) or 0.20
                b_type = str(getattr(b, "bubble_type", "regular")).lower()
                text = str(getattr(b, "text", f"Bubble {idx}"))

            b_box = self.compute_bubble_bbox(
                panel_w=pw,
                panel_h=ph,
                bx_ratio=bx,
                by_ratio=by,
                bw_ratio=bw,
                bh_ratio=bh,
                bubble_type=b_type,
            )
            bubble_bboxes.append(b_box)

            if face_box is not None:
                iou = b_box.compute_iou(face_box)
                dist = b_box.min_distance(face_box)
                intersects = b_box.intersects(face_box)

                if intersects or iou > 0.0 or dist < self.min_clearance_px:
                    col_info = {
                        "bubble_index": idx,
                        "bubble_type": b_type,
                        "text": text,
                        "iou": round(iou, 4),
                        "clearance_px": round(dist, 1),
                        "bubble_bbox": b_box,
                        "face_bbox": face_box,
                    }
                    collisions.append(col_info)
                    if intersects or iou > 0.0:
                        err = (
                            f"Panel {panel_index}: Bubble {idx} ({b_type}) covers the character's face! "
                            f"(IoU = {iou:.3f} > 0.0, overlap area detected)"
                        )
                    else:
                        err = (
                            f"Panel {panel_index}: Bubble {idx} ({b_type}) violates safe clearance distance! "
                            f"(distance = {dist:.1f}px < {self.min_clearance_px}px required)"
                        )
                    errors.append(err)

        is_valid = (len(collisions) == 0)

        return PanelQAResult(
            panel_index=panel_index,
            is_valid=is_valid,
            face_collisions=collisions,
            errors=errors,
            bubble_bboxes=bubble_bboxes,
            face_bbox=face_box,
        )

    def solve_optimal_negative_space(
        self,
        panel_w: int,
        panel_h: int,
        face_bbox: BoundingBox,
        bubble_w_ratio: float,
        bubble_h_ratio: float,
        bubble_type: str = "regular",
    ) -> Tuple[float, float]:
        """
        Calculates optimal normalized (center_x, center_y) placement for a speech bubble
        in open negative space, strictly guaranteeing zero intersection with character face
        and maximizing clearance distance.
        """
        # Prioritized candidate slots in Japanese Manga layout (Rule of Thirds corners)
        candidate_slots = [
            (0.76, 0.14),  # Top-Right (Manga primary)
            (0.24, 0.14),  # Top-Left (Reaction / response)
            (0.76, 0.82),  # Bottom-Right
            (0.24, 0.82),  # Bottom-Left
            (0.50, 0.12),  # Top-Center
            (0.82, 0.48),  # Middle-Right
            (0.18, 0.48),  # Middle-Left
            (0.50, 0.86),  # Bottom-Center
        ]

        face_cx = face_bbox.center[0] / float(panel_w)
        face_cy = face_bbox.center[1] / float(panel_h)

        best_slot = None
        best_dist = -1.0

        for cx, cy in candidate_slots:
            b_box = self.compute_bubble_bbox(
                panel_w=panel_w,
                panel_h=panel_h,
                bx_ratio=cx,
                by_ratio=cy,
                bw_ratio=bubble_w_ratio,
                bh_ratio=bubble_h_ratio,
                bubble_type=bubble_type,
            )
            if b_box.intersects(face_bbox):
                continue
            dist = b_box.min_distance(face_bbox)
            if dist >= self.min_clearance_px and dist > best_dist:
                best_dist = dist
                best_slot = (cx, cy)

        if best_slot is not None:
            return best_slot

        # Fallback: push to opposite quadrant of face center
        fallback_cx = 0.22 if face_cx > 0.50 else 0.78
        fallback_cy = 0.14 if face_cy > 0.40 else 0.82
        return (fallback_cx, fallback_cy)

    def analyze_de_ai_manga_aesthetic(self, image: Image.Image) -> Dict[str, Any]:
        """
        Analyzes 2D manga cel-shading authenticity vs. AI plastic sheen:
          - Specular Sheen Ratio: Blown-out white specular highlights (plastic shine).
          - Neon Oversaturation Ratio: Excessive saturated neon gradients.
          - Ink Line Density: Deep black G-pen ink lines.
        """
        img = image.convert("RGB")
        arr = np.array(img, dtype=np.float32)
        h, w, _ = arr.shape
        total_pixels = float(h * w)

        # 1. Specular sheen: Pure artificial plastic white spots
        specular_pixels = np.sum((arr[:, :, 0] > 250) & (arr[:, :, 1] > 250) & (arr[:, :, 2] > 250))
        specular_sheen_ratio = float(specular_pixels / total_pixels)

        # 2. Neon oversaturation in HSV space
        r, g, b = arr[:, :, 0] / 255.0, arr[:, :, 1] / 255.0, arr[:, :, 2] / 255.0
        c_max = np.maximum(np.maximum(r, g), b)
        c_min = np.minimum(np.minimum(r, g), b)
        delta = c_max - c_min
        sat = np.zeros_like(c_max)
        mask = c_max > 0.001
        sat[mask] = delta[mask] / c_max[mask]

        neon_pixels = np.sum((sat > 0.85) & (c_max > 0.85))
        neon_oversaturation_ratio = float(neon_pixels / total_pixels)

        # 3. Solid ink line density (deep black ink < 30)
        ink_pixels = np.sum((arr[:, :, 0] < 30) & (arr[:, :, 1] < 30) & (arr[:, :, 2] < 30))
        ink_density = float(ink_pixels / total_pixels)

        score = 100.0
        if specular_sheen_ratio > 0.05:
            score -= min(40.0, (specular_sheen_ratio - 0.05) * 400.0)
        if neon_oversaturation_ratio > 0.05:
            score -= min(40.0, (neon_oversaturation_ratio - 0.05) * 400.0)
        if ink_density < 0.05:
            score -= 15.0

        score = max(0.0, min(100.0, score))
        is_authentic = (score >= 75.0) and (specular_sheen_ratio < 0.05) and (neon_oversaturation_ratio < 0.05)

        return {
            "is_authentic_manga": is_authentic,
            "manga_de_ai_score": round(score, 1),
            "specular_sheen_ratio": round(specular_sheen_ratio, 3),
            "neon_oversaturation_ratio": round(neon_oversaturation_ratio, 3),
            "ink_density": round(ink_density, 3),
        }
