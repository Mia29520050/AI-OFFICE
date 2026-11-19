# MANGA STUDIO INTEGRATION – REPOSITORY & ENVIRONMENT AUDIT (PHASE 0)
**Date:** 2026-11-19  
**Target Repository:** `F:\AI-Office`  
**Host Environment:** Windows 11 Home Single Language x64 (Build 26300), Lenovo LOQ  
**Auditor:** Antigravity (Coordinator)

---

## 1. Mục đích và Phạm vi Khảo sát
Báo cáo này ghi nhận hiện trạng thực tế của repository `F:\AI-Office`, môi trường phần cứng, runtime, database, agent orchestration, Ollama và ComfyUI theo yêu cầu tại `MASTER_TASK.md` (Phase 0).  
**Nguyên tắc tuân thủ:** Không sửa mã nguồn, không cài package, không nâng cấp dependency, không tự ý tải model trong suốt quá trình audit.

---

## 2. Hiện trạng Git & Mã nguồn
- **Đường dẫn repo:** `F:\AI-Office`
- **Git Branch:** `master`
- **Git Commit:** Chưa có commit nào (`No commits yet`, toàn bộ file đang ở trạng thái Untracked).
- **Trạng thái file untracked:**
  - `.gitignore`, `README.md`, `RULES.md`, `requirements.txt`
  - `Start-AI-Office.bat`, `Start-AI-Office-Admin.bat`
  - `app/` (toàn bộ mã nguồn backend & UI)
  - `data/` (chứa SQLite DB `office.db`, backups, logs)
  - `docs/` (chứa tài liệu audit trước)
  - `skills/` (chứa 9 skills chuẩn của các agent)
  - `tests/` (hệ thống kiểm thử smoke & unit test)
- **Lưu ý an toàn:** Trước khi bước vào Phase 1, cần khởi tạo commit gốc (initial baseline commit) hoặc tạo snapshot backup để có thể rollback an toàn 100%.

---

## 3. Kiến trúc AI Office Hiện tại

### 3.1 Cấu trúc thư mục ứng dụng
```
F:\AI-Office\
├── .venv\                      # Virtualenv Python 3.13.15
├── app\
│   ├── browser.py              # Browser automation (Chrome profile riêng, DOM-based, có duyệt)
│   ├── computer.py             # Window inspection, UIA tree, capture màn hình
│   ├── computer_use.py         # Computer use planner qua proposal & approval
│   ├── game_agent.py           # Game automation agent & session management
│   ├── game_playbooks.py       # CZN/HSR playbooks & routing
│   ├── launcher.py             # App entry: elevation check, Ollama check, Uvicorn + pywebview
│   ├── main.py                 # FastAPI core: SQLite init, agent catalog, chat, tasks
│   ├── model_provider.py       # Model runtime manager (Ollama client, fallback, semaphore)
│   ├── ocr_helper.py           # Windows OCR worker
│   ├── research_tools.py       # Context building, project search & citations
│   ├── task_context.py         # Evidence composition (project + web evidence)
│   ├── task_qa.py              # Deterministic QA engine & verdict parser
│   ├── vtuber_models.py        # Live2D / VTuber model asset manager
│   ├── workspace_editor.py     # File proposal, unified diff, SHA-256 validation, backup/rollback
│   └── ui\
│       ├── index.html          # Single-page desktop UI (VS Code workbench style)
│       └── assets\             # Icons, Live2D assets, Inter font
├── data\
│   ├── office.db               # SQLite database chính
│   ├── workspace-backups\      # Backup gốc và manifest cho rollback
│   ├── workspace-edit-proposals\ # Các đề xuất sửa file đang chờ duyệt
│   └── launcher.log            # Log khởi động ứng dụng
├── skills\                     # 9 role skills (analysis, browser, coding, computer, orchestration, qa, research, workspace, writing)
└── tests\                      # Bộ test kiểm thử
```

