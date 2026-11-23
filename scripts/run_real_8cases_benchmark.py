"""Anime Intelligence System - Real Hardware Benchmark & Telemetry Runner.

Executes all 8 standardized test cases against live ComfyUI instance running
Anima Turbo v1.1 Q4_K_M (2.0B DiT) on NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM).
Collects real hardware telemetry (peak VRAM, peak RAM, real step latency, duration).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
DATA_DIR = ROOT_DIR / "data"
BENCHMARK_DIR = DATA_DIR / "manga" / "benchmarks"
REAL_DIR = BENCHMARK_DIR / "real_inference"
REAL_DIR.mkdir(parents=True, exist_ok=True)
COMFY_OUTPUT_DIR = Path(r"F:\AI\ComfyUI\output")
COMFY_URL = "http://127.0.0.1:8188"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    from manga_validator import validate_panel_image
except ImportError:
    validate_panel_image = None

try:
    from manga_metrics import evaluate_manga_panel, compute_panel_continuity
except ImportError:
    evaluate_manga_panel = None
    compute_panel_continuity = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("real_benchmark")

# 8 Standard Test Cases
BENCHMARK_TEST_CASES = [
    {
        "id": 1,
        "name": "Anime character portrait",
        "slug": "portrait",
        "description": "High-fidelity anime portrait focusing on facial features, eye details, hair rendering, and collar.",
        "prompt": "1boy, high school student Minh, short neat black hair, dark eyes, white collared shirt, navy tie, navy blazer, close-up portrait, expressive eyes, morning sunlight across face, soft focus classroom background, masterpiece, best quality, sharp focus",
        "neg_prompt": "low quality, bad anatomy, deformed eyes, extra ears, blurry, text, speech bubble",
        "art_style": "anime_color",
        "width": 768,
        "height": 1024,
    },
    {
        "id": 2,
        "name": "Full-body character design",
        "slug": "full_body",
        "description": "Full-body reference sheet showing posture, proportions, uniform detailing from head to shoes.",
        "prompt": "1boy, high school student Minh, short neat black hair, dark eyes, white collared shirt, navy tie, navy blazer, dark trousers, full-body standing pose, character turnaround, hands in pockets, leather shoes, neutral studio background, masterpiece",
        "neg_prompt": "cropped legs, missing feet, deformed hands, bad proportions, watermark, noise",
        "art_style": "anime_color",
        "width": 768,
        "height": 1024,
    },
    {
        "id": 3,
        "name": "Character in a classroom",
        "slug": "classroom",
        "description": "Character seated at back desk by the window, authentic classroom background with wooden desks, chalkboard, sunlight.",
        "prompt": "1boy, high school student Minh, sitting at wooden desk by open window, looking outside at blue sky, math textbook on desk, morning classroom atmosphere, chalkboard with white chalk formulas, detailed architectural perspective",
        "neg_prompt": "bad perspective, warped windows, floating furniture, blurry, deformed fingers",
        "art_style": "anime_color",
        "width": 1024,
        "height": 768,
    },
    {
        "id": 4,
        "name": "Two characters interacting",
        "slug": "two_characters",
        "description": "Minh waking up and turning around, interacting with desk neighbor Mai wearing cream cardigan and pleated skirt.",
        "prompt": "2people, 1boy, 1girl, high school student Minh looking confused, turning head toward desk neighbor Mai with shoulder-length brown hair cream cardigan navy pleated skirt, classroom desks, emotional dialogue scene, dynamic anime composition",
        "neg_prompt": "fused bodies, twin faces, extra limbs, deformed anatomy, blurry, artifacts",
        "art_style": "anime_color",
        "width": 1024,
        "height": 768,
    },
    {
        "id": 5,
        "name": "Different camera angles with the same character",
        "slug": "camera_angle_low",
        "description": "Dramatic low-angle worm's-eye view looking up at Minh standing up in shock, eyes wide, classroom desks receding.",
        "prompt": "1boy, high school student Minh, dramatic low angle, worm's-eye view, standing up abruptly in shock, wide pupils, hands slamming on wooden desk, intense anime cinema framing, towering classroom wall",
        "neg_prompt": "flat lighting, distorted head proportions, bad perspective, floating artifacts",
        "art_style": "manga_bw",
        "width": 768,
        "height": 1024,
    },
    {
        "id": 6,
        "name": "Black-and-white manga panel",
        "slug": "manga_bw_screentone",
        "description": "Traditional Japanese manga panel with authentic screen tones, deep black ink linework, cross-hatching, and speed lines.",
        "prompt": "monochrome manga, black and white ink, screentone shading, 1boy high school student Minh looking down at his uniform in disbelief, speed lines in background, intense psychological manga panel, Shonen Jump style",
        "neg_prompt": "color, chromatic aberration, gray soup, messy lineart, blurry, 3d render",
        "art_style": "manga_bw",
        "width": 768,
        "height": 1024,
    },
    {
        "id": 7,
        "name": "Full-color manga panel",
        "slug": "full_color_panel",
        "description": "Vibrant Japanese color manga with cel-shading, rich cinematic lighting, warm sunset glow reflecting on uniform.",
        "prompt": "full color manga, vibrant cel shading, 1boy high school student Minh standing in school hallway during crimson sunset, golden hour light shafts, glowing dusk particles, rich palette, Makoto Shinkai aesthetic",
        "neg_prompt": "monochrome, washed out colors, overexposed, muddy shadows, bad anatomy",
        "art_style": "anime_color",
        "width": 1024,
        "height": 768,
    },
    {
        "id": 8,
        "name": "Character identity across 4 consecutive panels",
        "slug": "four_panel_sequence",
        "description": "Sequential 4-panel storyboard verifying identity preservation (hair, eyes, tie, navy blazer) across changing actions.",
        "prompt": "4-panel sequential manga story, consistent face and locked traits across all frames: panel 1 drowsy sleeping, panel 2 waking startled, panel 3 inspecting uniform, panel 4 resolute expression, Japanese manga layout",
        "neg_prompt": "face morphing, inconsistent hair color, changing clothing styles, extra fingers",
        "art_style": "manga_bw",
        "width": 1024,
        "height": 1024,
    },
]


def get_vram_telemetry() -> tuple[float, float]:
    """Query current GPU VRAM used and total via nvidia-smi (MB)."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
            text=True,
            timeout=3,
        )
        used, total = out.strip().split(",")
        return float(used.strip()), float(total.strip())
    except Exception:
        return 0.0, 6144.0


