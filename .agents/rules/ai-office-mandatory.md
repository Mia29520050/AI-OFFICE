---
trigger: always_on
description: Quy định bắt buộc vận hành AI Office - VRAM lock, Export path, Engine isolation, Skill-first
---

# Quy Định Vận Hành Bắt Buộc (AI Office Mandatory Rules)

1. **Lưu trữ Thành phẩm (Export Rule):**
   - Mọi tệp kết quả đầu ra/thành phẩm PHẢI nằm trong `F:\AI-Office\Export\` theo phân loại:
     - `Export/Images/`: Ảnh minh họa, character design, visual asset.
     - `Export/Manga/`: Trang truyện tranh, strip, CBZ, PDF.
     - `Export/3D/`: Tài nguyên 3D, Blender (.blend, .obj, .fbx).
     - `Export/Audio/`: File âm thanh lồng tiếng, SFX, BGM.
     - `Export/Video/`: Video hoàn thiện, Motion Comic, Animation clip.

2. **Quy chuẩn Engine & Model (Engine Isolation):**
   - Mọi engine AI và model checkpoint phải nằm trong `F:\AI-Office\engine\`:
     - ComfyUI: `F:\AI-Office\engine\ComfyUI`
     - Ollama models: `F:\AI-Office\engine\MOSS-Image\ollama-models` (`OLLAMA_MODELS`)
   - Không tạo hoặc sử dụng thư mục `F:\AI` rời rạc.

3. **Khóa Phần Cứng 6GB VRAM / 12GB RAM (Hardware Guard):**
   - Tuyệt đối serialize mọi tác vụ GPU. Chỉ duy nhất 1 job inference GPU chạy tại một thời điểm (`ResourceScheduler`).
   - ComfyUI chạy với cờ `--lowvram --cpu-vae --reserve-vram 1.0`.
   - Giải phóng VRAM ngay sau khi hoàn thành inference bằng cách unload Ollama model hoặc garbage collect.

4. **Đọc Skill Trước Khi Thao Tác (Skill-First Protocol):**
   - Bắt buộc phải đọc kỹ hướng dẫn trong `.agents/skills/<skill>/SKILL.md` hoặc `skills/<skill>/SKILL.md` trước khi thao tác các tác vụ tương ứng (`voice`, `vtuber_companion`, `game_translator`, `blender_3d`, `video_gen`, `game_agent`, `weekly_radar`, `image_gen_ref`).

5. **Cấu Trúc Tệp (Project Structure):**
   - Tuân thủ nghiêm ngặt `PROJECT_STRUCTURE.md`.
   - Test suites đặt tại `tests/`, standalone scripts gom gọn trong `scripts/<subfolder>/`, tài liệu trong `docs/`, nháp trong `scratch/`.
   - KHÔNG sửa `app/main.py` hay `app/ui/*` trừ khi có chỉ đạo rõ ràng từ Coordinator.
