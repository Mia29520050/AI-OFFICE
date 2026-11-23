"""Download script for Anima Turbo v1.1 Q4_K_M weights and dependencies.

Downloads:
1. qwen_image_vae.safetensors (~242 MB) -> F:\\AI\\ComfyUI\\models\\vae\\
2. qwen_3_06b_base.safetensors (~1.14 GB) -> F:\\AI\\ComfyUI\\models\\text_encoders\\
3. anima-turbo-v1.1-Q4_K_M.gguf (~1.32 GB) -> F:\\AI\\ComfyUI\\models\\diffusion_models\\

Includes resume support, temporary file staging, and progress logging.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

TARGETS = [
    {
        "name": "qwen_image_vae.safetensors",
        "url": "https://huggingface.co/vanes430/Anima-Turbo-V1.1-GGUF/resolve/main/split_files/vae/qwen_image_vae.safetensors",
        "dest": Path(r"F:\AI\ComfyUI\models\vae\qwen_image_vae.safetensors"),
        "expected_bytes": 253815318, # ~242 MB
    },
    {
        "name": "qwen_3_06b_base.safetensors",
        "url": "https://huggingface.co/vanes430/Anima-Turbo-V1.1-GGUF/resolve/main/split_files/text_encoders/qwen_3_06b_base.safetensors",
        "dest": Path(r"F:\AI\ComfyUI\models\text_encoders\qwen_3_06b_base.safetensors"),
        "expected_bytes": 1192138984, # ~1.14 GB
    },
    {
        "name": "anima-turbo-v1.1-Q4_K_M.gguf",
        "url": "https://huggingface.co/vanes430/Anima-Turbo-V1.1-GGUF/resolve/main/anima-turbo-v1.1-Q4_K_M.gguf",
        "dest": Path(r"F:\AI\ComfyUI\models\diffusion_models\anima-turbo-v1.1-Q4_K_M.gguf"),
        "expected_bytes": 1384408416, # ~1.32 GB
    },
]


def download_file(item: dict[str, Any]) -> bool:
    dest: Path = item["dest"]
    url: str = item["url"]
    name: str = item["name"]

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".download")

    if dest.exists() and dest.stat().st_size > 1024 * 1024:
        print(f"[ALREADY_EXISTS] {name} is present ({dest.stat().st_size / (1024*1024):.1f} MB). Skipping.")
        return True

    existing_bytes = tmp_path.stat().st_size if tmp_path.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    if existing_bytes > 0:
        req.add_header("Range", f"bytes={existing_bytes}-")
        mode = "ab"
        print(f"[RESUME] Resuming {name} from {existing_bytes / (1024*1024):.1f} MB...")
    else:
        mode = "wb"
        print(f"[START] Downloading {name}...")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_length = resp.headers.get("Content-Length")
            total_bytes = int(content_length) + existing_bytes if content_length else 0

            downloaded = existing_bytes
            chunk_size = 1024 * 512 # 512 KB
            last_report = time.time()
            start_time = time.time()
            bytes_since_report = 0

            with open(tmp_path, mode) as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    bytes_since_report += len(chunk)

                    now = time.time()
                    if now - last_report >= 5.0:
                        speed_mb = (bytes_since_report / (1024 * 1024)) / (now - last_report)
                        pct = (downloaded / total_bytes * 100) if total_bytes else 0
                        print(f"[{name}] {downloaded / (1024*1024):.1f} / {total_bytes / (1024*1024):.1f} MB ({pct:.1f}%) - Speed: {speed_mb:.2f} MB/s", flush=True)
                        last_report = now
                        bytes_since_report = 0

        # Rename tmp to final
        if tmp_path.exists():
            if dest.exists():
                dest.unlink()
            tmp_path.rename(dest)
        print(f"[COMPLETE] {name} saved successfully ({dest.stat().st_size / (1024*1024):.1f} MB).", flush=True)
        return True
    except Exception as exc:
        print(f"[ERROR] Failed downloading {name}: {exc}", flush=True)
        return False


def main():
    print("=== Anima Turbo v1.1 Model Downloader ===")
    success_count = 0
    for target in TARGETS:
        ok = download_file(target)
        if ok:
            success_count += 1
        else:
            print(f"Aborting sequence due to failure in {target['name']}.")
            break

    print(f"Finished {success_count}/{len(TARGETS)} downloads.")
    if success_count == len(TARGETS):
        print("ALL_MODELS_READY")


if __name__ == "__main__":
    main()
