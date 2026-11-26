import urllib.request
import re
import json

url = "https://hinettruyen.com/truyen-tranh/huyet-co-va-ky-si"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        m_title = re.search(r"<title>(.*?)</title>", html, re.I)
        print("Page Title:", m_title.group(1) if m_title else "None")
        
        # Look for chapters
        chap_links = re.findall(r'href="([^"]*chap[^"]*)"', html, re.I)
        print("Chapter links count:", len(chap_links))
        if chap_links:
            print("First chapter link:", chap_links[0])
            
        # Look for cover or manga details
        meta_desc = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.I)
        if meta_desc:
            print("Description:", meta_desc.group(1)[:300])
except Exception as e:
    print("Error:", e)
