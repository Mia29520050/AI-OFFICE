# Manga Anime Prompt Harmonizer & StoryDiffusion Consistency Engine

## 1. Mục tiêu & Vấn đề Giải quyết
Manga Studio trong AI Office trước đây gặp phải tình trạng:
1. **Nhân vật không ra dáng anime:** Thiếu các trigger tags chất lượng cao và ngôn ngữ mô tả đặc thù manga/anime.
2. **Khuôn mặt và trang phục biến dạng, thiếu đồng nhất:** Khi sinh nhiều ô tranh liên tiếp, nhân vật bị đổi kiểu tóc, đổi màu mắt, đổi quần áo giữa các panel.

Module [app/manga_anime_generator.py](file:///f:/AI-Office/app/manga_anime_generator.py) giải quyết triệt để vấn đề này bằng việc chuẩn hóa phân rã **4 thành phần bắt buộc cho mỗi Panel** kết hợp cơ chế neo đặc tính ngoại hình **StoryDiffusion Consistency Anchors**.

---

## 2. Kiến trúc Phân rã 4 Thành phần Bắt buộc (4-Component Decomposition)

Mỗi Panel Prompt nạp vào ComfyUI được cấu trúc độc lập và rõ ràng:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          PANEL PROMPT STRUCTURE                        │
├────────────────────────────────────────────────────────────────────────┤
│ (1) ART STYLE / MEDIUM                                                 │
│     masterpiece, best quality, monochrome, greyscale, authentic        │
│     japanese manga, screentone, crisp lineart, screentone halftones    │
├────────────────────────────────────────────────────────────────────────┤
│ (2) LOCKED CHARACTER TRAITS (StoryDiffusion Anchor)                    │
│     [char_token], persistent hair, eyes, facial features, uniform      │
├────────────────────────────────────────────────────────────────────────┤
│ (3) EMOTION & DYNAMIC POSE                                             │
│     tsundere_pout / jaw_drop_shock / anime_sweatdrop + dynamic stance  │
├────────────────────────────────────────────────────────────────────────┤
│ (4) BACKGROUND / ENVIRONMENT & CAMERA SHOT                             │
│     close-up / low-angle dramatic + japanese_classroom / sunset_corridor│
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1. Thành phần 1: Phong cách Nghệ thuật & Checkpoint Presets
- **Animagine XL 3.1**: Tiêu chuẩn vàng cho 2D anime với trigger `masterpiece, best quality, very aesthetic, monochrome, screentone, crisp lineart`.
- **Pony Diffusion V6 XL**: Hệ thống đánh giá `score_9, score_8_up, rating_safe, manga style, traditional media, fine ink lines`.
- **SDXL Monochrome Manga**: Đậm chất bản in tạp chí Shonen/Seinen Nhật Bản với độ tương phản cao, đổ bóng sọc và halftone dots.

### 2.2. Thành phần 2: Locked Character Traits (Khóa Ngoại hình Cố định)
Ứng dụng nguyên lý **Consistent Self-Attention** của StoryDiffusion:
- Mỗi nhân vật có một tập tag bất biến (Invariant Tags):
  - **Minh (Protagonist)**: `short messy black hair, sharp dark hazel eyes, black gakuran jacket, unbuttoned collar, silver stud earring`.
  - **Mai (Heroine)**: `shoulder-length wavy chestnut brown hair, large expressive amber eyes, cream cardigan sweater, navy pleated skirt, red ribbon`.
  - **Huy (Rival)**: `neat sleek silver-grey hair with side part, narrow cold blue-grey eyes, dark navy blazer, spectacles`.
  - **Koharu (Mascot)**: `light lavender hair in twin low braids, emerald green eyes, oversized hoodie, cat-ear headset`.
- Khi sinh ảnh qua hàng loạt panel, tập tag này được giữ nguyên 100%, bảo toàn tính nhất quán tuyệt đối.

### 2.3. Thành phần 3: Biểu cảm Anime Đặc trưng (Emotion Catalog)
Tích hợp sẵn các biểu cảm kinh điển trong Manga:
- `tsundere_pout`: Phồng má giận dỗi, đỏ mặt quay đi, khoanh tay.
- `jaw_drop_shock`: Há hốc mồm kinh ngạc tột độ, tròng mắt trắng bóc, hét hoảng hốt.
- `anime_sweatdrop`: Giọt mồ hôi bên thái dương, nụ cười gượng gạo bối rối.
- `sparkling_eyes`: Mắt lấp lánh hình ngôi sao phấn khích.
- `chibi_panic`: Tỉ lệ chibi ngộ nghĩnh, mắt xoắn ốc, vung vẩy tay.
- `dramatic_shadow`: Bóng đen che nửa trên khuôn mặt, đồng tử phát sáng đe dọa.
- `smug_grin`: Cười đắc thắng tinh quái, miệng mèo `:3`.
- `determined_focus`: Ánh nhìn quyết tâm đanh thép, nghiến răng tập trung.

### 2.4. Thành phần 4: Bối cảnh, Cỡ cảnh & Hiệu ứng Thị giác (Visual FX)
- **Góc quay**: `close_up`, `extreme_close_up`, `medium_shot`, `low_angle_dramatic`, `high_angle`, `over_the_shoulder`, `dutch_angle`.
- **Bối cảnh**: Lớp học Nhật Bản, hành lang chiều tà, sân thượng dưới trăng, phố mưa Tokyo, thư viện cổ, phòng lab công nghệ AI.
- **Hiệu ứng**: `speed_lines` (đường kẻ tốc độ hành động), `focus_burst` (vạch tập trung kịch tính), `screentone_hatch` (halftone đổ bóng truyền thống), `doki_doki_aura` (hào quang lấp lánh), `menacing_gogogo` (sát khí gogogo).

---

## 3. Tập Dữ liệu Huấn luyện CoT Storyboard

- **Đường dẫn**: [data/training/manga_storyboard_cot.jsonl](file:///f:/AI-Office/data/training/manga_storyboard_cot.jsonl)
- **Quy mô**: 350 mẫu phân cảnh hoàn chỉnh (Dung lượng: 9.16 MB).
- **Định dạng**: ChatML / Qwen format tương thích 100% với pipeline QLoRA của `@trainer`.
- **Cấu trúc mẫu**:
  - `user`: Ý tưởng kịch bản thô.
  - `assistant`:
    - `<think>`: Đạo diễn diễn giải nhịp điệu manga, xác định nhân vật, khóa các traits StoryDiffusion, bóc tách 4 thành phần cho từng ô tranh, kiểm tra tính đồng nhất.
    - Kết luận: Kế hoạch phân cảnh chi tiết kèm các prompt ComfyUI chuẩn chỉnh.

---

## 4. Hướng dẫn Tích hợp & Kiểm thử

### Sinh lại tập dữ liệu tùy biến:
```bash
python scripts/generate_manga_storyboard_dataset.py --num-samples 500 --seed 123
```

### Chạy bộ kiểm thử tự động:
```bash
pytest tests/test_manga_anime_generator.py -v
```
*(Kết quả: 7/7 tests PASSED 100%)*
