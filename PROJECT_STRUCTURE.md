# AI Office – Bản đồ Cấu trúc Dự án (Project Structure Map)

> **Dành cho AI Agent & Developer:** Tài liệu này là nguồn tham chiếu chuẩn xác nhất về kiến trúc cây thư mục, trách nhiệm của từng module và quy ước vị trí tệp tin trong toàn bộ repository `F:\AI-Office`. Khi thực hiện bất kỳ tác vụ nào, hãy luôn đọc và tuân thủ cấu trúc này để đặt tệp tin đúng vị trí và không làm xáo trộn dự án.

---

## 1. Sơ đồ Tổng quan Cây Thư mục (Directory Tree)

```text
F:\AI-Office\
├── .venv\                           # Môi trường ảo Python 3.13 (đã cài dependencies)
├── app\                             # Toàn bộ mã nguồn ứng dụng lõi (Backend & Frontend)
│   ├── ui\                          # Giao diện người dùng Desktop (HTML5/CSS3/JS)
│   │   ├── assets\                  # Icons, font chữ tiếng Việt Inter-Variable, Live2D framework
│   │   │   ├── live2d\              # Thư viện Live2D Cubism Core & loader
│   │   │   ├── ai-office.ico        # Icon cửa sổ Windows & taskbar
│   │   │   ├── ai-office-icon.png   # Icon hiển thị trên thanh header & UI
│   │   │   └── Inter-Variable.ttf   # Font chữ hiển thị chuẩn Unicode tiếng Việt
│   │   └── index.html               # Giao diện SPA (Activity Rail, Explorer, Manga Studio, Editor...)
│   ├── browser.py                   # Engine tự động hóa trình duyệt web (Playwright / Chrome profile)
│   ├── computer.py                  # Quan sát desktop, chụp ảnh màn hình, trích xuất UI Automation tree
│   ├── computer_use.py              # Bộ lập kế hoạch thao tác máy tính (Computer Use planner)
│   ├── game_agent.py                # Agent điều khiển tương tác game / Live2D
│   ├── game_playbooks.py            # Kịch bản và quy tắc tương tác game
│   ├── launcher.py                  # Khởi chạy cửa sổ pywebview + WebView2 (hạ quyền tránh chặn tiếng Việt)
│   ├── main.py                      # FastAPI server (port 8765), SQLite init, router registration
│   ├── manga_benchmark.py           # Bộ thực thi Anime Intelligence Benchmark
│   ├── manga_comfy.py               # Adapter ComfyUI, GPU ResourceScheduler lock, model registry
│   ├── manga_composer.py            # Manga Compositor: render trang, bong bóng thoại tiếng Việt, CBZ/PDF
│   ├── manga_illustrator.py         # Đặc tả tạo hình nhân vật & tổng hợp prompt diffusion
│   ├── manga_metrics.py             # Tính toán chỉ số chất lượng ảnh, độ tương phản và continuity
│   ├── manga_story.py               # Story Engine: lorebook, locked traits, speech rules, continuity QA
│   ├── manga_studio.py              # Router REST API cho toàn bộ tính năng Manga Studio
│   ├── manga_validator.py           # Kiểm định chất lượng hình ảnh & phát hiện bất thường mỹ thuật
│   ├── model_provider.py            # Quản lý kết nối Ollama (qwen3.5:4b), inference serialization
│   ├── ocr_helper.py                # Nhận diện chữ trên ảnh màn hình (OCR)
│   ├── research_tools.py            # Công cụ tìm kiếm tệp và nghiên cứu tri thức
│   ├── task_context.py              # Quản lý ngữ cảnh, nhật ký thực thi và lịch sử nhiệm vụ trong SQLite
│   ├── task_qa.py                   # QA Agent kiểm tra acceptance conditions
│   ├── vtuber_models.py             # Quản lý và nạp mô hình Live2D / 3D Avatar
│   └── workspace_editor.py          # Workspace Editor Agent: đọc tệp an toàn, unified diff, SHA-256 backup
├── data\                            # Kho lưu trữ runtime cục bộ (được ignore trong git)
│   ├── backups\                     # Bản sao lưu cấu hình dự án
│   ├── browser-profile\             # Profile trình duyệt độc lập cho Browser Agent
│   ├── browser-research-profile\    # Profile trình duyệt phụ phục vụ nghiên cứu
│   ├── manga\                       # Dữ liệu xuất bản Manga Studio
│   │   ├── projects\                # Các panel ảnh gốc, trang ghép (composed) và gói CBZ/PDF xuất bản
│   │   └── benchmarks\              # Kết quả các đợt benchmark Anime Intelligence
│   ├── screenshots\                 # Ảnh chụp màn hình tạm thời cho Computer Use / QA
│   ├── vtuber_models\               # Tệp tài nguyên mô hình Live2D tải về
│   ├── workspace-backups\           # Bản sao lưu byte gốc của các tệp trước khi áp dụng đề xuất sửa đổi
│   ├── workspace-edit-proposals\    # Danh sách các tệp đề xuất sửa đổi đang chờ người dùng phê duyệt
│   ├── office.db                    # SQLite Database chính (tasks, chat, manga data, proposals)
│   ├── launcher.log                 # Nhật ký khởi động desktop launcher
│   └── ollama.log                   # Nhật ký phản hồi mô hình Ollama
├── docs\                            # Toàn bộ tài liệu kiến trúc, kế hoạch và đặc tả kỹ thuật
│   ├── anime_intelligence\          # Đặc tả chuẩn Anime Intelligence & Visual QA
│   │   ├── ANIME_INTELLIGENCE_BENCHMARK_PROMPTS.md
│   │   ├── ANIME_INTELLIGENCE_RESEARCH_AND_MEMORY_ARCHITECTURE.md
│   │   └── ANIME_INTELLIGENCE_VISUAL_QUALITY_AND_CONTINUITY.md
│   ├── audit\                       # Các báo cáo audit kiến trúc hệ thống
│   │   └── 2026-11-07\              # Báo cáo audit nền tảng AI Office (Security, Agents, Roadmap...)
│   ├── manga_studio\                # Hồ sơ thiết kế & kế hoạch tích hợp Manga Studio
│   │   ├── MANGA_STUDIO_AUDIT.md    # Báo cáo khảo sát thực trạng phần cứng, VRAM & ComfyUI
│   │   └── MANGA_STUDIO_IMPLEMENTATION_PLAN.md # Kế hoạch kỹ thuật 5 pha chi tiết
│   └── README.md                    # Chỉ mục toàn bộ tài liệu dự án
├── scratch\                         # Vùng đệm nháp / thử nghiệm tạm thời (được ignore trong git)
│   ├── qa_screenshots\              # Ảnh chụp màn hình khi chạy UI audit
│   └── README.md                    # Hướng dẫn sử dụng vùng đệm nháp
├── scripts\                         # Các CLI scripts, công cụ đo lường và pipeline sản xuất
│   ├── generate_official_chapter1.py# Pipeline sản xuất chính thức Chương 1 "Lớp Học Ánh Trăng"
│   ├── legacy_produce_moonlight_ch1.py # Bản prototype ban đầu (lưu trữ)
│   ├── run_anime_benchmark.py       # Chạy Anime Intelligence Benchmark
│   ├── run_real_comfy_benchmark.py  # Chạy đo đạc tải thực tế khi nối tới ComfyUI GPU
│   └── README.md                    # Hướng dẫn chi tiết cách chạy từng script
├── skills\                          # Tệp định nghĩa vai trò và kỹ năng chuẩn của các AI Agent
│   ├── analysis\SKILL.md            # Kỹ năng phân tích số liệu & logic
│   ├── browser\SKILL.md             # Kỹ năng tự động hóa web an toàn
│   ├── coding\SKILL.md              # Kỹ năng phát triển phần mềm & refactoring
│   ├── computer\SKILL.md            # Kỹ năng thao tác máy tính (Computer Use)
│   ├── orchestration\SKILL.md       # Kỹ năng điều phối tổng thể (CEO)
│   ├── qa\SKILL.md                  # Kỹ năng kiểm thử & bảo đảm chất lượng (QA)
│   ├── research\SKILL.md            # Kỹ năng tra cứu & tổng hợp tri thức
│   ├── workspace\SKILL.md           # Kỹ năng thao tác chỉnh sửa tệp an toàn (Workspace Editor)
│   ├── writing\SKILL.md             # Kỹ năng soạn thảo nội dung kỹ thuật & kịch bản
│   └── README.md                    # Danh mục các skill đã cài đặt
├── tests\                           # Hệ thống kiểm thử tự động (Pytest) & Kịch bản QA
│   ├── qa_story_check.py            # Kịch bản thẩm định E2E chất lượng Manga Story
│   ├── smoke_check.py               # Kiểm tra nhanh độ sẵn sàng của Backend & UI đang chạy
│   ├── test_anime_benchmark_specs.py# Unit tests đặc tả benchmark
│   ├── test_anime_intelligence_benchmark.py # Unit tests đo lường benchmark Anime Intelligence
│   ├── test_manga_comfy.py          # Unit tests ComfyUI Adapter & GPU lock
│   ├── test_manga_composer.py       # Unit tests Manga Compositor, bubble tiếng Việt & PDF/CBZ
│   ├── test_manga_metrics.py        # Unit tests công thức tính toán chỉ số chất lượng
│   ├── test_manga_story.py          # Unit tests Story Engine & Continuity Checker
│   ├── test_manga_studio.py         # Unit tests toàn bộ REST API Manga Studio
│   ├── test_qa_and_game.py          # Unit tests QA & game agent
│   ├── test_research_tools.py       # Unit tests công cụ nghiên cứu
│   ├── test_task_context.py         # Unit tests quản lý ngữ cảnh nhiệm vụ SQLite
│   ├── test_task_qa.py              # Unit tests acceptance conditions
│   ├── workspace_editor_check.py    # Kịch bản kiểm tra an toàn Workspace Editor (diff, backup, rollback)
│   ├── workspace_edit_smoke.py      # Smoke test API Workspace Editor
│   ├── workspace_ui_smoke.py        # Smoke test UI Workspace Editor
│   └── README.md                    # Hướng dẫn chi tiết chạy kiểm thử
├── .gitignore                       # Danh sách loại trừ git (bỏ qua data, venv, cache, scratch)
├── pytest.ini                       # Cấu hình Pytest (tắt cache provider lỗi quyền, lọc warnings)
├── requirements.txt                 # Danh sách thư viện Python phụ thuộc
├── README.md                        # Giới thiệu tổng quan dự án, hướng dẫn cài đặt & vận hành
├── RULES.md                         # 10 nguyên tắc kỹ thuật cốt lõi của AI Office
├── Start-AI-Office.bat              # Script khởi động ứng dụng AI Office (chế độ người dùng tiêu chuẩn)
└── Start-AI-Office-Admin.bat        # Script khởi động ứng dụng với quyền Administrator
```

