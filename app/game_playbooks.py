from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Concise combatant knowledge distilled from Prydwen.gg, GameWith, CZN.gg, and YouTube A-Z guides
CZN_CHARACTER_KITS: dict[str, str] = {
    # Striker (Frontline combo & burst)
    "rin": "Rin (Striker/Void): DPS boss với chuỗi thẻ 0-cost và thế Dark Cloud; TRÁNH nhận thẻ Attack tốn nhiều AP làm đứt chuỗi stance.",
    "haru": "Haru (Striker/Justice): DPS tuyến đầu dồn sát thương đơn/liên hoàn; cần Controller hồi AP (Mika/Tiphera) để xả combo.",
    "mei lin": "Mei Lin (Striker/Passion): DPS Passion đánh liên kích tuyến đầu; hợp trang bị tăng ATK/Crit và Fate +AP.",
    "yuki": "Yuki (Striker/Order): Striker hệ Order dồn sát thương chủ lực; ưu tiên thẻ chi phí thấp hoặc Epiphany giảm cost.",
    "owen": "Owen (Striker/Passion): DPS cận chiến cơ bản, thẻ ổn định dễ phối hợp đầu game.",
    "arabella": "Arabella (Striker/Instinct): Striker hệ Instinct gây sát thương chủ lực.",
    "anika": "Anika (Striker/Order): Striker tuyến đầu hệ Order.",
    "rossweisse": "Rossweisse (Striker/Justice): Striker hệ Justice dồn sát thương tuyến đầu.",
    # Vanguard (Tank, Shield & Counter)
    "khalipe": "Khalipe (Vanguard/Instinct): Tank/Bruiser mạnh với thẻ >=2 AP (như Vulture Launch) tự kích hoạt AoE/giáp/phá phòng thủ; hợp đồ DEF/HP.",
    "magna": "Magna (Vanguard/Justice): Tạo khiên & phản đòn tuyến đầu bảo vệ HP chung cả đội.",
    "amir": "Amir (Vanguard/Order): Tank tạo giáp và giữ ổn định đội hình.",
    "maribell": "Maribell (Vanguard/Passion): Tạo giáp/bảo hộ đồng đội trước đòn đánh địch.",
    "nine": "Nine (Vanguard/Order): Vanguard tuyến đầu phòng thủ & chống chịu.",
    "adelheid": "Adelheid (Vanguard/Void): Vanguard hệ Void hỗ trợ chống chịu.",
    # Controller (Heal, AP Recovery & Card Draw)
    "mika": "Mika (Controller/Justice): Hồi máu, giải hiệu ứng xấu và hồi AP; ưu tiên giữ thẻ hồi AP/heal và đồ phụ kiện hỗ trợ.",
    "cassius": "Cassius (Controller/Instinct): Hỗ trợ top-tier buff đội, rút bài và hồi máu; ưu tiên thẻ Draw/Buff.",
    "tiphera": "Tiphera (Controller/Order): Hỗ trợ hồi phục + tạo AP rất hợp đi cùng carry tốn AP.",
    "orlea": "Orlea (Controller/Instinct): Giữ bài [Retain] và buff nhịp đánh ổn định.",
    "nia": "Nia (Controller/Instinct): Điều phối bộ bài, xoay vòng bài và hồi phục.",
    "rei": "Rei (Controller/Void): Buff sát thương và hỗ trợ thẻ chi phí thấp.",
    "narja": "Narja (Controller/Instinct): Controller hỗ trợ buff/hồi phục.",
    "blazebell": "Blazebell (Controller/Justice): Controller hệ Justice hỗ trợ đội hình.",
    # Ranger (Follow-up & Draw Utility)
    "veronica": "Veronica (Ranger/Passion): Tháp pháo Ballista bắn phụ mỗi lượt không tốn AP và rút bài; không làm đứt stance của carry.",
    "veronika": "Veronica (Ranger/Passion): Tháp pháo Ballista bắn phụ mỗi lượt không tốn AP và rút bài; không làm đứt stance của carry.",
    "hugo": "Hugo (Ranger/Order): Kích hoạt đòn Follow-up đánh theo sau phối hợp cùng Striker.",
    "selena": "Selena (Ranger/Passion): Hỗ trợ sát thương tầm xa và bào thanh Tenacity.",
    "beryl": "Beryl (Ranger/Justice): Sub-DPS tầm xa kèm rút bài giúp xoay vòng bộ bài mượt.",
    "heidemarie": "Heidemarie (Ranger/Passion): Ranger tầm xa hệ Passion.",
    "hilde": "Hilde (Ranger/Instinct): Ranger hỗ trợ sát thương hệ Instinct.",
    "fei": "Fei (Ranger/Void): Ranger hệ Void đánh tầm xa.",
    # Psionic (Void/Exhaust & Deck Manipulation)
    "chizuru": "Chizuru (Psionic/Void): Psionic hệ Void biến đổi/tạo thẻ và dồn sát thương kỹ năng.",
    "kayron": "Kayron (Psionic/Void): Psionic hệ Void scale sát thương mạnh theo bộ bài & Exhaust.",
    "tressa": "Tressa (Psionic/Void): Biến đổi thẻ và tăng lực cho đội hình Void/tốn AP.",
    "olga": "Olga (Psionic/Instinct): Psionic điều phối thẻ và hiệu ứng phụ.",
    "rita": "Rita (Psionic/Justice): Psionic hệ Justice hỗ trợ sát thương/hiệu ứng.",
    "tenebria": "Tenebria (Psionic/Passion): Psionic hệ Passion gây debuff/áp lực.",
    # Hunter (Bullet & Rapid 0-cost Pressure)
    "luke": "Luke (Hunter/Order): Hunter xả đòn liên kích chi phí thấp; cực hợp trang bị tăng crit thẻ 0-cost (RFS-17).",
    "renoa": "Renoa (Hunter/Void): Tạo thẻ đạn/Bullet cộng dồn sát thương nhanh.",
    "lucas": "Lucas (Hunter/Passion): Hunter đánh nhanh tạo nhịp áp lực.",
    "diana": "Diana (Hunter/Passion): Hunter hệ Passion đánh chuỗi.",
    "sereniel": "Sereniel (Hunter/Instinct): Hunter hệ Instinct đánh nhanh.",
}

# Official in-game Help & community rulebook distilled by topic for compact per-phase injection
CZN_HELP_TOPICS: dict[str, str] = {
    "keywords": (
        "HELP TỪ KHÓA THẺ: [Retain]=giữ lại cuối lượt không bỏ; [Exhaust / N]=dùng hết N lần sẽ biến mất hết trận; "
        "[Lead]=50% giảm 1 AP CHỈ KHI đánh ĐẦU TIÊN trong lượt; [Retrieve]=đánh xong tự quay lại tay; "
        "[Celestial]=tự kích hoạt khi đánh thẻ >=2 AP; [Initiation]=luôn lên đầu bộ rút lượt 1; "
        "[Finale]=đánh xong KẾT THÚC LƯỢT NGAY (chỉ dùng cuối lượt!)."
    ),
    "combat": (
        "HELP CHIẾN ĐẤU & PHÍM TẮT PC CHÍNH THỨC: 3 AP/lượt, rút 5 thẻ (tối đa 10). Phím 1..9, 0 = Select/Use Card 1..10; "
        "Left/Right hoặc Tab = chọn mục tiêu địch; Enter = Confirm/dùng thẻ; ESC = hủy thẻ đang chọn; E = End Turn; Z = Skip; "
        "R = Auto Battle; F1/F2/F3 = Ego Skill 1/2/3; A = Draw Pile; S = Graveyard; D = All Cards; Space = Dialogue; T = Help; "
        "Sảnh: 4 = Chaos, 6 = Combatants, H = Home. Enemy Action Count -1 mỗi thẻ ta đánh -> Break Tenacity (+1 AP, Draw 1, hoãn +1); Stress 100 -> Mental Breakdown."
    ),
    "faint_memory": (
        "HELP SAVE DATA & FAINT MEMORY: Cap = 30 + 10*(Tier-1) (Tier 1=30, Tier 7=90, Tier 15=160). "
        "Removal 0/10/30/50/70 (+20 nếu xóa Basic), Duplication 0/10/30/50/70, Conversion +10, "
        "Neutral +20, Monster +80, Epiphany +10 (Basic=0), Divine Epiphany +20, Forbidden +20 (luôn được lưu kể cả vượt cap). "
        "Vượt cap bị hệ thống tự cắt ngẫu nhiên thẻ/nâng cấp lúc kết thúc Chaos."
    ),
    "map_nodes": (
        "HELP BẢN ĐỒ CHAOS: Safe Zone/Campfire -> chọn Rest (hồi HP/giảm Stress trước Elite/Boss), TRÁNH Training (thêm Neutral rác loãng deck). "
        "Dellang Shop -> ưu tiên dùng Credit XÓA thẻ Basic/Curse yếu. Unknown Area -> tìm Dimensional Tunnel (thẻ Forbidden/buff lớn). "
        "Elite Node -> x2 Credit, đồ Rare/Legendary và cơ hội rơi Monster Card."
    ),
    "ui_navigation": (
        "HELP GIAO DIỆN: Nút Back ◁ luôn ở góc trên trái (44, 44). Menu ≡ (955, 42) và icon (i) chứa Help chính thức. "
        "Combatant List: nút 'Details' [ĐEN] (dưới phải-giữa) là nút BẤM ĐƯỢC để xem nhân vật; 'Assign' [XÁM] là chưa chọn ô đổi. "
        "Details: tab trái gồm Stats / • Cards / Partners / Save Data / Potential / Memory Fragments (6 ô: Shock/Suppression/Denial/Ideal/Desire/Imagination); nút cam 'Promotions' góc dưới phải KHÔNG phải nút Confirm."
    ),
}

