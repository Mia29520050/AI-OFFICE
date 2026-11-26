from __future__ import annotations

import asyncio
import re
import threading
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

import computer
from grounded_search import execute_web_search
from ocr_helper import extract_ocr_labels
from vtuber_models import MOOD_TO_EXPRESSION

CS2_MAPS = (
    "mirage",
    "inferno",
    "dust2",
    "dust 2",
    "nuke",
    "ancient",
    "anubis",
    "vertigo",
    "overpass",
    "train",
)

CODING_HINTS = (
    "visual studio code",
    "vscode",
    "pycharm",
    "cursor",
    "windsurf",
    "intellij",
    "antigravity",
    "powershell",
    "terminal",
    "github",
    ".py",
    ".ts",
    ".js",
    "pytest",
    "def ",
    "import ",
)

GAME_HINTS = (
    "counter-strike",
    "cs2",
    "valorant",
    "league of legends",
    "dota 2",
    "honkai",
    "genshin",
    "chaos zero nightmare",
    "elden ring",
    "overwatch",
    "apex legends",
)

BROWSER_HINTS = (
    "chrome",
    "edge",
    "firefox",
    "brave",
    "opera",
    "youtube",
    "twitch",
    "hltv",
    "http",
)

VALID_MOODS = tuple(MOOD_TO_EXPRESSION.keys())


class CompanionStartRequest(BaseModel):
    vtuber_name: str = Field(default="Mina AI", max_length=60)
    interval_s: float = Field(default=6.0, ge=1.0, le=120.0)
    cooldown_s: float = Field(default=12.0, ge=0.0, le=300.0)
    use_web: bool = False
    max_width: int = Field(default=640, ge=320, le=1920)
    quality: int = Field(default=55, ge=25, le=95)


class CompanionTickRequest(BaseModel):
    force: bool = False
    use_web: bool | None = None


class CS2AnalyzeRequest(BaseModel):
    title: str = Field(default="", max_length=300)
    ocr_text: str = Field(default="", max_length=3000)
    team_a: str = Field(default="", max_length=80)
    team_b: str = Field(default="", max_length=80)
    score_a: int | None = Field(default=None, ge=0, le=60)
    score_b: int | None = Field(default=None, ge=0, le=60)
    map_name: str = Field(default="", max_length=40)
    economy_a: str = Field(default="", max_length=40)
    economy_b: str = Field(default="", max_length=40)
    use_web: bool = False


def detect_screen_context(window_title: str, ocr_text: str = "", process_name: str = "") -> str:
    """Classify the user's current screen activity from window title, process, and OCR text."""
    title_low = (window_title or "").lower()
    proc_low = (process_name or "").lower()
    ocr_low = (ocr_text or "").lower()
    combined = f"{title_low} {proc_low} {ocr_low}"

    is_video_stream = any(tok in title_low for tok in ("youtube", "twitch", "kick", "hltv", "esl", "blast", "pgl"))
    is_cs2 = any(
        tok in combined
        for tok in ("cs2", "counter-strike 2", "counter-strike", "hltv", "blast premier", "esl pro league", "pgl major")
    )
    if is_cs2 and is_video_stream:
        return "youtube_cs2"
    if is_cs2:
        return "gaming_cs2"
    if any(tok in title_low or tok in proc_low for tok in CODING_HINTS) or any(
        tok in combined for tok in ("traceback", "syntaxerror", "git commit", "fastapi")
    ):
        return "coding"
    if any(tok in title_low or tok in proc_low for tok in GAME_HINTS):
        return "gaming"
    if any(tok in title_low or tok in proc_low for tok in BROWSER_HINTS):
        return "browsing"
    return "general"