---

## 2. Trách nhiệm cụ thể của từng Thư mục

| Thư mục | Mục đích & Trách nhiệm | Loại tệp được phép lưu |
| :--- | :--- | :--- |
| `app/` | Chứa mã nguồn backend FastAPI, logic xử lý nghiệp vụ, thuật toán agent và giao diện UI desktop. | `.py`, `app/ui/` (`.html`, `.css`, `.js`, `.png`, `.ico`, `.ttf`). |
| `data/` | Dữ liệu runtime do ứng dụng sinh ra khi hoạt động: database SQLite, lịch sử backup, ảnh xuất bản manga, cache browser. | `.db`, `.log`, `.png`, `.cbz`, `.pdf`, `.json`. |
| `docs/` | Toàn bộ tài liệu chính thức: kiến trúc, audit, đặc tả tiêu chuẩn, kế hoạch triển khai. | Chỉ chứa các tệp `.md`. |
| `scripts/` | Các script dòng lệnh (CLI tools), pipeline sản xuất nội dung hàng loạt, công cụ đo benchmark. | Chỉ chứa các tệp `.py` chạy độc lập và `README.md`. |
| `skills/` | Định nghĩa System Prompt và Skills theo chuẩn dành cho các vai trò Agent của AI Office. | Mỗi thư mục con chứa 1 tệp `SKILL.md`. |
| `tests/` | Các bộ kiểm thử tự động (Unit Tests theo chuẩn Pytest) và script thẩm định QA/Smoke. | Tệp `test_*.py` hoặc `*_check.py`, `*_smoke.py`. |
| `scratch/` | Vùng nháp tạm thời (scratchpad) cho các thử nghiệm nhanh, code debug dùng một lần. | Các tệp nháp tạm, ảnh chụp kiểm thử. |

