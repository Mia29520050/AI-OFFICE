#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Manga Storyboard CoT Dataset
====================================
Generates rich Chain-of-Thought (CoT) training samples for Manga Storyboards,
enforcing 4-component prompt decomposition and StoryDiffusion character consistency.
Exports to: data/training/manga_storyboard_cot.jsonl
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import random
import argparse
from typing import List, Dict, Any

from app.manga_anime_generator import (
    MangaAnimePromptGenerator,
    generate_cot_storyboard_sample,
    ANIME_EMOTIONS,
    ANIME_POSES,
    CAMERA_SHOTS,
    BACKGROUND_ENVIRONMENTS,
    VISUAL_EFFECTS,
    MODEL_PRESETS,
    DEFAULT_CHARACTERS
)

OUTPUT_PATH = Path("data/training/manga_storyboard_cot.jsonl")

SCENARIO_TEMPLATES = [
    {
        "theme": "Giờ ra chơi tại lớp học: Minh bất ngờ phát hiện một bức thư bí ẩn kẹp trong vở, Mai tò mò gặng hỏi trong khi Huy quan sát từ xa.",
        "characters": ["Minh", "Mai", "Huy"],
        "panels": [
            {"characters": ["Minh"], "emotion": "anime_sweatdrop", "pose": "holding_book", "camera": "close_up", "background": "japanese_classroom", "vfx": "focus_burst"},
            {"characters": ["Mai"], "emotion": "tsundere_pout", "pose": "leaning_forward", "camera": "medium_shot", "background": "japanese_classroom", "vfx": "none"},
            {"characters": ["Huy"], "emotion": "mysterious_cool", "pose": "arms_crossed", "camera": "over_the_shoulder", "background": "japanese_classroom", "vfx": "screentone_hatch"}
        ]
    },
    {
        "theme": "Đêm muộn tại phòng lab AI Office: Minh và Koharu cùng xử lý lỗi thuật toán quan trọng trước hạn nộp dự án.",
        "characters": ["Minh", "Koharu"],
        "panels": [
            {"characters": ["Koharu"], "emotion": "chibi_panic", "pose": "running_panic", "camera": "wide_establishing", "background": "tech_lab_office", "vfx": "speed_lines"},
            {"characters": ["Minh"], "emotion": "determined_focus", "pose": "leaning_forward", "camera": "close_up", "background": "tech_lab_office", "vfx": "focus_burst"},
            {"characters": ["Koharu", "Minh"], "emotion": "sparkling_eyes", "pose": "pointing_finger", "camera": "medium_shot", "background": "tech_lab_office", "vfx": "doki_doki_aura"}
        ]
    },
    {
        "theme": "Cuộc chạm trán căng thẳng trên sân thượng trường học lúc hoàng hôn: Huy chất vấn Minh về dự án bí mật.",
        "characters": ["Huy", "Minh"],
        "panels": [
            {"characters": ["Huy"], "emotion": "dramatic_shadow", "pose": "pointing_finger", "camera": "low_angle_dramatic", "background": "school_rooftop", "vfx": "menacing_gogogo"},
            {"characters": ["Minh"], "emotion": "determined_focus", "pose": "turning_around", "camera": "dutch_angle", "background": "school_rooftop", "vfx": "screentone_hatch"},
            {"characters": ["Huy"], "emotion": "smug_grin", "pose": "arms_crossed", "camera": "close_up", "background": "school_rooftop", "vfx": "none"}
        ]
    },
    {
        "theme": "Cơn mưa rào bất chợt trên phố Tokyo: Mai và Minh trú mưa chung dưới một chiếc ô trước tiệm bánh.",
        "characters": ["Mai", "Minh"],
        "panels": [
            {"characters": ["Mai"], "emotion": "gentle_smile", "pose": "holding_book", "camera": "medium_shot", "background": "tokyo_street", "vfx": "doki_doki_aura"},
            {"characters": ["Minh"], "emotion": "anime_sweatdrop", "pose": "whispering_secret", "camera": "close_up", "background": "tokyo_street", "vfx": "screentone_hatch"},
            {"characters": ["Mai"], "emotion": "tsundere_pout", "pose": "turning_around", "camera": "medium_shot", "background": "tokyo_street", "vfx": "none"}
        ]
    },
    {
        "theme": "Hội trường công bố kết quả kỳ thi học sinh giỏi: Huy đứng đầu bảng điểm trong khi Minh quyết tâm bám đuổi.",
        "characters": ["Huy", "Minh", "Mai"],
        "panels": [
            {"characters": ["Huy"], "emotion": "smug_grin", "pose": "casual_seated", "camera": "medium_shot", "background": "sunset_corridor", "vfx": "screentone_hatch"},
            {"characters": ["Minh"], "emotion": "determined_focus", "pose": "slamming_desk", "camera": "low_angle_dramatic", "background": "japanese_classroom", "vfx": "focus_burst"},
            {"characters": ["Mai"], "emotion": "gentle_smile", "pose": "reaching_out", "camera": "close_up", "background": "japanese_classroom", "vfx": "doki_doki_aura"}
        ]
    },
    {
        "theme": "Khoảnh khắc yên tĩnh trong thư viện cổ: Mai đọc sách bên cửa sổ, những tia nắng chiều chiếu qua mái tóc.",
        "characters": ["Mai"],
        "panels": [
            {"characters": ["Mai"], "emotion": "gentle_smile", "pose": "casual_seated", "camera": "wide_establishing", "background": "quiet_library", "vfx": "screentone_hatch"},
            {"characters": ["Mai"], "emotion": "sparkling_eyes", "pose": "holding_book", "camera": "close_up", "background": "quiet_library", "vfx": "doki_doki_aura"}
        ]
    },
    {
        "theme": "Sự cố mất điện bất ngờ trong phòng thí nghiệm: Màn hình máy tính phụt tắt, chỉ còn ánh sáng khẩn cấp.",
        "characters": ["Minh", "Koharu"],
        "panels": [
            {"characters": ["Koharu"], "emotion": "jaw_drop_shock", "pose": "running_panic", "camera": "extreme_close_up", "background": "tech_lab_office", "vfx": "focus_burst"},
            {"characters": ["Minh"], "emotion": "dramatic_shadow", "pose": "slamming_desk", "camera": "dutch_angle", "background": "tech_lab_office", "vfx": "menacing_gogogo"},
            {"characters": ["Minh"], "emotion": "determined_focus", "pose": "reaching_out", "camera": "medium_shot", "background": "tech_lab_office", "vfx": "speed_lines"}
        ]
    }
]


