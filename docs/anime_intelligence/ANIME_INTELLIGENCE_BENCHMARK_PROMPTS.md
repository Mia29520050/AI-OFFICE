# Anime Intelligence System: Standardized Benchmark Test Prompts & Reference Character Specs

**Author:** story-dev (Story Studio Domain)  
**Date:** 2026-11-19  
**Target Hardware:** Lenovo LOQ (RTX 3050 Laptop 6GB VRAM, 12GB RAM)  
**Output Specification File:** [`F:\AI-Office\data\manga\benchmarks\benchmark_prompts.json`](file:///F:/AI-Office/data/manga/benchmarks/benchmark_prompts.json)  
**Domain Module:** [`F:\AI-Office\app\manga_benchmark.py`](file:///F:/AI-Office/app/manga_benchmark.py)  
**Verification Test:** [`F:\AI-Office\tests\test_anime_benchmark_specs.py`](file:///F:/AI-Office/tests/test_anime_benchmark_specs.py)  

---

## 1. Reference Character Specification: Minh (`char_minh_ref`)

The benchmark reference character **Minh** (*Kurogane Minh*) is designed as an anchor subject to evaluate character consistency, anatomy fidelity, costume anchoring, and identity preservation across diffusion models (Anima Base/Aesthetic/Turbo GGUF, Anima-Ref-Adapter, Z-Anime 6B, QWEN-Anime 20B).

| Attribute | Specification | Prompt Tag Anchor |
|---|---|---|
| **Role & Age** | Protagonist, 16 years old, High school second-year | `1boy, 16yo, slender athletic build` |
| **Hair** | Messy short raven-black hair with natural tufts and side bangs | `messy short black hair, side bangs` |
| **Eyes** | Sharp amber brown eyes with clear pupils and determined gaze | `sharp amber eyes, intense gaze` |
| **Physique** | Slender athletic teenage build (174cm, 1:7.5 head-to-body ratio) | `slender teen, clean jawline` |
| **Blazer** | Tailored dark navy blue school blazer with gold button accents | `fitted navy blue blazer, gold button accents` |
| **Shirt & Tie** | Crisp white collared dress shirt with tied dark navy necktie | `crisp white collared shirt, dark navy blue necktie` |
| **Trousers** | Straight-leg charcoal dark grey tailored school trousers | `charcoal grey tailored trousers` |
| **Footwear** | Dark brown leather school loafers | `dark leather loafers` |
| **Forbidden** | Skirts, blouses with frills, bright casual clothes, blonde hair | Enforced in negative prompts |

### Standard Trigger Prompt & Negative Prompt
```
Trigger Positive:
minh_character, 1boy, 16yo, slender teen, messy short black hair, side bangs, sharp amber eyes, white collared shirt, dark navy blue necktie, navy blue blazer, charcoal grey trousers, masterpiece, best quality, ultra-detailed anime illustration

Negative:
lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, artist name, realistic, 3d, photorealistic, deformed, bad proportions, female clothes, skirt, blonde hair, blue eyes, disfigured, extra limbs
```

---

## 2. The 8 Standardized Benchmark Test Cases

### Test Case 1: Portrait / Close-up (`tc1_portrait`)
- **Title**: Minh - Expressive Portrait & Facial Feature Fidelity
- **Category**: Facial Anatomy & Expression Fidelity
- **Resolution**: `768x1024` (3:4) | **Steps**: 24 | **CFG**: 7.0 | **Style**: Anime Color
- **Evaluation Focus**: Micro-details of amber iris reflections, messy black hair strand delineation, ear/nose anatomy, skin shading gradient.
- **Positive Prompt**:
  ```
  masterpiece, best quality, highres, close-up portrait, 1boy, minh_character, 16yo, messy short black hair with delicate strands, sharp amber eyes with detailed iris highlights, determined thoughtful expression, clean jawline, subtle rim lighting, white collared shirt, navy blue tie knot visible at collar, dramatic soft shadows, depth of field, anime key visual, 8k resolution
  ```
- **Pass Criteria**:
  1. Amber eye color is clearly discernible with sharp pupils.
  2. Short black hair has defined individual tufts, not a solid black blob.
  3. Facial anatomy is symmetrical and free of melting/blurring.
  4. White shirt collar and navy tie knot are accurately rendered.

---

### Test Case 2: Full-Body (`tc2_fullbody`)
- **Title**: Minh - Full-Body Anatomy & Uniform Integrity
- **Category**: Full-Body Proportions & Costume Anchoring
- **Resolution**: `768x1152` (2:3) | **Steps**: 26 | **CFG**: 7.0 | **Style**: Anime Color
- **Evaluation Focus**: Head-to-height ratio (1:7.5), hand anatomy (5 distinct fingers), trousers vs skirt check, footwear clarity.
- **Positive Prompt**:
  ```
  masterpiece, best quality, highres, full body shot, 1boy standing, minh_character, 16yo slender athletic build, messy short black hair, sharp amber eyes, confident relaxed standing pose, hands resting naturally at sides with 5 fingers, crisp white collared shirt, dark navy blue necktie, fitted navy blue school blazer with gold buttons, charcoal grey straight-leg trousers with realistic fabric creases, dark leather loafers, neutral light grey background, full figure visible from head to shoes
  ```
- **Pass Criteria**:
  1. Full figure visible from head to shoes without cropping.
  2. Trousers are clearly rendered (no skirts or dress artifacts).
  3. Hands have exactly 5 fingers without webbed or fused joints.
  4. Proportions conform to classic Japanese anime teenage aesthetics.

---

### Test Case 3: Classroom Environment (`tc3_classroom`)
- **Title**: Classroom Interior - Perspective & Lighting Integration
- **Category**: Background Integration & Spatial Coherence
- **Resolution**: `1024x768` (4:3) | **Steps**: 28 | **CFG**: 7.5 | **Style**: Anime Color
- **Evaluation Focus**: Vanishing point alignment, window sunlight beam interaction, natural character grounding, no floating desks.
- **Positive Prompt**:
  ```
  masterpiece, best quality, highres, interior wide shot, Japanese high school classroom in bright morning sunlight, 1boy, minh_character, sitting by open window on wooden school chair, head turned looking out window, messy short black hair caught in gentle morning breeze, white curtains fluttering, warm golden sunbeams streaming across wooden floorboards, detailed wooden student desks, chalkboard in background with faded mathematical formulas, dust motes dancing in sunlight, nostalgic cinematic anime atmosphere, Makoto Shinkai lighting aesthetic, high contrast soft shadows
  ```
- **Pass Criteria**:
  1. Perspective grid aligns naturally toward the window/chalkboard.
  2. Sunlight angle matches the shadow cast by the desk and character.
  3. Minh is correctly seated without clipping through furniture.
  4. Classroom details (chalkboard, desks, curtains) are crisp and identifiable.

---

### Test Case 4: 2 Characters Interaction (`tc4_two_characters`)
- **Title**: Two Characters - Identity Bleed & Interaction Check
- **Category**: Multi-Subject Disambiguation & Cross-Bleed Resistance
- **Resolution**: `1024x768` (4:3) | **Steps**: 28 | **CFG**: 7.0 | **Style**: Anime Color
- **Evaluation Focus**: Zero feature contamination between boy and girl, eye-contact direction, distinct heights, non-overlapping limb boundaries.
- **Positive Prompt**:
  ```
  masterpiece, best quality, highres, two characters interacting in classroom, (minh_character:1.1: 1boy, messy short black hair, sharp amber eyes, navy blazer, dark trousers), standing and talking to (mai_character:1.1: 1girl, shoulder-length brown hair, soft brown eyes, white blouse, cream cardigan, navy pleated skirt), distinct character appearances, boy looking down with serious expression, girl smiling warmly holding school notebook, natural space between characters, classroom desks background, clean separation of clothing and hair
  ```
- **Pass Criteria**:
  1. Boy and girl maintain strict individual identity (boy in dark trousers, girl in pleated skirt).
  2. No color bleeding between black hair (boy) and brown hair (girl).
  3. No fused limbs or extra arms between the two subjects.
  4. Clear spatial separation and conversational body language.

---

### Test Case 5: Dynamic Camera Angles (`tc5_camera_angles`)
- **Title**: Dynamic Low-Angle / Dutch Tilt - Extreme Perspective Foreshortening
- **Category**: Extreme Perspective & Foreshortening Under Stress
- **Resolution**: `768x1024` (3:4) | **Steps**: 26 | **CFG**: 7.5 | **Style**: Anime Color
- **Evaluation Focus**: Dramatic low-angle looking up from floor level, foreshortened legs and torso, upward shadow casting, Studio Trigger style dynamism.
- **Positive Prompt**:
  ```
  masterpiece, best quality, dramatic dynamic low-angle worm's-eye shot looking up, 1boy, minh_character, standing tall and imposing in center frame, intense focused downward gaze, foreshortened perspective, messy black hair framing face against school ceiling lights, navy blue blazer billowing slightly, crisp white shirt and tie, sharp ink lineart, high contrast anime lighting, dramatic shadows cast upwards, cinematic anime keyframe, Studio Trigger dynamic composition
  ```
- **Pass Criteria**:
  1. Extreme low-angle perspective looking upward is convincingly maintained.
  2. Foreshortened limbs maintain correct proportional anatomy.
  3. Face retains Minh's signature sharp amber eyes and short black hair.
  4. Lighting conforms to overhead school ceiling lights.

---

### Test Case 6: Classic B&W Manga (`tc6_bw_manga`)
- **Title**: Authentic B&W Manga - Screentone, Hatching & Pure Inkwork
- **Category**: Manga Ink Aesthetics & Binary Screentone Fidelity
- **Resolution**: `832x1216` (B5 Manga) | **Steps**: 25 | **CFG**: 7.0 | **Style**: Manga B&W
- **Evaluation Focus**: Pure monochrome ink (no muddy gray gradients where halftone dots belong), 60 LPI screentone pattern, clean G-pen line weight variation, dark ink ratio > 3.5%.
- **Positive Prompt**:
  ```
  masterpiece, best quality, authentic Japanese manga page style, pure black and white ink drawing, monochrome manga illustration, 1boy, minh_character, intense dramatic expression, messy short black hair rendered with crisp black ink and white highlights, sharp eyes with manga hatching, fitted school uniform with 60 LPI screentone pattern on blazer, fine cross-hatching shadows on collar, dynamic action speed lines in background, clean G-pen lineart, Shonen Jump publication quality, zero color, screentone shading, halftone dots, high contrast ink
  ```
- **Pass Criteria**:
  1. Image is strictly monochrome (no color, chromatic tint, or sepia wash).
  2. Screentone dots/patterns are visible on gray tonal areas (blazer, background).
  3. G-pen line weight dynamics are sharp and crisp.
  4. Passes the mathematical dark ink ratio gate (>3.5% dark ink).

---

### Test Case 7: Full-Color Modern Anime (`tc7_color_anime`)
- **Title**: Modern Anime Key Visual - Multi-Layer Cel-Shading & Atmosphere
- **Category**: Color Science, Cel-Shading & Atmospheric Lighting
- **Resolution**: `1024x1024` (Square 1:1) | **Steps**: 28 | **CFG**: 7.5 | **Style**: Anime Color
- **Evaluation Focus**: 2-step / 3-step cel-shading transitions, golden sunset lighting rim highlights along hair/shoulders, rich anime color palette.
- **Positive Prompt**:
  ```
  masterpiece, best quality, ultra-detailed full color anime key visual, official anime promotional poster, 1boy, minh_character, standing at school rooftop during golden hour sunset, wind blowing messy black hair, sharp amber eyes glowing with warm sunset reflections, gorgeous vibrant color palette, rich navy blue blazer with crisp two-tone cel-shading, golden sunlight rim lighting along hair and shoulders, breathtaking sky with pink and purple twilight clouds, lens flare, high budget anime film production aesthetic, ufotable and Kyoto Animation lighting style, 8k resolution
  ```
- **Pass Criteria**:
  1. Vibrant multi-layer cel-shading with clear highlight/midtone/shadow cuts.
  2. Warm sunset lighting creates consistent golden rim lights on hair and shoulders.
  3. Color harmony between navy blazer, white shirt, amber eyes, and sunset sky.
  4. Rich background clouds with cinematic atmospheric depth.

---

### Test Case 8: 4-Panel Sequential Continuity (`tc8_four_panel_sequence`)
- **Title**: 4-Panel Narrative Sequence - Temporal & Spatial Continuity
- **Category**: Multi-Frame Consistency & Narrative Coherence
- **Resolution**: `1200x1800` (Page 2:3) | **Steps**: 25 | **CFG**: 7.0 | **Style**: Manga B&W
- **Evaluation Focus**: Character identity locked across 4 consecutive narrative beats:
  - **Panel 1**: Morning desk sleep (peaceful atmosphere, morning light).
  - **Panel 2**: Shocked awakening (pupils contracting, sweat drop, psychological realization).
  - **Panel 3**: Classroom confrontation (standing in disbelief looking at classroom).
  - **Panel 4**: Sunset corridor suspense (holding glowing smartphone, ominous shadow).
- **Positive Prompt**:
  ```
  masterpiece, authentic Japanese manga 4-panel page, sequential storytelling, consistent character minh_character across all frames, (1boy, messy black hair, amber eyes, school uniform), Panel 1: sleeping peacefully on desk by window morning light, Panel 2: waking up startled with wide eyes in shock, Panel 3: standing up in disbelief looking at classroom, Panel 4: sunset corridor holding smartphone trembling, clean manga panel borders, screentone shading, dynamic inkwork, Shonen Jump layout
  ```
- **Pass Criteria**:
  1. Minh's hair, face shape, and outfit remain consistent across all 4 frames.
  2. Narrative progression from morning sleep -> shock -> standing -> sunset is clear.
  3. Camera angles vary dynamically (medium -> close-up -> wide -> low-angle).
  4. Panel borders and gutters are clean and properly proportioned.

---

## 3. Integration Interface for Core-Dev & Harness

The benchmark harness in `scripts/run_anime_benchmark.py` can load the prompts and character specifications via Python or JSON:

```python
# Option A: Import directly from app.manga_benchmark
from manga_benchmark import MINH_REFERENCE_SPEC, BENCHMARK_TEST_CASES, get_benchmark_spec_dict

# Option B: Read from standard JSON
import json
with open("data/manga/benchmarks/benchmark_prompts.json", "r", encoding="utf-8") as f:
    bench_data = json.load(f)
```
