# -*- coding: utf-8 -*-
"""
Manga Anime Prompt Harmonizer & Consistency Engine
=================================================
Core module for Manga Studio resolving:
  1. Inconsistent character appearances across consecutive panels (StoryDiffusion consistency).
  2. Subpar anime stylization by enforcing 4 mandatory decomposition components per panel:
     - (1) Art Style / Medium (Authentic Japanese manga screentone, ink linework)
     - (2) Locked Character Traits (Persistent physical anchor tags)
     - (3) Emotion & Dynamic Pose (Signature anime expressions: tsundere, jaw-drop, sweatdrop, etc.)
     - (4) Background/Environment & Camera Shot (Cinematic angles, speedlines, screentone shading)
  3. Optimized prompt formulation for Animagine XL 3.1, Pony Diffusion V6, and SDXL Manga.
"""

from __future__ import annotations

import json
import hashlib
from typing import Dict, List, Any, Optional, Literal, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# 1. PRESET STYLES & MODEL CHECKPOINT CONFIGS
# ==============================================================================

MODEL_PRESETS = {
    "animagine_xl": {
        "name": "Animagine XL 3.1",
        "style_prefix": "masterpiece, best quality, very aesthetic, monochrome, greyscale, authentic japanese manga, comic, screentone, crisp lineart",
        "negative_prompt": (
            "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, "
            "cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, "
            "username, blurry, artist name, color, colored skin, photorealistic, 3d render, western cartoon"
        )
    },
    "pony_diffusion": {
        "name": "Pony Diffusion V6 XL",
        "style_prefix": "score_9, score_8_up, score_7_up, rating_safe, monochrome, greyscale, manga style, traditional media, fine ink lines, screentone halftones",
        "negative_prompt": (
            "score_4, score_5, score_6, bad anatomy, deformed limbs, extra fingers, text, watermark, "
            "blurry, color, 3d, realistic photograph, western comic, saturated"
        )
    },
    "sdxl_manga": {
        "name": "SDXL Monochrome Manga",
        "style_prefix": "authentic manga page, high contrast ink drawing, screentone shading, clean black and white, dynamic manga panel composition",
        "negative_prompt": (
            "color, colorful, painting, 3d render, photo, photorealistic, deformed, bad anatomy, "
            "blurry, out of focus, distorted face, lowres"
        )
    },
    "webtoon_color": {
        "name": "Modern Webtoon Anime Color",
        "style_prefix": "masterpiece, best quality, highres anime illustration, vibrant cel shading, modern webtoon style, crisp digital linework",
        "negative_prompt": (
            "worst quality, low quality, bad anatomy, monochrome, greyscale, sketch, rough drawing, "
            "photorealistic, 3d cgi"
        )
    },
    "dark_fantasy_manga": {
        "name": "Dark Fantasy Gothic Manga (Huyết Cơ & Kỵ Sĩ)",
        "style_prefix": (
            "masterpiece, best quality, authentic 2D anime illustration, hand-drawn dark fantasy gothic manga art, "
            "crisp cel shading, solid black ink outlines, matte textures, fine screentone halftones, "
            "cross-hatching ink shadows, muted dark fantasy gothic palette, slate iron armor, "
            "high contrast chiaroscuro, inspired by Kentaro Miura and Ayami Kojima, clean manga page"
        ),
        "negative_prompt": (
            "(photorealistic:1.4), (3d render, cgi, airbrushed:1.4), (glowing neon, neon bloom:1.4), "
            "(fractal, fractal architecture:1.4), (smooth plastic skin, oily sheen:1.4), "
            "(digital gradient shading:1.3), muddy lineart, blurry edges, soft shading, low contrast, "
            "oversaturated colors, glossy skin, artificial oily shine, western comic, deformed anatomy, "
            "messy lines, bad eyes, extra fingers, color, colorful"
        )
    },
    "genshin_shonen_action": {
        "name": "Genshin Shonen Action (Raiden Shogun / Inazuma Arc)",
        "style_prefix": (
            "masterpiece, best quality, authentic 2D anime illustration, high-energy shonen manga action, "
            "crisp anime cel shading, solid G-pen ink linework, extreme dynamic angle, foreshortening, "
            "dramatic perspective, electric lightning arcs, vibrant anime colors with deep indigo and violet tones, "
            "action speed lines, fine screentone dot shading, cinematic Japanese anime battle scene"
        ),
        "negative_prompt": (
            "(photorealistic:1.4), (3d render, cgi, airbrushed:1.4), (smooth plastic skin, oily sheen:1.4), "
            "blurry, lowres, bad anatomy, deformed hands, extra fingers, missing fingers, "
            "wrong hair color, blonde, short hair, western comic, dull lighting, flat composition"
        )
    }
}


# ==============================================================================
# 1.1. RULE OF THIRDS & NEGATIVE SPACE COMPOSITIONS
# ==============================================================================