GOOD_FATES = ("altruism", "brainwash", "cheerful", "challenges", "equipment", "legendary", "remove", "draw", "+1 ap", "gain 1 action")
TRAP_FATES = ("satiety", "normal neutral card", "curse")

_LEARNED_CACHE: dict[str, str] = {}
_LEARNED_HELP: list[str] = []
_LEARNED_FILE: Path | None = None


def configure_learned_store(data_dir: Path) -> None:
    global _LEARNED_FILE, _LEARNED_CACHE, _LEARNED_HELP
    store = data_dir / "game_playbooks" / "czn_learned.json"
    _LEARNED_FILE = store
    if store.is_file():
        try:
            loaded = json.loads(store.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _LEARNED_CACHE = {str(k).lower(): str(v)[:240] for k, v in loaded.get("kits", {}).items() if v}
                _LEARNED_HELP = [str(x)[:360] for x in loaded.get("web_notes", []) if x][:8]
        except Exception:
            pass


def get_czn_knowledge_summary() -> dict[str, Any]:
    unique_kits = len(set(CZN_CHARACTER_KITS.values())) + len(_LEARNED_CACHE)
    return {
        "combatants_trained": unique_kits,
        "help_topics_trained": len(CZN_HELP_TOPICS),
        "sources": [
            "Help CZN chính thức (Keywords/Stress/Faint Memory/Nodes/UI)",
            "STOVE Guide",
            "Prydwen.gg",
            "GameWith",
            "CZN.gg",
            "Củ Lạc Giòn Tan A-Z",
        ],
        "web_learned_count": len(_LEARNED_CACHE) + len(_LEARNED_HELP),
    }


async def learn_czn_from_web(data_dir: Path) -> dict[str, Any]:
    """Explicitly fetch & cache fresh Chaos Zero Nightmare Help, mechanics & character guides from public wikis."""
    import browser as browser_tools

    configure_learned_store(data_dir)
    queries = [
        "site:page.onstove.com/chaoszeronightmare guide combat stress save data",
        "site:prydwen.gg/chaos-zero-nightmare beginners guide characters tier list",
        "site:gamewith.net OR site:czn.gg chaos zero nightmare faint memory fate keywords",
    ]
    res = await browser_tools.search_public_web(queries, max_results=2)
    pages = [p for p in res.get("results", []) if p.get("text")]
    learned_snippets: list[str] = []
    for pg in pages[:5]:
        title = str(pg.get("title", "")).strip()[:80]
        url = str(pg.get("url", ""))
        snippet = " ".join(str(pg.get("text", "")).split())[:320]
        if snippet:
            learned_snippets.append(f"{title}: {snippet} ({url})")
    target = data_dir / "game_playbooks" / "czn_learned.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"kits": _LEARNED_CACHE, "web_notes": learned_snippets}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "pages_read": len(pages), "notes": learned_snippets, **get_czn_knowledge_summary()}


PLAYBOOK_CATALOG: list[dict[str, Any]] = [
    {
        "id": "none",
        "name": "Tự do (cửa sổ thật bất kỳ)",
        "description": "Không ép kịch bản sẵn; AI đọc lưới tọa độ, Windows OCR và làm đúng mục tiêu bạn nhập.",
        "options": [],
    },
    {
        "id": "czn",
        "name": "Chaos Zero Nightmare (Help A-Z · Combatants · Chaos)",
        "description": "Tích hợp toàn bộ Help CZN (AP/Action Count/Tenacity/Keywords/Stress/Faint Memory/Nodes), tự quét Details -> Cards & Back, nhận diện màu nút CAM/TÍM/ĐEN vs XÁM.",
        "defaults": {
            "branch": "chaos_manifestation",
            "world": "blue_pot",
            "preset_team": "keep",
            "difficulty": 3,
            "scout_skills": True,
        },
        "branches": [
            {"id": "chaos_manifestation", "name": "Chaos Manifestation (đang mở)"},
            {"id": "zero_system", "name": "Zero System (chỉ chọn nếu đã mở khóa)"},
        ],
        "worlds": [
            {"id": "blue_pot", "name": "The Blue Pot"},
            {"id": "twin_stars", "name": "Twin Star's Shadow"},
            {"id": "city_of_mist", "name": "City of Mist"},
            {"id": "auto", "name": "Bất kỳ hành tinh nào đang mở"},
        ],
        "presets": [
            {"id": "keep", "name": "Giữ đội hình hiện tại"},
            {"id": "team1", "name": "Preset Team 1"},
            {"id": "team2", "name": "Preset Team 2"},
            {"id": "team3", "name": "Preset Team 3"},
        ],
    },
    {
        "id": "hsr",
        "name": "Honkai: Star Rail (Vũ trụ mô phỏng / Turn-based)",
        "description": "Quản lý điểm chiến kỹ (SP), kích hoạt Tuyệt kỹ (1..4), chọn Chúc phúc/Vật thể lạ Vũ trụ mô phỏng và phá điểm yếu.",
        "defaults": {"world_hint": "Vũ trụ mô phỏng", "difficulty": 3},
    },
]

WORLD_NAMES = {
    "blue_pot": "The Blue Pot",
    "twin_stars": "Twin Star's Shadow",
    "city_of_mist": "City of Mist",
    "auto": "any unlocked Chaos world",
}

WORLD_ALIASES: dict[str, tuple[str, ...]] = {
    "blue_pot": ("the blue pot", "blue pot"),
    "twin_stars": ("twin star's shadow", "twin star", "twin stgr", "shadow"),
    "city_of_mist": ("city of mist", "mist"),
}


def list_playbooks() -> list[dict[str, Any]]:
    return PLAYBOOK_CATALOG


def detect_game_for_window(title: str, process_name: str = "") -> dict[str, str]:
    """Infer known game playbook + UI mode metadata from desktop window title/process."""
    t = f"{title} {process_name}".lower()
    if "chaos zero nightmare" in t or "chaoszero" in t or "ssr-stove" in t:
        return {"playbook": "czn", "game_name": "Chaos Zero Nightmare"}
    if "honkai: star rail" in t or "star rail" in t or "starrail" in t or "băng hoại" in t:
        return {"playbook": "hsr", "game_name": "Honkai: Star Rail"}
    return {"playbook": "none", "game_name": ""}


def match_known_kits(texts: list[str]) -> list[str]:
    joined = " ".join(texts).lower()
    hits: list[str] = []
    seen = set()
    merged = {**CZN_CHARACTER_KITS, **_LEARNED_CACHE}
    for key, desc in merged.items():
        if key in joined and desc not in seen:
            seen.add(desc)
            hits.append(desc)
    return hits[:4]


def inject_czn_icon_hints(phase: str, ocr_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append synthetic CZN fixed-position icon labels unseen by text OCR (Back ◁, Skip >|, Home, Menu)."""
    items = list(ocr_items)
    existing = " ".join(str(it.get("text", "")).lower() for it in items)
    if phase in {"combatant_list", "character_details", "chaos_branch", "world_select", "preset_select", "team_formation"}:
        if "back" not in existing:
            items.append({"text": "Back_◁", "x": 44, "y": 44, "state": "ĐEN"})
    if phase == "fate_choice" and "skip" not in existing:
        items.append({"text": "Skip_>|", "x": 760, "y": 926})
    return items


def extract_visible_czn_scout_note(phase: str, ocr_items: list[dict[str, Any]]) -> str:
    """Capture real visible combatant name & Stats/Cards text on Character Details / Combatant List screens."""
    if phase != "character_details":
        return ""
    texts = [str(it.get("text", "")).strip() for it in ocr_items if str(it.get("text", "")).strip()]
    joined_low = " ".join(texts).lower()
    char_name = ""
    for key in CZN_CHARACTER_KITS:
        if key in joined_low:
            char_name = key.title()
            break
    if not char_name:
        for it in ocr_items:
            t = str(it.get("text", "")).strip()
            if int(it.get("x", 0)) >= 650 and int(it.get("y", 0)) <= 240 and len(t) >= 3 and re.match(r"^[A-Za-z][A-Za-z '\-]+$", t):
                if t.lower() not in {"stats", "cards", "lv.", "details", "tb"} and not any(ch.isdigit() for ch in t):
                    char_name = t
                    break
    if not char_name:
        return ""
    is_stats = "attack" in joined_low and "critical chance" in joined_low
    kit = CZN_CHARACTER_KITS.get(char_name.lower(), "")
    if is_stats:
        return f"[{char_name}] {kit}" if kit else f"[{char_name}] Đang mở Stats."
    card_snippets = [
        str(it.get("text", "")).strip()
        for it in ocr_items
        if int(it.get("x", 0)) >= 240 and int(it.get("y", 0)) >= 250 and len(str(it.get("text", "")).strip()) >= 3
    ][:8]
    cards_str = " / ".join(card_snippets)
    if kit and cards_str:
        return f"[{char_name} · Cards] {cards_str[:120]} — {kit[:110]}"
    if cards_str:
        return f"[{char_name} · Cards] {cards_str[:160]}"
    return kit


def detect_czn_phase(ocr_texts: list[str]) -> str:
    joined = " ".join(ocr_texts).lower()
    if ("faint memory" in joined and any(k in joined for k in ("copy", "remove", "set effect"))) or (
        "combatants" in joined and "partners" in joined and "fate" in joined
    ):
        return "run_info_overlay"
    if "content locked" in joined or ("tap to close" in joined and ("clear story" in joined or "locked" in joined)):
        return "locked_popup"
    if (
        "chaos manifestation" in joined
        and "zero system" in joined
        and "exploration" not in joined
        and "difficulty" not in joined
        and "team formation" not in joined
    ):
        return "chaos_branch"
    if "team formation" in joined or ("difficulty" in joined and any(k in joined for k in ("enter", "preset", "delegate"))):
        return "team_formation"
    if any(k in joined for k in ("exploration", "unconfirmed chaos", "chaos size", "reward info", "twin star", "twin stgr", "blue pot", "city of mist")):
        return "world_select"
    if "team preset" in joined or ("preset" not in joined and "team 1" in joined and "select" in joined):
        return "preset_select"
    if "combatant list" in joined or "quick formation" in joined or ("assign" in joined and "details" in joined):
        return "combatant_list"
    if (
        any(k in joined for k in ("ego skill", "unique cards", "neutral cards", "potential", "save data", "memory fragments", "ego manifestation", "promotions"))
        and "enter" not in joined
        and "choose your fate" not in joined
    ):
        return "character_details"
    if "choose your fate" in joined or ("fate" in joined and "confirm" in joined):
        return "fate_choice"
    if "card reward" in joined or "select the combatant" in joined:
        return "card_reward"
    if "equipment" in joined and ("extract" in joined or "confirm" in joined or "select combatant" in joined):
        return "equipment"
    if any(k in joined for k in ("end turn", "ep ", "stress", "breakdown", "draw", "discard")):
        return "combat"
    if ("tutorial" in joined or ("help" in joined and "close" in joined) or "tap to close" in joined) and "end turn" not in joined:
        return "help_popup"
    if any(k in joined for k in ("sortie", "simulation", "ark city", "combatants")) or ("story" in joined and "chaos" in joined):
        return "lobby"
    if any(k in joined for k in ("confirm", "continue", "next", "skip", "rest", "training", "shop", "dellang")):
        return "event_or_map"
    return "general"


def _find_ocr(
    ocr_items: list[dict[str, Any]],
    *terms: str,
    min_x: int = 0,
    max_x: int = 1000,
    min_y: int = 0,
    max_y: int = 1000,
    exclude: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    low_terms = tuple(t.lower() for t in terms)
    low_excl = tuple(e.lower() for e in exclude)
    for it in ocr_items:
        txt = str(it.get("text", "")).strip().lower()
        x = int(it.get("x", 0))
        y = int(it.get("y", 0))
        if min_x <= x <= max_x and min_y <= y <= max_y:
            if low_excl and any(ex in txt for ex in low_excl):
                continue
            if any(term in txt for term in low_terms):
                return it
    return None


def _mk_act(
    action: str,
    x: int,
    y: int,
    comment: str,
    reason: str,
    *,
    mood: str = "thinking",
    x2: int = 0,
    y2: int = 0,
    key: str = "",
    duration_ms: int = 80,
    note: str = "",
    fast_combat: bool = False,
) -> dict[str, Any]:
    return {
        "mood": mood,
        "comment": comment,
        "action": action,
        "x": x,
        "y": y,
        "x2": x2 or x,
        "y2": y2 or y,
        "key": key,
        "duration_ms": duration_ms,
        "direction": "down",
        "amount": 2,
        "text": "",
        "reason": reason,
        "note": note,
        "fast_combat": fast_combat,
    }


def _advise_lobby_or_chaos(
    phase: str, config: dict[str, Any], ocr_items: list[dict[str, Any]], corner_state: str, state: dict[str, Any]
) -> dict[str, Any] | None:
    scout_lobby = bool(config.get("scout_lobby", False))
    if phase == "locked_popup":
        if state.get("zero_tried"):
            state["zero_locked"] = True
        tap = _find_ocr(ocr_items, "tap to close")
        tx = int(tap["x"]) if tap else 500
        ty = int(tap["y"]) if tap else 935
        return _mk_act("click_xy", tx, ty, "Mục này đang khóa, đóng thông báo để chọn màn đang mở!", "CZN locked_popup: Tap to close")

    if phase == "lobby":
        if scout_lobby and not state.get("lobby_done"):
            cmb = _find_ocr(ocr_items, "combatants", min_x=650)
            if cmb:
                return _mk_act("click_xy", cmb["x"], cmb["y"], "Mình ghé Combatants xem nhanh đội hình trước nhé!", "CZN lobby scout: click Combatants")
        chaos = _find_ocr(ocr_items, "chaos", min_x=650)
        if chaos:
            return _mk_act("click_xy", chaos["x"], chaos["y"], "Vào chế độ Chaos thôi nào!", "CZN lobby: click Chaos", mood="excited")
        return None

    if phase == "chaos_branch":
        branch = str(config.get("branch", "chaos_manifestation"))
        if branch == "zero_system" and not state.get("zero_locked"):
            zs = _find_ocr(ocr_items, "zero system")
            if zs:
                state["zero_tried"] = True
                return _mk_act("click_xy", zs["x"], zs["y"], "Thử mở Zero System xem đã mở khóa chưa...", "CZN branch: try Zero System")
        cm = _find_ocr(ocr_items, "chaos manifestation")
        if cm:
            return _mk_act("click_xy", cm["x"], cm["y"], "Vào Chaos Manifestation nào!", "CZN branch: click Chaos Manifestation", mood="excited")
        return None

    if phase == "world_select":
        world_id = str(config.get("world", "blue_pot"))
        target_name = WORLD_NAMES.get(world_id, "The Blue Pot")
        aliases = WORLD_ALIASES.get(world_id, (target_name.lower(),))
        enter = _find_ocr(ocr_items, "enter", min_x=720, min_y=820)
        if world_id != "auto":
            right_panel_match = _find_ocr(ocr_items, *aliases, min_x=700, max_y=450, exclude=("unconfirmed",))
            if right_panel_match and enter and enter.get("state") != "XÁM" and corner_state != "XÁM":
                return _mk_act("click_xy", enter["x"], enter["y"], f"Đã chọn {target_name}, bấm Enter vào sảnh đội hình!", f"CZN world ready: click Enter for {target_name}", mood="excited")
            map_planet = _find_ocr(ocr_items, *aliases, min_x=100, max_x=880, min_y=180, max_y=850, exclude=("unconfirmed",))
            if map_planet:
                click_x = max(120, int(map_planet["x"]) - 75)
                return _mk_act("click_xy", click_x, int(map_planet["y"]), f"Chọn hành tinh {target_name} trên bản đồ Chaos!", f"CZN world select: click {target_name}")
        elif enter and (enter.get("state") in {"CAM", "TÍM"} or corner_state in {"CAM", "TÍM"}):
            return _mk_act("click_xy", enter["x"], enter["y"], "Hành tinh đã chọn sẵn, bấm Enter!", "CZN world auto: click Enter", mood="excited")
        else:
            any_world = _find_ocr(ocr_items, "the blue pot", "twin star", "twin stgr", "city of mist", min_x=100, max_x=880, min_y=180, max_y=850, exclude=("unconfirmed",))
            if any_world:
                click_x = max(120, int(any_world["x"]) - 75)
                return _mk_act("click_xy", click_x, int(any_world["y"]), f"Chọn {any_world['text']}!", "CZN world auto: select unlocked planet")
    return None


def _advise_scouting_or_team(
    phase: str, config: dict[str, Any], ocr_items: list[dict[str, Any]], corner_state: str, state: dict[str, Any]
) -> dict[str, Any] | None:
    scout_skills = bool(config.get("scout_skills", True))
    scout_lobby = bool(config.get("scout_lobby", False))

    if phase == "combatant_list":
        visits = int(state.get("combatant_list_visits", 0))
        if (scout_skills or scout_lobby) and not state.get("details_done") and visits < 3:
            det = _find_ocr(ocr_items, "details", min_x=480, min_y=840)
            if det and det.get("state") != "XÁM":
                state["combatant_list_visits"] = visits + 1
                return _mk_act("click_xy", det["x"], det["y"], "Mở Details xem bộ thẻ kỹ năng nhân vật!", "CZN combatant_list: click Details[ĐEN]")
        state["details_done"] = True
        state["lobby_done"] = True
        return _mk_act("click_xy", 44, 44, "Xem xong danh sách nhân vật rồi, bấm Back quay lại nhé!", "CZN combatant_list: Back ◁ (44,44)")

    if phase == "character_details":
        state["details_steps"] = int(state.get("details_steps", 0)) + 1
        texts_low = " ".join(str(it.get("text", "")).lower() for it in ocr_items)
        char_name = next((k for k in CZN_CHARACTER_KITS if k in texts_low), f"slot{state['details_steps']}")
        cards_checked: set[str] = state.setdefault("cards_checked", set())
        slots_clicked: set[int] = state.setdefault("slots_clicked", set())
        is_stats_tab = "attack" in texts_low and "critical chance" in texts_low

        if (scout_skills or scout_lobby) and not state.get("details_done"):
            if is_stats_tab and char_name not in cards_checked and int(state.get("cards_clicks", 0)) < 3:
                cards_tab = _find_ocr(ocr_items, "cards", max_x=280, min_y=280, max_y=450)
                if cards_tab:
                    state["cards_clicks"] = int(state.get("cards_clicks", 0)) + 1
                    return _mk_act("click_xy", cards_tab["x"], cards_tab["y"], f"Mở tab Cards để đọc bộ thẻ kỹ năng của {char_name.title()}!", f"CZN character_details: click Cards tab for {char_name}")
            cards_checked.add(char_name)
            portrait_ys = [152, 252, 358]
            next_idx = next((i for i in range(len(portrait_ys)) if i not in slots_clicked), None)
            if len(cards_checked) < 2 and next_idx is not None and state["details_steps"] < 6:
                slots_clicked.add(next_idx)
                return _mk_act("click_xy", 42, portrait_ys[next_idx], f"Đã ghi nhớ thẻ {char_name.title()}, chuyển sang đồng đội tiếp theo!", f"CZN character_details: inspect party slot {next_idx + 1}")
        state["details_done"] = True
        state["lobby_done"] = True
        return _mk_act("click_xy", 44, 44, "Đã đọc xong kỹ năng đội hình, bấm Back quay ra!", "CZN character_details: done scouting -> Back ◁ (44,44)")

    if phase == "preset_select":
        preset = str(config.get("preset_team", "keep"))
        team_label = {"team1": "team 1", "team2": "team 2", "team3": "team 3"}.get(preset, "team 1")
        if not state.get("preset_picked"):
            team_hdr = _find_ocr(ocr_items, team_label)
            if team_hdr:
                selects = [
                    it for it in ocr_items
                    if "select" in str(it.get("text", "")).lower()
                    and abs(int(it.get("x", 0)) - int(team_hdr["x"])) <= 150
                    and int(it.get("y", 0)) > int(team_hdr["y"])
                    and it.get("state") != "XÁM"
                ]
                if selects:
                    state["preset_picked"] = True
                    return _mk_act("click_xy", selects[0]["x"], selects[0]["y"], f"Chọn đội hình {team_label.upper()}!", f"CZN preset_select: click Select under {team_label}")
        state["preset_picked"] = True
        return _mk_act("click_xy", 44, 44, "Quay lại màn hình Team Formation!", "CZN preset_select: Back ◁ (44,44)")

    if phase == "team_formation":
        preset = str(config.get("preset_team", "keep"))
        diff = str(int(config.get("difficulty") or 3))
        if preset in {"team1", "team2", "team3"} and not state.get("preset_picked"):
            p_btn = _find_ocr(ocr_items, "preset", max_x=300, min_y=840)
            if p_btn:
                return _mk_act("click_xy", p_btn["x"], p_btn["y"], f"Mở Preset để chọn đội hình {preset.upper()}!", "CZN team_formation: click Preset")
        if scout_skills and not state.get("details_done"):
            return _mk_act("click_xy", 355, 480, "Xem nhanh kỹ năng thành viên trong đội trước khi vào Chaos!", "CZN team_formation: click middle character card to scout details")
        if not state.get("difficulty_clicked"):
            diff_btn = next(
                (it for it in ocr_items if str(it.get("text", "")).strip() == diff and int(it.get("x", 0)) >= 550 and int(it.get("y", 0)) <= 380),
                None,
            )
            if diff_btn:
                state["difficulty_clicked"] = True
                return _mk_act("click_xy", diff_btn["x"], diff_btn["y"], f"Chọn độ khó Difficulty {diff}!", f"CZN team_formation: click difficulty {diff}")
        enter = _find_ocr(ocr_items, "enter", min_x=800, min_y=850)
        if enter and enter.get("state") != "XÁM":
            return _mk_act("click_xy", enter["x"], enter["y"], "Đội hình và độ khó sẵn sàng, bấm Enter xuất phát!", "CZN team_formation: click Enter", mood="excited")
    return None


def _score_combat_card(text: str) -> int:
    low = text.lower()
    if any(k in low for k in ("breakdown", "curse", "wound", "trauma")):
        return -30
    if "finale" in low:
        return -20
    if any(k in low for k in ("lead", "initiation", "epiphany", "+1 ap", "+2 ap", "gain 1 ap", "draw", "upgrade")):
        return 100
    if any(k in low for k in ("strike", "slash", "attack", "shot", "bullet", "ballista", "vulture", "break", "tenacity", "dmg", "shield", "heal", "barrier", "counter")):
        return 65
    return 40


def _inspect_zoomed_card_decision(
    ocr_items: list[dict[str, Any]],
    cur_ap: int | None,
    tried_slots: set[int],
) -> tuple[str, str]:
    """Read previewed card text on screen after pressing 1..9 and decide: 'enter', 'esc', 'left', or 'right'."""
    noise = ("end turn", "draw", "discard", "ep ", "ap ", "auto", "stress", "x1", "x2", "x3")
    card_terms = ("cost", "deal", "%", "damage", "dmg", "enemy", "enemies", "slash", "strike", "shield", "heal", "finale", "curse")
    card_lines: list[str] = []
    enemies: list[tuple[int, str]] = []
    for it in ocr_items:
        txt = str(it.get("text", "")).strip()
        low = txt.lower()
        x, y = int(it.get("x", 0)), int(it.get("y", 0))
        if any(n in low for n in noise) or re.fullmatch(r"\d+\s*/\s*\d+", txt):
            continue
        if 380 <= x <= 930 and 150 <= y <= 460 and not any(ct in low for ct in card_terms):
            enemies.append((x, txt))
        if 120 <= x <= 880 and 200 <= y <= 840 and len(txt) >= 2:
            card_lines.append(txt)

    joined = " ".join(card_lines).lower()
    if any(b in joined for b in ("curse", "wound", "trauma", "unplayable", "cannot be used")):
        return "esc", "Thẻ bất lợi/không dùng được"
    if "finale" in joined and len(tried_slots) < 3 and (cur_ap is None or cur_ap > 1):
        return "esc", "Thẻ Finale sẽ kết thúc lượt ngay, để sau"

    # Extract card AP cost if visible
    cost_match = re.search(r"\b(?:cost|ap)\s*[:=]?\s*([0-9])\b", joined)
    card_cost = int(cost_match.group(1)) if cost_match else None
    if card_cost is None:
        for t in card_lines[:4]:
            if re.fullmatch(r"[0-3]", t):
                card_cost = int(t)
                break
    if card_cost is not None and cur_ap is not None and card_cost > cur_ap:
        return "esc", f"Thẻ tốn {card_cost} AP nhưng chỉ còn {cur_ap} AP"

    is_targeted = any(k in joined for k in ("damage", "dmg", "attack", "strike", "slash", "shot", "tenacity", "1 enemy", "single")) and not any(
        aoe in joined for aoe in ("all enemies", "every enemy", "shield", "heal", "barrier", "allies")
    )
    distinct_xs: list[int] = []
    for ex, _ in sorted(enemies):
        if not distinct_xs or abs(ex - distinct_xs[-1]) >= 95:
            distinct_xs.append(ex)
    if is_targeted and len(distinct_xs) >= 2:
        urgent = next(
            ((ex, txt) for ex, txt in enemies if any(u in txt.lower() for u in ("break", "weak")) or re.fullmatch(r"1", txt.strip())),
            None,
        )
        if urgent:
            mid = sum(distinct_xs) / len(distinct_xs)
            if urgent[0] < mid - 55:
                return "left", "Chuyển mũi tên trái sang địch ưu tiên"
            if urgent[0] > mid + 55:
                return "right", "Chuyển mũi tên phải sang địch ưu tiên"

    fn_tag = (
        "Rút bài/+AP"
        if any(k in joined for k in ("draw", "ap", "epiphany", "lead", "initiation"))
        else ("Khiên/Hồi" if any(k in joined for k in ("shield", "heal", "barrier", "def")) else "Tấn công/Kỹ năng")
    )
    return "enter", fn_tag


def _advise_combat_fast(
    ocr_items: list[dict[str, Any]],
    state: dict[str, Any],
    history: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Fast <1s turn-based combat planner: 1..9 inspect -> read card -> Left/Right target -> Enter/Esc (with drag fallback)."""
    ocr_texts = [str(it.get("text", "")) for it in ocr_items]
    phase = detect_czn_phase(ocr_texts)
    end_turn = _find_ocr(ocr_items, "end turn", "end tur", "kết thúc", min_x=740, min_y=700)

    zoom_active = state.get("combat_preview_slot") is not None and phase == "general"
    if phase != "combat" and end_turn is None and not zoom_active:
        if state.get("in_combat") and phase == "general" and len(ocr_items) <= 6:
            waits = sum(1 for h in history[-6:] if h.get("action") == "wait")
            if waits < 6:
                return _mk_act("wait", 500, 500, "Đang qua lượt / hiệu ứng chiêu...", "CZN combat animation: fast wait", duration_ms=200, fast_combat=True)
        state["in_combat"] = False
        state["combat_probes"] = 0
        state["combat_preview_slot"] = None
        return None

    state["in_combat"] = True
    tried_slots: set[int] = state.setdefault("combat_tried_slots", set())
    if history and (
        "end turn" in str(history[-1].get("reason", "")).lower()
        or (history[-1].get("action") == "key_press" and history[-1].get("key") == "e")
    ):
        state["combat_probes"] = 0
        state["combat_preview_slot"] = None
        state["combat_target_adjusted"] = False
        state["combat_key_fails"] = 0
        state["ego_used_this_turn"] = False
        tried_slots.clear()

    # Sync state with outcome of previous combat key/action
    if history:
        prev = history[-1]
        if prev.get("action") == "key_press":
            pk = str(prev.get("key", ""))
            if pk in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}:
                if prev.get("screen_changed"):
                    state["combat_key_fails"] = 0
                    state["combat_zoomed_ok"] = True
                else:
                    state["combat_key_fails"] = int(state.get("combat_key_fails", 0)) + 1
                    state["combat_preview_slot"] = None
                    if int(state.get("combat_key_fails", 0)) >= 2 and not state.get("combat_zoomed_ok"):
                        state["combat_kb_disabled"] = True
            elif pk == "esc":
                state["combat_preview_slot"] = None
                state["combat_target_adjusted"] = False
            elif pk in {"left", "right", "tab"}:
                state["combat_target_adjusted"] = True
            elif pk in {"f1", "f2", "f3"}:
                state["ego_used_this_turn"] = True
            elif pk == "enter":
                if prev.get("screen_changed"):
                    state["combat_preview_slot"] = None
                    state["combat_target_adjusted"] = False
                    tried_slots.clear()
                else:
                    # Enter didn't cast (no AP / invalid): leave preview open to hit Esc next step
                    state["combat_force_esc"] = True

    recent_fails = [
        h for h in history[-2:]
        if h.get("action") in {"drag_xy", "click_xy"} and not h.get("screen_changed", True)
    ]
    if len(history) >= 2 and len(recent_fails) >= 2:
        state["combat_probes"] = 0
        state["combat_preview_slot"] = None
        tried_slots.clear()
        ex = int(end_turn["x"]) if end_turn else 915
        ey = int(end_turn["y"]) if end_turn else 875
        return _mk_act("click_xy", ex, ey, "Thẻ bài hết AP hoặc không đánh được nữa, bấm End Turn ngay!", "CZN combat: 2 stalled plays -> End Turn", mood="happy", fast_combat=True)

    # Parse AP ratio like "3/3" or "0/3" on bottom HUD
    cur_ap: int | None = None
    for it in ocr_items:
        if int(it.get("x", 0)) <= 450 and int(it.get("y", 0)) >= 600:
            m = re.search(r"\b(\d+)\s*/\s*\d+\b", str(it.get("text", "")))
            if m:
                cur_ap = int(m.group(1))
                break

    # Primary PC keyboard card loop: 1..9 inspect -> read card -> Left/Right target -> Enter / Esc
    use_keyboard = bool((config or {}).get("combat_keyboard", True)) and not state.get("combat_kb_disabled", False)
    if use_keyboard:
        if state.pop("combat_force_esc", False):
            state["combat_preview_slot"] = None
            state["combat_target_adjusted"] = False
            return _mk_act("key_press", 0, 0, "Thẻ này không kích hoạt được, nhấn Esc hủy chọn!", "CZN combat key: Esc after failed Enter", key="esc", duration_ms=45, fast_combat=True)

        cur_slot = state.get("combat_preview_slot")
        if cur_slot is not None:
            decision, info = _inspect_zoomed_card_decision(ocr_items, cur_ap, tried_slots)
            if decision in {"left", "right"} and state.get("combat_target_adjusted"):
                decision = "enter"
            if decision == "esc":
                state["combat_preview_slot"] = None
                state["combat_target_adjusted"] = False
                return _mk_act("key_press", 0, 0, f"Thẻ #{cur_slot} ({info}), nhấn Esc bỏ qua!", f"CZN combat key: Esc card #{cur_slot} ({info})", key="esc", duration_ms=45, fast_combat=True)
            if decision in {"left", "right"}:
                state["combat_target_adjusted"] = True
                return _mk_act("key_press", 0, 0, f"Thẻ #{cur_slot} ({info}), bấm mũi tên chọn địch rồi đánh!", f"CZN combat key: target arrow {decision} for card #{cur_slot}", mood="thinking", key=decision, duration_ms=45, fast_combat=True)
            return _mk_act("key_press", 0, 0, f"Dùng thẻ #{cur_slot} ({info}) -> nhấn Enter!", f"CZN combat key: Enter play card #{cur_slot} ({info})", mood="excited", key="enter", duration_ms=45, fast_combat=True)

        ep_full = any(re.search(r"\b[67]\s*/\s*7\b", str(it.get("text", ""))) for it in ocr_items if int(it.get("x", 0)) <= 320 and int(it.get("y", 0)) >= 680)
        if ep_full and not state.get("ego_used_this_turn") and (cur_ap == 0 or len(tried_slots) >= 2):
            state["ego_used_this_turn"] = True
            return _mk_act("key_press", 0, 0, "Ego Point đầy, tung Ego Skill F1!", "CZN combat key: F1 Ego Skill", mood="excited", key="f1", duration_ms=45, fast_combat=True)

        def _end_turn_action(msg: str, reason: str) -> dict[str, Any]:
            tried_slots.clear()
            state["combat_key_fails"] = 0
            if state.get("combat_zoomed_ok") or not end_turn:
                return _mk_act("key_press", 0, 0, msg, reason, mood="happy", key="e", duration_ms=45, fast_combat=True)
            return _mk_act("click_xy", end_turn["x"], end_turn["y"], msg, reason, mood="happy", fast_combat=True)

        if cur_ap == 0 and (len(tried_slots) >= 1 or (bool(history) and not history[-1].get("screen_changed", True))):
            return _end_turn_action("Hết AP rồi, bấm E kết thúc lượt nhé!", "CZN combat: 0 AP -> End Turn (key E)")

        if int(state.get("combat_key_fails", 0)) >= 2 and state.get("combat_zoomed_ok"):
            return _end_turn_action("Đã duyệt hết thẻ trên tay, bấm E kết thúc lượt!", "CZN combat: empty remaining slots -> End Turn (key E)")

        slot_order = (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)
        next_slot = next((n for n in slot_order if n not in tried_slots), None)
        if next_slot is not None:
            tried_slots.add(next_slot)
            state["combat_preview_slot"] = next_slot
            state["combat_target_adjusted"] = False
            return _mk_act("key_press", 0, 0, f"Nhấn phím {next_slot} xem chức năng thẻ bài!", f"CZN combat key: inspect card slot {next_slot}", mood="thinking", key=str(next_slot), duration_ms=45, fast_combat=True)
        return _end_turn_action("Hết bài cần đánh, bấm E kết thúc lượt!", "CZN combat: end turn after inspecting all slots")

    # Pick enemy target above play midline (drag_xy fallback)
    enemy = next(
        (
            it for it in ocr_items
            if 400 <= int(it.get("x", 0)) <= 900
            and 170 <= int(it.get("y", 0)) <= 560
            and not any(ui in str(it.get("text", "")).lower() for ui in ("draw", "discard", "end turn", "ep", "ap"))
        ),
        None,
    )
    tx = int(enemy["x"]) if enemy else 640
    ty = max(270, min(460, int(enemy["y"]) - 40)) if enemy else 380

    # Collect failed card x positions from last 2 stalled drags so we move across hand
    fail_xs = [
        int(h.get("x", -999))
        for h in history[-2:]
        if h.get("action") == "drag_xy" and not h.get("screen_changed", True)
    ]

    # Collect readable hand cards (y >= 690, x in 130..830)
    ui_noise = ("end turn", "draw", "discard", "ep ", "ap ", "auto", "x1", "x2", "x3")
    cards = []
    for it in ocr_items:
        txt = str(it.get("text", "")).strip()
        low = txt.lower()
        x, y = int(it.get("x", 0)), int(it.get("y", 0))
        if 130 <= x <= 830 and 690 <= y <= 945 and len(txt) >= 3:
            if any(u in low for u in ui_noise) or re.fullmatch(r"[\d/\s.:]+", txt):
                continue
            if sum(1 for fx in fail_xs if abs(fx - x) <= 35) >= 1 and len(fail_xs) >= 1:
                continue
            cards.append((_score_combat_card(txt), x, max(785, min(910, y)), txt))

    has_zero_cost_card = any("0" in c[3] or "lead" in c[3].lower() or "epiphany" in c[3].lower() for c in cards)
    if cur_ap == 0 and end_turn and (not has_zero_cost_card or (bool(history) and not history[-1].get("screen_changed", True))):
        state["combat_probes"] = 0
        return _mk_act("click_xy", end_turn["x"], end_turn["y"], "Hết AP rồi, kết thúc lượt nhé!", "CZN combat: 0 AP -> End Turn", mood="happy", fast_combat=True)

    if cards:
        cards.sort(key=lambda item: item[0], reverse=True)
        _, cx, cy, label = cards[0]
        state["combat_probes"] = 0
        return _mk_act(
            "drag_xy",
            cx,
            cy,
            f"Tung thẻ {label[:28]} ngay!",
            f"CZN combat card play: drag '{label[:28]}' -> enemy ({tx},{ty})",
            mood="excited",
            x2=tx,
            y2=ty,
            duration_ms=45,
            fast_combat=True,
        )

    probes = int(state.get("combat_probes", 0))
    last_two_failed = len(fail_xs) >= 2
    if end_turn and (last_two_failed or probes >= 5):
        state["combat_probes"] = 0
        return _mk_act("click_xy", end_turn["x"], end_turn["y"], "Đã đánh hết bài dùng được, bấm End Turn!", "CZN combat: end turn after hand cycle", mood="happy", fast_combat=True)

    slots = (480, 350, 610, 240, 720)
    cx = slots[probes % len(slots)]
    state["combat_probes"] = probes + 1
    return _mk_act(
        "drag_xy",
        cx,
        855,
        "Ra đòn thẻ bài trong tay!",
        f"CZN combat fast play: drag hand slot {cx} -> ({tx},{ty})",
        mood="excited",
        x2=tx,
        y2=ty,
        duration_ms=45,
        fast_combat=True,
    )


def _advise_fate_reward_equip(
    phase: str,
    config: dict[str, Any],
    ocr_items: list[dict[str, Any]],
    corner_state: str,
    state: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if phase == "run_info_overlay":
        return _mk_act("click_xy", 955, 55, "Đóng bảng thông tin đội hình [X] để quay lại chọn màn!", "CZN run_info_overlay: close via X (955,55)")

    if phase == "fate_choice":
        confirm = _find_ocr(ocr_items, "confirm", min_x=780, min_y=850)
        texts_low = " ".join(str(it.get("text", "")).lower() for it in ocr_items)
        is_trap = any(t in texts_low for t in TRAP_FATES)
        confirm_active = (confirm and confirm.get("state") in {"CAM", "TÍM"}) or (not confirm and corner_state in {"CAM", "TÍM"})
        if confirm_active:
            if is_trap and not state.get("fate_skip_tried"):
                state["fate_skip_tried"] = True
                return _mk_act("click_xy", 760, 926, "Gặp Fate Satiety dễ loãng bộ bài, thử bấm Skip >| nhé!", "CZN fate_choice: skip trap Satiety once")
            state["fate_skip_tried"] = False
            cx = int(confirm["x"]) if confirm else 890
            cy = int(confirm["y"]) if confirm else 926
            return _mk_act("click_xy", cx, cy, "Xác nhận thẻ Fate này!", "CZN fate_choice: click active Confirm[CAM]", mood="excited")
        # Confirm is XÁM -> score candidate Fate cards and pick best
        candidates = []
        for it in ocr_items:
            t = str(it.get("text", "")).strip()
            low = t.lower()
            x, y = int(it.get("x", 0)), int(it.get("y", 0))
            if 120 <= x <= 880 and 220 <= y <= 800 and "choose your fate" not in low and "confirm" not in low:
                score = 100 if any(g in low for g in GOOD_FATES) else (-100 if any(tr in low for tr in TRAP_FATES) else 20)
                candidates.append((score, min(780, max(220, x)), min(640, max(360, y)), t))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            _, fx, fy, label = candidates[0]
            return _mk_act("click_xy", fx, fy, f"Chọn Fate {label[:26]} trước khi Confirm!", f"CZN fate_choice: pick Fate card {label[:26]}")
        return _mk_act("click_xy", 500, 480, "Chọn thẻ Fate ở giữa để bật Confirm!", "CZN fate_choice: select center Fate card")

    if phase == "card_reward":
        confirm = _find_ocr(ocr_items, "confirm", min_x=780, min_y=850)
        skip = _find_ocr(ocr_items, "skip", min_x=640, max_x=830, min_y=850)
        texts_low = " ".join(str(it.get("text", "")).lower() for it in ocr_items)
        should_skip = ("curse" in texts_low or "wound" in texts_low or "normal neutral" in texts_low) or (
            "rin" in texts_low and any(c in texts_low for c in ("2 ap", "3 ap", "cost 2", "cost 3"))
        )
        if skip and should_skip and not state.get("reward_skip_tried"):
            state["reward_skip_tried"] = True
            return _mk_act("click_xy", skip["x"], skip["y"], "Thẻ này không hợp đội hình, bấm Skip để giữ bộ bài gọn!", "CZN card_reward: Skip bloat card")
        state["reward_skip_tried"] = False
        if confirm and confirm.get("state") in {"CAM", "TÍM"}:
            state["reward_slot_idx"] = 0
            return _mk_act("click_xy", confirm["x"], confirm["y"], "Đã chọn nhân vật nhận thẻ, bấm Confirm!", "CZN card_reward: Confirm[CAM]", mood="excited")
        if "select the combatant" in texts_low or any(int(it.get("x", 0)) >= 680 and 260 <= int(it.get("y", 0)) <= 760 for it in ocr_items):
            ys = (380, 540, 700)
            idx = int(state.get("reward_slot_idx", 0)) % len(ys)
            state["reward_slot_idx"] = idx + 1
            return _mk_act("click_xy", 790, ys[idx], "Confirm đang xám, chọn nhân vật bên phải để nhận thẻ!", f"CZN card_reward: select combatant slot {idx + 1}")
        return _mk_act("click_xy", 500, 480, "Chọn lá bài thưởng trước khi Confirm!", "CZN card_reward: select center reward card")

    if phase == "equipment":
        confirm = _find_ocr(ocr_items, "confirm", min_x=780, min_y=850)
        extract = _find_ocr(ocr_items, "extract", min_x=640, max_x=830, min_y=850)
        texts_low = " ".join(str(it.get("text", "")).lower() for it in ocr_items)
        tries = int(state.get("equip_slot_tries", 0))
        if confirm and confirm.get("state") in {"CAM", "TÍM"}:
            state["equip_slot_tries"] = 0
            return _mk_act("click_xy", confirm["x"], confirm["y"], "Đã chọn người mang trang bị, bấm Confirm!", "CZN equipment: Confirm[CAM]", mood="excited")
        if tries >= 3 and extract:
            state["equip_slot_tries"] = 0
            return _mk_act("click_xy", extract["x"], extract["y"], "Ô trang bị đã đầy, phân giải Extract lấy Credit nhé!", "CZN equipment: slots full -> Extract")
        is_def = any(k in texts_low for k in ("def", "defense", "shield", "heal", "health", "armor", "recovery", "hp"))
        order = (540, 720, 360) if is_def else (360, 540, 720)
        sy = order[tries % len(order)]
        state["equip_slot_tries"] = tries + 1
        return _mk_act("click_xy", 790, sy, "Confirm đang xám, chọn nhân vật phù hợp bên phải để gắn trang bị!", f"CZN equipment: select combatant slot y={sy}")
    return None


def advise_czn_action(
    config: dict[str, Any],
    ocr_items: list[dict[str, Any]],
    corner_state: str,
    czn_state: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Fast deterministic CZN router for menus, scouting (Details -> Cards -> Back), Fate/Equip/Reward, and <1s combat."""
    ocr_texts = [str(it.get("text", "")) for it in ocr_items]
    phase = detect_czn_phase(ocr_texts)

    # Track whether Zero System locked after failed click
    if phase == "chaos_branch" and czn_state.get("zero_tried") and history and not history[-1].get("screen_changed", True):
        czn_state["zero_locked"] = True

    zoom_active = czn_state.get("combat_preview_slot") is not None and phase == "general"
    if phase != "combat" and not zoom_active and not (czn_state.get("in_combat") and phase == "general" and len(ocr_items) <= 6):
        czn_state["in_combat"] = False
        czn_state["combat_probes"] = 0

    if phase == "help_popup":
        close_btn = _find_ocr(ocr_items, "close", "confirm", "ok")
        if close_btn and close_btn.get("state") != "XÁM":
            return _mk_act("click_xy", close_btn["x"], close_btn["y"], "Đóng bảng giới thiệu để tiếp tục!", "CZN help_popup: close dialog")
        return _mk_act("click_xy", 920, 120, "Đóng popup hướng dẫn!", "CZN help_popup: click close area")

    act = _advise_fate_reward_equip(phase, config, ocr_items, corner_state, czn_state, history)
    if act is not None:
        return act

    act = _advise_lobby_or_chaos(phase, config, ocr_items, corner_state, czn_state)
    if act is not None:
        return act

    act = _advise_scouting_or_team(phase, config, ocr_items, corner_state, czn_state)
    if act is not None:
        return act

    act = _advise_combat_fast(ocr_items, czn_state, history, config)
    if act is not None:
        return act

    return None


def build_step_guidance(
    playbook: str,
    config: dict[str, Any],
    ocr_items: list[dict[str, Any]],
    scouted_notes: list[str],
    recent_history: list[dict[str, Any]],
    corner_state: str = "",
) -> tuple[str, str]:
    """Return (phase_name, concise Help-informed tactical guidance) for the current frame."""
    ocr_texts = [str(it.get("text", "")) for it in ocr_items]
    if playbook == "hsr":
        hsr_mode = str(config.get("hsr_mode", "simulated_universe"))
        mode_hint = {
            "simulated_universe": "Chế độ Vũ trụ mô phỏng (Simulated Universe): ưu tiên Chúc phúc (Blessings) cùng Vận mệnh & Vật thể lạ hợp đội hình.",
            "endgame": "Chế độ Hồi ức hỗn độn / Kể chuyện hư cấu / Ảo ảnh tận thế: tối ưu vòng xoay Tuyệt kỹ & phá điểm yếu nhanh nhất.",
            "farm": "Chế độ Farm Đài Hoa / Hang Xâm Thực: ưu tiên bật Auto Battle nếu có hoặc xả Chiến kỹ AoE dọn nhanh.",
            "story": "Chế độ Cốt truyện / Khám phá: theo dấu nhiệm vụ chính, nói chuyện hoặc nhặt rương.",
        }.get(hsr_mode, "")
        return (
            "hsr",
            f"PLAYBOOK HONKAI STAR RAIL ({mode_hint}): Quản lý SP (+1 từ Đánh thường Q, -1 từ Chiến kỹ E); "
            "khi Tuyệt kỹ nhân vật sáng hãy bấm phím 1/2/3/4 để chen lượt; ưu tiên đánh phá Thanh Sức Bền (Toughness) đúng hệ.",
        )

    if playbook != "czn":
        return "free", ""

    phase = detect_czn_phase(ocr_texts)
    branch = config.get("branch", "chaos_manifestation")
    world_id = config.get("world", "blue_pot")
    world_name = WORLD_NAMES.get(world_id, "The Blue Pot")
    preset = config.get("preset_team", "keep")
    difficulty = int(config.get("difficulty") or 3)
    scout_skills = bool(config.get("scout_skills", True))
    scout_lobby = bool(config.get("scout_lobby", False))
    already_opened_details = any(
        "details" in str(h.get("reason", "")).lower() or "kỹ năng" in str(h.get("reason", "")).lower() or "combatant" in str(h.get("reason", "")).lower()
        for h in recent_history[-8:]
    )
    already_picked_preset = any(
        "preset" in str(h.get("reason", "")).lower() or "team " in str(h.get("reason", "")).lower()
        for h in recent_history[-8:]
    )
    kits = match_known_kits(ocr_texts + scouted_notes)

    btn_rule = ""
    if phase not in {"character_details", "combatant_list", "locked_popup", "run_info_overlay"}:
        if corner_state == "XÁM":
            btn_rule = " QUY TẮC MÀU: Nút Confirm/Enter góc dưới-phải đang màu XÁM (chưa chọn thẻ/nhân vật/hành tinh — KHÔNG được bấm nút xám, phải chọn mục tiêu trước cho tới khi nó chuyển CAM hoặc TÍM!)."
        elif corner_state in {"CAM", "TÍM"}:
            btn_rule = f" QUY TẮC MÀU: Nút góc dưới-phải đang sáng màu {corner_state} (đã sẵn sàng bấm!)."

    if phase == "run_info_overlay":
        return phase, "CZN OVERLAY: Đang mở nhầm bảng trạng thái Combatants/Partners/Fate; bấm nút [X] góc trên phải (955, 55) để đóng lại."
    if phase == "locked_popup":
        return phase, "CZN LOCKED POPUP: Mục vừa bấm đang khóa; click 'Tap to close the window.' ở dưới giữa (500, 935) để đóng rồi chọn đúng màn đang mở."
    if phase == "lobby":
        if scout_lobby and not scouted_notes and not already_opened_details:
            return phase, "CZN LOBBY SCOUTING: Bấm nút 'Combatants' ở menu bên phải trước để kiểm tra kỹ năng/thẻ các nhân vật rồi mới quay lại bấm 'Chaos'."
        return phase, "CZN LOBBY: Click chính xác chữ/nút 'Chaos' ở menu bên phải (tránh khoảng trống bên trái). Nếu thấy popup thông báo thì đóng hoặc Confirm."
    if phase == "chaos_branch":
        if branch == "zero_system":
            return phase, "CZN MODE SELECT: Tìm 'Zero System' bên phải. Nếu có ổ khóa (locked), KHÔNG bấm kẹt mà chọn 'Chaos Manifestation' bên trái."
        return phase, "CZN MODE SELECT: Click vào thẻ 'Chaos Manifestation' bên trái."
    if phase == "world_select":
        joined_low = " ".join(ocr_texts).lower()
        if "enter" in joined_low and corner_state != "XÁM":
            return phase, f"CZN PLANET READY: Bảng '{world_name}' đã mở; click nút tím 'Enter' ở góc dưới phải (hoặc chọn lại '{world_name}' nếu sai hành tinh).{btn_rule}"
        return phase, f"CZN PLANET: Click trực tiếp hành tinh '{world_name}' trên bản đồ (Twin Star's Shadow giữa-trên, The Blue Pot dưới-trái, City of Mist giữa-dưới).{btn_rule}"
    if phase == "preset_select":
        team_num = {"team1": "Team 1", "team2": "Team 2", "team3": "Team 3"}.get(preset, "Team 1")
        return phase, f"CZN TEAM PRESET: Click nút cam 'Select' ngay dưới '{team_num}', rồi bấm Back_◁ (44,44)."
    if phase == "combatant_list":
        return (
            phase,
            "CZN COMBATANT LIST: Click vào nhân vật hoặc nút 'Details' [ĐEN] dưới-phải để xem Stats/Cards; KHÔNG bấm 'Assign' khi đang [XÁM]; xem xong bấm Back_◁ (44, 44). "
            + CZN_HELP_TOPICS["ui_navigation"],
        )
    if phase == "character_details":
        return (
            phase,
            "CZN DETAILS: Bấm tab 'Cards' bên trái (khoảng x=115, y=352) để đọc bộ thẻ kỹ năng vào 'note' rồi bấm Back_◁ (44, 44). "
            "TUYỆT ĐỐI KHÔNG bấm nút cam 'Promotions' góc dưới phải!",
        )
    if phase == "team_formation":
        steps = []
        if preset in {"team1", "team2", "team3"} and not already_picked_preset:
            steps.append(f"Bấm nút 'Preset' ở góc dưới trái để chọn {preset.upper()}")
        elif scout_skills and not scouted_notes and not already_opened_details:
            steps.append("QUÉT KỸ NĂNG TRƯỚC KHI VÀO TRẬN: Click vào chân dung nhân vật (cột giữa hoặc trái) để mở Combatant List/Details đọc bộ thẻ trước")
        steps.append(f"Chọn số độ khó Difficulty '{difficulty}' ở phía trên phải")
        steps.append("KHÔNG bấm Delegate; chỉ bấm 'Enter' góc dưới phải khi sáng TÍM/CAM.")
        kit_line = (" Đội hình đã biết: " + " | ".join(kits[:2])) if kits else ""
        return phase, "CZN TEAM FORMATION: " + "; ".join(steps) + "." + btn_rule + kit_line
    if phase == "fate_choice":
        joined_low = " ".join(ocr_texts).lower()
        satiety_warn = " PHÁT HIỆN SATIETY: thẻ rác tạo 1 Normal Neutral Card (+20 Faint Memory) — ưu tiên chọn Fate khác hoặc bấm Skip_>| (760, 926) nếu bỏ qua được!" if any(t in joined_low for t in TRAP_FATES) else ""
        return phase, (
            "CZN CHOOSE YOUR FATE: Ưu tiên Cheerful (+1 AP Elite/Boss), Altruism (+1 AP khi rút 3), Brainwash (Draw +DMG), Challenges/Equipment/Xóa bài. "
            "Tránh Satiety (tạo Neutral ngẫu nhiên làm loãng deck + tốn 20 Faint Memory). "
            "Chỉ bấm 'Confirm' khi nút sáng [CAM]; có thể bấm Skip_>| (760, 926) để bỏ qua." + satiety_warn + btn_rule
        )
    if phase == "card_reward":
        kit_line = (" Role team: " + " | ".join(kits[:2])) if kits else ""
        return phase, (
            "CZN CARD REWARD: " + CZN_HELP_TOPICS["faint_memory"] + " "
            "NÊN CHỌN thẻ 0-cost, Draw, +AP, [Retain], [Retrieve], [Initiation], hoặc hợp role. "
            "BẤM 'Skip' nếu thẻ đắt/lạc tông làm loãng combo (VD deck 0-cost của Rin). "
            "Confirm [XÁM] = chưa chọn nhân vật bên phải -> click nhân vật (x~820, y~380/540/700) cho Confirm chuyển [CAM] rồi mới bấm!" + kit_line
        )
    if phase == "equipment":
        return phase, (
            "CZN EQUIPMENT: Vũ khí ATK/Crit/0-cost (RFS-17, Obsidian Sword, Big Game Hunter) cho Striker/Hunter/Ranger; "
            "Giáp/Phụ kiện DEF/Shield/Heal cho Vanguard/Controller. Phải chọn nhân vật bên phải cho Confirm chuyển [CAM]!" + btn_rule
        )
    if phase == "combat":
        kit_line = (" Team: " + " | ".join(k.split(":")[0] + ":" + k.split(":")[1][:65] for k in kits[:3])) if kits else ""
        return phase, CZN_HELP_TOPICS["combat"] + " " + CZN_HELP_TOPICS["keywords"] + kit_line
    if phase == "event_or_map":
        return phase, "CZN MAP/EVENT: " + CZN_HELP_TOPICS["map_nodes"] + " Chỉ bấm Confirm khi sáng [CAM]." + btn_rule
    return phase, "CZN RUN: Chỉ bấm Confirm/Enter khi sáng [CAM]/[TÍM] (không bấm [XÁM]), bấm Back_◁ (44, 44) khi cần thoát menu." + btn_rule


GAME_PROFILES: dict[str, dict[str, Any]] = {
    "fps": {
        "label": "FPS / Bắn súng góc nhìn thứ nhất",
        "title_keywords": (
            "counter-strike", "cs2", "valorant", "apex legends", "overwatch",
            "call of duty", "pubg", "rainbow six", "doom", "halo",
        ),
        "hud_keywords": (
            "ammo", "hp", "armor", "kevlar", "round", "bomb", "spike",
            "headshot", "k/d", "buy", "crosshair", "defuse", "plant",
        ),
        "controls_map": {
            "w/a/s/d": "Di chuyển",
            "space": "Nhảy",
            "r": "Nạp đạn",
            "1/2/3/4": "Đổi vũ khí / Lựu đạn",
            "e": "Tương tác / Gỡ bom",
            "b": "Mở shop mua đồ",
            "click_xy": "Ngắm / Bắn mục tiêu",
        },
        "recommended_keys": ["w", "a", "s", "d", "space", "r", "1", "2", "3", "e", "b"],
        "guidance": "PROFILE FPS: Di chuyển WASD, nạp đạn R, đổi súng 1/2/3, tương tác E, bám crosshair và check góc.",
    },
    "moba": {
        "label": "MOBA / Đấu trường chiến thuật",
        "title_keywords": (
            "league of legends", "dota 2", "liên minh", "arena of valor",
            "liên quân", "mobile legends", "heroes of the storm", "smite",
        ),
        "hud_keywords": (
            "gold", "kda", "mana", "turret", "tower", "dragon", "baron",
            "minion", "recall", "cooldown", "cs ", "inhibitor", "nexus",
        ),
        "controls_map": {
            "q/w/e/r": "Tung kỹ năng Q/W/E và Chiêu cuối R",
            "d/f": "Phép bổ trợ",
            "1/2/3/4/5/6": "Kích hoạt trang bị",
            "b": "Biến về (Recall)",
            "space": "Khóa camera về tướng",
            "right_click_xy": "Di chuyển / Đánh thường",
            "a": "Attack-move",
        },
        "recommended_keys": ["q", "w", "e", "r", "d", "f", "b", "space", "a"],
        "guidance": "PROFILE MOBA: Dùng Q/W/E/R tung chiêu, D/F phép bổ trợ, B biến về hồi máu, right_click_xy để di chuyển/last-hit.",
    },
    "rpg": {
        "label": "RPG / Nhập vai phiêu lưu",
        "title_keywords": (
            "elden ring", "witcher", "cyberpunk", "skyrim", "final fantasy",
            "baldur", "diablo", "path of exile", "persona", "monster hunter",
            "black myth", "dark souls",
        ),
        "hud_keywords": (
            "quest", "exp", "lvl", "level", "stamina", "inventory", "equip",
            "boss", "mp", "hp", "interact", "talk", "skill", "potion",
        ),
        "controls_map": {
            "w/a/s/d": "Di chuyển nhân vật",
            "space": "Né đòn / Nhảy",
            "e/f": "Nói chuyện / Nhặt đồ / Tương tác",
            "q/r": "Kỹ năng / Tuyệt kỹ",
            "i/tab": "Mở túi đồ",
            "m": "Mở bản đồ",
            "1/2/3/4": "Dùng bình hồi phục / ô nhanh",
        },
        "recommended_keys": ["w", "a", "s", "d", "space", "e", "f", "q", "r", "1", "2", "m", "tab"],
        "guidance": "PROFILE RPG: Di chuyển WASD, né Space, tương tác E/F, dùng bình/skill 1..4 và theo dấu Quest.",
    },
    "visual_novel": {
        "label": "Visual Novel / Cốt truyện tương tác",
        "title_keywords": (
            "ren'py", "renpy", "nekopara", "steins;gate", "ace attorney",
            "doki doki", "visual novel", "clannad", "tsukihime", "mahoyo",
        ),
        "hud_keywords": (
            "auto", "skip", "save", "load", "backlog", "history",
            "choice", "hide", "q.save", "q.load", "dialogue",
        ),
        "controls_map": {
            "space/enter": "Qua câu thoại tiếp theo",
            "a": "Bật/tắt Auto-read",
            "s": "Quick Save",
            "l": "Quick Load",
            "esc": "Mở menu hệ thống",
            "click_xy": "Chọn nhánh hội thoại / nút UI",
        },
        "recommended_keys": ["space", "enter", "a", "s", "l", "esc"],
        "guidance": "PROFILE VISUAL NOVEL: Bấm Space/Enter hoặc click_xy để đọc thoại, chú ý chọn đáp án nhánh cốt truyện khi hiện Choice.",
    },
    "gacha": {
        "label": "Gacha / Turn-based & Chiến thuật thẻ bài",
        "title_keywords": (
            "chaos zero nightmare", "honkai: star rail", "star rail", "genshin impact",
            "zenless zone zero", "arknights", "blue archive", "nikke",
            "fate/grand order", "wuthering waves", "epic seven", "reverse: 1999",
        ),
        "hud_keywords": (
            "pull", "gacha", "warp", "wish", "banner", "trailblaze", "sanity",
            "tenacity", "ego", "ap", "sp", "auto battle", "combatant", "ultimate",
        ),
        "controls_map": {
            "1/2/3/4/5/0": "Chọn thẻ kỹ năng / Tuyệt kỹ",
            "e": "Kết thúc lượt / Chiến kỹ",
            "r": "Bật/tắt Auto Battle",
            "tab": "Đổi mục tiêu",
            "esc": "Quay lại / Hủy chọn",
            "click_xy": "Chọn thẻ, node bản đồ, nút Confirm",
        },
        "recommended_keys": ["1", "2", "3", "4", "e", "r", "tab", "esc", "space"],
        "guidance": "PROFILE GACHA: Quản lý tài nguyên lượt (AP/SP/Energy), ưu tiên nút Confirm/Enter sáng màu và dùng 1..4 hoặc click_xy chọn thẻ.",
    },
}


def detect_game_profile(
    window_title: str = "",
    ocr_items: list[dict[str, Any]] | list[str] | None = None,
    goal: str = "",
) -> dict[str, Any]:
    """Detect game genre (FPS/MOBA/RPG/Visual Novel/Gacha) from window title + OCR HUD and map controls."""
    title_low = (window_title or "").lower()
    goal_low = (goal or "").lower()
    ocr_texts: list[str] = []
    for item in ocr_items or []:
        if isinstance(item, dict):
            txt = str(item.get("text", "")).strip()
        else:
            txt = str(item).strip()
        if txt:
            ocr_texts.append(txt.lower())
    hud_blob = " ".join(ocr_texts)

    best_genre = "generic"
    best_score = 0
    best_signals: list[str] = []

    for genre, spec in GAME_PROFILES.items():
        score = 0
        signals: list[str] = []
        for kw in spec["title_keywords"]:
            if kw in title_low or kw in goal_low:
                score += 4
                signals.append(f"title:{kw}")
        for kw in spec["hud_keywords"]:
            if kw in hud_blob:
                score += 1
                signals.append(f"hud:{kw}")
        if score > best_score:
            best_score = score
            best_genre = genre
            best_signals = signals[:6]

    if best_genre == "generic" or best_score == 0:
        return {
            "genre": "generic",
            "label": "Game tổng quát",
            "confidence": 0.2,
            "matched_signals": [],
            "controls_map": {
                "click_xy": "Tương tác nút / đối tượng trên màn hình",
                "w/a/s/d": "Di chuyển",
                "space/enter": "Xác nhận / Nhảy",
                "esc": "Menu / Quay lại",
            },
            "recommended_keys": ["w", "a", "s", "d", "space", "enter", "esc"],
            "guidance": "PROFILE GENERIC: Đọc kỹ nhãn OCR và lưới tọa độ 0..1000 trước khi click hoặc nhấn phím.",
        }

    spec = GAME_PROFILES[best_genre]
    confidence = round(min(0.98, 0.35 + best_score * 0.12), 2)
    return {
        "genre": best_genre,
        "label": spec["label"],
        "confidence": confidence,
        "matched_signals": best_signals,
        "controls_map": dict(spec["controls_map"]),
        "recommended_keys": list(spec["recommended_keys"]),
        "guidance": spec["guidance"],
    }
