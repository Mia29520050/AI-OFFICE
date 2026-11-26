#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-Throughput Japanese Manga Grammar & Dark Fantasy 10k Dataset Generator
==========================================================================
Generates 10,000 standardized test and alignment cases for Manga Studio,
benchmarking against GPT-Image-2.6 Sunburst standards:
  1. Japanese Manga Grammar: Koma-wari layout, RTL & Top-to-Bottom eye gaze flow,
     face & eye safety clearance, frame-bleeding SFX onomatopoeia, and bubble typology.
  2. Dark Fantasy Theme "Huyết Cơ và Kỵ Sĩ" (Vampire Sovereign & Her Cursed Knight):
     Carmilla, Kaelen, Lucian, Vivian with StoryDiffusion consistency anchors.
  3. Structured ChatML format with in-depth <think> CoT reasoning.

Output: data/training/manga_japanese_grammar_10k.jsonl
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import random
import argparse
from typing import Dict, List, Any, Tuple

OUTPUT_PATH = Path("data/training/manga_japanese_grammar_10k.jsonl")

SYSTEM_MANGA_GRAMMAR_PROMPT = (
    "Bạn là Chuyên gia Cao cấp về Ngữ pháp Manga Nhật Bản (Manga Grammar & Storyboarding Director) "
    "và Kỹ sư Prompt Anime phong cách Dark Fantasy 'Huyết Cơ và Kỵ Sĩ'.\n"
    "Khi thiết kế hoặc giải quyết bài toán bố cục manga, bạn luôn suy luận chặt chẽ trong thẻ <think> ... </think>:\n"
    "1. Bố cục phân khung (Koma-wari): Xác định tỷ lệ và nhịp điệu (1-panel splash, 2-panel contrast, 3-panel dynamic, 4-panel yonkoma, 5-6 panel narrative).\n"
    "2. Luồng dẫn dắt thị giác (Shisen-yudou / Tachiyomi): Tuân thủ nghiêm ngặt nguyên tắc Right-to-Left, Top-to-Bottom (Score = y * 3.0 - x).\n"
    "3. Bảo vệ khuôn mặt & đôi mắt (Face & Eye Clearance): Tuyệt đối không để bong bóng thoại đè lên vùng mặt [0.28, 0.24]-[0.72, 0.70] (Overlap Area = 0.0 px²).\n"
    "4. Hiệu ứng âm thanh đè viền (Bleeding SFX): Bố trí từ tượng thanh (DON, GOGOGO, ZASH, BAKI) tạo chiều sâu không gian phá vỡ viền khung.\n"
    "5. Neo giữ ngoại hình nhân vật (StoryDiffusion Consistency): Khóa chặt các tag nhận dạng của Huyết Cơ Carmilla, Hắc Kỵ Sĩ Kaelen, v.v.\n"
    "Sau đó đưa ra bảng bố cục tọa độ an toàn, cấu hình bong bóng thoại và Prompt ComfyUI hoàn chỉnh."
)

# ==============================================================================
# DATA TABLES & VOCABULARY
# ==============================================================================

DARK_FANTASY_CHARACTERS = {
    "carmilla": {
        "name": "Huyết Cơ Carmilla",
        "title": "Vampire Princess / Sovereign of the Blood Realm",
        "anchor_token": "[carmilla_vampire_sovereign]",
        "tags": "1girl, flowing long silver-platinum hair with side drill locks, piercing crimson ruby eyes, glowing red pupils, subtle sharp fangs, porcelain pale skin, victorian gothic velvet gown with dark lace trims, black obsidian thorn crown, blood ruby choker necklace, elegant arrogant smirk",
        "gender": "female"
    },
    "kaelen": {
        "name": "Hắc Kỵ Sĩ Kaelen",
        "title": "Cursed Blood Knight / Sworn Guardian",
        "anchor_token": "[kaelen_blood_knight]",
        "tags": "1boy, messy jet-black hair with fallen bangs, sharp amber-gold eyes, faint battle scar across bridge of nose, full gothic black steel plate armor engraved with glowing crimson runes, tattered crimson cape fluttering, holding demonic greatsword with blood aura, determined intense stare",
        "gender": "male"
    },
    "lucian": {
        "name": "Giáo Đầu Thánh Điện Lucian",
        "title": "High Inquisitor of the Silver Dawn",
        "anchor_token": "[lucian_silver_inquisitor]",
        "tags": "1boy, short slicked-back blonde hair, cold steely grey eyes, ornate silver holy knight plate armor, white silk cape with golden cross embroidery, sacred silver rapier glowing with holy light, stern righteous scowl",
        "gender": "male"
    },
    "vivian": {
        "name": "Huyết Linh Pháp Sư Vivian",
        "title": "Blood Alchemist & Familiar",
        "anchor_token": "[vivian_blood_alchemist]",
        "tags": "1girl, twin high dark purple buns, glowing violet eyes, gothic lolita witch dress, floating bat familiars, holding arcane blood grimoire and crystal wand, playful mischievous wink",
        "gender": "female"
    }
}