COMPOSITION_LAYOUTS: Dict[str, Dict[str, Any]] = {
    "rule_of_thirds_left": {
        "tag": (
            "rule of thirds composition, character positioned on the left side, lower-left framing, "
            "looking towards right, off-center subject, wide negative space on upper right, "
            "empty dark background on upper-right quadrant, asymmetrical dynamic manga composition"
        ),
        "character_region": [0.35, 0.05, 0.95, 0.45],  # [ymin, xmin, ymax, xmax]
        "recommended_bubble_region": [0.08, 0.55, 0.35, 0.92],  # Top-Right quadrant
        "description_vi": "Nhân vật đứng lệch 1/3 góc trái dưới, chừa toàn bộ góc trên bên phải cho khung thoại"
    },
    "rule_of_thirds_right": {
        "tag": (
            "rule of thirds composition, character positioned on the right side, middle-right framing, "
            "looking towards left, off-center subject, wide negative space on upper left, "
            "empty dark background on upper-left quadrant, asymmetrical dynamic manga composition"
        ),
        "character_region": [0.25, 0.55, 0.90, 0.95],  # [ymin, xmin, ymax, xmax]
        "recommended_bubble_region": [0.08, 0.08, 0.35, 0.48],  # Top-Left quadrant
        "description_vi": "Nhân vật đứng lệch 1/3 góc phải, chừa toàn bộ góc trên bên trái cho khung thoại"
    },
    "wide_bottom_silhouette": {
        "tag": (
            "low angle dramatic perspective, characters positioned in the bottom third of frame, "
            "wide expansive empty space above, towering gothic ceiling and broken stained glass in upper two-thirds, "
            "massive negative space for typography and sfx, silhouette composition"
        ),
        "character_region": [0.65, 0.15, 0.95, 0.85],
        "recommended_bubble_region": [0.08, 0.20, 0.35, 0.80],  # Upper third
        "description_vi": "Góc quay thấp, nhân vật tập trung ở 1/3 đáy khung hình, 2/3 phía trên là không gian âm cho SFX và thoại"
    },
    "centered_close_up_top_clear": {
        "tag": (
            "intense close-up portrait, character face positioned in lower two-thirds of frame, "
            "high headroom, wide empty dark space at the top of the frame for speech bubbles, solid ink shadows"
        ),
        "character_region": [0.35, 0.25, 0.95, 0.75],
        "recommended_bubble_region": [0.05, 0.15, 0.25, 0.85],
        "description_vi": "Cận cảnh khuôn mặt dời xuống 2/3 dưới, chừa trần trên cao cho khung thoại"
    }
}


# ==============================================================================
# 2. ANIME EMOTION & POSE CATALOG
# ==============================================================================

ANIME_EMOTIONS: Dict[str, Dict[str, str]] = {
    "tsundere_pout": {
        "tag": "pouting, flushed cheeks, looking away, crossed arms, tsundere expression, angry blush, small frown",
        "description_vi": "Biểu cảm phồng má giận dỗi, đỏ mặt quay đi, khoanh tay đặc trưng kiểu tsundere"
    },
    "jaw_drop_shock": {
        "tag": "jaw drop, wide open mouth, extreme shock, white blank eyes, comedic scream, panic face, sweatdrop",
        "description_vi": "Há hốc mồm kinh ngạc tột độ, mắt biến thành tròng trắng, hét hoảng hốt hài hước"
    },
    "anime_sweatdrop": {
        "tag": "nervous sweatdrop on temple, forced nervous smile, trembling eyes, sheepish grin, awkward chuckle",
        "description_vi": "Giọt mồ hôi bên thái dương, nụ cười gượng gạo bối rối, ánh mắt run rẩy"
    },
    "sparkling_eyes": {
        "tag": "sparkling eyes, eyes with stars, excited smile, blush, ecstatic awe, mouth slightly open, happy energy",
        "description_vi": "Mắt lấp lánh hình ngôi sao, phấn khích ngập tràn, hào hứng tột cùng"
    },
    "chibi_panic": {
        "tag": "chibi proportions, spiral eyes, squiggly mouth, flailing arms, comical panic, tears at corner of eyes",
        "description_vi": "Tỉ lệ chibi biến hình ngộ nghĩnh, mắt xoắn ốc, miệng lượn sóng, vung vẩy tay hoảng loạn"
    },
    "dramatic_shadow": {
        "tag": "shadow over eyes, dark face shadow, intense glare, glowing pupils, ominous aura, clenched jaw",
        "description_vi": "Bóng đen che nửa trên khuôn mặt, ánh mắt phát sáng đe dọa, sát khí u ám"
    },
    "smug_grin": {
        "tag": "smug grin, sly smirk, half-closed eyes, cat mouth :3, cocky expression, raised eyebrow",
        "description_vi": "Nụ cười đắc thắng tự mãn, mắt nửa khép ranh mãnh, miệng mèo tinh quái"
    },
    "determined_focus": {
        "tag": "intense glare, clenched teeth, determined frown, focused gaze, serious stare, windblown hair",
        "description_vi": "Ánh nhìn quyết tâm đanh thép, nghiến răng tập trung cao độ, tóc bay trong gió"
    },
    "gentle_smile": {
        "tag": "gentle closed-eyes smile, soft blush, peaceful serene expression, slight tilt of head, warm aura",
        "description_vi": "Nụ cười dịu dàng nhắm mắt, ửng hồng nhẹ, thần thái ấm áp và bình yên"
    },
    "mysterious_cool": {
        "tag": "cool stoic expression, emotionless face, piercing gaze, adjusted glasses with finger, calm aura",
        "description_vi": "Thần thái điềm tĩnh lạnh lùng, đẩy kính trí thức, ánh mắt sắc bén bí ẩn"
    },
    "vampire_condescending": {
        "tag": "condescending regal smirk, half-closed crimson eyes, chin tilted up, arrogant vampire noble expression, slight fangs visible",
        "description_vi": "Nụ cười khẩy kiêu sa ngạo nghễ của nữ chúa ma cà rồng, mắt huyết sắc nửa khép, răng nanh lấp ló"
    },
    "bloodthirst_craze": {
        "tag": "wild glowing red eyes, hungry predatory grin, sharp vampire fangs, dark blood veins near temples, sinister thrill",
        "description_vi": "Ánh mắt đỏ rực cuồng nộ khát máu, nụ cười săn mồi man dại, răng nanh sắc nhọn"
    },
    "loyal_protector_rage": {
        "tag": "clenched jaw, ferocious protective roar, flaming amber eyes, windblown black hair, dark knight battle determination",
        "description_vi": "Nghiến răng gầm thét cuồng nộ để bảo vệ chủ nhân, mắt hổ phách rực lửa, khí thế kỵ sĩ bóng đêm"
    },
    "melancholy_curse": {
        "tag": "somber sorrowful gaze, eyes shadowed in grief, bitter closed-lip expression, tragic dark knight countenance",
        "description_vi": "Ánh mắt u uất bi tráng của kỵ sĩ mang huyết ấn nguyền rủa, bi thương trầm mặc"
    }
}

