#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
scripts/export_to_ollama.py
Automated Exporter & Ollama Modelfile Generator for QLoRA Reasoning Models
===============================================================================
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ADAPTER = ROOT_DIR / "models" / "qlora-reasoning-adapter"
DEFAULT_MERGED = ROOT_DIR / "models" / "merged-reasoning-qwen"
DEFAULT_BASE = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_MODEL_NAME = "reasoning-office"


def create_modelfile(adapter_or_gguf: str, base_model: str, modelfile_dest: Path) -> None:
    is_gguf = adapter_or_gguf.lower().endswith(".gguf")
    from_directive = f"FROM {adapter_or_gguf}" if is_gguf else f"FROM {base_model}\nADAPTER {adapter_or_gguf}"

    content = f"""# ==============================================================================
# Modelfile for AI-Office Reasoning CoT Engine
# Fine-tuned via QLoRA 4-bit on 6GB VRAM (NVIDIA RTX 3050 Laptop)
# ==============================================================================

{from_directive}

PARAMETER temperature 0.2
PARAMETER top_p 0.95
PARAMETER top_k 40
PARAMETER num_ctx 4096
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"

SYSTEM \"\"\"
You are Claude Office Reasoning Assistant, the lead AI architect for the AI-Office project.
You solve difficult reasoning, mathematical logic, and edge-case algorithmic challenges.
Rule: Always think step by step inside <think> ... </think> tags before formulating your final answer.
Never rush into intuitive shortcuts or linear approximations for exponential systems.
\"\"\"
"""
    modelfile_dest.parent.mkdir(parents=True, exist_ok=True)
    modelfile_dest.write_text(content, encoding="utf-8")
    print(f"[+] Created Modelfile at: {modelfile_dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export LoRA Adapter / GGUF to Ollama")
    parser.add_argument("--adapter_dir", type=str, default=str(DEFAULT_ADAPTER))
    parser.add_argument("--base_model", type=str, default=DEFAULT_BASE)
    parser.add_argument("--merged_dir", type=str, default=str(DEFAULT_MERGED))
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL_NAME)
    parser.add_argument("--gguf_path", type=str, default=None)
    parser.add_argument("--create_in_ollama", action="store_true", help="Run 'ollama create' automatically")
    args = parser.parse_args()

    adapter_path = Path(args.adapter_dir)
    modelfile_path = adapter_path / "Modelfile"

    target_source = args.gguf_path if args.gguf_path else str(adapter_path)
    create_modelfile(target_source, args.base_model, modelfile_path)

    if args.create_in_ollama:
        print(f"[*] Registering '{args.model_name}' in Ollama...")
        cmd = ["ollama", "create", args.model_name, "-f", str(modelfile_path)]
        try:
            res = subprocess.run(cmd, check=True)
            print(f"[+] Successfully registered '{args.model_name}' in Ollama!")
        except Exception as e:
            print(f"[-] Error calling Ollama: {e}")
            print(f"    Run manually: ollama create {args.model_name} -f \"{modelfile_path}\"")
    else:
        print(f"\n[+] Ready! To register in Ollama, execute:")
        print(f'    ollama create {args.model_name} -f "{modelfile_path}"')
        print(f'    ollama run {args.model_name} "Bài toán hoa bèo 4 cụm..."\n')


if __name__ == "__main__":
    main()
