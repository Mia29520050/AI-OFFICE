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

def generate_p1():
    prompt = (
        "authentic 2D anime illustration, hand-drawn dark fantasy manga art, clean architectural 1-point perspective, "
        "crisp solid G-pen ink linework, fine screentone shading, cross-hatching shadows on stone pillars, "
        "ruined gothic cathedral sanctuary at night, ancient stone arches, tall broken stained glass window with pale crimson blood moon light, "
        "crumbled stone steps, quiet eerie atmosphere, disciplined muted dark fantasy palette, charcoal stone textures, "
        "no neon red glow, no fractal architecture, no 3d cgi render, no airbrush, high quality 2D manga establishing shot, no people"
    )
    neg = (
        "3d render, cgi, digital painting, airbrush, neon red glow, hyper-saturated red, fractal, "
        "melting arches, glossy, plastic, photorealistic, blurry, people, person, character, silhouette"
    )

    width = 1024
    height = 640
    seed = 333444555

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
                "filename_prefix": "DeAI_Cathedral_P1",
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
        print(f"[P1] Submitted. Prompt ID: {prompt_id}")

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
                    local_out = os.path.join(OUTPUT_DIR, "p1_cathedral_de_ai.png")
                    urllib.request.urlretrieve(view_url, local_out)
                    dt = time.time() - t0
                    print(f"[P1] Finished in {dt:.1f}s -> {local_out}")
                    return local_out
        elapsed = time.time() - t0
        print(f"[P1] Generating clean 2D manga cathedral... ({elapsed:.0f}s)")
        if elapsed > 300:
            print("[P1] Timeout!")
            return None

if __name__ == "__main__":
    generate_p1()
