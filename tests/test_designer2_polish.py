import os
from playwright.sync_api import sync_playwright

BASE = os.getenv("AI_OFFICE_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def main():
    console_warnings = []
    console_errors = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=EDGE, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1426, "height": 900})
        
        page.on("console", lambda msg: (
            console_errors.append(msg.text) if msg.type == "error" else
            console_warnings.append(msg.text) if msg.type == "warning" else None
        ))
        
        response = page.goto(BASE, wait_until="networkidle", timeout=20_000)
        assert response and response.status == 200, "Page failed to load"
        page.wait_for_timeout(1000)

        print("=== Test 1: Chat Header VTuber Dock ===")
        dock = page.locator("#chat-vtuber-dock")
        assert dock.is_visible(), "Mini VTuber dock should be visible in chat header"
        name_text = page.locator("#chathead-vtuber-name").text_content()
        status_text = page.locator("#chathead-vtuber-mood").text_content()
        print(f"VTuber dock visible: name='{name_text}', status='{status_text}'")

        print("=== Test 2: Suggestion Bar Logic (Empty vs Non-Empty) ===")
        suggest = page.locator(".suggest")
        # On load with existing messages, .suggest should be hidden
        assert not suggest.is_visible(), ".suggest should be hidden when conversation has messages"
        print("Existing conversation with messages: .suggest is hidden (PASS)")

        # Create new conversation (empty / greeting only) -> .suggest should become visible
        page.locator('#new-conversation-btn').click()
        page.wait_for_timeout(600)
        assert suggest.is_visible(), ".suggest should be visible when conversation is new/empty greeting only"
        print("New empty conversation with greeting: .suggest is visible (PASS)")

        print("=== Test 3: Markdown Rendering & Suggestion Hiding ===")
        # Inject an assistant message with markdown formatting
        md_text = "Hôm nay là **thứ Năm, ngày 19/11/2026**.\nHãy chạy `aioffice --status` để kiểm tra.\n```python\ndef greet():\n    return 'Hello'\n```"
        page.evaluate("""(text) => {
            addMsg('user', 'Master hỏi ngày giờ');
            addMsg('assistant', text);
        }""", md_text)
        page.wait_for_timeout(500)

        # Check markdown rendered tags
        last_msg = page.locator("#chatlog .msg.assistant").last
        bold_el = last_msg.locator("strong")
        assert bold_el.count() >= 1, "Bold <strong> should exist"
        assert bold_el.first.text_content() == "thứ Năm, ngày 19/11/2026", f"Bold text mismatch: {bold_el.first.text_content()}"
        print(f"Bold rendered correctly: <strong>{bold_el.first.text_content()}</strong>")

        code_el = last_msg.locator("code:not(pre code)")
        assert code_el.count() >= 1, "Inline <code> should exist"
        assert code_el.first.text_content() == "aioffice --status"
        print(f"Inline code rendered correctly: <code>{code_el.first.text_content()}</code>")

        pre_code = last_msg.locator("pre code")
        assert pre_code.count() >= 1, "Fenced code block <pre><code> should exist"
        print(f"Code block rendered correctly: <pre><code>...</code></pre>")

        # Check suggestion bar is now hidden
        assert not suggest.is_visible(), ".suggest should be HIDDEN after messages exist"
        print("After messages exist .suggest visibility: HIDDEN (PASS)")

        print("=== Test 4: Message Action Buttons Styling ===")
        action_btn = last_msg.locator(".msg-action").first
        assert action_btn.is_visible(), "Action button should exist"
        btn_style = action_btn.evaluate("""(el) => {
            const s = window.getComputedStyle(el);
            return {
                bg: s.backgroundColor,
                color: s.color,
                borderRadius: s.borderRadius,
                fontSize: s.fontSize,
                border: s.border
            };
        }""")
        print("Action button styles:", btn_style)
        assert btn_style["bg"] in ["rgba(0, 0, 0, 0)", "transparent"], f"Background should be transparent, got {btn_style['bg']}"
        assert btn_style["borderRadius"] == "4px", f"Border radius should be 4px, got {btn_style['borderRadius']}"
        assert btn_style["fontSize"] == "11px", f"Font size should be 11px, got {btn_style['fontSize']}"
        print("Ghost button styling: PASS")

        print("=== Test 5: Sidebar Action Icons & Tooltips ===")
        page.locator('#new-conversation-btn').click()
        page.wait_for_timeout(500)
        row = page.locator(".conversation-row").first
        actions = row.locator(".conversation-action")
        assert actions.count() >= 2, "Conversation row should have at least 2 action buttons (pin and menu)"
        pin_btn = actions.first
        menu_btn = actions.nth(1)
        assert pin_btn.locator("svg").count() == 1, "Pin button should contain SVG icon"
        assert menu_btn.locator("svg").count() == 1, "Menu button should contain SVG icon"
        assert pin_btn.get_attribute("title") in ["Ghim cuộc trò chuyện", "Bỏ ghim"], "Pin button should have tooltip"
        assert menu_btn.get_attribute("title") == "Tùy chọn cuộc trò chuyện", "Menu button should have tooltip"
        print("Sidebar SVG icons and tooltips: PASS")

        print("=== Test 6: Game & VTuber View and Live2D Warning Check ===")
        console_warnings.clear()
        page.locator('.act[data-view="game"]').click()
        page.wait_for_selector(".vtuber-stage", timeout=15_000)
        page.wait_for_timeout(1500)

        zero_size_warnings = [w for w in console_warnings if "zero size" in w.lower() or "1x1" in w.lower()]
        print("Zero size warnings captured:", zero_size_warnings)
        assert len(zero_size_warnings) == 0, f"Found unexpected 1x1 zero size warning: {zero_size_warnings}"
        print("Live2D 1x1 zero size warning check: PASS (0 warnings)")

        # Test dock navigation from chat
        page.locator('.act[data-view="home"]').click()
        page.wait_for_timeout(500)
        page.locator("#chat-vtuber-dock").click()
        page.wait_for_selector(".vtuber-stage", timeout=15_000)
        print("Chat VTuber dock click navigation: PASS")

        browser.close()
        print("\nALL 5 REQUIREMENTS FULLY VERIFIED AND PASSING!")

if __name__ == "__main__":
    main()
