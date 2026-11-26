# AI Office - Quy Định Vận Hành Cốt Lõi (Mandatory Rules)

Tài liệu này áp dụng bắt buộc cho mọi AI Agent và Developer thao tác trong repository `F:\AI-Office`.

## 1. Lưu Trữ Tệp Thành Phẩm (Export Strict Rule)
- Mọi tệp thành phẩm sinh ra (ảnh minh họa, truyện tranh, mô hình 3D, video, âm thanh) **bắt buộc** phải được lưu trữ trong đúng chuyên mục con của `F:\AI-Office\Export\`:
  - `Export/Images/`: Ảnh đơn, minh họa nhân vật, banner, thumbnail.
  - `Export/Manga/`: Chương truyện, panel, tệp đóng gói CBZ, PDF.
  - `Export/3D/`: Mô hình 3D, tệp Blender (.blend, .obj, .fbx).
  - `Export/Audio/`: Giọng lồng tiếng TTS, nhạc nền, SFX (.mp3, .wav).
  - `Export/Video/`: Video render, hoạt hình motion comic, video clip (.mp4, .webm).
- Tuyệt đối không lưu tệp thành phẩm tự do ở thư mục gốc hoặc trong `data/` mà không liên kết Export.

## 2. Quản Lý Engine & Model (Engine Isolation)
- Toàn bộ AI engine (ComfyUI, MOSS-Image/Ollama models) nằm tập trung trong `F:\AI-Office\engine\`.
  - ComfyUI: `F:\AI-Office\engine\ComfyUI`
  - Ollama Models: `F:\AI-Office\engine\MOSS-Image\ollama-models` (biến môi trường `OLLAMA_MODELS`)
- Không để các thư mục engine rời rạc ngoài root như `F:\AI`.

## 3. Khóa Tài Nguyên Phần Cứng (Hardware VRAM 6GB / RAM 12GB Lock)
- Hệ thống chạy trên cấu hình giới hạn: **6GB VRAM / 12GB RAM**.
- Quy tắc kiểm soát tài nguyên:
  - Chỉ chạy **duy nhất 1 tiến trình GPU heavy** tại một thời điểm (tuân thủ `ResourceScheduler` / `MODEL_SEMAPHORE`).
  - ComfyUI phải luôn chạy với cờ `--lowvram --cpu-vae --reserve-vram 1.0`.
  - Khi cần tải mô hình nặng hoặc chuyển tác vụ, phải giải phóng VRAM của mô hình trước đó (`keep_alive: 0` trên Ollama hoặc gọi garbage collection).

## 4. Tuân Thủ Cấu Trúc Dự Án (Tree Compliance)
- Mọi thao tác tạo/sửa tệp phải tuân thủ nghiêm ngặt theo [PROJECT_STRUCTURE.md](file:///F:/AI-Office/PROJECT_STRUCTURE.md):
  - Mã nguồn ứng dụng: `app/` (không tự ý sửa `app/main.py` hay `app/ui/*` nếu không có yêu cầu cụ thể).
  - Kịch bản thực thi độc lập: phân loại vào `scripts/benchmarks/`, `scripts/experiments/`, `scripts/qa/`, `scripts/tools/`.
  - Bộ kiểm thử tự động: `tests/`.
  - Dữ liệu runtime/cache: `data/`.
  - Vùng nháp tạm thời: `scratch/`.

## 5. Nguyên Tắc Đọc Skill Trước Khi Thao Tác (Skill-First Protocol)
- Trước khi thực hiện bất kỳ năng lực nghiệp vụ nào (Voice, VTuber, Game Translation, 3D, Video Generation, Game Agent, Weekly Radar, Image Generation/Anima), Agent **bắt buộc phải đọc file Skill tương ứng** trong `.agents/skills/` hoặc `skills/`.