ANIME_POSES: Dict[str, str] = {
    "leaning_forward": "leaning forward towards camera, hands resting on knees or desk, dynamic perspective",
    "pointing_finger": "pointing finger dramatically forward, outstretched arm, confident stance",
    "turning_around": "turning head over shoulder, surprised turn, hair swaying with movement",
    "slamming_desk": "hands slammed firmly on wooden desk, leaning over with authority, tension",
    "holding_book": "holding open book with one hand, casual standing posture, scholarly look",
    "arms_crossed": "arms crossed tightly over chest, defensive proud stance, standing firm",
    "reaching_out": "one arm reaching forward towards viewer, open hand, emotional gesture",
    "whispering_secret": "hand cupped near mouth, leaning in close, confidential whispering posture",
    "running_panic": "running away in panic, looking back, dynamic motion blur, animated legs",
    "casual_seated": "seated relaxed in classroom chair, hand propping chin, looking out window",
    "drawing_cursed_blade": "drawing massive dark greatsword from back scabbard, dual handed grip, combat ready crouch",
    "holding_blood_rose": "delicate fingers holding a glowing crimson rose near lips, elegant vampire posture, standing tall",
    "shield_defend_kneel": "one knee on cracked stone ground, heavy knight shield raised, blocking incoming strike",
    "levitating_vampire": "floating slightly above floor, flowing gothic dress and dark cape, arms spread wide, dark magical presence"
}

CAMERA_SHOTS: Dict[str, str] = {
    "close_up": "close-up portrait, focusing on face expression and eyes",
    "extreme_close_up": "extreme close-up on eyes, high tension, detailed iris reflections",
    "medium_shot": "medium shot, waist up, showing upper body and hand gesture",
    "full_shot": "full length body shot, showing complete outfit and stance",
    "wide_establishing": "wide establishing shot, panoramic view of setting, environmental perspective",
    "low_angle_dramatic": "dramatic low angle shot, looking up at character, commanding presence",
    "high_angle": "high angle shot, looking down from above, vulnerability perspective",
    "over_the_shoulder": "over-the-shoulder shot, conversation depth, viewing second character",
    "dutch_angle": "dutch angle tilted camera, psychological tension, dynamic diagonal composition",
    "eye_zoom_focus": "ultra extreme macro shot focusing strictly on character eyes and gaze, cinematic eye tension",
    "backlight_silhouette": "dramatic rim lighting from behind, dark silhouette against glowing moon, mysterious contour"
}

BACKGROUND_ENVIRONMENTS: Dict[str, str] = {
    "japanese_classroom": "japanese high school classroom, rows of wooden desks, chalk blackboard, large sunny windows, fluttering curtains",
    "sunset_corridor": "long school corridor, warm sunset light streaming through windows, elongated shadows, rows of lockers",
    "school_rooftop": "school rooftop, chain-link fence, expansive sky with fluffy clouds, distant city skyline",
    "tokyo_street": "bustling tokyo street, pedestrian crossing, convenience store signs, utility poles with wires",
    "quiet_library": "silent school library, towering bookshelves, wooden study tables, dust motes in sunbeams",
    "tech_lab_office": "modern ai engineering lab, dual ultrawide monitors, illuminated server rack, whiteboard with architecture diagrams",
    "screentone_void": "minimalist abstract background, halftone dot screentone gradient, clean manga white space",
    "gothic_cathedral_ruins": "ancient gothic ruined cathedral, towering broken stained glass window with blood moon light, cracked stone pillars, crimson rose vines",
    "vampire_throne_room": "opulent dark vampire castle throne room, massive scarlet velvet throne, candelabras with violet flames, red carpet, stone gargoyles",
    "blood_moon_balcony": "gothic castle stone balcony, overlooking dark misty forest and jagged mountains, gigantic glowing blood red moon in overcast sky",
    "cursed_cemetery_mist": "foggy gothic graveyard, weathered stone crosses and angel statues, dead gnarled trees, hovering glowing red wisps",
    "crimson_eclipse_battlefield": "ruined desolate battlefield under crimson eclipse, shattered swords stuck in ground, dark swirling smoke and blood red embers"
}

VISUAL_EFFECTS: Dict[str, str] = {
    "speed_lines": "dynamic action speedlines, motion blur streaks in background, sense of rapid movement",
    "focus_burst": "radial focus lines converging on character, dramatic shock emphasis, impact effect",
    "screentone_hatch": "classic manga screentone halftones, delicate cross-hatching shadows, clean ink contrast",
    "doki_doki_aura": "floating sparkles, subtle heart shaped screentone accents, fluttery romantic aura",
    "menacing_gogogo": "dark heavy screentone aura, textured menacing shading, intense manga atmosphere",
    "blood_magic_aura": "floating crimson blood droplets, swirling scarlet energy ribbons, dark occult runic circle, dark mist",
    "demonic_blade_slash": "glowing curved scarlet blade arc, dark shadow trails, sharp dynamic sword strike effect, high contrast ink impact",
    "gothic_shadow_veil": "dramatic heavy chiaroscuro lighting, deep black ink shadows, ominous bat silhouettes, eerie gothic horror atmosphere",
    "none": ""
}


# ==============================================================================
# 3. LOCKED CHARACTER REGISTRY (CONSISTENCY ANCHORS)
# ==============================================================================

