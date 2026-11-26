"""Capture Claude sidebar expanded in both dark and light modes."""
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

SCREENSHOT_DIR = ROOT_DIR / "data" / "screenshots"
ARTIFACT_DIR = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\ba17a7d2-fcc5-4468-8872-6615a2f705c6")
TEST_PORT = 8899


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


async def capture_sidebar():
    server_thread = ServerThread(app, TEST_PORT)
    server_thread.start()
    time.sleep(1.5)

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = await p.chromium.launch(headless=True, channel="msedge")

            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            target_url = f"http://127.0.0.1:{TEST_PORT}"
            await page.goto(target_url, wait_until="networkidle")

            # Expand sidebar explicitly
            await page.evaluate("""() => {
                const body = document.querySelector('.body');
                if (body) {
                    body.classList.remove('hide-sidebar', 'hide-explorer');
                }
                if (window.setTheme) window.setTheme('dark');
            }""")
            await page.wait_for_timeout(400)

            p_dark_sidebar = SCREENSHOT_DIR / "ui_theme_dark_sidebar.png"
            await page.screenshot(path=str(p_dark_sidebar))
            print(f"[+] Saved {p_dark_sidebar}")

            # Switch to light
            await page.evaluate("""() => {
                if (window.setTheme) window.setTheme('light');
            }""")
            await page.wait_for_timeout(400)

            p_light_sidebar = SCREENSHOT_DIR / "ui_theme_light_sidebar.png"
            await page.screenshot(path=str(p_light_sidebar))
            print(f"[+] Saved {p_light_sidebar}")

            if ARTIFACT_DIR.exists():
                shutil.copy2(p_dark_sidebar, ARTIFACT_DIR / p_dark_sidebar.name)
                shutil.copy2(p_light_sidebar, ARTIFACT_DIR / p_light_sidebar.name)

            await browser.close()
    finally:
        server_thread.stop()


if __name__ == "__main__":
    asyncio.run(capture_sidebar())
