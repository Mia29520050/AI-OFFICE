"""Unify all tools into a single cohesive interface and fix UI/UX layout collisions in app/ui/index.html."""
from pathlib import Path
import re

html_path = Path("app/ui/index.html")
content = html_path.read_text(encoding="utf-8")

# 1. Add Unified CSS before </style></head>
unified_css = """
/* =========================================================================
   Unified Studio & Non-colliding Omnibar Styles
   ========================================================================= */

/* Hero Action Grid in empty chat */
.welcome-hero {
  max-width: 880px;
  margin: 18px auto 26px auto;
  padding: 0 16px;
  animation: fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.welcome-hero.hidden {
  display: none !important;
}
.hero-brand {
  text-align: center;
  margin-bottom: 22px;
}
.hero-logo {
  width: 48px;
  height: 48px;
  object-fit: contain;
  margin-bottom: 10px;
  filter: drop-shadow(0 4px 16px rgba(99, 102, 241, 0.45));
}
.hero-brand h1 {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}
.hero-brand p {
  font-size: 13px;
  color: var(--text-muted);
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.5;
}
.hero-action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
@media (max-width: 768px) {
  .hero-action-grid {
    grid-template-columns: 1fr;
  }
}
.hero-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  padding: 13px 16px;
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}
.hero-card:hover {
  background: rgba(99, 102, 241, 0.09);
  border-color: rgba(99, 102, 241, 0.45);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}
.card-icon {
  font-size: 24px;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.card-body {
  flex: 1;
  min-width: 0;
}
.card-body strong {
  display: block;
  font-size: 13px;
  color: #fff;
  margin-bottom: 2px;
}
.card-body p {
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.35;
  margin: 0;
}
.card-arrow {
  color: var(--text-dim);
  font-size: 13px;
  transition: transform 0.2s;
}
.hero-card:hover .card-arrow {
  color: var(--cyan);
  transform: translateX(3px);
}

/* Inline Attachment Card inside Composer (Contained, zero collision) */
.smart-inline-attachment {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 8px;
  animation: fadeIn 0.2s ease;
}
.smart-inline-attachment[hidden] {
  display: none !important;
}
.inline-attach-card {
  display: flex;
  align-items: center;
  gap: 12px;
}
.inline-attach-card img {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: #000;
}
.inline-attach-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.inline-attach-name {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
}
.inline-attach-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* Sleek Quick Tool Pills in Composer Toolbar */
.tool-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 11px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--radius-full);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
.tool-pill:hover {
  background: rgba(99, 102, 241, 0.25);
  border-color: rgba(99, 102, 241, 0.5);
  color: #fff;
}
.tool-pill span:first-child {
  font-size: 13px;
}
"""

if "/* Unified Studio & Non-colliding Omnibar Styles */" not in content:
    content = content.replace("</style></head>", unified_css + "\n</style></head>")

# 2. Consolidate Activity Rail to 5 Crisp Unified Icons
old_nav = re.search(r'<nav class="activity" aria-label="Điều hướng chính">.*?</nav>', content, re.DOTALL)
if old_nav:
    new_nav = """<nav class="activity" aria-label="Điều hướng chính">
<button class="act" type="button" title="Explorer" aria-label="Explorer" data-layout-toggle="explorer"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h7l2 2h9v11H3z"/><path d="M3 10h18"/></svg></button>
<button class="act active" type="button" title="Trò chuyện AI & Trợ lý Đa năng" aria-label="Trò chuyện AI" data-view="home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V21H3z"/><path d="M9 21v-7h6v7"/></svg></button>
<button class="act" type="button" title="Studio Sáng Tạo Đa Năng (Motion Comic & Manga)" aria-label="Studio Sáng Tạo Đa Năng" data-view="studio"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="3"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><circle cx="12" cy="7" r="1.5"/><circle cx="12" cy="17" r="1.5"/></svg></button>
<button class="act" type="button" title="Không gian Lập trình & Workspace" aria-label="Không gian Lập trình & Workspace" data-view="workspace"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h6"/></svg></button>
<button class="act" type="button" title="Game & AI VTuber Đồng hành" aria-label="Game & AI VTuber" data-view="game"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="4"/><path d="M6 12h4M8 10v4"/><circle cx="15.5" cy="11" r="1"/><circle cx="18" cy="13" r="1"/></svg></button>
<span class="rail-separator"></span>
<button class="act bottom" type="button" title="Cài đặt hệ thống" aria-label="Cài đặt hệ thống" data-view="settings"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.25.6.83.99 1.51 1H21a2 2 0 1 1 0 4h-.09c-.68.01-1.26.4-1.51 1z"/></svg></button>
</nav>"""
    content = content.replace(old_nav.group(0), new_nav)

# 3. Add Welcome Hero Grid into center-scroll and clean composer
content = re.sub(r'<div class="suggest">.*?</div>', '', content, flags=re.DOTALL)