@dataclass
class CharacterAnchor:
    """Locked physical traits forming a persistent StoryDiffusion identity."""
    id: str
    name: str
    gender: Literal["male", "female", "other"]
    hair_tags: str
    eye_tags: str
    face_tags: str
    outfit_tags: str
    accessories_tags: str = ""
    consistency_token: str = ""

    def to_anchor_prompt(self) -> str:
        """Returns the invariant tag sequence that must be injected into every panel."""
        parts = []
        if self.consistency_token:
            parts.append(self.consistency_token)
        parts.extend([
            self.hair_tags,
            self.eye_tags,
            self.face_tags,
            self.outfit_tags
        ])
        if self.accessories_tags:
            parts.append(self.accessories_tags)
        return ", ".join(p for p in parts if p.strip())


DEFAULT_CHARACTERS: Dict[str, CharacterAnchor] = {
    "minh": CharacterAnchor(
        id="char_minh",
        name="Minh",
        gender="male",
        hair_tags="short messy black hair, natural front bangs",
        eye_tags="sharp dark hazel eyes, determined gaze",
        face_tags="clean handsome young male face, youthful jawline",
        outfit_tags="black gakuran jacket unbuttoned at collar, white inner shirt, loose dark trousers",
        accessories_tags="single silver stud earring in left ear",
        consistency_token="[minh_protagonist]"
    ),
    "mai": CharacterAnchor(
        id="char_mai",
        name="Mai",
        gender="female",
        hair_tags="shoulder-length wavy chestnut brown hair, side swept bangs",
        eye_tags="large expressive warm amber eyes, soft eyelashes",
        face_tags="cute feminine face, gentle cheeks",
        outfit_tags="cream knitted cardigan sweater over white collared blouse, navy pleated school skirt, red ribbon necktie",
        accessories_tags="small white flower hairpin",
        consistency_token="[mai_heroine]"
    ),
    "huy": CharacterAnchor(
        id="char_huy",
        name="Huy",
        gender="male",
        hair_tags="neat sleek silver-grey hair with left side part",
        eye_tags="narrow cold blue-grey eyes, analytical piercing gaze",
        face_tags="sharp refined aristocratic facial features",
        outfit_tags="tailored dark navy school blazer, crisp ironed white shirt, neat striped tie",
        accessories_tags="silver wire-rimmed spectacles",
        consistency_token="[huy_rival]"
    ),
    "koharu": CharacterAnchor(
        id="char_koharu",
        name="Koharu",
        gender="female",
        hair_tags="light lavender hair in twin low braids, blunt bangs",
        eye_tags="bright energetic emerald green eyes",
        face_tags="cheerful petite face, rosy cheeks",
        outfit_tags="oversized pastel hoodie with cat ears on hood, pleated mini skirt, knee-high black socks",
        accessories_tags="cyberpunk cat-ear wireless headset around neck",
        consistency_token="[koharu_mascot]"
    ),
    "carmilla": CharacterAnchor(
        id="char_carmilla",
        name="Carmilla",
        gender="female",
        hair_tags="long flowing silver-white hair with twin gothic sidelocks, micro bat-wing hair ribbons",
        eye_tags="piercing crimson red vampire eyes with slit pupils, glowing scarlet iris, elegant dark eyelashes",
        face_tags="aristocratic pale porcelain vampire face, graceful cold beauty, subtle vampire fangs, dark lipstick",
        outfit_tags="ornate Victorian gothic lolita dress, black silk and crimson velvet, layered lace corset, high ruffled collar, flared dark sleeves",
        accessories_tags="dark blood crystal choker, gothic silver rose ornament, flowing shadow silk capelet",
        consistency_token="[carmilla_vampire_sovereign]"
    ),
    "valerius": CharacterAnchor(
        id="char_valerius",
        name="Valerius",
        gender="male",
        hair_tags="messy textured midnight-black hair with jagged front bangs",
        eye_tags="intense glowing amber-gold eyes with cursed crimson flecks, brooding resolute stare",
        face_tags="chiselled warrior jawline, faint battle scar across cheek, cursed blood seal tattoo on neck",
        outfit_tags="dark gothic plate armor with silver filigree, engraved gauntlets, black chainmail undergarment, tattered midnight fur-trimmed cape",
        accessories_tags="massive blood-forged greatsword sheathed on back, iron knight signet ring",
        consistency_token="[valerius_cursed_knight]"
    ),
    "kaelen": CharacterAnchor(
        id="char_kaelen",
        name="Hắc Kỵ Sĩ Kaelen",
        gender="male",
        hair_tags="messy jet-black hair with fallen bangs",
        eye_tags="sharp amber-gold eyes, determined intense stare",
        face_tags="faint battle scar across bridge of nose, cursed warrior face",
        outfit_tags="full gothic black steel plate armor engraved with glowing crimson runes, tattered crimson cape fluttering",
        accessories_tags="demonic greatsword with blood aura",
        consistency_token="[kaelen_blood_knight]"
    ),
    "lucian": CharacterAnchor(
        id="char_lucian",
        name="Giáo Đầu Thánh Điện Lucian",
        gender="male",
        hair_tags="short slicked-back blonde hair",
        eye_tags="cold steely grey eyes, stern righteous scowl",
        face_tags="sharp aristocratic holy inquisitor features",
        outfit_tags="ornate silver holy knight plate armor, white silk cape with golden cross embroidery",
        accessories_tags="sacred silver rapier glowing with holy light",
        consistency_token="[lucian_silver_inquisitor]"
    ),
    "vivian": CharacterAnchor(
        id="char_vivian",
        name="Huyết Linh Pháp Sư Vivian",
        gender="female",
        hair_tags="twin high dark purple buns, blunt bangs",
        eye_tags="glowing violet eyes, playful mischievous wink",
        face_tags="cute petite alchemist face, youthful porcelain skin",
        outfit_tags="gothic lolita witch dress, layered dark petticoats",
        accessories_tags="floating bat familiars, arcane blood grimoire and crystal wand",
        consistency_token="[vivian_blood_alchemist]"
    ),
    "raiden_shogun": CharacterAnchor(
        id="char_raiden_shogun",
        name="Raiden Shogun (Raiden Ei / Lôi Điện Tướng Quân)",
        gender="female",
        hair_tags="very long dark purple hair fading to electric lavender tips, single thick braid hanging down back, blunt symmetrical front bangs, framing side strands",
        eye_tags="deep royal purple anime eyes with divine intensity, glowing electric violet pupils, subtle electro mitsudomoe iris ring",
        face_tags="flawless aristocratic anime face, distinct beauty mark mole under right eye, serene divine sovereign expression",
        outfit_tags="short lavender and royal purple kimono dress with gold cloud patterns, asymmetrical long flowing sleeve, dark purple sheer bodysuit underneath, wide purple obi sash with crimson braided cord and gold mitsudomoe crest, single curved black and gold pauldron on left shoulder, purple thighhighs with gold floral embroidery",
        accessories_tags="golden fan-shaped hairpin with purple morning glory flower and hanging tassel on right side, floating chakra desiderata ring behind back with glowing electro tomoe marks, holding musou isshin katana crackling with purple lightning",
        consistency_token="[raiden_shogun_genshin]"
    )
}