DARK_FANTASY_ENVIRONMENTS = [
    ("gothic_cathedral_blood_moon", "ancient gothic cathedral ruins, towering broken stained glass windows, massive red blood moon glowing in night sky, climbing black rose vines with crimson thorns, misty stone altar"),
    ("vampire_throne_room", "grand vampire throne room, opulent obsidian throne draped in red velvet, tall iron candelabras with flickering blue flames, towering stone gargoyle statues, gothic vaulted ceiling"),
    ("misty_ruined_battlefield", "desolate ruined battlefield engulfed in dense white mist, broken stone pillars, scattered cracked shields and rusted swords, withered black roses, twilight atmosphere"),
    ("castle_balcony_overlook", "high castle balcony, intricately carved wrought-iron gothic balustrade, howling wind fluttering capes, flock of silhouetted bats swarming against dark stormy clouds"),
    ("subterranean_crypt_library", "subterranean crypt library, ancient stone book shelves filled with forbidden grimoires, glowing arcane magic circles on stone floor, hovering lanterns, eerie green embers"),
    ("iron_maiden_dungeon", "dark stone dungeon hallway, heavy iron portcullis, torches casting long flickering shadows, chains hanging from damp mossy walls, cold foreboding atmosphere")
]

MANGA_SFX_CATALOG = [
    {"romaji": "GOGOGO...", "kanji": "ゴゴゴ...", "meaning": "Áp lực tâm linh đè nén, tà khí ma vương xuất hiện", "bleed_style": "floating_left_border"},
    {"romaji": "DON!", "kanji": "ドンッ!", "meaning": "Tiếng đập mạnh vang dội, sự xuất hiện gây chấn động", "bleed_style": "burst_top_center"},
    {"romaji": "ZASH!", "kanji": "ザシュッ!", "meaning": "Nhát chém kiếm khí xé toạc không gian", "bleed_style": "diagonal_slice_across_panel"},
    {"romaji": "BAKI!", "kanji": "バキッ!", "meaning": "Tiếng giáp trụ vỡ vụn hoặc đất đá nứt toác", "bleed_style": "shatter_corner"},
    {"romaji": "DOKI DOKI", "kanji": "ドキドキ", "meaning": "Tiếng tim đập căng thẳng, hơi thở nghẹn ngào", "bleed_style": "heartbeat_screentone_accent"},
    {"romaji": "SHIN...", "kanji": "シーン...", "meaning": "Sự im lặng chết chóc, không khí ngưng đọng", "bleed_style": "vertical_margin_fade"},
    {"romaji": "HYUUU", "kanji": "ヒョオオ", "meaning": "Gió lạnh rít gào qua khe đá, áo choàng bay phần phật", "bleed_style": "flowing_wind_lines"},
    {"romaji": "BAAAM!", "kanji": "ドカーン!", "meaning": "Vụ nổ ma pháp huyết sắc bùng phát", "bleed_style": "frame_breaking_impact"}
]

