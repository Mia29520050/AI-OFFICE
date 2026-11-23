# AI Office Test Suite & QA (`tests/`)

Thư mục `tests/` chứa toàn bộ các bài kiểm thử tự động (Unit Tests, Integration Tests) và các kịch bản kiểm tra chất lượng (QA / Smoke Check) của hệ thống **AI Office**.

---

## 1. Unit & Integration Tests (Chạy bằng Pytest)

Cấu hình thực thi đã được tối ưu trong `pytest.ini` (tự động bỏ qua cache provider bị giới hạn quyền truy cập và lọc warnings).

Lệnh chạy toàn bộ test suite:
```powershell
.venv\Scripts\python.exe -m pytest
```

Hoặc chạy từng module:
```powershell
.venv\Scripts\python.exe -m pytest tests\test_manga_composer.py
```

### Danh mục test suites:
- `test_anime_benchmark_specs.py`: Kiểm thử các đặc tả benchmark của Anime Intelligence.
- `test_anime_intelligence_benchmark.py`: Kiểm thử bộ sinh kịch bản và đo lường benchmark.
- `test_manga_comfy.py`: Kiểm thử ComfyUI adapter, ResourceScheduler (GPU lock), workflow discovery và mock panel generator.
- `test_manga_composer.py`: Kiểm thử bộ ghép trang manga (PIL compositor), speech bubble tiếng Việt, screentones, xuất CBZ và PDF.
- `test_manga_metrics.py`: Kiểm thử các hàm tính toán chỉ số chất lượng hình ảnh, độ tương phản và continuity score.
- `test_manga_story.py`: Kiểm thử CharacterProfile, locked traits, speech rules, scene planning và deterministic continuity checker.
- `test_manga_studio.py`: Kiểm thử toàn bộ REST API endpoints của Manga Studio (Series, Volume, Chapter, Character, Storyboard, Export).
- `test_qa_and_game.py`: Kiểm thử QA verification, tọa độ Computer Use, Live2D/game agent mapping.
- `test_research_tools.py`: Kiểm thử công cụ nghiên cứu, duyệt tệp và mock web search.
- `test_task_context.py`: Kiểm thử quản lý ngữ cảnh nhiệm vụ và lưu trữ SQLite.
- `test_task_qa.py`: Kiểm thử điều kiện chấp nhận (acceptance conditions) và ghi nhận kết quả nhiệm vụ.

---

## 2. QA & Smoke Verification Scripts

Các script chạy độc lập phục vụ kiểm tra hệ thống đang chạy hoặc kiểm tra logic chuyên sâu:

- `smoke_check.py`: Kiểm tra nhanh tính sẵn sàng của backend FastAPI (`http://127.0.0.1:8765`) và UI tĩnh khi ứng dụng đang chạy.
  ```powershell
  .venv\Scripts\python.exe tests\smoke_check.py
  ```
- `qa_story_check.py`: Kiểm tra end-to-end chất lượng nội dung manga (cốt truyện tiếng Việt, phát hiện mâu thuẫn nhân vật, font chữ, screentone, xuất file).
  ```powershell
  .venv\Scripts\python.exe tests\qa_story_check.py
  ```
- `workspace_editor_check.py`: Kiểm tra cô lập cơ chế Workspace Editor (đọc file an toàn, sinh unified diff, xác thực SHA-256, atomic write, backup và rollback).
  ```powershell
  .venv\Scripts\python.exe tests\workspace_editor_check.py
  ```
- `workspace_edit_smoke.py`: Kiểm tra smoke tính năng tạo và sửa file qua API của Workspace Editor.
- `workspace_ui_smoke.py`: Kiểm tra luồng tương tác UI với Workspace Editor.
