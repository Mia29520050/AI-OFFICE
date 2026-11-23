from __future__ import annotations

import asyncio
import sqlite3
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import browser  # noqa: E402
import computer  # noqa: E402
import game_agent  # noqa: E402
import game_playbooks  # noqa: E402
import launcher  # noqa: E402
import model_provider  # noqa: E402
import ocr_helper  # noqa: E402
import vtuber_models  # noqa: E402

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def test_launcher_timeout_handles_offline_ollama() -> None:
    src = Path(launcher.__file__).read_text(encoding="utf-8")
    assert "timeout=5" in src or "timeout=4" in src
    assert "ensure_local_ollama" in src
    assert hasattr(computer, "ensure_dpi_aware")


def test_real_window_picker_and_live2d_ui() -> None:
    html = (ROOT / "app" / "ui" / "index.html").read_text(encoding="utf-8")
    assert 'id="game-preset"' not in html
    assert 'id="game-open-sandbox"' not in html
    assert "Đi chế độ Chaos bằng đội hình Preset Team 1 có sẵn" not in html
    assert 'id="game-czn-panel"' in html and 'id="game-playbook"' in html
    assert 'id="game-window-select"' in html
    assert 'id="vtuber-model-select"' in html and 'id="vtuber-live2d-box"' in html
    assert 'id="vtuber-fit-select"' in html and 'id="vtuber-expr-bar"' in html
    assert (ROOT / "app" / "ui" / "assets" / "live2d" / "live2dcubismcore.min.js").is_file()
    assert (ROOT / "app" / "ui" / "assets" / "live2d" / "stage-controller.mjs").is_file()
    assert hasattr(computer, "_is_window_cloaked")
    assert "Program Manager" in computer._SHELL_WINDOW_TITLES


def test_visual_diff_and_self_token_check() -> None:
    import io, os
    buf_a, buf_b = io.BytesIO(), io.BytesIO()
    im1 = Image.new("RGB", (120, 80), (10, 20, 30))
    im2 = Image.new("RGB", (120, 80), (200, 210, 220))
    im1.save(buf_a, format="JPEG")
    im2.save(buf_b, format="JPEG")
    assert game_agent._mean_image_diff(buf_a.getvalue(), buf_a.getvalue()) == 0.0
    assert game_agent._mean_image_diff(buf_a.getvalue(), buf_b.getvalue()) > 10.0
    # Small localized button highlight (~5% of frame) should still trigger changed_pct >= 0.8 even if mean_diff < 0.8
    im3 = im1.copy()
    from PIL import ImageDraw
    ImageDraw.Draw(im3).rectangle([80, 50, 105, 65], fill=(240, 240, 240))
    buf_c = io.BytesIO()
    im3.save(buf_c, format="JPEG")
    md, pct = game_agent._image_change_metrics(buf_a.getvalue(), buf_c.getvalue())
    assert pct >= 0.8, f"Expected changed_pct >= 0.8, got {pct} (mean={md})"
    assert computer._is_process_elevated_blocked(os.getpid()) is False


