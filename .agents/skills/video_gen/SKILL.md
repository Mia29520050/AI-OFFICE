---
name: video_gen
description: Sản xuất Motion Comic, video hoạt họa ngắn và video clip từ hình ảnh tĩnh với hiệu ứng chuyển cảnh Ken Burns và SFX.
---

# Kỹ Năng Video Gen (Motion Comic & Animation Studio)

## 1. Mục Đích
Sản xuất video clip, Motion Comic định dạng 16:9 (YouTube) hoặc 9:16 (TikTok), kết hợp lồng tiếng, phụ đề động và chuyển động camera.

## 2. Quy Tắc Bắt Buộc
- **Đầu ra Video:** Mọi video render hoàn chỉnh PHẢI lưu tại `F:\AI-Office\Export\Video\`.
- **Mã nguồn tích hợp:** Sử dụng `app/motion_comic.py` và `app/motion_comic_routes.py`.
- **Quản lý VRAM:** Quá trình render video sử dụng CPU ffmpeg đa luồng hoặc GPU encoder nhẹ, tránh chiếm dụng 6GB VRAM của ComfyUI.
