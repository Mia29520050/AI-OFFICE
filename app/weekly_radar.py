# -*- coding: utf-8 -*-
"""
app/weekly_radar.py
===================
Weekly Information & Lore Radar Module for AI Office.

Capabilities:
1. Autonomous scanning and indexing of weekly character lore, Genshin Impact updates,
   outfits/costumes, and seasonal anime trends.
2. Persistent storage in data/lore_radar/ (JSON reports, Markdown digests, character lore sheets).
3. Automated synchronization with AutonomousCharacterResearcher & character repository.
4. Multi-criteria query engine: search by character, franchise, category, outfit, or trending status.
5. Rich prompt synthesis with aspect ratio (1:1, 3:4, 16:9, 9:16) and format presets (PNG, WEBP, JPEG).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.character_researcher import ResearchedCharacter, get_character_researcher

logger = logging.getLogger("weekly_radar")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[WEEKLY-RADAR] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

ROOT = Path(__file__).resolve().parent.parent
LORE_RADAR_DIR = ROOT / "data" / "lore_radar"
LORE_RADAR_DIR.mkdir(parents=True, exist_ok=True)
RADAR_CHARACTERS_DIR = LORE_RADAR_DIR / "characters"
RADAR_CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
RADAR_OUTFITS_DIR = LORE_RADAR_DIR / "outfits"
RADAR_OUTFITS_DIR.mkdir(parents=True, exist_ok=True)
RADAR_REPORTS_DIR = LORE_RADAR_DIR / "reports"
RADAR_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class LoreRadarEntry:
    id: str
    name: str
    franchise: str
    category: str  # "character", "outfit", "anime", "patch_lore"
    version_or_season: str
    title: str
    summary: str
    visual_tags: Dict[str, str] = field(default_factory=dict)
    danbooru_prompt: str = ""
    negative_prompt: str = ""
    recommended_aspect_ratio: str = "3:4"
    supported_aspect_ratios: List[str] = field(default_factory=lambda: ["1:1", "3:4", "16:9", "9:16"])
    preferred_format: str = "PNG"
    outfit_name: Optional[str] = None
    outfit_prompt: Optional[str] = None
    lore_facts: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    is_trending: bool = True
    priority: int = 5
    last_scanned: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeeklyRadarReport:
    week_id: str
    title: str
    timestamp: str
    summary: str
    total_entries: int
    characters: List[LoreRadarEntry] = field(default_factory=list)
    outfits: List[LoreRadarEntry] = field(default_factory=list)
    anime_spotlight: List[LoreRadarEntry] = field(default_factory=list)
    genshin_patch: List[LoreRadarEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_id": self.week_id,
            "title": self.title,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "total_entries": self.total_entries,
            "characters": [c.to_dict() for c in self.characters],
            "outfits": [o.to_dict() for o in self.outfits],
            "anime_spotlight": [a.to_dict() for a in self.anime_spotlight],
            "genshin_patch": [g.to_dict() for g in self.genshin_patch],
        }


# Curated baseline knowledge base for current Genshin, anime & outfits
CANONICAL_LORE_DATABASE: List[Dict[str, Any]] = [
    {
        "id": "citlali",
        "name": "Citlali",
        "franchise": "Genshin Impact",
        "category": "character",
        "version_or_season": "Genshin 5.3 Natlan",
        "title": "Masters of the Night-Wind High Shaman Citlali",
        "summary": "Elder shaman of the Masters of the Night-Wind tribe in Natlan. Known for her grumpy grandmotherly facade hiding a deeply caring heart.",
        "visual_tags": {
            "hair": "pink hair with dark purple underlayer, braided front hair, twin loose low side bunches",
            "eyes": "sharp deep teal-blue anime eyes, slight tsundere gaze",
            "face": "cute youthful anime face with slight blush",
            "outfit": "tribal night-wind ceremonial garment with obsidian jewel, dark purple cloth, gold bracelets",
            "accessories": "feathered obsidian headdress ornament, Citlalin spirit mask",
            "weapon": "cryo catalyst floating obsidian spirit talisman",
            "arena": "masters of the night-wind glowing twilight cavern with obsidian crystals"
        },
        "danbooru_prompt": "citlali (genshin impact), 1girl, solo, pink hair, purple underlayer, braided hair, teal eyes, tribal clothing, cryo effects, obsidian crystal, twilight night background",
        "negative_prompt": "photorealistic, 3d, realistic, deformed hands, bad anatomy, missing fingers, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Whispers of Stars and Smoke",
        "outfit_prompt": "wearing Citlali Whispers of Stars and Smoke sleepwear outfit, pastel lavender nightgown dress with lace hem, purple ombre shawl, Citlalin sleeping mask pushed up on hair, lavender leg warmers",
        "lore_facts": [
            "Resides in the Masters of the Night-Wind tribe in Natlan.",
            "Wears a trademark sleeping mask known as Citlalin when resting.",
            "Specializes in Night-Wind spiritual divination and astral warding."
        ],
        "sources": ["Genshin Impact Natlan Version 5.3", "HoYoWiki Citlali", "Genshin Lore Radar"],
        "is_trending": True,
        "priority": 10
    },
    {
        "id": "mavuika",
        "name": "Mavuika",
        "franchise": "Genshin Impact",
        "category": "character",
        "version_or_season": "Genshin 5.3 Natlan",
        "title": "Pyro Archon Habitation of Fire Mavuika",
        "summary": "The fiery sovereign Archon of Natlan, leading humanity with unyielding courage and blazing spirit.",
        "visual_tags": {
            "hair": "very long voluminous bright fiery orange-red hair, radiant flowing locks, glowing flame tips",
            "eyes": "fiery golden amber eyes, intense sovereign regal gaze",
            "face": "confident heroic anime face, determined smile",
            "outfit": "black leather motorcycle biker jacket with gold trim, dark form-fitting bodysuit with gold flame filigree, leather chaps",
            "accessories": "tinted sunglasses perched on forehead, golden sun crest choker",
            "weapon": "blazing fiery greatsword engulfed in radiant pyro flames",
            "arena": "stadium of the sacred flame in natlan, incandescent magma lava pillars, cheering volcanic arena"
        },
        "danbooru_prompt": "mavuika (genshin impact), 1girl, solo, long blazing fiery orange-red hair, amber eyes, black leather biker coat, pyro flame aura, glowing greatsword, volcanic stadium background",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, missing fingers, extra limbs, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Archon Flame Regalia",
        "outfit_prompt": "wearing Pyro Archon leather motorcycle suit, radiant blazing coat, gold flame embroidery",
        "lore_facts": [
            "Pyro Archon of Natlan and leader of the Sacred Flame.",
            "Possesses a motorized flame vehicle and rider aesthetic.",
            "Sacrificed personal immortality centuries ago to fight the Abyss."
        ],
        "sources": ["Genshin Impact Archon Quest Chapter V", "HoYoWiki Mavuika"],
        "is_trending": True,
        "priority": 10
    },
    {
        "id": "chasca",
        "name": "Chasca",
        "franchise": "Genshin Impact",
        "category": "character",
        "version_or_season": "Genshin 5.2 Natlan",
        "title": "Tlalocan Peacekeeper Chasca",
        "summary": "The fierce Tlalocan peacekeeper raised by Qucusaur dragons, patrolling the skies with her flying firearm Soulsnatcher.",
        "visual_tags": {
            "hair": "long deep crimson magenta hair, wild voluminous bangs, feathered braids",
            "eyes": "sharp keen golden amber eyes, focused dragon hunter gaze",
            "face": "fierce alert anime face, warrior markings",
            "outfit": "asymmetrical leather cowboy vest, fringed arm sleeves, dark shorts with ornate dragon belt",
            "accessories": "wide-brimmed feathered cowboy hat, qucusaur feathers",
            "weapon": "custom flying anemo rifle firearm soulsnatcher",
            "arena": "floating rocky cliffs of tlalocan at sunset, high altitude canyon with qucusaur flocks"
        },
        "danbooru_prompt": "chasca (genshin impact), 1girl, solo, crimson magenta hair, golden eyes, feathered cowboy hat, leather vest, firearm weapon, flying in sky, canyon background",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Tlalocan Feathered Ranger",
        "outfit_prompt": "wearing Tlalocan peacekeeper attire, fringed leather chaps, feathered cowboy hat",
        "lore_facts": [
            "Raised among Qucusaur saurian dragons in the high crags.",
            "Known as the Peacekeeper of Tlalocan resolving territorial clashes."
        ],
        "sources": ["Genshin Impact Version 5.2", "HoYoWiki Chasca"],
        "is_trending": True,
        "priority": 8
    },
    {
        "id": "furina",
        "name": "Furina",
        "franchise": "Genshin Impact",
        "category": "character",
        "version_or_season": "Genshin 4.2 Fontaine",
        "title": "The Endless Solo of Solitude Furina",
        "summary": "Former Hydro Archon Focalors human vessel who bore 500 years of solitude to save the people of Fontaine.",
        "visual_tags": {
            "hair": "silver-white and blue streak hair, asymmetrical bob cut with elegant curving ponytail",
            "eyes": "dual blue heterochromia eyes, water tear iris mark",
            "face": "theatrical dramatic expressive anime face",
            "outfit": "formal navy blue and white rococo aristocratic coat, ruffled cravat, dark tailored shorts, high heel boots",
            "accessories": "signature navy top hat with blue ribbon and gem ornament",
            "weapon": "splendor of tranquil waters sword, floating water droplets and salon solitaire companions",
            "arena": "opera epiclese stage, dramatic spotlight, floating bubbles and crystal chandeliers"
        },
        "danbooru_prompt": "furina (genshin impact), 1girl, solo, silver-blue hair, heterochromia eyes, navy blue top hat, rococo aristocratic coat, opera stage, water ripples, dramatic theater spotlight",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, missing fingers, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Pneuma / Ousia Stage Ensemble",
        "outfit_prompt": "wearing rococo navy coat, white lace cravat, aristocratic top hat, high heel boots",
        "lore_facts": [
            "Performed as the Hydro Archon for 500 years before the prophecy's dissolution.",
            "Can switch between Pneuma and Ousia states modifying her outfit color tone."
        ],
        "sources": ["Genshin Impact Fontaine Archon Quest", "HoYoWiki Furina"],
        "is_trending": True,
        "priority": 9
    },
    {
        "id": "raiden_shogun",
        "name": "Raiden Shogun",
        "franchise": "Genshin Impact",
        "category": "character",
        "version_or_season": "Genshin Inazuma",
        "title": "Narukami Ogosho Raiden Shogun (Ei)",
        "summary": "The supreme sovereign ruler of Inazuma, embodiment of divine thunder and the eternal lightning.",
        "visual_tags": {
            "hair": "very long dark purple braided hair, glowing lavender tips, symmetrical front bangs",
            "eyes": "glowing deep violet eyes, divine electric iris crest",
            "face": "aristocratic divine anime face, teardrop mole under right eye",
            "outfit": "lavender and royal purple kimono, pauldron with mitsudomoe crest, wide purple obi sash, purple thigh-high stockings",
            "accessories": "golden fan-shaped hairpin with violet balloon flower, glowing electro chakra ring",
            "weapon": "musou isshin glowing electro katana crackling with high-voltage purple lightning",
            "arena": "plane of euthymia, stormy purple void, floating shattered red torii gates"
        },
        "danbooru_prompt": "raiden shogun, 1girl, solo, long dark purple braided hair, beauty mark mole under right eye, purple eyes, kimono, musou isshin katana, purple lightning arcs, plane of euthymia",
        "negative_prompt": "photorealistic, 3d, realistic, deformed hands, bad anatomy, missing fingers, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Narukami Sovereign Kimono",
        "outfit_prompt": "wearing royal purple kimono with gold cloud embroideries, purple obi sash, thigh-high stockings",
        "lore_facts": [
            "Ruler of the Inazuma Shogunate and master of the Musou no Hitotachi.",
            "Created the mechanical puppet Shogun while meditating within the Plane of Euthymia."
        ],
        "sources": ["Genshin Impact Inazuma Archon Quest", "HoYoWiki Raiden Shogun"],
        "is_trending": True,
        "priority": 9
    },
    {
        "id": "hu_tao",
        "name": "Hu Tao",
        "franchise": "Genshin Impact",
        "category": "character",
        "version_or_season": "Genshin Liyue",
        "title": "77th Director of the Wangsheng Funeral Parlor",
        "summary": "The spirited 77th Director of Wangsheng Funeral Parlor, playful poet and guardian of the boundary between life and death.",
        "visual_tags": {
            "hair": "very long dark brown hair, low twin twintails, parted bangs, brown gradient hair",
            "eyes": "bright crimson red blossom eyes, flower-shaped pupils",
            "face": "cheerful confident mischievous smile, cute anime face",
            "outfit": "traditional chinese dark coat with gold ornaments, mandarin collar, black shorts, white socks with red flower",
            "accessories": "dark brown porkpie hat with plum blossom branch and gold talisman, rings on fingers",
            "weapon": "ghost companion boo tao, floating translucent smiling ghost, fiery pyro butterfly embers",
            "arena": "wangsheng funeral parlor courtyard at night, warm lantern glow, pyro sparks"
        },
        "danbooru_prompt": "hu tao (genshin impact), 1girl, solo, dark brown twintails, flower-shaped pupils, porkpie hat with plum blossom, dark coat, boo tao ghost companion, butterfly pyro embers",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, missing fingers, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Wangsheng Ceremonial Coat",
        "outfit_prompt": "wearing traditional Chinese dark coat with mandarin collar, plum blossom porkpie hat",
        "lore_facts": [
            "77th Director of Wangsheng Funeral Parlor in Liyue Harbor.",
            "Accompanied by Boo Tao, a mischievous floating spirit."
        ],
        "sources": ["Genshin Impact Liyue Story", "HoYoWiki Hu Tao"],
        "is_trending": True,
        "priority": 9
    },
    # Outfits Category
    {
        "id": "outfit_whispers_of_stars_and_smoke",
        "name": "Whispers of Stars and Smoke",
        "franchise": "Genshin Impact",
        "category": "outfit",
        "version_or_season": "Genshin 5.3",
        "title": "Citlali Signature Sleepwear: Whispers of Stars and Smoke",
        "summary": "Special sleepwear outfit designed for Citlali with soothing lavender nightgown, Citlalin sleeping mask, and plush slippers.",
        "visual_tags": {
            "outfit": "short pastel lavender nightgown dress with white lace hem and dark purple zig-zag pattern, open knee-length purple ombre shawl overcoat",
            "accessories": "Citlalin sleeping mask with folded ears pushed up on left side of head, teal chest jewel with gold necklace, pale pink bows",
            "footwear": "lavender leg warmers, plush indoor slippers"
        },
        "danbooru_prompt": "wearing Citlali Whispers of Stars and Smoke sleepwear outfit, short pastel lavender nightgown dress with white lace hem and dark purple zig-zag patterns, open knee-length purple ombre shawl overcoat, dark purple chest bow with bright teal jewel, white Citlalin sleeping mask pushed up on hair with cute folded ears, lavender leg warmers, indoor slippers",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, missing fingers, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Whispers of Stars and Smoke",
        "outfit_prompt": "Citlali Whispers of Stars and Smoke sleepwear costume, nightgown dress, Citlalin sleeping mask, purple ombre shawl",
        "lore_facts": [
            "Canonical sleepwear costume for Citlali from Masters of the Night-Wind.",
            "Features the iconic sleep mask Citlalin crafted by Night-Wind shamans."
        ],
        "sources": ["Genshin Impact 5.3 Special Program", "Natlan Lore Radar"],
        "is_trending": True,
        "priority": 10
    },
    {
        "id": "outfit_orchid_evening_gown",
        "name": "Orchid's Evening Gown",
        "franchise": "Genshin Impact",
        "category": "outfit",
        "version_or_season": "Lantern Rite",
        "title": "Ningguang Formal Attire: Orchid's Evening Gown",
        "summary": "Deep indigo and ocean blue formal evening gown worn by the Tianquan Ningguang during the Lantern Rite festival.",
        "visual_tags": {
            "outfit": "deep indigo halter evening gown, open back, golden butterfly embroidery, flowing translucent dark capelet",
            "accessories": "golden hairpin, dangling sapphire earrings",
            "footwear": "midnight blue high heels"
        },
        "danbooru_prompt": "ningguang (genshin impact), wearing orchid's evening gown, deep blue formal halter dress, backless dress, golden embroidery, butterfly motifs, sapphire hair ornament",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Orchid's Evening Gown",
        "outfit_prompt": "wearing Ningguang Orchid's Evening Gown, dark blue indigo halter dress, golden butterfly filigree",
        "lore_facts": ["Worn by Ningguang during the Liyue Lantern Rite celebrations."],
        "sources": ["Genshin Impact Lantern Rite Special"],
        "is_trending": False,
        "priority": 6
    },
    # Seasonal Anime Spotlight
    {
        "id": "anime_frieren",
        "name": "Frieren",
        "franchise": "Frieren: Beyond Journey's End",
        "category": "anime",
        "version_or_season": "Winter 2024 / 2025 Spotlight",
        "title": "Frieren the Slayer (Sousou no Frieren)",
        "summary": "Elven mage who defeated the Demon King alongside Himmel's party, now journeying to understand humans and the fleeting nature of time.",
        "visual_tags": {
            "hair": "white silver hair tied in twin low twintails, parted bangs, long elf ears",
            "eyes": "calm serene green eyes, detached wistful expression",
            "face": "youthful elf face, timeless calm gaze",
            "outfit": "white mage robe with black and gold trim, striped capelet, brown leather belt, black stockings, brown boots",
            "accessories": "red gem pendant earrings",
            "weapon": "tall wooden mage staff with brass crescent crescent moon top and red ribbon",
            "arena": "peaceful sunlit field of blue mirrortree flowers under clear blue sky"
        },
        "danbooru_prompt": "frieren (frieren: beyond journey's end), 1girl, solo, silver white hair, twin twintails, long elf ears, green eyes, white mage robe, striped capelet, holding mage staff, field of blue flowers",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, missing fingers, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Elven Traveler Mage Robe",
        "outfit_prompt": "white elven mage robe, striped capelet, tall brass crescent staff",
        "lore_facts": [
            "Over a thousand years old, student of Great Mage Flamme.",
            "Known as 'Frieren the Slayer' among demons for exterminating demonic armies."
        ],
        "sources": ["Sousou no Frieren Anime", "Weekly Anime Radar"],
        "is_trending": True,
        "priority": 9
    },
    {
        "id": "anime_sung_jinwoo",
        "name": "Sung Jin-woo",
        "franchise": "Solo Leveling",
        "category": "anime",
        "version_or_season": "Solo Leveling Season 2",
        "title": "Shadow Monarch Sung Jin-woo",
        "summary": "From the weakest E-Rank Hunter to the supreme Shadow Monarch commanding legions of shadow soldiers.",
        "visual_tags": {
            "hair": "sharp dark spiky hair, neat bangs over forehead",
            "eyes": "glowing neon electric blue eyes, cold sovereign gaze",
            "face": "sharp chiseled handsome anime face",
            "outfit": "dark charcoal trench coat, fitted black compression shirt, black combat trousers, fingerless gloves",
            "accessories": "shadow aura tendrils rising from ground",
            "weapon": "dual glowing daggers baruka's dagger and kasaka's venom fang, shadow monarch aura",
            "arena": "shattered dungeon cavern, swirling purple and black shadow army rising from mist"
        },
        "danbooru_prompt": "sung jin-woo (solo leveling), 1boy, solo, glowing blue eyes, dark hair, black trench coat, holding glowing daggers, shadow monarch aura, dark shadows rising, dungeon background",
        "negative_prompt": "1girl, female, photorealistic, 3d, deformed hands, bad anatomy, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Shadow Monarch Duster",
        "outfit_prompt": "black trench coat, dark combat attire, purple shadow tendrils",
        "lore_facts": [
            "Chosen as the vessel of Ashborn, the Monarch of Shadows.",
            "Commands legendary shadow soldiers including Igris, Iron, and Tank."
        ],
        "sources": ["Solo Leveling Anime & Manhwa", "Weekly Anime Radar"],
        "is_trending": True,
        "priority": 8
    },
    {
        "id": "anime_dandadan",
        "name": "Momo Ayase & Okarun",
        "franchise": "Dandadan",
        "category": "anime",
        "version_or_season": "Fall / Winter 2024 Dandadan",
        "title": "Occult & Alien Investigators Momo & Okarun",
        "summary": "Dynamic occult duo confronting spirits, aliens, and cursed urban legends with psychic and turbo powers.",
        "visual_tags": {
            "hair": "momo with stylish gyaru brunette bob; okarun with messy black hair and glasses",
            "eyes": "expressive high-energy anime eyes",
            "face": "dynamic expressive anime expressions",
            "outfit": "japanese high school uniform with loose socks and accessories, cursed turbo aura",
            "accessories": "spirit ward talismans, occult phone strap",
            "weapon": "psychic giant spirit hands and turbo speed sprint aura",
            "arena": "neon suburban japanese road at midnight, surreal alien geometric barrier"
        },
        "danbooru_prompt": "momo ayase (dandadan), 1girl, solo, gyaru aesthetic, brunette hair, school uniform, psychic aura, giant glowing hand, neon midnight city background",
        "negative_prompt": "photorealistic, 3d, deformed hands, bad anatomy, blurry",
        "recommended_aspect_ratio": "3:4",
        "supported_aspect_ratios": ["1:1", "3:4", "16:9", "9:16"],
        "preferred_format": "PNG",
        "outfit_name": "Occult School Uniform",
        "outfit_prompt": "Japanese school uniform, psychic barrier aura",
        "lore_facts": [
            "Granddaughter of famous medium Seiko Ayase.",
            "Combines psychic manipulation with Okarun's Turbo Granny curse speed."
        ],
        "sources": ["Dandadan Anime", "Science SARU"],
        "is_trending": True,
        "priority": 8
    }
]


class WeeklyLoreRadar:
    """
    Weekly Information & Lore Radar Engine.
    Scans, indexes, persists and synchronizes anime and Genshin lore data.
    """

    def __init__(self, radar_dir: Optional[Path] = None):
        self.radar_dir = radar_dir or LORE_RADAR_DIR
        self.radar_dir.mkdir(parents=True, exist_ok=True)
        self.characters_dir = self.radar_dir / "characters"
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.outfits_dir = self.radar_dir / "outfits"
        self.outfits_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = self.radar_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self._entries: Dict[str, LoreRadarEntry] = {}
        self._load_cached_entries()

    def _load_cached_entries(self) -> None:
        """Loads cached radar entries from disk if available."""
        # Load character entries
        for p in self.characters_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                entry = LoreRadarEntry(**data)
                self._entries[entry.id] = entry
            except Exception as e:
                logger.debug(f"Failed to load cached radar character {p.name}: {e}")

        # Load outfit entries
        for p in self.outfits_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                entry = LoreRadarEntry(**data)
                self._entries[entry.id] = entry
            except Exception as e:
                logger.debug(f"Failed to load cached radar outfit {p.name}: {e}")

    def scan_and_update(self, force_refresh: bool = False) -> WeeklyRadarReport:
        """
        Executes weekly radar scan:
        1. Indexes canonical characters, patches, outfits & anime trends.
        2. Persists JSON sheets to data/lore_radar/.
        3. Synchronizes characters into AutonomousCharacterResearcher knowledge base.
        4. Compiles and saves weekly report (JSON + Markdown).
        """
        now_dt = datetime.datetime.now()
        week_id = now_dt.strftime("%Y-W%W")
        timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Scanning and updating Weekly Lore Radar for {week_id}...")

        # Ingest canonical database
        for item in CANONICAL_LORE_DATABASE:
            entry_id = item["id"]
            if entry_id not in self._entries or force_refresh:
                item_copy = dict(item)
                item_copy["last_scanned"] = timestamp_str
                entry = LoreRadarEntry(**item_copy)
                self._entries[entry_id] = entry

                # Persist to disk
                if entry.category == "outfit":
                    out_path = self.outfits_dir / f"{entry.id}.json"
                else:
                    out_path = self.characters_dir / f"{entry.id}.json"
                out_path.write_text(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # Synchronize characters into AutonomousCharacterResearcher & data/characters/
        self._sync_with_character_researcher()

        # Group entries for weekly report
        all_entries = list(self._entries.values())
        chars = [e for e in all_entries if e.category == "character"]
        outfits = [e for e in all_entries if e.category == "outfit"]
        anime = [e for e in all_entries if e.category == "anime"]
        genshin = [e for e in all_entries if "Genshin" in e.franchise]

        report = WeeklyRadarReport(
            week_id=week_id,
            title=f"Weekly Character & Lore Radar ({week_id})",
            timestamp=timestamp_str,
            summary=(
                f"Radar tuần {week_id} cập nhật {len(all_entries)} mục tin tiêu điểm: "
                f"Genshin 5.3 Natlan (Citlali & trang phục Whispers of Stars and Smoke, Mavuika), "
                f"anime nổi bật (Frieren, Solo Leveling, Dandadan) và chuẩn hóa khung hình 1:1, 3:4, 16:9, 9:16."
            ),
            total_entries=len(all_entries),
            characters=chars,
            outfits=outfits,
            anime_spotlight=anime,
            genshin_patch=genshin,
        )

        # Save latest report JSON & week-specific JSON
        latest_json_path = self.radar_dir / "weekly_radar_latest.json"
        latest_json_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        week_json_path = self.reports_dir / f"{week_id}.json"
        week_json_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # Save Markdown Report Digest
        md_content = self.generate_markdown_report(report)
        latest_md_path = self.radar_dir / "weekly_radar_latest.md"
        latest_md_path.write_text(md_content, encoding="utf-8")

        week_md_path = self.reports_dir / f"{week_id}.md"
        week_md_path.write_text(md_content, encoding="utf-8")

        logger.info(f"Weekly Lore Radar report generated successfully at {latest_json_path} and {latest_md_path}")
        return report

    def _sync_with_character_researcher(self) -> None:
        """Syncs radar characters into the main character researcher cache."""
        try:
            researcher = get_character_researcher()
            for entry in self._entries.values():
                if entry.category not in ("character", "anime"):
                    continue

                slug = re.sub(r"[^a-z0-9_]+", "_", entry.name.lower().strip())
                char_file = researcher.cache_dir / f"{slug}.json"
                if not char_file.exists():
                    res_char = ResearchedCharacter(
                        character_id=slug,
                        display_name=entry.name,
                        franchise=entry.franchise,
                        summary=entry.summary,
                        hair_tags=entry.visual_tags.get("hair", ""),
                        eye_tags=entry.visual_tags.get("eyes", ""),
                        face_tags=entry.visual_tags.get("face", ""),
                        outfit_tags=entry.visual_tags.get("outfit", ""),
                        accessories_tags=entry.visual_tags.get("accessories", ""),
                        weapon_tags=entry.visual_tags.get("weapon", ""),
                        arena_tags=entry.visual_tags.get("arena", ""),
                        sources_consulted=entry.sources,
                        danbooru_prompt=entry.danbooru_prompt,
                        negative_prompt=entry.negative_prompt,
                        recommended_aspect_ratio=entry.recommended_aspect_ratio,
                        supported_aspect_ratios=entry.supported_aspect_ratios,
                        preferred_format=entry.preferred_format,
                        outfit_variations={
                            entry.outfit_name: {
                                "prompt": entry.outfit_prompt or "",
                                "ratio": entry.recommended_aspect_ratio
                            }
                        } if entry.outfit_name else {}
                    )
                    char_file.write_text(json.dumps(res_char.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
                    logger.info(f"Synced radar character '{entry.name}' into character repository {char_file.name}")
        except Exception as e:
            logger.warning(f"Error syncing radar characters with researcher: {e}")

    def get_latest_report(self) -> WeeklyRadarReport:
        """Retrieves or generates the latest weekly report."""
        latest_file = self.radar_dir / "weekly_radar_latest.json"
        if latest_file.exists():
            try:
                data = json.loads(latest_file.read_text(encoding="utf-8"))
                return WeeklyRadarReport(
                    week_id=data["week_id"],
                    title=data["title"],
                    timestamp=data["timestamp"],
                    summary=data["summary"],
                    total_entries=data["total_entries"],
                    characters=[LoreRadarEntry(**c) for c in data.get("characters", [])],
                    outfits=[LoreRadarEntry(**o) for o in data.get("outfits", [])],
                    anime_spotlight=[LoreRadarEntry(**a) for a in data.get("anime_spotlight", [])],
                    genshin_patch=[LoreRadarEntry(**g) for g in data.get("genshin_patch", [])],
                )
            except Exception:
                pass
        return self.scan_and_update()

    def search_radar(self, query: str, category: Optional[str] = None) -> List[LoreRadarEntry]:
        """Searches radar entries by keyword across name, title, summary, and visual tags."""
        if not self._entries:
            self.scan_and_update()

        q = query.lower().strip()
        results = []
        for entry in self._entries.values():
            if category and entry.category != category:
                continue

            # Check match in name, franchise, title, summary, or outfit
            match_pool = [
                entry.name.lower(),
                entry.franchise.lower(),
                entry.title.lower(),
                entry.summary.lower(),
                (entry.outfit_name or "").lower(),
                (entry.version_or_season or "").lower(),
            ]
            if any(q in text for text in match_pool):
                results.append(entry)

        # Sort by priority desc
        results.sort(key=lambda x: x.priority, reverse=True)
        return results

    def get_character_radar(self, character_id: str) -> Optional[LoreRadarEntry]:
        """Finds entry by character id or slug."""
        if not self._entries:
            self.scan_and_update()
        norm_id = character_id.lower().strip().replace(" ", "_")
        return self._entries.get(norm_id)

    def get_outfits(self) -> List[LoreRadarEntry]:
        """Returns all registered outfit entries."""
        if not self._entries:
            self.scan_and_update()
        return [e for e in self._entries.values() if e.category == "outfit"]

    def get_anime_spotlight(self) -> List[LoreRadarEntry]:
        """Returns all trending anime entries."""
        if not self._entries:
            self.scan_and_update()
        return [e for e in self._entries.values() if e.category == "anime"]

    def generate_markdown_report(self, report: WeeklyRadarReport) -> str:
        """Formats the weekly radar report into a readable Markdown document."""
        md = [
            f"# 📡 {report.title}",
            f"**Thời gian cập nhật:** `{report.timestamp}` | **Mã tuần:** `{report.week_id}`",
            "",
            "## 📌 Tóm tắt Xu hướng Tuần",
            f"> {report.summary}",
            "",
            "---",
            "",
            "## 🌟 1. Nhân vật & Banner Genshin Impact Tiêu điểm",
        ]

        for c in report.characters:
            md.append(f"### ✦ {c.name} ({c.version_or_season})")
            md.append(f"*{c.title}*")
            md.append(f"- **Mô tả:** {c.summary}")
            md.append(f"- **Tỉ lệ khung hình khuyến nghị:** `{c.recommended_aspect_ratio}` | **Hỗ trợ:** {', '.join(c.supported_aspect_ratios)}")
            md.append(f"- **Prompt mẫu:** `{c.danbooru_prompt}`")
            if c.outfit_name:
                md.append(f"- **Trang phục gắn liền:** `{c.outfit_name}`")
            md.append("")

        md.append("---")
        md.append("## 👗 2. Trang phục / Outfits & Biến thể mới")
        for o in report.outfits:
            md.append(f"### ✦ {o.name} ({o.franchise})")
            md.append(f"- **Chi tiết:** {o.summary}")
            md.append(f"- **Prompt trang phục:** `{o.danbooru_prompt}`")
            md.append("")

        md.append("---")
        md.append("## 🎬 3. Anime Spotlight & Nhân vật Xu hướng")
        for a in report.anime_spotlight:
            md.append(f"### ✦ {a.name} — *{a.franchise}*")
            md.append(f"- **Tóm lược:** {a.summary}")
            md.append(f"- **Visual Core:** {a.danbooru_prompt}")
            md.append("")

        md.append("---")
        md.append("## ⚙️ 4. Hỗ trợ Tỉ lệ & Định dạng tạo ảnh (Anima 2.9B ComfyUI)")
        md.append("- **Tỉ lệ khung hình:** `1:1` (1024×1024), `3:4` (768×1024), `16:9` (1344×768), `9:16` (768×1344)")
        md.append("- **Định dạng file xuất:** `PNG`, `WEBP`, `JPEG`")
        md.append("- **Cú pháp trong chat:** `vẽ [nhân vật] tỉ lệ [16:9|9:16|1:1|3:4] định dạng [webp|jpeg|png]`")

        return "\n".join(md)


_GLOBAL_RADAR: Optional[WeeklyLoreRadar] = None


def get_weekly_radar() -> WeeklyLoreRadar:
    """Singleton getter for the WeeklyLoreRadar engine."""
    global _GLOBAL_RADAR
    if _GLOBAL_RADAR is None:
        _GLOBAL_RADAR = WeeklyLoreRadar()
    return _GLOBAL_RADAR


def get_weekly_radar_report(force_refresh: bool = False) -> WeeklyRadarReport:
    """Convenience function to get or refresh the weekly radar report."""
    radar = get_weekly_radar()
    if force_refresh:
        return radar.scan_and_update(force_refresh=True)
    return radar.get_latest_report()


def check_and_refresh_weekly_radar(
    max_age_days: int = 7,
    radar: Optional[WeeklyLoreRadar] = None,
) -> Dict[str, Any]:
    """
    Lightweight startup/scheduled check for Weekly Lore Radar.
    Refreshes only if the latest report is missing, belongs to a past week, or is older than max_age_days.
    """
    engine = radar or get_weekly_radar()
    latest_file = engine.radar_dir / "weekly_radar_latest.json"
    current_week_id = datetime.datetime.now().strftime("%Y-W%W")

    needs_refresh = True
    if latest_file.exists():
        try:
            age_secs = datetime.datetime.now().timestamp() - latest_file.stat().st_mtime
            if age_secs < max_age_days * 86400:
                data = json.loads(latest_file.read_text(encoding="utf-8"))
                if data.get("week_id") == current_week_id and data.get("total_entries", 0) > 0:
                    needs_refresh = False
        except Exception as exc:
            logger.debug(f"Radar freshness check error: {exc}")

    if needs_refresh:
        report = engine.scan_and_update(force_refresh=True)
        return {
            "refreshed": True,
            "week_id": report.week_id,
            "total_entries": report.total_entries,
        }

    return {
        "refreshed": False,
        "week_id": current_week_id,
        "cached": True,
    }
