---
name: voice
description: Tạo giọng nói tự nhiên, lồng tiếng nhân vật anime/manga bằng Neural TTS (Edge-TTS), sound effects (SFX) và đồng bộ phụ đề.
---

# Kỹ Năng Voice Engine (Neural TTS & Audio Production)

## 1. Mục Đích
Thực hiện chuyển văn bản thành giọng nói (Text-To-Speech) tiếng Việt & đa ngôn ngữ chất lượng cao, procedural SFX và tạo phụ đề tự động (SRT/VTT).

## 2. Quy Tắc Bắt Buộc
- **Đầu ra âm thanh:** Mọi tệp âm thanh thành phẩm xuất ra PHẢI lưu tại `F:\AI-Office\Export\Audio\`.
- **Hardware Footprint:** Sử dụng các giải pháp TTS nhẹ (như Edge-TTS hoặc lightweight neural model), không chiếm dụng VRAM của card đồ họa rời.
- **Tích hợp:** Phối hợp cùng `app/voice_engine.py` để đồng bộ timeline và hiệu ứng âm thanh.