# Alias mappings for convenience
DEFAULT_CHARACTERS["huyet_co"] = DEFAULT_CHARACTERS["carmilla"]
DEFAULT_CHARACTERS["blood_princess"] = DEFAULT_CHARACTERS["carmilla"]
DEFAULT_CHARACTERS["ky_si"] = DEFAULT_CHARACTERS["kaelen"]
DEFAULT_CHARACTERS["vampire_knight"] = DEFAULT_CHARACTERS["kaelen"]
DEFAULT_CHARACTERS["hac_ky_si"] = DEFAULT_CHARACTERS["kaelen"]
DEFAULT_CHARACTERS["inquisitor"] = DEFAULT_CHARACTERS["lucian"]
DEFAULT_CHARACTERS["blood_alchemist"] = DEFAULT_CHARACTERS["vivian"]
DEFAULT_CHARACTERS["raiden"] = DEFAULT_CHARACTERS["raiden_shogun"]
DEFAULT_CHARACTERS["ei"] = DEFAULT_CHARACTERS["raiden_shogun"]
DEFAULT_CHARACTERS["loi_than"] = DEFAULT_CHARACTERS["raiden_shogun"]




# ==============================================================================
# 4. DECOMPOSED PANEL PROMPT BUILDER
# ==============================================================================