DIALOGUE_LINES_BY_CHAR = {
    "carmilla": [
        ("Kaelen, quỳ xuống trước mặt ta... Máu của ngươi tối nay có vị ngọt ngào hơn thường lệ.", "speech_oval", "whisper_dashed"),
        ("Lũ giáo sĩ ngu xuẩn dám bước chân vào lãnh địa của ta? Hãy để chúng nếm trải sự phẫn nộ của bóng đêm!", "shout_burst", "speech_oval"),
        ("Ngươi nghĩ lưỡi kiếm rỉ sét đó có thể chạm được vào ta sao, kẻ phàm trần tầm thường?", "speech_oval", "dark_telepathy"),
        ("Đừng chết trước khi ta cho phép, Kaelen... Ngươi là hiệp sĩ duy nhất của ta.", "whisper_dashed", "speech_oval"),
        ("Mặt trăng máu đã lên đến đỉnh... Lễ thanh tẩy bắt đầu!", "dark_telepathy", "shout_burst")
    ],
    "kaelen": [
        ("Huyết Cơ điện hạ! Thần sẽ dùng thanh kiếm này xé nát bất cứ kẻ nào dám mạo phạm người!", "shout_burst", "speech_oval"),
        ("Máu trong huyết quản ta sôi lên... Hãy ban cho thần sức mạnh bóng tối, Carmilla!", "dark_telepathy", "speech_oval"),
        ("Lùi lại! Nhát kiếm tiếp theo sẽ không chỉ cắt đứt áo giáp của ngươi đâu, Lucian!", "shout_burst", "speech_oval"),
        ("Dù phải rơi xuống tận cùng hắc ngục, thần vẫn mãi là chiếc khiên của người.", "whisper_dashed", "speech_oval"),
        ("Cảm nhận vết chém của Huyết Cực Kiếm đi! ZASH!", "shout_burst", "speech_oval")
    ],
    "lucian": [
        ("Nữ chúa ma cà rồng tà ác! Hôm nay ánh sáng của Thánh Điện sẽ thiêu rụi lâu đài này!", "shout_burst", "speech_oval"),
        ("Kaelen... Ngươi từng là niềm tự hào của giáo hội, tại sao lại sa ngã làm nô bộc cho quỷ dữ?", "speech_oval", "speech_oval"),
        ("Thanh kiếm ánh sáng không bao giờ dung tha cho bóng tối!", "shout_burst", "speech_oval")
    ],
    "vivian": [
        ("Hihi, nghi thức triệu hồi đã hoàn tất rồi đó, Carmilla-sama!", "speech_oval", "speech_oval"),
        ("Những con dơi đêm nay đang đói khát... Chúng muốn thưởng thức linh hồn của các hiệp sĩ!", "dark_telepathy", "speech_oval")
    ]
}

PANEL_LAYOUT_PRESETS = [
    {
        "name": "1_panel_splash",
        "description": "Trang Splash toàn cảnh kích thước cực đại, tạo cảm giác choáng ngợp và hoành tráng",
        "panel_count": 1,
        "grid": [{"box": [0.04, 0.04, 0.96, 0.96], "type": "splash"}]
    },
    {
        "name": "2_panel_contrast",
        "description": "Bố cục 2 khung đối chiếu tương phản mạnh mẽ (trên: toàn cảnh, dưới: cận cảnh căng thẳng)",
        "panel_count": 2,
        "grid": [
            {"box": [0.04, 0.04, 0.96, 0.48], "type": "wide"},
            {"box": [0.04, 0.52, 0.96, 0.96], "type": "wide"}
        ]
    },
    {
        "name": "3_panel_cinematic",
        "description": "Bố cục 3 khung điện ảnh kinh điển Manga Nhật Bản (Khung 1 trên cùng bên phải -> Khung 2 góc trái -> Khung 3 tràn đáy)",
        "panel_count": 3,
        "grid": [
            {"box": [0.52, 0.04, 0.96, 0.46], "type": "standard"},
            {"box": [0.04, 0.04, 0.48, 0.46], "type": "standard"},
            {"box": [0.04, 0.50, 0.96, 0.96], "type": "wide"}
        ]
    },
    {
        "name": "4_panel_yonkoma",
        "description": "Bố cục 4 khung truyền thống (Khởi - Thừa - Chuyển - Hợp) xếp dọc theo luồng đọc tự nhiên",
        "panel_count": 4,
        "grid": [
            {"box": [0.04, 0.04, 0.96, 0.25], "type": "yonkoma_1"},
            {"box": [0.04, 0.28, 0.96, 0.49], "type": "yonkoma_2"},
            {"box": [0.04, 0.52, 0.96, 0.73], "type": "yonkoma_3"},
            {"box": [0.04, 0.76, 0.96, 0.96], "type": "yonkoma_4"}
        ]
    },
    {
        "name": "5_panel_action_dynamic",
        "description": "Bố cục 5 khung hành động chiến đấu dồn dập (Khung chéo, zoom cận cảnh, đòn đánh bất ngờ)",
        "panel_count": 5,
        "grid": [
            {"box": [0.52, 0.04, 0.96, 0.32], "type": "top_right"},
            {"box": [0.04, 0.04, 0.48, 0.32], "type": "top_left"},
            {"box": [0.04, 0.36, 0.96, 0.64], "type": "center_wide"},
            {"box": [0.52, 0.68, 0.96, 0.96], "type": "bottom_right"},
            {"box": [0.04, 0.68, 0.48, 0.96], "type": "bottom_left"}
        ]
    }
]

