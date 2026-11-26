import urllib.request
import json
import re

url = "https://civitai.com/api/v1/models/2898169"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, timeout=12) as r:
        data = json.loads(r.read())

    print("Title:", data.get("name"))
    print("Type:", data.get("type"))
    print("Tags:", data.get("tags"))
    
    desc = data.get("description", "")
    # strip html
    clean_desc = re.sub(r"<[^>]+>", " ", desc)
    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
    print("\nDescription:\n", clean_desc[:1200])

    print("\nModel Versions:")
    for v in data.get("modelVersions", []):
        v_id = v.get("id")
        v_name = v.get("name")
        base = v.get("baseModel")
        files = v.get("files", [])
        f_info = ", ".join([f"{f.get('name')} ({round(f.get('sizeKB',0)/1024, 1)} MB)" for f in files])
        print(f"  - Version {v_id}: {v_name} | Base: {base} | Files: {f_info}")
        images = v.get("images", [])
        if images:
            meta = images[0].get("meta", {})
            print(f"    Sample Prompt: {meta.get('prompt', 'N/A')[:200]}")
            print(f"    Sampler: {meta.get('sampler', 'N/A')}, Steps: {meta.get('steps', 'N/A')}, CFG: {meta.get('cfgScale', 'N/A')}")
except Exception as e:
    print("Error:", e)