def test_model_provider_local_default_and_cloud_masking() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"

        def connect():
            c = sqlite3.connect(db_path)
            c.row_factory = sqlite3.Row
            return c

        mgr = model_provider.ModelProviderManager(connect, asyncio.Semaphore(1))
        initial = mgr.get_settings(include_secret=False)
        assert initial["provider"] == "local"
        assert initial["cloud_enabled"] is False
        assert initial["cloud_api_key_set"] is False
        assert "cloud_api_key" not in initial

        # Incomplete cloud config must fail validation
        try:
            mgr.update_settings(model_provider.ModelSettingsUpdate(provider="cloud", cloud_enabled=True))
            raise AssertionError("Expected HTTPException when cloud API key is missing")
        except HTTPException as exc:
            assert exc.status_code == 400

        updated = mgr.update_settings(model_provider.ModelSettingsUpdate(
            provider="cloud",
            cloud_enabled=True,
            cloud_base_url="https://api.example.com/v1",
            cloud_model="gpt-4o-mini",
            cloud_api_key="sk-secret-key-12345",
        ))
        assert updated["provider"] == "cloud"
        assert updated["cloud_api_key_set"] is True
        assert "sk-secret-key-12345" not in str(updated)
        assert mgr.active_route()["mode"] == "cloud"

        # OpenAI multimodal formatting check
        conv = mgr._to_openai_messages([{"role": "user", "content": "Look", "images": ["ABCD"]}])
        assert conv[0]["content"][1]["type"] == "image_url"
        assert conv[0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,ABCD")


def test_computer_norm_mapping_clamped_and_grid() -> None:
    rect = {"left": 100, "top": 200, "right": 900, "bottom": 800, "width": 800, "height": 600}
    x0, y0 = computer._map_norm_to_window(rect, -50, -50)
    x1, y1 = computer._map_norm_to_window(rect, 1500, 1500)
    xc, yc = computer._map_norm_to_window(rect, 500, 500)
    assert rect["left"] < x0 < xc < x1 < rect["right"]
    assert rect["top"] < y0 < yc < y1 < rect["bottom"]
    assert "win" not in computer.ALLOWED_KEYS
    assert "space" in computer.ALLOWED_KEYS and "up" in computer.ALLOWED_KEYS

    img = Image.new("RGB", (640, 480), (15, 20, 30))
    gridded = computer._add_grid_overlay(img)
    assert gridded.size == (640, 480)
    assert list(gridded.getdata()) != list(img.getdata())


def test_game_manager_validation_and_safety() -> None:
    mgr = game_agent.GameSessionManager()
    # Clamping coordinates and rejecting unsafe keys
    valid = mgr._validate_plan({
        "mood": "excited",
        "comment": "Chém thôi!",
        "action": "click_xy",
        "x": 1200,
        "y": -20,
        "reason": "Attack Slime",
    }, "desktop")
    assert valid["x"] == 1000 and valid["y"] == 0 and valid["mood"] == "excited"

    try:
        mgr._validate_plan({"action": "key_press", "key": "lwin"}, "desktop")
        raise AssertionError("Expected ValueError for disallowed key")
    except ValueError:
        pass

    try:
        mgr._validate_plan({"action": "click_xy", "x": 500, "y": 500, "reason": "Enter password"}, "desktop")
        raise AssertionError("Expected ValueError for blocked term")
    except ValueError:
        pass


def test_browser_snapshot_js_fixes() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=EDGE, args=["--disable-gpu"])
        page = b.new_page(viewport={"width": 1024, "height": 720})
        page.set_content("""
        <html><body>
          <button id="b1">Start</button>
          <div role="button" id="b2">Card 1</div>
          <button type="button" title="Jump" id="b3"></button>
          <input id="i1" placeholder="Type move">
          <form><button id="f1">Submit</button></form>
          <canvas id="c1" width="200" height="100"></canvas>
        </body></html>
        """)
        snap = page.evaluate(browser.SNAPSHOT_JS)
        ctrls = snap["controls"]
        assert snap["has_canvas"] is True
        b1 = next(c for c in ctrls if c["text"] == "Start")
        assert b1["type"] == "button" and b1["in_form"] is False and "x" in b1 and "y" in b1
        b2 = next(c for c in ctrls if c["text"] == "Card 1")
        assert b2["role"] == "button" and b2["type"] == "button"
        b3 = next(c for c in ctrls if c["text"] == "Jump")
        assert b3["text"] == "Jump"
        i1 = next(c for c in ctrls if c["placeholder"] == "Type move")
        assert i1["type"] == "text"
        f1 = next(c for c in ctrls if c["text"] == "Submit")
        assert f1["in_form"] is True and f1["type"] == "submit"
        b.close()


def test_browser_url_guards_preserve_security_while_allowing_sandbox() -> None:
    try:
        browser._validate_url("http://127.0.0.1:8765/", allow_opted_local=False)
        raise AssertionError("127.0.0.1 must be blocked when allow_opted_local=False")
    except HTTPException as exc:
        assert exc.status_code == 403

    try:
        browser._validate_url("http://192.168.1.10/", allow_opted_local=True)
        raise AssertionError("LAN IP must stay blocked even when allow_opted_local=True")
    except HTTPException as exc:
        assert exc.status_code == 403

    # /sandbox-game allowed when opted in, but /api/ on 8765 remains blocked
    ok_url = browser._validate_url("http://127.0.0.1:8765/sandbox-game", allow_opted_local=True)
    assert ok_url.endswith("/sandbox-game")
    try:
        browser._validate_url("http://127.0.0.1:8765/api/tasks", allow_opted_local=True)
        raise AssertionError("Internal /api/ on 8765 must stay blocked")
    except HTTPException as exc:
        assert exc.status_code == 403


def test_launcher_allow_elevated_opt_in() -> None:
    bat = (ROOT / "Start-AI-Office-Admin.bat").read_text(encoding="utf-8")
    assert "--allow-elevated" in bat and "-Verb RunAs" in bat

    orig_argv = sys.argv[:]
    orig_vals = {
        "set_id": launcher.set_app_user_model_id,
        "init_db": launcher.init_db,
        "ollama": launcher.ensure_local_ollama,
        "running": launcher.server_is_running,
        "webview": launcher.webview,
    }
    calls: list[str] = []

    class FakeWebview:
        @staticmethod
        def create_window(*args, **kwargs):
            calls.append("create_window")
            return object()

        @staticmethod
        def start(*args, **kwargs):
            calls.append("webview_start")

    try:
        launcher.set_app_user_model_id = lambda: calls.append("set_id") or True
        launcher.init_db = lambda: calls.append("init_db")
        launcher.ensure_local_ollama = lambda: None
        launcher.server_is_running = lambda: True
        launcher.webview = FakeWebview

        sys.argv = ["app/launcher.py"]
        launcher.main()
        # Direct execution without flashing cmd loops
        assert "create_window" in calls and "webview_start" in calls

        calls.clear()
        sys.argv = ["app/launcher.py", "--allow-elevated"]
        launcher.main()
        assert "create_window" in calls and "webview_start" in calls
    finally:
        sys.argv = orig_argv
        launcher.set_app_user_model_id = orig_vals["set_id"]
        launcher.init_db = orig_vals["init_db"]
        launcher.ensure_local_ollama = orig_vals["ollama"]
        launcher.server_is_running = orig_vals["running"]
        launcher.webview = orig_vals["webview"]