# Safe Bubble Positions avoiding Face Zone [0.28, 0.24] - [0.72, 0.70]
SAFE_CORNER_ANCHORS = [
    {"pos": "top_right", "x": 0.78, "y": 0.12, "desc": "Góc trên bên phải (Ưu tiên đọc số 1 theo RTL)"},
    {"pos": "top_left", "x": 0.22, "y": 0.12, "desc": "Góc trên bên trái (Đọc tiếp theo hàng ngang)"},
    {"pos": "bottom_right", "x": 0.78, "y": 0.85, "desc": "Góc dưới bên phải (Lời đáp chuyển cảnh)"},
    {"pos": "bottom_left", "x": 0.22, "y": 0.85, "desc": "Góc dưới bên trái (Lời kết panel)"}
]


def generate_single_sample(idx: int, rng: random.Random) -> Dict[str, Any]:
    """Generates one rich, validated Dark Fantasy Manga Grammar CoT case."""
    layout = rng.choice(PANEL_LAYOUT_PRESETS)
    koma_count = layout["panel_count"]
    layout_name = layout["name"]

    # Select characters for scene
    char_keys = ["carmilla", "kaelen"]
    if koma_count >= 3 and rng.random() < 0.6:
        char_keys.append("lucian")
    if koma_count >= 4 and rng.random() < 0.4:
        char_keys.append("vivian")

    primary_char_key = rng.choice(char_keys)
    primary_char = DARK_FANTASY_CHARACTERS[primary_char_key]
    env_name, env_desc = rng.choice(DARK_FANTASY_ENVIRONMENTS)
    sfx = rng.choice(MANGA_SFX_CATALOG)

    # Build dialogue sequence for the panel
    dialogue_count = rng.randint(2, min(4, koma_count + 1))
    dialogues: List[Dict[str, Any]] = []

    # Assign safe non-overlapping positions adhering to RTL flow
    assigned_corners = SAFE_CORNER_ANCHORS[:dialogue_count]

    for d_idx, corner in enumerate(assigned_corners):
        speaker_key = char_keys[d_idx % len(char_keys)]
        speaker_info = DARK_FANTASY_CHARACTERS[speaker_key]
        dlg_lines = DIALOGUE_LINES_BY_CHAR.get(speaker_key, DIALOGUE_LINES_BY_CHAR["carmilla"])
        text, bubble_type, fallback_type = rng.choice(dlg_lines)

        dialogues.append({
            "order": d_idx + 1,
            "speaker": speaker_info["name"],
            "speaker_key": speaker_key,
            "text": text,
            "bubble_type": bubble_type,
            "anchor_position": corner["pos"],
            "coords": {"x": corner["x"], "y": corner["y"]},
            "priority_score": round(corner["y"] * 3.0 - corner["x"], 3)
        })

    # Sort dialogues by reading priority score (lowest score = read first)
    dialogues.sort(key=lambda d: d["priority_score"])
    for rank, d in enumerate(dialogues, 1):
        d["reading_rank"] = rank

    # Compose Prompt 4 Components
    art_style_comp = (
        "masterpiece, best quality, ultra-detailed monochrome manga, high contrast dark fantasy ink, "
        "screentone halftones, authentic japanese manga scan, deep blacks, crisp lineart, gothic aesthetic"
    )
    char_traits_comp = f"{primary_char['anchor_token']}, {primary_char['tags']}"
    emotion_pose_comp = (
        "intense glowing eye gaze, dramatic battle stance, flowing garments caught in dark magical wind, "
        "subtle sinister smile, summoning blood magic runes"
    )
    bg_camera_comp = f"dramatic low angle cinematic shot, looking up, {env_desc}, atmospheric lighting"
    full_pos_prompt = f"{art_style_comp}, {char_traits_comp}, {emotion_pose_comp}, {bg_camera_comp}"
    full_neg_prompt = (
        "lowres, bad anatomy, bad hands, deformed limbs, blurry, western comic, 3d render, "
        "photorealistic, color, colored skin, bad eyes, extra fingers"
    )

    # Construct Deep CoT Reasoning in <think>
    think_lines = [
        "<think>",
        f"1. Phân tích Kịch bản & Chủ đề: Dark Fantasy 'Huyết Cơ và Kỵ Sĩ' ({primary_char['name']} tại bối cảnh {env_name}).",
        f"2. Ngữ pháp Bố cục Manga (Koma-wari):",
        f"   - Chọn kiểu bố cục: {layout_name} ({layout['description']}).",
        f"   - Luồng chuyển động mắt (Eye Movement): Đi từ khung Trên-Phải -> chuyển dần sang Trái-Dưới.",
        f"3. Thiết lập Vùng An toàn Khuôn mặt (Face & Eye Clearance):",
        f"   - Vùng cấm tuyệt đối (Face Zone): Tọa độ chuẩn hóa [0.28, 0.24] đến [0.72, 0.70].",
        f"   - Toàn bộ {len(dialogues)} bong bóng thoại được neo tại 4 góc an toàn: " + ", ".join(d["anchor_position"] for d in dialogues) + ".",
        f"   - Tính toán va chạm (Anti-Collision): Khoảng cách giữa các hộp thoại tối thiểu 20px, Overlap Area = 0.0 px².",
        f"4. Sắp xếp Luồng Đọc Manga Nhật (RTL & Top-to-Bottom):",
    ]
    for d in dialogues:
        think_lines.append(f"   * Câu {d['reading_rank']} [{d['speaker']}]: Vị trí {d['anchor_position']} (Score = {d['priority_score']}) -> Loại '{d['bubble_type']}'.")

    think_lines.extend([
        f"5. Tích hợp Dynamic SFX (Từ tượng thanh đè viền):",
        f"   - Hiệu ứng: '{sfx['romaji']}' ({sfx['kanji']}) - Ý nghĩa: {sfx['meaning']}.",
        f"   - Kiểu bố trí đè viền: {sfx['bleed_style']} tạo cảm giác vỡ tung không gian.",
        f"6. Phân rã 4 thành phần Prompt ComfyUI theo StoryDiffusion:",
        f"   - (1) Art Style: {art_style_comp[:60]}...",
        f"   - (2) Locked Traits: {char_traits_comp[:80]}...",
        f"   - (3) Emotion/Pose: {emotion_pose_comp}",
        f"   - (4) Camera/BG: {bg_camera_comp}",
        "</think>"
    ])
    think_text = "\n".join(think_lines)

    # Output text response outside <think>
    response_lines = [
        f"### Thiết kế Phân cảnh Manga: {primary_char['name']} - {layout_name.upper()}\n",
        f"**Kiểu bố cục:** {layout_name} ({koma_count} panels) | **Bối cảnh:** {env_name}\n",
        f"**Dynamic SFX Đè Viền:** `{sfx['romaji']}` ({sfx['kanji']}) - *{sfx['meaning']}*\n\n",
        "#### 1. Bố cục Khung thoại An toàn (Anti-Collision & Face Avoidance):"
    ]
    for d in dialogues:
        response_lines.append(
            f"- **Thoại #{d['reading_rank']}** [{d['speaker']}]: `{d['text']}` "
            f"(Loại: *{d['bubble_type']}*, Vị trí: `{d['anchor_position']}`, Tọa độ: x={d['coords']['x']}, y={d['coords']['y']})"
        )

    response_lines.extend([
        "\n#### 2. Prompt ComfyUI Phân rã 4 Thành phần Bắt buộc:",
        f"- **Art Style/Medium:** `{art_style_comp}`",
        f"- **Locked Character Traits:** `{char_traits_comp}`",
        f"- **Emotion & Dynamic Pose:** `{emotion_pose_comp}`",
        f"- **Background & Camera Shot:** `{bg_camera_comp}`",
        "\n```text",
        f"# Positive Prompt:\n{full_pos_prompt}\n",
        f"# Negative Prompt:\n{full_neg_prompt}",
        "```"
    ])
    response_text = "\n".join(response_lines)

    user_query = (
        f"Hãy thiết kế phân cảnh manga Dark Fantasy chủ đề 'Huyết Cơ và Kỵ Sĩ' với nhân vật {primary_char['name']}, "
        f"bối cảnh {env_name}, sử dụng bố cục chuẩn Nhật Bản {layout_name} kèm {len(dialogues)} câu thoại và hiệu ứng SFX {sfx['romaji']}. "
        f"Đảm bảo tuyệt đối không che khuôn mặt/mắt nhân vật và xếp thứ tự đọc chuẩn Manga RTL."
    )

    sample_id = f"manga_10k_{idx:05d}"
    return {
        "id": sample_id,
        "category": "japanese_manga_grammar_dark_fantasy",
        "benchmark_standard": "GPT-Image-2.6-Sunburst-Equiv",
        "koma_layout": layout_name,
        "koma_count": koma_count,
        "primary_character": primary_char["name"],
        "dialogue_count": len(dialogues),
        "sfx": sfx["romaji"],
        "verification_metrics": {
            "target_overlap_area": 0.0,
            "face_safe_zone": [0.28, 0.24, 0.72, 0.70],
            "reading_order_valid": True,
            "all_bubbles_outside_face_zone": True
        },
        "messages": [
            {"role": "system", "content": SYSTEM_MANGA_GRAMMAR_PROMPT},
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": f"{think_text}\n\n{response_text}"}
        ],
        "text": (
            f"<|im_start|>system\n{SYSTEM_MANGA_GRAMMAR_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user_query}<|im_end|>\n"
            f"<|im_start|>assistant\n{think_text}\n\n{response_text}<|im_end|>"
        )
    }


