# AI Office Core Application (`app/`)

Thư mục `app/` chứa toàn bộ mã nguồn ứng dụng lõi (Backend FastAPI và giao diện Desktop Frontend WebView2) của hệ thống **AI Office**.

---

## 1. Phân nhóm kiến trúc modules

### 1.1. Core Server & Runtime
- `main.py`: Entry point của FastAPI backend (port `8765`), khởi tạo SQLite database `data/office.db`, cấu hình CORS, static file routing và đăng ký router cho toàn hệ thống.
- `launcher.py`: Trình khởi chạy cửa sổ desktop pywebview với Microsoft WebView2, cơ chế tự động hạ quyền nếu chạy elevated để bảo đảm tương thích với bộ gõ tiếng Việt (UniKey, EVKey), icon infinity chính hãng và quản lý tiến trình.
- `model_provider.py`: Quản lý kết nối tới Ollama local runtime (`qwen3.5:4b`), serialize hàng đợi inference để tối ưu hóa trên máy tính RAM 12-16GB / VRAM 6GB.
- `task_context.py`: Lưu vết ngữ cảnh, nhiệm vụ, kế hoạch từng bước và trạng thái thực thi vào SQLite.
- `task_qa.py`: QA Agent thẩm định kết quả thực thi nhiệm vụ dựa trên Acceptance Conditions.
- `workspace_editor.py`: Workspace Editor Agent - cung cấp cơ chế đọc file an toàn trong phạm vi workspace, sinh unified diff, xác thực SHA-256 tránh stale edit, ghi atomic, lưu backup và hỗ trợ rollback có kiểm tra hash.

### 1.2. Automation & Perception Agents
- `browser.py`: Tự động hóa trình duyệt qua profile Chrome riêng biệt (`data/browser-profile`), trích xuất DOM compact, chặn truy cập mạng nội bộ và yêu cầu phê duyệt từng bước hành động.
- `computer.py`: Quan sát màn hình, trích xuất cây UI Automation (UIA) và chụp màn hình desktop.
- `computer_use.py`: Planner cho Computer Use Agent, sinh đề xuất từng click/type/scroll và chờ xác nhận từ người dùng.
- `ocr_helper.py`: Trợ lý OCR nhận dạng văn bản trên ảnh màn hình.
- `research_tools.py`: Công cụ tìm kiếm tệp cục bộ và công cụ nghiên cứu nội dung.
- `game_agent.py` & `game_playbooks.py`: Agent điều khiển tương tác trò chơi và các kịch bản hành vi.
- `vtuber_models.py`: Quản lý mô hình Live2D / VTuber ảo hiển thị trên giao diện.

### 1.3. Manga Studio & Anime Intelligence
- `manga_studio.py`: Router API chính cho Manga Studio: CRUD Series, Volumes, Chapters, Characters, Storyboard, Compositor và Assets.
- `manga_story.py`: Story Engine - quản lý hồ sơ nhân vật (Locked Traits, Speech Rules), sinh kịch bản phân cảnh và kiểm định tính nhất quán (Deterministic & LLM Continuity Checks).
- `manga_composer.py`: Manga Compositor - ghép các panel ảnh thành trang manga hoàn chỉnh, kẻ đường viền khung tranh, vẽ bong bóng thoại (speech bubble) tiếng Việt có đuôi định hướng, áp screentone và xuất sang CBZ / PDF.
- `manga_comfy.py`: ComfyUI Adapter - kết nối tới ComfyUI cục bộ, ResourceScheduler GPU lock chống xung đột VRAM, ModelRegistryManager và fallback mock generator.
- `manga_illustrator.py`: Bộ sinh đặc tả tạo hình nhân vật và cấu trúc prompt tạo ảnh diffusion.
- `manga_validator.py`: Thẩm định chất lượng hình ảnh manga, phát hiện lỗi giải phẫu/artifacts.
- `manga_benchmark.py`: Bộ kiểm thử đo lường chuẩn hóa Anime Intelligence Benchmark.
- `manga_metrics.py`: Công thức tính toán các chỉ số chất lượng hình ảnh, độ tương phản và điểm số continuity.

### 1.4. Frontend UI (`app/ui/`)
- `index.html`: Giao diện người dùng đơn trang phong cách Dark VS Code Workbench: Activity Rail, Explorer, Central Workspace, Manga Studio Canvas, Live2D Viewer, Tasks Panel và Status Bar.
- `assets/`: Biểu tượng ứng dụng (`ai-office.ico`, `ai-office-icon.png`), font chuẩn tiếng Việt `Inter-Variable.ttf`, và thư viện Live2D Cubism Framework.
