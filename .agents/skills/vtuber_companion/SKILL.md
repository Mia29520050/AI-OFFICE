---
name: vtuber_companion
description: Quản lý và tương tác với Live2D / 3D Avatar VTuber, biểu cảm gương mặt, hội thoại thời gian thực và đồng bộ môi (lip-sync).
---

# Kỹ Năng VTuber Companion (Interactive Avatar & Live2D)

## 1. Mục Đích
Điều khiển trợ lý ảo hình ảnh Anime/VTuber đại diện (Live2D Cubism & 3D Avatar), tương tác hội thoại tự nhiên và phản hồi cảm xúc.

## 2. Quy Tắc Bắt Buộc
- **Tài nguyên mô hình:** Lưu trữ và quản lý trong `data/vtuber_models/` hoặc `app/ui/assets/live2d/`.
- **Hiệu năng & Tối ưu:** Giữ frame rate ổn định 60fps trên WebGL / pywebview mà không gây nghẽn RAM hệ thống (giới hạn 12GB RAM).
- **Tích hợp:** Sử dụng module `app/vtuber_models.py` để nạp model và mapping thông số biểu cảm.