@dataclass
class DecomposedPanelPrompt:
    """Structured 4-component panel prompt representation with spatial composition."""
    panel_number: int
    art_style_component: str
    character_traits_component: str
    emotion_and_pose_component: str
    background_and_camera_component: str
    full_positive_prompt: str
    full_negative_prompt: str
    model_preset: str
    consistency_hash: str
    composition_key: str = "default"
    character_region: List[float] = field(default_factory=lambda: [0.30, 0.25, 0.90, 0.75])
    recommended_bubble_region: List[float] = field(default_factory=lambda: [0.08, 0.55, 0.35, 0.92])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MangaAnimePromptGenerator:
    """Engine to assemble consistent, authentic anime manga panel prompts."""

    def __init__(self, character_registry: Optional[Dict[str, CharacterAnchor]] = None):
        self.characters = dict(DEFAULT_CHARACTERS)
        if character_registry:
            self.characters.update(character_registry)

    def register_character(self, anchor: CharacterAnchor) -> None:
        self.characters[anchor.id.lower()] = anchor
        self.characters[anchor.name.lower()] = anchor

    def build_panel_prompt(
        self,
        panel_number: int = 1,
        character_names: Optional[List[str]] = None,
        emotion_key: str = "determined_focus",
        pose_key: str = "leaning_forward",
        camera_key: str = "medium_shot",
        background_key: str = "japanese_classroom",
        vfx_key: str = "screentone_hatch",
        model_preset: str = "animagine_xl",
        composition_key: Optional[str] = None,
        extra_positive: str = "",
        extra_negative: str = "",
    ) -> DecomposedPanelPrompt:
        """Constructs a decomposed 4-component panel prompt adhering to manga standards."""
        preset = MODEL_PRESETS.get(model_preset, MODEL_PRESETS["animagine_xl"])

        # 1. Art Style / Medium Component
        style_comp = preset["style_prefix"]
        if vfx_key in VISUAL_EFFECTS and VISUAL_EFFECTS[vfx_key]:
            style_comp += f", {VISUAL_EFFECTS[vfx_key]}"

        # 2. Locked Character Traits Component (StoryDiffusion consistency)
        char_prompts = []
        if character_names:
            for c_name in character_names:
                c_key = c_name.strip().lower()
                anchor = self.characters.get(c_key)
                if anchor:
                    char_prompts.append(anchor.to_anchor_prompt())
                else:
                    char_prompts.append(f"{c_name}, anime character")
            char_comp = " AND ".join(char_prompts) if len(char_prompts) > 1 else char_prompts[0]
        else:
            char_comp = "1person, anime character"

        # 3. Emotion & Pose Component
        emotion_data = ANIME_EMOTIONS.get(emotion_key, ANIME_EMOTIONS["determined_focus"])
        pose_str = ANIME_POSES.get(pose_key, ANIME_POSES["leaning_forward"])
        emotion_pose_comp = f"{emotion_data['tag']}, {pose_str}"

        # 4. Background / Environment & Camera Shot Component
        camera_str = CAMERA_SHOTS.get(camera_key, CAMERA_SHOTS["medium_shot"])
        bg_str = BACKGROUND_ENVIRONMENTS.get(background_key, BACKGROUND_ENVIRONMENTS["japanese_classroom"])
        bg_camera_comp = f"{camera_str}, {bg_str}"

        # 5. Composition & Negative Space (Rule of Thirds)
        char_reg = [0.30, 0.25, 0.90, 0.75]
        bubble_reg = [0.08, 0.55, 0.35, 0.92]
        comp_tag = ""
        comp_k = composition_key or "default"
        if composition_key and composition_key in COMPOSITION_LAYOUTS:
            c_info = COMPOSITION_LAYOUTS[composition_key]
            comp_tag = c_info["tag"]
            char_reg = list(c_info["character_region"])
            bubble_reg = list(c_info["recommended_bubble_region"])

        # Assemble Full Positive Prompt
        parts = [
            style_comp,
            char_comp,
            emotion_pose_comp,
            bg_camera_comp
        ]
        if comp_tag:
            parts.append(comp_tag)
        if extra_positive.strip():
            parts.append(extra_positive.strip())

        full_positive = ", ".join(parts)

        # Assemble Full Negative Prompt
        neg_parts = [preset["negative_prompt"]]
        if extra_negative.strip():
            neg_parts.append(extra_negative.strip())
        full_negative = ", ".join(neg_parts)

        # Consistency hash (for verifying character anchor persistence across panels)
        consistency_str = f"{char_comp}::{model_preset}"
        consistency_hash = hashlib.sha256(consistency_str.encode("utf-8")).hexdigest()[:12]

        return DecomposedPanelPrompt(
            panel_number=panel_number,
            art_style_component=style_comp,
            character_traits_component=char_comp,
            emotion_and_pose_component=emotion_pose_comp,
            background_and_camera_component=bg_camera_comp,
            full_positive_prompt=full_positive,
            full_negative_prompt=full_negative,
            model_preset=model_preset,
            consistency_hash=consistency_hash,
            composition_key=comp_k,
            character_region=char_reg,
            recommended_bubble_region=bubble_reg
        )

    def harmonize_scene_panels(
        self,
        scene_description: str,
        panel_configs: List[Dict[str, Any]],
        model_preset: str = "animagine_xl"
    ) -> List[DecomposedPanelPrompt]:
        """Harmonizes an entire sequence of panels to ensure character & style consistency."""
        results = []
        for idx, cfg in enumerate(panel_configs, 1):
            panel_prompt = self.build_panel_prompt(
                panel_number=idx,
                character_names=cfg.get("characters", []),
                emotion_key=cfg.get("emotion", "determined_focus"),
                pose_key=cfg.get("pose", "leaning_forward"),
                camera_key=cfg.get("camera", "medium_shot"),
                background_key=cfg.get("background", "japanese_classroom"),
                vfx_key=cfg.get("vfx", "screentone_hatch"),
                model_preset=model_preset,
                composition_key=cfg.get("composition_key", None),
                extra_positive=cfg.get("extra_positive", ""),
                extra_negative=cfg.get("extra_negative", "")
            )
            results.append(panel_prompt)
        return results


# ==============================================================================
# 5. COT STORYBOARD DATASET GENERATOR
# ==============================================================================

SYSTEM_STORYBOARD_COT_PROMPT = (
    "Bạn là Đạo diễn Diễn hoạt Manga & Kỹ sư Prompt Anime cao cấp trong Manga Studio. "
    "Khi nhận được kịch bản phân cảnh thô, hãy luôn suy luận từng bước trong thẻ <think> ... </think>:\n"
    "1. Phân tích nhịp điệu kể chuyện và chia khung ô tranh (Panel Breakdown) theo luồng đọc Manga Nhật Bản (Right-to-Left, Top-to-Bottom).\n"
    "2. Khóa chặt đặc tính ngoại hình nhân vật (Locked Character Consistency Anchors) theo chuẩn StoryDiffusion để tránh vẽ sai người.\n"
    "3. Bóc tách 4 thành phần bắt buộc cho mỗi ô tranh: (1) Art Style/Medium, (2) Character Anchor, (3) Emotion & Pose, (4) Background & Camera Shot.\n"
    "4. Tối ưu hóa prompt tiếng Anh cho checkpoint ComfyUI (Animagine XL 3.1 / Pony Diffusion / SDXL Manga).\n"
    "Sau đó xuất ra bảng kế hoạch phân cảnh và danh sách Prompt ComfyUI chuẩn xác."
)


