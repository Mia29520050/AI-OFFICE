"""Run real Anima Turbo v1.1 GGUF test on ComfyUI and record hardware telemetry."""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
import psutil

COMFY_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = Path(r"F:\AI\ComfyUI\output")
BENCHMARK_REAL_DIR = Path(r"F:\AI-Office\data\manga\benchmarks\real_inference")
BENCHMARK_REAL_DIR.mkdir(parents=True, exist_ok=True)

def build_anima_turbo_graph(prompt: str, neg_prompt: str, width: int = 768, height: int = 1024, seed: int = 42, prefix: str = "anima_turbo") -> dict:
    return {
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "anima-turbo-v1.1-Q4_K_M.gguf"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_06b_base.safetensors",
                "type": "qwen_image"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "qwen_image_vae.safetensors"
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["2", 0]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": neg_prompt,
                "clip": ["2", 0]
            }
        },
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "seed": seed,
                "steps": 8,
                "cfg": 1.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": prefix,
                "images": ["8", 0]
            }
        }
    }


def get_vram_telemetry():
    vram_used = 0.0
    try:
        import subprocess
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"], text=True)
        used, total = out.strip().split(",")
        return float(used.strip()), float(total.strip())
    except Exception:
        return 0.0, 0.0


def submit_and_wait(prompt_graph: dict) -> dict:
    req_body = json.dumps({"prompt": prompt_graph}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=req_body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        res_data = json.loads(resp.read())
    prompt_id = res_data["prompt_id"]
    print(f"Submitted to ComfyUI. Prompt ID: {prompt_id}")

    start_time = time.time()
    peak_vram = 0.0
    peak_ram = 0.0
    initial_vram, total_vram = get_vram_telemetry()

    while True:
        v_used, _ = get_vram_telemetry()
        if v_used > peak_vram:
            peak_vram = v_used
        r_used = psutil.virtual_memory().used / (1024*1024)
        if r_used > peak_ram:
            peak_ram = r_used

        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as r:
                h = json.loads(r.read())
                if prompt_id in h:
                    status = h[prompt_id].get("status", {})
                    outputs = h[prompt_id].get("outputs", {})
                    duration = time.time() - start_time
                    print(f"Execution completed in {duration:.2f}s!")
                    print(f"Telemetry: Initial VRAM: {initial_vram:.1f} MB, Peak VRAM: {peak_vram:.1f} MB (Total: {total_vram:.1f} MB), Peak RAM: {peak_ram:.1f} MB")
                    
                    # Find generated image
                    images = []
                    for node_id, node_out in outputs.items():
                        if "images" in node_out:
                            for img_info in node_out["images"]:
                                img_fn = img_info["filename"]
                                img_path = OUTPUT_DIR / img_fn
                                images.append(str(img_path))
                    return {
                        "prompt_id": prompt_id,
                        "status": "COMPLETED",
                        "duration_s": round(duration, 2),
                        "initial_vram_mb": initial_vram,
                        "peak_vram_mb": peak_vram,
                        "total_vram_mb": total_vram,
                        "peak_ram_mb": peak_ram,
                        "images": images,
                        "history": status
                    }
        except Exception as e:
            pass

        time.sleep(0.5)
        if time.time() - start_time > 180:
            return {"prompt_id": prompt_id, "status": "TIMEOUT", "error": "Execution timed out after 180s"}


if __name__ == "__main__":
    print("=== Submitting Test Case 1 to Real ComfyUI ===")
    prompt = "1boy, high school student Minh, short neat black hair, dark eyes, white collared shirt, navy tie, navy blue blazer, close-up portrait, morning sunlight streaming across face, soft focus classroom background, masterpiece, best quality, sharp focus"
    neg_prompt = "low quality, bad anatomy, deformed eyes, extra ears, blurry, text, speech bubble"
    graph = build_anima_turbo_graph(prompt, neg_prompt, width=768, height=1024, seed=42, prefix="real_tc01_portrait")
    result = submit_and_wait(graph)
    print("RESULT:", json.dumps(result, indent=2))
