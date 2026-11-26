# -*- coding: utf-8 -*-
"""
Standardized Manga Onomatopoeia (SFX) Dictionary
================================================
Replaces crude English sounds (e.g. "CLANNNG!", "BOOM!") with authentic
Vietnamese & Japanese Katakana Manga Onomatopoeia tailored for Dark Fantasy & Action.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Any, Optional, Tuple

MANGA_SFX_REGISTRY = {
    # 1. Combat Melee & Blade Clashes (Cận chiến & Va chạm vũ khí)
    "keng": {
        "vi": "KENG!",
        "vi_alt": "KEEENG!",
        "kanji": "キィンッ!",
        "category": "combat_melee",
        "description": "Tiếng hai thanh kiếm va chạm sắc sảo, tia lửa bắn tóe",
        "stroke_color": (255, 255, 255),
        "fill_color": (230, 30, 40),
        "shadow_color": (30, 0, 10),
        "aura": "sparks"
    },
    "choang": {
        "vi": "CHOẢNG!",
        "vi_alt": "XOẢNG!",
        "kanji": "ガギンッ!",
        "category": "combat_melee",
        "description": "Tiếng đại kiếm nện thẳng vào khiên giáp hắc thép",
        "stroke_color": (255, 255, 255),
        "fill_color": (20, 20, 25),
        "shadow_color": (180, 20, 30),
        "aura": "shockwave"
    },
    "xoet": {
        "vi": "XOẸT!",
        "vi_alt": "PHẬP!",
        "kanji": "ザシュッ!",
        "category": "combat_melee",
        "description": "Đường kiếm sắc lẹm xé toạc không gian hoặc chém qua tà áo",
        "stroke_color": (255, 255, 255),
        "fill_color": (220, 20, 40),
        "shadow_color": (40, 5, 10),
        "aura": "blood_slice"
    },
    "vu": {
        "vi": "VÙ!",
        "vi_alt": "VÚT!",
        "kanji": "ブンッ!",
        "category": "combat_melee",
        "description": "Tiếng vung đại kiếm ma quái xé gió",
        "stroke_color": (255, 255, 255),
        "fill_color": (40, 40, 50),
        "shadow_color": (120, 120, 140),
        "aura": "wind_motion"
    },
    "rac": {
        "vi": "RẮC!",
        "vi_alt": "BAKI!",
        "kanji": "バキッ!",
        "category": "combat_melee",
        "description": "Tiếng giáp trụ thánh điện rạn nứt trước lực chém ngàn cân",
        "stroke_color": (255, 255, 255),
        "fill_color": (240, 50, 30),
        "shadow_color": (20, 20, 20),
        "aura": "shatter"
    },

    # 2. Magic & Blood Arts (Ma pháp Huyết tộc & Siêu nhiên)
    "gogogo": {
        "vi": "GÙ GÙ...",
        "vi_alt": "GOGOGO...",
        "kanji": "ゴゴゴ...",
        "category": "magic_supernatural",
        "description": "Tà khí ma vương áp bức nặng nề, không khí đặc quánh",
        "stroke_color": (255, 255, 255),
        "fill_color": (60, 10, 80),
        "shadow_color": (160, 20, 100),
        "aura": "menacing_purple"
    },
    "am": {
        "vi": "ẦM...!",
        "vi_alt": "ÙM...!",
        "kanji": "ドォォン!",
        "category": "magic_supernatural",
        "description": "Vụ nổ ma pháp huyết sắc bùng phát phá hủy đại sảnh",
        "stroke_color": (255, 255, 255),
        "fill_color": (200, 15, 30),
        "shadow_color": (10, 0, 0),
        "aura": "explosion"
    },
    "xeo": {
        "vi": "XÈO...!",
        "vi_alt": "XOẸT...!",
        "kanji": "ジュウウ!",
        "category": "magic_supernatural",
        "description": "Ngọn lửa huyết ma ăn mòn giáp sắt bốc khói",
        "stroke_color": (255, 255, 255),
        "fill_color": (180, 30, 20),
        "shadow_color": (40, 10, 10),
        "aura": "smoke"
    },
    "chieu": {
        "vi": "CHIẾU!",
        "vi_alt": "LÓA!",
        "kanji": "ピカッ!",
        "category": "magic_supernatural",
        "description": "Ánh sáng thánh kiếm lóe sáng chói mắt",
        "stroke_color": (20, 20, 30),
        "fill_color": (255, 240, 150),
        "shadow_color": (255, 200, 50),
        "aura": "holy_flash"
    },

    # 3. Motion & Agility (Chuyển động & Tốc độ)
    "vut": {
        "vi": "VÚT!",
        "vi_alt": "THOẮT!",
        "kanji": "シュッ!",
        "category": "motion_speed",
        "description": "Bóng đen lướt nhanh biến mất trong tích tắc",
        "stroke_color": (255, 255, 255),
        "fill_color": (50, 50, 70),
        "shadow_color": (150, 150, 180),
        "aura": "speed_lines"
    },
    "bich": {
        "vi": "BỊCH!",
        "vi_alt": "THỊCH!",
        "kanji": "ドサッ!",
        "category": "motion_speed",
        "description": "Tiếp đất nặng nề hoặc thi thể kỵ sĩ đổ rạp xuống sàn đá",
        "stroke_color": (255, 255, 255),
        "fill_color": (30, 30, 35),
        "shadow_color": (100, 100, 110),
        "aura": "dust"
    },

    # 4. Psychological & Ambient (Tâm lý & Nhịp đập)
    "thinh_thich": {
        "vi": "THÌNH THỊCH!",
        "vi_alt": "DOKI DOKI",
        "kanji": "ドキドキ!",
        "category": "psychological",
        "description": "Tiếng tim đập dồn dập trước khoảnh khắc sinh tử",
        "stroke_color": (255, 255, 255),
        "fill_color": (220, 40, 80),
        "shadow_color": (80, 10, 30),
        "aura": "pulse"
    },
    "im_lang": {
        "vi": "IM LẶNG...",
        "vi_alt": "SHIN...",
        "kanji": "シーン...",
        "category": "psychological",
        "description": "Sự im lặng chết chóc bao trùm không gian",
        "stroke_color": (255, 255, 255),
        "fill_color": (100, 100, 120),
        "shadow_color": (20, 20, 30),
        "aura": "fade"
    }
}

# Mapping table to automatically detect and replace crude English SFX
CRUDE_ENGLISH_SFX_MAP = {
    "clannng": "keng",
    "clangg": "keng",
    "clanng": "keng",
    "clang": "keng",
    "clash": "choang",
    "slash": "xoet",
    "slice": "xoet",
    "boom": "am",
    "kaboom": "am",
    "crash": "choang",
    "bang": "keng",
    "whoosh": "vu",
    "swish": "vu",
    "punch": "choang",
    "thud": "bich",
    "crack": "rac",
    "gasp": "thinh_thich",
    "screeech": "xoet"
}


def sanitize_manga_sfx(raw_text: str) -> Optional[Dict[str, Any]]:
    """Converts raw or crude English onomatopoeia to standardized Manga Vietnamese/Japanese SFX.
    Returns None if text is dialogue, silence (e.g. '...'), or not an actual sound effect.
    """
    stripped_raw = raw_text.strip().upper()
    if not stripped_raw or set(stripped_raw) <= {".", "…", " ", "!", "?", "-"}:
        return None

    # First check direct matches in registry values (e.g. "CHOẢNG!", "KENG!", etc.)
    for key, data in MANGA_SFX_REGISTRY.items():
        if stripped_raw in (data.get("vi", "").upper(), data.get("vi_alt", "").upper(), data.get("kanji", "").upper()):
            return data

    # Strip diacritics for phonetic ASCII matching
    nfkd = unicodedata.normalize("NFKD", raw_text)
    ascii_norm = "".join(c for c in nfkd if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")
    clean_key = re.sub(r"[^a-zA-Z0-9]", "", ascii_norm.lower())

    if not clean_key or len(clean_key) < 2:
        return None

    # Check if it matches a crude English word
    if clean_key in CRUDE_ENGLISH_SFX_MAP:
        mapped_key = CRUDE_ENGLISH_SFX_MAP[clean_key]
        return MANGA_SFX_REGISTRY[mapped_key]

    # Check direct key match in registry
    for key, data in MANGA_SFX_REGISTRY.items():
        if key == clean_key or (len(clean_key) >= 3 and (key in clean_key or clean_key in key)):
            return data

    # Do not force "keng" onto quiet/unknown text
    return None


def get_sfx_display_text(sfx_key: str, style: str = "vi_with_kanji") -> str:
    """Formats SFX for rendering on manga panel."""
    data = MANGA_SFX_REGISTRY.get(sfx_key.lower(), MANGA_SFX_REGISTRY["keng"])
    if style == "vi_only":
        return data["vi"]
    elif style == "kanji_only":
        return data["kanji"]
    elif style == "vi_with_kanji":
        return f"{data['vi']} ({data['kanji']})"
    return data["vi"]