def test_copilot_mode_ui_and_non_invasive_loop() -> None:
    import json

    html = (ROOT / "app" / "ui" / "index.html").read_text(encoding="utf-8")
    assert 'value="copilot"' in html and 'id="game-drag-dot"' in html

    req = game_agent.GameSessionStartRequest(
        source="desktop",
        target_handle=12345,
        goal="Observe Chaos team 1",
        mode="copilot",
        max_steps=1,
        interval_ms=250,
    )
    assert req.mode == "copilot"

    with tempfile.TemporaryDirectory() as tmp:
        preview = Path(tmp) / "game_preview.jpg"
        Image.new("RGB", (200, 120), (30, 40, 50)).save(preview, format="JPEG")

        mgr = game_agent.GameSessionManager()
        mgr._preview_path = preview

        focus_called: list[int] = []
        exec_called: list[str] = []

        orig_focus = game_agent.focus_window
        orig_capture = game_agent.capture_window

        class FakeMain:
            @staticmethod
            async def ollama_chat(*args, **kwargs):
                return json.dumps({
                    "mood": "excited",
                    "comment": "Kéo thẻ bài lên Slime nha!",
                    "action": "drag_xy",
                    "x": 320,
                    "y": 820,
                    "x2": 510,
                    "y2": 420,
                    "reason": "Play attack card",
                })

        async def run_case():
            mgr._execute_action = lambda *a, **kw: exec_called.append("exec")  # type: ignore[assignment]
            await mgr._run_loop(FakeMain(), req, {"handle": 12345, "process_id": 999, "title": "Chaos Zero Nightmare"}, "sess1")

        try:
            game_agent.focus_window = lambda h: focus_called.append(int(h)) or {}
            game_agent.capture_window = lambda *a, **kw: {"ai_path": str(preview)}
            asyncio.run(run_case())
        finally:
            game_agent.focus_window = orig_focus
            game_agent.capture_window = orig_capture

        snap = mgr.snapshot_state()
        assert focus_called == []
        assert exec_called == []
        assert snap["status"] == "completed", f"Expected completed, got {snap}"
        assert len(snap["history"]) == 1
        assert snap["history"][0]["copilot"] is True
        assert snap["history"][0]["executed"] is False
        assert snap["history"][0]["action"] == "drag_xy"


def test_vtuber_models_manifest_import_and_traversal_guard() -> None:
    import json
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmp:
        root_tmp = Path(tmp)
        data_dir = root_tmp / "data"
        src_dir = root_tmp / "src_avatar"
        src_dir.mkdir(parents=True)
        (src_dir / "Demo.moc3").write_bytes(b"MOC3\x05\x00\x00\x00")
        (src_dir / "Demo.model3.json").write_text(json.dumps({
            "Version": 3,
            "FileReferences": {"Moc": "Demo.moc3", "Textures": []},
        }), encoding="utf-8")
        (src_dir / "xx.exp3.json").write_text(json.dumps({
            "Type": "Live2D Expression",
            "Parameters": [{"Id": "Param59", "Value": 30, "Blend": "Add"}],
        }), encoding="utf-8")
        (src_dir / "Idle0.motion3.json").write_text('{"Version":3}', encoding="utf-8")
        (data_dir / "secret.txt").parent.mkdir(parents=True, exist_ok=True)
        (data_dir / "secret.txt").write_text("TOP_SECRET", encoding="utf-8")

        test_app = FastAPI()
        # Temporarily avoid copying F:\Download\魔女 into temp test dir
        orig_candidates = list(vtuber_models.DEFAULT_IMPORT_CANDIDATES)
        vtuber_models.DEFAULT_IMPORT_CANDIDATES.clear()
        try:
            vtuber_models.register_routes(test_app, data_dir)
        finally:
            vtuber_models.DEFAULT_IMPORT_CANDIDATES[:] = orig_candidates

        client = TestClient(test_app)
        res = client.post("/api/vtuber/models/import", json={"path": str(src_dir), "name": "DemoWitch"})
        assert res.status_code == 200, res.text
        model_id = res.json()["model"]["id"]
        assert model_id == "demowitch"

        listing = client.get("/api/vtuber/models").json()["models"]
        demo = next(m for m in listing if m["id"] == model_id)
        assert any(e["id"] == "xx" for e in demo["expressions"])
        assert demo["mood_map"].get("excited") == "xx"
        assert any(m["id"] == "svg-fallback" for m in listing)

        manifest = client.get(f"/api/vtuber/model-files/{model_id}/manifest.model3.json").json()
        assert any(e["Name"] == "xx" for e in manifest["FileReferences"]["Expressions"])
        assert manifest["FileReferences"]["Motions"]["Idle"][0]["File"] == "Idle0.motion3.json"

        # Path traversal guard must block reading parent data/secret.txt
        trav = client.get(f"/api/vtuber/model-files/{model_id}/../secret.txt")
        assert trav.status_code in {400, 404}
        bad_id = client.get("/api/vtuber/model-files/..bad/manifest.model3.json")
        assert bad_id.status_code == 400


