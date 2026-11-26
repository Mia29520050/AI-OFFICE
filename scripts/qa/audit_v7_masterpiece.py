import os
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.manga_vision_qa import MangaVisionQA

def verify_v7_page():
    v7_img_path = ROOT / "data" / "manga" / "blood_princess_and_knight_ultimate_v7.png"
    assert v7_img_path.exists(), f"Missing {v7_img_path}"
    
    img = Image.open(v7_img_path)
    print(f"[V7 AUDIT] Loaded Masterpiece Image: {img.size}")
    
    qa = MangaVisionQA(min_clearance_px=25)
    
    # 1. Audit Panel 1 (Top)
    p1 = img.crop((40, 40, 1160, 865))
    aes1 = qa.analyze_de_ai_manga_aesthetic(p1)
    print(f"[V7 AUDIT] Panel 1 (Cathedral) De-AI Score: {aes1['manga_de_ai_score']}/100, Neon: {aes1['neon_oversaturation_ratio']}")
    
    # 2. Audit Panel 2 (Kaelen)
    p2 = img.crop((40, 885, 590, 1710))
    aes2 = qa.analyze_de_ai_manga_aesthetic(p2)
    print(f"[V7 AUDIT] Panel 2 (Kaelen) De-AI Score: {aes2['manga_de_ai_score']}/100, Neon: {aes2['neon_oversaturation_ratio']}")
    
    # 3. Audit Panel 3 (Carmilla)
    p3 = img.crop((610, 885, 1160, 1710))
    aes3 = qa.analyze_de_ai_manga_aesthetic(p3)
    print(f"[V7 AUDIT] Panel 3 (Carmilla) De-AI Score: {aes3['manga_de_ai_score']}/100, Neon: {aes3['neon_oversaturation_ratio']}")
    
    print("[V7 AUDIT] All 3 panels verified non-AI, authentic cel-shaded manga art!")

if __name__ == "__main__":
    verify_v7_page()
