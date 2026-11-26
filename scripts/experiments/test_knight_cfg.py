import urllib.request
import json
import time
from pathlib import Path
import shutil

COMFY_URL = "http://127.0.0.1:8188"
OUT_DIR = Path("F:/AI-Office/data/manga/test_cfg_comparison")
OUT_DIR.mkdir(parents=True, exist_ok=True)
ART_DIR = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394")

def queue_prompt(prompt_graph):
    data = json.dumps({"prompt": prompt_graph}).encode('utf-8')
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())['prompt_id']

def wait_for_prompt(prompt_id):
    while True:
        req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}")
        with urllib.request.urlopen(req, timeout=10) as r:
            history = json.loads(r.read())
            if prompt_id in history:
                outputs = history[prompt_id].get('outputs', {})
                for node_id, node_out in outputs.items():
                    if 'images' in node_out and len(node_out['images']) > 0:
                        fn = node_out['images'][0]['filename']
                        return fn
        time.sleep(1.0)

def download_image(filename, dest_path):
    url = f"{COMFY_URL}/view?filename={filename}&type=output"
    with urllib.request.urlopen(url, timeout=10) as r:
        with open(dest_path, 'wb') as f:
            f.write(r.read())

def test_knight():
    prompt_text = "masterpiece, best quality, score_7, newest, highres, absurdres, safe, 1boy, solo, dark fantasy knight, 3/4 battle stance, messy black hair, intense glowing amber eyes, wearing dark steel plate armor with intricate glowing red runes, tattered cape, holding heavy steel broadsword with both hands, correct hand grip, dynamic lighting, dramatic rim lighting, intricate fine lineart, modern anime illustration 2024"
    neg_text = "worst quality, low quality, score_4, score_5, blurry, 3d, plastic skin, clay, flat lighting, amateur, deformed hands, bad anatomy, cartoonish"

    for seed in [20261132, 777888]:
        print(f"Testing Knight Seed = {seed} with CFG 1.5 ...")
        graph = {
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": "anima-turbo-v1.1-Q4_K_M.gguf"},
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {"clip_name": "qwen_3_06b_base.safetensors", "type": "stable_diffusion"},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt_text, "clip": ["2", 0]},
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": neg_text, "clip": ["2", 0]},
            },
            "5": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "qwen_image_vae.safetensors"},
            },
            "6": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 768, "batch_size": 1},
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": 10,
                    "cfg": 1.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["6", 0],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["7", 0], "vae": ["5", 0]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": f"test_knight_{seed}", "images": ["8", 0]},
            },
        }

        pid = queue_prompt(graph)
        fn = wait_for_prompt(pid)
        dest = OUT_DIR / f"knight_seed_{seed}.png"
        download_image(fn, dest)
        shutil.copyfile(dest, ART_DIR / f"knight_seed_{seed}.png")
        print(f"Saved: {dest}")

if __name__ == "__main__":
    test_knight()
