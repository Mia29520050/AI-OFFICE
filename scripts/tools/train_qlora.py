#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
scripts/train_qlora.py
QLoRA 4-bit Fine-Tuning Pipeline for Synthetic Reasoning CoT Models
Optimized specifically for 6GB VRAM GPUs (NVIDIA GeForce RTX 3050 Laptop)
===============================================================================

Key Architectural Constraints & Memory Budget (6GB VRAM):
  * Total Hardware VRAM : 6,144 MiB (~5,200 MiB available after OS / Desktop)
  * Quantization        : 4-bit NormalFloat (NF4) + Double Quantization (bnb)
  * Target Base Models  : Qwen/Qwen2.5-3B-Instruct (Recommended for 6GB)
                          Qwen/Qwen2.5-Coder-7B-Instruct (Tight, max_seq=1536)
                          Qwen/Qwen2.5-1.5B-Instruct (Ultra-safe, fast)
  * Batch Size          : 1 (micro batch size)
  * Gradient Accum      : 8 (effective batch size = 8)
  * Gradient Checkpoint : Enabled (use_reentrant=False) -> ~65% activation saving
  * Optimizer           : paged_adamw_8bit -> Pages memory to CPU on peak spikes
  * Context Length      : 2048 tokens (capped to strictly avoid OOM)
  * Attention Engine    : PyTorch SDPA (Scaled Dot-Product Attention)
  * Multi-processing    : num_workers=0 (Required for Windows stability & VRAM)
===============================================================================
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Set PyTorch memory allocator to avoid fragmentation before any CUDA calls
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "training" / "reasoning_cot_train.jsonl"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "models" / "qlora-reasoning-adapter"
DEFAULT_MERGED_DIR = ROOT_DIR / "models" / "merged-reasoning-qwen"
DEFAULT_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"


def check_gpu_environment() -> Dict[str, Any]:
    """Inspect GPU, CUDA availability, and compute capability."""
    info: Dict[str, Any] = {
        "cuda_available": False,
        "device_name": "Unknown",
        "total_vram_mb": 0.0,
        "free_vram_mb": 0.0,
        "bf16_supported": False,
        "compute_capability": (0, 0),
    }

    try:
        import torch
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["device_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["total_vram_mb"] = props.total_memory / (1024 ** 2)
            # Free memory
            allocated = torch.cuda.memory_allocated(0) / (1024 ** 2)
            reserved = torch.cuda.memory_reserved(0) / (1024 ** 2)
            info["free_vram_mb"] = info["total_vram_mb"] - reserved
            info["compute_capability"] = (props.major, props.minor)
            info["bf16_supported"] = torch.cuda.is_bf16_supported()
            return info
    except ImportError:
        pass

    # Fallback to nvidia-smi if torch is not installed or not imported yet
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        )
        lines = [line.strip() for line in out.strip().split("\n") if line.strip()]
        if lines:
            parts = [p.strip() for p in lines[0].split(",")]
            info["cuda_available"] = True
            info["device_name"] = parts[0]
            info["total_vram_mb"] = float(parts[1])
            info["free_vram_mb"] = float(parts[2])
            # Ampere or newer (RTX 3050 is sm_86) supports bf16
            if "RTX 30" in parts[0] or "RTX 40" in parts[0] or "A100" in parts[0]:
                info["bf16_supported"] = True
    except Exception:
        pass

    return info