---

## 3. Quy tắc Đặt Tệp Mới (File Placement Rules)

Khi tạo tệp mới hoặc bổ sung tính năng, AI Agent và Developer **bắt buộc tuân thủ** các quy tắc sau:

1. **Thêm API hoặc Logic Backend mới:**  
   - Viết trực tiếp vào module tương ứng trong `app/` (ví dụ: `app/manga_*.py` nếu thuộc Manga Studio, `app/workspace_editor.py` nếu thuộc Workspace).
   - Đăng ký endpoint trong `app/main.py`.

2. **Thêm Kiểm thử (Test Cases):**  
   - Mọi test tự động dùng `pytest` **phải đặt trong `tests/`** và bắt đầu bằng tiền tố `test_` (ví dụ: `tests/test_new_feature.py`).
   - Mọi script kiểm tra tổng thể hoặc smoke test phải đặt trong `tests/` và có hậu tố `_check.py` hoặc `_smoke.py`.
   - **Tuyệt đối không để script sản xuất hoặc công cụ dòng lệnh trong `tests/`**.

3. **Thêm Script Dòng Lệnh hoặc Pipeline Tự Động:**  
   - Mọi script thực thi độc lập (CLI script) **phải đặt trong `scripts/`**.
   - Cung cấp mô tả và lệnh chạy vào `scripts/README.md`.

