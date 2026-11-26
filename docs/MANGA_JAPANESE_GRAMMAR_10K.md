# Japanese Manga Grammar & Dark Fantasy 10,000 Alignment Dataset

## 1. Mục tiêu & Chuẩn Đối sánh (Benchmark Objective)
Nâng cấp **Manga Studio** đạt năng lực thông minh và độ chuẩn mực mỹ học tương đương với **GPT-Image-2.6 Sunburst**:
- **Bố cục phân khung chuyên nghiệp (Koma-wari):** Phân chia nhịp điệu trang truyện đa dạng (Splash, Contrast, Cinematic, Yonkoma, Dynamic Action, Psychological Narrative).
- **Luồng đọc tự nhiên (Shisen-yudou):** Dẫn dắt ánh mắt từ Phải sang Trái, Trên xuống Dưới (Right-to-Left & Top-to-Bottom) theo quy chuẩn Manga Nhật Bản cổ điển.
- **Bảo vệ khuôn mặt & đôi mắt (Face & Eye Safety Clearance):** Triệt tiêu hoàn toàn tình trạng khung thoại che mặt nhân vật (`Overlap Area = 0.0 px²`, 100% Face Clearance).
- **Từ tượng thanh đè viền (Bleeding SFX):** Bố trí onomatopoeia phá vỡ đường viền khung tranh tạo chiều sâu và sức công phá thị giác.
- **Chủ đề Dark Fantasy "Huyết Cơ và Kỵ Sĩ":** Xây dựng thế giới gothic ma cà rồng tóc bạc mắt đỏ và kỵ sĩ giáp đen kiếm huyết mạch với tính đồng nhất nhân vật StoryDiffusion tuyệt đối.

---

## 2. Thông số Kỹ thuật Tập Dữ liệu 10,000 Mẫu

