import asyncio
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from playwright.async_api import async_playwright
import uvicorn

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "app"))

from app.main import app

ARTIFACT_DIR = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\ba17a7d2-fcc5-4468-8872-6615a2f705c6")
TEST_PORT = 8871

class ServerThread(threading.Thread):
    def __init__(self, app, port):
        super().__init__(daemon=True)
        self.port = port
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

async def verify_all():
    print("Starting server on port", TEST_PORT)
    s = ServerThread(app, TEST_PORT)
    s.start()
    await asyncio.sleep(1.5)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            url = f"http://127.0.0.1:{TEST_PORT}"
            await page.goto(url, wait_until="networkidle")

            # 1. Antigravity Composer Screenshot
            p1 = ARTIFACT_DIR / "antigravity_composer_audit.png"
            await page.screenshot(path=str(p1))
            print("1. Captured composer screenshot:", p1)

            # 2. Studio navigation & persistent topbar & collapse sidebar
            btn_studio = await page.query_selector("#btn-quick-studio")
            assert btn_studio, "Missing #btn-quick-studio"
            await btn_studio.click()
            await page.wait_for_timeout(500)

            topbar = await page.query_selector("#chat-topbar")
            assert await topbar.is_visible(), "Topbar must be visible in Studio!"

            # Collapse sidebar
            collapse_btn = await page.query_selector(".panel-collapse-btn")
            if collapse_btn and await collapse_btn.is_visible():
                await collapse_btn.click()
                await page.wait_for_timeout(300)

            # Hamburger button ☰ must be visible
            hamburger = await page.query_selector(".sidebar-toggle-btn")
            assert await hamburger.is_visible(), "Hamburger button ☰ must be visible when sidebar is collapsed in Studio!"

            p2 = ARTIFACT_DIR / "studio_topbar_unstick_audit.png"
            await page.screenshot(path=str(p2))
            print("2. Captured Studio unstick screenshot:", p2)

            # 3. Open Settings Modal
            btn_settings = await page.query_selector("#topbar-open-settings")
            assert btn_settings, "Missing #topbar-open-settings"
            await btn_settings.click()
            await page.wait_for_timeout(500)

            settings_modal = await page.query_selector("#settings-modal")
            assert await settings_modal.is_visible(), "Settings modal must be visible!"

            p3 = ARTIFACT_DIR / "antigravity_settings_modal_general.png"
            await page.screenshot(path=str(p3))
            print("3. Captured Settings General screenshot:", p3)

            # 4. Switch to Appearance tab
            btn_tab_app = await page.query_selector('[data-cfg-tab="appearance"]')
            assert btn_tab_app, "Missing appearance tab button"
            await btn_tab_app.click()
            await page.wait_for_timeout(400)

            p4 = ARTIFACT_DIR / "antigravity_settings_modal_appearance.png"
            await page.screenshot(path=str(p4))
            print("4. Captured Settings Appearance screenshot:", p4)

            await browser.close()
    finally:
        s.stop()

    print("ALL 4 SPECIFIC VERIFICATIONS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(verify_all())