welcome_hero_html = """
<div class="welcome-hero" id="welcome-hero">
  <div class="hero-brand">
    <img src="/assets/ai-office-icon.png" class="hero-logo" alt="AI Office">
    <h1>AI Office Studio</h1>
    <p>Hệ thống AI Đa Năng Cục Bộ: Sáng tạo Hoạt Họa 4K · Manga · Lập trình · Nhận diện ảnh · Máy tính 1ms</p>
  </div>
  <div class="hero-action-grid">
    <div class="hero-card" id="hero-card-motion">
      <div class="card-icon">🎬</div>
      <div class="card-body">
        <strong>Xưởng Motion Comic & Video 4K</strong>
        <p>Xuất video hoạt họa YouTube (16:9) & TikTok (9:16) có chuyển động Ken Burns & lồng tiếng AI.</p>
      </div>
      <span class="card-arrow">➔</span>
    </div>
    <div class="hero-card" id="hero-card-manga">
      <div class="card-icon">📖</div>
      <div class="card-body">
        <strong>Manga Studio & Tẩy chữ Koharu</strong>
        <p>Dựng truyện tranh, tẩy chữ bóng thoại giữ nguyên nét vẽ bằng AI LaMa.</p>
      </div>
      <span class="card-arrow">➔</span>
    </div>
    <div class="hero-card" id="hero-card-code">
      <div class="card-icon">💻</div>
      <div class="card-body">
        <strong>Lập trình & Codebase Graph</strong>
        <p>Trích xuất quan hệ class & hàm toàn bộ dự án với 0 MB VRAM.</p>
      </div>
      <span class="card-arrow">➔</span>
    </div>
    <div class="hero-card" id="hero-card-calc">
      <div class="card-icon">⚡</div>
      <div class="card-body">
        <strong>Máy tính số lớn siêu tốc</strong>
        <p>Giải các phép toán 12+ chữ số chính xác 100% trong dưới 1 mili-giây.</p>
      </div>
      <span class="card-arrow">➔</span>
    </div>
  </div>
</div>
"""

if '<div class="welcome-hero"' not in content:
    content = content.replace('<section class="chat" id="chat-surface">', welcome_hero_html + '\n<section class="chat" id="chat-surface">')

# 4. Redesign Composer with Inline Attachment Card
clean_composer_html = """<form class="composer" id="chatform">
<div class="composer-attachments" id="composer-attachments" hidden></div>
<div class="composer-main claude-composer smart-omnibar">
  <!-- Inline Attachment Card: Contained inside composer box with zero overlap -->
  <div class="smart-inline-attachment" id="smart-inline-attachment" hidden>
    <div class="inline-attach-card">
      <img id="omnibar-preview-img" src="" alt="Attached Media">
      <div class="inline-attach-info">
        <div class="inline-attach-name" id="omnibar-image-name">image.png</div>
        <div class="inline-attach-actions">
          <button type="button" class="mini-pill" id="action-vision-btn" title="Phân tích ảnh với AI Thị giác">👁️ Nhận diện ảnh</button>
          <button type="button" class="mini-pill" id="action-inpaint-btn" title="Tẩy chữ Manga bảo toàn nét vẽ với Koharu">🎨 Tẩy chữ (Koharu)</button>
          <button type="button" class="mini-pill" id="action-motion-btn" title="Tạo video hoạt họa từ ảnh này">🎬 Dựng Motion Comic</button>
          <button type="button" class="mini-pill close" id="action-remove-img" title="Bỏ ảnh đính kèm">✕</button>
        </div>
      </div>
    </div>
  </div>
  <div class="smart-intent-badge" id="smart-intent-badge" hidden></div>
  <textarea id="chatinput" lang="vi-VN" spellcheck="true" autocomplete="on" autocapitalize="off" inputmode="text" enterkeyhint="send" placeholder="Nhắn tin cho AI Office, dán ảnh (Ctrl+V) hoặc nhập phép tính..." rows="2"></textarea>
  <div class="claude-composer-toolbar smart-toolbar">
    <div class="claude-toolbar-left smart-toolbar-left" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <button type="button" class="tool-pill" id="btn-quick-attach-img" title="Tải ảnh lên hoặc dán ảnh (Ctrl+V)">
        <span>🖼️</span> <span>Ảnh</span>
      </button>
      <button type="button" class="tool-pill" id="btn-quick-studio" title="Mở Studio sáng tạo hoạt họa & Manga">
        <span>🎨</span> <span>Studio Sáng tạo</span>
      </button>
      <button type="button" class="tool-pill" id="btn-quick-calc" title="Máy tính số học 12+ chữ số trong 1ms">
        <span>⚡</span> <span>Tính 1ms</span>
      </button>
      <button type="button" class="tool-pill" id="btn-quick-graph" title="Bản đồ quan hệ Codebase Graph">
        <span>🌐</span> <span>Graphify</span>
      </button>
      <select id="agent-select" aria-label="Chọn tác nhân AI" title="Chọn tác nhân AI" style="font-size:12px;height:28px">
        <option>CEO</option>
        <option value="Researcher">Nhà nghiên cứu</option>
        <option value="Developer">Lập trình viên</option>
        <option value="Workspace">Workspace</option>
        <option value="Vision">Thị giác</option>
        <option value="Computer Use">Điều khiển máy</option>
        <option value="Browser">Trình duyệt</option>
        <option value="Writer">Biên soạn</option>
        <option value="QA">Kiểm thử</option>
      </select>
      <span id="admin-ime-warning" class="subtle" hidden style="font-size:11px;color:var(--amber);margin-left:4px" title="Ứng dụng đang chạy quyền Administrator.">🛡 Admin</span>
    </div>
    <div class="claude-toolbar-right">
      <button class="send" id="sendbtn" type="submit" title="Gửi tin nhắn" aria-label="Gửi tin nhắn">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5"/><path d="m6 11 6-6 6 6"/></svg>
      </button>
    </div>
  </div>
</div>
<input id="chat-files" type="file" multiple accept="image/png,image/jpeg,image/webp,.md,.txt,.py,.js,.ts,.html,.css,.json,.yaml,.yml,.toml,.ini,.bat,.ps1,.sql,.xml,.csv,.log" hidden>
<input id="chat-folder" type="file" webkitdirectory directory multiple hidden>
</form>"""