def generate_cot_storyboard_sample(
    scene_id: int,
    story_theme: str,
    characters: List[str],
    panels_data: List[Dict[str, Any]],
    model_preset: str = "animagine_xl"
) -> Dict[str, Any]:
    """Generates a high-quality CoT training sample for storyboard reasoning."""
    generator = MangaAnimePromptGenerator()
    decomposed_panels = generator.harmonize_scene_panels(
        scene_description=story_theme,
        panel_configs=panels_data,
        model_preset=model_preset
    )

    user_query = (
        f"Hãy thiết kế phân cảnh Storyboard manga chi tiết và sinh prompt ComfyUI chuyên nghiệp cho phân đoạn sau:\n"
        f"- Bối cảnh/Cốt truyện: {story_theme}\n"
        f"- Nhân vật tham gia: {', '.join(characters)}\n"
        f"- Mục tiêu: Đảm bảo nhân vật giữ nguyên ngoại hình nhất quán (Character Consistency) "
        f"và tuân thủ cấu trúc phân rã 4 thành phần bắt buộc cho từng Panel."
    )

    think_steps = [
        "<think>",
        f"1. Phân tích kịch bản & Mục tiêu diễn hoạt:",
        f"- Cốt truyện chính: {story_theme}",
        f"- Nhân vật trọng tâm: {', '.join(characters)}.",
        f"- Định hướng bố cục: Chia làm {len(panels_data)} ô tranh (panels) tạo nhịp kịch tính tăng dần theo thị giác manga Nhật.",
        "",
        "2. Thiết lập Khung neo ngoại hình nhất quán (StoryDiffusion Consistency Anchors):"
    ]

    for char_name in characters:
        anchor = generator.characters.get(char_name.lower())
        if anchor:
            think_steps.append(
                f"- Nhân vật [{anchor.name}]: Tóc ({anchor.hair_tags}), Mắt ({anchor.eye_tags}), "
                f"Khuôn mặt ({anchor.face_tags}), Trang phục ({anchor.outfit_tags}). "
                f"Anchor token: '{anchor.consistency_token}'."
            )

    think_steps.extend([
        "",
        "3. Phân rã 4 thành phần bắt buộc cho từng Panel:"
    ])

    for p in decomposed_panels:
        think_steps.extend([
            f"  * Ô {p.panel_number}:",
            f"    - (1) Art Style/Medium: {p.art_style_component}",
            f"    - (2) Locked Traits: {p.character_traits_component}",
            f"    - (3) Emotion & Pose: {p.emotion_and_pose_component}",
            f"    - (4) Background & Camera: {p.background_and_camera_component}",
            f"    => Consistency Hash: {p.consistency_hash}"
        ])

    think_steps.extend([
        "",
        "4. Kiểm tra độ đồng nhất (Consistency Check):",
        f"- Toàn bộ {len(panels_data)} panel đều sử dụng chung bộ Locked Character Traits và Model Preset '{model_preset}'.",
        "- Negative prompt được cấu hình chặn hoàn toàn lỗi biến dạng giải phẫu và phong cách 3D/realistic.",
        "</think>"
    ])

    think_content = "\n".join(think_steps)

    # Response outside <think>
    response_lines = [
        f"### Kế hoạch Phân cảnh Storyboard Manga: \"{story_theme}\"\n",
        f"**Số lượng ô tranh:** {len(decomposed_panels)} panels | **Model Checkpoint:** {MODEL_PRESETS[model_preset]['name']}\n"
    ]

    for p in decomposed_panels:
        response_lines.extend([
            f"#### [Panel {p.panel_number}]",
            f"- **Phân rã 4 thành phần:**",
            f"  1. *Art Style/Medium:* `{p.art_style_component}`",
            f"  2. *Locked Character Traits:* `{p.character_traits_component}`",
            f"  3. *Emotion & Pose:* `{p.emotion_and_pose_component}`",
            f"  4. *Background & Camera Shot:* `{p.background_and_camera_component}`",
            f"- **Positive Prompt (ComfyUI):**",
            f"  ```text",
            f"  {p.full_positive_prompt}",
            f"  ```",
            f"- **Negative Prompt:**",
            f"  ```text",
            f"  {p.full_negative_prompt}",
            f"  ```\n"
        ])

    final_response = f"{think_content}\n\n" + "\n".join(response_lines)

    sample_id = f"manga_storyboard_cot_{scene_id:05d}"
    return {
        "id": sample_id,
        "category": "manga_storyboard_consistency",
        "difficulty": "hard",
        "messages": [
            {"role": "system", "content": SYSTEM_STORYBOARD_COT_PROMPT},
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": final_response}
        ],
        "text": (
            f"<|im_start|>system\n{SYSTEM_STORYBOARD_COT_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user_query}<|im_end|>\n"
            f"<|im_start|>assistant\n{final_response}<|im_end|>"
        )
    }


# ==============================================================================
# 6. V7 AUTHORITATIVE VAMPIRE KNIGHT SCENE SPECIFICATION
# ==============================================================================

