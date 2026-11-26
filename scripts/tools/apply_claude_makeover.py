"""Complete Claude-style UI/UX Makeover with Zero 'Chìm Chữ' (No Invisible Text).
Applies:
1. Two-column Claude layout (260px sleek sidebar + 1fr main chat).
2. Completely eliminates <aside class="right"> ('Tổng quan không gian làm việc'), footer statusbar, and redundant desktop menus.
3. Fixes ALL hardcoded colors to CSS variables so Dark and Light themes have 100% readable text.
4. Adds dual-theme switcher synced between Topbar and Sidebar.
"""
from pathlib import Path
import re

html_path = Path("app/ui/index.html")
content = html_path.read_text(encoding="utf-8")

# Backup original
backup_path = Path("app/ui/index.html.bak")
if not backup_path.exists():
    backup_path.write_text(content, encoding="utf-8")
    print(f"[+] Created backup at {backup_path}")

# =========================================================================
# 1. CSS SYSTEM: CLAUDE MINIMALISM & ZERO CHÌM CHỮ
# =========================================================================
claude_css = """
/* =========================================================================
   Claude-style Minimalist Theme & Layout System (Zero Invisible Text)
   ========================================================================= */

:root, body[data-theme="dark"] {
  color-scheme: dark;
  --bg: #18181b;
  --bg-sidebar: #131316;
  --bg-card: #222226;
  --bg-card-hover: #2a2a30;
  --bg-input: #1f1f23;
  --bg-user-msg: #27272a;
  --bg-ai-msg: transparent;
  --line: rgba(255, 255, 255, 0.08);
  --line-strong: rgba(255, 255, 255, 0.14);
  --text: #f4f4f5;
  --text-secondary: #d4d4d8;
  --text-muted: #a1a1aa;
  --text-dim: #71717a;
  --accent: #6366f1;
  --accent-hover: #4f46e5;
  --accent-light: rgba(99, 102, 241, 0.16);
  --card-border: rgba(255, 255, 255, 0.08);
  --card-shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
  --code-bg: #131316;
}

body[data-theme="light"] {
  color-scheme: light;
  --bg: #fcfbf8;
  --bg-sidebar: #f5f4ef;
  --bg-card: #ffffff;
  --bg-card-hover: #f0ede6;
  --bg-input: #ffffff;
  --bg-user-msg: #eeeae0;
  --bg-ai-msg: transparent;
  --line: rgba(0, 0, 0, 0.08);
  --line-strong: rgba(0, 0, 0, 0.16);
  --text: #18181b;
  --text-secondary: #3f3f46;
  --text-muted: #52525b;
  --text-dim: #71717a;
  --accent: #4f46e5;
  --accent-hover: #4338ca;
  --accent-light: rgba(79, 70, 229, 0.1);
  --card-border: rgba(0, 0, 0, 0.08);
  --card-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  --code-bg: #f3f2ee;
}

body {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--font-sans) !important;
  transition: background 0.2s ease, color 0.2s ease;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

/* Base typography inheritance - ZERO hardcoded white in light mode! */
strong, b, .strong {
  color: var(--text) !important;
  font-weight: 600 !important;
}

.brand, .hero-brand h1, .mc-card-title, .page-head h1, .view-card h2, .view-card h3 {
  color: var(--text) !important;
}

.subtle, .hero-brand p, .card-body p, .page-head p, .view-card p, .workspace-field span {
  color: var(--text-muted) !important;
}

.card-body strong {
  color: var(--text) !important;
}

/* App Layout Grid (Claude Two-Column) */
.app {
  height: 100vh !important;
  display: grid !important;
  grid-template-rows: 1fr !important;
  background: var(--bg) !important;
  overflow: hidden !important;
}

.body {
  min-height: 0 !important;
  height: 100% !important;
  display: grid !important;
  grid-template-columns: 260px minmax(0, 1fr) !important;
  overflow: hidden !important;
  background: var(--bg) !important;
  transition: grid-template-columns 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.body.hide-sidebar, .body.hide-explorer {
  grid-template-columns: 0px minmax(0, 1fr) !important;
}

.body.hide-sidebar .claude-sidebar,
.body.hide-explorer .claude-sidebar,
.body.hide-sidebar .explorer,
.body.hide-explorer .explorer {
  display: none !important;
}

/* HIDE UNWANTED CLUTTER: Right workspace inspector, footer statusbar, activity rail, tabs, menus */
nav.activity, .activity {
  display: none !important;
}

aside.right, .right {
  display: none !important;
}

footer.statusbar, .statusbar, footer.status, .status {
  display: none !important;
}

.tabs#app-tabs, .tabs {
  display: none !important;
}

header.menu, .quick {
  display: none !important;
}

/* =========================================================================
   CLAUDE SIDEBAR STYLING
   ========================================================================= */
.claude-sidebar {
  background: var(--bg-sidebar) !important;
  border-right: 1px solid var(--line) !important;
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
  padding: 12px 10px !important;
  box-sizing: border-box !important;
  overflow: hidden !important;
  user-select: none;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 12px 6px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-logo {
  width: 24px;
  height: 24px;
  border-radius: 6px;
}

.sidebar-brand-name {
  font-weight: 700;
  font-size: 15px;
  color: var(--text) !important;
  letter-spacing: -0.01em;
}

.panel-collapse-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel-collapse-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text);
}

.claude-new-chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  border-radius: 10px;
  background: var(--bg-card);
  border: 1px solid var(--line);
  color: var(--text);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  transition: all 0.15s ease;
  margin-bottom: 12px;
}
.claude-new-chat-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--line-strong);
}

.sidebar-nav-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
}

.sidebar-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border-radius: 8px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
}
.sidebar-nav-item:hover {
  background: var(--bg-card-hover);
  color: var(--text);
}
.sidebar-nav-item.active {
  background: var(--bg-card);
  color: var(--text);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.sidebar-divider {
  height: 1px;
  background: var(--line);
  margin: 6px 0 12px 0;
}

.claude-sidebar .history-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.claude-sidebar .history-heading {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim) !important;
  letter-spacing: 0.05em;
  padding: 0 6px 8px 6px;
  text-transform: uppercase;
}

.claude-sidebar .conversation-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-right: 2px;
}

.conversation-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 10px !important;
  border-radius: 8px !important;
  color: var(--text-secondary) !important;
  font-size: 13px !important;
  cursor: pointer;
  transition: all 0.15s ease;
}
.conversation-row:hover {
  background: var(--bg-card-hover) !important;
  color: var(--text) !important;
}
.conversation-row.active {
  background: var(--bg-card) !important;
  color: var(--text) !important;
  font-weight: 600 !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}
.conversation-item {
  color: inherit !important;
  text-decoration: none !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.sidebar-footer {
  padding-top: 10px;
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar-footer-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border-radius: 8px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.sidebar-footer-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text);
}

/* =========================================================================
   MAIN CHAT & TOPBAR (CLAUDE STYLE)
   ========================================================================= */
main.center {
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
  background: var(--bg) !important;
  overflow: hidden !important;
  position: relative;
}

.center-scroll {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  min-height: 0 !important;
  overflow: hidden !important;
}

.chat-topbar {
  height: 48px !important;
  padding: 0 20px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  border-bottom: 1px solid var(--line) !important;
  background: var(--bg) !important;
  color: var(--text) !important;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar-toggle-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sidebar-toggle-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text);
}

.topbar-model-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
}
.topbar-model-badge strong {
  color: var(--text) !important;
  font-weight: 600;
}
.subtle-dot {
  color: var(--text-dim);
}
.subtle-agent {
  color: var(--text-muted) !important;
  font-size: 12px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-pill, .topbar-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.tool-pill {
  background: var(--bg-card) !important;
  border: 1px solid var(--line) !important;
  color: var(--text-secondary) !important;
}
.tool-pill:hover {
  background: var(--bg-card-hover) !important;
  color: var(--text) !important;
  border-color: var(--line-strong) !important;
}

.topbar-pill-btn {
  background: var(--accent-light) !important;
  border: 1px solid var(--accent) !important;
  color: var(--text) !important;
}
.topbar-pill-btn:hover {
  background: var(--accent) !important;
  color: #ffffff !important;
}

/* =========================================================================
   CHAT STREAM & MESSAGES (CLAUDE BREATHING ROOM)
   ========================================================================= */
.chat {
  flex: 1 !important;
  overflow-y: auto !important;
  padding: 24px 20px !important;
  background: var(--bg) !important;
  display: flex !important;
  flex-direction: column !important;
}

.chat-thread {
  max-width: 820px !important;
  margin: 0 auto !important;
  width: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 20px !important;
}

.msg {
  display: flex !important;
  flex-direction: column !important;
  width: 100% !important;
  color: var(--text) !important;
  animation: fadeInMsg 0.15s ease-out;
}

@keyframes fadeInMsg {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg.user {
  align-items: flex-end !important;
  background: transparent !important;
  border: none !important;
}

.msg.user .msg-content {
  background: var(--bg-user-msg) !important;
  color: var(--text) !important;
  border: 1px solid var(--line) !important;
  border-radius: 20px 20px 4px 20px !important;
  padding: 12px 18px !important;
  max-width: min(85%, 680px) !important;
  font-size: 14.5px !important;
  line-height: 1.55 !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

.msg.assistant {
  align-items: flex-start !important;
  background: transparent !important;
  border: none !important;
}

.msg.assistant .msg-content {
  background: transparent !important;
  color: var(--text) !important;
  border: none !important;
  padding: 4px 0 !important;
  max-width: 100% !important;
  font-size: 15px !important;
  line-height: 1.65 !important;
}

.msg-content p, .msg-content li, .msg-content span {
  color: var(--text) !important;
}

.msg-content code {
  background: var(--code-bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--line) !important;
  padding: 2px 6px !important;
  border-radius: 5px !important;
  font-family: monospace;
  font-size: 13px;
}

.msg-content pre {
  background: var(--code-bg) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  padding: 14px 18px !important;
  overflow-x: auto;
}

.msg-content pre code {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

/* =========================================================================
   WELCOME HERO (CLAUDE STYLE)
   ========================================================================= */
.welcome-hero {
  max-width: 780px !important;
  margin: 30px auto auto auto !important;
  width: 100% !important;
  text-align: center;
}

.hero-brand {
  margin-bottom: 28px;
}

.hero-logo-wrap {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: var(--bg-card);
  border: 1px solid var(--line);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
  box-shadow: var(--card-shadow);
}

.hero-logo {
  width: 34px;
  height: 34px;
}

.hero-brand h1 {
  font-size: 24px !important;
  font-weight: 700 !important;
  color: var(--text) !important;
  letter-spacing: -0.02em;
  margin: 0 0 8px 0 !important;
}

.hero-brand p {
  font-size: 14px !important;
  color: var(--text-muted) !important;
  max-width: 580px;
  margin: 0 auto !important;
  line-height: 1.5;
}

.hero-action-grid {
  display: grid !important;
  grid-template-columns: repeat(2, 1fr) !important;
  gap: 12px !important;
  text-align: left;
}

.hero-card {
  display: flex !important;
  align-items: flex-start !important;
  gap: 12px !important;
  padding: 14px 16px !important;
  background: var(--bg-card) !important;
  border: 1px solid var(--card-border) !important;
  border-radius: 14px !important;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: var(--card-shadow) !important;
}
.hero-card:hover {
  background: var(--bg-card-hover) !important;
  border-color: var(--accent) !important;
  transform: translateY(-1px);
}

.card-icon {
  font-size: 20px;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-body strong {
  display: block;
  font-size: 13.5px !important;
  font-weight: 600 !important;
  color: var(--text) !important;
  margin-bottom: 3px;
}

.card-body p {
  font-size: 12px !important;
  color: var(--text-muted) !important;
  margin: 0 !important;
  line-height: 1.4;
}

/* =========================================================================
   OMNIBAR COMPOSER (CLAUDE FLOATING CAPSULE)
   ========================================================================= */
.composer {
  flex-shrink: 0;
  padding: 12px 20px 20px 20px !important;
  background: transparent !important;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.composer form {
  max-width: 820px !important;
  width: 100% !important;
  background: var(--bg-card) !important;
  border: 1px solid var(--line-strong) !important;
  border-radius: 20px !important;
  box-shadow: var(--card-shadow) !important;
  padding: 8px 12px !important;
  box-sizing: border-box;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.composer form:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 4px 28px rgba(99, 102, 241, 0.18) !important;
}

.composer-disclaimer {
  font-size: 11.5px;
  color: var(--text-dim);
  text-align: center;
  margin-top: 8px;
}

/* Smart Inline Attachment Preview */
.smart-inline-attachment {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  margin-bottom: 8px;
  border-radius: 10px;
  background: var(--bg-card-hover) !important;
  border: 1px solid var(--line) !important;
}

.inline-attach-thumb {
  width: 44px;
  height: 44px;
  border-radius: 6px;
  object-fit: cover;
}

.inline-attach-meta {
  flex: 1;
  min-width: 0;
}

.inline-attach-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text) !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inline-attach-chips {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.inline-attach-chip {
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--line);
  color: var(--text-secondary);
}

.inline-attach-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}
.inline-attach-close:hover {
  background: var(--bg-card);
  color: var(--text);
}

.composer-row-main {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.attach-clip-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.attach-clip-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text);
}

.composer textarea.field {
  flex: 1;
  background: transparent !important;
  border: none !important;
  color: var(--text) !important;
  font-size: 14.5px !important;
  line-height: 1.5 !important;
  resize: none !important;
  outline: none !important;
  padding: 6px 8px !important;
  max-height: 200px !important;
  min-height: 24px !important;
  box-shadow: none !important;
}

.composer textarea.field::placeholder {
  color: var(--text-dim) !important;
}

.send-arrow-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--accent) !important;
  border: none !important;
  color: #ffffff !important;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.send-arrow-btn:hover {
  background: var(--accent-hover) !important;
  transform: scale(1.05);
}

/* =========================================================================
   STUDIO & DYNAMIC PAGES (HIGH CONTRAST & READABILITY)
   ========================================================================= */
#page-studio, #dynamic-page {
  background: var(--bg) !important;
  color: var(--text) !important;
  padding: 24px 30px !important;
  overflow-y: auto !important;
}

.mc-card, .view-card {
  background: var(--bg-card) !important;
  border: 1px solid var(--card-border) !important;
  color: var(--text) !important;
  border-radius: 16px !important;
  box-shadow: var(--card-shadow) !important;
}

.field, select.field, input.field {
  background: var(--bg-input) !important;
  border: 1px solid var(--line) !important;
  color: var(--text) !important;
  border-radius: 8px !important;
}

.field:focus, select.field:focus, input.field:focus {
  border-color: var(--accent) !important;
}
"""