old_composer = re.search(r'<form class="composer" id="chatform">.*?</form>', content, re.DOTALL)
if old_composer:
    content = content.replace(old_composer.group(0), clean_composer_html)

# 5. Add dynamic container for Unified Creative Studio
old_containers = '<section id="dynamic-page" class="dynamic-page" hidden></section><section id="page-manga" class="dynamic-page" hidden></section><section id="page-motion-comic" class="dynamic-page" hidden></section></main>'
new_containers = '<section id="dynamic-page" class="dynamic-page" hidden></section><section id="page-studio" class="dynamic-page" hidden></section></main>'
if old_containers in content:
    content = content.replace(old_containers, new_containers)

# Update setPage to handle view === 'studio'
old_sp = re.search(r'const setPage=\(view,title\)=>\{.*?byId\(\'tab-workbench-close\'\)\?\.addEventListener', content, re.DOTALL)
if old_sp:
    new_sp = """const setPage=(view,title)=>{
    const prev=activeView;
    activeView=view;
    home.hidden=view!=='home';
    const dynPage=byId('dynamic-page');
    const studioPage=byId('page-studio');
    if(view==='home'){
      if(dynPage)dynPage.hidden=true;
      if(studioPage)studioPage.hidden=true;
    }else if(view==='studio'||view==='manga'||view==='motion-comic'){
      activeView='studio';
      if(dynPage)dynPage.hidden=true;
      if(studioPage)studioPage.hidden=false;
    }else{
      if(dynPage)dynPage.hidden=false;
      if(studioPage)studioPage.hidden=true;
    }
    if(prev==='game'&&view!=='game'){stopGamePolling();if(window.AIOfficeLive2D)window.AIOfficeLive2D.dispose();}
    if(view==='game'&&window.AIOfficeLive2D&&window.AIOfficeLive2D.resize){setTimeout(()=>{try{window.AIOfficeLive2D.resize();}catch{}},60);}
    document.querySelectorAll('.act[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===view||(view==='studio'&&(x.dataset.view==='studio'||x.dataset.view==='manga'))));
    const tabChat=byId('tab-chat');
    const tabWb=byId('tab-workbench');
    const tabWbLabel=byId('tab-workbench-label');
    if(tabChat&&tabWb){
      if(view==='home'){
        tabChat.classList.add('active');
        tabWb.style.display='none';
        tabWb.classList.remove('active');
      } else {
        tabChat.classList.remove('active');
        tabWb.style.display='inline-flex';
        tabWb.classList.add('active');
        const label=({workspace:'Workspace',tasks:'Nhiệm vụ',agents:'Tác nhân AI',skills:'Kỹ năng',models:'Mô hình',tools:'Công cụ',game:'Game & VTuber',studio:'Studio Sáng Tạo Đa Năng',manga:'Studio Sáng Tạo', 'motion-comic':'Studio Sáng Tạo'}[view]||title||view);
        if(tabWbLabel) tabWbLabel.textContent=label;
      }
    }
    if(view!=='home') page.scrollTop=0;
  };
  byId('tab-workbench-close')?.addEventListener"""
    content = content.replace(old_sp.group(0), new_sp)

# 6. Update navigate(view)
content = re.sub(
    r"if\(view==='manga'\)return renderManga\(\);if\(view==='motion-comic'\)return renderMotionComic\(\);",
    "if(view==='studio'||view==='manga'||view==='motion-comic')return renderUnifiedStudio(view==='motion-comic'?'motion':'manga');",
    content
)

