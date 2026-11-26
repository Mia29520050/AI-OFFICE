"""Test Anima Ref Adapter with live ComfyUI instance."""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"
COMFY_OUTPUT_DIR = Path(r"F:\AI\ComfyUI\output")

def test_adapter():
    prompt = "1boy, reading a math textbook in a library, looking thoughtful, sunlight through bookshelves, masterpiece"
    neg_prompt = "low quality, bad anatomy, deformed eyes, blurry, text"

    graph = {
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
        "10": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "minh_reference.png"
            }
        },
        "11": {
            "class_type": "AnimaRefAdapter",
            "inputs": {
                "model": ["1", 0],
                "vae": ["3", 0],
                "image": ["10", 0],
                "lora_name": "anima_ref_adapter_v2_r64.safetensors",
                "ref_guidance": 1.0,
                "correction": "apg",
                "strength": 1.0
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
                "width": 768,
                "height": 1024,
                "batch_size": 1
            }
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["11", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "seed": 100,
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
                "filename_prefix": "adapter_test_minh",
                "images": ["8", 0]
            }
        }
    }

    req_body = json.dumps({"prompt": graph}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=req_body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read())
        prompt_id = res_data["prompt_id"]
        print(f"Submitted successfully! Prompt ID: {prompt_id}")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code}: {err}")
        return

    start_time = time.time()
    while True:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as r:
                h = json.loads(r.read())
                if prompt_id in h:
                    status = h[prompt_id].get("status", {})
                    outputs = h[prompt_id].get("outputs", {})
                    duration = time.time() - start_time
                    print(f"Completed in {duration:.2f}s! Status: {status}")
                    return
        except Exception:
            pass

        time.sleep(1.0)
        if time.time() - start_time > 180:
            print("Timed out after 180s")
            return

if __name__ == "__main__":
    test_adapter()