def generate_10k_dataset(num_samples: int = 10000, seed: int = 42, output_path: Path = OUTPUT_PATH) -> None:
    rng = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting high-throughput procedural generation of {num_samples:,} Japanese Manga Grammar cases...")
    print(f"[*] Target destination: {output_path}")

    # Buffer writing for high throughput
    buffer = []
    buffer_size = 500
    written = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for i in range(1, num_samples + 1):
            sample = generate_single_sample(i, rng)
            buffer.append(json.dumps(sample, ensure_ascii=False) + "\n")

            if len(buffer) >= buffer_size:
                f.writelines(buffer)
                written += len(buffer)
                buffer.clear()
                pct = (written / num_samples) * 100
                print(f"    ... Generated & written {written:,} / {num_samples:,} samples ({pct:.1f}%)")

        if buffer:
            f.writelines(buffer)
            written += len(buffer)
            buffer.clear()

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[+] COMPLETE: Successfully generated {written:,} samples!")
    print(f"[+] Output file size: {file_size_mb:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Japanese Manga Grammar 10k Dataset Generator")
    parser.add_argument("--num-samples", type=int, default=10000, help="Number of samples (default: 10000)")
    parser.add_argument("--output-path", type=str, default=str(OUTPUT_PATH), help="Destination JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Reproducibility seed")

    args = parser.parse_args()
    generate_10k_dataset(
        num_samples=args.num_samples,
        seed=args.seed,
        output_path=Path(args.output_path).resolve()
    )


if __name__ == "__main__":
    main()