4. **Thêm Tài liệu hoặc Báo cáo:**  
   - Phân loại vào thư mục con thích hợp trong `docs/`:
     - Đặc tả Anime / Manga: `docs/anime_intelligence/` hoặc `docs/manga_studio/`.
     - Báo cáo audit hệ thống: `docs/audit/<YYYY-MM-DD>/`.
   - Không tạo các tệp markdown tự do ở thư mục gốc (`F:\AI-Office\`) ngoại trừ `README.md`, `RULES.md`, `PROJECT_STRUCTURE.md`.

5. **Lưu trữ Trạng thái hoặc Dữ liệu Runtime:**  
   - Mọi dữ liệu phát sinh trong thời gian chạy (database, ảnh render, export PDF/CBZ, logs, backups) **phải nằm trong `data/`** để được `.gitignore` bảo vệ.

6. **Tác vụ Nháp / Debug một lần:**  
   - Chỉ được tạo tệp tạm trong `scratch/`. Sau khi hoàn thiện, hãy dọn dẹp hoặc chuyển thành test/script chính thức.

---

## 4. Các Lệnh Vận hành & Kiểm thử Chuẩn

### Khởi chạy Ứng dụng Desktop
```powershell
# Chạy ứng dụng thông qua launcher WebView2 (khuyên dùng):
.\Start-AI-Office.bat

# Hoặc chạy backend trực tiếp bằng Python:
.venv\Scripts\python.exe app\launcher.py
```

### Chạy Kiểm thử Tự động (Pytest)
```powershell
# Chạy toàn bộ test suites (đã qua cấu hình pytest.ini):
.venv\Scripts\python.exe -m pytest

# Chạy một file test cụ thể:
.venv\Scripts\python.exe -m pytest tests\test_manga_studio.py
```

### Chạy Kịch bản QA Thẩm định
```powershell
# Thẩm định an toàn Workspace Editor:
.venv\Scripts\python.exe tests\workspace_editor_check.py

# Thẩm định E2E chất lượng Manga Story (tiếng Việt, locked traits, bubble tail, xuất CBZ/PDF):
.venv\Scripts\python.exe tests\qa_story_check.py
```

### Chạy Pipeline Sản xuất Manga
```powershell
# Sản xuất trọn vẹn Chương 1 "Lớp Học Ánh Trăng":
.venv\Scripts\python.exe scripts\generate_official_chapter1.py

# Chạy Anime Intelligence Benchmark:
.venv\Scripts\python.exe scripts\run_anime_benchmark.py
```