def test_windows_ocr_worker_detects_labels_accurately() -> None:
    from PIL import ImageDraw, ImageFont

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "ocr_sample.png"
        im = Image.new("RGB", (1000, 500), (14, 18, 28))
        draw = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 36)
        except Exception:
            font = ImageFont.load_default()
        draw.text((880, 260), "Chaos", fill=(255, 255, 255), font=font, anchor="mm")
        draw.text((840, 440), "Enter", fill=(255, 255, 255), font=font, anchor="mm")
        im.save(p)

        res = ocr_helper.extract_ocr_labels(p, max_items=16)
        ocr_helper.OCR_WORKER.close()
        assert res["ok"] is True, res
        items = res["items"]
        chaos = next((it for it in items if "chaos" in it["text"].lower()), None)
        enter = next((it for it in items if "enter" in it["text"].lower()), None)
        assert chaos is not None and abs(chaos["x"] - 880) <= 30 and abs(chaos["y"] - 520) <= 30, items
        assert enter is not None and abs(enter["x"] - 840) <= 30 and abs(enter["y"] - 880) <= 30, items


def test_button_color_state_classifier() -> None:
    from PIL import ImageDraw

    with tempfile.TemporaryDirectory() as tmp:
        for rgb, label, expected in [
            ((235, 130, 35), "Confirm", "CAM"),
            ((135, 95, 210), "Enter", "TÍM"),
            ((185, 188, 194), "Assign", "XÁM"),
            ((42, 44, 50), "Details", "ĐEN"),
        ]:
            img_path = Path(tmp) / f"btn_{label}_{expected}.jpg"
            im = Image.new("RGB", (1000, 1000), (14, 16, 24))
            ImageDraw.Draw(im).rectangle([800, 880, 980, 965], fill=rgb)
            im.save(img_path, format="JPEG", quality=95)
            items, corner = ocr_helper.annotate_button_colors(img_path, [{"text": label, "x": 890, "y": 922}])
            assert items[0].get("state") == expected, f"Expected {expected}, got {items[0]}"
            assert corner == expected, f"Expected corner {expected}, got {corner}"


def test_czn_and_hsr_playbook_phase_routing() -> None:
    cfg = {"branch": "chaos_manifestation", "world": "blue_pot", "preset_team": "team1", "difficulty": 3, "scout_skills": True}

    def ocr(words):
        return [{"text": w, "x": 500, "y": 500} for w in words]

    p_lobby, g_lobby = game_playbooks.build_step_guidance("czn", cfg, ocr(["Story", "Sortie", "Chaos"]), [], [])
    assert p_lobby == "lobby" and "Chaos" in g_lobby
    p_lobby_scout, g_lobby_scout = game_playbooks.build_step_guidance("czn", {**cfg, "scout_lobby": True}, ocr(["Story", "Chaos", "Combatants"]), [], [])
    assert p_lobby_scout == "lobby" and "Combatants" in g_lobby_scout

    p_branch, g_branch = game_playbooks.build_step_guidance("czn", cfg, ocr(["Chaos Manifestation", "Zero System"]), [], [])
    assert p_branch == "chaos_branch" and "Chaos Manifestation" in g_branch

    p_world, g_world = game_playbooks.build_step_guidance("czn", cfg, ocr(["Twin Star's Shadow", "The Blue Pot", "City of Mist", "Enter"]), [], [], corner_state="TÍM")
    assert p_world == "world_select" and "The Blue Pot" in g_world and "Enter" in g_world

    p_world_gray, g_world_gray = game_playbooks.build_step_guidance("czn", cfg, ocr(["The Blue Pot", "Enter"]), [], [], corner_state="XÁM")
    assert p_world_gray == "world_select" and "KHÔNG được bấm nút xám" in g_world_gray

    p_team, g_team = game_playbooks.build_step_guidance("czn", {**cfg, "preset_team": "keep"}, ocr(["Team Formation", "Difficulty", "Enter"]), [], [])
    assert p_team == "team_formation" and "QUÉT KỸ NĂNG" in g_team and "Difficulty '3'" in g_team

    p_det, g_det = game_playbooks.build_step_guidance("czn", cfg, ocr(["Stats", "Cards", "Partners", "Save Data", "Promotions"]), [], [], corner_state="CAM")
    assert p_det == "character_details" and "Cards" in g_det and "Promotions" in g_det

    p_list, g_list = game_playbooks.build_step_guidance("czn", cfg, ocr(["Combatant List", "Quick Formation", "Details", "Assign"]), [], [], corner_state="XÁM")
    assert p_list == "combatant_list" and "Details" in g_list and "44, 44" in g_list

    p_fate, g_fate = game_playbooks.build_step_guidance("czn", cfg, ocr(["Choose your Fate", "Satiety", "Confirm"]), [], [], corner_state="CAM")
    assert p_fate == "fate_choice" and "Satiety" in g_fate and "Faint Memory" in g_fate and "CAM" in g_fate

    p_card, g_card = game_playbooks.build_step_guidance("czn", cfg, ocr(["Card Reward", "Select the combatant", "Rin", "Skip"]), [], [])
    assert p_card == "card_reward" and "Skip" in g_card and "Rin" in g_card and "faint memory" in g_card.lower()

    p_eq, _ = game_playbooks.build_step_guidance("czn", cfg, ocr(["Equipment", "Extract", "Confirm"]), [], [])
    assert p_eq == "equipment"

    p_cmb, g_cmb = game_playbooks.build_step_guidance("czn", cfg, ocr(["End Turn", "Mika", "Stress"]), [], [])
    assert p_cmb == "combat" and "3 AP" in g_cmb and "Action Count" in g_cmb and "Tenacity" in g_cmb and "Mental Breakdown" in g_cmb

    matched = game_playbooks.match_known_kits(["Chizuru", "Cassius", "Tiphera"])
    assert len(matched) == 3

    summary = game_playbooks.get_czn_knowledge_summary()
    assert summary["combatants_trained"] >= 35 and summary["help_topics_trained"] >= 5

    p_hsr, g_hsr = game_playbooks.build_step_guidance("hsr", {}, [], [], [])
    assert p_hsr == "hsr" and "SP" in g_hsr


