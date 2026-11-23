from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

SCREENSHOT_PATH = ROOT_DIR / "data" / "screenshots" / "ui_qa_audit.png"
INDEX_HTML_PATH = ROOT_DIR / "app" / "ui" / "index.html"


async def run_qa_audit() -> bool:
    print("=================================================================")
    print("AI-OFFICE: E2E QA WEB-TO-APP AUDIT & SCREENSHOT CAPTURE")
    print("=================================================================")

    SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not INDEX_HTML_PATH.exists():
        print(f"[-] Missing index.html at {INDEX_HTML_PATH}")
        return False

    async with async_playwright() as p:
        print("[*] Launching system Chrome browser for UI verification...")
        try:
            browser = await p.chromium.launch(headless=True, channel="chrome")
        except Exception:
            print("[*] Chrome failed, attempting Edge...")
            browser = await p.chromium.launch(headless=True, channel="msedge")
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        target_url = INDEX_HTML_PATH.as_uri()
        print(f"[*] Navigating to: {target_url}")
        await page.goto(target_url, wait_until="load")

        # 1. Verify Title & Header
        title = await page.title()
        print(f"[+] Page loaded. Title: '{title}'")

        # 2. Verify Omnibar elements
        chatinput = await page.query_selector("#chatinput")
        smart_hub_btn = await page.query_selector("#smart-hub-btn")
        sendbtn = await page.query_selector("#sendbtn")
        omnibar_preview = await page.query_selector("#smart-omnibar-preview")

        assert chatinput is not None, "Missing #chatinput in DOM"
        assert smart_hub_btn is not None, "Missing #smart-hub-btn in DOM"
        assert sendbtn is not None, "Missing #sendbtn in DOM"
        assert omnibar_preview is not None, "Missing #smart-omnibar-preview in DOM"
        print("[+] Verified all core Omnibar DOM selectors present.")

        # 3. Simulate Smart Hub Button Click
        print("[*] Clicking #smart-hub-btn to open Smart Hub Menu...")
        await smart_hub_btn.click()
        await page.wait_for_timeout(300)

        menu = await page.query_selector("#smart-hub-menu")
        is_hidden = await menu.get_attribute("hidden")
        assert is_hidden is None, "Smart Hub Menu should be visible after click"
        print("[+] Smart Hub Menu opened successfully!")

        # 4. Type a fast math formula to test intent badge
        print("[*] Typing 12-digit calculation into #chatinput...")
        await chatinput.fill("123456789012 * 987654321098")
        await page.wait_for_timeout(200)

        badge = await page.query_selector("#smart-intent-badge")
        badge_text = await badge.text_content()
        print(f"[+] Smart Intent Badge triggered: '{badge_text.strip()}'")

        # 5. Capture Screenshot
        print(f"[*] Capturing audit screenshot to: {SCREENSHOT_PATH}...")
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=False)
        print(f"[+] Screenshot successfully captured ({os.path.getsize(SCREENSHOT_PATH):,} bytes).")

        await browser.close()

    print("\n=================================================================")
    print("QA E2E AUDIT VERDICT: 100% PASS (VERIFIED)")
    print("=================================================================")
    return True


if __name__ == "__main__":
    success = asyncio.run(run_qa_audit())
    sys.exit(0 if success else 1)