def generate_dataset(num_samples: int = 350, seed: int = 42) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    samples: List[Dict[str, Any]] = []

    emotions_list = list(ANIME_EMOTIONS.keys())
    poses_list = list(ANIME_POSES.keys())
    cameras_list = list(CAMERA_SHOTS.keys())
    bg_list = list(BACKGROUND_ENVIRONMENTS.keys())
    vfx_list = list(VISUAL_EFFECTS.keys())
    models_list = list(MODEL_PRESETS.keys())
    char_names_all = ["Minh", "Mai", "Huy", "Koharu"]

    for i in range(1, num_samples + 1):
        if i <= len(SCENARIO_TEMPLATES):
            base_template = SCENARIO_TEMPLATES[i - 1]
            theme = base_template["theme"]
            chars = base_template["characters"]
            panels_data = base_template["panels"]
            model_preset = rng.choice(models_list)
        else:
            # Procedural combination
            char_count = rng.choice([1, 2, 3])
            chars = rng.sample(char_names_all, char_count)
            panel_count = rng.choice([2, 3, 4])
            model_preset = rng.choice(models_list)

            theme_env = rng.choice(bg_list).replace("_", " ")
            theme = f"Phân cảnh kịch tính tại {theme_env} với sự tham gia của {', '.join(chars)}."

            panels_data = []
            for p_idx in range(panel_count):
                panel_chars = rng.sample(chars, rng.randint(1, len(chars)))
                panels_data.append({
                    "characters": panel_chars,
                    "emotion": rng.choice(emotions_list),
                    "pose": rng.choice(poses_list),
                    "camera": rng.choice(cameras_list),
                    "background": rng.choice(bg_list),
                    "vfx": rng.choice(vfx_list)
                })

        sample = generate_cot_storyboard_sample(
            scene_id=i,
            story_theme=theme,
            characters=chars,
            panels_data=panels_data,
            model_preset=model_preset
        )
        samples.append(sample)

    return samples


def main():
    parser = argparse.ArgumentParser(description="Generate Manga Storyboard CoT Dataset")
    parser.add_argument("--num-samples", type=int, default=350, help="Number of samples to generate")
    parser.add_argument("--output-path", type=str, default=str(OUTPUT_PATH), help="Output JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    out_file = Path(args.output_path).resolve()
    print(f"[*] Generating {args.num_samples} Manga Storyboard CoT samples (seed={args.seed})...")
    samples = generate_dataset(num_samples=args.num_samples, seed=args.seed)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    file_size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"[+] Successfully exported {len(samples)} samples to: {out_file} ({file_size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
