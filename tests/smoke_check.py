import os
import httpx

BASE = os.getenv("AI_OFFICE_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def main():
    ui = httpx.get(BASE + "/", timeout=10)
    assert ui.status_code == 200 and "AI Office" in ui.text
    assert 'id="chatinput"' in ui.text and 'id="sendbtn"' in ui.text
    assert "KHÔNG GIAN LÀM VIỆC" in ui.text and "LỊCH SỬ CHAT" in ui.text
    assert "chat-agent-mark" in ui.text and "chat-agent-title" in ui.text
    assert "Tổng quan không gian làm việc" in ui.text
    assert 'data-view="workspace"' in ui.text and 'data-view="game"' in ui.text
    assert "aioffice:open-workspace-editor" in ui.text
    assert "if(currentAgent==='Workspace'" in ui.text
    assert ".center-scroll[hidden]{display:none!important;}" in ui.text
    assert "WORKSPACE EDITOR" in ui.text and "workspace-agent-form" in ui.text
    assert "workspace-change-list" in ui.text and "Duyệt và áp dụng" in ui.text
    assert "DIFF · BACKUP · ROLLBACK" in ui.text
    assert "renderGameVTuber" in ui.text and "vtuberAvatarSvg" in ui.text
    assert 'id="dynamic-page"' in ui.text and "renderWorkspace" in ui.text and "renderTasks" in ui.text
    assert "@media(max-width:1180px)" in ui.text and "@media(max-width:900px)" in ui.text
    assert "@media(max-width:700px)" in ui.text and "@media(max-height:720px)" in ui.text
    assert 'role="menu"' in ui.text and 'role="menuitem"' in ui.text
    assert 'data-menu-toggle="workspace"' in ui.text and 'data-menu-toggle="view"' in ui.text and 'data-menu-toggle="window"' in ui.text
    assert 'id="menu-workspace"' in ui.text and 'id="menu-view"' in ui.text and 'id="menu-window"' in ui.text
    assert "Thu nhỏ · Phóng to · Đóng: thanh tiêu đề Windows" in ui.text
    assert ui.text.count("</html>") == 1 and ui.text.rstrip().endswith("</html>")
    icon = httpx.get(BASE + "/assets/ai-office-icon.png", timeout=10)
    assert icon.status_code == 200 and icon.headers.get("content-type", "").startswith("image/png")
    assert len(icon.content) > 1000

    sandbox = httpx.get(BASE + "/sandbox-game", timeout=10)
    assert sandbox.status_code == 200 and "Đấu Thẻ Bài" in sandbox.text and "Cờ Caro" in sandbox.text

    status = httpx.get(BASE + "/api/status", timeout=10).json()
    assert status["runtime"] in {"local", "cloud_opt_in"}
    assert status["version"] == "0.6.0"
    assert status["capabilities"]["workspace_browse"] and status["capabilities"]["task_details"]
    assert status["capabilities"]["workspace_file_read"] and status["capabilities"]["workspace_file_create"] and status["capabilities"]["workspace_file_edit"]
    assert status["capabilities"]["workspace_edit_proposals"] and status["capabilities"]["workspace_diff_preview"]
    assert status["capabilities"]["workspace_backup_before_apply"] and status["capabilities"]["workspace_rollback"]
    assert status["capabilities"]["workspace_agent_edit"] and status["capabilities"]["workspace_edit_approval_required"]
    assert status["capabilities"]["computer_use_planner"]
    assert status["capabilities"]["computer_use_target_window_picker"]
    assert status["capabilities"]["game_vtuber_session"]
    assert status["capabilities"]["cloud_vision_opt_in"]
    assert status["capabilities"]["computer_use_approval_required"]
    assert status["capabilities"]["computer_use_post_action_verification"]
    assert status["capabilities"]["computer_use_max_steps"] == 8
    assert status["capabilities"]["computer_use_step_history"]
    assert status["capabilities"]["computer_use_unattended"] is False
    assert status["capabilities"]["browser_automation"] and status["capabilities"]["browser_isolated_profile"]
    assert status["capabilities"]["browser_dom_observation"] and status["capabilities"]["browser_approval_required"]
    assert status["capabilities"]["browser_form_submission"] is False
    assert status["capabilities"]["browser_download_upload"] is False

    model_cfg = httpx.get(BASE + "/api/settings/model", timeout=10)
    assert model_cfg.status_code == 200 and "cloud_api_key" not in model_cfg.json()
    game_state = httpx.get(BASE + "/api/game/session", timeout=10)
    assert game_state.status_code == 200 and "status" in game_state.json()
    playbooks = httpx.get(BASE + "/api/game/playbooks", timeout=10)
    assert playbooks.status_code == 200 and any(p.get("id") == "czn" for p in playbooks.json().get("playbooks", []))
    assert playbooks.json().get("czn_knowledge", {}).get("combatants_trained", 0) >= 35
    vtuber_models = httpx.get(BASE + "/api/vtuber/models", timeout=10)
    assert vtuber_models.status_code == 200 and any(m.get("id") == "svg-fallback" for m in vtuber_models.json().get("models", []))
    live2d_ctrl = httpx.get(BASE + "/assets/live2d/stage-controller.mjs", timeout=10)
    assert live2d_ctrl.status_code == 200 and "javascript" in live2d_ctrl.headers.get("content-type", "")

    tasks = httpx.get(BASE + "/api/tasks", timeout=10).json()
    messages = httpx.get(BASE + "/api/messages", timeout=10).json()
    agents = httpx.get(BASE + "/api/agents", timeout=10)
    skills = httpx.get(BASE + "/api/skills", timeout=10)
    workspace = httpx.get(BASE + "/api/workspace", timeout=10)
    hidden_workspace = httpx.get(BASE + "/api/workspace", params={"path": "data"}, timeout=10)
    traversal = httpx.get(BASE + "/api/workspace", params={"path": "../"}, timeout=10)
    assert agents.status_code == 200 and len(agents.json()) >= 9
    workspace_agent = next((a for a in agents.json() if a["id"] == "Workspace"), None)
    assert workspace_agent and workspace_agent["skill"] == "workspace" and workspace_agent["skill_installed"]
    assert any(a["id"] == "Browser" and a["skill"] == "browser" for a in agents.json())
    assert all(a["skill_installed"] for a in agents.json())
    if status["model"].get("online") and status["model"].get("model_ready"):
        browser_chat = httpx.post(BASE + "/api/chat", json={"message": "State your safe browser capabilities in one concise sentence; do not browse or act.", "agent": "Browser"}, timeout=180)
        assert browser_chat.status_code == 200 and "answer" in browser_chat.json()
    assert skills.status_code == 200 and len(skills.json()) >= 7
    skill_detail = httpx.get(BASE + "/api/skills/computer", timeout=10)
    assert skill_detail.status_code == 200 and "Computer-control skill" in skill_detail.json()["content"]
    assert workspace.status_code == 200 and any(e["name"] == "app" for e in workspace.json()["entries"])
    readme_preview = httpx.get(BASE + "/api/workspace/file", params={"path": "README.md"}, timeout=10)
    assert readme_preview.status_code == 200 and "AI Office" in readme_preview.json()["content"]
    assert hidden_workspace.status_code == 403 and traversal.status_code == 403
    if tasks:
        detail = httpx.get(BASE + "/api/tasks/" + tasks[0]["id"], timeout=10)
        assert detail.status_code == 200 and detail.json()["id"] == tasks[0]["id"]

    active = httpx.get(BASE + "/api/computer/active", timeout=15)
    windows = httpx.get(BASE + "/api/computer/windows", timeout=15)
    tree = httpx.get(BASE + "/api/computer/tree", timeout=20)
    denied = httpx.post(BASE + "/api/computer/action", json={"action": "scroll", "confirm": False}, timeout=10)
    direct_bypass = httpx.post(BASE + "/api/computer/action", json={"action": "scroll", "confirm": True}, timeout=10)
    sensitive_goal = httpx.post(BASE + "/api/computer/plan", json={"goal": "Enter my password in the current window."}, timeout=10)
    pending = httpx.get(BASE + "/api/computer/pending", timeout=10)
    approval_denied = httpx.post(BASE + "/api/computer/approve/not-a-real-id", json={"confirm": False}, timeout=10)
    invalid_plan = httpx.post(BASE + "/api/computer/plan", json={"goal": "abc"}, timeout=10)
    history_limit = httpx.post(BASE + "/api/computer/plan", json={"goal": "Scroll to the next section safely.", "history": [{"action": "scroll", "target": "main", "window_title": "AI Office", "result": "verified"} for _ in range(9)]}, timeout=10)
    browser_state = httpx.get(BASE + "/api/browser/status", timeout=10)
    browser_pending = httpx.get(BASE + "/api/browser/pending", timeout=10)
    browser_local = httpx.post(BASE + "/api/browser/navigate", json={"url": "http://127.0.0.1:8765"}, timeout=10)
    browser_file = httpx.post(BASE + "/api/browser/navigate", json={"url": "file:///C:/Windows/win.ini"}, timeout=10)
    browser_private_ip = httpx.post(BASE + "/api/browser/navigate", json={"url": "http://192.168.1.1"}, timeout=10)
    browser_sensitive_url = httpx.post(BASE + "/api/browser/navigate", json={"url": "https://example.com/login"}, timeout=10)
    browser_bad_port = httpx.post(BASE + "/api/browser/navigate", json={"url": "https://example.com:99999/"}, timeout=10)
    browser_sensitive = httpx.post(BASE + "/api/browser/plan", json={"goal": "Enter my password on this website."}, timeout=10)
    browser_approval_denied = httpx.post(BASE + "/api/browser/approve/not-a-real-id", json={"confirm": False}, timeout=10)
    browser_history_limit = httpx.post(BASE + "/api/browser/plan", json={"goal": "Find a public documentation link.", "history": [{} for _ in range(8)]}, timeout=10)

    assert active.status_code == 200 and "found" in active.json()
    assert windows.status_code == 200 and isinstance(windows.json(), list)
    assert tree.status_code == 200 and "controls" in tree.json()
    assert denied.status_code == 403 and direct_bypass.status_code == 403
    assert sensitive_goal.status_code in {403, 503}
    assert pending.status_code == 200 and isinstance(pending.json(), list)
    assert approval_denied.status_code == 403
    assert invalid_plan.status_code == 422
    assert history_limit.status_code == 422
    assert browser_state.status_code == 200 and browser_pending.status_code == 200
    assert browser_local.status_code == 403 and browser_file.status_code == 400
    assert browser_private_ip.status_code == 403 and browser_sensitive_url.status_code == 403
    assert browser_bad_port.status_code == 400
    assert browser_sensitive.status_code in {403, 503} and browser_approval_denied.status_code == 403
    assert browser_history_limit.status_code == 422

    print("UI route: PASS")
    print("Sandbox game route: PASS")
    print("Model settings & route: PASS -", status["model_route"])
    print("Task API: PASS -", len(tasks), "task(s)")
    print("Chat history: PASS -", len(messages), "message(s)")
    print("Agent catalog: PASS -", len(agents.json()), "roles; all skills installed")
    print("Skills registry: PASS -", len(skills.json()), "skills")
    print("Workspace Explorer: PASS -", len(workspace.json()["entries"]), "entries; hidden paths blocked")
    print("Computer & Game gates: PASS")
    print("Browser Automation gates: PASS")


if __name__ == "__main__":
    main()