def test_czn_smart_router_and_guardrails() -> None:
    cfg = {"branch": "chaos_manifestation", "world": "blue_pot", "preset_team": "keep", "difficulty": 3, "scout_skills": True, "scout_lobby": True}
    state: dict = {}

    # 1. Combatant List: prefers active Details[ĐEN] over disabled Assign[XÁM], then backs out via Back ◁ (44, 44)
    list_ocr = [
        {"text": "Combatant List", "x": 200, "y": 48},
        {"text": "Quick Formation", "x": 600, "y": 48},
        {"text": "Details", "x": 635, "y": 922, "state": "ĐEN"},
        {"text": "Assign", "x": 865, "y": 922, "state": "XÁM"},
    ]
    a1 = game_playbooks.advise_czn_action(cfg, list_ocr, "XÁM", state, [])
    assert a1 is not None and (a1["x"], a1["y"]) == (635, 922)

    # 2. Character Details (Tiphera Stats -> Cards -> Portrait Switch -> Back ◁)
    det_stats = [
        {"text": "Details I", "x": 137, "y": 48},
        {"text": "Stats", "x": 122, "y": 259},
        {"text": "• Cards", "x": 115, "y": 352},
        {"text": "Potential", "x": 135, "y": 631},
        {"text": "Tiphera", "x": 770, "y": 172},
        {"text": "Attack", "x": 759, "y": 378},
        {"text": "Critical Chance", "x": 789, "y": 520},
        {"text": "Promotions", "x": 862, "y": 922, "state": "CAM"},
    ]
    a2 = game_playbooks.advise_czn_action(cfg, det_stats, "CAM", state, [])
    assert a2 is not None and (a2["x"], a2["y"]) == (115, 352), a2

    det_cards_1 = [
        {"text": "Details", "x": 137, "y": 48},
        {"text": "• Cards", "x": 115, "y": 352},
        {"text": "Potential", "x": 135, "y": 631},
        {"text": "Tiphera", "x": 770, "y": 172},
        {"text": "Creation", "x": 450, "y": 420},
    ]
    note1 = game_playbooks.extract_visible_czn_scout_note("character_details", det_cards_1)
    assert "Tiphera" in note1 and "Creation" in note1
    a3 = game_playbooks.advise_czn_action(cfg, det_cards_1, "", state, [])
    assert a3 is not None and a3["x"] == 42 and a3["y"] in {152, 252, 358}, a3

    det_cards_2 = [
        {"text": "Details", "x": 137, "y": 48},
        {"text": "• Cards", "x": 115, "y": 352},
        {"text": "Potential", "x": 135, "y": 631},
        {"text": "Mika", "x": 770, "y": 172},
        {"text": "Source of Water", "x": 460, "y": 420},
    ]
    a4 = game_playbooks.advise_czn_action(cfg, det_cards_2, "", state, [])
    assert a4 is not None and (a4["x"], a4["y"]) == (44, 44) and state["details_done"] is True

    # Exiting Combatant List once details_done=True clicks Back ◁ (44, 44)
    a5 = game_playbooks.advise_czn_action(cfg, list_ocr, "XÁM", state, [])
    assert a5 is not None and (a5["x"], a5["y"]) == (44, 44)

    # 3. Runtime Guardrails against [XÁM], Promotions, and 2-step stall loops
    req_czn = game_agent.GameSessionStartRequest(source="desktop", playbook="czn", goal="Đi Chaos")
    mgr = game_agent.GAME_MANAGER
    # Trying to click disabled Confirm[XÁM] in Card Reward redirects to combatant slot
    g1 = mgr._guard_vlm_action(
        {"action": "click_xy", "x": 890, "y": 922, "x2": 890, "y2": 922, "comment": "c", "reason": "r"},
        req_czn,
        "card_reward",
        [{"text": "Confirm", "x": 890, "y": 922, "state": "XÁM"}],
        [],
    )
    assert (g1["x"], g1["y"]) == (820, 380)
    # Trying to click Promotions on Character Details redirects to Back ◁ (44, 44)
    g2 = mgr._guard_vlm_action(
        {"action": "click_xy", "x": 862, "y": 922, "x2": 862, "y2": 922, "comment": "c", "reason": "r"},
        req_czn,
        "character_details",
        [{"text": "Promotions", "x": 862, "y": 922, "state": "CAM"}],
        [],
    )
    assert (g2["x"], g2["y"]) == (44, 44)
    # Two failed Fate skip clicks break stall by hitting Confirm[CAM]
    g3 = mgr._guard_vlm_action(
        {"action": "click_xy", "x": 760, "y": 926, "x2": 760, "y2": 926, "comment": "c", "reason": "r"},
        req_czn,
        "fate_choice",
        [{"text": "Confirm", "x": 890, "y": 922, "state": "CAM"}],
        [{"x": 760, "y": 926, "screen_changed": False}, {"x": 760, "y": 926, "screen_changed": False}],
    )
    assert (g3["x"], g3["y"]) == (890, 922)


