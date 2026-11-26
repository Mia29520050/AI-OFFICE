import urllib.request
import re
import json

url = "https://hinettruyen.com/truyen-tranh/huyet-co-va-ky-si"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req, timeout=12) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
except Exception as e:
    print(f"Error fetching URL: {e}")
    html = ""

if html:
    def clean(s):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()

    title_match = re.search(r"<h1[^>]*class=['\"][^'\"]*title-detail[^'\"]*['\"][^>]*>(.*?)</h1>", html, re.I | re.S)
    print("=== TÊN TRUYỆN ===")
    print(clean(title_match.group(1)) if title_match else "N/A")

    # Author
    author_m = re.search(r"<li[^>]*class=['\"][^'\"]*author[^'\"]*['\"][^>]*>(.*?)</li>", html, re.I | re.S)
    if author_m:
        print("\n=== TÁC GIẢ ===")
        print(clean(author_m.group(1)))

    # Status
    status_m = re.search(r"<li[^>]*class=['\"][^'\"]*status[^'\"]*['\"][^>]*>(.*?)</li>", html, re.I | re.S)
    if status_m:
        print("\n=== TÌNH TRẠNG ===")
        print(clean(status_m.group(1)))

    # Genres
    genres_m = re.search(r"<li[^>]*class=['\"][^'\"]*kind[^'\"]*['\"][^>]*>(.*?)</li>", html, re.I | re.S)
    if genres_m:
        print("\n=== THỂ LOẠI ===")
        print(clean(genres_m.group(1)))

    # Synopsis
    desc_m = re.search(r"<div[^>]*class=['\"][^'\"]*detail-content[^'\"]*['\"][^>]*>(.*?)</div>", html, re.I | re.S)
    if desc_m:
        print("\n=== TÓM TẮT NỘI DUNG ===")
        print(clean(desc_m.group(1)))
    else:
        meta_m = re.search(r"<meta[^>]*name=['\"]description['\"][^>]*content=['\"]([^'\"]*)['\"]", html, re.I)
        if meta_m:
            print("\n=== META MÔ TẢ ===")
            print(clean(meta_m.group(1)))

    # Cover image
    img_m = re.search(r"<div[^>]*class=['\"][^'\"]*col-image[^'\"]*['\"][^>]*>.*?<img[^>]*src=['\"]([^'\"]*)['\"]", html, re.I | re.S)
    if img_m:
        print("\n=== LINK ẢNH BÌA ===")
        print(img_m.group(1))

    # Chapters list
    chaps = re.findall(r"<a[^>]*href=['\"]([^'\"]*chap[^'\"]*)['\"][^>]*>(.*?)</a>", html, re.I)
    print(f"\n=== TỔNG SỐ CHƯƠNG TÌM THẤY: {len(chaps)} ===")
    for href, cname in chaps[:10]:
        print(f"  - {clean(cname)}: {href}")
