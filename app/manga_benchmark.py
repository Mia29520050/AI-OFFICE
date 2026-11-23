from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field

# ==============================================================================
# 1. Pydantic Schemas for Benchmark Specifications
# ==============================================================================

class CharacterBenchmarkSpec(BaseModel):
    """Specification of the reference character for model consistency benchmarking."""
    id: str = "char_minh_ref"
    name: str = "Minh"
    full_name: str = "Kurogane Minh"
    role: str = "Protagonist"
    gender: str = "1boy"
    age: int = 16
    archetype: str = "High school second-year student, perceptive, cautious, determined"
    physical_locked_traits: dict[str, Any] = Field(default_factory=lambda: {
        "hair_color": "black",
        "hair_style": "messy short hair with natural tufts and side bangs",
        "eye_color": "sharp amber brown",
        "eye_shape": "sharp focused gaze, slightly upturned outer corners",
        "build": "slender athletic teenage frame, height ~174cm",
        "skin_tone": "fair East-Asian complexion, subtle natural shadows"
    })
    costume_locked_traits: dict[str, Any] = Field(default_factory=lambda: {
        "shirt": "crisp white collared school dress shirt",
        "tie": "dark navy blue necktie tied neatly",
        "blazer": "tailored navy blue blazer with gold button accents",
        "trousers": "straight-leg charcoal dark grey school trousers",
        "footwear": "dark brown leather school loafers",
        "forbidden_attire": ["skirt", "blouse with frills", "cardigan", "bright casual clothing"]
    })
    trigger_tags: str = (
        "minh_character, 1boy, 16yo, slender teen, messy short black hair, side bangs, "
        "sharp amber eyes, white collared shirt, dark navy blue necktie, navy blue blazer, charcoal grey trousers"
    )
    negative_prompt: str = (
        "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, "
        "cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, "
        "username, blurry, artist name, realistic, 3d, photorealistic, deformed, bad proportions, "
        "female clothes, skirt, blonde hair, blue eyes, disfigured, extra limbs"
    )


class BenchmarkTestCase(BaseModel):
    """Specification for each standardized benchmark test case."""
    test_id: str
    case_number: int
    title: str
    category: Literal[
        "portrait", "fullbody", "classroom_environment", "multi_character",
        "camera_angles", "bw_manga", "color_anime", "sequential_continuity"
    ]
    evaluation_focus: str
    target_hardware: str = "RTX 3050 Laptop 6GB VRAM / 12GB RAM"
    art_style: Literal["manga_bw", "anime_color"] = "anime_color"
    prompt_positive: str
    prompt_negative: str
    recommended_resolution: tuple[int, int] = (768, 1024)
    aspect_ratio: str = "3:4"
    recommended_steps: int = 24
    recommended_cfg: float = 7.0
    sampler_name: str = "euler_ancestral"
    scheduler: str = "karras"
    sequential_panels: list[dict[str, Any]] | None = None
    pass_criteria: list[str] = Field(default_factory=list)


# ==============================================================================
# 2. Standardized Reference Character: Minh
# ==============================================================================

MINH_REFERENCE_SPEC = CharacterBenchmarkSpec()


# ==============================================================================
# 3. Standardized 8 Test Cases Definition
# ==============================================================================