def test_czn_map_bugfixes_and_fast_combat() -> None:
    # 1. Locked popup with "Clear Story Act I" must NOT misclassify as lobby
    locked_ocr = [
        {"text": "Content locked", "x": 501, "y": 448},
        {"text": "Clear Story Act I - Chapter 4 #05 [Swamp of Judgment]", "x": 429, "y": 562},
        {"text": "Tap to close the window.", "x": 501, "y": 938},
    ]
    assert game_playbooks.detect_czn_phase([it["text"] for it in locked_ocr]) == "locked_popup"
    act_lock = game_playbooks.advise_czn_action({"world": "blue_pot"}, locked_ocr, "", {}, [])
    assert act_lock is not None and (act_lock["x"], act_lock["y"]) == (501, 938)

    # 2. World Select with "Content Introduction" & "City of Mist" at x=725 stays world_select (never help_popup / Unconfirmed Chaos)
    world_ocr = [
        {"text": "Chaos Manifestation", "x": 180, "y": 48},
        {"text": "Content Introduction", "x": 885, "y": 130},
        {"text": "Twin Star's Shadow", "x": 550, "y": 310},
        {"text": "Unconfirmed Chaos", "x": 910, "y": 320},
        {"text": "The Blue Pot", "x": 315, "y": 675},
        {"text": "City of Mist", "x": 725, "y": 675},
    ]
    assert game_playbooks.detect_czn_phase([it["text"] for it in world_ocr]) == "world_select"
    a_city = game_playbooks.advise_czn_action({"world": "city_of_mist"}, world_ocr, "", {}, [])
    assert a_city is not None and a_city["x"] == 650 and a_city["y"] == 675
    a_blue = game_playbooks.advise_czn_action({"world": "blue_pot"}, world_ocr, "", {}, [])
    assert a_blue is not None and a_blue["x"] == 240 and a_blue["y"] == 675

    # 3. Team Formation containing "The Blue Pot" in top-right header must NOT misclassify as world_select
    team_ocr = [
        {"text": "Team Formation", "x": 160, "y": 48},
        {"text": "The Blue Pot", "x": 860, "y": 170},
        {"text": "Difficulty", "x": 740, "y": 240},
        {"text": "3", "x": 740, "y": 295},
        {"text": "Preset", "x": 120, "y": 910},
        {"text": "Enter", "x": 900, "y": 920, "state": "TÍM"},
    ]
    assert game_playbooks.detect_czn_phase([it["text"] for it in team_ocr]) == "team_formation"

    # 4. Fast <1s combat engine fallback (drag_xy when combat_keyboard=False): Lead card beats Finale; 0/3 AP clicks End Turn; cutscene returns wait
    cstate: dict = {}
    combat_ocr = [
        {"text": "2/3", "x": 180, "y": 730},
        {"text": "Lead Strike", "x": 340, "y": 850},
        {"text": "Finale Slash", "x": 560, "y": 850},
        {"text": "Dark Slime", "x": 660, "y": 410},
        {"text": "End Turn", "x": 910, "y": 880, "state": "CAM"},
    ]
    a_play = game_playbooks.advise_czn_action({"combat_keyboard": False}, combat_ocr, "CAM", cstate, [])
    assert a_play is not None and a_play["action"] == "drag_xy" and a_play["x"] == 340 and a_play["fast_combat"] is True
    assert a_play["x2"] == 660 and 270 <= a_play["y2"] <= 460

    no_ap_ocr = [
        {"text": "0/3", "x": 180, "y": 730},
        {"text": "Heavy Blow", "x": 450, "y": 850},
        {"text": "End Turn", "x": 910, "y": 880, "state": "CAM"},
    ]
    a_end = game_playbooks.advise_czn_action({"combat_keyboard": False}, no_ap_ocr, "CAM", cstate, [])
    assert a_end is not None and a_end["action"] == "click_xy" and (a_end["x"], a_end["y"]) == (910, 880)

    a_anim = game_playbooks.advise_czn_action({"combat_keyboard": False}, [{"text": "99", "x": 650, "y": 380}], "", cstate, [])
    assert a_anim is not None and a_anim["action"] == "wait" and a_anim["fast_combat"] is True