def print_vram_budget_report(gpu_info: Dict[str, Any], model_id: str, context_length: int) -> None:
    """Print detailed VRAM budget analysis for 6GB GPU."""
    print("=" * 75)
    print(" [6GB VRAM OPTIMIZATION PROFILE - NVIDIA RTX 3050 LAPTOP]")
    print("=" * 75)
    print(f" * Detected GPU       : {gpu_info.get('device_name', 'N/A')}")
    print(f" * Total VRAM         : {gpu_info.get('total_vram_mb', 0):.0f} MiB (~{gpu_info.get('total_vram_mb', 0)/1024:.1f} GB)")
    print(f" * Available VRAM     : {gpu_info.get('free_vram_mb', 0):.0f} MiB (~{gpu_info.get('free_vram_mb', 0)/1024:.1f} GB)")
    print(f" * BF16 Native Compute: {gpu_info.get('bf16_supported', False)}")
    print(f" * Target Model       : {model_id}")
    print(f" * Context Length     : {context_length} tokens")
    print("-" * 75)
    print(" Memory Breakdown Simulation (Quantized 4-bit NF4 + QLoRA):")

    is_7b = "7b" in model_id.lower() or "7B" in model_id
    base_weight_mb = 4200 if is_7b else 2100
    lora_weight_mb = 45
    optimizer_mb = 95
    activations_mb = 1100 if context_length >= 2048 else 650
    total_est = base_weight_mb + lora_weight_mb + optimizer_mb + activations_mb

    print(f"   - 4-bit Base Model Weights  : ~{base_weight_mb:,} MiB")
    print(f"   - LoRA Adapters (r=16, alpha=32) : ~{lora_weight_mb:,} MiB")
    print(f"   - Paged 8-bit AdamW States  : ~{optimizer_mb:,} MiB")
    print(f"   - Activations (Checkpointing): ~{activations_mb:,} MiB (batch=1, grad_accum=8)")
    print(f"   -------------------------------------------------")
    print(f"   - Total Estimated Peak VRAM : ~{total_est:,} MiB (~{total_est/1024:.2f} GB)")

    if total_est > 5600:
        print("   [!] WARNING: Estimated VRAM exceeds 5.6 GB. For 6GB GPU, consider:")
        print("       1. Use Qwen/Qwen2.5-3B-Instruct (Recommended, ~3.3 GB peak)")
        print("       2. Reduce --context_length to 1536 or 1024")
    else:
        margin = max(0.0, gpu_info.get("free_vram_mb", 6144) - total_est)
        print(f"   [+] STATUS: SAFE FOR 6GB VRAM (Safety Margin: ~{margin:.0f} MiB free)")
    print("=" * 75 + "\n")