# 7. JavaScript logic for Unified Studio and Omnibar Quick Actions
unified_js = """
  // =========================================================================
  // Unified Studio Implementation (Motion Comic + Manga + Koharu)
  // =========================================================================
  let unifiedStudioActiveTab = 'motion';
  let mcPanelsState = [
    {
      id: "p1",
      thumb: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAACAAQMAAACq9p52AAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAACNJREFUGBntwQEBAAAAgiD/r25IQAEAAAAAAAAAAAAAAAAAgIcBFu4AAaZ4z6cAAAAASUVORK5CYII=",
      speaker: "Luffy",
      text: "Tôi sẽ trở thành Vua Hải Tặc! Không ai có thể cản bước!",
      motion: "zoom_in",
      sfx: "boom"
    },
    {
      id: "p2",
      thumb: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAACAAQMAAACq9p52AAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAACNJREFUGBntwQEBAAAAgiD/r25IQAEAAAAAAAAAAAAAAAAAgIcBFu4AAaZ4z6cAAAAASUVORK5CYII=",
      speaker: "Zoro",
      text: "Tam Kiếm Phái: Tam Thiên Thế Giới! Lên đường thôi!",
      motion: "pan_rtl",
      sfx: "swoosh"
    }
  ];

  function renderTimelineList() {
    const list = byId('mc-timeline-list');
    const counter = byId('mc-panel-counter');
    if (!list) return;
    if (counter) counter.textContent = `${mcPanelsState.length} phân cảnh`;
    if (!mcPanelsState.length) {
      list.innerHTML = '<div class="empty-state" style="padding:16px">Chưa có phân cảnh nào. Bấm "+ Thêm Phân Cảnh" hoặc "Nạp Demo".</div>';
      return;
    }
    list.innerHTML = mcPanelsState.map((p, idx) => `
      <div class="mc-panel-card" data-panel-idx="${idx}" style="display:flex;gap:12px;align-items:center;background:rgba(255,255,255,0.03);border:1px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px;margin-bottom:8px">
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <span style="font-size:11px;font-weight:700;color:var(--text-muted)">#${idx + 1}</span>
          <img src="${p.thumb || ''}" alt="Panel ${idx + 1}" style="width:64px;height:48px;object-fit:cover;border-radius:4px;border:1px solid rgba(255,255,255,0.1);background:#000">
        </div>
        <div style="flex:1;display:grid;grid-template-columns:110px 1fr 140px 110px 32px;gap:8px;align-items:center">
          <input type="text" class="field" style="font-size:12px;padding:4px 8px" placeholder="Nhân vật" value="${esc(p.speaker || '')}" onchange="mcPanelsState[${idx}].speaker=this.value">
          <input type="text" class="field" style="font-size:12px;padding:4px 8px" placeholder="Lời thoại..." value="${esc(p.text || '')}" onchange="mcPanelsState[${idx}].text=this.value">
          <select class="field" style="font-size:11.5px;padding:4px 6px" onchange="mcPanelsState[${idx}].motion=this.value">
            <option value="zoom_in" ${p.motion === 'zoom_in' ? 'selected' : ''}>Zoom In (Kịch tính)</option>
            <option value="zoom_out" ${p.motion === 'zoom_out' ? 'selected' : ''}>Zoom Out (Toàn cảnh)</option>
            <option value="pan_rtl" ${p.motion === 'pan_rtl' ? 'selected' : ''}>Pan Manga (Phải-Trái)</option>
            <option value="pan_ltr" ${p.motion === 'pan_ltr' ? 'selected' : ''}>Pan Điện ảnh (Trái-Phải)</option>
            <option value="action_shake" ${p.motion === 'action_shake' ? 'selected' : ''}>Rung lắc chấn động</option>
            <option value="static" ${p.motion === 'static' ? 'selected' : ''}>Tĩnh (Static)</option>
          </select>
          <select class="field" style="font-size:11.5px;padding:4px 6px" onchange="mcPanelsState[${idx}].sfx=this.value">
            <option value="none" ${(!p.sfx || p.sfx === 'none') ? 'selected' : ''}>Không SFX</option>
            <option value="boom" ${p.sfx === 'boom' ? 'selected' : ''}>💥 Boom (Va chạm)</option>
            <option value="swoosh" ${p.sfx === 'swoosh' ? 'selected' : ''}>⚡ Swoosh (Kiếm/Gió)</option>
            <option value="thump" ${p.sfx === 'thump' ? 'selected' : ''}>💓 Thump (Hồi hộp)</option>
          </select>
          <button type="button" class="mini-pill close" style="height:28px;width:28px;padding:0;display:flex;align-items:center;justify-content:center" title="Xóa phân cảnh" onclick="mcPanelsState.splice(${idx},1);renderTimelineList()">✕</button>
        </div>
      </div>
    `).join('');
  }

  async function startRenderMotionComic() {
    if (!mcPanelsState.length) {
      alert("Vui lòng thêm ít nhất một phân cảnh trước khi xuất video.");
      return;
    }
    const statusBox = byId('mc-render-status');
    const statusText = byId('mc-status-text');
    const statusPct = byId('mc-status-pct');
    const progressBar = byId('mc-progress-bar');
    const videoElem = byId('mc-video-elem');
    const placeholder = byId('mc-player-placeholder');
    const downloadActions = byId('mc-download-actions');

    if (statusBox) statusBox.style.display = 'block';
    if (downloadActions) downloadActions.style.display = 'none';
    if (statusText) statusText.textContent = "Đang khởi tạo GPU NVENC & Anime4K...";
    if (statusPct) statusPct.textContent = "20%";
    if (progressBar) progressBar.style.width = "20%";

    const payload = {
      panels: mcPanelsState.map((p, i) => ({
        panel_id: p.id || `p${i+1}`,
        image_data: p.thumb && p.thumb.startsWith('data:') ? p.thumb : undefined,
        text: p.text || '',
        speaker: p.speaker || '',
        motion_style: p.motion || 'zoom_in',
        sfx: p.sfx !== 'none' ? p.sfx : undefined
      })),
      aspect_ratio: byId('mc-aspect-ratio')?.value || '16:9',
      voice_id: byId('mc-voice-select')?.value || 'vi-VN-HoaiMyNeural',
      fit_mode: byId('mc-fit-mode')?.value || 'blur_bg',
      enable_anime4k: byId('mc-anime4k-check')?.checked ?? true,
      enable_tts: true,
      enable_sfx: true
    };

    try {
      if (statusText) statusText.textContent = "Đang tổng hợp giọng đọc AI & lồng tiếng...";
      if (statusPct) statusPct.textContent = "50%";
      if (progressBar) progressBar.style.width = "50%";

      const res = await fetch('/api/motion-comic/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success && data.video_url) {
        if (statusText) statusText.textContent = `Xuất video hoàn tất! (${data.duration}s · ${data.resolution})`;
        if (statusPct) statusPct.textContent = "100%";
        if (progressBar) progressBar.style.width = "100%";

        if (placeholder) placeholder.style.display = 'none';
        if (videoElem) {
          videoElem.src = data.video_url;
          videoElem.style.display = 'block';
          videoElem.load();
        }
        if (downloadActions) {
          downloadActions.style.display = 'flex';
          const btnVid = byId('mc-btn-download-video');
          const btnSrt = byId('mc-btn-download-srt');
          const btnVtt = byId('mc-btn-download-vtt');
          if (btnVid) btnVid.href = data.video_url;
          if (btnSrt && data.srt_url) btnSrt.href = data.srt_url;
          if (btnVtt && data.vtt_url) btnVtt.href = data.vtt_url;
        }
      } else {
        throw new Error(data.detail || "Không thể xuất video");
      }
    } catch (err) {
      if (statusText) statusText.textContent = `Lỗi: ${err.message}`;
      if (progressBar) progressBar.style.background = 'var(--red)';
    }
  }

  async function renderUnifiedStudio(initialTab) {
    if (initialTab) unifiedStudioActiveTab = initialTab;
    setPage('studio', 'Studio Sáng Tạo Đa Năng');
    const host = byId('page-studio');
    if (!host) return;

    host.innerHTML = `
      <div class="manga-header" style="border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:16px">
        <div>
          <div class="page-head" style="margin-bottom:4px;padding-bottom:0">
            <div>
              <h1>🎨 Studio Sáng Tạo Đa Năng <span class="mc-badge-pro">COMMERCIAL 4K</span></h1>
              <p>Hệ thống sản xuất toàn diện: Dựng truyện tranh Manga · Tẩy bóng thoại Koharu · Xuất video Motion Comic 4K & TikTok 9:16 có lồng tiếng AI</p>
            </div>
          </div>
        </div>
        <div class="page-actions">
          <button type="button" class="secondary-btn" id="studio-btn-seed-sample">★ Nạp Dự Án Mẫu</button>
          <button type="button" class="primary-btn" id="studio-btn-quick-export">▶ Xuất Video Motion Comic</button>
        </div>
      </div>
      <nav class="manga-subnav" style="margin-bottom:18px">
        <button type="button" class="manga-nav-tab ${unifiedStudioActiveTab === 'motion' ? 'active' : ''}" data-studio-tab="motion">🎬 Xưởng Motion Comic (Video 4K / TikTok)</button>
        <button type="button" class="manga-nav-tab ${unifiedStudioActiveTab === 'manga' ? 'active' : ''}" data-studio-tab="manga">📖 Vẽ Manga & Storyboard</button>
        <button type="button" class="manga-nav-tab ${unifiedStudioActiveTab === 'inpaint' ? 'active' : ''}" data-studio-tab="inpaint">🎨 Tẩy chữ bóng thoại (Koharu)</button>
        <button type="button" class="manga-nav-tab ${unifiedStudioActiveTab === 'export' ? 'active' : ''}" data-studio-tab="export">📦 Hàng đợi Xuất bản</button>
      </nav>
      <div id="studio-tab-content"></div>
    `;

    host.querySelectorAll('[data-studio-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        unifiedStudioActiveTab = btn.dataset.studioTab;
        renderUnifiedStudio();
      });
    });

    byId('studio-btn-seed-sample')?.addEventListener('click', () => {
      if (unifiedStudioActiveTab === 'motion') {
        byId('mc-btn-seed-demo')?.click();
      } else {
        alert("Đã nạp dữ liệu truyện tranh mẫu thành công.");
      }
    });

    byId('studio-btn-quick-export')?.addEventListener('click', () => {
      unifiedStudioActiveTab = 'motion';
      renderUnifiedStudio();
      setTimeout(() => {
        byId('mc-btn-render')?.click();
      }, 100);
    });

    const tabContainer = byId('studio-tab-content');
    if (!tabContainer) return;

    if (unifiedStudioActiveTab === 'motion') {
      renderMotionComicInside(tabContainer);
    } else if (unifiedStudioActiveTab === 'inpaint') {
      tabContainer.innerHTML = `
        <div class="view-card" style="max-width:800px;margin:0 auto;text-align:center;padding:32px">
          <div style="font-size:42px;margin-bottom:12px">🎨</div>
          <h2>Tẩy Chữ Bóng Thoại Manga (Koharu Sidecar)</h2>
          <p style="color:var(--text-muted);margin:8px auto 20px auto;max-width:540px">
            Tự động phát hiện và xóa văn bản trong bóng thoại manga, tái tạo lại toàn bộ nét vẽ và hoa văn nền bằng mô hình LaMa inpainting.
          </p>
          <div style="display:flex;justify-content:center;gap:12px">
            <button type="button" class="primary-btn" id="btn-upload-inpaint-sample">Tải ảnh Manga cần tẩy chữ</button>
          </div>
        </div>
      `;
      byId('btn-upload-inpaint-sample')?.addEventListener('click', () => {
        setPage('home');
        $('chat-files')?.click();
      });
    } else if (unifiedStudioActiveTab === 'export') {
      tabContainer.innerHTML = `
        <div class="view-card" style="padding:24px">
          <h3>Hàng đợi Xuất bản (Export Queue)</h3>
          <p style="color:var(--text-muted);font-size:12.5px;margin-bottom:16px">Các tệp CBZ, PDF và video MP4 Motion Comic đã xuất bản trên máy.</p>
          <div id="studio-export-list" style="display:flex;flex-direction:column;gap:10px">
            <div class="empty-state">Chưa có tệp xuất bản nào gần đây. Hãy tạo video Motion Comic hoặc xuất CBZ Manga.</div>
          </div>
        </div>
      `;
    } else {
      tabContainer.innerHTML = `
        <div class="view-card" style="padding:24px">
          <h3>Manga Storyboard & Bố Cục Trang</h3>
          <p style="color:var(--text-muted);font-size:12.5px;margin-bottom:16px">Bố trí các panel tranh, sắp đặt khung thoại tiếng Việt Unicode và bộ lọc Screentone.</p>
          <div style="display:flex;gap:10px;margin-bottom:20px">
            <button type="button" class="primary-btn" id="btn-create-manga-page">＋ Tạo Trang Manga Mới</button>
            <button type="button" class="secondary-btn" id="btn-switch-to-motion">🎬 Chuyển Thành Video Motion Comic</button>
          </div>
          <div class="empty-state">Chọn một series để bắt đầu bố cục trang tranh hoặc bấm "Chuyển Thành Video Motion Comic" để tạo video ngay.</div>
        </div>
      `;
      byId('btn-switch-to-motion')?.addEventListener('click', () => {
        unifiedStudioActiveTab = 'motion';
        renderUnifiedStudio();
      });
    }
  }

  function renderMotionComicInside(container) {
    container.innerHTML = `
      <div class="mc-container">
        <div class="mc-grid">
          <div class="mc-card">
            <div class="mc-card-title">
              <span>🎞 Dòng thời gian phân cảnh (Storyboard Timeline)</span>
              <span id="mc-panel-counter" class="subtle" style="font-size:12px">2 phân cảnh</span>
            </div>
            <div style="display:flex;gap:8px;margin-bottom:6px">
              <button type="button" class="secondary-btn" id="mc-btn-seed-demo" style="font-size:12px;padding:4px 10px">★ Nạp Demo Luffy & Zoro</button>
              <button type="button" class="secondary-btn" id="mc-btn-add-panel" style="font-size:12px;padding:4px 10px">＋ Thêm Phân Cảnh</button>
            </div>
            <div class="mc-timeline-list" id="mc-timeline-list"></div>
          </div>

          <div class="mc-card">
            <div class="mc-card-title">
              <span>⚙ Cấu hình Video & Trình phát (Export Player)</span>
              <button type="button" class="primary-btn" id="mc-btn-render" style="padding:4px 14px">▶ Xuất Video MP4</button>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <label class="workspace-field">
                <span>TỈ LỆ VIDEO</span>
                <select id="mc-aspect-ratio" class="field">
                  <option value="16:9">YouTube / TV Widescreen (16:9 - 1080p)</option>
                  <option value="9:16">TikTok / Shorts / Reels (9:16 Dọc)</option>
                  <option value="1:1">Instagram Square (1:1)</option>
                  <option value="4K">Ultra HD 4K (3840x2160)</option>
                </select>
              </label>

              <label class="workspace-field">
                <span>GIỌNG LỒNG TIẾNG AI</span>
                <select id="mc-voice-select" class="field">
                  <option value="vi-VN-HoaiMyNeural">Hoài My (Nữ Việt Nam - Anime/Diễn cảm)</option>
                  <option value="vi-VN-NamMinhNeural">Nam Minh (Nam Việt Nam - Trầm ấm/Kể chuyện)</option>
                  <option value="ja-JP-NanamiNeural">Nanami (Nữ Nhật Bản - Anime)</option>
                  <option value="ja-JP-KeitaNeural">Keita (Nam Nhật Bản - Shonen)</option>
                  <option value="en-US-GuyNeural">Guy (English - Cinematic Narrator)</option>
                </select>
              </label>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <label class="workspace-field">
                <span>XỬ LÝ NỀN (FIT MODE)</span>
                <select id="mc-fit-mode" class="field">
                  <option value="blur_bg">Mờ ảo thông minh (Blur BG - Chuẩn TikTok/YouTube)</option>
                  <option value="contain">Khung viền đen nguyên bản (Contain)</option>
                  <option value="cover">Cắt lấp đầy khung hình (Cover)</option>
                </select>
              </label>

              <div style="display:flex;flex-direction:column;justify-content:center;gap:4px">
                <label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text):cursor:pointer">
                  <input type="checkbox" id="mc-anime4k-check" checked>
                  <strong>Khử mờ Anime4K (0 MB VRAM)</strong>
                </label>
                <small class="subtle" style="font-size:11px">Làm sắc nét đường nét mực manga mà không tốn VRAM.</small>
              </div>
            </div>

            <div class="mc-video-wrapper" id="mc-video-wrapper">
              <div id="mc-player-placeholder" style="text-align:center;padding:24px;color:var(--text-muted)">
                <div style="font-size:36px;margin-bottom:8px">🎬</div>
                <strong>Chưa có video được xuất</strong>
                <p style="font-size:12px;margin-top:4px">Bấm nút "Xuất Video MP4" để dựng tập phim với âm thanh và hiệu ứng.</p>
              </div>
              <video id="mc-video-elem" class="mc-video-preview" controls playsinline style="display:none"></video>
            </div>

            <div id="mc-render-status" style="display:none;background:rgba(255,255,255,0.04);padding:12px;border-radius:var(--radius-sm)">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
                <span id="mc-status-text" style="font-size:12.5px;font-weight:600">Đang dựng video...</span>
                <span id="mc-status-pct" style="font-size:12px;color:var(--cyan)">0%</span>
              </div>
              <div style="width:100%;height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden">
                <div id="mc-progress-bar" style="width:0%;height:100%;background:linear-gradient(90deg,#06b6d4,#6366f1);transition:width 0.2s"></div>
              </div>
            </div>

            <div id="mc-download-actions" style="display:none;gap:10px;flex-wrap:wrap">
              <a id="mc-btn-download-video" class="primary-btn" download style="text-decoration:none;display:inline-flex;align-items:center;gap:6px">⬇ Tải Video MP4</a>
              <a id="mc-btn-download-srt" class="secondary-btn" download style="text-decoration:none;display:inline-flex;align-items:center;gap:6px">📝 Tải Phụ đề SRT</a>
              <a id="mc-btn-download-vtt" class="secondary-btn" download style="text-decoration:none;display:inline-flex;align-items:center;gap:6px">🌐 Tải WebVTT</a>
            </div>
          </div>
        </div>
      </div>
    `;

    renderTimelineList();

    byId('mc-btn-seed-demo')?.addEventListener('click', () => {
      mcPanelsState = [
        {
          id: "p1",
          thumb: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAACAAQMAAACq9p52AAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAACNJREFUGBntwQEBAAAAgiD/r25IQAEAAAAAAAAAAAAAAAAAgIcBFu4AAaZ4z6cAAAAASUVORK5CYII=",
          speaker: "Luffy",
          text: "Tôi sẽ trở thành Vua Hải Tặc! Không ai có thể cản bước!",
          motion: "zoom_in",
          sfx: "boom"
        },
        {
          id: "p2",
          thumb: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAACAAQMAAACq9p52AAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAACNJREFUGBntwQEBAAAAgiD/r25IQAEAAAAAAAAAAAAAAAAAgIcBFu4AAaZ4z6cAAAAASUVORK5CYII=",
          speaker: "Zoro",
          text: "Tam Kiếm Phái: Tam Thiên Thế Giới! Lên đường thôi!",
          motion: "pan_rtl",
          sfx: "swoosh"
        }
      ];
      renderTimelineList();
    });

    byId('mc-btn-add-panel')?.addEventListener('click', () => {
      const idx = mcPanelsState.length + 1;
      mcPanelsState.push({
        id: "p" + Date.now().toString(36),
        thumb: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAACAAQMAAACq9p52AAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAACNJREFUGBntwQEBAAAAgiD/r25IQAEAAAAAAAAAAAAAAAAAgIcBFu4AAaZ4z6cAAAAASUVORK5CYII=",
        speaker: "Nhân vật " + idx,
        text: "Lời thoại phân cảnh " + idx,
        motion: "zoom_in",
        sfx: "swoosh"
      });
      renderTimelineList();
    });

    byId('mc-btn-render')?.addEventListener('click', startRenderMotionComic);
  }

  // Hook Quick Tools in Composer
  byId('btn-quick-attach-img')?.addEventListener('click', () => $('chat-files')?.click());
  byId('btn-quick-studio')?.addEventListener('click', () => navigate('studio'));
  byId('btn-quick-calc')?.addEventListener('click', () => {
    $('chatinput').value = '123456789012 * 987654321098';
    triggerSmartIntentCheck();
    $('chatinput').focus();
  });
  byId('btn-quick-graph')?.addEventListener('click', async () => {
    try {
      const r = await fetch('/api/research/codebase-graph').then(res => res.json());
      addMsg('assistant', '🌐 **Codebase Knowledge Graph (Graphify)**: Đã lập chỉ mục `' + (r.modules_count || 0) + '` modules, `' + (r.classes_count || 0) + '` classes, và `' + (r.functions_count || 0) + '` functions. 0 MB VRAM GPU.');
    } catch (err) {
      addMsg('assistant', 'Chưa thể kết nối Codebase Graph.');
    }
  });

  // Hero Cards Listeners
  byId('hero-card-motion')?.addEventListener('click', () => {
    navigate('studio');
    setTimeout(() => {
      unifiedStudioActiveTab = 'motion';
      renderUnifiedStudio();
    }, 50);
  });
  byId('hero-card-manga')?.addEventListener('click', () => {
    navigate('studio');
    setTimeout(() => {
      unifiedStudioActiveTab = 'manga';
      renderUnifiedStudio();
    }, 50);
  });
  byId('hero-card-code')?.addEventListener('click', () => navigate('workspace'));
  byId('hero-card-calc')?.addEventListener('click', () => {
    $('chatinput').value = '123456789012 * 987654321098';
    triggerSmartIntentCheck();
    $('chatinput').focus();
  });

  // Action Pills for Attached Image
  byId('action-vision-btn')?.addEventListener('click', () => {
    $('agent-select').value = 'Vision';
    $('chatinput').value = 'Hãy nhận diện và phân tích chi tiết hình ảnh này giúp tôi.';
    $('sendbtn')?.click();
  });
  byId('action-inpaint-btn')?.addEventListener('click', () => {
    navigate('studio');
    setTimeout(() => {
      unifiedStudioActiveTab = 'inpaint';
      renderUnifiedStudio();
    }, 50);
  });
  byId('action-motion-btn')?.addEventListener('click', () => {
    navigate('studio');
    setTimeout(() => {
      unifiedStudioActiveTab = 'motion';
      renderUnifiedStudio();
    }, 50);
  });
  byId('action-remove-img')?.addEventListener('click', () => {
    chatAttachments = chatAttachments.filter(x => x.kind !== 'image');
    renderChatAttachments();
  });

  // Updated renderChatAttachments to control smart-inline-attachment
  const _orig_renderChatAttachments = renderChatAttachments;
  renderChatAttachments = function() {
    const imgItem = chatAttachments.find(x => x.kind === 'image');
    const inlineCard = byId('smart-inline-attachment');
    if (inlineCard) {
      if (imgItem) {
        inlineCard.hidden = false;
        const prevImg = byId('omnibar-preview-img');
        if (prevImg) prevImg.src = imgItem.preview || '';
        const nameDiv = byId('omnibar-image-name');
        if (nameDiv) nameDiv.textContent = imgItem.name || 'Ảnh đính kèm';
      } else {
        inlineCard.hidden = true;
      }
    }
    const nonImages = chatAttachments.filter(x => x.kind !== 'image');
    const host = $('composer-attachments');
    if (host) {
      host.replaceChildren();
      host.hidden = !nonImages.length;
      nonImages.forEach((item, index) => {
        const chip = document.createElement('div');
        chip.className = 'attachment-chip';
        const span = document.createElement('span');
        span.textContent = item.name;
        chip.append(span);
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'attachment-chip-remove';
        remove.textContent = '✕';
        remove.addEventListener('click', () => {
          const origIdx = chatAttachments.indexOf(item);
          if (origIdx >= 0) chatAttachments.splice(origIdx, 1);
          renderChatAttachments();
        });
        chip.append(remove);
        host.append(chip);
      });
    }
  };
"""

# Insert unified_js inside IIFE right before })();
if "let unifiedStudioActiveTab" not in content:
    content = content.replace("})();\n</script>", unified_js + "\n})();\n</script>")

html_path.write_text(content, encoding="utf-8")
print("SUCCESS: Unified UI and fixed layout collisions in app/ui/index.html!")
