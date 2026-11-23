# AI Office

Local-first multi-agent desktop workspace. Current milestone: 0.7.0.

## Current implementation
- **Desktop Shell & Native Integration**: Windows desktop window using pywebview + WebView2. The launcher automatically reopens through the standard-user Explorer shell if started elevated, keeping WebView2 at the same integrity level as UniKey/EVKey so Vietnamese IME input is not blocked. Native HWND and shortcut AppUserModelID use the official AI Office infinity icon.
- **VS Code-Inspired Workbench**: Dark workbench with activity rail, Explorer, central workspace, agents, task panels, status bar, and dedicated views for Home, Workspace Editor, Manga Studio, Game/VTuber, Tasks, and Tools.
- **Backend & Local AI Runtime**: FastAPI local backend at `127.0.0.1:8765`, SQLite database at `data/office.db`, and serialized inference queue for local Ollama (`qwen3.5:4b`) to prevent VRAM over-allocation on 6 GB VRAM GPUs.
- **Functional Explorer**: Browse project folders and preview allow-listed text files (maximum 512 KB). Sensitive folders such as `.git`, `.venv`, and `data` are hidden; path traversal outside the project root is rejected.
- **Workspace Editor Engine**: Dedicated Workspace Editor Agent reads allow-listed UTF-8 files or proposes new files. Every change requires explicit user approval via persistent pending proposals with unified diffs, SHA-256 integrity verification, pre-apply backups, atomic writing, and hash-guarded rollback under `data/workspace-backups/`.
- **Manga Studio & Anime Intelligence**: Complete manga creation suite:
  - Series, Volume, Chapter, and Character CRUD with locked visual traits and speech rules.
  - Scene and dialogue generation with deterministic and LLM-based continuity checking.
  - ComfyUI Adapter with GPU ResourceScheduler lock to avoid VRAM collision with Ollama.
  - Full Page Manga Compositor: panel layout, border rendering, Vietnamese Unicode speech bubbles with directional tails, screentones, and export to CBZ (with `ComicInfo.xml`) and multi-page PDF.
- **Browser Automation**: Restricted Chrome automation using a dedicated profile (`data/browser-profile`). DOM-targeted proposal queue with strict human approval per step; sensitive and transactional actions are blocked.
- **Computer Use Planner**: Step-by-step UI Automation (UIA) tree and screen-based planning with verification loops and explicit user approval before every click or keypress.
- **Multi-Agent Roster**: CEO, Researcher, Developer, Workspace Editor, Vision, Computer Use, Browser, Writer, and QA roles with modular `SKILL.md` definitions under `skills/`.

---

## Cấu trúc Thư mục Dự án (Project Structure)

Chi tiết bản đồ thư mục và quy tắc đặt tệp xem tại [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

```text
F:\AI-Office\
├── app/                  # Mã nguồn lõi: backend FastAPI, agents, manga studio, UI
│   └── ui/               # Giao diện desktop HTML5/CSS3/JS, font Unicode, Live2D
├── data/                 # Dữ liệu runtime: SQLite DB, manga exports, browser profiles, backups
├── docs/                 # Tài liệu kỹ thuật: kiến trúc, Manga Studio, Anime Intelligence, audits
├── scripts/              # Dòng lệnh CLI, pipeline sản xuất Manga, Anime Intelligence benchmark
├── skills/               # Định nghĩa vai trò & System Prompt cho từng AI Agent (SKILL.md)
├── tests/                # Bộ kiểm thử tự động (pytest) và các kịch bản QA verification
├── scratch/              # Vùng nháp tạm thời cho các thử nghiệm nhanh (được ignore)
├── .gitignore            # Cấu hình bỏ qua tệp git chuẩn mực
├── pytest.ini            # Cấu hình kiểm thử pytest tối ưu
├── requirements.txt      # Thư viện Python phụ thuộc
├── RULES.md              # 11 nguyên tắc kỹ thuật cốt lõi
├── PROJECT_STRUCTURE.md  # Bản đồ kiến trúc thư mục chuẩn chi tiết
├── Start-AI-Office.bat   # Script khởi động giao diện người dùng
└── Start-AI-Office-Admin.bat # Script khởi động quyền Administrator
```

---

## Run & Testing

### Khởi động Ứng dụng
- Chạy `Start-AI-Office.bat` hoặc mở shortcut `AI Office` trên Desktop.
- Yêu cầu: Ollama đang chạy với mô hình `qwen3.5:4b`.
- Địa chỉ backend: `http://127.0.0.1:8765`

### Chạy Kiểm thử Tự động (Pytest)
```powershell
# Chạy toàn bộ test suite (tự động theo cấu hình pytest.ini):
.venv\Scripts\python.exe -m pytest

# Chạy riêng module Manga Studio & Compositor:
.venv\Scripts\python.exe -m pytest tests/test_manga_studio.py tests/test_manga_composer.py
```

### Chạy Kịch bản Thẩm định QA
```powershell
# Kiểm định chất lượng toàn diện Manga Story (tiếng Việt, locked traits, screentone, xuất file):
.venv\Scripts\python.exe tests/qa_story_check.py

# Kiểm định an toàn Workspace Editor (diff, atomic write, backup & rollback):
.venv\Scripts\python.exe tests/workspace_editor_check.py
```

### Chạy Pipeline Sản xuất Manga
```powershell
# Sản xuất trọn vẹn Chương 1 bộ truyện "Lớp Học Ánh Trăng" (CBZ + PDF):
.venv\Scripts\python.exe scripts/generate_official_chapter1.py

# Chạy đo lường chuẩn hóa Anime Intelligence Benchmark:
.venv\Scripts\python.exe scripts/run_anime_benchmark.py
```
