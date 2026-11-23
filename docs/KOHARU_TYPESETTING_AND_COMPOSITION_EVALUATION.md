# Koharu Typesetting, Segmentation & Layer Composition Evaluation

**Document Version**: 1.0.0  
**Author**: `@composer-dev` (Composition & Export Engine Specialist)  
**Date**: 2026-11-23  
**Target System**: AI Office Manga Studio (`F:\AI-Office`)  
**Upstream Project**: [koharu-rs/koharu](https://github.com/koharu-rs/koharu)  
**Evaluation Scope**: Typesetting engine, text-bubble segmentation, vertical/horizontal CJK & Vietnamese rendering, non-destructive layer composition, PSD layered export vs. AI Office `MangaComposer`.

---

## 1. Executive Summary & Purpose

`koharu-rs/koharu` is an open-source, local-first manga and comic localization suite written in Rust and TypeScript with a WebGPU-accelerated canvas. While AI Office's existing `app/manga_composer.py` is engineered as a **generative manga composition engine** (authoring original manga from script, layout templates, AI panel art, and vector speech bubbles), Koharu serves as a **manga localization and scanlation engine** (detecting, erasing/inpainting, and re-typesetting foreign language text on existing manga scans).

This evaluation analyzes Koharu's typography, bubble segmentation, multi-script rendering, layer stack, and layered PSD export, benchmarking them against AI Office's native `MangaComposer` to establish technical feasibility and integration synergies.

---

## 2. Koharu Typesetting Engine Architecture (`koharu-renderer`)

Koharu separates machine learning inference from visual typesetting by employing a dedicated WebGPU-powered rendering engine.

### 2.1 Typesetting Stack & Rendering Pipeline

```
[Detected Text Polygon / OBB]
             │
             ▼
┌────────────────────────────────────────────────────────┐
│               koharu-renderer Layout Engine            │
├────────────────────────────────────────────────────────┤
│ 1. Writing Mode Detection (Vertical CJK vs Horiz LTR) │
│ 2. Text Frame Bounding Box / Balloon Polygon Fitting   │
│ 3. Font Cascading & Fallback Lookup                    │
│ 4. Line Breaking & Word Wrapping Algorithm             │
│ 5. Auto-Size Binary Search (Dynamic Point Scaling)     │
│ 6. Text Stroke / Outline / Shadow Synthesis            │
└────────────────────────────────────────────────────────┘
             │
             ▼
[WebGPU Texture / Vector Render Graph] ──► [Canvas Display / PSD Exporter]
```

1. **Paragraph & Point Text Modes**:
   - Koharu supports two text creation paradigms: *Point Text* (single-line or auto-flow anchored to a point) and *Paragraph Frames* (constrained within a bounding box or detected balloon polygon).
2. **Dynamic Auto-Sizing**:
   - The auto-size engine measures text bounding boxes against the maximum allowable dimensions of the detected balloon.
   - It iterates font size down (binary or stepped decrease) until all words fit without vertical or horizontal overflow, preventing text clipping.
3. **Font Dataset & Automated Fallback Cascade**:
   - Koharu maintains an integrated font dataset capable of on-demand font family retrieval.
   - The font shaper evaluates glyph coverage through a strict multi-tier fallback cascade:
     $$\text{User Preferred Font} \longrightarrow \text{System Default Font} \longrightarrow \text{Arial / Base Sans} \longrightarrow \text{CJK / Symbol / Emoji Fallbacks}$$
   - This ensures that missing glyphs in specialty comic fonts (e.g., CJK punctuation, accents, symbols) never render as empty boxes (`.notdef` / "tofu").

---

## 3. Text-Bubble Segmentation & Geometry

Manga localization requires segmenting existing speech balloons and sound effects from artwork before translated text can be overlaid.

### 3.1 Detection & Bounding Polygon Geometry

1. **Oriented Bounding Boxes (OBB) & Segmentation Polygons**:
   - Koharu uses ML detectors (`comic-text-detector` / `RF-DETR`) to identify text lines and speech balloons.
   - Rather than simple axis-aligned bounding boxes (AABB), Koharu extracts rotated rectangles and polygon contours. This preserves the natural tilt of dynamic dialogue and angled balloons common in manga.
2. **Text vs. Background Mask Generation**:
   - A binary mask is generated separating text glyph pixels from the balloon interior.
   - The mask is passed to generative inpainting models (such as LaMa or AOT-GAN), which reconstruct the speech bubble fill or underlying artwork texture.
3. **Balloon Inset & Safe Margins**:
   - Koharu computes an inner *safe typesetting polygon* by eroding the detected bubble contour by 8–15%, guaranteeing that newly laid out text remains centered within the white balloon body without colliding with outer ink borders.

---

## 4. Vertical / Horizontal CJK vs. Vietnamese Text Rendering

Manga localization from Japanese to Vietnamese presents unique typographic challenges due to writing direction, aspect ratio divergence, and diacritic density.

### 4.1 Writing Direction & Transformation

| Parameter | Japanese Source (CJK) | Vietnamese Target (Latin) | Typographic Challenge |
|---|---|---|---|
| **Writing Mode** | Vertical Top-to-Bottom, Right-to-Left (`ttb-rtl`) | Horizontal Left-to-Right (`ltr`) | 90° orientation mismatch between source balloon and target text. |
| **Balloon Aspect Ratio** | Tall and narrow ($H \gg W$, typical ratio 1:3 to 1:5) | Wide or square ($W \ge H$, typical ratio 1.5:1 to 1:1) | Translated horizontal text reflows into narrow vertical balloons. |
| **Punctuation & Glyphs** | Vertical punctuation (rotated brackets `（）`, dashes `ー`, ellipses `…`) | Standard Latin punctuation (horizontal baseline) | Glyph metrics must switch from vertical origin to horizontal baseline. |
| **Line Breaking** | Character-level breaking (any kanji/kana boundary) | Word-level breaking (spaces, hyphenation) | Long Vietnamese words risk overflowing narrow balloon widths. |

### 4.2 Vietnamese Unicode & Diacritic Handling in Koharu vs. MangaComposer

1. **Vietnamese Diacritic Stacking**:
   - Vietnamese employs combined tones and vowel marks (e.g., `ể, ễ, ệ, ồ, ổ, ộ, ử, ữ, ự, đ`).
   - Standard Latin fonts without proper vertical metric tables (`vhea`/`vmtx`) or generous line height cause stacked accents to collide with the line above or clip at the top of the balloon.
2. **Requirements for Koharu in Vietnamese**:
   - Koharu must be configured with Unicode fonts covering **Latin Extended Additional** (`U+1E00` – `U+1EFF`).
   - Line-height multiplier must be set to $\ge 1.30\times - 1.40\times$ (compared to standard English comic lettering at $1.15\times - 1.20\times$).
3. **MangaComposer Native Capability**:
   - In `app/manga_composer.py`, Vietnamese support is natively baked into `wrap_text_to_width` and `fit_text_in_bubble`, explicitly utilizing `app/ui/assets/Inter-Variable.ttf` with line spacing factor $1.30\times$ and accurate bounding box computation via `ImageDraw.textbbox`.

---

## 5. Non-Destructive Layer Composition Architecture

Koharu implements a multi-layer composition model that mirrors professional desktop graphic editors (Photoshop, Clip Studio Paint).

```
┌────────────────────────────────────────────────────────┐
│ Layer 5: SFX Re-draw & Onomatopoeia (Vector / Brush)   │
├────────────────────────────────────────────────────────┤
│ Layer 4: Manual Touch-Up / Inpainting Corrections     │
├────────────────────────────────────────────────────────┤
│ Layer 3: Typeset Text Blocks (Editable text, fonts)    │  <-- Non-destructive
├────────────────────────────────────────────────────────┤
│ Layer 2: Inpainted Clean Art (LaMa background fill)    │
├────────────────────────────────────────────────────────┤
│ Layer 1: Inpainting Mask Layer (Auto-detected + Lasso) │
├────────────────────────────────────────────────────────┤
│ Layer 0: Original Manga Page Scan (Immutable Source)   │
└────────────────────────────────────────────────────────┘
```

### 5.1 Benefits of Non-Destructive Layering

1. **Decoupled Iteration**:
   - Translators and proofreaders can re-word dialogue or change font size without triggering re-inpainting or losing manual mask touch-ups.
2. **Selective Inpainting**:
   - Complex SFX crossing over line art or screentones can be masked and painted manually while regular dialogue balloons are cleaned automatically.
3. **AI Agent Interaction**:
   - AI agents (via Koharu's MCP server) can read or modify Layer 3 (Text Blocks) directly through JSON RPC without manipulating raw pixel rasters.

---

## 6. Layered PSD Export vs. AI Office MangaComposer

A core highlight of Koharu is its **layered PSD export**, designed for interoperability with desktop publishing software.

### 6.1 Architectural Comparison

| Dimension | `koharu-rs/koharu` | AI Office `app/manga_composer.py` |
|---|---|---|
| **Primary Domain** | **Manga Localization** (Scan translation) | **Manga Creation** (Generative authoring from script) |
| **Rendering Backend** | WebGPU / Rust Canvas (`wgpu`, `cosmic-text`) | Python Pillow + Standard Libraries (Zero C/GPU dependencies) |
| **Input Source** | Existing raw scanned images (PNG/JPEG) | Structured story data (`PageConfig`, `PanelPlan`, AI panel art) |
| **Bubble Construction** | Inpainting existing bubbles + placing text frame | Generates vector bubbles (regular, thought, shout, SFX) + tails |
| **Tail Synthesis** | Preserves original scan tail; erases text inside | Morphological dilation (`MaxFilter`) seamlessly joining body & tail |
| **Screentone / Filters** | Preserves original scan screentone during inpainting | Native procedural dot halftone (45°), dither, anime pastel/vibrant |
| **Layered PSD Export** | **Native Layered PSD** (Image, Inpaint, Text layers) | Flattened multi-layer RGBA composite |
| **Digital Comic Export** | Standard CBZ (images only) | **Enhanced CBZ** with `ComicInfo.xml` metadata + multi-page PDF |
| **Resource Footprint** | Moderate (WebGPU context + ONNX models) | Ultra-lightweight (< 50MB RAM, fast CPU/PIL execution) |

### 6.2 Koharu PSD Structure

When Koharu exports to `.psd`, it serializes:
- **Base Layer**: Inpainted clean manga artwork (RGB/Grayscale).
- **Text Layers**: Independent raster or editable text layers positioned at exact balloon coordinates.
- **SFX Layer**: Isolated onomatopoeia drawings or vector outlines.
- **Layer Masks**: Preserves selection masks for fine-tuning in Photoshop.

---

## 7. Strategic Synergies & Integration Roadmap for AI Office

Rather than viewing Koharu as a replacement for `MangaComposer`, Koharu and `MangaComposer` form a **complete bidirectional manga lifecycle pipeline**:

```
                       ┌────────────────────────────────────────┐
                       │     AI Office Manga Studio Suite       │
                       └────────────────────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│     AI MANGA CREATION         │               │     MANGA LOCALIZATION        │
│   (app/manga_composer.py)     │               │      (koharu-rs/koharu)       │
├───────────────────────────────┤               ├───────────────────────────────┤
│ • Story Studio Scripting      │               │ • Import Foreign Manga Scans  │
│ • Panel Layout Framing        │               │ • Text Detection & Inpainting │
│ • AI Diffusion Art Generation │               │ • LLM Multi-script Translation│
│ • Vector Bubble Synthesis     │               │ • Text Reflow & Replacement   │
│ • Screentone & Halftone Polish│               │ • Non-destructive PSD Export  │
└───────────────────────────────┘               └───────────────────────────────┘
            │                                               │
            └───────────────────────┬───────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         Unified Multi-Format Publishing                       │
│  • Production CBZ with ComicInfo.xml metadata (RTL reading order)             │
│  • High-Resolution Multi-Page PDF (150-300 DPI)                               │
│  • Webtoon Vertical Strip / Lossless PNG Archives                             │
│  • Layered PSD for Professional Typography & Print Houses                     │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Key Recommendations for AI Office Integration

1. **Layered PSD Exporter for MangaComposer**:
   - Port Koharu's non-destructive layer serialization concepts to `app/manga_composer.py` using Python's `pytoshop` or custom PSD header serialization.
   - This will allow Manga Studio creators to export both finished CBZ/PDF and editable layered PSD files for Adobe Photoshop and Clip Studio Paint.
2. **Headless Sidecar Service for Localization**:
   - Run Koharu as a sandboxed headless sidecar binary (`koharu --headless --port 8484`) or MCP server.
   - Manga Studio users can upload existing Japanese manga, let Koharu handle text removal and OCR, and use AI Office's `qwen3.5:4b` and `manga_composer` for high-quality Vietnamese typography.
3. **Vietnamese Typography Preset for Koharu**:
   - Provide AI Office's `Inter-Variable.ttf` font asset and Vietnamese typesetting profiles (line spacing $1.35\times$, auto-hyphenation) to Koharu's renderer settings to prevent diacritic clipping during scanlation.