def _extract_economy_hint(text_low: str) -> str:
    if "eco" in text_low or "save" in text_low:
        return "eco"
    if "force" in text_low or "half buy" in text_low:
        return "force"
    if "full buy" in text_low or "rifle" in text_low or "awp" in text_low:
        return "full_buy"
    money_matches = re.findall(r"\$\s*(\d{3,5})", text_low)
    if money_matches:
        vals = [int(m) for m in money_matches]
        avg = sum(vals) / len(vals)
        if avg < 2000:
            return "eco"
        if avg < 3700:
            return "force"
        return "full_buy"
    return "unknown"


def parse_cs2_match_state(title: str, ocr_text: str = "") -> dict[str, Any]:
    """Extract CS2 teams, round score, map, side, and economy hints from title + OCR."""
    combined = f"{title or ''} | {ocr_text or ''}"
    low = combined.lower()

    team_a = "Team A"
    team_b = "Team B"
    vs_match = re.search(
        r"([A-Za-z0-9][A-Za-z0-9 ._-]{1,24}?)\s+(?:vs\.?|v\.?)\s+([A-Za-z0-9][A-Za-z0-9 ._-]{1,24}?)(?:\s*[-|\[\(]|$|\s+(?:map|bo\d|mirage|inferno|nuke|dust|ancient|anubis|vertigo|overpass|train|live|highlights|cs2))",
        combined,
        flags=re.IGNORECASE,
    )
    if vs_match:
        team_a = vs_match.group(1).strip(" -|[]()")
        team_b = vs_match.group(2).strip(" -|[]()")

    score_a = 0
    score_b = 0
    has_score = False
    score_match = re.search(r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)", combined)
    if score_match:
        a_val, b_val = int(score_match.group(1)), int(score_match.group(2))
        if a_val <= 30 and b_val <= 30:
            score_a, score_b = a_val, b_val
            has_score = True

    map_name = ""
    for mp in CS2_MAPS:
        if mp in low:
            map_name = "Dust 2" if mp in ("dust2", "dust 2") else mp.title()
            break

    economy = _extract_economy_hint(low)
    overtime = score_a >= 12 and score_b >= 12
    match_point = (score_a == 12 and score_b < 12) or (score_b == 12 and score_a < 12)
    is_cs2 = any(tok in low for tok in ("cs2", "counter-strike", "hltv", "blast", "esl", "pgl")) or bool(map_name)

    return {
        "is_cs2": is_cs2,
        "team_a": team_a,
        "team_b": team_b,
        "score_a": score_a,
        "score_b": score_b,
        "has_score": has_score,
        "map_name": map_name or "Unknown",
        "economy": economy,
        "overtime": overtime,
        "match_point": match_point,
    }


def _economy_bonus(econ: str) -> float:
    return {"full_buy": 0.06, "force": -0.03, "eco": -0.09}.get(econ, 0.0)


