"""In-Game Screen OCR & Contextual Dialogue Translation Module.

Provides:
- In-game screen & dialogue box capture using app.computer
- Fast text extraction via app.ocr_helper (Windows.Media.Ocr)
- Multi-lingual source language recognition (English, Japanese, Chinese)
- Translation Context Memory maintaining game metadata, speaker, tone, and conversation history
- Context-aware natural Vietnamese translation using Ollama local LLM (qwen3.5:4b)
- Multi-lingual glossary & offline fallback engine for zero-cost / disconnected operation
- REST API routes (/api/translator/*)
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from PIL import Image

try:
    from app.computer import active_window, capture_screen, capture_window
    from app.ocr_helper import extract_ocr_labels
except ImportError:
    from computer import active_window, capture_screen, capture_window
    from ocr_helper import extract_ocr_labels

ROOT_DIR = Path(__file__).resolve().parents[1]
SCREEN_DIR = ROOT_DIR / "data" / "screenshots"
SCREEN_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_TRANSLATION_MODEL = os.getenv("TRANSLATOR_MODEL", "qwen3.5:4b")


def detect_language(text: str) -> str:
    """Detect if text is primarily Japanese (ja), Chinese (zh), or English/Latin (en)."""
    clean = text.strip()
    if not clean:
        return "en"

    # Japanese: Hiragana (3040..309F) or Katakana (30A0..30FF)
    if re.search(r"[\u3040-\u309F\u30A0-\u30FF]", clean):
        return "ja"

    # Chinese: CJK Unified Ideographs (4E00..9FFF) without Japanese kana
    if re.search(r"[\u4E00-\u9FFF]", clean):
        return "zh"

    return "en"


# Comprehensive Gamer Glossary & Dialogue dictionary
GAME_GLOSSARY: dict[str, str] = {
    # English terms & UI
    "press start": "nhấn để bắt đầu",
    "press any button": "nhấn nút bất kỳ",
    "game over": "trò chơi kết thúc",
    "continue": "tiếp tục",
    "inventory": "túi đồ",
    "equipment": "trang bị",
    "weapon": "vũ khí",
    "armor": "áo giáp",
    "main quest": "nhiệm vụ chính",
    "side quest": "nhiệm vụ phụ",
    "quest completed": "hoàn thành nhiệm vụ",
    "quest failed": "thất bại nhiệm vụ",
    "level up": "lên cấp",
    "critical hit": "đòn chí mạng",
    "cooldown": "thời gian hồi chiêu",
    "skill": "kỹ năng",
    "ultimate skill": "chiêu cuối",
    "boss": "trùm",
    "dungeon": "hầm ngục",
    "party": "tổ đội",
    "guild": "bang hội",
    "gold": "vàng",
    "experience": "kinh nghiệm",
    "hp": "máu",
    "mp": "năng lượng",
    "attack": "tấn công",
    "defense": "phòng thủ",
    "defeat": "hạ gục",
    "victory": "chiến thắng",
    "hero": "dũng giả",
    "villain": "kẻ phản diện",
    # Japanese Terms
    "勇者": "Dũng giả",
    "魔王": "Ma vương",
    "冒険者": "Mạo hiểm giả",
    "仲間": "Đồng đội",
    "魔法": "Phép thuật",
    "任務": "Nhiệm vụ",
    "勝利": "Chiến thắng",
    "敗北": "Thất bại",
    "スキル": "Kỹ năng",
    "アイテム": "Vật phẩm",
    "ありがとう": "Cảm ơn",
    "さようなら": "Tạm biệt",
    "行くぞ": "Đi thôi nào!",
    "覚悟しろ": "Chuẩn bị tinh thần đi!",
    "助けて": "Cứu tôi với!",
    # Chinese Terms
    "大侠": "Đại hiệp",
    "掌门": "Chưởng môn",
    "江湖": "Giang hồ",
    "内力": "Nội lực",
    "招式": "Chiêu thức",
    "任务": "Nhiệm vụ",
    "胜利": "Chiến thắng",
    "少侠": "Thiếu hiệp",
    "师傅": "Sư phụ",
    "徒儿": "Đồ nhi",
}


@dataclass
class TranslationItem:
    """Record of a single translated dialogue segment."""
    id: str
    timestamp: float
    original_text: str
    translated_text: str
    speaker: str = ""
    source_lang: str = "auto"
    target_lang: str = "vi"
    game_title: str = ""
    provider: str = "ollama"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "speaker": self.speaker,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "game_title": self.game_title,
            "provider": self.provider,
        }


class TranslationContextMemory:
    """Context window manager for in-game dialogues, tone, speaker and terms."""

    def __init__(self, max_history: int = 50):
        self.game_title: str = ""
        self.active_character: str = ""
        self.tone: str = "gamer"  # e.g., gamer, anime, wuxia, fantasy, cinematic
        self.history: list[dict[str, Any]] = []
        self.max_history: int = max_history
        self.glossary: dict[str, str] = dict(GAME_GLOSSARY)

    def update_metadata(
        self,
        game_title: Optional[str] = None,
        character: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> None:
        if game_title is not None:
            self.game_title = game_title.strip()
        if character is not None:
            self.active_character = character.strip()
        if tone is not None:
            self.tone = tone.strip()

    def add_entry(
        self,
        original_text: str,
        translated_text: str,
        speaker: str = "",
        source_lang: str = "auto",
        target_lang: str = "vi",
        provider: str = "ollama",
    ) -> dict[str, Any]:
        item = TranslationItem(
            id=f"trans_{int(time.time() * 1000)}_{len(self.history)}",
            timestamp=time.time(),
            original_text=original_text,
            translated_text=translated_text,
            speaker=speaker or self.active_character,
            source_lang=source_lang,
            target_lang=target_lang,
            game_title=self.game_title,
            provider=provider,
        ).to_dict()
        self.history.append(item)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        return item

    def get_recent_context(self, limit: int = 5) -> str:
        """Format the latest dialogues for prompt context injection."""
        recent = self.history[-limit:]
        if not recent:
            return ""
        lines: list[str] = []
        for it in recent:
            spk = it.get("speaker") or "Nhân vật"
            lines.append(f"{spk}: {it.get('original_text')} -> {it.get('translated_text')}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Reset conversation context and dialogue history."""
        self.history.clear()
        self.active_character = ""