def test_czn_keyboard_card_preview_and_targets() -> None:
    kb_state: dict = {}
    hist: list = []
    base_hud = [
        {"text": "2/3", "x": 180, "y": 730},
        {"text": "End Turn", "x": 910, "y": 880, "state": "CAM"},
    ]

    # Step 1: Press '1' to inspect first card
    k1 = game_playbooks.advise_czn_action({}, base_hud, "CAM", kb_state, hist)
    assert k1 is not None and k1["action"] == "key_press" and k1["key"] == "1"
    hist.append({"action": "key_press", "key": "1", "screen_changed": True})

    # Step 2: Card #1 zoomed text is Curse -> press 'esc' to cancel
    curse_zoom = base_hud + [{"text": "Wound Curse Cannot be played", "x": 500, "y": 500}]
    k2 = game_playbooks.advise_czn_action({}, curse_zoom, "CAM", kb_state, hist)
    assert k2 is not None and k2["action"] == "key_press" and k2["key"] == "esc"
    hist.append({"action": "key_press", "key": "esc", "screen_changed": True})

    # Step 3: Press '2' to inspect second card
    k3 = game_playbooks.advise_czn_action({}, base_hud, "CAM", kb_state, hist)
    assert k3 is not None and k3["action"] == "key_press" and k3["key"] == "2"
    hist.append({"action": "key_press", "key": "2", "screen_changed": True})

    # Step 4: Card #2 is targeted Attack with urgent enemy on RIGHT (even if End Turn covered during zoom) -> press 'right' then 'enter'
    atk_zoom = [
        {"text": "2/3", "x": 180, "y": 730},
        {"text": "Heavy Slash", "x": 500, "y": 420},
        {"text": "Cost 1", "x": 420, "y": 380},
        {"text": "Deal 120% Damage", "x": 500, "y": 540},
        {"text": "1 enemy", "x": 500, "y": 580},
        {"text": "Minion", "x": 460, "y": 320},
        {"text": "Boss Break 1", "x": 790, "y": 310},
    ]
    k4 = game_playbooks.advise_czn_action({}, atk_zoom, "", kb_state, hist)
    assert k4 is not None and k4["action"] == "key_press" and k4["key"] == "right"
    hist.append({"action": "key_press", "key": "right", "screen_changed": True})

    k5 = game_playbooks.advise_czn_action({}, atk_zoom, "", kb_state, hist)
    assert k5 is not None and k5["action"] == "key_press" and k5["key"] == "enter"
    hist.append({"action": "key_press", "key": "enter", "screen_changed": True})

    # Step 5: When key '1' fails (out of slots after already zooming cards) -> End Turn via official key 'e'
    end_hist = hist + [
        {"action": "key_press", "key": "1", "screen_changed": False},
        {"action": "key_press", "key": "2", "screen_changed": False},
    ]
    kb_end_state = {"combat_zoomed_ok": True, "combat_key_fails": 1}
    k_end = game_playbooks.advise_czn_action({}, base_hud, "CAM", kb_end_state, [end_hist[-1]])
    assert k_end is not None and k_end["action"] == "key_press" and k_end["key"] == "e"

    # Step 6: After failing key '1' twice when keys never worked -> falls back to drag_xy
    fb_state: dict = {}
    fb_hist = [
        {"action": "key_press", "key": "1", "screen_changed": False},
        {"action": "key_press", "key": "2", "screen_changed": False},
    ]
    fb_state["combat_key_fails"] = 1
    a_fb = game_playbooks.advise_czn_action(
        {},
        [{"text": "2/3", "x": 180, "y": 730}, {"text": "Lead Strike", "x": 340, "y": 850}, {"text": "End Turn", "x": 910, "y": 880}],
        "CAM",
        fb_state,
        [fb_hist[1]],
    )
    assert a_fb is not None and a_fb["action"] == "drag_xy" and a_fb["x"] == 340