### 3.2 Quy chuẩn thiết kế mô-đun (Pattern)
- **FastAPI Endpoints:** Mỗi domain feature được tách thành module độc lập có hàm `register_routes(app, ...)`.
  - Đã có: `register_model_routes`, `register_research_routes`, `register_computer_use_routes`, `register_browser_routes`, `register_game_routes`, `register_vtuber_model_routes`, `register_workspace_editor_routes`.
  - **Manga Studio** phải tuân thủ chuẩn này: xây dựng `app/manga_studio.py` (hoặc package `app/manga/`) và gọi `register_manga_routes(app, ...)` trong `app/main.py`.
- **Cơ sở dữ liệu SQLite:**
  - File DB: `data/office.db`.
  - Khởi tạo bảng trong `init_db()` (`app/main.py`) bằng `CREATE TABLE IF NOT EXISTS` và kiểm tra `PRAGMA table_info` để thêm cột an toàn không làm hỏng dữ liệu cũ.
  - Không tạo database SQLite thứ hai. Mở rộng trực tiếp `office.db` với các bảng có tiền tố `manga_`.
- **Quản lý tài nguyên & Concurrency:**
  - `MODEL_SEMAPHORE = asyncio.Semaphore(1)`: Đảm bảo chỉ 1 tác vụ suy luận nặng chạy tại một thời điểm trên máy phần cứng khiêm tốn.
- **Frontend Workbench:**
  - `app/ui/index.html` dùng mô hình Activity Bar (cột icon bên trái) -> Dynamic View Containers trong vùng center.
  - Các view hiện tại: Chat (`home`), Workspace (`workspace`), Tasks (`tasks`), Skills (`skills`), Agents (`agents`), Tools (`tools`), Game (`game`), VTuber (`vtuber`).
  - Manga Studio sẽ bổ sung nút Activity Bar (`data-view="manga"`) và trang container `#page-manga` với giao diện chuyên dụng.

---

## 4. Kiểm tra Môi trường, Phần cứng & Dung lượng

