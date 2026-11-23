# AI Office Scripts (`scripts/`)

Thư mục `scripts/` chứa các script thực thi độc lập (CLI tools, pipeline runner, benchmark utilities) phục vụ việc vận hành, sản xuất nội dung hoặc đo lường hiệu năng của hệ thống.

---

## Danh mục Scripts

| Tên Script | Mục đích | Cách thực thi |
| :--- | :--- | :--- |
| `generate_official_chapter1.py` | Pipeline sản xuất chính thức trọn vẹn Chương 1 bộ truyện **"Lớp Học Ánh Trăng" (Moonlight Classroom)**: khởi tạo series, nhân vật, phân cảnh, vẽ panel, ghép trang hoàn chỉnh và xuất gói CBZ + PDF. | `.venv\Scripts\python.exe scripts\generate_official_chapter1.py` |
| `run_anime_benchmark.py` | Chạy bộ đo lường Anime Intelligence Benchmark: đánh giá độ tuân thủ nhân vật, tính nhất quán ngữ cảnh (continuity) và các chỉ số chất lượng tạo hình. | `.venv\Scripts\python.exe scripts\run_anime_benchmark.py` |
| `run_real_comfy_benchmark.py` | Chạy đo đạc hiệu năng thực tế khi kết nối tới dịch vụ ComfyUI cục bộ (`127.0.0.1:8188`) với GPU resource lock. | `.venv\Scripts\python.exe scripts\run_real_comfy_benchmark.py` |
| `legacy_produce_moonlight_ch1.py` | Phiên bản prototype ban đầu của pipeline sản xuất Manga Chapter 1 (lưu trữ phục vụ tham chiếu). | `.venv\Scripts\python.exe scripts\legacy_produce_moonlight_ch1.py` |

---

## Nguyên tắc khi thêm script mới
1. Mọi script độc lập hoặc công cụ dòng lệnh phải đặt trong thư mục `scripts/`.
2. Không import trực tiếp từ thư mục `scratch/`.
3. Script phải có `ROOT` path resolution chuẩn xác để chạy được từ bất kỳ thư mục làm việc nào.
