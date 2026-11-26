---
name: game_translator
description: Dịch thuật tự động và bản địa hóa nội dung game / manga / visual novel thời gian thực qua OCR và LLM.
---

# Kỹ Năng Game Translator (OCR & Realtime Localization)

## 1. Mục Đích
Chụp màn hình game/visual novel, nhận diện văn bản (OCR) và dịch ngữ cảnh sang tiếng Việt chuẩn văn phong anime/gaming.

## 2. Quy Tắc Bắt Buộc
- **Sử dụng OCR nhẹ:** Phối hợp cùng `app/ocr_helper.py` và `app/computer.py` để quét vùng hiển thị màn hình mà không làm sụt giảm FPS của game.
- **LLM Inference:** Tận dụng Ollama cục bộ (`qwen3.5:4b`) hoặc fast dictionary lookup, giải phóng VRAM ngay khi dịch xong.
