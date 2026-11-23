# MANGA STUDIO INTEGRATION – IMPLEMENTATION PLAN & ARCHITECTURE
**Feature Name:** Manga Studio  
**Host Application:** AI Office (`F:\AI-Office`)  
**Target Hardware:** Lenovo LOQ (i5-12450HX, RTX 3050 Laptop 6GB VRAM, 12GB RAM)  
**Storage Partition:** F: Drive (`F:\AI-Office\data\manga\` và `F:\AI\`)  
**Orchestration Model:** Swarm-Ready Multi-Agent Architecture

---

## 1. Nguyên Tắc Thiết Kế Cốt Lõi (Non-Negotiable Rules)
1. **Không tạo app mới:** Tích hợp trực tiếp vào giao diện và backend FastAPI/WebView2 hiện có của AI Office.
2. **Không rewrite mã nguồn hiện có:** Tận dụng 100% các pattern hiện hành (`register_routes`, `MODEL_MANAGER`, `init_db`, `DATA` directory, `workspace_editor`).
3. **Đa dự án độc lập (Multi-series):** Không hardcode bất kỳ series nào (MOONLIGHT CLASSROOM chỉ là dữ liệu mẫu).
4. **Hybrid Art Direction:** Hỗ trợ cả 2 phong cách (Manga Nhật B&W cổ điển và Manga màu phong cách Nhật) tùy chỉnh linh hoạt ở cấp Series, Volume, Chapter, Page.
5. **Local-first & Bảo vệ phần cứng:**
   - LLM: Dùng Ollama `qwen3.5:4b` có sẵn tại `F:\AI\MOSS-Image\ollama-models`.
   - VRAM 6GB / RAM 12GB: Khóa tài nguyên nghiêm ngặt (`ResourceScheduler` / Semaphore = 1), không chạy song song LLM và Image Diffusion.
   - Không tự động tải model lớn qua mạng; có chế độ Mock/Template/Adapter an toàn khi chưa có checkpoint diffusion 2D.
6. **Thoại tiếng Việt tách biệt (Vector/Text Layer):**
   - Tuyệt đối không để AI diffusion vẽ chữ lên ảnh.
   - Toàn bộ Speech bubble, thought bubble, SFX, caption được vẽ đè bằng vector/Pillow engine với font Unicode tiếng Việt chuẩn (`app/ui/assets/Inter-Variable.ttf`).

---

## 2. Thiết Kế Kiến Trúc & Dữ Liệu

### 2.1 Backend Modules (`app/`)
- `app/manga_studio.py`: Module trung tâm chứa router FastAPI (`register_manga_routes(app)`).
- `app/manga_story.py`: Logic Story Studio (Lore, nhân vật, phân cảnh, kiểm tra tính nhất quán qua Ollama).
- `app/manga_comfy.py`: ComfyUI Adapter (phát hiện API 127.0.0.1:8188, quản lý queue, serialization, mock/real generation).
- `app/manga_composer.py`: Engine dàn trang manga, chia panel (gutters/frames), vẽ bóng thoại tiếng Việt (speech bubbles) và xuất file (PNG, PDF, CBZ).

### 2.2 Cơ sở dữ liệu SQLite (`data/office.db`)
Mở rộng trực tiếp `office.db` thông qua `init_db()` với các bảng độc lập, có khóa ngoại và chỉ mục:
1. `manga_series`: Quản lý danh sách các bộ truyện (id, title, slug, synopsis, genre, art_style, reading_direction, settings_json, created_at, updated_at).
2. `manga_volumes`: Quản lý các tập/quyển (id, series_id, number, title, metadata_json).
3. `manga_chapters`: Quản lý các chương (id, series_id, volume_id, number, title, synopsis, status, canon_snapshot_json, created_at).
4. `manga_characters`: Hồ sơ nhân vật (id, series_id, name, identity_json, personality_json, speech_rules_json, locked_traits_json).
5. `manga_character_states`: Trạng thái nhân vật theo phân cảnh (id, character_id, costume_json, appearance_json, emotions_json).
6. `manga_scenes`: Danh sách cảnh trong chương (id, chapter_id, position, summary, location, characters_json, content_json).
7. `manga_storyboard_pages`: Trang phân cảnh (id, chapter_id, page_number, layout_template, status).
8. `manga_panels`: Từng ô tranh (id, page_id, panel_number, prompt_json, dialogue_json, sfx_json, status).
9. `manga_art_jobs`: Quản lý hàng đợi sinh ảnh ComfyUI (id, panel_id, status, attempt, seed, input_json, output_asset_id, error_text, created_at, updated_at).
10. `manga_assets`: Quản lý file ảnh/tài nguyên trên ổ đĩa (id, series_id, owner_type, owner_id, file_path, metadata_json, checksum, created_at).
11. `manga_exports`: Lịch sử xuất bản (id, chapter_id, format, output_path, status, created_at).

### 2.3 Cấu trúc lưu trữ tệp tin trên ổ F: (`F:\AI-Office\data\manga\`)
```
F:\AI-Office\data\manga\
└── projects\
    └── <series-id>\
        ├── series.json
        ├── characters\
        │   └── <character-id>\
        │       ├── profile.json
        │       └── references\ (ảnh mẫu, expression sheets)
        ├── chapters\
        │   └── <chapter-id>\
        │       ├── chapter.json
        │       ├── scenes.json
        │       ├── storyboard.json
        │       ├── panels\
        │       │   └── <panel-id>\ (ảnh thô, prompt, qa)
        │       └── pages\
        │           └── page_01.png (ảnh trang đã ghép thoại hoàn chỉnh)
        └── exports\
            ├── <chapter-title>.cbz
            └── <chapter-title>.pdf
```

### 2.4 Giao diện người dùng (`app/ui/index.html`)
- Thêm icon Manga Studio vào **Activity Bar** (nút Manga Studio).
- Thêm container trang chuyên biệt `#page-manga` có các tab:
  1. **Series Hub:** Tạo, chọn, xem danh sách truyện, cấu hình B&W / Color, khổ giấy, chiều đọc (Phải qua Trái / Trái qua Phải).
  2. **Story Studio:** Quản lý kịch bản, nhân vật, dòng thời gian, thế giới; trình soạn thảo chương và nút sinh kịch bản tự động bằng Ollama Qwen3.5-4B.
  3. **Storyboard & Art:** Bảng storyboard trực quan từng trang, xem trước prompt, chọn tham chiếu nhân vật, theo dõi tiến độ sinh ảnh panel.
  4. **Manga Composer:** Xem trước trang manga hoàn chỉnh, kéo thả / chỉnh sửa bóng thoại (speech bubble), căn chỉnh chữ tiếng Việt, xem screentone / color rendering.
  5. **Export & Queue:** Quản lý hàng đợi sinh ảnh, nút tạm dừng/tiếp tục, tải về file CBZ/PDF/PNG.

---

## 3. Thiết Kế Swarm (/swarm) Trong Quá Trình Triển Khai
Nhằm thực hiện yêu cầu phối hợp nhiều agent tự động của người dùng, phân chia công việc theo các vai trò chuyên biệt:

```
               ┌────────────────────────────────────────────────────────┐
               │         manga-coordinator (Điều phối tổng)             │
               │  - Giữ board, phân tách task, kiểm soát merge/sync     │
               └───────────┬────────────────────────────────┬───────────┘
                           │                                │
          ┌────────────────┴───────────────┐   ┌────────────┴────────────────┐
          │   manga-writer (Nội dung)      │   │    manga-artist (Đồ họa)    │
          │ - Story Studio, kịch bản       │   │ - ComfyUI adapter, queue    │
          │ - Nhân vật, hội thoại, canon   │   │ - Low-VRAM lock, prompts    │
          │ - Tích hợp Ollama Qwen3.5-4B   │   │ - Panel generation pipeline │
          └────────────────┬───────────────┘   └────────────┬────────────────┘
                           │                                │
          ┌────────────────┴───────────────┐   ┌────────────┴────────────────┐
          │  manga-composer (Dàn trang)    │   │   manga-verifier (Kiểm định)│
          │ - Layout, panel frames, gutters│   │ - Chạy test unit, regression│
          │ - Vector bóng thoại tiếng Việt │   │ - Đo đạc RAM/VRAM thực tế   │
          │ - Xuất PNG, PDF, CBZ           │   │ - Bắt lỗi rollback an toàn  │
          └────────────────────────────────┘   └─────────────────────────────┘
```

---

## 4. Kế Hoạch 6 Giai Đoạn Chi Tiết

### Phase 0: Hoàn tất Audit & Khởi tạo An toàn (Hiện tại)
- Tạo báo cáo audit `MANGA_STUDIO_AUDIT.md`.
- Tạo kế hoạch kỹ thuật `MANGA_STUDIO_IMPLEMENTATION_PLAN.md`.
- Tạo snapshot Git ban đầu (Initial Baseline Commit) để đảm bảo 100% khả năng phục hồi nếu có sự cố.

### Phase 1: Skeleton Tích Hợp & Quản Lý Series (Series CRUD)
- Khởi tạo bảng `manga_series`, `manga_volumes`, `manga_chapters`, `manga_assets` trong `init_db()`.
- Tạo file `app/manga_studio.py` với các API CRUD series.
- Cập nhật `app/main.py`: đăng ký `register_manga_routes(app)`.
- Cập nhật `app/ui/index.html`: thêm tab Manga Studio vào Activity Bar và khung điều hướng Series Hub.
- Viết test `tests/test_manga_series.py` kiểm tra tạo, sửa, liệt kê và lưu trữ series.
- **Tiêu chuẩn nghiệm thu:** AI Office khởi động bình thường, mở Manga Studio tạo được nhiều series độc lập, không lỗi regression.

### Phase 2: Story Studio (Kịch Bản, Nhân Vật, Canon & Thoại Tiếng Việt)
- Xây dựng `app/manga_story.py`:
  - Quản lý hồ sơ nhân vật (tên, ngoại hình, tính cách, giọng thoại, đặc điểm bắt buộc).
  - Tích hợp Ollama `qwen3.5:4b` qua `MODEL_MANAGER` để sinh ý tưởng, dàn ý chương, phân cảnh (scenes).
  - Kiểm tra tính nhất quán (Continuity Check): phát hiện mâu thuẫn nhân vật, địa điểm, thời gian.
- Giao diện Story Studio trên UI: cây kịch bản, chỉnh sửa nhân vật, xem lịch sử phiên bản.
- Viết test `tests/test_manga_story.py` kiểm thử sinh kịch bản tiếng Việt có cấu trúc JSON hợp lệ.

### Phase 3: ComfyUI Adapter & Quản Lý Hàng Đợi (Resource Scheduler)
- Xây dựng `app/manga_comfy.py`:
  - Kết nối ComfyUI tại `http://127.0.0.1:8188`.
  - Cơ chế dò tìm model/workflow thực tế trên máy người dùng.
  - Chế độ Mock/Template an toàn khi ComfyUI offline hoặc chưa có checkpoint 2D: sinh placeholder panel hợp lệ để pipeline tiếp tục chạy mà không bị crash.
  - `ResourceScheduler`: Semaphore giới hạn 1 tác vụ GPU tại một thời điểm, kiểm tra VRAM trước khi submit prompt, cơ chế timeout và hủy job an toàn.
  - Lưu trữ thông số tái lập (seed, prompt, model, workflow id).
- Viết test `tests/test_manga_comfy.py` kiểm thử hàng đợi, trạng thái job, khả năng khôi phục sau restart.

### Phase 4: Character Studio & Storyboard Studio
- Bổ sung bộ phân cảnh chi tiết: từ Scene -> Page -> Panels (gồm góc máy, cỡ cảnh, nhân vật xuất hiện, biểu cảm, vị trí bóng thoại).
- Cung cấp các layout template mẫu (4 ô, 6 ô, splash page, phong cách shonen, seinen).
- Cơ chế nạp reference nhân vật vào workflow sinh ảnh để giữ tính nhất quán ngoại hình.
- Viết test `tests/test_manga_storyboard.py`.

### Phase 5: Manga Composer & Xuất File (CBZ, PDF, PNG)
- Xây dựng `app/manga_composer.py`:
  - Dàn trang hoàn chỉnh: ghép các panel theo kích thước gutter, khung trang chuẩn A4/B5/Webtoon.
  - Bộ tạo bóng thoại (Speech bubble engine): hỗ trợ thoại tròn, bóng thoại gắt, bóng thoại suy nghĩ, SFX.
  - Sử dụng font Unicode tiếng Việt (`app/ui/assets/Inter-Variable.ttf`) để vẽ chữ nét căng, tuyệt đối không bị lỗi font hoặc nhòe.
  - Bộ lọc hiệu ứng: Screentone, hatching, tốc tuyến (speed lines) cho B&W; cân chỉnh màu cel-shading cho Color.
  - Bộ xuất file: PNG từng trang, file PDF chuẩn in/đọc, và file nén truyện tranh CBZ (Comic Book Zip).
- Viết test `tests/test_manga_composer.py`.

### Phase 6: Chế Độ Tự Động Hóa End-to-End & Tổng Nghiệm Thu
- Kết nối pipeline 1-click: Nhập ý tưởng/chương -> Sinh kịch bản -> Phân cảnh storyboard -> Sinh art từng panel -> Kiểm duyệt QA -> Dàn trang bóng thoại -> Xuất bản phẩm.
- Cơ chế Resume sau khi khởi động lại ứng dụng nếu đang sinh dở.
- Chạy toàn bộ regression test suite của AI Office (Chat, Tasks, Skills, Workspace Editor, Tools, Game, VTuber).
- Xuất báo cáo hoàn thành đầy đủ kèm 1 chương truyện mẫu minh họa.

---

## 5. Danh Sách Tệp Sẽ Thêm Mới & Chỉnh Sửa

### Tệp thêm mới:
1. `app/manga_studio.py` – Controller chính và REST API cho Manga Studio.
2. `app/manga_story.py` – Engine kịch bản, nhân vật, continuity qua Ollama.
3. `app/manga_comfy.py` – Adapter giao tiếp ComfyUI và hàng đợi GPU ResourceScheduler.
4. `app/manga_composer.py` – Engine dàn trang, vẽ bóng thoại tiếng Việt, xuất PNG/PDF/CBZ.
5. `tests/test_manga_studio.py` – Test tổng hợp API & workflow của Manga Studio.
6. `tests/test_manga_composer.py` – Test dàn trang, render bóng thoại tiếng Việt và xuất file.

### Tệp chỉnh sửa (có phương án rollback):
1. `app/main.py` – Thêm bảng `manga_*` vào `init_db()` và đăng ký `register_manga_routes(app)`.
2. `app/ui/index.html` – Thêm tab Manga Studio trên Activity Bar và view container `#page-manga`.
3. `requirements.txt` – Bổ sung `reportlab>=4.0` hoặc `pypdf` (nếu cần cho xuất PDF nguyên bản) và `pydantic` models nếu cần (hiện Pillow đã có sẵn 13.0.0).

---

## 6. Đánh Giá Rủi Ro & Chiến Lược Rollback

| Rủi ro | Mức độ | Biện pháp giảm thiểu |
|---|---|---|
| **VRAM 6GB bị tràn (CUDA OOM)** | Cao | Khóa cứng `ResourceScheduler` max 1 job tại một thời điểm; giải phóng VRAM giữa các panel; không chạy cùng lúc Ollama và ComfyUI |
| **ComfyUI chưa có checkpoint 2D manga** | Cao | Xây dựng chế độ Mock/Template Adapter: khi chưa có model 2D, pipeline vẫn hoàn thành với panel draft vector/placeholder, thông báo rõ ràng cho người dùng cấu hình model |
| **Ổ đĩa C: bị đầy (chỉ còn 15.9GB)** | Nghiêm trọng | Cấu hình toàn bộ đường dẫn lưu trữ sang `F:\AI-Office\data\manga\` và `F:\AI\`. Tuyệt đối không ghi file tạm vào `%TEMP%` trên ổ C |
| **Lỗi font chữ tiếng Việt trên manga** | Trung bình | Sử dụng trực tiếp font `Inter-Variable.ttf` đã nhúng sẵn trong `app/ui/assets/` với encoding UTF-8, hỗ trợ đầy đủ dấu thanh tiếng Việt |
| **Xung đột mã nguồn AI Office cũ** | Thấp | Toàn bộ mã Manga Studio nằm ở module riêng (`manga_*.py`); DB thêm bảng mới, không sửa đổi các bảng `tasks`, `messages`, `projects` cũ |

### Kế hoạch Rollback:
- Tạo Git snapshot commit trước khi bắt đầu Phase 1.
- Lưu trữ bản sao lưu `data/office.db` trước khi chạy migration bảng mới.
- Nếu cần hủy bỏ, chỉ cần xóa bỏ lời gọi `register_manga_routes` trong `app/main.py` và khôi phục commit gốc.