- **Đường dẫn tệp tin**: [data/training/manga_japanese_grammar_10k.jsonl](file:///f:/AI-Office/data/training/manga_japanese_grammar_10k.jsonl)
- **Quy mô**: **10,000 trường hợp kiểm định & huấn luyện** (Dung lượng: **141.06 MB**).
- **Định dạng**: ChatML / Qwen format tương thích 100% với SFTTrainer, Unsloth và Benchmark Evaluator.
- **Bộ sinh dữ liệu tự động**: [scripts/generate_manga_japanese_grammar_10k.py](file:///f:/AI-Office/scripts/generate_manga_japanese_grammar_10k.py).
- **Bộ kiểm thử toàn vẹn**: [tests/test_manga_japanese_grammar_10k.py](file:///f:/AI-Office/tests/test_manga_japanese_grammar_10k.py) *(5/5 tests PASSED 100%)*.

---

## 3. Ngũ Trụ Ngữ Pháp Manga Nhật Bản (The 5 Pillars)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   5 TRỤ NGỮ PHÁP MANGA NHẬT BẢN                        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. KOMA-WARI (Bố cục phân khung)                                       │
│    1-panel Splash │ 2-panel Contrast │ 3-panel Cinematic               │
│    4-panel Yonkoma (Khởi-Thừa-Chuyển-Hợp) │ 5-panel Dynamic Action     │
├────────────────────────────────────────────────────────────────────────┤
│ 2. SHISEN-YUDOU (Luồng dẫn dắt thị giác)                               │
│    Right-to-Left & Top-to-Bottom: Score = y * 3.0 - x                  │
│    Khung Trên-Phải mở đầu -> chuyển dịch theo đường Z/S                │
├────────────────────────────────────────────────────────────────────────┤
│ 3. FACE & EYE CLEARANCE ZONE (Vùng an toàn khuôn mặt)                  │
│    Vùng cấm trung tâm: [ymin: 0.28, xmin: 0.24, ymax: 0.72, xmax: 0.70]│
│    Bong bóng thoại tự động dạt về 4 góc an toàn: Overlap = 0.0 px²     │
├────────────────────────────────────────────────────────────────────────┤
│ 4. BLEEDING ONOMATOPOEIA (SFX đè viền bùng nổ)                         │
│    DON!, GOGOGO, ZASH!, BAKI!, DOKI DOKI, SHIN..., HYUUU, BAAAM!       │
├────────────────────────────────────────────────────────────────────────┤
│ 5. SPEECH BUBBLE TYPOLOGY (Phân loại khung thoại)                      │
│    speech_oval │ shout_burst │ whisper_dashed │ dark_telepathy         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Chủ đề Dark Fantasy "Huyết Cơ và Kỵ Sĩ" (Vampire Sovereign & Blood Knight)

Mỗi nhân vật được trang bị **StoryDiffusion Invariant Anchor Token** nhằm đảm bảo không bao giờ bị biến đổi ngoại hình:

1. **Huyết Cơ Carmilla (`[carmilla_vampire_sovereign]`)**:
   - Nữ chúa ma cà rồng kiêu hãnh: Tóc dài bạch kim uốn lọn, mắt ngọc huyết đỏ rực (`glowing crimson ruby eyes`), răng nanh nhỏ sắc nhọn, váy dạ hội gothic nhung đen viền ren đỏ thẫm, vương miện gai đen obsidian, vòng cổ blood ruby.
2. **Hắc Kỵ Sĩ Kaelen (`[kaelen_blood_knight]`)**:
   - Hiệp sĩ hộ vệ mang lời nguyền huyết thệ: Tóc đen rối, mắt hổ phách sắc bén, sẹo chiến chinh ngang sống mũi, đại giáp hắc thép chạm khắc phù văn ma pháp phát sáng đỏ, áo choàng rách bay trong gió, thanh Huyết Cực Kiếm tỏa huyết khí ma mị.
3. **Giáo Đầu Thánh Điện Lucian (`[lucian_silver_inquisitor]`)**:
   - Hiệp sĩ thánh chiến: Tóc vàng chải ngược, mắt xám thép, giáp bạc rực rỡ khắc thánh giá vàng, trường kiếm bạc thánh diệt ma tộc.
4. **Huyết Linh Pháp Sư Vivian (`[vivian_blood_alchemist]`)**:
   - Ma pháp sư dơi: Tóc tím búi hai bên, mắt tím huyền ảo, váy gothic lolita, đàn dơi bóng đêm bay lượn, quyền trượng pha lê dơi.

---

## 5. Cấu trúc Mẫu Huấn luyện CoT Trực quan

```json
{
  "id": "manga_10k_00001",
  "category": "japanese_manga_grammar_dark_fantasy",
  "benchmark_standard": "GPT-Image-2.6-Sunburst-Equiv",
  "koma_layout": "1_panel_splash",
  "primary_character": "Huyết Cơ Carmilla",
  "verification_metrics": {
    "target_overlap_area": 0.0,
    "face_safe_zone": [0.28, 0.24, 0.72, 0.70],
    "reading_order_valid": true,
    "all_bubbles_outside_face_zone": true
  },
  "messages": [
    {"role": "system", "content": "Bạn là Chuyên gia Cao cấp về Ngữ pháp Manga Nhật Bản..."},
    {"role": "user", "content": "Hãy thiết kế phân cảnh manga Dark Fantasy chủ đề 'Huyết Cơ và Kỵ Sĩ'..."},
    {"role": "assistant", "content": "<think>\n1. Phân tích Kịch bản & Chủ đề: Dark Fantasy 'Huyết Cơ và Kỵ Sĩ'...\n2. Ngữ pháp Bố cục Manga (Koma-wari): 1_panel_splash...\n3. Thiết lập Vùng An toàn Khuôn mặt: [0.28, 0.24]-[0.72, 0.70], Overlap Area = 0.0 px²...\n4. Sắp xếp Luồng Đọc Manga Nhật (RTL & Top-to-Bottom)...\n5. Tích hợp Dynamic SFX: 'DOKI DOKI'...\n6. Phân rã 4 thành phần Prompt ComfyUI theo StoryDiffusion...\n</think>\n\n### Thiết kế Phân cảnh Manga..."}
  ]
}
```

---

## 6. Hướng dẫn Tái tạo & Đánh giá

### Chạy sinh tập dữ liệu:
```bash
python scripts/generate_manga_japanese_grammar_10k.py --num-samples 10000
```

### Chạy kiểm thử tự động:
```bash
pytest tests/test_manga_japanese_grammar_10k.py -v
```
*(Kết quả: 5/5 tests PASSED 100%)*