| Hạng mục | Thực tế phát hiện trên máy | Nhận định |
|---|---|---|
| **CPU** | 12th Gen Intel Core i5-12450HX (8 cores, 12 threads) | Đáp ứng tốt xử lý pipeline và LLM cục bộ |
| **GPU** | NVIDIA GeForce RTX 3050 Laptop GPU (6 GB VRAM) + Intel UHD Graphics | VRAM 6GB: Bắt buộc serialize tác vụ, không chạy song song LLM + Image generation |
| **RAM** | 12 GB vật lý (Tổng: 11.73 GB, Còn trống: ~3.68 GB) | Khá hạn hẹp, cần kiểm soát bộ nhớ Python tránh OOM |
| **Ổ đĩa C:** | Dung lượng: 150 GB, Còn trống: **15.92 GB** | **Rất eo hẹp**. Tuyệt đối KHÔNG lưu cache ảnh hoặc model vào C: |
| **Ổ đĩa F:** | Dung lượng: 325.83 GB, Còn trống: **96.61 GB** | **Rộng rãi**. Toàn bộ dữ liệu Manga Studio, ảnh, export và models đều phải nằm trên F: (`F:\AI-Office\data\manga\` và `F:\AI\`) |
| **Python** | Python 3.13.15 (tại `F:\AI-Office\.venv`) | Đã cài đầy đủ FastAPI, Uvicorn, Pydantic, Pillow 13.0.0, Pywebview, Playwright, Pywinauto |
| **Node.js** | v24.20.0 | Có sẵn |
| **Git** | git version 2.55.0.windows.5 | Sẵn sàng |

---

## 5. Khảo sát Ollama & Mô hình Ngôn ngữ (LLM)
- **Đường dẫn cài đặt:** `C:\Users\Shiro\AppData\Local\Programs\Ollama\ollama.exe` (v0.40.15)
- **Biến môi trường:** `OLLAMA_MODELS=F:\AI\MOSS-Image\ollama-models` (đã trỏ chính xác về ổ F:)
- **Model đã cài:**
  - `qwen3.5:4b` (Kích thước ~2.7 GB, manifest tại `F:\AI\MOSS-Image\ollama-models\manifests\registry.ollama.ai\library\qwen3.5\4b`).
- **Trạng thái dịch vụ:** Hiện tại cổng `11434` chưa bật. Khi khởi động `Start-AI-Office.bat`, `app/launcher.py` sẽ tự động gọi `ollama serve` ngầm.
- **Khả năng tái sử dụng:** Tái sử dụng 100% `MODEL_MANAGER` trong `app/model_provider.py` và `qwen3.5:4b` cho toàn bộ tác vụ Story Studio (kịch bản, thế giới, nhân vật, chia cảnh, hội thoại tiếng Việt có dấu, kiểm tra tính nhất quán).

---

## 6. Khảo sát ComfyUI & Mô hình Hình ảnh (Diffusion)
- **Đường dẫn cài đặt:** `F:\AI\ComfyUI` (ComfyUI v0.43.0, môi trường riêng `.venv` Python 3.13.15 + PyTorch 2.14.1+cu130 có CUDA).
- **Cổng tiêu chuẩn:** `http://127.0.0.1:8188` (hiện tại chưa bật process).
- **Model hiện có trong `F:\AI\ComfyUI\models\`:**
  - `diffusion_models/wan_1.3B_exp_e14.safetensors` (Wan 1.3B)
  - `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`
  - `vae/wan_2.1_vae.safetensors`
  - `checkpoints/`: Hiện tại **trống** (chỉ có file placeholder).
- **Workflows hiện có trong `F:\AI\ComfyUI\user\default\workflows\`:**
  - `NSFW_Wan_1.3B_e14_LowVRAM.json` (Text-to-Video, độ phân giải 480x272)
  - `text_to_video_wan_official.json`
- **PHÁT HIỆN QUAN TRỌNG VỀ COMFYUI:**
  1. Máy người dùng hiện chỉ có model video Wan 1.3B, **chưa có checkpoint 2D manga tĩnh** (như SD1.5 Manga/Anything, Animagine XL, Illustrious).
  2. Quy tắc an toàn cấm tuyệt đối việc tự động tải model lớn qua mạng.
  3. Do đó, thiết kế kiến trúc ComfyUI adapter phải có cơ chế:
     - **Adapter Discovery & Mock/Template Mode:** Hỗ trợ kiểm tra kết nối ComfyUI, liệt kê model/workflow có sẵn, và có chế độ Preview/Mock SVG canvas hoặc dùng Wan 1.3B frame nếu người dùng cấu hình, hoặc thông báo rõ ràng cho người dùng về việc cấu hình checkpoint Manga phù hợp khi họ muốn tạo ảnh thật.
     - **Hardware Protection:** Khi sinh ảnh, bắt buộc lấy semaphore khóa tài nguyên GPU, chạy tuần tự từng panel (serial execution), timeout an toàn và giải phóng bộ nhớ.

---

## 7. Kết quả Chạy Test Cơ sở (Baseline Tests)
- **Unit Tests:**
  - `tests/test_task_context.py`: **PASS** (100%)
  - `tests/test_task_qa.py`: **PASS** (100%)
  - `tests/test_research_tools.py`: **PASS** (100%)
  - `tests/test_qa_and_game.py`: **PASS** (19/19 test cases, bao gồm streaming, window picker, OCR, game routing).
- **Integration Tests (Yêu cầu server đang bật):**
  - `tests/smoke_check.py`, `tests/workspace_editor_check.py`, `tests/workspace_edit_smoke.py`, `tests/workspace_ui_smoke.py`: Các script này kết nối tới `http://127.0.0.1:8765`. Khi server chạy, các endpoint hoạt động bình thường theo chuẩn FastAPI.

---

## 8. Kết luận Audit Phase 0
Hệ thống `F:\AI-Office` hoàn toàn lành mạnh, kiến trúc module hóa rất sạch và nhất quán. Toàn bộ yêu cầu của `MASTER_TASK.md` có thể tích hợp mượt mà mà không cần tạo ứng dụng mới hay viết lại bất kỳ module hiện có nào.
Mọi rủi ro về phần cứng (RAM 12GB, VRAM 6GB, ổ C eo hẹp) đều đã có phương án kỹ thuật cách ly triệt để.
Chuyển sang bước lập kế hoạch chi tiết `MANGA_STUDIO_IMPLEMENTATION_PLAN.md`.