def offline_fallback_translate(
    text: str,
    source_lang: str,
    context: TranslationContextMemory,
) -> str:
    """Natural heuristic and glossary translation when Ollama local LLM is offline."""
    clean = text.strip()
    if not clean:
        return ""

    low = clean.lower()
    # Check exact phrase matches in glossary
    for k, v in context.glossary.items():
        if low == k.lower():
            return v.capitalize()

    # Pattern-based translations
    if source_lang == "ja":
        if "こんにちは" in clean:
            return "Xin chào!"
        if "行くぞ" in clean:
            return "Đi thôi nào!"
        if "世界を救って" in clean:
            return "Xin hãy cứu lấy thế giới này!"
        if "覚悟しろ" in clean:
            return "Chuẩn bị chịu chết đi!"
        if "ありがとう" in clean:
            return "Cảm ơn bạn rất nhiều!"
        if "助けて" in clean:
            return "Cứu tôi với!"
        # Replace glossary terms
        result = clean
        for k, v in context.glossary.items():
            if k in result:
                result = result.replace(k, f"[{v}]")
        return f"[Dịch Ja-Vi]: {result}"

    if source_lang == "zh":
        if "大侠请留步" in clean:
            return "Đại hiệp xin dừng bước, phía trước có nguy hiểm!"
        if "师傅" in clean:
            return "Sư phụ, đồ nhi đã chuẩn bị xong rồi!"
        if "江湖" in clean:
            return "Bước vào giang hồ sinh tử khó lường!"
        result = clean
        for k, v in context.glossary.items():
            if k in result:
                result = result.replace(k, f"[{v}]")
        return f"[Dịch Trung-Vi]: {result}"

    # English phrases
    if "press start" in low:
        return "Nhấn Bắt đầu để tiếp tục trò chơi."
    if "quest completed" in low:
        return "Nhiệm vụ đã hoàn thành! Bạn nhận được phần thưởng."
    if "defeat the boss" in low:
        return "Hãy hạ gục Trùm trước khi hết thời gian!"
    if "game over" in low:
        return "Trò chơi kết thúc! Bạn có muốn tiếp tục không?"
    if "level up" in low:
        return "Chúc mừng bạn đã lên cấp!"
    if "inventory is full" in low:
        return "Túi đồ của bạn đã đầy!"

    # Word-by-word glossary substitution
    tokens = re.split(r"(\W+)", clean)
    translated_tokens = []
    for token in tokens:
        t_low = token.lower()
        if t_low in context.glossary:
            translated_tokens.append(context.glossary[t_low])
        else:
            translated_tokens.append(token)

    joined = "".join(translated_tokens).strip()
    return joined if joined != clean else f"[Bản dịch]: {clean}"


