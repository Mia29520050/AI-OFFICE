import asyncio
import os
import sys
import threading
import time
from pathlib import Path
from playwright.async_api import async_playwright
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from main import app

ARTIFACT_DIR = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\ba17a7d2-fcc5-4468-8872-6615a2f705c6")

async def main():
    server_config = uvicorn.Config(app, host='127.0.0.1', port=8898, log_level='warning')
    server = uvicorn.Server(server_config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        await page.goto('http://127.0.0.1:8898/')
        await page.wait_for_selector('#chatlog')

        # 1. Click Studio in sidebar or navigate('studio')
        await page.evaluate("() => navigate('studio')")
        await asyncio.sleep(0.5)

        # 2. Click "Vẽ Manga & Storyboard" tab
        await page.click('[data-studio-tab="manga"]')
        await asyncio.sleep(1.0)
        await page.screenshot(path=str(ARTIFACT_DIR / "qa_manga_series_hub.png"))
        print("✓ Captured qa_manga_series_hub.png")

        # 3. Click "Storyboard & Art" tab
        await page.click('[data-manga-tab="storyboard"]')
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(ARTIFACT_DIR / "qa_manga_storyboard_20pages.png"))
        print("✓ Captured qa_manga_storyboard_20pages.png")

        # 4. Click "Manga Composer" tab
        await page.click('[data-manga-tab="composer"]')
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(ARTIFACT_DIR / "qa_manga_composer_viewer.png"))
        print("✓ Captured qa_manga_composer_viewer.png")

        await browser.close()
    server.should_exit = True

if __name__ == "__main__":
    asyncio.run(main())