def test_czn_overlay_fate_equip_reward_and_auto_detect() -> None:
    # 1. Run Info Overlay (Combatants/Partners/Fate/Faint Memory/Stress/Equipment) closes via [X] (955, 55), never misclassified as combat
    overlay_ocr = [
        {"text": "Combatants", "x": 195, "y": 48},
        {"text": "Partners", "x": 370, "y": 48},
        {"text": "Fate", "x": 555, "y": 48},
        {"text": "Faint Memory", "x": 200, "y": 600},
        {"text": "Copy", "x": 180, "y": 650},
        {"text": "Remove", "x": 180, "y": 700},
        {"text": "Stress", "x": 180, "y": 750},
        {"text": "Equipment", "x": 180, "y": 820},
    ]
    assert game_playbooks.detect_czn_phase([it["text"] for it in overlay_ocr]) == "run_info_overlay"
    a_ov = game_playbooks.advise_czn_action({}, overlay_ocr, "", {}, [])
    assert a_ov is not None and (a_ov["x"], a_ov["y"]) == (955, 55)

    # 2. Fate: picks Altruism over Satiety when Confirm[XÁM]; tries Skip once on Satiety then falls back to Confirm[CAM]
    fstate: dict = {}
    fate_pick = game_playbooks.advise_czn_action(
        {},
        [
            {"text": "Choose your Fate", "x": 500, "y": 930},
            {"text": "Satiety", "x": 260, "y": 480},
            {"text": "Altruism", "x": 740, "y": 480},
            {"text": "Confirm", "x": 890, "y": 926, "state": "XÁM"},
        ],
        "XÁM",
        fstate,
        [],
    )
    assert fate_pick is not None and fate_pick["x"] == 740
    fate_trap = [
        {"text": "Choose your Fate", "x": 500, "y": 930},
        {"text": "Satiety", "x": 500, "y": 540},
        {"text": "Confirm", "x": 890, "y": 926, "state": "CAM"},
    ]
    a_f1 = game_playbooks.advise_czn_action({}, fate_trap, "CAM", fstate, [])
    a_f2 = game_playbooks.advise_czn_action({}, fate_trap, "CAM", fstate, [])
    assert a_f1 is not None and (a_f1["x"], a_f1["y"]) == (760, 926)
    assert a_f2 is not None and (a_f2["x"], a_f2["y"]) == (890, 926)

    # 3. Equipment: selects DPS slot 1 when ATK item & Confirm[XÁM], confirms when [CAM], extracts when 3 slots tried
    estate: dict = {}
    eq_gray = [
        {"text": "Equipment", "x": 160, "y": 48},
        {"text": "Amorphous Cube Attack +23", "x": 310, "y": 500},
        {"text": "Extract", "x": 730, "y": 922},
        {"text": "Confirm", "x": 895, "y": 922, "state": "XÁM"},
    ]
    ae1 = game_playbooks.advise_czn_action({}, eq_gray, "XÁM", estate, [])
    assert ae1 is not None and ae1["x"] == 790 and ae1["y"] == 360
    game_playbooks.advise_czn_action({}, eq_gray, "XÁM", estate, [])
    game_playbooks.advise_czn_action({}, eq_gray, "XÁM", estate, [])
    ae_ext = game_playbooks.advise_czn_action({}, eq_gray, "XÁM", estate, [])
    assert ae_ext is not None and (ae_ext["x"], ae_ext["y"]) == (730, 922)

    # 4. Card Reward: Confirm[XÁM] picks combatant row instead of failing on Confirm
    rstate: dict = {}
    ar1 = game_playbooks.advise_czn_action(
        {},
        [
            {"text": "Card Reward", "x": 720, "y": 140},
            {"text": "Select the combatant", "x": 820, "y": 200},
            {"text": "Wind of Belief 0", "x": 280, "y": 480},
            {"text": "Skip", "x": 765, "y": 922},
            {"text": "Confirm", "x": 895, "y": 922, "state": "XÁM"},
        ],
        "XÁM",
        rstate,
        [],
    )
    assert ar1 is not None and (ar1["x"], ar1["y"]) == (790, 380)

    # 5. Combat failsafe: 2 stalled drags immediately trigger End Turn (no 3rd fail crash)
    stalled_hist = [
        {"action": "drag_xy", "x": 340, "y": 850, "screen_changed": False},
        {"action": "drag_xy", "x": 560, "y": 850, "screen_changed": False},
    ]
    a_end2 = game_playbooks.advise_czn_action(
        {},
        [{"text": "Strike", "x": 450, "y": 850}, {"text": "End Turn", "x": 910, "y": 880}],
        "",
        {},
        stalled_hist,
    )
    assert a_end2 is not None and (a_end2["x"], a_end2["y"]) == (910, 880)

    # 6. Auto-detect game & unlimited max_steps=0
    assert game_playbooks.detect_game_for_window("Chaos Zero Nightmare", "ssr-stove-shield.exe")["playbook"] == "czn"
    assert game_playbooks.detect_game_for_window("Honkai: Star Rail", "StarRail.exe")["playbook"] == "hsr"
    assert game_playbooks.detect_game_for_window("Notepad", "notepad.exe")["playbook"] == "none"
    req_inf = game_agent.GameSessionStartRequest(source="desktop", playbook="czn", max_steps=0)
    assert req_inf.max_steps == 0


def test_chat_streaming_and_startup_wait() -> None:
    import main
    from fastapi.testclient import TestClient

    src = Path(main.__file__).read_text(encoding="utf-8")
    assert "/api/chat/stream" in src
    assert "wait_for_model_ready" in src
    assert "StreamingResponse" in src
    assert "_background_warmup" in src

    client = TestClient(main.app)
    r = client.post("/api/chat", json={"message": "Bây giờ là mấy giờ?"})
    assert r.status_code == 200
    assert "conversation_id" in r.json()

    with client.stream("POST", "/api/chat/stream", json={"message": "Hôm nay ngày mấy?"}) as stream_resp:
        assert stream_resp.status_code == 200
        lines = [line for line in stream_resp.iter_lines() if line.startswith("data:")]
        assert len(lines) >= 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS:", name)
    print("ALL_QA_AND_GAME_UNIT_TESTS_PASSED")
