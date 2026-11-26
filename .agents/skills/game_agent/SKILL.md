---
name: game_agent
description: Điều khiển, tự động hóa tác vụ trong game hoặc ứng dụng qua thị giác máy tính và playbook chiến thuật.
---

# Kỹ Năng Game Agent (Vision-Based Interaction & Playbooks)

## 1. Mục Đích
Thực thi các chuỗi tương tác, kịch bản tự động trong game và ứng dụng đồ họa bằng cách quan sát màn hình và điều khiển chuột/phím an toàn.

## 2. Quy Tắc Bắt Buộc
- **Mã nguồn:** Sử dụng `app/game_agent.py` và các kịch bản định nghĩa trong `app/game_playbooks.py`.
- **An toàn thao tác:** Tuân thủ cơ chế kiểm soát của `SecurityGuard` và không thao tác ngoài phạm vi cửa sổ được chỉ định.