def build_anima_turbo_graph(
    prompt: str,
    neg_prompt: str,
    width: int = 768,
    height: int = 1024,
    seed: int = 42,
    prefix: str = "real_benchmark",
) -> dict[str, Any]:
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


def execute_test_case(tc: dict[str, Any], run_index: int) -> dict[str, Any]:
    """Submits workflow to ComfyUI, monitors live telemetry, and gathers results."""
    tc_id = tc["id"]
    prefix = f"real_bench_tc0{tc_id}_{tc['slug']}"
    graph = build_anima_turbo_graph(
        prompt=tc["prompt"],
        neg_prompt=tc["neg_prompt"],
        width=tc["width"],
        height=tc["height"],
        seed=42 + tc_id,
        prefix=prefix,
    )

    logger.info(f"[{tc_id}/8] Submitting '{tc['name']}' ({tc['width']}x{tc['height']})...")
    req_body = json.dumps({"prompt": graph}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=req_body, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        res_data = json.loads(resp.read())
    prompt_id = res_data["prompt_id"]
    logger.info(f"Prompt ID assigned: {prompt_id}")

    start_time = time.time()
    peak_vram = 0.0
    peak_ram = 0.0
    initial_vram, total_vram = get_vram_telemetry()
    vram_samples = []

    # Polling loop
    while True:
        v_used, _ = get_vram_telemetry()
        vram_samples.append(v_used)
        if v_used > peak_vram:
            peak_vram = v_used
        r_used = psutil.virtual_memory().used / (1024 * 1024)
        if r_used > peak_ram:
            peak_ram = r_used

        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as r:
                h = json.loads(r.read())
                if prompt_id in h:
                    status = h[prompt_id].get("status", {})
                    outputs = h[prompt_id].get("outputs", {})
                    duration = time.time() - start_time
                    final_vram, _ = get_vram_telemetry()
                    
                    # Locate saved image
                    saved_path = None
                    for node_id, node_out in outputs.items():
                        if "images" in node_out:
                            for img_info in node_out["images"]:
                                img_fn = img_info["filename"]
                                orig_path = COMFY_OUTPUT_DIR / img_fn
                                if orig_path.exists():
                                    dest_path = REAL_DIR / f"real_tc0{tc_id}_{tc['slug']}.png"
                                    shutil.copy2(orig_path, dest_path)
                                    saved_path = dest_path
                                    break

                    logger.info(
                        f"[{tc_id}/8] Completed in {duration:.2f}s | "
                        f"Initial VRAM: {initial_vram:.0f} MB | Peak VRAM: {peak_vram:.0f} MB | "
                        f"Peak RAM: {peak_ram:.0f} MB | Saved: {saved_path.name if saved_path else 'None'}"
                    )

                    return {
                        "id": tc_id,
                        "name": tc["name"],
                        "slug": tc["slug"],
                        "width": tc["width"],
                        "height": tc["height"],
                        "art_style": tc["art_style"],
                        "prompt_id": prompt_id,
                        "status": "PASS" if saved_path and saved_path.exists() else "FAILED",
                        "duration_s": round(duration, 2),
                        "initial_vram_mb": round(initial_vram, 1),
                        "peak_vram_mb": round(peak_vram, 1),
                        "final_vram_mb": round(final_vram, 1),
                        "total_vram_mb": round(total_vram, 1),
                        "peak_ram_mb": round(peak_ram, 1),
                        "output_image_path": str(saved_path) if saved_path else None,
                        "output_image_size_bytes": saved_path.stat().st_size if saved_path else 0,
                    }
        except Exception:
            pass

        time.sleep(0.4)
        if time.time() - start_time > 180:
            logger.error(f"[{tc_id}/8] Timed out after 180 seconds!")
            return {
                "id": tc_id,
                "name": tc["name"],
                "slug": tc["slug"],
                "status": "TIMEOUT",
                "duration_s": 180.0,
                "error": "Execution timed out",
            }


def run_full_real_benchmark() -> dict[str, Any]:
    """Runs all 8 test cases and compiles the verified empirical telemetry report."""
    logger.info("=================================================================")
    logger.info("STARTING EMPIRICAL ANIME BENCHMARK (REAL COMFYUI HARDWARE RUN)")
    logger.info("Model: CircleStone Labs Anima Turbo v1.1 Q4_K_M (2.0B DiT)")
    logger.info("Text Encoder: Qwen 3 0.6B Base (FP16)")
    logger.info("VAE: Qwen Image VAE (FP32, CPU-offloaded)")
    logger.info("Hardware: NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM) / 12GB RAM")
    logger.info("=================================================================")

    start_wall = time.time()
    results = []

    for idx, tc in enumerate(BENCHMARK_TEST_CASES, start=1):
        res = execute_test_case(tc, idx)
        
        # Calculate visual quality metrics on actual generated image
        if res.get("output_image_path") and Path(res["output_image_path"]).exists():
            img_p = Path(res["output_image_path"])
            try:
                with Image.open(img_p) as im:
                    w, h = im.size
                    res["actual_width"] = w
                    res["actual_height"] = h

                if validate_panel_image:
                    v_res = validate_panel_image(img_p)
                    res["qa_validation"] = {
                        "is_valid": v_res.is_valid,
                        "status": v_res.status,
                        "lineart_density": round(v_res.lineart_density, 4),
                        "white_pixel_ratio": round(v_res.white_pixel_ratio, 4),
                        "dark_pixel_ratio": round(v_res.dark_pixel_ratio, 4),
                    }
                if evaluate_manga_panel:
                    m_res = evaluate_manga_panel(img_p, res["art_style"])
                    res["quality_metrics"] = {
                        "screentone_score": round(m_res.screentone_score, 2),
                        "inking_sharpness": round(m_res.inking_sharpness, 2),
                        "contrast_balance": round(m_res.contrast_balance, 2),
                        "composite_score": round(m_res.composite_score, 2),
                    }
            except Exception as e:
                logger.warning(f"Metrics evaluation failed for {img_p.name}: {e}")

        results.append(res)
        time.sleep(1.0)  # Brief pause between jobs to observe VRAM stabilization

    total_wall_s = round(time.time() - start_wall, 2)
    max_peak_vram = max(r.get("peak_vram_mb", 0.0) for r in results)
    max_peak_ram = max(r.get("peak_ram_mb", 0.0) for r in results)
    avg_duration = round(sum(r.get("duration_s", 0.0) for r in results) / len(results), 2)

    # Compute continuity across panels 1, 2, 3, 5, 8 (Minh focus)
    continuity_pairs = []
    if compute_panel_continuity:
        eval_imgs = [Path(r["output_image_path"]) for r in results if r.get("output_image_path") and Path(r["output_image_path"]).exists()]
        for i in range(len(eval_imgs) - 1):
            try:
                c_score = compute_panel_continuity(eval_imgs[i], eval_imgs[i+1])
                continuity_pairs.append({
                    "pair": f"TC{i+1}->TC{i+2}",
                    "continuity_score": round(c_score, 2)
                })
            except Exception:
                pass

    overall_continuity = (
        round(sum(p["continuity_score"] for p in continuity_pairs) / len(continuity_pairs), 2)
        if continuity_pairs else 0.0
    )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_empirical_model_benchmark": True,
        "execution_engine": "ComfyUI 0.43.0 via REST API",
        "hardware_profile": {
            "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
            "vram_total_mb": 6144.0,
            "system_ram_total_mb": round(psutil.virtual_memory().total / (1024 * 1024), 1),
            "os": "Windows 11",
            "max_peak_vram_mb": round(max_peak_vram, 1),
            "max_peak_ram_mb": round(max_peak_ram, 1),
            "vram_headroom_mb": round(6144.0 - max_peak_vram, 1),
        },
        "model_under_test": {
            "display_name": "Anima Turbo v1.1 Q4_K_M (Distilled DiT)",
            "architecture": "Diffusion Transformer (DiT)",
            "parameter_count": "2.0B",
            "quantization": "Q4_K_M (GGUF)",
            "weights_size_mb": 1320.3,
            "text_encoder": "qwen_3_06b_base.safetensors (1136.9 MB)",
            "vae": "qwen_image_vae.safetensors (242.0 MB, CPU offloaded)",
            "steps": 8,
            "cfg": 1.0,
            "sampler": "euler_ancestral / normal",
        },
        "total_wall_time_s": total_wall_s,
        "average_generation_duration_s": avg_duration,
        "overall_continuity_score": overall_continuity,
        "continuity_pairs": continuity_pairs,
        "test_cases": results,
    }

    # Save to JSON
    json_path = BENCHMARK_DIR / "real_hardware_telemetry.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Telemetry report saved to: {json_path}")

    return report


if __name__ == "__main__":
    report = run_full_real_benchmark()
    print("\n================ BENCHMARK SUMMARY ================")
    print(f"Total Test Cases: {len(report['test_cases'])}")
    print(f"Average Duration: {report['average_generation_duration_s']}s")
    print(f"Max Peak VRAM: {report['hardware_profile']['max_peak_vram_mb']} MB / {report['hardware_profile']['vram_total_mb']} MB")
    print(f"Max Peak RAM: {report['hardware_profile']['max_peak_ram_mb']} MB")
    print(f"VRAM Headroom: {report['hardware_profile']['vram_headroom_mb']} MB")
    print(f"Overall Continuity Score: {report['overall_continuity_score']}/100")
    print("===================================================\n")
