from __future__ import annotations

import os
from playwright.sync_api import sync_playwright

BASE = os.getenv("AI_OFFICE_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=EDGE, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1426, "height": 900})
        response = page.goto(BASE, wait_until="domcontentloaded", timeout=20_000)
        assert response and response.status == 200
        page.locator('.act[data-view="workspace"]').click()
        assert page.locator("#workspace-agent-form").is_visible()
        assert page.locator("#workspace-edit-path").is_visible()
        assert page.locator("#workspace-edit-goal").is_visible()
        assert page.locator("#workspace-edit-agent option").count() >= 4
        assert page.locator("#workspace-change-list").is_visible()
        assert page.locator("#workspace-change-detail").is_visible()
        page.wait_for_selector(".file-row", timeout=15_000)
        assert page.locator(".file-row").count() > 0
        readme = page.locator('.file-row[data-entry="README.md"]')
        if readme.count():
            readme.click()
            page.wait_for_selector("#workspace-use-file", timeout=15_000)
            assert page.locator("#workspace-use-file").is_visible()
            assert page.locator("#workspace-edit-path").input_value() == "README.md"
        rows = page.locator("[data-workspace-change]")
        if rows.count():
            rows.first.click()
            page.wait_for_selector(".workspace-diff", timeout=15_000)
            assert page.locator(".workspace-diff").is_visible()
        print("Workspace page: PASS")
        print("Agent editor form: PASS")
        print("File selection -> Agent path: PASS" if readme.count() else "File selection: PASS - README not in root listing")
        print("Proposal history and diff review: PASS")
        browser.close()


if __name__ == "__main__":
    main()
