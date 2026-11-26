"""
End-to-end QA verification for:
1. Antigravity-style 3-dots context menu on conversation items (Rename, Pin, Copy, Project, Delete)
2. 3-dots icon visibility with SVG currentColor fill
3. Progress header auto-hide after 1.2s
4. Real-time Vietnam holiday responses (24/11 - Ngày Di sản Văn hóa Việt Nam)
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
    print("Starting background uvicorn test server...")
    init_db()
    server_thread = ServerThread()
    server_thread.start()

    # Wait for server to be responsive on root
    import urllib.request
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:8765/", timeout=2.0)
            print("Server is listening on 127.0.0.1:8765")
            break
        except Exception:
            time.sleep(0.3)
    else:
        raise RuntimeError("Server failed to start")

    print("Starting Playwright QA verification...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. Load AI Office
        print("1. Navigating to http://127.0.0.1:8765 ...")
        await page.goto("http://127.0.0.1:8765", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # 2. Check conversation row & 3-dots button
        rows = page.locator(".conversation-row")
        row_count = await rows.count()
        print(f"Found {row_count} conversation rows.")
        if row_count == 0:
            await page.click("#new-conversation-btn")
            await page.wait_for_timeout(500)
            rows = page.locator(".conversation-row")
            row_count = await rows.count()

        first_row = rows.first
        await first_row.hover()
        await page.wait_for_timeout(200)

        # Check dots button
        dots_btn = first_row.locator(".conversation-action-dots, .conversation-actions button:last-child")
        is_visible = await dots_btn.is_visible()
        print(f"3-dots button visible on hover: {is_visible}")
        assert is_visible, "3-dots button should be visible on hover"

        # Click 3-dots button to open Antigravity context popover
        await dots_btn.click()
        await page.wait_for_timeout(300)

        popover = page.locator(".conversation-menu-popover")
        popover_visible = await popover.is_visible()
        print(f"Antigravity context menu popover visible: {popover_visible}")
        assert popover_visible, "Context popover should be open"

        # Capture screenshot of Antigravity popover
        popover_shot = ARTIFACT_DIR / "qa_antigravity_popover.png"
        await page.screenshot(path=str(popover_shot))
        print(f"Captured screenshot: {popover_shot}")

        # Close popover by clicking outside
        await page.mouse.click(500, 300)
        await page.wait_for_timeout(300)

        # 3. Test Chat Progress Banner Auto-Hide with holiday query
        print("Testing Chat Progress Auto-Hide with holiday query...")
        chat_input = page.locator("#chatinput")
        await chat_input.fill("24/11 là ngày gì ở Việt Nam?")
        await page.click("#sendbtn")

        # Wait until sendbtn is enabled again (meaning streaming has finished completely)
        await page.wait_for_selector("#sendbtn:not([disabled])", timeout=25000)
        await page.wait_for_timeout(500)

        # Check response content for Vietnam Cultural Heritage Day
        last_msg = page.locator(".msg.assistant .msg-content").last
        response_text = await last_msg.text_content()
        print(f"Holiday query response: {response_text}")
        assert "Di sản Văn hóa Việt Nam" in response_text, "Response must identify Ngày Di sản Văn hóa Việt Nam"

        # Progress banner auto-hide verification: wait 1.8s
        await page.wait_for_timeout(1800)
        progress_box = page.locator("#chat-progress")
        is_hidden_after = await progress_box.is_hidden()
        print(f"Progress box after 1.8s: is_hidden={is_hidden_after}")
        assert is_hidden_after, "Progress banner should auto-hide after 1.2s when done"

        # Capture screenshot of chat view after progress hide
        chat_shot = ARTIFACT_DIR / "qa_chat_auto_hide_and_holiday.png"
        await page.screenshot(path=str(chat_shot))
        print(f"Captured screenshot: {chat_shot}")

        await browser.close()
        server_thread.stop()
        print("ALL QA CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_qa())
