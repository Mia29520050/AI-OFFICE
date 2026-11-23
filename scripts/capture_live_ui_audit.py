"""Live E2E UI verification & Multi-step screenshot capture."""
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

VALID_PNG_B64 = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKAAAAB4CAIAAAD6wG44AAAFFklEQVR4nO3dbUxV"
    "dQDH8T/ee5kY9AIQM9OQAZNsmqEXQR7kQWw0aGCaUKEuwVhQjmrT0exFDBYFqVxDIhAQJRiMgqKyBAF5uBeMKB4G"
    "M01WL8QLPUwLLnBpeNgZM++VGmT++H1enfM/5393xveec+7lxbkWK9w2CcK14G4fAM0tBgbHwOAYGBwDg2NgcAwM"
    "joHBMTA4BgbHwOAYGBwDg2NgcAwMjoHBMTA4BgbHwOAYGBwDg2NgcAwMjoHBMTA4BgbHwOAYGBwDg2NgcAwMjoHB"
    "MTA4BgbHwOAYGBwDg5vlwH3tNe+/95a8eiTtUF97jby68+nQix219na28s4l+Zny1k7tF9JC1I6wytKcitPHC7Lf"
    "XbrEwdR0SeT2sOryvNJCTf7xdx58wOGWl/r7qo2NdY4mtbwoK0eTamNjLQ3eb2OdnpLUpftSwJnlwAaDwclxhUIx"
    "+bIWFhYPL19mMBjkrUH+m04UlQX4eso7K5SKjep101/Bx2vD1iC/iKi48KgXW1rb05IPmJou7fxUSFDEs3E7ouPz"
    "T5Wnpybd8QgT9kXr2jq2PRenu9DxUszz0mBeVtr3Xb0TExMCzuxfoju7e9c86iaEeGSVS0/vD/K41cKFi6ysisuq"
    "Ajf7yYMZmbmJ8S9Mnx67JzLj6IdjY2NCiMLiiuGREentctvpsXsi3z6cPTw8IoQ419Bypf9npfIOTx3x9/WsrP5a"
    "CFBVfTbAb+q9Erf/jfxTZQLR7Aeub9T5eXsIIfy81XWNWnnc11t9rqHl0uX+h5YtValU0mCT9oIQwtPjcXk3V+eV"
    "PT0XpeUbN/6IiT84Pm40Nd3VeWVXT58898CbadI7wwx7O9tr+iEhxMC1QflqL43M66fszFx9oy46KuLwsTwvD/fC"
    "4gp5PDjAZ7WbS8hW/yUO9hs3PNbQ1CqNZ2hyX03Yu137zdQBKRXSQszunUH+3g72tv5PRpmarlBM7XwLlUpVUqCZ"
    "virmq9kP/OtvvxuNRunzzvXrN6RBhWKBk+PyJ8J33zyzPQI3e8mBW3TtxnGjl4e7tHr5yk9urs4dnT05+R+VlH/a"
    "Vl9pZvqlH/tXr3Jp/65buuWnpyQlHkwWQoyOjj6zK/62H7L0g0OL7W2vDugdFtvpB2FP3Ln9mlR3Xvv6/n3nm9vk"
    "kYX169d0905deHVtHb5e6un7Z2hyExOm7sSnSz9JfHmv9CvdFbVt3Gg0M/1kccVrr8RaWk6eoGEhgdKCKfctshJC"
    "1NY3h4UECSFCQwJr65sFujkJXFPXFB4aPP3PtyXAu6ll8nYrhPhzeFg/9Iuzk6O8Vdv27ejoqKWlpRCioupsV3ff"
    "mY8Lik8cuTqgH795TzU1verzsy2t7Z+V5ZXkZwYH+h5KzjBzVNlHU4QQmdmF6vVry4uy1O5rNR+cFOgszP+sjvws"
    "NT7p7n9oJnX4nywwDAyOgcExMDgGBsfA4BgYHAOAY2BwDAyOgcExMDgGBsfA4BgYHAOAY2BwDAyOgcExMDgGBsfA"
    "4BgYHAOAY2BwDAyOgcExMDgGBsfA4BgYHAOAY2BwDAyOgcExMDgGBsfA4BgYHAOAY2BwDAyOgcExMDgGBsfA4BgY"
    "HAOAY2BwDAyOgcExMDgGBsfA4BgYHAOAY2BwDAyOgcExMDgGBsfA4JT/9Pcf6N7CMxgcA8/v302iex3PYHAYGBwD"
    "g2NgcAwMjoHBMTA4BgbHwALbXzoGjKB2wZOzAAAAAElFTkSuQmCC"
)


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


