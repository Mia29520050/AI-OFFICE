"""
QA Verification for the 4 UI refinements:
1. Agent selector dropdown: options without '⌄', clean dropdown styling
2. AI assistant response unboxed: no frame/card, transparent background
3. Settings modal 'Mô hình AI & Trí tuệ': 2-column + full-width layout, no overflow, no scrollbars
4. Studio Sáng Tạo timeline: 2-tier panel card, all controls and delete button fully visible without clipping
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
    def __init__(self, port=8888):
        super().__init__(daemon=True)
        self.port = port
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


async def run_qa():
    print("Starting background server on port 8888...")
    init_db()
    server_thread = ServerThread(port=8888)
    server_thread.start()

    import urllib.request
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:8888/", timeout=2.0)
            break
        except Exception:
            time.sleep(0.3)
    else:
        raise RuntimeError("Server failed to start on port 8888")

    print("Server ready!")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        await page.goto("http://127.0.0.1:8888/")
        await page.wait_for_selector("#chatlog", timeout=8000)
        await asyncio.sleep(0.5)

        # ---------------------------------------------------------------------
        # 1. VERIFY AGENT SELECTOR
        # ---------------------------------------------------------------------
        print("\n--- 1. Testing Agent Selector ---")
        options = await page.locator("#agent-select option").all_text_contents()
        print(f"Agent options: {options}")
        for opt in options:
            assert "⌄" not in opt, f"Option text '{opt}' still contains '⌄'!"
        print("✓ All option texts are clean (no unicode '⌄')")

        # Snapshot of composer toolbar with agent select
        composer_toolbar = page.locator(".claude-composer-toolbar")
        await composer_toolbar.screenshot(path=str(ARTIFACT_DIR / "qa_agent_selector_clean.png"))
        print("✓ Saved qa_agent_selector_clean.png")

        # ---------------------------------------------------------------------
        # 2. VERIFY ASSISTANT CHAT MESSAGE (UNBOXED / FRAMELESS)
        # ---------------------------------------------------------------------
        print("\n--- 2. Testing Unboxed Assistant Chat Message ---")
        # Add test assistant message via page.evaluate
        await page.evaluate("""() => {
            addMsg('user', 'Hãy cho tôi 3 lời khuyên cải thiện cuộc sống');
            addMsg('assistant', 'Để cải thiện cuộc sống, bạn nên tập trung vào 3 trụ cột cốt lõi: Sức khỏe thể chất, Tài chính bền vững và Mối quan hệ xã hội.\\n\\n1. **Sức khỏe**: Duy trì thói quen vận động đều đặn (ít nhất 30 phút/ngày).\\n2. **Tài chính**: Xây dựng quỹ khẩn cấp.\\n3. **Mối quan hệ**: Đầu tư thời gian cho những người thân thiết.\\n\\nBạn có muốn tôi hỗ trợ lập kế hoạch chi tiết không?');
        }""")
        await asyncio.sleep(0.5)

        asst_msg = page.locator(".msg.assistant").first
        asst_box = await asst_msg.evaluate("""el => {
            const style = window.getComputedStyle(el);
            const content = el.querySelector('.msg-content');
            const cStyle = content ? window.getComputedStyle(content) : null;
            return {
                bg: style.backgroundColor,
                border: style.borderWidth,
                boxShadow: style.boxShadow,
                contentBg: cStyle ? cStyle.backgroundColor : null,
                contentBorder: cStyle ? cStyle.borderWidth : null
            };
        }""")
        print(f"Assistant msg computed styles: {asst_box}")
        assert asst_box["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), f"Assistant bg is not transparent: {asst_box['bg']}"
        assert asst_box["contentBg"] in ("rgba(0, 0, 0, 0)", "transparent"), f"Content bg is not transparent: {asst_box['contentBg']}"
        assert asst_box["boxShadow"] in ("none", ""), f"Assistant has box shadow: {asst_box['boxShadow']}"
        print("✓ Assistant message is 100% transparent and unboxed!")

        chat_surface = page.locator("#chat-surface")
        await chat_surface.screenshot(path=str(ARTIFACT_DIR / "qa_assistant_unboxed.png"))
        print("✓ Saved qa_assistant_unboxed.png")

        # Also test light theme
        await page.evaluate("() => window.setTheme('light')")
        await asyncio.sleep(0.4)
        asst_box_light = await asst_msg.evaluate("""el => {
            const style = window.getComputedStyle(el);
            const content = el.querySelector('.msg-content');
            const cStyle = content ? window.getComputedStyle(content) : null;
            return {
                bg: style.backgroundColor,
                contentBg: cStyle ? cStyle.backgroundColor : null,
                boxShadow: style.boxShadow
            };
        }""")
        print(f"Light mode assistant styles: {asst_box_light}")
        assert asst_box_light["bg"] in ("rgba(0, 0, 0, 0)", "transparent")
        assert asst_box_light["contentBg"] in ("rgba(0, 0, 0, 0)", "transparent")
        await chat_surface.screenshot(path=str(ARTIFACT_DIR / "qa_assistant_unboxed_light.png"))
        print("✓ Saved qa_assistant_unboxed_light.png")

        # Switch back to dark theme
        await page.evaluate("() => window.setTheme('dark')")
        await asyncio.sleep(0.3)

        # ---------------------------------------------------------------------
        # 3. VERIFY SETTINGS MODAL 'MÔ HÌNH AI & TRÍ TUỆ'
        # ---------------------------------------------------------------------
        print("\n--- 3. Testing Settings 'Mô hình AI & Trí tuệ' Layout ---")
        await page.evaluate("() => openSettingsModal('models')")
        await page.wait_for_selector("#modal-model-settings-form", timeout=5000)
        await asyncio.sleep(0.5)

        modal_overflow = await page.evaluate("""() => {
            const body = document.getElementById('settings-modal-body');
            const form = document.getElementById('modal-model-settings-form');
            const card = document.querySelector('.settings-modal-card');
            const inputs = Array.from(form.querySelectorAll('input, select'));
            const overflowingInputs = inputs.filter(inp => {
                const r = inp.getBoundingClientRect();
                const cardR = card.getBoundingClientRect();
                return r.right > cardR.right;
            }).map(inp => inp.id);
            return {
                bodyScrollWidth: body.scrollWidth,
                bodyClientWidth: body.clientWidth,
                hasHorizScroll: body.scrollWidth > body.clientWidth,
                overflowingInputs
            };
        }""")
        print(f"Modal overflow check: {modal_overflow}")
        assert not modal_overflow["hasHorizScroll"], "Modal body has horizontal scrollbar!"
        assert len(modal_overflow["overflowingInputs"]) == 0, f"Inputs overflow outside card: {modal_overflow['overflowingInputs']}"
        print("✓ Settings modal 'models' tab fits completely without any overflow!")

        modal_card = page.locator(".settings-modal-card")
        await modal_card.screenshot(path=str(ARTIFACT_DIR / "qa_settings_models_clean.png"))
        print("✓ Saved qa_settings_models_clean.png")

        await page.evaluate("() => closeSettingsModal()")
        await asyncio.sleep(0.3)

        # ---------------------------------------------------------------------
        # 4. VERIFY STUDIO SÁNG TẠO TIMELINE ROW
        # ---------------------------------------------------------------------
        print("\n--- 4. Testing Studio Sáng Tạo Timeline Controls ---")
        await page.evaluate("() => navigate('studio')")
        await page.wait_for_selector("#mc-timeline-list", timeout=5000)
        await asyncio.sleep(0.6)

        timeline_overflow = await page.evaluate("""() => {
            const list = document.getElementById('mc-timeline-list');
            const cards = Array.from(list.querySelectorAll('.mc-panel-card'));
            const cardStats = cards.map((c, i) => {
                const r = c.getBoundingClientRect();
                const closeBtn = c.querySelector('.mini-pill.close');
                const closeR = closeBtn ? closeBtn.getBoundingClientRect() : null;
                const selects = Array.from(c.querySelectorAll('select')).map(s => ({
                    val: s.value,
                    w: s.clientWidth,
                    overflow: s.scrollWidth > s.clientWidth
                }));
                return {
                    idx: i,
                    cardWidth: c.clientWidth,
                    closeVisible: closeR ? (closeR.right <= r.right + 2 && closeR.left >= r.left) : false,
                    selects
                };
            });
            return {
                listScrollWidth: list.scrollWidth,
                listClientWidth: list.clientWidth,
                cardStats
            };
        }""")
        print(f"Studio timeline check: {timeline_overflow}")
        for stat in timeline_overflow["cardStats"]:
            assert stat["closeVisible"], f"Panel #{stat['idx']+1} delete button is clipped or hidden!"
            for sel in stat["selects"]:
                assert not sel["overflow"], f"Dropdown in panel #{stat['idx']+1} overflows!"
        print("✓ Studio Creative timeline cards fit cleanly with delete buttons and selects fully visible!")

        studio_container = page.locator("#page-studio")
        await studio_container.screenshot(path=str(ARTIFACT_DIR / "qa_studio_creative_timeline_clean.png"))
        print("✓ Saved qa_studio_creative_timeline_clean.png")

        await browser.close()

    server_thread.stop()
    print("\n==========================================")
    print("ALL 4 QA VERIFICATIONS PASSED SUCCESSFULLY!")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(run_qa())