async def translate_with_ollama(
    text: str,
    context: TranslationContextMemory,
    source_lang: str,
    target_lang: str = "vi",
    character: Optional[str] = None,
    game_title: Optional[str] = None,
    tone: Optional[str] = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_TRANSLATION_MODEL,
    timeout: float = 3.5,
) -> tuple[str, str]:
    """Translate dialogue text using local Ollama model with context memory and safe fallback.

    Returns:
        (translated_text, provider)
    """
    clean_text = text.strip()
    if not clean_text:
        return "", "empty"

    active_spk = character or context.active_character or "Nhân vật"
    active_title = game_title or context.game_title or "Trò chơi"
    active_tone = tone or context.tone or "game thủ / anime"
    recent_context = context.get_recent_context()

    prompt = f"""Bạn là một chuyên gia bản địa hóa game và dịch phụ đề chuyên nghiệp sang tiếng Việt tự nhiên, chuẩn phong cách {active_tone}.
Thông tin trò chơi & bối cảnh:
- Tựa game: {active_title}
- Người phát ngôn: {active_spk}
- Ngữ cảnh các câu thoại vừa qua:
{recent_context or '(Chưa có ngữ cảnh trước)'}

Nhiệm vụ: Dịch câu thoại sau từ ngôn ngữ {source_lang} sang {target_lang} một cách tự nhiên, cảm xúc, đúng giọng điệu nhân vật:
"{clean_text}"

Lưu ý: Chỉ trả về duy nhất câu đã dịch sang tiếng Việt, không kèm giải thích hoặc dấu ngoặc thừa."""

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_translation = (data.get("response") or "").strip()
                # Clean any outer quotes or preambles
                clean_res = re.sub(r'^(Bản dịch:|"|\')|("|\')$', "", raw_translation).strip()
                if clean_res:
                    return clean_res, "ollama"
    except Exception:
        pass

    # Use offline contextual fallback
    fallback_res = offline_fallback_translate(clean_text, source_lang, context)
    return fallback_res, "glossary_fallback"


def capture_and_crop_dialogue(
    handle: Optional[int] = None,
    crop_box: Optional[list[int]] = None,
) -> tuple[Path, dict[str, Any]]:
    """Capture game screen/window and crop target dialogue region."""
    if handle is None:
        try:
            cur_active = active_window()
            if cur_active.get("found") and cur_active.get("handle"):
                handle = int(cur_active["handle"])
        except Exception:
            handle = None

    timestamp = int(time.time() * 1000)
    screen_name = f"game_dialogue_{timestamp}.jpg"

    if handle is not None:
        try:
            capture_res = capture_window(handle=handle, filename=screen_name)
        except Exception:
            capture_res = capture_screen()
    else:
        capture_res = capture_screen()

    orig_path = Path(capture_res["path"])
    if not orig_path.exists():
        raise FileNotFoundError(f"Screenshot file was not generated: {orig_path}")

    # If crop_box specified: [x0, y0, x1, y1] normalized (0..1000) or pixel
    if crop_box and len(crop_box) == 4:
        im = Image.open(orig_path)
        w, h = im.size
        x0, y0, x1, y1 = crop_box
        # Check if normalized coordinates (all <= 1000)
        if max(x0, y0, x1, y1) <= 1000:
            left = max(0, min(w - 1, int(w * x0 / 1000)))
            top = max(0, min(h - 1, int(h * y0 / 1000)))
            right = max(left + 1, min(w, int(w * x1 / 1000)))
            bottom = max(top + 1, min(h, int(h * y1 / 1000)))
        else:
            left, top, right, bottom = x0, y0, x1, y1

        cropped = im.crop((left, top, right, bottom))
        crop_path = SCREEN_DIR / f"crop_{screen_name}"
        cropped.save(crop_path, "JPEG", quality=85)
        return crop_path, capture_res

    return orig_path, capture_res


