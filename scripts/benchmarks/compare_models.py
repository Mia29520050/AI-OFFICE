import os
from PIL import Image, ImageDraw, ImageFont
from app.manga_composer import apply_de_ai_organic_enhancer

P1_PATH = r"F:\AI-Office\data\manga\test_cfg_comparison\carmilla_cfg_1.5.png"
P2_PATH = r"F:\AI-Office\data\manga\carmilla_deltamix_v8_raw.png"
ORGANIC_OUT = r"F:\AI-Office\data\manga\carmilla_deltamix_v8_organic.png"
COMPARE_OUT = r"F:\AI-Office\data\manga\carmilla_model_benchmark_comparison.png"
ARTIFACT_DIR = r"C:\Users\Shiro\.gemini\antigravity\brain\d2888882-c5f1-463b-913f-d9262e881394"

# 1. Apply De-AI Organic filter to DeltaMix
img2 = Image.open(P2_PATH).convert("RGB")
img2_organic = apply_de_ai_organic_enhancer(img2, grain_intensity=0.08, gpen_contrast=1.25, sharpness=1.45)
img2_organic.save(ORGANIC_OUT, "PNG")

# 2. Build Side-by-Side comparison canvas
img1 = Image.open(P1_PATH).convert("RGB").resize((768, 1024), Image.Resampling.LANCZOS)
img2_raw = img2.resize((768, 1024), Image.Resampling.LANCZOS)
img2_org = img2_organic.resize((768, 1024), Image.Resampling.LANCZOS)

cw, ch = 768 * 3 + 40, 1024 + 140
canvas = Image.new("RGB", (cw, ch), (18, 18, 24))
draw = ImageDraw.Draw(canvas)

try:
    font_title = ImageFont.truetype(r"F:\AI-Office\app\ui\assets\fonts\ComicNeue-Bold.ttf", 36)
    font_sub = ImageFont.truetype(r"F:\AI-Office\app\ui\assets\fonts\PatrickHand-Regular.ttf", 24)
except Exception:
    font_title = font_sub = ImageFont.load_default()

# Header
draw.text((30, 20), "MODEL BENCHMARK: ANIMA TURBO GGUF vs ANIMA DELTA MIX 2.9B (CIVITAI v8.0)", fill=(255, 230, 150), font=font_title)
draw.text((30, 65), "Comparing Base Distilled Turbo (CFG 1.5) vs Non-Turbo 40-Block Merge (DeltaMix v8.0) + De-AI Filter", fill=(200, 200, 210), font=font_sub)

# Paste images
canvas.paste(img1, (10, 110))
canvas.paste(img2_raw, (768 + 20, 110))
canvas.paste(img2_org, (768 * 2 + 30, 110))

# Captions below/above
draw.text((15, 115), "[A] Anima Turbo Q4_K_M (8 steps, CFG 1.5)", fill=(255, 255, 255), font=font_sub)
draw.text((768 + 25, 115), "[B] Anima DeltaMix v8.0 Raw (25 steps, CFG 4.5)", fill=(255, 255, 255), font=font_sub)
draw.text((768 * 2 + 35, 115), "[C] DeltaMix v8.0 + De-AI Organic Filter", fill=(255, 230, 100), font=font_sub)

canvas.save(COMPARE_OUT, "PNG")

# Copy to artifacts
for fname in ["carmilla_deltamix_v8_raw.png", "carmilla_deltamix_v8_organic.png", "carmilla_model_benchmark_comparison.png"]:
    src = os.path.join(r"F:\AI-Office\data\manga", fname)
    dst = os.path.join(ARTIFACT_DIR, fname)
    if os.path.exists(src):
        with open(src, "rb") as sf, open(dst, "wb") as df:
            df.write(sf.read())

print(f"[BENCHMARK] Comparison image generated at {COMPARE_OUT} and copied to artifact directory!")
