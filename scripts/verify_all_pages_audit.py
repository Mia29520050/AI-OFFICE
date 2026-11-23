import os
import glob
import json
import zipfile
import math
from PIL import Image

def get_stats_from_hist(img_l):
    hist = img_l.histogram()
    total_pixels = img_l.width * img_l.height
    dark_pixels = sum(hist[:40])
    white_pixels = sum(hist[245:])
    mid_pixels = sum(hist[40:245])
    
    mean_lum = sum(i * count for i, count in enumerate(hist)) / total_pixels
    var_lum = sum(((i - mean_lum) ** 2) * count for i, count in enumerate(hist)) / total_pixels
    std_lum = math.sqrt(var_lum)
    
    return {
        "dark_ratio": round(dark_pixels / total_pixels, 4),
        "white_ratio": round(white_pixels / total_pixels, 4),
        "mid_ratio": round(mid_pixels / total_pixels, 4),
        "mean_lum": round(mean_lum, 2),
        "std_lum": round(std_lum, 2)
    }

def run_audit():
    bw_dir = "data/manga/exports/moonlight_classroom_ch01_bw"
    color_dir = "data/manga/exports/moonlight_classroom_ch01_color"
    bw_cbz = "data/manga/exports/moonlight_classroom_ch01_bw.cbz"
    bw_pdf = "data/manga/exports/moonlight_classroom_ch01_bw.pdf"
    color_cbz = "data/manga/exports/moonlight_classroom_ch01_color.cbz"
    color_pdf = "data/manga/exports/moonlight_classroom_ch01_color.pdf"

    bw_files = sorted(glob.glob(os.path.join(bw_dir, "page_*.png")))
    color_files = sorted(glob.glob(os.path.join(color_dir, "page_*.png")))

    print(f"=== MOONLIGHT CLASSROOM CH. 1 GLOBAL AUDIT ===")
    print(f"Found BW Pages: {len(bw_files)}")
    print(f"Found Color Pages: {len(color_files)}")

    bw_stats = []
    for f in bw_files:
        with Image.open(f) as img:
            w, h = img.size
            mode = img.mode
            img_l = img.convert("L")
            st = get_stats_from_hist(img_l)
            bw_stats.append({
                "page": os.path.basename(f),
                "size": f"{w}x{h}",
                "mode": mode,
                "file_size_kb": round(os.path.getsize(f) / 1024, 2),
                **st
            })

    color_stats = []
    for f in color_files:
        with Image.open(f) as img:
            w, h = img.size
            mode = img.mode
            img_l = img.convert("L")
            st = get_stats_from_hist(img_l)
            color_stats.append({
                "page": os.path.basename(f),
                "size": f"{w}x{h}",
                "mode": mode,
                "file_size_kb": round(os.path.getsize(f) / 1024, 2),
                **st
            })

    # Audit CBZ
    cbz_results = {}
    for name, path in [("BW CBZ", bw_cbz), ("Color CBZ", color_cbz)]:
        if os.path.exists(path):
            with zipfile.ZipFile(path, "r") as z:
                namelist = z.namelist()
                has_comicinfo = "ComicInfo.xml" in namelist
                comicinfo_xml = ""
                if has_comicinfo:
                    comicinfo_xml = z.read("ComicInfo.xml").decode("utf-8", errors="ignore")
                cbz_results[name] = {
                    "exists": True,
                    "size_bytes": os.path.getsize(path),
                    "file_count": len(namelist),
                    "has_comicinfo": has_comicinfo,
                    "comicinfo_full": comicinfo_xml,
                    "images": [x for x in namelist if x.endswith(".png")]
                }

    # Audit PDF
    pdf_results = {}
    for name, path in [("BW PDF", bw_pdf), ("Color PDF", color_pdf)]:
        if os.path.exists(path):
            with open(path, "rb") as pf:
                header = pf.read(10)
            pdf_results[name] = {
                "exists": True,
                "size_bytes": os.path.getsize(path),
                "header": str(header)
            }

    report = {
        "bw_pages_count": len(bw_stats),
        "color_pages_count": len(color_stats),
        "bw_stats": bw_stats,
        "color_stats": color_stats,
        "cbz_results": cbz_results,
        "pdf_results": pdf_results
    }

    os.makedirs("data/manga/exports/inspections", exist_ok=True)
    with open("data/manga/exports/inspections/verifier_audit_prelim.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("Audit JSON written to data/manga/exports/inspections/verifier_audit_prelim.json")
    print(f"BW stats sample (page 1): {bw_stats[0]}")
    print(f"Color stats sample (page 1): {color_stats[0]}")

if __name__ == "__main__":
    run_audit()