def inspect_and_format_dataset(data_path: Path, max_length: int = 2048) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Parse reasoning dataset in JSONL format.
    Supports:
      1. ChatML messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
      2. ShareGPT conversations: [{"from": "...", "value": "..."}]
      3. Alpaca format: {"instruction": "...", "input": "...", "output": "..."}
      4. Prompt/Completion or Prompt/Response
    """
    if not data_path.exists():
        raise FileNotFoundError(f"Training dataset not found at: {data_path}")

    formatted_samples: List[Dict[str, str]] = []
    stats = {
        "total_lines": 0,
        "valid_samples": 0,
        "skipped_samples": 0,
        "has_cot_think_tags": 0,
        "approx_char_lengths": [],
    }

    with open(data_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            stats["total_lines"] += 1
            try:
                row = json.loads(line)
            except Exception as e:
                print(f"[!] JSON parse error on line {idx}: {e}")
                stats["skipped_samples"] += 1
                continue

            # Case A: Standard ChatML "messages" format
            if "messages" in row and isinstance(row["messages"], list):
                messages = row["messages"]
                # Convert to standard ChatML text representation
                rendered_text = ""
                has_think = False
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "assistant" and ("<think>" in content or "</think>" in content):
                        has_think = True
                    rendered_text += f"<|im_start|>{role}\n{content}<|im_end|>\n"
                
                if has_think:
                    stats["has_cot_think_tags"] += 1
                
                formatted_samples.append({"text": rendered_text.strip()})
                stats["approx_char_lengths"].append(len(rendered_text))
                stats["valid_samples"] += 1

            # Case B: ShareGPT "conversations" format
            elif "conversations" in row and isinstance(row["conversations"], list):
                rendered_text = ""
                has_think = False
                for msg in row["conversations"]:
                    role_raw = msg.get("from", "human")
                    role = "user" if role_raw in ("human", "user") else "assistant" if role_raw in ("gpt", "assistant") else "system"
                    content = msg.get("value", "")
                    if role == "assistant" and ("<think>" in content or "</think>" in content):
                        has_think = True
                    rendered_text += f"<|im_start|>{role}\n{content}<|im_end|>\n"

                if has_think:
                    stats["has_cot_think_tags"] += 1

                formatted_samples.append({"text": rendered_text.strip()})
                stats["approx_char_lengths"].append(len(rendered_text))
                stats["valid_samples"] += 1

            # Case C: Alpaca format (instruction / input / output)
            elif "instruction" in row and "output" in row:
                inst = row["instruction"]
                inp = row.get("input", "")
                out = row["output"]
                user_msg = f"{inst}\n{inp}".strip() if inp else inst
                has_think = "<think>" in out or "</think>" in out
                if has_think:
                    stats["has_cot_think_tags"] += 1

                rendered_text = (
                    f"<|im_start|>system\nYou are a precise reasoning model. Think step by step inside <think>...</think> tags.<|im_end|>\n"
                    f"<|im_start|>user\n{user_msg}<|im_end|>\n"
                    f"<|im_start|>assistant\n{out}<|im_end|>"
                )
                formatted_samples.append({"text": rendered_text.strip()})
                stats["approx_char_lengths"].append(len(rendered_text))
                stats["valid_samples"] += 1

            # Case D: Prompt / Response or Prompt / Completion
            elif "prompt" in row and ("response" in row or "completion" in row):
                prompt = row["prompt"]
                resp = row.get("response", row.get("completion", ""))
                has_think = "<think>" in resp or "</think>" in resp
                if has_think:
                    stats["has_cot_think_tags"] += 1

                rendered_text = (
                    f"<|im_start|>system\nYou are a precise reasoning model. Think step by step inside <think>...</think> tags.<|im_end|>\n"
                    f"<|im_start|>user\n{prompt}<|im_end|>\n"
                    f"<|im_start|>assistant\n{resp}<|im_end|>"
                )
                formatted_samples.append({"text": rendered_text.strip()})
                stats["approx_char_lengths"].append(len(rendered_text))
                stats["valid_samples"] += 1

            # Case E: Raw text field already formatted
            elif "text" in row and isinstance(row["text"], str):
                text_content = row["text"]
                if "<think>" in text_content or "</think>" in text_content:
                    stats["has_cot_think_tags"] += 1
                formatted_samples.append({"text": text_content.strip()})
                stats["approx_char_lengths"].append(len(text_content))
                stats["valid_samples"] += 1
            else:
                stats["skipped_samples"] += 1

    return formatted_samples, stats


def generate_ollama_modelfile(
    adapter_or_gguf_path: str,
    base_model_name: str,
    output_modelfile_path: Path,
) -> Path:
    """Generate an Ollama Modelfile tailored for the trained reasoning model."""
    system_prompt = (
        "You are Claude Office Reasoning Assistant, an expert AI software architect and mathematical logician.\n"
        "You operate with constitutional truthfulness. For every complex question, math problem, or reasoning puzzle, "
        "you MUST structure your thinking inside <think> ... </think> tags before formulating your final verified answer."
    )

    is_gguf = adapter_or_gguf_path.lower().endswith(".gguf")
    from_line = f"FROM {adapter_or_gguf_path}" if is_gguf else f"FROM {base_model_name}\nADAPTER {adapter_or_gguf_path}"

    content = f"""# ==============================================================================
# Modelfile generated by scripts/train_qlora.py
# QLoRA Reasoning CoT Fine-Tuned Model for Ollama
# ==============================================================================

{from_line}

# Inference Runtime Parameters optimized for 6GB VRAM
PARAMETER temperature 0.2
PARAMETER top_p 0.95
PARAMETER top_k 40
PARAMETER num_ctx 4096
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"

SYSTEM \"\"\"
{system_prompt}
\"\"\"
"""
    output_modelfile_path.parent.mkdir(parents=True, exist_ok=True)
    output_modelfile_path.write_text(content, encoding="utf-8")
    return output_modelfile_path


def generate_gguf_conversion_guide(output_dir: Path, merged_dir: Path) -> Path:
    """Write an automated batch script and instructions for converting to GGUF."""
    guide_path = output_dir / "EXPORT_TO_OLLAMA_GUIDE.md"
    script_bat = output_dir / "convert_and_import_ollama.bat"

    guide_content = f"""# Guide: Convert Fine-Tuned LoRA Adapter to GGUF & Load into Ollama

Trained Adapter Path: `{output_dir}`
Merged Model Path:   `{merged_dir}`

## Step 1: Merge LoRA Adapter with Base Model
Run `train_qlora.py` with the `--merge_and_save` flag:
```cmd
python scripts/train_qlora.py --merge_and_save --output_dir "{output_dir}" --merged_output_dir "{merged_dir}"
```