BENCHMARK_TEST_CASES: list[BenchmarkTestCase] = [
    # Case 1: Portrait / Close-up
    BenchmarkTestCase(
        test_id="tc1_portrait",
        case_number=1,
        title="Minh - Expressive Portrait & Facial Feature Fidelity",
        category="portrait",
        evaluation_focus="Facial micro-details, amber iris highlights, messy hair strand fidelity, skin tonal transition, clean lineart",
        art_style="anime_color",
        recommended_resolution=(768, 1024),
        aspect_ratio="3:4",
        recommended_steps=24,
        recommended_cfg=7.0,
        prompt_positive=(
            "masterpiece, best quality, highres, close-up portrait, 1boy, minh_character, 16yo, "
            "messy short black hair with delicate strands, sharp amber eyes with detailed iris highlights, "
            "determined thoughtful expression, clean jawline, subtle rim lighting, white collared shirt, "
            "navy blue tie knot visible at collar, dramatic soft shadows, depth of field, anime key visual, 8k resolution"
        ),
        prompt_negative=(
            "lowres, bad anatomy, bad eyes, asymmetric pupils, crossed eyes, extra ears, blurry, "
            "low quality, 3d render, photorealistic, deformed mouth, messy linework, flat shading, disfigured"
        ),
        pass_criteria=[
            "Amber eye color is clearly discernible with sharp pupils",
            "Short black hair has defined individual tufts, not a solid black blob",
            "Facial anatomy is symmetrical and free of melting/blurring",
            "White shirt collar and navy tie knot are accurately rendered"
        ]
    ),

    # Case 2: Full-Body Anatomy & Costume
    BenchmarkTestCase(
        test_id="tc2_fullbody",
        case_number=2,
        title="Minh - Full-Body Anatomy & Uniform Integrity",
        category="fullbody",
        evaluation_focus="Head-to-height ratio (1:7.5), hand anatomy (5 distinct fingers), trousers vs skirt check, footwear clarity",
        art_style="anime_color",
        recommended_resolution=(768, 1152),
        aspect_ratio="2:3",
        recommended_steps=26,
        recommended_cfg=7.0,
        prompt_positive=(
            "masterpiece, best quality, highres, full body shot, 1boy standing, minh_character, "
            "16yo slender athletic build, messy short black hair, sharp amber eyes, confident relaxed standing pose, "
            "hands resting naturally at sides with 5 fingers, crisp white collared shirt, dark navy blue necktie, "
            "fitted navy blue school blazer with gold buttons, charcoal grey straight-leg trousers with realistic fabric creases, "
            "dark leather loafers, neutral light grey background, full figure visible from head to shoes"
        ),
        prompt_negative=(
            "lowres, bad anatomy, bad hands, missing fingers, extra limbs, bad feet, distorted shoes, "
            "cropped head, cropped feet, skirt, feminine clothing, disproportionate limbs, blurry, 3d render"
        ),
        pass_criteria=[
            "Full figure visible from head to shoes without cropping",
            "Trousers are clearly rendered (no skirts or dress artifacts)",
            "Hands have exactly 5 fingers without webbed or fused joints",
            "Proportions conform to classic Japanese anime teenage aesthetics"
        ]
    ),

    # Case 3: Classroom Environmental Storytelling
    BenchmarkTestCase(
        test_id="tc3_classroom",
        case_number=3,
        title="Classroom Interior - Perspective & Lighting Integration",
        category="classroom_environment",
        evaluation_focus="Vanishing point alignment, window sunlight beam interaction, natural character grounding, no floating desks",
        art_style="anime_color",
        recommended_resolution=(1024, 768),
        aspect_ratio="4:3",
        recommended_steps=28,
        recommended_cfg=7.5,
        prompt_positive=(
            "masterpiece, best quality, highres, interior wide shot, Japanese high school classroom in bright morning sunlight, "
            "1boy, minh_character, sitting by open window on wooden school chair, head turned looking out window, "
            "messy short black hair caught in gentle morning breeze, white curtains fluttering, "
            "warm golden sunbeams streaming across wooden floorboards, detailed wooden student desks, "
            "chalkboard in background with faded mathematical formulas, dust motes dancing in sunlight, "
            "nostalgic cinematic anime atmosphere, Makoto Shinkai lighting aesthetic, high contrast soft shadows"
        ),
        prompt_negative=(
            "lowres, bad architecture, distorted perspective, floating furniture, warped windows, "
            "bad anatomy, cluttered artifacts, blurry background, flat lighting, 3d render"
        ),
        pass_criteria=[
            "Perspective grid aligns naturally toward the window/chalkboard",
            "Sunlight angle matches the shadow cast by the desk and character",
            "Minh is correctly seated without clipping through furniture",
            "Classroom details (chalkboard, desks, curtains) are crisp and identifiable"
        ]
    ),

    # Case 4: Two Characters Interaction & Identity Separation
    BenchmarkTestCase(
        test_id="tc4_two_characters",
        case_number=4,
        title="Two Characters - Identity Bleed & Interaction Check",
        category="multi_character",
        evaluation_focus="Zero feature contamination (no hair/outfit bleed between boy and girl), mutual gaze direction, scale balance",
        art_style="anime_color",
        recommended_resolution=(1024, 768),
        aspect_ratio="4:3",
        recommended_steps=28,
        recommended_cfg=7.0,
        prompt_positive=(
            "masterpiece, best quality, highres, two characters interacting in classroom, "
            "(minh_character:1.1: 1boy, messy short black hair, sharp amber eyes, navy blazer, dark trousers), "
            "standing and talking to (mai_character:1.1: 1girl, shoulder-length brown hair, soft brown eyes, "
            "white blouse, cream cardigan, navy pleated skirt), distinct character appearances, "
            "boy looking down with serious expression, girl smiling warmly holding school notebook, "
            "natural space between characters, classroom desks background, clean separation of clothing and hair"
        ),
        prompt_negative=(
            "lowres, bad anatomy, fused bodies, cloned characters, cross-eyed, feature bleed, "
            "boy wearing skirt, girl wearing trousers, tangled limbs, extra arms, bad hands, blurry"
        ),
        pass_criteria=[
            "Boy and girl maintain strict individual identity (boy in dark trousers, girl in pleated skirt)",
            "No color bleeding between black hair (boy) and brown hair (girl)",
            "No fused limbs or extra arms between the two subjects",
            "Clear spatial separation and conversational body language"
        ]
    ),

    # Case 5: Dynamic Camera Angles (Extreme Perspective)
    BenchmarkTestCase(
        test_id="tc5_camera_angles",
        case_number=5,
        title="Dynamic Low-Angle / Dutch Tilt - Extreme Perspective Foreshortening",
        category="camera_angles",
        evaluation_focus="Foreshortening under wide-angle lens, dramatic low perspective from floor level, upward shadow casting",
        art_style="anime_color",
        recommended_resolution=(768, 1024),
        aspect_ratio="3:4",
        recommended_steps=26,
        recommended_cfg=7.5,
        prompt_positive=(
            "masterpiece, best quality, dramatic dynamic low-angle worm's-eye shot looking up, "
            "1boy, minh_character, standing tall and imposing in center frame, intense focused downward gaze, "
            "foreshortened perspective, messy black hair framing face against school ceiling lights, "
            "navy blue blazer billowing slightly, crisp white shirt and tie, sharp ink lineart, "
            "high contrast anime lighting, dramatic shadows cast upwards, cinematic anime keyframe, Studio Trigger dynamic composition"
        ),
        prompt_negative=(
            "lowres, bad anatomy, broken perspective, warped body, flat angle, straight shot, "
            "blurry, missing limbs, distorted proportions, low quality, 3d render"
        ),
        pass_criteria=[
            "Extreme low-angle perspective looking upward is convincingly maintained",
            "Foreshortened limbs maintain correct proportional anatomy",
            "Face retains Minh's signature sharp amber eyes and short black hair",
            "Lighting conforms to overhead school ceiling lights"
        ]
    ),

    # Case 6: Classic Black & White Manga Screentoning
    BenchmarkTestCase(
        test_id="tc6_bw_manga",
        case_number=6,
        title="Authentic B&W Manga - Screentone, Hatching & Pure Inkwork",
        category="bw_manga",
        evaluation_focus="Pure black & white ink, 60-line screentone dot simulation, G-pen line weight variation, zero color artifacts",
        art_style="manga_bw",
        recommended_resolution=(832, 1216),
        aspect_ratio="B5 (~1:1.46)",
        recommended_steps=25,
        recommended_cfg=7.0,
        prompt_positive=(
            "masterpiece, best quality, authentic Japanese manga page style, pure black and white ink drawing, "
            "monochrome manga illustration, 1boy, minh_character, intense dramatic expression, "
            "messy short black hair rendered with crisp black ink and white highlights, sharp eyes with manga hatching, "
            "fitted school uniform with 60 LPI screentone pattern on blazer, fine cross-hatching shadows on collar, "
            "dynamic action speed lines in background, clean G-pen lineart, Shonen Jump publication quality, "
            "zero color, screentone shading, halftone dots, high contrast ink"
        ),
        prompt_negative=(
            "color, colorized, sepia, grayscale blur, muddy gradients, photorealistic, 3d, "
            "digital smudge, blurry lineart, washed out, low contrast, text, dialogue bubble"
        ),
        pass_criteria=[
            "Image is strictly monochrome (no color, chromatic tint, or sepia wash)",
            "Screentone dots/patterns are visible on gray tonal areas (blazer, background)",
            "G-pen line weight dynamics are sharp and crisp",
            "Passes the mathematical dark ink ratio gate (>3.5% dark ink)"
        ]
    ),

    # Case 7: Full-Color Modern Anime Rendering
    BenchmarkTestCase(
        test_id="tc7_color_anime",
        case_number=7,
        title="Modern Anime Key Visual - Multi-Layer Cel-Shading & Atmosphere",
        category="color_anime",
        evaluation_focus="2-step/3-step cel shading transitions, sunset atmospheric lighting, golden rim highlights, rich anime palette",
        art_style="anime_color",
        recommended_resolution=(1024, 1024),
        aspect_ratio="1:1",
        recommended_steps=28,
        recommended_cfg=7.5,
        prompt_positive=(
            "masterpiece, best quality, ultra-detailed full color anime key visual, official anime promotional poster, "
            "1boy, minh_character, standing at school rooftop during golden hour sunset, wind blowing messy black hair, "
            "sharp amber eyes glowing with warm sunset reflections, gorgeous vibrant color palette, "
            "rich navy blue blazer with crisp two-tone cel-shading, golden sunlight rim lighting along hair and shoulders, "
            "breathtaking sky with pink and purple twilight clouds, lens flare, high budget anime film production aesthetic, "
            "ufotable and Kyoto Animation lighting style, 8k resolution"
        ),
        prompt_negative=(
            "lowres, dull colors, oversaturated, muddy shading, monochrome, black and white, "
            "bad anatomy, blurry, artifacts, sketch, rough drawing, 3d render"
        ),
        pass_criteria=[
            "Vibrant multi-layer cel-shading with clear highlight/midtone/shadow cuts",
            "Warm sunset lighting creates consistent golden rim lights on hair and shoulders",
            "Color harmony between navy blazer, white shirt, amber eyes, and sunset sky",
            "Rich background clouds with cinematic atmospheric depth"
        ]
    ),

    # Case 8: 4-Panel Sequential Narrative Continuity
    BenchmarkTestCase(
        test_id="tc8_four_panel_sequence",
        case_number=8,
        title="4-Panel Narrative Sequence - Temporal & Spatial Continuity",
        category="sequential_continuity",
        evaluation_focus="Identity persistence across 4 sequential panels, sequential storytelling coherence, lighting evolution",
        art_style="manga_bw",
        recommended_resolution=(1200, 1800),
        aspect_ratio="Page (2:3)",
        recommended_steps=25,
        recommended_cfg=7.0,
        prompt_positive=(
            "masterpiece, authentic Japanese manga 4-panel page, sequential storytelling, "
            "consistent character minh_character across all frames, (1boy, messy black hair, amber eyes, school uniform), "
            "Panel 1: sleeping peacefully on desk by window morning light, "
            "Panel 2: waking up startled with wide eyes in shock, "
            "Panel 3: standing up in disbelief looking at classroom, "
            "Panel 4: sunset corridor holding smartphone trembling, "
            "clean manga panel borders, screentone shading, dynamic inkwork, Shonen Jump layout"
        ),
        prompt_negative=(
            "color, character inconsistency, changing hair color, changing gender, "
            "muddy gradients, bad panel borders, blurry linework, deformed hands"
        ),
        sequential_panels=[
            {
                "panel_number": 1,
                "scene": "Morning desk sleep",
                "camera": "medium_shot",
                "focus": "Peaceful sleep by open window, fluttering curtains"
            },
            {
                "panel_number": 2,
                "scene": "Shocked awakening",
                "camera": "close_up",
                "focus": "Pupils contracting, sweat drop, psychological realization"
            },
            {
                "panel_number": 3,
                "scene": "Classroom confrontation",
                "camera": "wide_shot",
                "focus": "Standing in disbelief looking at peers and blackboard"
            },
            {
                "panel_number": 4,
                "scene": "Sunset corridor suspense",
                "camera": "low_angle",
                "focus": "Smartphone glowing with mysterious text message, distant shadow"
            }
        ],
        pass_criteria=[
            "Minh's hair, face shape, and outfit remain consistent across all 4 frames",
            "Narrative progression from morning sleep -> shock -> standing -> sunset is clear",
            "Camera angles vary dynamically (medium -> close-up -> wide -> low-angle)",
            "Panel borders and gutters are clean and properly proportioned"
        ]
    )
]


