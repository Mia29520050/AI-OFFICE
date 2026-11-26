"""
QA Verification for mouse drag text selection in chat messages:
1. Verify text selection via mouse drag (mousedown, mousemove, mouseup)
2. Verify selection highlight style
3. Verify right-click copy menu (.selection-copy-popover)
4. Verify pywebview text_select=True in launcher.py
"""
import asyncio
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
for p in (str(ROOT), str(APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
from main import app, init_db
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\ba17a7d2-fcc5-4468-8872-6615a2f705c6")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


async def run_qa():
    print("Checking launcher.py text_select setting...")
    launcher_text = (ROOT / "app" / "launcher.py").read_text(encoding="utf-8")
    assert "text_select=True" in launcher_text, "app/launcher.py must have text_select=True in webview.create_window"
    print("app/launcher.py has text_select=True: OK")

    print("Starting background server...")
    init_db()
    server_thread = ServerThread()
    server_thread.start()

    import urllib.request
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:8765/", timeout=2.0)
            break
        except Exception:
            time.sleep(0.3)
    else:
        raise RuntimeError("Server failed to start")

    print("Launching Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        await page.goto("http://127.0.0.1:8765", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # 1. Check user-select style on .msg-content
        user_select = await page.evaluate("""() => {
            const el = document.querySelector('.msg-content');
            return el ? window.getComputedStyle(el).userSelect : 'none';
        }""")
        print(f"Computed userSelect on .msg-content: {user_select}")
        assert user_select in ("text", "auto"), f"userSelect should be text/auto, got {user_select}"

        # 2. Perform mouse drag selection over message text
        msg_el = page.locator(".msg-content").first
        box = await msg_el.bounding_box()
        assert box, "Message box must exist"

        print(f"Dragging mouse from ({box['x']+10}, {box['y']+10}) to ({box['x']+200}, {box['y']+10})...")
        await page.mouse.move(box["x"] + 10, box["y"] + 10)
        await page.mouse.down()
        await page.mouse.move(box["x"] + 250, box["y"] + 10, steps=10)
        await page.mouse.up()
        await page.wait_for_timeout(300)

        # 3. Check selected text
        selected_text = await page.evaluate("() => window.getSelection().toString()")
        print(f"Selected text via mouse drag: '{selected_text}'")
        assert len(selected_text.strip()) > 0, "Selected text must not be empty after mouse drag"

        # 4. Trigger right-click context menu on selection
        await page.mouse.click(box["x"] + 100, box["y"] + 10, button="right")
        await page.wait_for_timeout(300)

        copy_popover = page.locator(".selection-copy-popover")
        is_popover_visible = await copy_popover.is_visible()
        print(f"Right-click copy popover visible: {is_popover_visible}")
        assert is_popover_visible, "Copy popover must be visible on right-click over selection"

        # Capture screenshot of selected text and copy popover
        shot_path = ARTIFACT_DIR / "qa_mouse_text_selection_and_copy.png"
        await page.screenshot(path=str(shot_path))
        print(f"Captured screenshot: {shot_path}")

        # 5. Click the copy button in popover
        await copy_popover.locator("button").click()
        await page.wait_for_timeout(200)

        # Verify popover closed after click
        is_popover_closed = await copy_popover.is_hidden()
        print(f"Popover closed after copy: {is_popover_closed}")
        assert is_popover_closed, "Popover should close after copy action"

        await browser.close()
        server_thread.stop()
        print("ALL TEXT SELECTION & COPY QA CHECKS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_qa())