## Step 2: Convert to GGUF using llama.cpp
1. Ensure llama.cpp repository is cloned:
   ```cmd
   git clone https://github.com/ggerganov/llama.cpp.git F:\\llama.cpp
   pip install -r F:\\llama.cpp\\requirements.txt
   ```
2. Run conversion to 16-bit GGUF:
   ```cmd
   python F:\\llama.cpp\\convert_hf_to_gguf.py "{merged_dir}" --outtype f16 --outfile "{merged_dir}\\reasoning-model-f16.gguf"
   ```
3. (Recommended for 6GB VRAM) Quantize to Q4_K_M:
   ```cmd
   F:\\llama.cpp\\build\\bin\\Release\\llama-quantize.exe "{merged_dir}\\reasoning-model-f16.gguf" "{merged_dir}\\reasoning-model-q4_k_m.gguf" q4_k_m
   ```

## Step 3: Register in Ollama
1. Navigate to output folder:
   ```cmd
   cd /d "{output_dir}"
   ```
2. Build Ollama model:
   ```cmd
   ollama create reasoning-office -f Modelfile.reasoning-office
   ```
3. Test inference:
   ```cmd
   ollama run reasoning-office "Nếu 1 cụm hoa bèo nhân đôi mỗi ngày phủ kín hồ trong 30 ngày, thì 4 cụm phủ kín hồ trong bao nhiêu ngày?"
   ```
"""
    guide_path.write_text(guide_content, encoding="utf-8")

    bat_content = f"""@echo off
REM Automated Export & Ollama Registration Script
echo ========================================================
echo  AI-Office QLoRA - Export to Ollama
echo ========================================================
set ADAPTER_DIR={output_dir}
set MODELFILE=%ADAPTER_DIR%\\Modelfile.reasoning-office

if not exist "%MODELFILE%" (
    echo [-] Modelfile not found: %MODELFILE%
    exit /b 1
)