def estimate_cs2_win_probability(
    match_state: dict[str, Any],
    *,
    use_web: bool = False,
) -> dict[str, Any]:
    """Estimate CS2 win probability using round/economy heuristics plus optional grounded_search."""
    team_a = str(match_state.get("team_a") or "Team A")
    team_b = str(match_state.get("team_b") or "Team B")
    score_a = int(match_state.get("score_a") or 0)
    score_b = int(match_state.get("score_b") or 0)
    map_name = str(match_state.get("map_name") or "Unknown")
    econ_a = str(match_state.get("economy_a") or match_state.get("economy") or "unknown")
    econ_b = str(match_state.get("economy_b") or "unknown")

    # MR12 heuristic: each round lead shifts win probability; amplified near match point (13 rounds to win)
    diff = score_a - score_b
    rounds_played = score_a + score_b
    progress_weight = 0.032 + min(0.025, rounds_played * 0.0012)
    prob_a = 0.5 + diff * progress_weight
    factors: list[str] = []

    if diff != 0:
        leader = team_a if diff > 0 else team_b
        factors.append(f"{leader} đang dẫn {abs(diff)} round ({score_a}-{score_b})")
    else:
        factors.append(f"Tỉ số đang cân bằng ({score_a}-{score_b})")

    if score_a >= 12 and score_a > score_b:
        prob_a += 0.08
        factors.append(f"{team_a} đang chạm Match Point")
    elif score_b >= 12 and score_b > score_a:
        prob_a -= 0.08
        factors.append(f"{team_b} đang chạm Match Point")

    ea_bonus = _economy_bonus(econ_a)
    eb_bonus = _economy_bonus(econ_b)
    if ea_bonus != eb_bonus:
        prob_a += ea_bonus - eb_bonus
        factors.append(f"Kinh tế: {team_a}={econ_a}, {team_b}={econ_b}")

    search_snippets: list[str] = []
    source_mode = "heuristic_offline"
    if use_web and team_a != "Team A" and team_b != "Team B":
        try:
            query = f"CS2 {team_a} vs {team_b} {map_name if map_name != 'Unknown' else ''} HLTV win rate".strip()
            results = execute_web_search(query, max_results=2, timeout=4.0)
            valid_snippets = [
                r.compressed_text
                for r in results
                if r.domain != "ai-office.local" and r.compressed_text
            ]
            if valid_snippets:
                search_snippets = valid_snippets[:2]
                source_mode = "grounded_search+heuristic"
                joined = " ".join(valid_snippets).lower()
                if team_a.lower() in joined and any(w in joined for w in ("favorite", "win", "streak", "rank #1")):
                    prob_a += 0.03
                    factors.append(f"Tra cứu web ghi nhận phong độ tốt cho {team_a}")
                elif team_b.lower() in joined and any(w in joined for w in ("favorite", "win", "streak", "rank #1")):
                    prob_a -= 0.03
                    factors.append(f"Tra cứu web ghi nhận phong độ tốt cho {team_b}")
        except Exception:
            pass

    prob_a = max(0.05, min(0.95, prob_a))
    pct_a = round(prob_a * 100)
    pct_b = 100 - pct_a

    return {
        "team_a": team_a,
        "team_b": team_b,
        "score_a": score_a,
        "score_b": score_b,
        "map_name": map_name,
        "team_a_prob": pct_a,
        "team_b_prob": pct_b,
        "favored": team_a if pct_a >= pct_b else team_b,
        "factors": factors,
        "source": source_mode,
        "search_snippets": search_snippets,
    }


def select_mood_for_context(context: str, cs2_analysis: dict[str, Any] | None = None) -> tuple[str, str]:
    """Choose a VTuber mood and map it to Live2D expression ID from vtuber_models.MOOD_TO_EXPRESSION."""
    if cs2_analysis:
        sa = int(cs2_analysis.get("score_a") or 0)
        sb = int(cs2_analysis.get("score_b") or 0)
        diff = abs(sa - sb)
        if sa >= 12 or sb >= 12:
            mood = "panic" if diff <= 1 else "excited"
        elif diff <= 2 and (sa + sb) > 0:
            mood = "surprised"
        elif diff >= 5:
            mood = "happy"
        else:
            mood = "thinking"
    else:
        mood = {
            "youtube_cs2": "excited",
            "gaming_cs2": "excited",
            "gaming": "happy",
            "coding": "thinking",
            "browsing": "happy",
            "general": "happy",
        }.get(context, "happy")

    if mood not in MOOD_TO_EXPRESSION:
        mood = "happy"
    return mood, MOOD_TO_EXPRESSION[mood]