# Replace old injected claude theme or insert before </head>
if "/* Claude-style Minimalist Theme System" in content:
    content = re.sub(
        r'/\* =+ \s*Claude-style Minimalist Theme System.*?</style></head>',
        claude_css + "\n</style></head>",
        content,
        flags=re.DOTALL
    )
    print("[+] Updated Claude CSS block")
else:
    content = content.replace("</style></head>", claude_css + "\n</style></head>")
    print("[+] Injected Claude CSS block")

# =========================================================================
# 2. REDESIGN ASIDE.EXPLORER TO CLAUDE SIDEBAR
# =========================================================================
old_explorer = re.search(r'<aside class="explorer">.*?</aside>', content, re.DOTALL)
if old_explorer:
    new_explorer = """<aside class="explorer claude-sidebar">
  <div class="sidebar-header">
    <div class="sidebar-brand">
      <img src="/assets/ai-office-icon.png" alt="AI Office" class="sidebar-logo">
      <span class="sidebar-brand-name">AI Office</span>
    </div>
    <button class="panel-collapse-btn" type="button" title="Thu gọn thanh bên" data-layout-toggle="explorer">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
    </button>
  </div>

  <div class="sidebar-new-chat-wrap">
    <button type="button" id="new-conversation-btn" class="claude-new-chat-btn" title="Bắt đầu cuộc trò chuyện mới">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
      <span>Cuộc trò chuyện mới</span>
    </button>
  </div>

  <nav class="sidebar-nav-items">
    <button type="button" class="sidebar-nav-item active" data-view="home">
      <span class="nav-icon">💬</span> <span>Trò chuyện</span>
    </button>
    <button type="button" class="sidebar-nav-item" data-view="studio">
      <span class="nav-icon">🎬</span> <span>Studio Sáng tạo</span>
    </button>
    <button type="button" class="sidebar-nav-item" data-view="workspace">
      <span class="nav-icon">💻</span> <span>Workspace</span>
    </button>
  </nav>

  <div class="sidebar-divider"></div>

  <section class="history-panel">
    <div class="history-heading">
      <span>GẦN ĐÂY</span>
    </div>
    <div id="conversation-list" class="conversation-list">
      <div class="history-empty">Đang tải lịch sử...</div>
    </div>
  </section>

  <!-- Invisible DOM nodes for backward JS compatibility -->
  <div style="display:none">
    <button id="new-project-btn"></button>
    <div id="project-list"></div>
    <div class="tree"></div>
  </div>

  <div class="sidebar-footer">
    <button type="button" class="sidebar-footer-btn" id="btn-theme-toggle-sidebar" title="Chuyển đổi Sáng / Tối">
      <span id="sidebar-theme-icon">🌙</span> <span id="sidebar-theme-text">Giao diện tối</span>
    </button>
    <button type="button" class="sidebar-footer-btn" data-view="settings" title="Cài đặt hệ thống">
      <span>⚙️</span> <span>Cài đặt</span>
    </button>
  </div>
</aside>"""
    content = content.replace(old_explorer.group(0), new_explorer)
    print("[+] Replaced explorer with clean Claude sidebar")

