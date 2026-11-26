from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.train_qlora import (
    check_gpu_environment,
    generate_ollama_modelfile,
    generate_gguf_conversion_guide,
    inspect_and_format_dataset,
    parse_arguments,
    print_vram_budget_report,
)


def test_gpu_environment_detection():
    info = check_gpu_environment()
    assert isinstance(info, dict)
    assert "cuda_available" in info
    assert "total_vram_mb" in info
    assert "free_vram_mb" in info


def test_dataset_chatml_formatting(tmp_path: Path):
    data_file = tmp_path / "train.jsonl"
    sample_data = [
        {
            "messages": [
                {"role": "system", "content": "You are a math solver."},
                {"role": "user", "content": "Bài toán bèo 4 cụm?"},
                {
                    "role": "assistant",
                    "content": "<think>\nBước 1: 1 cụm mất 30 ngày.\nBước 2: 4 cụm = 2^2, tiết kiệm 2 ngày -> 28 ngày.\n</think>\nKết quả là 28 ngày.",
                },
            ]
        },
        {
            "conversations": [
                {"from": "human", "value": "Đếm ký tự strawberry"},
                {"from": "gpt", "value": "<think>\ns-t-r-a-w-b-e-r-r-y: 3 r</think>\nCó 3 chữ r."},
            ]
        },
        {
            "instruction": "Câu đố logic hiệp sĩ",
            "input": "A nói B là kẻ nói dối",
            "output": "<think>\nGiả thiết A thật...\n</think>\nA là hiệp sĩ.",
        },
    ]

    with open(data_file, "w", encoding="utf-8") as f:
        for item in sample_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    formatted, stats = inspect_and_format_dataset(data_file, max_length=2048)
    assert stats["valid_samples"] == 3
    assert stats["has_cot_think_tags"] == 3
    assert stats["skipped_samples"] == 0
    assert len(formatted) == 3
    assert "<|im_start|>user\nBài toán bèo 4 cụm?<|im_end|>" in formatted[0]["text"]
    assert "<think>" in formatted[0]["text"]
    assert "</think>" in formatted[0]["text"]


def test_ollama_modelfile_generation(tmp_path: Path):
    output_modelfile = tmp_path / "Modelfile.test"
    result_path = generate_ollama_modelfile(
        adapter_or_gguf_path=str(tmp_path / "adapter"),
        base_model_name="Qwen/Qwen2.5-3B-Instruct",
        output_modelfile_path=output_modelfile,
    )
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    assert "ADAPTER" in content
    assert "num_ctx 4096" in content
    assert "<|im_end|>" in content
    assert "<think>" in content


def test_gguf_guide_generation(tmp_path: Path):
    adapter_dir = tmp_path / "adapter"
    merged_dir = tmp_path / "merged"
    adapter_dir.mkdir(parents=True)
    guide_path = generate_gguf_conversion_guide(adapter_dir, merged_dir)
    assert guide_path.exists()
    assert (adapter_dir / "convert_and_import_ollama.bat").exists()
    guide_text = guide_path.read_text(encoding="utf-8")
    assert "llama.cpp" in guide_text
    assert "ollama create" in guide_text


def test_default_6gb_hyperparameters():
    with patch("sys.argv", ["train_qlora.py"]):
        args = parse_arguments()
        assert args.batch_size == 1
        assert args.grad_accum == 8
        assert args.context_length == 2048
        assert args.lora_r == 16
        assert args.lora_alpha == 32
        assert "q_proj" in args.target_modules
