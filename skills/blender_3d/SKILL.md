---
name: blender_3d
description: Điều khiển và tự động hóa Blender Python API để tạo mô hình 3D, dựng phối cảnh phối cảnh anime và xuất assets 3D.
---

# Kỹ Năng Blender 3D (Automated Modeling & Scene Staging)

## 1. Mục Đích
Tạo dựng khung cảnh không gian 3D, camera phối cảnh làm khung nền cho manga/anime, xuất mô hình 3D cho VTuber/Unity.

## 2. Quy Tắc Bắt Buộc
- **Đầu ra 3D:** Mọi asset xuất khẩu (.blend, .obj, .fbx, render preview) PHẢI lưu tại `F:\AI-Office\Export\3D\`.
- **Tối ưu render:** Chạy chế độ headless/background (`blender -b`) với số samples phù hợp, không xung đột tài nguyên GPU khi ComfyUI đang hoạt động.
