"""Generate remaining specific story panels for Moonlight Classroom Chapter 1 using ComfyUI."""

import json
import logging
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"
COMFY_OUTPUT_DIR = Path(r"F:\AI\ComfyUI\output")
STORY_ART_DIR = Path(r"F:\AI-Office\data\manga\series\moonlight_classroom\ch01\panels")
STORY_ART_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ch1_art_gen")

TARGET_SCENES = [
    {
        "id": "ch1_math_teacher_blackboard",
        "prompt": "monochrome manga, mature male teacher, around 35 years old, round glasses, dark hair, wearing beige cardigan, navy bow tie, black pencil skirt, standing by blackboard with chalk formulas, writing 'QUY DINH DONG PHUC HOC SINH - 1990', authentic Japanese manga panel, screentone shading, sharp ink lineart",
        "neg": "color, blurry, 3d, deformed anatomy, bad hands",
        "w": 768, "h": 1024, "seed": 701
    },
    {
        "id": "ch1_smartphone_news",
        "prompt": "monochrome manga, close-up student hands holding glowing smartphone in classroom, screen displaying archival newspaper article with bold Japanese headline text and 1989 school photo, psychological manga screentone, high contrast ink",
        "neg": "color, blurry, extra fingers, deformed hands",
        "w": 768, "h": 1024, "seed": 702
    },
    {
        "id": "ch1_glitch_photo_morph",
        "prompt": "monochrome manga, student inspecting opening ceremony group photo on phone screen, faces blurring and glitching, digital distortion effect, students uniforms transforming into skirts, intense shock manga panel",
        "neg": "color, washed out, blurry",
        "w": 768, "h": 1024, "seed": 703
    },
    {
        "id": "ch1_hallway_ending_silhouette",
        "prompt": "monochrome manga, dark empty school hallway at dusk, moonlight streaming through high windows, silhouette of mature man in pencil skirt and round glasses standing at corner, chilling knowing smile, psychological mystery climax, Shonen Jump style",
        "neg": "color, bright daytime, flat lighting",
        "w": 768, "h": 1024, "seed": 704
    }
]

def build_graph(prompt: str, neg: str, w: int, h: int, seed: int, prefix: str) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "anima-turbo-v1.1-Q4_K_M.gguf"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_06b_base.safetensors", "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["2", 0]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["6", 0], "seed": seed, "steps": 8, "cfg": 1.0,
            "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}}
    }

def run_gen():
    for item in TARGET_SCENES:
        prefix = f"ch1_{item['id']}"
        dest_file = STORY_ART_DIR / f"{item['id']}.png"
        if dest_file.exists():
            logger.info(f"Skipping already generated: {dest_file.name}")
            continue

        graph = build_graph(item["prompt"], item["neg"], item["w"], item["h"], item["seed"], prefix)
        req_body = json.dumps({"prompt": graph}).encode("utf-8")
        req = urllib.request.Request(f"{COMFY_URL}/prompt", data=req_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        p_id = data["prompt_id"]
        logger.info(f"Queued {item['id']} -> Prompt ID: {p_id}")

        start = time.time()
        while True:
            try:
                with urllib.request.urlopen(f"{COMFY_URL}/history/{p_id}", timeout=5) as r:
                    h = json.loads(r.read())
                    if p_id in h:
                        outputs = h[p_id].get("outputs", {})
                        for _, out in outputs.items():
                            if "images" in out:
                                for im_info in out["images"]:
                                    src = COMFY_OUTPUT_DIR / im_info["filename"]
                                    if src.exists():
                                        shutil.copy2(src, dest_file)
                                        logger.info(f"Generated and saved: {dest_file.name} in {time.time()-start:.2f}s")
                                        break
                        break
            except Exception:
                pass
            time.sleep(0.5)
            if time.time() - start > 180:
                logger.error(f"Timeout generating {item['id']}")
                break

if __name__ == "__main__":
    run_gen()