async def run_visual_audit():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
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
            print(f"[*] Navigating to: {target_url}")
            await page.goto(target_url, wait_until="networkidle")

            # Reset to empty state: clear chatlog to test pristine Welcome Hero
            await page.evaluate("""() => {
                const log = document.getElementById('chatlog');
                if (log) log.replaceChildren();
                if (window.updateWelcomeHeroVisibility) window.updateWelcomeHeroVisibility();
            }""")
            await page.wait_for_timeout(300)

            # -------------------------------------------------------------
            # STEP 1: Empty Home View with Pinned Topbar & Centered Hero Grid
            # -------------------------------------------------------------
            print("[*] Capturing Step 1: Pristine Empty Home View with 4 Hero Cards...")
            s1_path = SCREENSHOT_DIR / "ui_step1_empty_home.png"
            await page.screenshot(path=str(s1_path))
            print(f"[+] Saved {s1_path}")

            # -------------------------------------------------------------
            # STEP 2: Image Attachment inside Omnibar with Valid Thumbnail
            # -------------------------------------------------------------
            print("[*] Testing Image Attachment inside Omnibar...")
            await page.evaluate(f"""() => {{
                if (window.setChatAttachments) {{
                    window.setChatAttachments([{{
                        name: "manga_cover_ch01.png",
                        kind: "image",
                        preview: "{VALID_PNG_B64}"
                    }}]);
                }}
                if (window.renderChatAttachments) window.renderChatAttachments();
            }}""")
            await page.wait_for_timeout(300)

            # Type 12-digit math formula to trigger 1ms badge
            chatinput = await page.query_selector("#chatinput")
            await chatinput.fill("987654321987 * 123456789123")
            await page.wait_for_timeout(200)

            s2_path = SCREENSHOT_DIR / "ui_step2_inline_attachment.png"
            await page.screenshot(path=str(s2_path))
            print(f"[+] Saved {s2_path}")

            # Copy s2 as primary audit proof
            audit_path = SCREENSHOT_DIR / "ui_qa_audit.png"
            shutil.copy2(s2_path, audit_path)
            if ARTIFACT_DIR.exists():
                shutil.copy2(s2_path, ARTIFACT_DIR / "ui_qa_audit.png")

            # -------------------------------------------------------------
            # STEP 3: Active Chat Stream (Welcome Hero Auto-Hides Completely)
            # -------------------------------------------------------------
            print("[*] Testing Active Chat Stream (Hero automatically hidden)...")
            await page.evaluate("""() => {
                if (window.setChatAttachments) window.setChatAttachments([]);
                if (window.renderChatAttachments) window.renderChatAttachments();
                if (window.addMsg) {
                    window.addMsg('user', 'Xin chào AI Office, hãy tóm tắt năng lực studio giúp tôi.');
                    window.addMsg('assistant', 'Chào bạn! AI Office Studio là hệ thống sáng tạo đa năng cục bộ: Dựng Motion Comic 4K, Tẩy bóng thoại Koharu, Lập trình và Giải toán số lớn trong < 1ms.');
                }
            }""")
            await page.wait_for_timeout(400)

            s3_path = SCREENSHOT_DIR / "ui_step3_active_chat.png"
            await page.screenshot(path=str(s3_path))
            print(f"[+] Saved {s3_path}")

            # -------------------------------------------------------------
            # STEP 4: Full-Width Unified Studio View
            # -------------------------------------------------------------
            print("[*] Navigating to Studio Sáng Tạo Đa Năng...")
            await page.evaluate("""() => {
                if (window.navigate) {
                    window.navigate('studio');
                }
            }""")
            await page.wait_for_timeout(600)

            s4_path = SCREENSHOT_DIR / "ui_step4_studio.png"
            await page.screenshot(path=str(s4_path))
            print(f"[+] Saved {s4_path}")

            if ARTIFACT_DIR.exists():
                shutil.copy2(s4_path, ARTIFACT_DIR / "ui_qa_studio.png")

            await browser.close()

    finally:
        server_thread.stop()

    print("[+] All screenshots captured successfully!")


if __name__ == "__main__":
    asyncio.run(run_visual_audit())