# =========================================================================
# 3. REDESIGN CHAT TOPBAR (CLEAN, SINGLE HEADER)
# =========================================================================
# Match and replace whatever is currently in the topbar region down to <section class="chat"
topbar_region = re.search(r'<div class="chat-topbar" id="chat-topbar">.*?<section class="chat"', content, re.DOTALL)
if topbar_region:
    new_topbar_region = """<div class="chat-topbar" id="chat-topbar">
  <div class="topbar-left">
    <button class="sidebar-toggle-btn" type="button" title="Mở/Đóng thanh bên" data-layout-toggle="explorer">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <div class="topbar-model-badge">
      <strong>AI Office</strong>
      <span class="subtle-dot">·</span>
      <span class="subtle-agent">Claude Minimal · Cục bộ</span>
    </div>
  </div>
  <div class="topbar-right">
    <button type="button" class="tool-pill" id="btn-theme-toggle" title="Chuyển đổi Giao diện Sáng / Tối">
      <span id="theme-toggle-icon">🌙</span> <span id="theme-toggle-text">Tối</span>
    </button>
    <button type="button" class="topbar-pill-btn" id="topbar-open-studio" title="Mở Studio Sáng Tạo Đa Năng">
      <span>🎬</span> <span>Studio Sáng tạo</span>
    </button>
    <button type="button" class="tool-pill" id="topbar-open-workspace" title="Mở Không gian Workspace">
      <span>💻</span> <span>Workspace</span>
    </button>
  </div>
</div>
<section class="chat\""""
    content = content.replace(topbar_region.group(0), new_topbar_region)
    print("[+] Cleaned up topbar region and removed duplicates")