def _fallback_commentary(
    vtuber_name: str,
    context: str,
    window_title: str,
    cs2_analysis: dict[str, Any] | None = None,
) -> str:
    if cs2_analysis:
        ta = cs2_analysis["team_a"]
        tb = cs2_analysis["team_b"]
        pa = cs2_analysis["team_a_prob"]
        pb = cs2_analysis["team_b_prob"]
        sa = cs2_analysis["score_a"]
        sb = cs2_analysis["score_b"]
        mp = cs2_analysis["map_name"]
        if abs(sa - sb) <= 1 and (sa >= 11 or sb >= 11):
            return f"Căng cực luôn Master ơi! {ta} {sa}-{sb} {tb} trên {mp}, tỉ lệ thắng đang là {pa}% - {pb}%, nín thở xem round này nào!"
        return f"Kèo {ta} vs {tb} ({sa}-{sb}, map {mp}): {vtuber_name} tạm tính {ta} {pa}% - {tb} {pb}% nhé Master!"

    templates = {
        "youtube_cs2": "Master đang xem highlight CS2 hả? Để em soi kèo cùng Master nha!",
        "gaming_cs2": "Vào CS2 rồi! Nhớ check góc kỹ và giữ kinh tế round này nha Master!",
        "gaming": f"Đang chiến game '{window_title[:40]}' cực cháy luôn, cố lên Master!",
        "coding": "Master đang code hăng say quá! Nhớ uống ngụm nước kẻo mỏi mắt nha~",
        "browsing": "Đang lướt web tìm thông tin gì thú vị thế Master, cho em hóng với!",
        "general": f"{vtuber_name} vẫn đang ngồi ngoan quan sát màn hình cùng Master nè!",
    }
    return templates.get(context, templates["general"])


async def generate_vtuber_commentary(
    *,
    vtuber_name: str,
    context: str,
    window_title: str,
    ocr_text: str,
    cs2_analysis: dict[str, Any] | None = None,
    ollama_chat_fn: Any | None = None,
) -> tuple[str, str]:
    """Generate natural Vietnamese VTuber commentary via local Ollama with fun offline fallback."""
    fallback = _fallback_commentary(vtuber_name, context, window_title, cs2_analysis)
    if ollama_chat_fn is None:
        try:
            import main as m  # type: ignore
            ollama_chat_fn = getattr(m, "ollama_chat", None)
        except Exception:
            ollama_chat_fn = None

    if ollama_chat_fn is None:
        return fallback, "fallback"

    cs2_line = ""
    if cs2_analysis:
        cs2_line = (
            f"CS2 Match: {cs2_analysis['team_a']} {cs2_analysis['score_a']}-{cs2_analysis['score_b']} "
            f"{cs2_analysis['team_b']} on {cs2_analysis['map_name']} "
            f"(Win prob: {cs2_analysis['team_a_prob']}% vs {cs2_analysis['team_b_prob']}%). "
        )
    prompt = (
        f"Bạn là {vtuber_name}, AI VTuber tiếng Việt vui tính đang ngồi xem màn hình cùng Master. "
        f"Bối cảnh: {context}. Cửa sổ: {window_title[:120]}. {cs2_line}"
        f"OCR tóm tắt: {ocr_text[:220]}. "
        "Hãy viết ĐÚNG 1 câu bình luận tự nhiên, dí dỏm bằng tiếng Việt (tối đa 35 từ)."
    )
    try:
        raw = await asyncio.wait_for(
            ollama_chat_fn(
                [{"role": "user", "content": prompt}],
                json_mode=False,
                num_predict=90,
                num_ctx=2048,
                temperature=0.7,
            ),
            timeout=6.0,
        )
        cleaned = " ".join(str(raw or "").strip().split())
        if cleaned:
            return cleaned[:240], "ollama"
    except Exception:
        pass
    return fallback, "fallback"