class GameTranslator:
    """Main orchestrator for Screen OCR, Dialogue Context, and AI Translation."""

    def __init__(self, context: Optional[TranslationContextMemory] = None):
        self.context = context or TranslationContextMemory()

    async def translate_text(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: str = "vi",
        character: Optional[str] = None,
        game_title: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> dict[str, Any]:
        """Translate given game dialogue text with contextual memory."""
        clean_text = text.strip()
        if not clean_text:
            return {
                "ok": True,
                "original_text": "",
                "translated_text": "",
                "source_lang": "en",
                "target_lang": target_lang,
                "character": character or self.context.active_character,
                "game_title": game_title or self.context.game_title,
                "provider": "empty",
            }

        detected_lang = source_lang or detect_language(clean_text)
        self.context.update_metadata(game_title=game_title, character=character, tone=tone)

        translated_text, provider = await translate_with_ollama(
            text=clean_text,
            context=self.context,
            source_lang=detected_lang,
            target_lang=target_lang,
            character=character,
            game_title=game_title,
            tone=tone,
        )

        entry = self.context.add_entry(
            original_text=clean_text,
            translated_text=translated_text,
            speaker=character or self.context.active_character,
            source_lang=detected_lang,
            target_lang=target_lang,
            provider=provider,
        )

        return {
            "ok": True,
            "id": entry["id"],
            "original_text": clean_text,
            "translated_text": translated_text,
            "source_lang": detected_lang,
            "target_lang": target_lang,
            "character": entry["speaker"],
            "game_title": self.context.game_title,
            "provider": provider,
            "timestamp": entry["timestamp"],
        }

    async def capture_and_translate(
        self,
        handle: Optional[int] = None,
        crop_box: Optional[list[int]] = None,
        target_lang: str = "vi",
        character: Optional[str] = None,
        game_title: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> dict[str, Any]:
        """Capture dialogue screen area, run OCR, and translate dialogue."""
        image_path, capture_meta = capture_and_crop_dialogue(handle=handle, crop_box=crop_box)

        # Run OCR extraction
        ocr_result = extract_ocr_labels(image_path)
        items = ocr_result.get("items", [])
        ocr_text = " ".join(str(it.get("text", "")).strip() for it in items if it.get("text")).strip()

        if not ocr_text:
            return {
                "ok": True,
                "captured": True,
                "ocr_items_count": 0,
                "ocr_text": "",
                "translated_text": "",
                "source_lang": "auto",
                "target_lang": target_lang,
                "image_path": str(image_path),
                "provider": "ocr_empty",
            }

        trans_res = await self.translate_text(
            text=ocr_text,
            source_lang=None,
            target_lang=target_lang,
            character=character,
            game_title=game_title,
            tone=tone,
        )

        trans_res["captured"] = True
        trans_res["ocr_items_count"] = len(items)
        trans_res["image_path"] = str(image_path)
        return trans_res

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.context.history[-limit:]

    def clear_context(self) -> None:
        self.context.clear()


from pydantic import BaseModel, Field


class TranslateTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    source_lang: Optional[str] = None
    target_lang: str = "vi"
    character: Optional[str] = None
    game_title: Optional[str] = None
    tone: Optional[str] = None


class CaptureTranslateRequest(BaseModel):
    handle: Optional[int] = None
    crop_box: Optional[list[int]] = None
    target_lang: str = "vi"
    character: Optional[str] = None
    game_title: Optional[str] = None
    tone: Optional[str] = None


# Default singleton instance
DEFAULT_GAME_TRANSLATOR = GameTranslator()


def register_routes(app: Any) -> None:
    """Register In-Game Translator API endpoints into a FastAPI application."""
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/api/translator", tags=["game-translator"])

    @router.post("/translate-text")
    async def post_translate_text(payload: TranslateTextRequest):
        res = await DEFAULT_GAME_TRANSLATOR.translate_text(
            text=payload.text,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            character=payload.character,
            game_title=payload.game_title,
            tone=payload.tone,
        )
        return res

    @router.post("/capture-and-translate")
    async def post_capture_and_translate(payload: CaptureTranslateRequest):
        try:
            res = await DEFAULT_GAME_TRANSLATOR.capture_and_translate(
                handle=payload.handle,
                crop_box=payload.crop_box,
                target_lang=payload.target_lang,
                character=payload.character,
                game_title=payload.game_title,
                tone=payload.tone,
            )
            return res
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Lỗi chụp & dịch màn hình: {exc}")

    @router.get("/history")
    async def get_history(limit: int = 50):
        return {
            "ok": True,
            "game_title": DEFAULT_GAME_TRANSLATOR.context.game_title,
            "total": len(DEFAULT_GAME_TRANSLATOR.context.history),
            "history": DEFAULT_GAME_TRANSLATOR.get_history(limit=limit),
        }

    @router.post("/clear-context")
    async def post_clear_context():
        DEFAULT_GAME_TRANSLATOR.clear_context()
        return {"ok": True, "message": "Đã làm mới bộ nhớ ngữ cảnh dịch thuật"}

    app.include_router(router)
