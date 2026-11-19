from __future__ import annotations

import asyncio
import base64
import io
import itertools
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image, ImageChops
from pydantic import BaseModel, Field

from browser import (
    ALLOWED_BROWSER_KEYS,
    _cdp_ready as browser_cdp_ready,
    _snapshot as browser_snapshot,
    _with_context as browser_with_context,
    browser_capture_screenshot_b64,
    browser_game_step_exec,
)
from computer import (
    ALLOWED_KEYS,
    SCREEN_DIR,
    active_window,
    capture_window,
    focus_window,
    is_f12_pressed,
    perform_scoped_input,
    window_info,
)
from computer_use import BLOCKED_TERMS
from game_playbooks import (
    WORLD_NAMES,
    advise_czn_action,
    build_step_guidance,
    configure_learned_store,
    detect_czn_phase,
    extract_visible_czn_scout_note,
    get_czn_knowledge_summary,
    inject_czn_icon_hints,
    learn_czn_from_web,
    list_playbooks,
    match_known_kits,
)
from ocr_helper import annotate_button_colors, extract_ocr_labels

BLOCKED_PROCESSES = {
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "windowsterminal.exe",
    "openconsole.exe",
    "regedit.exe",
    "taskmgr.exe",
    "mmc.exe",
    "control.exe",
    "keepass.exe",
    "keepassxc.exe",
    "1password.exe",
    "bitwarden.exe",
}
VALID_ACTIONS = {
    "click_xy",
    "double_click_xy",
    "right_click_xy",
    "drag_xy",
    "key_press",
    "scroll",
    "type_text",
    "wait",
    "stop",
}
VALID_MOODS = {"happy", "thinking", "excited", "surprised", "panic"}


class GameSessionStartRequest(BaseModel):
    source: str = Field(default="desktop", pattern="^(desktop|browser)$")
    target_handle: int | None = None
    goal: str = Field(default="", max_length=1000)
    controls_hint: str = Field(default="", max_length=600)
    playbook: str = Field(default="none", pattern="^(none|czn|hsr)$")
    playbook_config: dict[str, Any] = Field(default_factory=dict)
    vtuber_name: str = Field(default="Mina AI", max_length=60)
    vtuber_enabled: bool = True
    mode: str = Field(default="auto_play", pattern="^(auto_play|step_confirm|copilot)$")
    interval_ms: int = Field(default=350, ge=150, le=8000)
    max_steps: int = Field(default=0, ge=0, le=10000)


