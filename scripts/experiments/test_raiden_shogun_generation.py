#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/test_raiden_shogun_generation.py
========================================
Shonen Action / Genshin Impact Combat Benchmark:
  1. raiden_baseline.png: Test base model recall (zero-shot prompt "raiden shogun, genshin impact").
  2. raiden_canonical_portrait.png: Test full canonical HoYoverse traits (braid, kanzashi, mole, kimono, mitsudomoe).
  3. raiden_combat_action.png: High-octane Shonen battle action in Plane of Euthymia with Musou Isshin lightning.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

COMFY_URL = "http://127.0.0.1:8188"
MODEL_NAME = "2.9V8.safetensors"
CLIP_NAME = "qwen_3_06b_base.safetensors"
VAE_NAME = "qwen_image_vae.safetensors"

OUTPUT_DIR = ROOT_DIR / "data" / "manga" / "raiden_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def check_comfy_server():
    """Verify ComfyUI server availability."""
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"[ComfyUI] Server online. RAM free: {data['system']['ram_free'] / (1024**3):.1f} GB")
            return True
    except Exception as e:
        print(f"[ComfyUI] Connection error: {e}")
        return False


def generate_comfy_image(
    prefix: str,
    prompt: str,
    negative_prompt: str,
    seed: int = 42,
    width: int = 768,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 4.5,
) -> Path:
    """Submits a generation workflow to ComfyUI and polls until image is saved."""
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
                "text": negative_prompt,
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
                "steps": steps,
                "cfg": cfg,
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
                "filename_prefix": f"Raiden_{prefix}",
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
        print(f"[{prefix}] Submitted to ComfyUI. Prompt ID: {prompt_id}")

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
                    local_out = OUTPUT_DIR / f"{prefix}.png"
                    urllib.request.urlretrieve(view_url, str(local_out))
                    dt = time.time() - t0
                    print(f"[{prefix}] Success! Finished in {dt:.1f}s -> {local_out}")
                    return local_out

        elapsed = time.time() - t0
        print(f"[{prefix}] Sampling in progress... ({elapsed:.0f}s)")
        if elapsed > 240:
            raise TimeoutError(f"Generation for {prefix} timed out after 240 seconds")


def run_raiden_benchmark():
    """Runs all 3 Raiden Shogun test cases."""
    print("=" * 70)
    print("⚡ GENSHIN IMPACT / SHONEN ACTION BENCHMARK: RAIDEN SHOGUN")
    print("=" * 70)

    if not check_comfy_server():
        print("[ERROR] ComfyUI server not running at 127.0.0.1:8188!")
        sys.exit(1)

    # Load character knowledge base if available
    kb_path = ROOT_DIR / "data" / "characters" / "raiden_shogun_genshin.json"
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
            print(f"[KnowledgeBase] Loaded {kb['full_name']} specs from {kb_path.name}")
    else:
        print("[KnowledgeBase] Note: raiden_shogun_genshin.json not found, using embedded matrix.")

    common_neg = (
        "(photorealistic:1.4), (3d render, cgi, airbrushed:1.4), (smooth plastic skin, oily sheen:1.4), "
        "digital gradient shading, western comic, blurry, deformed hands, extra limbs, extra weapons, "
        "blonde hair, short hair, twin tails, low quality, bad anatomy"
    )

    # -------------------------------------------------------------------------
    # Test 1: Baseline Recall (Zero-shot minimal prompt)
    # -------------------------------------------------------------------------
    print("\n--- [Test 1/3] Baseline Recall: raiden_baseline.png ---")
    prompt_baseline = (
        "raiden shogun, genshin impact, 1girl, solo, upper body, "
        "anime art style, authentic 2D anime illustration, hand-drawn manga art"
    )
    neg_baseline = common_neg
    out_baseline = generate_comfy_image(
        prefix="raiden_baseline",
        prompt=prompt_baseline,
        negative_prompt=neg_baseline,
        seed=101,
        width=768,
        height=1024,
    )

    # -------------------------------------------------------------------------
    # Test 2: Canonical Portrait (Pinned Danbooru tags & official anatomy)
    # -------------------------------------------------------------------------
    print("\n--- [Test 2/3] Canonical Portrait: raiden_canonical_portrait.png ---")
    prompt_portrait = (
        "masterpiece, best quality, authentic 2D anime illustration, hand-drawn manga art, "
        "crisp cel shading, clean solid black G-pen ink lines, matte textures, fine screentones, "
        "raiden shogun (genshin impact), 1girl, solo, portrait, dark violet hair with glowing lavender tips, "
        "long hair, single braid hanging down back, straight front bangs, deep purple eyes with electro iris crest, "
        "distinct beauty mark under right eye, golden fan-shaped hairpin, flower hair ornament with purple hanging tassel, "
        "lavender short kimono, gold cloud embroidery, mitsudomoe crest, black and gold left shoulder pauldron, "
        "form-fitting dark purple bodysuit, elegant divine archon aura, looking at viewer, calm stern expression, "
        "plain dark background, rule of thirds composition, off-center framing"
    )
    neg_portrait = (
        "blonde hair, blue eyes, short hair, twin tails, western knight, "
        + common_neg
    )
    out_portrait = generate_comfy_image(
        prefix="raiden_canonical_portrait",
        prompt=prompt_portrait,
        negative_prompt=neg_portrait,
        seed=202,
        width=768,
        height=1024,
    )

    # -------------------------------------------------------------------------
    # Test 3: Shonen Combat Action (Plane of Euthymia, Musou Isshin, speedlines)
    # -------------------------------------------------------------------------
    print("\n--- [Test 3/3] Shonen Combat Action: raiden_combat_action.png ---")
    prompt_combat = (
        "masterpiece, best quality, authentic 2D anime illustration, high-octane shonen action manga panel, "
        "crisp cel shading, solid dynamic ink lines, dramatic foreshortening, action lines, speed lines, "
        "raiden shogun (genshin impact), 1girl, solo, dynamic leaping battle stance, combat action, "
        "wielding glowing katana, musou isshin, sword slash, curved blade crackling with intense purple electro lightning arcs, "
        "violent lightning discharge, purple plasma sparks, flowing dark violet braided hair, intense fierce battle glare, "
        "plane of euthymia, inner consciousness dimension, stormy purple dimensional void, cracked floating dark stone arena, "
        "glowing purple electro ground fissures, massive crimson torii gate in background, ominous glowing purple sky, "
        "rule of thirds dynamic diagonal composition, manga panel masterpiece"
    )
    neg_combat = (
        "peaceful, standing still, smiling, blonde hair, western sword, "
        + common_neg
    )
    out_combat = generate_comfy_image(
        prefix="raiden_combat_action",
        prompt=prompt_combat,
        negative_prompt=neg_combat,
        seed=303,
        width=768,
        height=1024,
    )

    print("\n" + "=" * 70)
    print("✅ RAIDEN SHOGUN BENCHMARK COMPLETE!")
    print(f"1. Baseline:           {out_baseline}")
    print(f"2. Canonical Portrait: {out_portrait}")
    print(f"3. Combat Action:      {out_combat}")
    print("=" * 70)


if __name__ == "__main__":
    run_raiden_benchmark()
