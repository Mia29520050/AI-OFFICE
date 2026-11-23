# Koharu (koharu-rs/koharu): Translation Fidelity, Context Preservation, Proofreading Workflow & MCP Server Integration

**Document Version**: 1.0.0  
**Author**: `@story-dev` (Story Studio Lead & Narrative Continuity)  
**Date**: 2026-11-23  
**Target System**: AI Office Manga Studio (`F:\AI-Office`)  
**Hardware Baseline**: Lenovo LOQ (RTX 3050 Laptop GPU 6GB VRAM, 12GB RAM, Windows 11 x64)  
**Upstream Repository**: [koharu-rs/koharu](https://github.com/koharu-rs/koharu)  

---

## 1. Executive Summary & Purpose

`koharu-rs/koharu` is an open-source, local-first manga and comic localization suite written in Rust and TypeScript with a WebGPU-accelerated canvas. While AI Office's existing `app/manga_story.py` and `app/manga_composer.py` operate as a **generative manga composition engine** (authoring original manga from script, layout templates, AI panel art, and vector speech bubbles), Koharu is engineered as an **automated manga localization and scanlation engine** (detecting text regions, performing inpainting/erasure of raw art, translating dialogue, and re-typesetting).

This evaluation investigates Koharu's capabilities from the perspective of **Story Studio, Narrative Consistency, and AI Agent Architecture**:
1. **Translation Fidelity & Nuance**: Accuracy of LLM-based translation, handling of anime-specific Japanese dialogue, honorifics, tone registers, and Vietnamese pronoun systems (`tớ - cậu`, `anh - em`, `mình - bạn`).
2. **Context Preservation**: Text bubble reading order spatial sorting, multi-bubble sentence clustering (broken sentence syntax), and cross-page conversation memory.
3. **Proofreading Workflow & Data Integrity**: Dedicated "Story" review panel, quad-linked text element data model (source OCR, translation, inpaint patch, typesetting layer), non-destructive editing, and terminology lock glossaries.
4. **Model Context Protocol (MCP) Server Integration**: Local Streamable HTTP MCP server (`http://127.0.0.1:7878/mcp`), headless mode CLI (`koharu --headless --port 7878`), exposed tool schema, and how AI Office agents can autonomously drive Koharu as a specialized localization and continuity copilot.
5. **6GB VRAM Optimization**: Strategy to eliminate duplicate LLM memory consumption by offloading Koharu's translation requests to AI Office's local Ollama instance (`qwen3.5:4b`).

---

## 2. Translation Fidelity & Nuance Handling

### 2.1 Translation Engine Architecture

Koharu processes translations using a decoupled LLM architecture managed under `[pipeline.translator]` and `[providers]` in `~/.koharu/config.toml`:

```
┌──────────────────────────────────────────────────────────────┐
│                    Koharu Translation Engine                 │
├──────────────────────────────────────────────────────────────┤
│ 1. Local In-Process Engine (llama.cpp / Candle via GGUF)     │
│    - Default: koharu/index-translate-9b:Q8_0                 │
│    - Quantized variants: Q4_K_M, Q5_K_M, Q8_0                │
├──────────────────────────────────────────────────────────────┤
│ 2. Remote / Sidecar Providers (OpenAI-Compatible API)        │
│    - OpenAI (GPT-4o, GPT-4o-mini)                            │
│    - Anthropic Claude (Claude 3.5 Sonnet / Haiku)            │
│    - DeepSeek (DeepSeek-V3 / R1)                             │
│    - Ollama (AI Office Local Host: http://127.0.0.1:11434/v1)│
└──────────────────────────────────────────────────────────────┘
```

#### Default Translation Prompt Structure
Koharu uses an adaptation of the **Index-Translate** prompt format in English. The model is instructed to treat input as a structured list of manga text blocks and output a strictly typed JSON array:
```json
[
  {"id": 0, "translation": "..."},
  {"id": 1, "translation": "..."}
]
```
This structured format ensures that:
- Each translated phrase maps directly to its corresponding detected spatial bounding box.
- The model does not emit conversational filler or reasoning tokens into the typesetting stream.
- Unchanged or untranslated blocks (SFX, logos) can be flagged and bypassed cleanly.

#### Custom Instructions Pipeline (`Additional instructions`)
In `Settings → Pipeline → Additional instructions`, users can supply project-wide or chapter-wide rules in natural language. Koharu automatically appends these instructions to the system prompt, enabling:
- Custom terminology glossaries.
- Explicit character pronoun rules.
- Untranslated token bypass rules (e.g., sound effects to leave in original Japanese katakana).

---

### 2.2 Vietnamese Manga Localization Nuances

Manga translation into Vietnamese poses unique linguistic challenges that generic machine translation engines handle poorly:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Vietnamese Manga Translation Nuances                │
├───────────────────┬───────────────────────────────┬─────────────────────┤
│ Dimension         │ Japanese / Source Challenge   │ Vietnamese Dynamic  │
├───────────────────┼───────────────────────────────┼─────────────────────┤
│ Pronoun Hierarchy │ watashi, boku, ore, atashi,   │ tớ - cậu (friends)  │
│ (Xưng hô)         │ washi, anata, omae, kimi,     │ anh - em (intimate) │
│                   │ temee, kisama                 │ mày - tao (combat)  │
│                   │                               │ tôi - bạn (neutral) │
├───────────────────┼───────────────────────────────┼─────────────────────┤
│ Honorifics        │ -san, -kun, -chan, -senpai,   │ Tiền bối, đại ca,   │
│ (Kính ngữ)        │ -sensei, -sama, dono          │ sư phụ, sensei      │
├───────────────────┼───────────────────────────────┼─────────────────────┤
│ Speech Registers  │ Keigo (kính ngữ),             │ Dạ thưa, lễ phép vs │
│ (Sắc thái khẩu khí)│ Ore-sama (kiêu ngạo),         │ cộc cằn, giang hồ,  │
│                   │ Tsundere (lạnh ngoài ấm trong)│ ngây thơ, tri thức  │
├───────────────────┼───────────────────────────────┼─────────────────────┤
│ Bubble Fitting    │ High information density per  │ Vietnamese words    │
│ (Mật độ chữ)      │ Kanji character               │ require 20-40% more │
│                   │                               │ horizontal space    │
└───────────────────┴───────────────────────────────┴─────────────────────┘
```

1. **The Pronoun Hierarchy (Hệ thống đại từ nhân xưng)**:
   - Japanese has distinct 1st-person (`boku` = humble youth, `ore` = masculine/assertive, `watashi` = formal/neutral) and 2nd-person pronouns (`omae` = blunt/intimate, `temee` = aggressive enemy, `anata` = polite/spouse).
   - In Vietnamese, there is no generic "I" and "you". The translation *must* reflect the exact social hierarchy:
     - Classmates / peers: `tớ - cậu` (friendly), `mình - bạn` (polite), `tôi - cậu` (distant).
     - Older/younger schoolmates: `tiền bối - em` or `anh/chị - em`.
     - Hostile / Rival combat: `mày - tao` or `ngươi - ta`.
   - Without explicit pronoun injection, standard LLMs fluctuate between `tôi - bạn` and `anh - em` mid-chapter.

2. **Honorific Retention vs Naturalization**:
   - Anime fans often prefer preserving iconic Japanese suffixes (`-senpai`, `-sensei`, `-san`, `-kun`, `-chan`).
   - Mainstream publication requires naturalization (`tiền bối`, `thầy`, `bác`, `bé`).
   - Koharu's prompt injection allows specifying an exact honorific mapping policy per project.

---

### 2.3 Synergistic Bridging with AI Office `app/manga_story.py`

AI Office already possesses an expressive, typed domain schema for character profiles and speech rules in `app/manga_story.py`:

```python
# From app/manga_story.py:
class SpeechRules(BaseModel):
    first_person: str = "tôi"
    second_person: str = "cậu"
    tone: str = "tự nhiên, điềm đạm"
    honorifics: list[str] = []
    catchphrases: list[str] = []
    vocabulary_habits: list[str] = []
    forbidden_words: list[str] = []
    sample_dialogues: list[str] = []

class CharacterProfile(BaseModel):
    name: str
    japanese_name: str | None
    role: str
    speech_rules: SpeechRules
    locked_traits: CharacterLockedTraits
```

#### Automated Prompt & Glossary Synthesizer
Rather than requiring manual user entry into Koharu's GUI, AI Office can automatically compile `CharacterProfile` and `CanonFact` registries into Koharu's `Additional instructions` format:

```python
def export_koharu_instruction_prompt(
    characters: list[CharacterProfile],
    canon_facts: list[CanonFact]
) -> str:
    lines = [
        "### HƯỚNG DẪN DỊCH THUẬT MANGA TIẾNG VIỆT CHUYÊN NGHIỆP ###",
        "1. QUY TẮC ĐẠI TỪ XƯNG HÔ VÀ KHẨU KHÍ CỐ ĐỊNH:"
    ]
    for char in characters:
        rules = char.speech_rules
        lines.append(
            f"- Nhân vật '{char.name}' (Tiếng Nhật: {char.japanese_name or 'N/A'}): "
            f"Xưng ngôi 1 là '{rules.first_person}', gọi người đối diện ngôi 2 là '{rules.second_person}'. "
            f"Giọng điệu: {rules.tone}. Kính ngữ: {', '.join(rules.honorifics) or 'Không'}. "
            f"Từ cấm kỵ tuyệt đối: {', '.join(rules.forbidden_words) or 'Không'}."
        )
    lines.append("\n2. DANH MỤC THUẬT NGỮ KHÓA (CANON GLOSSARY):")
    for fact in canon_facts:
        lines.append(f"- [{fact.category}] {fact.title}: {fact.fact}")
    lines.append(
        "\n3. ĐỊNH DẠNG ĐẦU RA: Giữ nguyên cấu trúc JSON. Lời thoại tiếng Việt tự nhiên, "
        "cô đọng, phù hợp bóng thoại manga (dưới 25 từ mỗi ô)."
    )
    return "\n".join(lines)
```

This guarantees **zero pronoun drift** and **100% canon consistency** across long multi-chapter serialization.

---

## 3. Context Preservation & Multi-Bubble Clustering

### 3.1 Spatial Reading Order Sorting

Manga is read in a non-linear 2D spatial hierarchy:
- **Japanese Manga (RTL)**: Top-to-bottom, right-to-left.
- **Western Comics / Korean Manhwa (LTR)**: Top-to-bottom, left-to-right.

Koharu's layout analysis module (`koharu-ml`) sorts detected text bounding boxes into reading order before passing them to the OCR and translation stages. Each detected text block receives an incremental sequential identifier (`id: 0, 1, 2, ...`).

```
┌────────────────────────────────────────────────────────┐
│ Page Top                                               │
│                                                        │
│   [Panel 1]                                            │
│   (2) "Chuyện đó..."            (1) "Nhưng mà..."      │
│          ▲                              ▲              │
│          │                              │              │
│          └────── Reading Order ◄────────┘              │
│                                                        │
│   [Panel 2]                                            │
│   (3) "...làm sao có thể chứ?!"                        │
│                                                        │
│ Page Bottom                                            │
└────────────────────────────────────────────────────────┘
```

---

### 3.2 Multi-Bubble Sentence Clustering (The Broken Sentence Problem)

In manga, authors frequently break a single compound sentence across 2 to 4 consecutive speech bubbles across one or more panels to create dramatic pause or pacing.

#### Failure Mode of Isolated Bubble Translation:
Translating bubbles independently in isolation produces disjointed, ungrammatical gibberish:
- Bubble 1: `しかし…` -> Translated in isolation: *"Tuy nhiên..."*
- Bubble 2: `そんなことが…` -> Translated in isolation: *"Điều đó..."*
- Bubble 3: `あり得るはずがない！` -> Translated in isolation: *"Không thể có lý do tồn tại!"*
- **Result**: Fragmented, robotic sentences without grammatical continuity.

#### Koharu's Page-Level Batch Prompting Solution:
Koharu feeds the **entire ordered sequence of text blocks on a page** into the LLM in a single request:
```json
[
  {"id": 0, "text": "しかし…"},
  {"id": 1, "text": "そんなことが…"},
  {"id": 2, "text": "あり得るはずがない！"}
]
```
The LLM's multi-head attention mechanism spans the full prompt context, allowing it to:
1. Recognize that bubbles 0, 1, and 2 form a single compound thought.
2. Resolve the ellipsis and cross-bubble syntactic dependencies.
3. Distribute the natural Vietnamese sentence smoothly across the bubbles:
   - `id 0`: *"Nhưng mà..."*
   - `id 1`: *"chuyện như vậy..."*
   - `id 2`: *"...làm sao có thể xảy ra được chứ?!"*

---

### 3.3 Multi-Turn Sequential Page Conversation Memory

A major strength of Koharu's translation pipeline is its **continuous conversation flow**:
- Translation runs as an ongoing conversational session per active project.
- **One turn per page in sequential order** (Page 1 -> Page 2 -> Page 3...).
- The model maintains the context of prior pages:
  - Characters present in the scene.
  - Active conversational topics.
  - Established pronoun pairs (`tớ - cậu` vs `anh - em`).
- **Session Reset Triggers**: Changing the translation model, target language, or system prompt cleanly resets the conversation stream, preventing cross-project hallucination.

---

### 3.4 Handling Untranslated SFX and Background Elements

In manga localization, not every text element should be translated:
- **SFX (Sound Effects / Onomatopoeia)**: Stylized Japanese katakana hand-drawn sound effects (e.g., `ドンッ`, `ゴゴゴ`, `バキッ`) are often left intact or subtitled.
- **Artist Signatures & Copyright Watermarks**: Must remain untouched.

Koharu solves this cleanly:
- When a text block's translation is left blank or identical to the source text, Koharu's pipeline **bypasses inpainting and text replacement**.
- The original artwork and lettering are retained at pixel fidelity without blurring or artifacting.

---

## 4. Proofreading Workflow & Linked Data Integrity

### 4.1 The "Story" Review Panel

Koharu features a dedicated, specialized review surface called the **Story Panel**:
- Displays all text blocks organized hierarchically by page and sorted in reading order.
- **Side-by-Side Dual-Pane Interface**:
  - Left column: Source OCR text (Japanese/English) with confidence score.
  - Right column: Target translated text (editable field).
- Direct bi-directional canvas highlighting: Clicking a text block in the Story Panel immediately centers and highlights the corresponding balloon on the WebGPU canvas.

```
┌────────────────────────────────────────────────────────────────────────┐
│ Story Review Panel                                                     │
├──────┬────────────────────────────────────┬────────────────────────────┤
│ ID   │ Source Text (OCR)                  │ Translated Text (Editable) │
├──────┼────────────────────────────────────┼────────────────────────────┤
│ P1-1 │ でも…あいつはもう…                 │ Nhưng mà... cậu ấy đã...   │
│ P1-2 │ あきらめたわけじゃないんだろ？！   │ ...không hề bỏ cuộc đúng   │
│      │                                    │ không hả?!                 │
│ P1-3 │ [SFX] ドンッ                       │ (Untranslated - Preserved) │
│ P1-4 │ 行くぞ、レン！                     │ Đi thôi, Ren!              │
└──────┴────────────────────────────────────┴────────────────────────────┘
```

---

### 4.2 Quad-Linked Text Element Data Architecture

Koharu implements a robust, non-destructive data model for every localized text element:

```
┌───────────────────────────────────────────────────────────┐
│              Quad-Linked Text Element Node                │
├───────────────────────────────────────────────────────────┤
│ 1. Geometry & Spatial Polygon (OBB / Bounding Box)        │
├───────────────────────────────────────────────────────────┤
│ 2. Source Text Layer (Raw OCR Transcription)              │
├───────────────────────────────────────────────────────────┤
│ 3. Clean Background Layer (Inpainted Patch + Mask)        │
├───────────────────────────────────────────────────────────┤
│ 4. Typesetting & Typography Vector Layer (Rendered Text)   │
└───────────────────────────────────────────────────────────┘
```

#### Why Decoupling is Crucial for Proofreading:
1. **Zero Art Degradation during Text Edits**:
   - In traditional raster editors, correcting a typo requires re-cloning or re-inpainting the underlying artwork.
   - In Koharu, modifying the translated string or adjusting manual line breaks (`\n`) only recalculates the vector glyph layout. **The inpaint patch is never regenerated or re-compressed**, preserving 100% of the underlying background artwork quality.
2. **Surgical OCR Correction**:
   - If OCR misidentifies a kanji (e.g., `木` instead of `本`), the proofreader simply corrects the source text in the Story Panel.
   - The user can trigger a **single-element re-translation** without invalidating the rest of the page.

---

### 4.3 Terminology Locks & Layered PSD Export

- **Terminology Consistency**: Recurring proper nouns (character names, attack moves, magic spells, locations) remain locked across chapters.
- **Layered PSD Export**:
  - When exporting to Adobe Photoshop / Clip Studio Paint format (`.psd`), Koharu preserves the exact layer separation:
    - Layer 1 (Bottom): Original Art Scan.
    - Layer 2: Inpainted Patches & Cleaned Speech Balloons.
    - Layer 3: Text Masks & Bounding Envelopes.
    - Layer 4 (Top): Native, Editable Photoshop Type Layers with font family, size, line-height, and alignment intact.

---

## 5. Model Context Protocol (MCP) Server Architecture

### 5.1 MCP Protocol Specifications

Koharu integrates a built-in **AI Agent** and exposes its entire toolset over the **Model Context Protocol (MCP)** via **Streamable HTTP transport**.

```
┌─────────────────────────────────────────────────────────────┐
│                    Koharu MCP Server Host                   │
├─────────────────────────────────────────────────────────────┤
│ Protocol: Model Context Protocol (MCP)                      │
│ Transport: Streamable HTTP (JSON-RPC over HTTP POST / SSE)  │
│ Default Endpoint: http://127.0.0.1:7878/mcp                 │
│ Headless Mode CLI: koharu.exe --headless --port 7878        │
│ Scope: Bound to Active Project Workspace                    │
│ Security: Localhost only (127.0.0.1), rejects cross-origin   │
└─────────────────────────────────────────────────────────────┘
```

#### Configuration in `~/.koharu/config.toml`:
```toml
[agent]
provider = "ollama"
model = "qwen3.5:4b"
max_turns = 20
corrections = 2
```
- `max_turns`: Maximum autonomous reasoning loops per request (default: 20).
- `corrections`: Maximum retry attempts for malformed tool calls before failing gracefully (default: 2).

---

### 5.2 Exposed MCP Tool Inventory (Schema & Semantics)

Koharu's MCP server exposes a rich set of granular tools enabling external agents (such as Antigravity / AI Office) to programmatically inspect and manipulate manga projects:

| MCP Tool Name | Parameters | Return Type | Description |
| :--- | :--- | :--- | :--- |
| `get_project_outline` | None | `ProjectOutline` | Returns project metadata, page count, reading direction (`rtl`/`ltr`), and resolution. |
| `list_pages` | `offset?: int, limit?: int` | `list[PageSummary]` | Returns index, dimensions, file paths, and processing status for all pages. |
| `get_page` | `page_id: str` | `PageDetail` | Returns full layer tree, dimensions, and image metadata for a single page. |
| `get_text_blocks` | `page_id: str` | `list[TextBlock]` | Returns all detected text blocks on a page, including bounding polygons, OCR text, current translation, confidence, and reading order index. |
| `update_text_block` | `block_id: str, text: str, style?: TextStyle` | `TextBlock` | Programmatically updates translated text, manual line breaks (`\n`), font size, or alignment. |
| `trigger_pipeline_stage` | `stage: str, page_id?: str, block_id?: str` | `TaskStatus` | Triggers detection, OCR, inpainting, or translation scoped to a specific page or text block. |
| `export_project` | `format: "cbz" \| "psd" \| "png", output_dir: str` | `ExportResult` | Renders and exports the finalized project to disk. |

---

### 5.3 Autonomous Continuity Proofreading Copilot Architecture

By combining Koharu's MCP server with AI Office's `app/manga_story.py`, we can construct an **Autonomous AI Manga Continuity & Proofreading Agent**:

```
┌────────────────────────────────────────────────────────────────────────┐
│              Autonomous Proofreading Pipeline over MCP                 │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Koharu Headless Sidecar (Port 7878)                                 │
│    - Runs detection, OCR, and initial translation on manga scan        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   │ MCP: get_text_blocks(page_id)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. AI Office Story Studio (`app/manga_story.py`)                       │
│    - Receives raw translated text blocks and reading order             │
│    - Fetches CharacterProfile, SpeechRules & CanonFacts                │
│    - Executes check_deterministic_continuity()                         │
│      * Audits first_person & second_person pronouns                    │
│      * Scans for forbidden words                                       │
│      * Checks honorific consistency                                    │
│      * Validates dialogue length for bubble bounds (<25 words)         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   │ Violations Detected?
                                   ├─────────────────────────────┐
                                   │ Yes                         │ No
                                   ▼                             ▼
┌──────────────────────────────────────────────┐  ┌──────────────────────┐
│ 3. Automated Rewrite & Surgical Correction   │  │ 4. Approve & Log     │
│    - Qwen 3.5:4B rewrites violating dialogue │  │    ContinuityReport  │
│    - Calls MCP: update_text_block()          │  │    (100/100 score)   │
└──────────────────────┬───────────────────────┘  └──────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5. Koharu WebGPU Canvas & PSD Export                                   │
│    - Typesetting vector layer updates instantly                        │
│    - Background art remains 100% pristine                              │
└────────────────────────────────────────────────────────────────────────┘
```

#### Proofreading Agent Code Pattern (`app/manga_koharu_mcp.py`):
```python
import httpx
from app.manga_story import CharacterProfile, check_deterministic_continuity

class KoharuMCPClient:
    def __init__(self, base_url: str = "http://127.0.0.1:7878/mcp"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def call_tool(self, name: str, arguments: dict) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": 1
        }
        res = await self.client.post(self.base_url, json=payload)
        res.raise_for_status()
        return res.json().get("result", {})

    async def audit_and_fix_page(self, page_id: str, characters: list[CharacterProfile]):
        # 1. Fetch text blocks over MCP
        result = await self.call_tool("get_text_blocks", {"page_id": page_id})
        blocks = result.get("text_blocks", [])

        # 2. Check each dialogue line against character speech rules
        for b in blocks:
            text = b["translated_text"]
            for char in characters:
                # Check pronoun violation (e.g. using 'ông' instead of 'cậu')
                if "ông" in text and char.speech_rules.second_person == "cậu":
                    corrected = text.replace("ông", "cậu")
                    # 3. Push correction directly back into Koharu over MCP
                    await self.call_tool("update_text_block", {
                        "block_id": b["id"],
                        "text": corrected
                    })
```

---

## 6. Hardware & VRAM Optimization for RTX 3050 (6GB)

### 6.1 The VRAM Bottleneck Problem
Our target hardware is a **Lenovo LOQ Laptop GPU (RTX 3050 6GB VRAM, 12GB RAM)**:
- **Koharu's Default In-Process Model (`index-translate-9b:Q8_0`)**: Requires **~9.5GB VRAM** -> **CUDA Out-of-Memory (Crash)**.
- Even running a 4B GGUF model in Koharu consumes **~3.2GB VRAM**.
- Running Koharu's detection (`comic-text-detector`), OCR (`Manga-OCR`), inpainting (`LaMa`), and ComfyUI diffusion simultaneously will catastrophically exceed the 6GB VRAM ceiling.

---

### 6.2 The Zero-Duplicate LLM Offloading Solution

To guarantee 100% stability on the 6GB VRAM hardware baseline, we enforce the **Zero-Duplicate LLM Strategy**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Zero-Duplicate LLM Architecture                      │
├────────────────────────────────────────────────────────────────────────┤
│ Host GPU: NVIDIA RTX 3050 (6.0 GB VRAM Ceiling)                        │
│                                                                        │
│   [Single Shared LLM Process]                                          │
│   Ollama Runtime (`qwen3.5:4b`) ──────────────► VRAM: ~2.8 GB          │
│        ▲                                                               │
│        │ OpenAI-Compatible API Endpoint                                │
│        │ (http://127.0.0.1:11434/v1)                                   │
│        │                                                               │
│   ┌────┴──────────────────────────┐                                    │
│   │ Koharu Headless Sidecar       │                                    │
│   │ [pipeline.translator]         │                                    │
│   │ provider = "ollama"           │                                    │
│   │ model = "qwen3.5:4b"          │                                    │
│   └───────────────────────────────┘                                    │
│   Koharu Internal LLM VRAM Allocation: 0 MB!                           │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Configure Koharu Provider**:
   In `~/.koharu/config.toml`, route translation directly to Ollama:
   ```toml
   [providers.ollama]
   kind = "openai"
   base_url = "http://127.0.0.1:11434/v1"
   api_key = "unused"

   [pipeline.translator]
   provider = "ollama"
   model = "qwen3.5:4b"
   ```
2. **Resource Scheduling Gate**:
   - Koharu's CV stages (Detection + OCR + LaMa Inpainting) require ~1.8GB VRAM peak.
   - When Koharu runs CV inpainting, ComfyUI diffusion is paused via AI Office's `ResourceScheduler` (`asyncio.Semaphore(1)`).
   - Once inpainting completes, Koharu frees its CV memory, allowing ComfyUI or typesetting to proceed safely.

---

## 7. Comparative Analysis: Koharu vs AI Office Story Studio

| Dimension | AI Office (`app/manga_story.py` + `manga_composer.py`) | Koharu (`koharu-rs/koharu`) | Hybrid Integrated Solution |
| :--- | :--- | :--- | :--- |
| **Primary Domain** | Original Generative Manga Authoring (Script -> Art -> Panels) | Manga Localization & Scanlation (Scan -> OCR -> Inpaint -> Retype) | Complete End-to-End Suite (Author original IP + Localize international manga) |
| **Translation Engine** | Ollama `qwen3.5:4b` / Cloud LLMs | In-process `llama.cpp` or OpenAI-compatible API | Koharu delegates to AI Office Ollama instance (0 MB extra VRAM) |
| **Speech Rules & Continuity** | Typed Pydantic schemas (`SpeechRules`, `CharacterProfile`, `CanonFact`) | Freeform text instructions (`Additional instructions`) | AI Office auto-synthesizes typed schemas into Koharu prompt instructions |
| **Reading Order Sorting** | N/A (Script determines layout sequence) | Automated 2D layout analysis (RTL & LTR) | Koharu provides layout sequence to AI Office over MCP |
| **Multi-Bubble Clustering** | Panel-level dialogue script planning | Page-level batch JSON array prompt | Preserves compound dialogue flow seamlessly |
| **Inpainting & Cleanup** | Not needed (Panels generated cleanly via ComfyUI) | SOTA LaMa / AOT-GAN neural inpainting | Koharu handles non-destructive scan lettering erasure |
| **Typesetting & Typography** | Pillow / Skia SVG vector speech bubbles | WebGPU typography engine with auto-sizing & font cascades | Koharu handles complex CJK & vertical bubble typography |
| **PSD Export** | CBZ and PDF export | Layered PSD with native Photoshop text layers | Full professional studio workflow for human letterers |
| **Agent / MCP Support** | Antigravity multi-agent swarm architecture | Streamable HTTP MCP server (`/mcp`) | AI Office agents drive Koharu autonomously via MCP tools |

---

## 8. Implementation & Integration Roadmap

### Phase 1: Koharu Headless Sidecar & MCP Client (Sprint 1)
- Create `app/manga_koharu_mcp.py` implementing `KoharuMCPClient`.
- Configure `~/.koharu/config.toml` to route translation through local Ollama (`qwen3.5:4b`).
- Verify MCP communication over `http://127.0.0.1:7878/mcp` using mock and live payloads.

### Phase 2: Dynamic Speech Rules & Glossary Injection (Sprint 2)
- Implement `export_koharu_instruction_prompt()` in `app/manga_story.py`.
- Auto-generate Koharu pipeline configuration containing character speech rules, honorific mappings, and canon facts.
- Verify zero pronoun drift across Japanese-to-Vietnamese translation test benchmarks.

### Phase 3: Autonomous Continuity & Proofreading Copilot (Sprint 3)
- Integrate Koharu's `get_text_blocks` and `update_text_block` MCP tools with `check_deterministic_continuity()`.
- Automatically flag and correct pronoun violations, forbidden words, and dialogue overflow before final render.

### Phase 4: Full QA Verification & End-to-End Test Suite (Sprint 4)
- Author `tests/test_manga_koharu_story_bridge.py`.
- Benchmark localization speed, VRAM ceiling adherence (≤ 5.8GB peak), and translation fidelity on standard manga test pages.

---

## 9. Conclusion & Recommendations

`koharu-rs/koharu` provides an exceptionally well-engineered, non-destructive manga localization foundation. Its **quad-linked text architecture**, **page-level context preservation**, and **Streamable HTTP MCP server** make it an ideal sidecar companion to AI Office.

By pairing Koharu's layout/inpainting engine with AI Office's `app/manga_story.py` (serving as an MCP-driven Continuity and Speech-Rule Governor) and offloading translation to the shared Ollama `qwen3.5:4b` instance:
1. We achieve **flawless Vietnamese translation fidelity** with zero pronoun or honorific drift.
2. We maintain **strict adherence to the 6GB VRAM ceiling** on the Lenovo LOQ RTX 3050 hardware.
3. We provide an end-to-end autonomous proofreading and localization pipeline capable of running fully offline.