# ==============================================================================
# 4. Export & Utility Functions
# ==============================================================================

def get_benchmark_spec_dict() -> dict[str, Any]:
    """Returns the complete benchmark specification as a Python dictionary."""
    return {
        "benchmark_metadata": {
            "title": "AI Office Anime Intelligence Benchmark Suite",
            "version": "1.0.0",
            "target_hardware": "Lenovo LOQ RTX 3050 Laptop 6GB VRAM / 12GB RAM",
            "benchmark_period": "2026-05-19 to 2026-11-19",
            "reference_character": MINH_REFERENCE_SPEC.model_dump(),
            "total_test_cases": len(BENCHMARK_TEST_CASES),
        },
        "test_cases": [tc.model_dump() for tc in BENCHMARK_TEST_CASES]
    }


def export_benchmark_specs_to_json(target_path: Path | str | None = None) -> Path:
    """Exports the benchmark specifications to a standard JSON file."""
    if target_path is None:
        target_path = Path(r"F:\AI-Office\data\manga\benchmarks\benchmark_prompts.json")
    else:
        target_path = Path(target_path)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    data = get_benchmark_spec_dict()
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return target_path


if __name__ == "__main__":
    out_file = export_benchmark_specs_to_json()
    print(f"Benchmark specifications exported successfully to: {out_file}")
    print(f"Total test cases defined: {len(BENCHMARK_TEST_CASES)}")