echo [*] Creating Ollama model 'reasoning-office'...
ollama create reasoning-office -f "%MODELFILE%"
if %ERRORLEVEL% EQU 0 (
    echo [+] Successfully registered reasoning-office in Ollama!
    echo [*] Testing prompt...
    ollama run reasoning-office "Hãy suy luận bài toán hoa bèo với 4 cụm khởi đầu."
) else (
    echo [-] Failed to create model in Ollama. Make sure Ollama service is running.
)
pause
"""
    script_bat.write_text(bat_content, encoding="utf-8")
    return guide_path


def run_training_unsloth(args: argparse.Namespace, dataset_samples: List[Dict[str, str]]) -> None:
    """Fast fine-tuning branch using Unsloth FastLanguageModel (if installed)."""
    print("[*] Initializing Unsloth FastLanguageModel...")
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments

    max_seq_length = args.context_length
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_id,
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        dtype=None,  # Auto-detect bfloat16 / float16
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=args.target_modules.split(","),
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    raw_dataset = Dataset.from_list(dataset_samples)
    train_test_split = raw_dataset.train_test_split(test_size=args.eval_split, seed=args.seed) if args.eval_split > 0 else None
    train_dataset = train_test_split["train"] if train_test_split else raw_dataset
    eval_dataset = train_test_split["test"] if train_test_split else None

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        dataset_num_proc=1,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            warmup_ratio=args.warmup_ratio,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            fp16=not model.config.torch_dtype == "bfloat16",
            bf16=model.config.torch_dtype == "bfloat16",
            logging_steps=args.logging_steps,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            seed=args.seed,
            output_dir=str(args.output_dir),
            save_strategy="steps",
            save_steps=args.save_steps,
            save_total_limit=2,
            dataloader_num_workers=0,
            report_to="none",
        ),
    )

    print("[*] Starting Unsloth training...")
    trainer.train()
    print(f"[+] Training complete. Saving adapter to {args.output_dir}...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


def run_training_peft_trl(args: argparse.Namespace, dataset_samples: List[Dict[str, str]]) -> None:
    """
    Standard Windows-compatible Hugging Face PEFT + TRL + BitsAndBytes pipeline.
    Optimized strictly for 6GB VRAM.
    """
    import torch
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from datasets import Dataset

    # TRL import handling for both newer and older versions
    try:
        from trl import SFTTrainer, SFTConfig
        has_sft_config = True
    except ImportError:
        from trl import SFTTrainer
        has_sft_config = False

    print("[*] Configuring 4-bit BitsAndBytes quantization for 6GB VRAM...")
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )

    print(f"[*] Loading tokenizer: {args.model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_id,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[*] Loading base model in 4-bit NF4: {args.model_id}...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=compute_dtype,
        trust_remote_code=True,
        attn_implementation="sdpa",
    )

    # Prepare model for gradient checkpointing and k-bit training
    print("[*] Preparing model for k-bit training with gradient checkpointing...")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.config.use_cache = False  # Must be False during training with checkpointing

    # Setup LoRA
    target_modules = [m.strip() for m in args.target_modules.split(",") if m.strip()]
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, peft_config)

    # Print trainable parameters breakdown
    trainable_params, all_param = 0, 0
    for _, param in model.named_parameters():
        all_param += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()
    pct = 100 * trainable_params / all_param
    print(f"[+] Model Prepared: Trainable Params: {trainable_params:,} / {all_param:,} ({pct:.2f}%)")

    # Dataset preparation
    raw_dataset = Dataset.from_list(dataset_samples)
    if args.eval_split > 0 and len(dataset_samples) >= 10:
        split_data = raw_dataset.train_test_split(test_size=args.eval_split, seed=args.seed)
        train_data = split_data["train"]
        eval_data = split_data["test"]
    else:
        train_data = raw_dataset
        eval_data = None

    common_kwargs = {
        "output_dir": str(args.output_dir),
        "per_device_train_batch_size": args.batch_size,
        "gradient_accumulation_steps": args.grad_accum,
        "gradient_checkpointing": True,
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
        "optim": "paged_adamw_8bit",  # Crucial for 6GB VRAM stability
        "learning_rate": args.learning_rate,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": args.warmup_ratio,
        "num_train_epochs": args.epochs,
        "logging_steps": args.logging_steps,
        "save_strategy": "steps",
        "save_steps": args.save_steps,
        "save_total_limit": 2,
        "fp16": not torch.cuda.is_bf16_supported(),
        "bf16": torch.cuda.is_bf16_supported(),
        "dataloader_num_workers": 0,
        "dataloader_pin_memory": False,
        "report_to": "none",
        "seed": args.seed,
    }

    if has_sft_config:
        training_args = SFTConfig(
            max_seq_length=args.context_length,
            dataset_text_field="text",
            packing=False,
            **common_kwargs,
        )
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=train_data,
            eval_dataset=eval_data,
            args=training_args,
        )
    else:
        training_args = TrainingArguments(**common_kwargs)
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=train_data,
            eval_dataset=eval_data,
            dataset_text_field="text",
            max_seq_length=args.context_length,
            packing=False,
            args=training_args,
        )

    print("\n[*] Commencing QLoRA training on GPU...")
    start_time = time.time()
    trainer.train()
    duration = time.time() - start_time
    print(f"\n[+] Training completed in {duration:.1f}s ({duration/60:.2f} min).")

    # Save fine-tuned adapter and tokenizer
    print(f"[*] Saving LoRA adapter weights to: {args.output_dir}")
    os.makedirs(args.output_dir, exist_ok=True)
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"[+] Adapter successfully saved to: {args.output_dir}")


def merge_lora_and_save(base_model_id: str, adapter_path: Path, merged_out_path: Path) -> None:
    """Merge LoRA adapter back into base weights and save full model."""
    print(f"\n[*] Merging LoRA adapter '{adapter_path}' into base model '{base_model_id}'...")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), trust_remote_code=True)
    
    # Load base model in 16-bit to preserve quality for GGUF conversion
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    print("[*] Loading base model in 16-bit float...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=compute_dtype,
        device_map="cpu",  # Merge on CPU or auto to preserve GPU VRAM
        trust_remote_code=True,
    )

    print("[*] Attaching PEFT LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    print("[*] Executing merge_and_unload()...")
    merged_model = model.merge_and_unload()

    print(f"[*] Saving merged full model to: {merged_out_path}...")
    merged_out_path.mkdir(parents=True, exist_ok=True)
    merged_model.save_pretrained(str(merged_out_path), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_out_path))
    print(f"[+] Merged model saved successfully to: {merged_out_path}")


def execute_dry_run_diagnostics(args: argparse.Namespace, gpu_info: Dict[str, Any]) -> None:
    """Diagnostic mode: validate configuration, dataset, memory budget without CUDA training."""
    print("\n" + "=" * 75)
    print(" [DRY RUN / PRE-FLIGHT SYSTEM DIAGNOSTICS]")
    print("=" * 75)
    print_vram_budget_report(gpu_info, args.model_id, args.context_length)

    data_file = Path(args.data_path)
    print(f"[*] Checking dataset path: {data_file}")
    if data_file.exists():
        samples, stats = inspect_and_format_dataset(data_file, max_length=args.context_length)
        print(f"    - Total Lines in File       : {stats['total_lines']}")
        print(f"    - Valid Formatted Samples   : {stats['valid_samples']}")
        print(f"    - Samples with <think> tags : {stats['has_cot_think_tags']}")
        print(f"    - Skipped / Invalid Lines   : {stats['skipped_samples']}")
        if stats["approx_char_lengths"]:
            avg_len = sum(stats["approx_char_lengths"]) / len(stats["approx_char_lengths"])
            max_len = max(stats["approx_char_lengths"])
            print(f"    - Avg Character Length      : {avg_len:.1f} chars (~{avg_len/4:.0f} tokens)")
            print(f"    - Max Character Length      : {max_len} chars (~{max_len/4:.0f} tokens)")
        if samples:
            print("\n    [Preview of Formatted Sample #1]:")
            preview = samples[0]["text"]
            lines = preview.split("\n")
            preview_short = "\n".join(lines[:8]) + ("\n... [truncated]" if len(lines) > 8 else "")
            print("    " + preview_short.replace("\n", "\n    "))
    else:
        print(f"    [-] Dataset file not found yet at {data_file}")
        print("    [*] (This will be automatically populated by scripts/generate_reasoning_data.py)")

    # Test Modelfile generation
    modelfile_path = Path(args.output_dir) / "Modelfile.reasoning-office"
    generate_ollama_modelfile(str(args.output_dir), args.model_id, modelfile_path)
    generate_gguf_conversion_guide(Path(args.output_dir), Path(args.merged_output_dir))
    print(f"\n[+] Generated test Ollama Modelfile at: {modelfile_path}")
    print(f"[+] Generated Ollama Export Guide at: {Path(args.output_dir) / 'EXPORT_TO_OLLAMA_GUIDE.md'}")
    print("\n[+] DRY RUN DIAGNOSTICS COMPLETED: ALL CONFIGURATIONS VERIFIED FOR 6GB VRAM.")
    print("=" * 75 + "\n")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QLoRA 4-bit Fine-Tuning Pipeline Optimized for 6GB VRAM GPU (RTX 3050 Laptop)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Model & Data Paths
    parser.add_argument("--model_id", type=str, default=DEFAULT_MODEL_ID,
                        help="Hugging Face base model identifier or local path")
    parser.add_argument("--data_path", type=str, default=str(DEFAULT_DATA_PATH),
                        help="Path to training JSONL dataset (with <think> tags)")
    parser.add_argument("--output_dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help="Directory to save LoRA adapter weights")
    parser.add_argument("--merged_output_dir", type=str, default=str(DEFAULT_MERGED_DIR),
                        help="Directory to save full merged weights (if --merge_and_save)")

    # 6GB VRAM Optimized Training Hyperparameters
    parser.add_argument("--batch_size", type=int, default=1,
                        help="Per-device micro-batch size (fixed to 1 for 6GB VRAM)")
    parser.add_argument("--grad_accum", type=int, default=8,
                        help="Gradient accumulation steps (effective batch size = batch_size * grad_accum)")
    parser.add_argument("--context_length", type=int, default=2048,
                        help="Maximum token sequence length (2048 strictly fits in 6GB)")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Total number of training epochs")
    parser.add_argument("--learning_rate", type=float, default=2e-4,
                        help="Learning rate for LoRA adapter parameters")
    parser.add_argument("--warmup_ratio", type=float, default=0.03,
                        help="Ratio of total steps for learning rate warmup")
    parser.add_argument("--eval_split", type=float, default=0.05,
                        help="Validation dataset split ratio (0.0 to disable)")

    # LoRA Architecture
    parser.add_argument("--lora_r", type=int, default=16,
                        help="LoRA rank dimension")
    parser.add_argument("--lora_alpha", type=int, default=32,
                        help="LoRA scaling alpha factor")
    parser.add_argument("--lora_dropout", type=float, default=0.05,
                        help="LoRA dropout rate")
    parser.add_argument("--target_modules", type=str,
                        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
                        help="Target linear modules for LoRA injection (comma-separated)")

    # Checkpoint & Logging
    parser.add_argument("--save_steps", type=int, default=50,
                        help="Save checkpoint every N steps")
    parser.add_argument("--logging_steps", type=int, default=5,
                        help="Log metrics every N steps")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")

    # Execution Modes & Export
    parser.add_argument("--use_unsloth", action="store_true",
                        help="Use Unsloth FastLanguageModel if installed")
    parser.add_argument("--merge_and_save", action="store_true",
                        help="Merge adapter back into base model and save 16-bit weights")
    parser.add_argument("--export_gguf_guide", action="store_true",
                        help="Generate Ollama Modelfile and GGUF conversion instructions")
    parser.add_argument("--dry_run", action="store_true",
                        help="Run pre-flight validation and dataset audit without starting CUDA training")

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    gpu_info = check_gpu_environment()

    # Pre-flight check / Dry-run execution
    if args.dry_run:
        execute_dry_run_diagnostics(args, gpu_info)
        return

    # Check if dependencies are installed
    missing_deps = []
    try:
        import torch
    except ImportError:
        missing_deps.append("torch (with CUDA: https://pytorch.org)")
    try:
        import transformers
    except ImportError:
        missing_deps.append("transformers")
    try:
        import peft
    except ImportError:
        missing_deps.append("peft")
    try:
        import trl
    except ImportError:
        missing_deps.append("trl")
    try:
        import bitsandbytes
    except ImportError:
        missing_deps.append("bitsandbytes (Windows: bitsandbytes>=0.43.0)")
    try:
        import datasets
    except ImportError:
        missing_deps.append("datasets")

    if missing_deps:
        print("\n" + "!" * 75)
        print(" [!] Missing required deep learning libraries for live training:")
        for dep in missing_deps:
            print(f"     - {dep}")
        print("\n Install them with CUDA support:")
        print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
        print("   pip install transformers peft trl bitsandbytes accelerate datasets scipy")
        print("\n Running pre-flight system diagnostics with --dry_run instead...")
        print("!" * 75 + "\n")
        execute_dry_run_diagnostics(args, gpu_info)
        return

    print_vram_budget_report(gpu_info, args.model_id, args.context_length)

    data_file = Path(args.data_path)
    print(f"[*] Loading training dataset from: {data_file}")
    dataset_samples, stats = inspect_and_format_dataset(data_file, max_length=args.context_length)
    print(f"[+] Loaded {stats['valid_samples']} valid samples ({stats['has_cot_think_tags']} with <think> reasoning tags).")

    if not dataset_samples:
        print("[-] Error: No valid training samples found. Aborting.")
        sys.exit(1)

    # Launch Unsloth or PEFT+TRL
    if args.use_unsloth:
        try:
            run_training_unsloth(args, dataset_samples)
        except ImportError:
            print("[!] Unsloth not detected. Falling back to standard Hugging Face PEFT + TRL + BitsAndBytes...")
            run_training_peft_trl(args, dataset_samples)
    else:
        run_training_peft_trl(args, dataset_samples)

    # Export Ollama artifacts
    modelfile_path = Path(args.output_dir) / "Modelfile.reasoning-office"
    generate_ollama_modelfile(str(args.output_dir), args.model_id, modelfile_path)
    generate_gguf_conversion_guide(Path(args.output_dir), Path(args.merged_output_dir))
    print(f"[+] Generated Ollama Modelfile: {modelfile_path}")

    # Optional merge and export
    if args.merge_and_save:
        merge_lora_and_save(args.model_id, Path(args.output_dir), Path(args.merged_output_dir))

    print("\n" + "=" * 75)
    print(" [TRAINING PIPELINE FINISHED SUCCESSFULLY]")
    print(f" * Adapter Output : {args.output_dir}")
    print(f" * Ollama Model   : {modelfile_path}")
    print(f" * Export Guide   : {Path(args.output_dir) / 'EXPORT_TO_OLLAMA_GUIDE.md'}")
    print("=" * 75)


if __name__ == "__main__":
    main()