def get_vampire_knight_v7_scene_specification() -> Dict[str, Any]:
    """
    Returns the authoritative V7 3-panel storyboard specification for 'Huyết Cơ và Kỵ Sĩ',
    eliminating AI plastic look and guaranteeing zero face collision via Rule of Thirds Negative Space.
    """
    generator = MangaAnimePromptGenerator()

    panel_1_prompt = generator.build_panel_prompt(
        panel_number=1,
        character_names=["kaelen"],
        emotion_key="determined_focus",
        pose_key="pointing_finger",
        camera_key="low_angle_dramatic",
        background_key="gothic_cathedral_ruins",
        vfx_key="screentone_hatch",
        model_preset="dark_fantasy_manga",
        composition_key="rule_of_thirds_left",
        extra_positive="authentic 2D anime illustration, hand-drawn manga page, solid ink contours, matte slate iron armor, dark shadows, negative space on upper right"
    )

    panel_2_prompt = generator.build_panel_prompt(
        panel_number=2,
        character_names=["carmilla"],
        emotion_key="mysterious_cool",
        pose_key="arms_crossed",
        camera_key="close_up",
        background_key="vampire_throne_room",
        vfx_key="screentone_hatch",
        model_preset="dark_fantasy_manga",
        composition_key="rule_of_thirds_right",
        extra_positive="authentic 2D anime illustration, hand-drawn manga page, porcelain pale matte skin, silver hair, crimson velvet gown, negative space on upper left"
    )

    panel_3_prompt = generator.build_panel_prompt(
        panel_number=3,
        character_names=["kaelen", "carmilla"],
        emotion_key="determined_focus",
        pose_key="leaning_forward",
        camera_key="wide_establishing",
        background_key="crimson_eclipse_battlefield",
        vfx_key="speed_lines",
        model_preset="dark_fantasy_manga",
        composition_key="wide_bottom_silhouette",
        extra_positive="authentic 2D anime illustration, hand-drawn manga page, characters positioned in bottom third, massive dark sky and cathedral ceiling in upper space for sfx and dialogue"
    )

    return {
        "title": "Huyết Cơ Và Kỵ Sĩ - Bản V7 Chuẩn Mỹ Thuật 2D Manga",
        "panels": [
            {
                "panel_number": 1,
                "speaker": "Hắc Kỵ Sĩ Kaelen",
                "dialogue": "Kẻ nào dám mạo phạm Huyết Cơ, thanh kiếm này sẽ chém đứt linh hồn kẻ đó!",
                "bubble_type": "shout_burst",
                "sfx": "CHOẢNG!",
                "composition": "rule_of_thirds_left",
                "character_zone": [0.35, 0.05, 0.95, 0.45],  # Lower-Left
                "safe_bubble_zone": [0.08, 0.55, 0.35, 0.92],  # Upper-Right (Clearance Distance >= 35px)
                "prompt_plan": panel_1_prompt.to_dict()
            },
            {
                "panel_number": 2,
                "speaker": "Huyết Cơ Carmilla",
                "dialogue": "Ngươi nghĩ lưỡi kiếm rỉ sét của Thánh Điện có thể chạm được vào ta sao?",
                "bubble_type": "speech_oval",
                "sfx": "THÌNH THỊCH!",
                "composition": "rule_of_thirds_right",
                "character_zone": [0.25, 0.55, 0.90, 0.95],  # Middle-Right
                "safe_bubble_zone": [0.08, 0.08, 0.35, 0.48],  # Upper-Left (Clearance Distance >= 35px)
                "prompt_plan": panel_2_prompt.to_dict()
            },
            {
                "panel_number": 3,
                "speaker": "Lời dẫn / Huyết Cơ",
                "dialogue": "Đêm nay... Mặt trăng máu sẽ nuốt chửng giáo đường này!",
                "bubble_type": "narration_rect",
                "sfx": "XOẸT!",
                "composition": "wide_bottom_silhouette",
                "character_zone": [0.65, 0.15, 0.95, 0.85],  # Bottom Third
                "safe_bubble_zone": [0.08, 0.20, 0.30, 0.80],  # Upper Third (Clearance Distance >= 40px)
                "prompt_plan": panel_3_prompt.to_dict()
            }
        ]
    }


def get_raiden_shogun_genshin_scene_specification() -> Dict[str, Any]:
    """
    Returns the complete 3-Tier Benchmark Specification for Raiden Shogun (Genshin Impact):
      - Test 1 (Baseline): Zero-shot recognition test.
      - Test 2 (Canonical Portrait): Full locked Danbooru visual anchors & mole under eye.
      - Test 3 (Combat Action): High-octane Shonen battle action in Plane of Euthymia.
    """
    json_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            pass

    # Built-in fallback specification
    generator = MangaAnimePromptGenerator()
    return {
        "character_id": "raiden_shogun",
        "full_name": "Raiden Shogun (Raiden Ei / Lôi Điện Tướng Quân)",
        "origin": "Genshin Impact (HoYoverse)",
        "model_preset": "genshin_shonen_action",
        "benchmark_tests": [
            {
                "id": "test_1_baseline",
                "output_filename": "raiden_baseline.png",
                "character": "raiden_shogun",
                "composition": "center_close_up",
                "prompt": (
                    "raiden_shogun_(genshin_impact), 1girl, solo, purple hair, long hair, "
                    "single braid, purple eyes, kimono, looking at viewer, authentic 2D anime illustration, crisp cel shading"
                ),
                "negative_prompt": "lowres, bad anatomy, blurry, 3d render, western comic, deformed"
            },
            {
                "id": "test_2_canonical_portrait",
                "output_filename": "raiden_canonical_portrait.png",
                "character": "raiden_shogun",
                "composition": "rule_of_thirds_right",
                "prompt": (
                    "masterpiece, best quality, authentic 2D anime illustration, raiden_shogun_(genshin_impact), 1girl, solo, "
                    "close-up portrait, purple hair, very long hair, single braid, purple eyes, mole under eye, "
                    "hair flower, golden fan hairpin, purple tassel, purple kimono, single pauldron, shoulder armor, "
                    "crisp cel shading, solid G-pen ink lines, fine screentone, matte skin, neutral divine expression"
                ),
                "negative_prompt": (
                    "(photorealistic:1.4), (3d render, cgi:1.4), (plastic skin:1.3), blonde hair, twintails, "
                    "short hair, western armor, blurry, lowres, bad anatomy, deformed"
                )
            },
            {
                "id": "test_3_combat_action",
                "output_filename": "raiden_combat_action.png",
                "character": "raiden_shogun",
                "composition": "rule_of_thirds_left",
                "prompt": (
                    "masterpiece, best quality, authentic 2D anime illustration, high-energy shonen action manga style, "
                    "raiden_shogun_(genshin_impact), 1girl, solo, dynamic combat pose, holding katana, musou isshin, "
                    "sword slash, unleashing purple lightning storm, electric arcs, glowing violet eyes, single braid flying, "
                    "purple kimono with detached sleeves, single pauldron, thighhighs, background is plane of euthymia, "
                    "surreal red sky, floating cracked torii gates, shattered obsidian floor with electric reflections, "
                    "dramatic Dutch angle, extreme foreshortening, action speed lines, solid black ink contours, vibrant cel shading"
                ),
                "negative_prompt": (
                    "(photorealistic:1.4), (3d render, cgi, airbrushed:1.4), (plastic skin:1.3), blonde hair, loose hair, "
                    "twin tails, western sword, shield, western knight armor, dull lighting, bad hands, extra fingers, blurry, lowres"
                )
            }
        ]
    }