class VTuberCompanionManager:
    """Passive screen observer + CS2 match analyst + Live2D mood/commentary companion."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._task: asyncio.Task | None = None
        self._stop_flag = False
        self._last_comment_at: float = 0.0
        self._last_signature: str = ""
        self.state: dict[str, Any] = {
            "active": False,
            "vtuber_name": "Mina AI",
            "interval_s": 6.0,
            "cooldown_s": 12.0,
            "use_web": False,
            "max_width": 640,
            "quality": 55,
            "context": "general",
            "window_title": "",
            "mood": "happy",
            "expression": MOOD_TO_EXPRESSION["happy"],
            "comment": "Mina AI sẵn sàng đồng hành cùng Master!",
            "comment_source": "fallback",
            "cs2_analysis": None,
            "last_tick_at": 0.0,
            "cooldown_remaining_s": 0.0,
            "history": [],
            "error": "",
        }

    def snapshot_state(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            cd = max(0.0, float(self.state["cooldown_s"]) - (now - self._last_comment_at)) if self._last_comment_at else 0.0
            return {
                **self.state,
                "cooldown_remaining_s": round(cd, 2),
                "history": list(self.state.get("history", []))[-10:],
            }

    def _update(self, **kwargs: Any) -> None:
        with self._lock:
            self.state.update(kwargs)

    async def start(self, req: CompanionStartRequest) -> dict[str, Any]:
        await self.stop()
        self._stop_flag = False
        self._update(
            active=True,
            vtuber_name=req.vtuber_name,
            interval_s=req.interval_s,
            cooldown_s=req.cooldown_s,
            use_web=req.use_web,
            max_width=req.max_width,
            quality=req.quality,
            error="",
        )
        self._task = asyncio.create_task(self._loop())
        return {"ok": True, **self.snapshot_state()}

    async def stop(self) -> dict[str, Any]:
        self._stop_flag = True
        task = self._task
        self._task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._update(active=False)
        return {"ok": True, **self.snapshot_state()}

    async def _loop(self) -> None:
        while not self._stop_flag:
            try:
                await self.tick(force=False)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._update(error=str(exc))
            await asyncio.sleep(float(self.state.get("interval_s", 6.0)))

    async def tick(
        self,
        *,
        force: bool = False,
        use_web: bool | None = None,
        ollama_chat_fn: Any | None = None,
    ) -> dict[str, Any]:
        """Observe active window + lightweight screen OCR once, respecting anti-spam cooldown."""
        win = await asyncio.to_thread(computer.active_window)
        window_title = str(win.get("title", "") or "")
        process_name = str(win.get("process_name", "") or "")

        shot = await asyncio.to_thread(
            computer.capture_screen,
            max_width=int(self.state.get("max_width", 640)),
            quality=int(self.state.get("quality", 55)),
        )
        ocr_text = ""
        try:
            ocr_res = await asyncio.to_thread(extract_ocr_labels, shot["path"], max_items=18)
            items = ocr_res.get("items", []) or []
            ocr_text = " | ".join(str(it.get("text", "")).strip() for it in items if it.get("text"))
        except Exception:
            ocr_text = ""

        context = detect_screen_context(window_title, ocr_text, process_name)
        cs2_analysis: dict[str, Any] | None = None
        effective_web = self.state["use_web"] if use_web is None else use_web

        if context in {"youtube_cs2", "gaming_cs2"}:
            parsed = parse_cs2_match_state(window_title, ocr_text)
            cs2_analysis = estimate_cs2_win_probability(parsed, use_web=bool(effective_web))

        mood, expression = select_mood_for_context(context, cs2_analysis)
        now = time.time()
        cooldown_s = float(self.state.get("cooldown_s", 12.0))
        signature = f"{context}:{window_title[:60]}:{cs2_analysis['score_a'] if cs2_analysis else ''}-{cs2_analysis['score_b'] if cs2_analysis else ''}"

        in_cooldown = (not force) and self._last_comment_at > 0 and (now - self._last_comment_at) < cooldown_s
        same_as_last = (not force) and signature == self._last_signature and self._last_comment_at > 0 and (now - self._last_comment_at) < (cooldown_s * 2)

        if in_cooldown or same_as_last:
            self._update(
                context=context,
                window_title=window_title,
                mood=mood,
                expression=expression,
                cs2_analysis=cs2_analysis,
                last_tick_at=now,
            )
            return {"ok": True, "skipped_comment": True, "reason": "cooldown", **self.snapshot_state()}

        comment, source = await generate_vtuber_commentary(
            vtuber_name=str(self.state.get("vtuber_name", "Mina AI")),
            context=context,
            window_title=window_title,
            ocr_text=ocr_text,
            cs2_analysis=cs2_analysis,
            ollama_chat_fn=ollama_chat_fn,
        )
        self._last_comment_at = now
        self._last_signature = signature
        with self._lock:
            history = list(self.state.get("history", []))
            history.append({
                "at": now,
                "context": context,
                "mood": mood,
                "expression": expression,
                "comment": comment,
            })
            self.state.update({
                "context": context,
                "window_title": window_title,
                "mood": mood,
                "expression": expression,
                "comment": comment,
                "comment_source": source,
                "cs2_analysis": cs2_analysis,
                "last_tick_at": now,
                "history": history[-10:],
                "error": "",
            })
        return {"ok": True, "skipped_comment": False, **self.snapshot_state()}

    async def analyze_cs2(self, req: CS2AnalyzeRequest, ollama_chat_fn: Any | None = None) -> dict[str, Any]:
        parsed = parse_cs2_match_state(req.title, req.ocr_text)
        if req.team_a:
            parsed["team_a"] = req.team_a
        if req.team_b:
            parsed["team_b"] = req.team_b
        if req.score_a is not None:
            parsed["score_a"] = req.score_a
        if req.score_b is not None:
            parsed["score_b"] = req.score_b
        if req.map_name:
            parsed["map_name"] = req.map_name
        if req.economy_a:
            parsed["economy_a"] = req.economy_a
        if req.economy_b:
            parsed["economy_b"] = req.economy_b

        cs2_analysis = estimate_cs2_win_probability(parsed, use_web=req.use_web)
        mood, expression = select_mood_for_context("youtube_cs2", cs2_analysis)
        comment, source = await generate_vtuber_commentary(
            vtuber_name=str(self.state.get("vtuber_name", "Mina AI")),
            context="youtube_cs2",
            window_title=req.title or f"{cs2_analysis['team_a']} vs {cs2_analysis['team_b']}",
            ocr_text=req.ocr_text,
            cs2_analysis=cs2_analysis,
            ollama_chat_fn=ollama_chat_fn,
        )
        self._update(
            context="youtube_cs2",
            mood=mood,
            expression=expression,
            comment=comment,
            comment_source=source,
            cs2_analysis=cs2_analysis,
        )
        return {
            "ok": True,
            "mood": mood,
            "expression": expression,
            "comment": comment,
            "comment_source": source,
            "analysis": cs2_analysis,
        }


COMPANION_MANAGER = VTuberCompanionManager()


def register_routes(app: FastAPI) -> None:
    @app.post("/api/vtuber/companion/start")
    async def api_companion_start(req: CompanionStartRequest | None = None) -> dict[str, Any]:
        return await COMPANION_MANAGER.start(req or CompanionStartRequest())

    @app.post("/api/vtuber/companion/stop")
    async def api_companion_stop() -> dict[str, Any]:
        return await COMPANION_MANAGER.stop()

    @app.post("/api/vtuber/companion/tick")
    async def api_companion_tick(req: CompanionTickRequest | None = None) -> dict[str, Any]:
        body = req or CompanionTickRequest()
        return await COMPANION_MANAGER.tick(force=body.force, use_web=body.use_web)

    @app.get("/api/vtuber/companion/status")
    async def api_companion_status() -> dict[str, Any]:
        return COMPANION_MANAGER.snapshot_state()

    @app.post("/api/vtuber/companion/analyze-cs2")
    async def api_companion_analyze_cs2(req: CS2AnalyzeRequest) -> dict[str, Any]:
        return await COMPANION_MANAGER.analyze_cs2(req)