# =========================================================================
# 4. HIDE ASIDE.RIGHT AND FOOTER.STATUSBAR IN HTML
# =========================================================================
content = re.sub(r'<aside class="right">', '<aside class="right" style="display:none !important;" hidden>', content)
content = re.sub(r'<footer class="statusbar">', '<footer class="statusbar" style="display:none !important;" hidden>', content)
print("[+] Permanently hid aside.right and footer.statusbar")

# =========================================================================
# 5. SYNC THEME SWITCHER LOGIC
# =========================================================================
# Make sure toggleTheme syncs both topbar and sidebar toggle buttons
theme_sync_js = """
  // Dual-Theme Sync Switcher (Zero Chìm Chữ)
  window.setTheme = function(theme) {
    const value = theme === 'light' ? 'light' : 'dark';
    document.body.dataset.theme = value;
    try { localStorage.setItem('aioffice.theme', value); } catch {}
    updateAllThemeUI(value);
  };

  window.toggleTheme = function() {
    const cur = document.body.dataset.theme || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    window.setTheme(next);
  };

  function updateAllThemeUI(theme) {
    // Topbar
    const icon1 = byId('theme-toggle-icon');
    const text1 = byId('theme-toggle-text');
    if (icon1 && text1) {
      icon1.textContent = theme === 'light' ? '☀️' : '🌙';
      text1.textContent = theme === 'light' ? 'Sáng' : 'Tối';
    }
    // Sidebar
    const icon2 = byId('sidebar-theme-icon');
    const text2 = byId('sidebar-theme-text');
    if (icon2 && text2) {
      icon2.textContent = theme === 'light' ? '☀️' : '🌙';
      text2.textContent = theme === 'light' ? 'Giao diện sáng' : 'Giao diện tối';
    }
    document.querySelectorAll('[data-theme-choice]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.themeChoice === theme));
    });
  }

  // Hook event listeners
  byId('btn-theme-toggle')?.addEventListener('click', () => window.toggleTheme());
  byId('btn-theme-toggle-sidebar')?.addEventListener('click', () => window.toggleTheme());
  byId('topbar-open-studio')?.addEventListener('click', () => navigate('studio'));
  byId('topbar-open-workspace')?.addEventListener('click', () => navigate('workspace'));

  // Initial theme sync
  setTimeout(() => {
    let saved = 'dark';
    try { saved = localStorage.getItem('aioffice.theme') || 'dark'; } catch {}
    window.setTheme(saved);
  }, 50);
"""

# Replace or inject toggleTheme
if "function toggleTheme()" in content or "window.toggleTheme = function()" in content:
    content = re.sub(
        r'// Instant Theme Switcher.*?</script>\s*</body>',
        theme_sync_js + "\n})();\n</script>\n</body>",
        content,
        flags=re.DOTALL
    )
    print("[+] Replaced theme sync JS")
else:
    content = content.replace("})();\n</script>\n</body>", theme_sync_js + "\n})();\n</script>\n</body>")
    print("[+] Appended theme sync JS")

html_path.write_text(content, encoding="utf-8")
print("[+] Full Claude Makeover applied successfully to app/ui/index.html!")