def _blocked(*values: str) -> str | None:
    joined = " ".join(v for v in values if v)
    m = BLOCKED_TERMS.search(joined)
    return m.group(0) if m else None


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("Model không trả về JSON hợp lệ.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("JSON root không phải object.")
    return parsed


def _clamp_norm(val: Any, default: int = 500) -> int:
    try:
        return max(0, min(1000, int(round(float(val)))))
    except (TypeError, ValueError):
        return default


def _image_change_metrics(before_bytes: bytes, after_bytes: bytes) -> tuple[float, float]:
    """Return (mean_rgb_diff 0..255, changed_pixel_pct 0..100) to catch both scene transitions and small button state changes."""
    if not before_bytes or not after_bytes:
        return 0.0, 0.0
    try:
        im_a = Image.open(io.BytesIO(before_bytes)).convert("RGB").resize((96, 54), Image.Resampling.BILINEAR)
        im_b = Image.open(io.BytesIO(after_bytes)).convert("RGB").resize((96, 54), Image.Resampling.BILINEAR)
        diff = ImageChops.difference(im_a, im_b)
        raw = diff.tobytes()
        n_bytes = max(1, len(raw))
        mean_diff = sum(raw) / n_bytes
        pixels = n_bytes // 3
        changed = sum(1 for i in range(0, pixels * 3, 3) if (raw[i] + raw[i + 1] + raw[i + 2]) >= 36)
        changed_pct = (changed * 100.0) / max(1, pixels)
        return mean_diff, changed_pct
    except Exception:
        return 0.0, 0.0


def _mean_image_diff(before_bytes: bytes, after_bytes: bytes) -> float:
    """Compute mean RGB pixel change (0..255) on downscaled thumbnails to detect visual reaction."""
    mean_diff, _ = _image_change_metrics(before_bytes, after_bytes)
    return mean_diff


class GameSessionManager:
    """Manage a single window-locked interactive game / AI VTuber session."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._task: asyncio.Task | None = None
        self._stop_flag = False
        self._pause_flag = False
        self._preview_path = SCREEN_DIR / "game_preview.jpg"
        self._scouted_notes: list[str] = []
        self._czn_state: dict[str, Any] = {}
        self._had_visual_change = False
        self.state: dict[str, Any] = {
            "active": False,
            "status": "idle",
            "session_id": "",
            "source": "desktop",
            "target_handle": None,
            "target_pid": None,
            "target_title": "",
            "goal": "",
            "playbook": "none",
            "playbook_phase": "",
            "scouted_notes": [],
            "mode": "auto_play",
            "vtuber_name": "Mina AI",
            "vtuber_enabled": True,
            "mood": "happy",
            "comment": "Sẵn sàng chơi game cùng Master!",
            "step": 0,
            "max_steps": 25,
            "last_action": None,
            "pending_action": None,
            "last_latency_ms": 0,
            "history": [],
            "error": "",
            "updated_at": time.time(),
        }

    def snapshot_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self.state,
                "history": list(self.state.get("history", []))[-12:],
                "has_preview": self._preview_path.is_file(),
            }

    def _update(self, **kwargs: Any) -> None:
        with self._lock:
            self.state.update(kwargs)
            self.state["updated_at"] = time.time()

    def _validate_desktop_target(self, handle: int | None) -> dict[str, Any]:
        if handle is None:
            raise HTTPException(400, "Cần chọn một cửa sổ game cụ thể (target_handle).")
        info = window_info(handle)
        if not info.get("found") or not info.get("visible"):
            raise HTTPException(409, "Cửa sổ mục tiêu không tồn tại hoặc đã ẩn.")
        if info.get("minimized"):
            raise HTTPException(409, "Cửa sổ mục tiêu đang bị thu nhỏ; hãy mở lên trước.")
        if int(info.get("process_id", -1)) == os.getpid():
            raise HTTPException(403, "Không cho phép tự điều khiển cửa sổ tiến trình AI Office.")
        proc = str(info.get("process_name", "")).lower()
        title = str(info.get("title", ""))
        if proc in BLOCKED_PROCESSES or title == "AI Office":
            raise HTTPException(403, f"Cửa sổ '{title}' ({proc}) bị chặn vì an toàn.")
        hit = _blocked(title, proc)
        if hit:
            raise HTTPException(403, f"Tiêu đề cửa sổ chứa từ nhạy cảm ({hit}); từ chối điều khiển.")
        return info

    def _validate_plan(self, plan: dict[str, Any], source: str) -> dict[str, Any]:
        action = str(plan.get("action", "wait")).strip().lower()
        if action not in VALID_ACTIONS:
            action = "wait"
        mood = str(plan.get("mood", "thinking")).strip().lower()
        if mood not in VALID_MOODS:
            mood = "thinking"
        comment = str(plan.get("comment", "") or "").strip()[:260]
        reason = str(plan.get("reason", "") or "").strip()[:300]
        x = _clamp_norm(plan.get("x", 500))
        y = _clamp_norm(plan.get("y", 500))
        x2 = _clamp_norm(plan.get("x2", x))
        y2 = _clamp_norm(plan.get("y2", y))
        key = str(plan.get("key", "") or "").strip().lower()
        direction = str(plan.get("direction", "down") or "down").strip().lower()
        if direction not in {"up", "down"}:
            direction = "down"
        try:
            amount = max(1, min(6, int(plan.get("amount", 2))))
        except (TypeError, ValueError):
            amount = 2
        try:
            duration_ms = max(40, min(400, int(plan.get("duration_ms", 80))))
        except (TypeError, ValueError):
            duration_ms = 80
        text = str(plan.get("text", "") or "")[:120]

        if action == "key_press":
            allowed_map = ALLOWED_BROWSER_KEYS if source == "browser" else ALLOWED_KEYS
            if key not in allowed_map:
                raise ValueError(f"Phím không nằm trong danh sách an toàn: {key!r}")
        if action == "type_text" and (not text or _blocked(text)):
            raise ValueError("Nội dung nhập bị trống hoặc nhạy cảm.")
        if _blocked(reason, comment):
            raise ValueError("Hành động chứa từ nhạy cảm bị chặn.")
        if source == "browser" and action in {"right_click_xy", "drag_xy"}:
            action = "click_xy"

        return {
            "mood": mood,
            "comment": comment or "Đang quan sát màn hình game...",
            "action": action,
            "x": x,
            "y": y,
            "x2": x2,
            "y2": y2,
            "key": key,
            "duration_ms": duration_ms,
            "direction": direction,
            "amount": amount,
            "text": text,
            "reason": reason,
            "fast_combat": bool(plan.get("fast_combat", False)),
        }

    def _guard_vlm_action(
        self,
        act: dict[str, Any],
        req: GameSessionStartRequest,
        phase_name: str,
        ocr_items: list[dict[str, Any]],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Prevent VLM from clicking gray disabled buttons, Promotions/Delegate traps, or repeating failed clicks."""
        if req.source != "desktop" or act["action"] not in {"click_xy", "double_click_xy"}:
            return act
        ax, ay = int(act["x"]), int(act["y"])
        # 1. Block clicks landing on [XÁM] disabled OCR buttons
        gray_hit = next(
            (
                it for it in ocr_items
                if it.get("state") == "XÁM" and abs(ax - int(it["x"])) <= 65 and abs(ay - int(it["y"])) <= 35
            ),
            None,
        )
        if gray_hit is not None:
            txt = str(gray_hit.get("text", "")).lower()
            if req.playbook == "czn" and phase_name in {"card_reward", "equipment"} and "confirm" in txt:
                slot_ys = (380, 540, 700)
                idx = sum(1 for h in history[-4:] if "chọn nhân vật" in str(h.get("reason", "")).lower()) % len(slot_ys)
                return {**act, "x": 820, "y": slot_ys[idx], "x2": 820, "y2": slot_ys[idx], "comment": "Confirm đang màu xám, chọn nhân vật bên phải trước nhé!", "reason": "Guardrail: chọn nhân vật để Confirm chuyển CAM"}
            if req.playbook == "czn" and phase_name == "world_select" and "enter" in txt:
                wname = WORLD_NAMES.get(str(req.playbook_config.get("world", "blue_pot")), "The Blue Pot").lower()
                planet = next((it for it in ocr_items if wname in str(it.get("text", "")).lower() and int(it["x"]) < 700), None)
                if planet:
                    return {**act, "x": planet["x"], "y": planet["y"], "x2": planet["x"], "y2": planet["y"], "comment": f"Nút Enter đang xám, bấm chọn {planet['text']} trước!", "reason": "Guardrail: click planet before Enter[XÁM]"}
            if req.playbook == "czn" and phase_name == "combatant_list" and "assign" in txt:
                det = next((it for it in ocr_items if "details" in str(it.get("text", "")).lower() and it.get("state") != "XÁM"), None)
                if det:
                    return {**act, "x": det["x"], "y": det["y"], "x2": det["x"], "y2": det["y"], "comment": "Nút Assign đang xám, bấm Details hoặc Back nhé!", "reason": "Guardrail: avoid Assign[XÁM], click Details"}
                return {**act, "x": 44, "y": 44, "x2": 44, "y2": 44, "comment": "Nút Assign đang xám, bấm Back quay lại nhé!", "reason": "Guardrail: avoid Assign[XÁM] -> Back"}
            if req.playbook == "czn":
                return {**act, "x": 500, "y": 480, "x2": 500, "y2": 480, "comment": "Nút này đang màu xám chưa chọn được, bấm chọn mục giữa màn hình trước!", "reason": f"Guardrail: blocked disabled {gray_hit['text']}[XÁM]"}

        # 2. Block wrong-trap clicks in CZN (Promotions during scouting, Delegate during manual run)
        if req.playbook == "czn" and phase_name == "character_details":
            promo = next((it for it in ocr_items if "promotions" in str(it.get("text", "")).lower()), None)
            if promo and abs(ax - int(promo["x"])) <= 95 and abs(ay - int(promo["y"])) <= 45:
                return {**act, "x": 44, "y": 44, "x2": 44, "y2": 44, "comment": "Xem xong thông tin nhân vật rồi, bấm Back quay ra nhé!", "reason": "Guardrail: skip Promotions -> Back ◁"}
        if req.playbook == "czn" and phase_name == "team_formation" and "delegate" not in req.goal.lower():
            dlg = next((it for it in ocr_items if "delegate" in str(it.get("text", "")).lower()), None)
            enter = next((it for it in ocr_items if "enter" in str(it.get("text", "")).lower() and it.get("state") != "XÁM"), None)
            if dlg and abs(ax - int(dlg["x"])) <= 70 and abs(ay - int(dlg["y"])) <= 40 and enter:
                return {**act, "x": enter["x"], "y": enter["y"], "x2": enter["x"], "y2": enter["y"], "comment": "Đi tay không bấm Delegate, bấm Enter vào trận nhé!", "reason": "Guardrail: avoid Delegate -> Enter"}

        # 3. Break repeated identical dead clicks before triggering 3-step error abort
        if req.playbook == "czn" and len(history) >= 2:
            h1, h2 = history[-1], history[-2]
            if (
                not h1.get("screen_changed")
                and not h2.get("screen_changed")
                and abs(ax - int(h1.get("x", -999))) <= 22
                and abs(ay - int(h1.get("y", -999))) <= 22
                and abs(ax - int(h2.get("x", -999))) <= 22
                and abs(ay - int(h2.get("y", -999))) <= 22
            ):
                if phase_name == "fate_choice":
                    cfm = next((it for it in ocr_items if "confirm" in str(it.get("text", "")).lower() and it.get("state") != "XÁM"), None)
                    if cfm:
                        return {**act, "x": cfm["x"], "y": cfm["y"], "x2": cfm["x"], "y2": cfm["y"], "comment": "Không bỏ qua được Fate này, bấm Confirm để đi tiếp!", "reason": "Guardrail: break fate skip stall -> Confirm"}
                if phase_name != "combat":
                    return {**act, "x": 44, "y": 44, "x2": 44, "y2": 44, "comment": "Thao tác vừa rồi không đổi màn hình, thử bấm Back thoát kẹt!", "reason": "Guardrail: break 2-step stall -> Back ◁"}
        return act

    async def _observe_and_decide(
        self,
        m: Any,
        req: GameSessionStartRequest,
        target_info: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], int]:
        t0 = time.perf_counter()
        extra_dom = ""
        if req.source == "browser":
            def grab_browser(ctx):
                snap = browser_snapshot(ctx, with_image=True)
                return snap
            snap = await asyncio.to_thread(browser_with_context, grab_browser)
            img_b64 = snap.get("image", "")
            if not img_b64:
                img_b64 = await asyncio.to_thread(browser_capture_screenshot_b64)
            if img_b64:
                self._preview_path.write_bytes(base64.b64decode(img_b64))
            controls_brief = [
                {"text": c.get("text", "")[:50], "tag": c.get("tag"), "x": c.get("x"), "y": c.get("y")}
                for c in snap.get("controls", [])[:25]
            ]
            extra_dom = (
                f"Page title: {snap.get('title','')}\n"
                f"Visible text: {str(snap.get('text',''))[:600]}\n"
                f"Clickable elements (x,y in 0..1000): {json.dumps(controls_brief, ensure_ascii=False)[:1400]}\n"
            )
        else:
            if req.mode != "copilot":
                fg_now = await asyncio.to_thread(active_window)
                if not fg_now.get("found") or int(fg_now.get("handle", -1)) != int(target_info["handle"]):
                    await asyncio.to_thread(focus_window, target_info["handle"])
                    await asyncio.sleep(0.08)
            shot = await asyncio.to_thread(
                capture_window,
                target_info["handle"],
                max_width=800,
                quality=72,
                draw_grid=True,
                filename="game_preview.jpg",
            )
            img_b64 = base64.b64encode(Path(shot["ai_path"]).read_bytes()).decode("ascii")

        ocr_items: list[dict[str, Any]] = []
        corner_state = ""
        ocr_hint = ""
        if req.source == "desktop":
            try:
                ocr_res = await asyncio.to_thread(extract_ocr_labels, shot["path"], max_items=26)
                ocr_items = ocr_res.get("items", []) or []
                ocr_items, corner_state = await asyncio.to_thread(annotate_button_colors, shot["path"], ocr_items)
            except Exception:
                ocr_items = []
                corner_state = ""
            if req.playbook == "czn":
                czn_phase_now = detect_czn_phase([str(it.get("text", "")) for it in ocr_items])
                ocr_items = inject_czn_icon_hints(czn_phase_now, ocr_items)
                real_note = extract_visible_czn_scout_note(czn_phase_now, ocr_items)
                if real_note and real_note not in self._scouted_notes:
                    self._scouted_notes = (self._scouted_notes + [real_note])[-8:]
            if ocr_items:
                ocr_hint = (
                    "Detected UI labels (0..1000): "
                    + ", ".join(
                        f"{it['text']!r}@({it['x']},{it['y']})" + (f"[{it['state']}]" if it.get("state") else "")
                        for it in ocr_items[:24]
                    )
                    + "\n"
                )
                for kit in match_known_kits([it["text"] for it in ocr_items]):
                    if kit not in self._scouted_notes:
                        self._scouted_notes = (self._scouted_notes + [kit])[-8:]

        phase_name, playbook_guidance = build_step_guidance(
            req.playbook, req.playbook_config, ocr_items, self._scouted_notes, history, corner_state=corner_state
        )
        self._update(playbook_phase=phase_name, scouted_notes=list(self._scouted_notes))

        if req.playbook == "czn" and req.source == "desktop":
            fast_plan = advise_czn_action(req.playbook_config, ocr_items, corner_state, self._czn_state, history)
            if fast_plan is not None:
                if len(history) >= 2 and not history[-1].get("screen_changed") and not history[-2].get("screen_changed"):
                    same_act = fast_plan.get("action") == history[-1].get("action")
                    if fast_plan.get("action") == "key_press":
                        is_same_stall = same_act and str(fast_plan.get("key", "")) == str(history[-1].get("key", ""))
                    else:
                        is_same_stall = (
                            same_act
                            and abs(int(fast_plan["x"]) - int(history[-1].get("x", -999))) <= 18
                            and abs(int(fast_plan["y"]) - int(history[-1].get("y", -999))) <= 18
                        )
                else:
                    is_same_stall = False
                if not is_same_stall:
                    validated = self._validate_plan(fast_plan, req.source)
                    return validated, round((time.perf_counter() - t0) * 1000)

        recent_hist = [
            {
                "s": h.get("step"),
                "a": h.get("action"),
                "pos": f"({h.get('x')},{h.get('y')})" if "click" in str(h.get("action")) or "drag" in str(h.get("action")) else h.get("key", ""),
                "note": str(h.get("comment", ""))[:45],
            }
            for h in history[-3:]
        ]

        stuck_warning = ""
        if req.mode != "copilot" and len(history) >= 2:
            a1, a2 = history[-1], history[-2]
            if a1.get("action") == a2.get("action") and "click" in str(a1.get("action")):
                if abs(int(a1.get("x", 0)) - int(a2.get("x", 0))) <= 18 and abs(int(a1.get("y", 0)) - int(a2.get("y", 0))) <= 18:
                    stuck_warning = (
                        "STUCK WARNING: Last 2 clicks hit same spot. Try drag_xy from card up to enemy/center (x2,y2~420), or click Enter/Confirm/End Turn.\n"
                    )

        persona = (
            f"You are {req.vtuber_name}, a lively Vietnamese AI VTuber playing a game."
            if req.vtuber_enabled
            else "You are an AI game controller."
        )
        copilot_note = " MODE: CO-PILOT (suggest next move, do not claim you clicked it)." if req.mode == "copilot" else ""
        system = (
            f"{persona}{copilot_note} Screenshot uses 0..1000 coordinates (x=0 left..1000 right, y=0 top..1000 bottom). "
            "Return ONLY ONE compact JSON object: "
            '{"mood":"happy|thinking|excited|surprised|panic","comment":"1 short Vietnamese sentence","action":"click_xy|double_click_xy|right_click_xy|drag_xy|key_press|scroll|type_text|wait|stop","x":0,"y":0,"x2":0,"y2":0,"key":"","duration_ms":80,"direction":"down","amount":2,"text":"","reason":"short","note":"optional skill summary"}. '
            "Use exact 'Detected UI labels' coordinates when clicking labeled buttons; never click [XÁM] disabled buttons; use [ĐEN]/[CAM]/[TÍM] active buttons or edge grid labels for cards/icons. Never invent results before seeing the next frame. Set action='stop' only when goal is completed."
        )
        prompt = (
            (f"Goal: {req.goal}\n" if req.goal else "")
            + (f"Guide ({phase_name}): {playbook_guidance}\n" if playbook_guidance else "")
            + (f"Scouted notes: {' | '.join(self._scouted_notes[-3:])}\n" if self._scouted_notes else "")
            + (f"Controls hint: {req.controls_hint}\n" if req.controls_hint else "")
            + f"Window: {target_info.get('title', 'Browser')}\n"
            + ocr_hint
            + extra_dom
            + stuck_warning
            + f"Recent: {json.dumps(recent_hist, ensure_ascii=False)}"
        )
        user_msg: dict[str, Any] = {"role": "user", "content": prompt}
        if img_b64:
            user_msg["images"] = [img_b64]
        raw = await m.ollama_chat(
            [{"role": "system", "content": system}, user_msg],
            json_mode=True,
            num_predict=180,
            num_ctx=4096,
            temperature=0.15,
        )
        parsed = _extract_json(raw)
        note_text = str(parsed.get("note", "") or "").strip()[:180]
        if note_text and note_text not in self._scouted_notes:
            self._scouted_notes = (self._scouted_notes + [note_text])[-8:]
            self._update(scouted_notes=list(self._scouted_notes))
        validated = self._validate_plan(parsed, req.source)
        validated = self._guard_vlm_action(validated, req, phase_name, ocr_items, history)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        return validated, latency_ms

    async def _execute_action(
        self,
        req: GameSessionStartRequest,
        target_info: dict[str, Any],
        act: dict[str, Any],
    ) -> dict[str, Any]:
        action = act["action"]
        if action == "stop":
            return {"ok": True, "action": "stop"}
        if req.source == "browser":
            return await asyncio.to_thread(
                browser_game_step_exec,
                action,
                x=act["x"],
                y=act["y"],
                key=act["key"],
                direction=act["direction"],
                amount=act["amount"],
                text=act["text"],
            )
        # Revalidate desktop target window before every input
        live = await asyncio.to_thread(window_info, target_info["handle"])
        if not live.get("found") or not live.get("visible") or live.get("minimized"):
            raise RuntimeError("Cửa sổ game đã đóng hoặc bị thu nhỏ; dừng phiên.")
        if int(live.get("process_id", -1)) != int(target_info["process_id"]):
            raise RuntimeError("Tiến trình cửa sổ mục tiêu đã thay đổi; dừng phiên.")
        if _blocked(live.get("title", "")):
            raise RuntimeError("Tiêu đề cửa sổ chuyển sang nội dung nhạy cảm; dừng phiên.")
        return await asyncio.to_thread(
            perform_scoped_input,
            target_info["handle"],
            action,
            expected_pid=target_info["process_id"],
            x=act["x"],
            y=act["y"],
            x2=act["x2"],
            y2=act["y2"],
            key=act["key"],
            duration_ms=act["duration_ms"],
            direction=act["direction"],
            amount=act["amount"],
            text=act["text"],
        )

    async def _run_loop(self, m: Any, req: GameSessionStartRequest, target_info: dict[str, Any], session_id: str) -> None:
        history: list[dict[str, Any]] = []
        try:
            for step_num in itertools.count(1):
                if req.max_steps > 0 and step_num > req.max_steps:
                    break
                if self._stop_flag or is_f12_pressed():
                    reason = "Đã dừng khẩn cấp bằng phím F12." if is_f12_pressed() else "Master đã dừng phiên chơi."
                    self._update(active=False, status="stopped", comment=reason, pending_action=None)
                    return

                while self._pause_flag and not self._stop_flag:
                    self._update(status="paused")
                    await asyncio.sleep(0.2)
                    if is_f12_pressed():
                        self._update(active=False, status="stopped", comment="Đã dừng khẩn cấp bằng phím F12.", pending_action=None)
                        return
                if self._stop_flag:
                    self._update(active=False, status="stopped", comment="Master đã dừng phiên chơi.", pending_action=None)
                    return

                self._update(status="observing", step=step_num)
                act, latency_ms = await self._observe_and_decide(m, req, target_info, history)

                if self._stop_flag or is_f12_pressed():
                    self._update(active=False, status="stopped", comment="Đã dừng phiên chơi.", pending_action=None)
                    return

                if act["action"] == "stop":
                    self._update(
                        active=False,
                        status="completed",
                        mood=act["mood"],
                        comment=act["comment"],
                        last_action=act,
                        last_latency_ms=latency_ms,
                        pending_action=None,
                    )
                    return

                if req.mode == "step_confirm":
                    self._update(
                        status="awaiting_approval",
                        mood=act["mood"],
                        comment=act["comment"],
                        pending_action=act,
                        last_latency_ms=latency_ms,
                    )
                    while not self._stop_flag:
                        with self._lock:
                            pending = self.state.get("pending_action")
                        if pending is None:
                            break
                        if is_f12_pressed():
                            self._update(active=False, status="stopped", comment="Đã dừng khẩn cấp bằng phím F12.", pending_action=None)
                            return
                        await asyncio.sleep(0.15)
                    if self._stop_flag:
                        return
                    # Pending was either approved (executed) or skipped; record and continue
                    with self._lock:
                        history = list(self.state.get("history", []))
                    continue

                if req.mode == "copilot":
                    entry = {
                        "step": step_num,
                        "action": act["action"],
                        "x": act["x"],
                        "y": act["y"],
                        "x2": act["x2"],
                        "y2": act["y2"],
                        "key": act["key"],
                        "mood": act["mood"],
                        "comment": act["comment"],
                        "reason": act["reason"],
                        "latency_ms": latency_ms,
                        "copilot": True,
                        "executed": False,
                        "ok": True,
                    }
                    history.append(entry)
                    self._update(
                        status="observing",
                        mood=act["mood"],
                        comment=act["comment"],
                        last_action=entry,
                        last_latency_ms=latency_ms,
                        history=history[-12:],
                    )
                    await asyncio.sleep(req.interval_ms / 1000.0)
                    continue

                self._update(status="acting", mood=act["mood"], comment=act["comment"], last_latency_ms=latency_ms)
                before_bytes = self._preview_path.read_bytes() if self._preview_path.is_file() else b""
                exec_res = await self._execute_action(req, target_info, act)

                async def grab_after() -> bytes:
                    if req.source == "desktop":
                        try:
                            await asyncio.to_thread(
                                capture_window,
                                target_info["handle"],
                                max_width=960,
                                quality=72,
                                draw_grid=False,
                                filename="game_preview.jpg",
                            )
                        except Exception:
                            return b""
                    else:
                        try:
                            b64 = await asyncio.to_thread(browser_capture_screenshot_b64)
                            if b64:
                                self._preview_path.write_bytes(base64.b64decode(b64))
                        except Exception:
                            return b""
                    return self._preview_path.read_bytes() if self._preview_path.is_file() else b""

                is_fast_combat = bool(act.get("fast_combat")) or self.state.get("playbook_phase") == "combat"
                if req.source == "desktop" and req.playbook == "czn":
                    first_wait = 0.15 if is_fast_combat else 0.45
                    retry_wait = (0.45 if "end turn" in act["reason"].lower() else 0.22) if is_fast_combat else 0.55
                else:
                    first_wait = 0.35
                    retry_wait = 0.60

                await asyncio.sleep(first_wait)
                after_bytes = await grab_after()
                visual_diff, changed_pct = _image_change_metrics(before_bytes, after_bytes)
                screen_changed = (visual_diff >= 0.45) or (changed_pct >= 0.8)
                # Give full-screen games extra time to finish fade/scene transition before judging unreactive.
                if req.source == "desktop" and act["action"] != "wait" and not screen_changed:
                    await asyncio.sleep(retry_wait)
                    after_bytes = await grab_after()
                    visual_diff, changed_pct = _image_change_metrics(before_bytes, after_bytes)
                    screen_changed = (visual_diff >= 0.45) or (changed_pct >= 0.8)

                entry = {
                    "step": step_num,
                    "action": act["action"],
                    "x": act["x"],
                    "y": act["y"],
                    "x2": act["x2"],
                    "y2": act["y2"],
                    "key": act["key"],
                    "mood": act["mood"],
                    "comment": act["comment"] + ("" if screen_changed or act["action"] == "wait" else " (màn hình chưa đổi)"),
                    "reason": act["reason"],
                    "latency_ms": latency_ms,
                    "screen_changed": screen_changed,
                    "visual_diff": round(visual_diff, 2),
                    "changed_pct": round(changed_pct, 2),
                    "ok": bool(exec_res.get("ok")) and (screen_changed or act["action"] == "wait"),
                }
                history.append(entry)
                if screen_changed:
                    self._had_visual_change = True
                if len(history) > 48:
                    history = history[-24:]
                self._update(last_action=entry, history=history[-12:])

                # Fail honestly ONLY if the session has never had a single visual reaction (true UIPI/anti-cheat block).
                if req.source == "desktop" and len(history) >= 3:
                    recent_interactive = [h for h in history[-3:] if h.get("action") in {"click_xy", "double_click_xy", "right_click_xy", "drag_xy", "key_press"}]
                    if len(recent_interactive) == 3 and all(not h.get("screen_changed") for h in recent_interactive):
                        if not self._had_visual_change:
                            msg = (
                                f"Đã thử 3 thao tác liên tiếp lên '{target_info.get('title')}' nhưng màn hình hoàn toàn không thay đổi (diff={visual_diff:.2f}, changed={changed_pct:.1f}%). "
                                "Game có thể đang có shield/anti-cheat chặn chuột/phím giả lập — dừng để không báo sai. "
                                "Hãy thử chuyển Chế độ sang 'VTuber Co-pilot (quan sát & gợi ý)' hoặc kiểm tra cửa sổ không bị che."
                            )
                            self._update(active=False, status="error", mood="surprised", error=msg, comment=msg, pending_action=None)
                            return
                        # Later in an active session: clear probe cache and pause briefly so transient animations/popups recover cleanly.
                        self._czn_state["combat_probes"] = 0
                        await asyncio.sleep(0.45)

                if req.source == "desktop" and req.playbook == "czn":
                    if is_fast_combat:
                        inter_sleep = 0.18 if act["action"] == "wait" else (min(req.interval_ms, 120) / 1000.0)
                    else:
                        inter_sleep = max(0.55, (req.interval_ms / 1000.0) if screen_changed else 0.70)
                    await asyncio.sleep(inter_sleep)
                else:
                    await asyncio.sleep(req.interval_ms / 1000.0)

            self._update(active=False, status="completed", comment="Đã hoàn thành số bước tối đa trong phiên chơi.")
        except Exception as exc:
            self._update(active=False, status="error", mood="surprised", error=str(exc)[:300], comment=f"Tạm dừng vì lỗi: {str(exc)[:140]}", pending_action=None)

    async def start(self, m: Any, req: GameSessionStartRequest) -> dict[str, Any]:
        if len(req.goal.strip()) < 4 and req.playbook == "none":
            raise HTTPException(400, "Cần nhập mục tiêu chơi (ít nhất 4 ký tự) hoặc chọn Kịch bản game.")
        ready, reason_offline = await m.model_runtime_ready()
        if not ready:
            raise HTTPException(503, reason_offline or "Model chưa sẵn sàng.")
        hit = _blocked(req.goal, req.controls_hint)
        if hit:
            raise HTTPException(403, f"Mục tiêu chứa từ nhạy cảm ({hit}) bị chặn.")

        if req.source == "browser":
            if not await asyncio.to_thread(browser_cdp_ready):
                raise HTTPException(409, "Hãy mở Browser riêng và vào trang game trước.")
            target_info = {"handle": 0, "process_id": 0, "title": "Isolated Browser"}
        else:
            target_info = await asyncio.to_thread(self._validate_desktop_target, req.target_handle)
            # Capture initial preview cleanly
            try:
                await asyncio.to_thread(capture_window, target_info["handle"], max_width=800, quality=72, draw_grid=False, filename="game_preview.jpg")
            except Exception as exc:
                raise HTTPException(409, f"Không chụp được cửa sổ game: {str(exc)[:220]}")

        await self.stop()
        session_id = uuid.uuid4().hex[:10]
        self._stop_flag = False
        self._pause_flag = False
        self._scouted_notes = []
        self._czn_state = {}
        self._had_visual_change = False
        self._update(
            active=True,
            status="starting",
            session_id=session_id,
            source=req.source,
            target_handle=target_info["handle"],
            target_pid=target_info["process_id"],
            target_title=target_info["title"],
            goal=req.goal,
            playbook=req.playbook,
            playbook_phase="",
            scouted_notes=[],
            mode=req.mode,
            vtuber_name=req.vtuber_name,
            vtuber_enabled=req.vtuber_enabled,
            mood="excited",
            comment=(
                f"{req.vtuber_name} đang quan sát '{target_info['title']}' ở chế độ Co-pilot (chỉ gợi ý nước đi, không tự bấm)!"
                if req.mode == "copilot"
                else f"{req.vtuber_name} đã khóa cửa sổ '{target_info['title']}' — bắt đầu chơi nhé!"
            ),
            step=0,
            max_steps=req.max_steps,
            last_action=None,
            pending_action=None,
            last_latency_ms=0,
            history=[],
            error="",
        )
        self._req = req
        self._target_info = target_info
        self._task = asyncio.create_task(self._run_loop(m, req, target_info, session_id))
        return self.snapshot_state()

    async def approve_pending(self) -> dict[str, Any]:
        with self._lock:
            pending = self.state.get("pending_action")
            if not self.state.get("active") or not pending:
                raise HTTPException(404, "Không có bước game nào đang chờ duyệt.")
            req = getattr(self, "_req", None)
            target_info = getattr(self, "_target_info", None)
            step_num = int(self.state.get("step", 1))
            latency_ms = int(self.state.get("last_latency_ms", 0))
            history = list(self.state.get("history", []))
        if req is None or target_info is None:
            raise HTTPException(409, "Phiên không hợp lệ.")
        exec_res = await self._execute_action(req, target_info, pending)
        entry = {
            "step": step_num,
            "action": pending["action"],
            "x": pending["x"],
            "y": pending["y"],
            "x2": pending["x2"],
            "y2": pending["y2"],
            "key": pending["key"],
            "mood": pending["mood"],
            "comment": pending["comment"],
            "reason": pending["reason"],
            "latency_ms": latency_ms,
            "ok": bool(exec_res.get("ok")),
        }
        history.append(entry)
        if req.source == "desktop":
            try:
                await asyncio.to_thread(capture_window, target_info["handle"], max_width=960, quality=70, draw_grid=False, filename="game_preview.jpg")
            except Exception:
                pass
        else:
            try:
                b64 = await asyncio.to_thread(browser_capture_screenshot_b64)
                if b64:
                    self._preview_path.write_bytes(base64.b64decode(b64))
            except Exception:
                pass
        self._update(last_action=entry, history=history[-12:], pending_action=None, status="running")
        return self.snapshot_state()

    async def stop(self) -> dict[str, Any]:
        self._stop_flag = True
        self._pause_flag = False
        task = self._task
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=1.5)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
        self._task = None
        if self.state.get("active"):
            self._update(active=False, status="stopped", pending_action=None, comment="Đã dừng phiên chơi.")
        return self.snapshot_state()

    def pause(self, paused: bool) -> dict[str, Any]:
        with self._lock:
            if not self.state.get("active"):
                raise HTTPException(409, "Chưa có phiên chơi nào đang chạy.")
            self._pause_flag = paused
            self.state["status"] = "paused" if paused else "running"
            self.state["updated_at"] = time.time()
        return self.snapshot_state()


