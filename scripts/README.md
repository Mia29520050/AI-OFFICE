# AI Office Scripts (`scripts/`)

Thư mục `scripts/` chứa các script thực thi độc lập (CLI tools, pipeline runner, benchmark utilities, QA testing) phục vụ việc vận hành, sản xuất nội dung và kiểm thử chất lượng hệ thống. Toàn bộ scripts được phân nhóm khoa học vào 4 chuyên mục con:

---

## Cấu trúc thư mục

### 1. `scripts/benchmarks/` (Đo lường & Đánh giá Hiệu năng)
Chứa các công cụ benchmark, đánh giá tốc độ sinh ảnh, đo tải VRAM/RAM, kiểm thử độ nhất quán nhân vật và so sánh mô hình.
- `benchmark_1000_tests.py`: Stress test và benchmark quy mô lớn.
- `benchmark_manga_10k.py`: Benchmark tải xử lý Manga pipeline.
- `run_anime_benchmark.py`: Benchmark đo lường chất lượng anime generation & continuity.
- `run_real_comfy_benchmark.py`: Đo đạc hiệu năng thực tế kết nối ComfyUI cục bộ (`127.0.0.1:8188`) dưới GPU lock.
- `run_real_8cases_benchmark.py`: Bộ kiểm thử 8 kịch bản prompt thực tế.
- `eval_raiden_fidelity.py`: Kiểm thử đo độ trung thực hình ảnh nhân vật Raiden Shogun.
- `eval_reasoning.py`: Đánh giá năng lực suy luận của mô hình LLM.
- `evaluate_real_benchmark_metrics.py`: Tính toán và tổng hợp các metric benchmark.
- `compare_models.py`: So sánh chất lượng và tốc độ giữa các checkpoint/GGUF models.

### 2. `scripts/qa/` (Kiểm thử Giao diện & Chất lượng)
Chứa các công cụ tự động hóa QA, Playwright test, chụp ảnh audit giao diện và xác minh sản phẩm.
- `test_dual_interface_qa.py`: Kiểm thử đồng thời Web UI và Desktop UI.
- `test_gemini_mobile_playwright.py`: Playwright end-to-end test cho giao diện mobile & chat Gemini.
- `test_both_themes_qa.py`: Kiểm thử hiển thị Dark / Light mode.
- `simulate_user_journey.py`: Giả lập toàn bộ hành trình trải nghiệm của người dùng.
- `capture_live_ui_audit.py`, `capture_sidebar_qa.py`: Chụp ảnh snapshot giao diện thực tế.
- `audit_v7_masterpiece.py`, `compile_master_inspection.py`: Tổng hợp báo cáo kiểm định chất lượng nghệ thuật.
- `verify_all_pages_audit.py`, `verify_deliverables.py`: Kiểm định trang storyboard và tệp bàn giao.
- `verify_manga_aesthetic_upgrade.py`, `verify_manga_studio_reforms.py`: Đánh giá nâng cấp thẩm mỹ Manga Studio.
- `verify_v7_face_clearance_and_acceptance.py`: Đánh giá độ nét và chuẩn khuôn mặt V7.
- `debug_manga_ui.py`: Công cụ gỡ lỗi hiển thị Manga Studio.

### 3. `scripts/tools/` (Công cụ Vận hành & Thiết lập)
Chứa các script CLI hỗ trợ cài đặt môi trường, tải model, tinh chỉnh LoRA, đồng bộ font chữ.
- `download_anima_turbo_models.py`: Tải các mô hình Anima Turbo DiT và VAE cần thiết.
- `download_civitai_model.py`: Script hỗ trợ tải mô hình từ Civitai API.
- `setup_claude_ollama.py`: Cấu hình Ollama model phục vụ tác vụ nội bộ.
- `setup_manga_fonts.py`: Kiểm tra và cài đặt font chữ truyện tranh tiêu chuẩn.
- `train_qlora.py`: Pipeline huấn luyện QLoRA cho LLM/VLM cục bộ.
- `export_to_ollama.py`: Chuyển đổi và đóng gói model sang Ollama Modelfile.
- `create_desktop_shortcut.py`: Tạo phím tắt khởi chạy nhanh trên Desktop.
- `apply_claude_makeover.py`, `unify_ui_ux.py`: Công cụ chuẩn hóa giao diện UI/UX.
- `crawl_anhkysuai_kho.py`, `fetch_manga_info.py`: Công cụ thu thập tài nguyên và dữ liệu.
- `generate_codebase_graph.py`: Trực quan hóa kiến trúc codebase.

### 4. `scripts/experiments/` (Thử nghiệm & Tạo mẫu)
Chứa các kịch bản thử nghiệm tạo hình ảnh, storyboard manga, render prompt phức tạp và tinh chỉnh chi tiết:
- `generate_official_chapter1.py`, `generate_chapter1_scenes.py`, `generate_ch01_color_scenes.py`: Kịch bản thử nghiệm và tạo chương manga.
- `render_blood_princess_*.py`: Chuỗi thử nghiệm tạo hình nhân vật Blood Princess từ v4 đến v8.
- `render_real_anime_manga_page*.py`: Render các trang manga hoàn chỉnh với bố cục tự nhiên.
- `test_anima_deltamix.py`, `test_anima_ref_adapter.py`: Thử nghiệm adapter tham chiếu hình ảnh và Anima DeltaMix.
- `test_rule_of_thirds_generation.py`, `test_natural_manga_panels.py`, `test_scenery_enhancer.py`: Nghiên cứu bố cục, khung hình và cảnh nền.
- `generate_reasoning_data.py`, `generate_manga_japanese_grammar_10k.py`: Tạo dữ liệu huấn luyện thử nghiệm.

---

## Nguyên tắc khi thêm script mới
1. Mọi script độc lập phải đặt vào đúng thư mục chuyên mục (`benchmarks/`, `qa/`, `tools/`, hoặc `experiments/`).
2. Không import trực tiếp từ thư mục `scratch/`.
3. Script phải có `ROOT` path resolution chuẩn xác để chạy được từ bất kỳ thư mục làm việc nào.
4. Mọi engine và model phải trỏ về `F:\AI-Office\engine\`, xuất file thành phẩm vào `F:\AI-Office\Export\`.
