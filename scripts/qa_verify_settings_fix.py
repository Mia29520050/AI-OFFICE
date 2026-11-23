"""Automated test script to verify Settings modal, tab switching, close X button, and theme toggle removal."""
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
TEST_PORT = 8872

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

async def verify():
    print("[*] Starting server on port", TEST_PORT)
    s = ServerThread(app, TEST_PORT)
    s.start()
    await asyncio.sleep(1.5)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            url = f"http://127.0.0.1:{TEST_PORT}"
            await page.goto(url, wait_until="networkidle")

            # 1. Verify theme button is GONE from sidebar footer
            theme_btn_sidebar = await page.query_selector("#btn-theme-toggle-sidebar")
            assert theme_btn_sidebar is None, "ERROR: #btn-theme-toggle-sidebar still exists in DOM!"
            print("[✓] Verified #btn-theme-toggle-sidebar is completely removed from sidebar footer.")

            # Capture sidebar screenshot
            p_sidebar = ARTIFACT_DIR / "sidebar_clean_settings.png"
            sidebar_el = await page.query_selector("aside.left")
            if sidebar_el:
                await sidebar_el.screenshot(path=str(p_sidebar))
            print("[✓] Captured clean sidebar footer screenshot:", p_sidebar)

            # 2. Open Settings via sidebar button
            settings_sidebar_btn = await page.query_selector("#sidebar-open-settings")
            assert settings_sidebar_btn, "Missing #sidebar-open-settings"
            await settings_sidebar_btn.click()
            await page.wait_for_timeout(400)

            modal = await page.query_selector("#settings-modal")
            assert await modal.is_visible(), "Settings modal failed to open!"
            print("[✓] Settings modal opened successfully via sidebar button.")

            # Capture General tab
            p_general = ARTIFACT_DIR / "settings_modal_general_pure_vi.png"
            await modal.screenshot(path=str(p_general))
            print("[✓] Captured settings modal general tab screenshot:", p_general)

            # 3. Test Close 'X' button
            close_btn = await page.query_selector("#btn-close-settings-modal")
            assert close_btn, "Missing #btn-close-settings-modal"
            await close_btn.click()
            await page.wait_for_timeout(300)
            assert not await modal.is_visible(), "Modal failed to close on X button click!"
            print("[✓] Verified Close 'X' button closes the modal cleanly.")

            # 4. Open Settings via topbar button
            topbar_settings = await page.query_selector("#topbar-open-settings")
            assert topbar_settings, "Missing #topbar-open-settings"
            await topbar_settings.click()
            await page.wait_for_timeout(300)
            assert await modal.is_visible(), "Settings modal failed to open via topbar!"
            print("[✓] Settings modal opened successfully via topbar button.")

            # 5. Test tab switching: Appearance
            tab_app = await page.query_selector('[data-cfg-tab="appearance"]')
            assert tab_app, "Missing appearance tab"
            await tab_app.click()
            await page.wait_for_timeout(300)
            heading = await page.inner_text("#settings-tab-heading")
            assert "Giao diện & Màu sắc" in heading, f"Expected 'Giao diện & Màu sắc', got '{heading}'"
            print("[✓] Switched to Appearance tab successfully.")

            # Capture Appearance tab
            p_app = ARTIFACT_DIR / "settings_modal_appearance_pure_vi.png"
            await modal.screenshot(path=str(p_app))
            print("[✓] Captured settings modal appearance tab screenshot:", p_app)

            # 6. Test tab switching: Models
            tab_models = await page.query_selector('[data-cfg-tab="models"]')
            assert tab_models, "Missing models tab"
            await tab_models.click()
            await page.wait_for_timeout(300)
            heading_models = await page.inner_text("#settings-tab-heading")
            assert "Mô hình AI & Trí tuệ" in heading_models, f"Expected 'Mô hình AI & Trí tuệ', got '{heading_models}'"
            print("[✓] Switched to Models tab successfully.")

            # 7. Test tab switching: Workspace
            tab_ws = await page.query_selector('[data-cfg-tab="workspace"]')
            assert tab_ws, "Missing workspace tab"
            await tab_ws.click()
            await page.wait_for_timeout(300)
            heading_ws = await page.inner_text("#settings-tab-heading")
            assert "Bố cục làm việc" in heading_ws, f"Expected 'Bố cục làm việc', got '{heading_ws}'"
            print("[✓] Switched to Workspace tab successfully.")

            # 8. Test tab switching: Data
            tab_data = await page.query_selector('[data-cfg-tab="data"]')
            assert tab_data, "Missing data tab"
            await tab_data.click()
            await page.wait_for_timeout(300)
            heading_data = await page.inner_text("#settings-tab-heading")
            assert "Lịch sử & Dữ liệu" in heading_data, f"Expected 'Lịch sử & Dữ liệu', got '{heading_data}'"
            print("[✓] Switched to Data tab successfully.")

            # 9. Test Close via Escape key
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
            assert not await modal.is_visible(), "Modal failed to close on Escape key press!"
            print("[✓] Verified Escape key closes the modal cleanly.")

            await browser.close()
    finally:
        s.stop()

    print("\n==========================================")
    print("ALL VERIFICATIONS COMPLETED WITH 100% PASS!")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(verify())
