import json
import os
import sys
import time
import urllib.request
import urllib.parse
from PIL import Image

COMFY_URL = "http://127.0.0.1:8188"
MODEL_NAME = "2.9V8.safetensors"
CLIP_NAME = "qwen_3_06b_base.safetensors"
VAE_NAME = "qwen_image_vae.safetensors"
OUTPUT_DIR = r"F:\AI-Office\data\manga\blood_princess_panels"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_panel_1():
    prompt_text = (
        "anime, masterpiece, best quality, ultra detailed, sharp focus, intricate architectural details, "
        "cinematic dramatic lighting, strong chiaroscuro, dark fantasy gothic cathedral ruins, "
        "massive glowing blood moon in crimson night sky, towering vampire castle spires, "
        "crumbling gothic stone arches, glowing red rose stained glass windows, "
        "ancient stone steps covered in swirling blood mist, gargoyles, bats flying in the distance, "
        "highly atmospheric, dark fantasy background, manga establishing shot, no people"
    )
    neg_text = (
        "low quality, worst quality, deformed, blurry, 3d cgi render, plastic, photorealistic, "
        "people, person, woman, girl, man, character, silhouette, human figure, text, watermark"
    )

    width = 1024
    height = 640
    seed = 888999111

    workflow = {
        "1": {
            "inputs": {
                "unet_name": MODEL_NAME,
                "weight_dtype": "fp8_e4m3fn"
            },
            "class_type": "UNETLoader"
        },
        "2": {
            "inputs": {
                "clip_name": CLIP_NAME,
                "type": "stable_diffusion",
                "device": "default"
            },
            "class_type": "CLIPLoader"
        },
        "3": {
            "inputs": {
                "vae_name": VAE_NAME
            },
            "class_type": "VAELoader"
        },
        "4": {
            "inputs": {
                "text": prompt_text,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "5": {
            "inputs": {
                "text": neg_text,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "6": {
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "7": {
            "inputs": {
                "seed": seed,
                "steps": 25,
                "cfg": 4.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0]
            },
            "class_type": "KSampler"
        },
        "8": {
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "filename_prefix": "DeltaMix_Cathedral_P1",
                "images": ["8", 0]
            },
            "class_type": "SaveImage"
        }
    }

    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        prompt_id = res["prompt_id"]
        print(f"[COMFYUI] Prompt submitted. ID: {prompt_id}")

    t0 = time.time()
    while True:
        time.sleep(2)
        h_req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}")
        with urllib.request.urlopen(h_req) as resp:
            history = json.loads(resp.read().decode())
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                if "9" in outputs and "images" in outputs["9"]:
                    img_info = outputs["9"]["images"][0]
                    params = urllib.parse.urlencode({
                        "filename": img_info["filename"],
                        "subfolder": img_info["subfolder"],
                        "type": img_info["type"]
                    })
                    view_url = f"{COMFY_URL}/view?{params}"
                    local_out = os.path.join(OUTPUT_DIR, "p1_blood_moon_cathedral_deltamix.png")
                    urllib.request.urlretrieve(view_url, local_out)
                    dt = time.time() - t0
                    print(f"[COMFYUI] Finished P1 generation in {dt:.1f}s! Saved to {local_out}")
                    return local_out
        elapsed = time.time() - t0
        print(f"[COMFYUI] Generating Cathedral Establishing Shot with DeltaMix... ({elapsed:.0f}s elapsed)")
        if elapsed > 300:
            print("[COMFYUI] Timeout exceeded!")
            return None

if __name__ == "__main__":
    generate_panel_1()