GAME_MANAGER = GameSessionManager()


SANDBOX_GAME_HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>AI Office · Game Sandbox</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;background:#0e1624;color:#edf4fc;font:15px/1.5 "Segoe UI",Inter,sans-serif;display:flex;flex-direction:column;min-height:100vh;align-items:center;padding:24px}
  .wrap{width:min(860px,100%);display:flex;flex-direction:column;gap:16px}
  .bar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:14px 18px;background:#162336;border:1px solid #2b425e;border-radius:14px}
  .tabs{display:flex;gap:8px;flex-wrap:wrap}
  button{cursor:pointer;border:1px solid #35506e;background:#1c2e45;color:#e6f2ff;border-radius:10px;padding:10px 14px;font:inherit;font-weight:650}
  button:hover{border-color:#3ce0ed;background:#233b58}
  button.active{background:linear-gradient(120deg,#2fd6e3,#4f91f5);color:#061722;border-color:transparent}
  .arena{padding:22px;background:#142033;border:1px solid #2b425e;border-radius:16px;min-height:430px}
  .status{padding:12px 14px;background:#0e1827;border:1px solid #2a405a;border-radius:10px;margin-bottom:16px;font-weight:600;color:#8be9f0}
  .ttt-grid{display:grid;grid-template-columns:repeat(3,108px);gap:10px;margin:16px auto;width:max-content}
  .ttt-cell{width:108px;height:108px;font-size:38px;font-weight:800;display:grid;place-items:center;border-radius:12px}
  .duel-bars{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
  .fighter{padding:14px;background:#101b2b;border:1px solid #2b425e;border-radius:12px}
  .hp-track{height:14px;background:#1d2e44;border-radius:99px;overflow:hidden;margin-top:8px}
  .hp-fill{height:100%;background:linear-gradient(90deg,#3fe08b,#19b37d);transition:width .25s}
  .hp-fill.enemy{background:linear-gradient(90deg,#ff7474,#d93b50)}
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}
  .card{padding:16px;text-align:left;display:flex;flex-direction:column;gap:6px;min-height:126px;background:#1a2b42;border:2px solid #38587a}
  .card strong{font-size:16px;color:#73e6f0}.card small{color:#b7cbe0;font-weight:400}
  canvas{display:block;margin:12px auto;background:#0a111c;border:2px solid #355273;border-radius:10px}
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <div><strong>AI Office · Game Sandbox Offline</strong><br><small style="color:#97aec8">Dùng để thử Browser Agent hoặc Computer Use / AI VTuber ngay trên máy</small></div>
    <div class="tabs">
      <button type="button" class="active" data-tab="duel">Đấu Thẻ Bài (Turn-based)</button>
      <button type="button" data-tab="ttt">Cờ Caro 3×3</button>
      <button type="button" data-tab="snake">Rắn Săn Mồi (Phím)</button>
    </div>
  </div>
  <div class="arena" id="arena"></div>
</div>
<script>
let mode = 'duel';
document.querySelectorAll('[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => {
    mode = btn.dataset.tab;
    document.querySelectorAll('[data-tab]').forEach(x => x.classList.toggle('active', x === btn));
    if (snakeTimer) { clearInterval(snakeTimer); snakeTimer = null; }
    render();
  });
});

// 1. Mini Turn-based Card Duel
let duel = { hp: 30, maxHp: 30, shield: 0, energy: 3, enemyHp: 28, enemyMax: 28, intent: 6, turn: 1, msg: 'Lượt 1: Hãy chọn thẻ bài để đánh Slime!' };
function resetDuel() { duel = { hp: 30, maxHp: 30, shield: 0, energy: 3, enemyHp: 28, enemyMax: 28, intent: 6, turn: 1, msg: 'Ván mới! Chọn thẻ bài!' }; render(); }
function playCard(kind) {
  if (duel.hp <= 0 || duel.enemyHp <= 0 || duel.energy <= 0) return;
  duel.energy--;
  if (kind === 'strike') { duel.enemyHp = Math.max(0, duel.enemyHp - 7); duel.msg = 'Dùng Chém Mạnh (-7 HP địch)!'; }
  if (kind === 'guard') { duel.shield += 6; duel.msg = 'Dùng Khiên Thép (+6 Giáp)!'; }
  if (kind === 'heal') { duel.hp = Math.min(duel.maxHp, duel.hp + 5); duel.msg = 'Dùng Hồi Máu (+5 HP)!'; }
  if (duel.enemyHp <= 0) duel.msg = 'CHIẾN THẮNG ở lượt ' + duel.turn + '! Bấm Chơi lại.';
  render();
}
function endDuelTurn() {
  if (duel.hp <= 0 || duel.enemyHp <= 0) return;
  const dmg = Math.max(0, duel.intent - duel.shield);
  duel.hp = Math.max(0, duel.hp - dmg);
  duel.shield = 0;
  duel.turn++;
  duel.energy = 3;
  duel.intent = 5 + (duel.turn % 3) * 2;
  duel.msg = duel.hp <= 0 ? 'THẤT BẠI! Bấm Chơi lại.' : 'Quái đánh ' + dmg + ' sát thương. Lượt ' + duel.turn + ' bắt đầu (3 Energy).';
  render();
}

// 2. Tic-Tac-Toe 3x3
let board = Array(9).fill('');
let tttMsg = 'Lượt của bạn (X). Hãy chọn 1 ô trống!';
function checkWinner(b) {
  const lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  for (const [a,c,d] of lines) if (b[a] && b[a] === b[c] && b[a] === b[d]) return b[a];
  return b.every(Boolean) ? 'DRAW' : '';
}
function clickTTT(idx) {
  if (board[idx] || checkWinner(board)) return;
  board[idx] = 'X';
  let w = checkWinner(board);
  if (!w) {
    const empty = board.map((v,i)=>v===''?i:-1).filter(i=>i>=0);
    if (empty.length) {
      const pick = empty.includes(4) ? 4 : empty[Math.floor(Math.random()*empty.length)];
      board[pick] = 'O';
      w = checkWinner(board);
    }
  }
  tttMsg = w === 'X' ? 'BẠN THẮNG (X)!' : w === 'O' ? 'BOT THẮNG (O)!' : w === 'DRAW' ? 'HÒA!' : 'Lượt tiếp theo của bạn (X)';
  render();
}
function resetTTT() { board = Array(9).fill(''); tttMsg = 'Ván mới! Lượt của bạn (X).'; render(); }

// 3. Snake keyboard game
let snakeTimer = null, snake = [{x:7,y:7}], dir = {x:1,y:0}, food = {x:11,y:7}, score = 0, alive = true;
function startSnake() {
  if (snakeTimer) clearInterval(snakeTimer);
  snake = [{x:7,y:7}]; dir = {x:1,y:0}; food = {x:11,y:7}; score = 0; alive = true;
  snakeTimer = setInterval(() => {
    if (!alive || mode !== 'snake') return;
    const head = {x: snake[0].x + dir.x, y: snake[0].y + dir.y};
    if (head.x < 0 || head.y < 0 || head.x >= 16 || head.y >= 16 || snake.some(s => s.x === head.x && s.y === head.y)) {
      alive = false; drawSnake(); return;
    }
    snake.unshift(head);
    if (head.x === food.x && head.y === food.y) {
      score += 10;
      food = {x: Math.floor(Math.random()*16), y: Math.floor(Math.random()*16)};
    } else snake.pop();
    drawSnake();
  }, 260);
  drawSnake();
}
function drawSnake() {
  const c = document.getElementById('snake-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#0a111c'; ctx.fillRect(0, 0, 320, 320);
  ctx.fillStyle = '#ff6470'; ctx.fillRect(food.x*20+2, food.y*20+2, 16, 16);
  snake.forEach((s, i) => { ctx.fillStyle = i === 0 ? '#3fe5ef' : '#2ea9c7'; ctx.fillRect(s.x*20+1, s.y*20+1, 18, 18); });
  const lbl = document.getElementById('snake-status');
  if (lbl) lbl.textContent = alive ? 'Điểm: ' + score + ' · Dùng phím mũi tên hoặc W/A/S/D' : 'GAME OVER! Điểm: ' + score + ' · Bấm Chơi lại';
}
document.addEventListener('keydown', e => {
  if (mode !== 'snake') return;
  const k = e.key.toLowerCase();
  if ((k === 'arrowup' || k === 'w') && dir.y !== 1) dir = {x:0,y:-1};
  if ((k === 'arrowdown' || k === 's') && dir.y !== -1) dir = {x:0,y:1};
  if ((k === 'arrowleft' || k === 'a') && dir.x !== 1) dir = {x:-1,y:0};
  if ((k === 'arrowright' || k === 'd') && dir.x !== -1) dir = {x:1,y:0};
});

function render() {
  const host = document.getElementById('arena');
  if (mode === 'duel') {
    host.innerHTML =
      '<div class="status">' + duel.msg + '</div>' +
      '<div class="duel-bars">' +
        '<div class="fighter"><strong>Anh Hùng (Bạn)</strong><div>HP: ' + duel.hp + '/' + duel.maxHp + ' · Giáp: ' + duel.shield + ' · Energy: ' + duel.energy + '/3</div><div class="hp-track"><div class="hp-fill" style="width:' + Math.round(duel.hp*100/duel.maxHp) + '%"></div></div></div>' +
        '<div class="fighter"><strong>Slime Chúa</strong><div>HP: ' + duel.enemyHp + '/' + duel.enemyMax + ' · Sắp đánh: ' + duel.intent + ' DMG</div><div class="hp-track"><div class="hp-fill enemy" style="width:' + Math.round(duel.enemyHp*100/duel.enemyMax) + '%"></div></div></div>' +
      '</div>' +
      '<div class="cards">' +
        '<button type="button" class="card" onclick="playCard(\'strike\')"><strong>⚔ Chém Mạnh (1⚡)</strong><small>Gây 7 sát thương lên Slime Chúa</small></button>' +
        '<button type="button" class="card" onclick="playCard(\'guard\')"><strong>🛡 Khiên Thép (1⚡)</strong><small>Tăng 6 Giáp chặn đòn lượt này</small></button>' +
        '<button type="button" class="card" onclick="playCard(\'heal\')"><strong>💚 Hồi Máu (1⚡)</strong><small>Hồi 5 HP cho Anh Hùng</small></button>' +
      '</div>' +
      '<div style="display:flex;gap:10px"><button type="button" class="active" onclick="endDuelTurn()">Kết Thúc Lượt</button><button type="button" onclick="resetDuel()">Chơi Lại</button></div>';
  } else if (mode === 'ttt') {
    const names = ['A1','B1','C1','A2','B2','C2','A3','B3','C3'];
    host.innerHTML =
      '<div class="status">' + tttMsg + '</div>' +
      '<div class="ttt-grid">' + board.map((v, i) => '<button type="button" class="ttt-cell" aria-label="Ô ' + names[i] + '" onclick="clickTTT(' + i + ')">' + (v || names[i]) + '</button>').join('') + '</div>' +
      '<div style="text-align:center"><button type="button" onclick="resetTTT()">Chơi Lại</button></div>';
  } else {
    host.innerHTML =
      '<div class="status" id="snake-status">Điểm: 0 · Bấm Bắt đầu rồi dùng W/A/S/D hoặc Mũi tên</div>' +
      '<canvas id="snake-canvas" width="320" height="320"></canvas>' +
      '<div style="text-align:center"><button type="button" class="active" onclick="startSnake()">Bắt đầu / Chơi lại</button></div>';
    drawSnake();
  }
}
render();
</script>
</body>
</html>
"""


def register_routes(app: FastAPI) -> None:
    import main as m
    configure_learned_store(m.DATA)

    @app.get("/sandbox-game", response_class=HTMLResponse)
    async def sandbox_game() -> str:
        return SANDBOX_GAME_HTML

    @app.get("/api/game/playbooks")
    async def get_game_playbooks() -> dict[str, Any]:
        return {"playbooks": list_playbooks(), "czn_knowledge": get_czn_knowledge_summary()}

    @app.post("/api/game/playbooks/learn-web")
    async def learn_czn_web() -> dict[str, Any]:
        return await learn_czn_from_web(m.DATA)

    @app.get("/api/game/session")
    async def get_game_session() -> dict[str, Any]:
        return GAME_MANAGER.snapshot_state()

    @app.get("/api/game/screenshot")
    async def get_game_preview():
        path = GAME_MANAGER._preview_path
        if not path.is_file():
            raise HTTPException(404, "Chưa có ảnh xem trước phiên chơi game.")
        return FileResponse(path, media_type="image/jpeg", filename="game_preview.jpg")

    @app.post("/api/game/session/start")
    async def start_game_session(req: GameSessionStartRequest) -> dict[str, Any]:
        return await GAME_MANAGER.start(m, req)

    @app.post("/api/game/session/stop")
    async def stop_game_session() -> dict[str, Any]:
        return await GAME_MANAGER.stop()

    @app.post("/api/game/session/pause")
    async def pause_game_session(paused: bool = True) -> dict[str, Any]:
        return GAME_MANAGER.pause(paused)

    @app.post("/api/game/session/approve")
    async def approve_game_step() -> dict[str, Any]:
        return await GAME_MANAGER.approve_pending()
