---
name: image_gen_ref
description: Tạo ảnh chất lượng cao với ComfyUI Anima DeltaMix, khóa danh tính và vóc dáng nhân vật qua AnimaRefAdapter và Danbooru prompt.
---

# Kỹ Năng Image Gen Ref (ComfyUI & Character Identity Lock)

## 1. Mục Đích
Tạo ảnh minh họa anime/manga chuẩn xác với tỷ lệ khung hình tùy biến (1:1, 3:4, 16:9, 9:16), định dạng (PNG, WEBP, JPEG) và khóa danh tính/khuôn mặt qua ảnh tham chiếu (Ref Adapter).

## 2. Quy Tắc Bắt Buộc
- **Đầu ra hình ảnh:** Mọi ảnh thành phẩm xuất bản PHẢI lưu tại `F:\AI-Office\Export\Images\` (hoặc `Export/Manga/` nếu là trang truyện).
- **Engine chuẩn:** Kết nối tới ComfyUI cục bộ tại `127.0.0.1:8188` (`F:\AI-Office\engine\ComfyUI`).
- **Khóa GPU:** Phải thông qua `ResourceScheduler` hoặc kiểm tra port để đảm bảo không xung đột VRAM 6GB.
- **Tích hợp:** Phối hợp cùng `app/chat_image_handler.py` và `app/manga_comfy.py`.
