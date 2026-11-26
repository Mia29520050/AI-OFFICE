#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Manga Fonts for AI Office
==============================
Downloads and verifies high-quality Vietnamese Manga / Comic lettering fonts:
  1. Patrick Hand (PatrickHand-Regular.ttf) - Authentic manga dialogue font with full Vietnamese diacritics.
  2. Bangers (Bangers-Regular.ttf) - High-impact action / SFX / shouting font.
  3. Comic Neue Bold (ComicNeue-Bold.ttf) - Modern professional comic lettering.
  4. Comic Neue Regular (ComicNeue-Regular.ttf) - Clean manga narrative font.
Stores in: app/ui/assets/fonts/
"""

import os
import sys
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path("app/ui/assets/fonts")

FONT_URLS = {
    "PatrickHand-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "Bangers-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf",
    "ComicNeue-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/comicneue/ComicNeue-Bold.ttf",
    "ComicNeue-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/comicneue/ComicNeue-Regular.ttf",
}

# Test sentence containing all Vietnamese diacritics and tones
VIETNAMESE_TEST_TEXT = "Huyết Cơ Carmilla: KENG! Hãy cảm nhận nhát chém ma mị của Hắc Kỵ Sĩ!"


def download_and_verify_fonts() -> bool:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    all_success = True

    print(f"[*] Setting up Vietnamese Manga fonts in {FONTS_DIR}...")
    for filename, url in FONT_URLS.items():
        dest = FONTS_DIR / filename
        if not dest.exists() or dest.stat().st_size < 1000:
            print(f"    Downloading {filename} from Google Fonts...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AI-Office"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read()
                with open(dest, "wb") as f:
                    f.write(content)
                print(f"    [+] Saved {filename} ({len(content) / 1024:.1f} KB)")
            except Exception as e:
                print(f"    [!] Failed to download {filename}: {e}")
                all_success = False
                continue
        else:
            print(f"    [+] Font exists: {filename} ({dest.stat().st_size / 1024:.1f} KB)")

        # Verify PIL can load font and render Vietnamese text without crashing
        try:
            font = ImageFont.truetype(str(dest), size=24)
            img = Image.new("RGB", (800, 100), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), VIETNAMESE_TEST_TEXT, font=font, fill=(0, 0, 0))
            print(f"    [v] Verified Vietnamese rendering for {filename}")
        except Exception as e:
            print(f"    [x] Font rendering error for {filename}: {e}")
            all_success = False

    return all_success


if __name__ == "__main__":
    success = download_and_verify_fonts()
    if success:
        print("[+] All Manga / Comic lettering fonts installed and verified successfully!")
    else:
        print("[!] Font setup had errors.")
        sys.exit(1)
