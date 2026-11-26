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
OUTPUT_DIR = r"F:\AI-Office\data\manga\de_ai_panels"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_panel(prefix: str, prompt: str, neg: str, seed: int = 123456, width: int = 768, height: int = 1024):
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
                "text": prompt,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "5": {
            "inputs": {
                "text": neg,
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
                "filename_prefix": f"DeAI_{prefix}",
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
        print(f"[{prefix}] Submitted. Prompt ID: {prompt_id}")

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
                    local_out = os.path.join(OUTPUT_DIR, f"{prefix}.png")
                    urllib.request.urlretrieve(view_url, local_out)
                    dt = time.time() - t0
                    print(f"[{prefix}] Finished in {dt:.1f}s -> {local_out}")
                    return local_out
        elapsed = time.time() - t0
        print(f"[{prefix}] Sampling... ({elapsed:.0f}s)")
        if elapsed > 300:
            print(f"[{prefix}] Timeout!")
            return None

if __name__ == "__main__":
    # 1. Kaelen with Left side framing + negative space on top-right
    kaelen_prompt = (
        "authentic 2D anime illustration, hand-drawn manga art style, crisp cel shading, "
        "clean solid G-pen ink lines, matte textures, rule of thirds composition, "
        "character positioned on left side, right side has empty dark stone cathedral wall negative space, "
        "blood knight Kaelen, messy jet-black hair with fallen bangs, sharp amber eyes, "
        "faint battle scar on nose bridge, stern resolute grimace, "
        "matte charcoal black steel plate armor, dark leather straps, weathered greatsword, "
        "disciplined dark fantasy color palette, muted tones, no plastic skin, no 3d cgi, no glowing neon runes, no airbrush"
    )
    kaelen_neg = (
        "3d render, cgi, digital painting, airbrush, glossy skin, plastic specular highlights, "
        "neon glow, glowing armor, centered composition, bad anatomy, deformed face, blurry, photorealistic"
    )
    generate_panel("kaelen_cel_left", kaelen_prompt, kaelen_neg, seed=999888, width=768, height=1024)

    # 2. Carmilla with Right side framing + negative space on top-left
    carmilla_prompt = (
        "authentic 2D anime illustration, hand-drawn manga art style, crisp cel shading, "
        "clean solid G-pen ink lines, matte textures, rule of thirds composition, "
        "character positioned on right side looking left, left side has empty dark gothic arch negative space, "
        "vampire princess Carmilla, cascading silver hair with delicate curl strands, "
        "ruby crimson eyes with subtle anime shading, small vampire fangs, "
        "gothic dark velvet dress with subtle deep wine-red accents, delicate obsidian tiara, "
        "disciplined dark fantasy palette, matte porcelain skin, no plastic skin, no 3d cgi, no neon blue backlight, no airbrush"
    )
    carmilla_neg = (
        "3d render, cgi, digital painting, airbrush, glossy skin, plastic specular highlights, "
        "neon blue backlight, glowing aura, centered composition, bad anatomy, deformed face, blurry, photorealistic"
    )
    generate_panel("carmilla_cel_right", carmilla_prompt, carmilla_neg, seed=888777, width=768, height=1024)
