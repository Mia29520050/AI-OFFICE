import os
import sys
import time
import urllib.request

MODEL_URL = "https://civitai.com/api/download/models/3485184"
DEST_DIR = r"F:\AI\ComfyUI\models\diffusion_models"
FINAL_FILE = os.path.join(DEST_DIR, "2.9V8.safetensors")
PART_FILE = FINAL_FILE + ".part"

os.makedirs(DEST_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

if os.path.exists(FINAL_FILE):
    size_mb = os.path.getsize(FINAL_FILE) / 1024 / 1024
    print(f"[DOWNLOAD] File already exists: {FINAL_FILE} ({size_mb:.2f} MB)")
    sys.exit(0)

existing_bytes = os.path.getsize(PART_FILE) if os.path.exists(PART_FILE) else 0
if existing_bytes > 0:
    headers["Range"] = f"bytes={existing_bytes}-"
    print(f"[DOWNLOAD] Resuming from byte {existing_bytes} ({existing_bytes / 1024 / 1024:.2f} MB)...")

req = urllib.request.Request(MODEL_URL, headers=headers)
print(f"[DOWNLOAD] Connecting to {MODEL_URL}...")

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        content_range = resp.headers.get("Content-Range")
        total_len = resp.headers.get("Content-Length")
        total_bytes = int(total_len) + existing_bytes if total_len else 0
        print(f"[DOWNLOAD] Total size: {total_bytes / 1024 / 1024:.2f} MB")

        mode = "ab" if existing_bytes > 0 and resp.status == 206 else "wb"
        downloaded = existing_bytes if mode == "ab" else 0

        chunk_size = 1024 * 1024 * 2  # 2MB chunks
        last_log = time.time()
        start_time = time.time()

        with open(PART_FILE, mode) as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                if now - last_log >= 5.0:
                    pct = (downloaded / total_bytes * 100) if total_bytes > 0 else 0
                    speed = (downloaded - existing_bytes) / (now - start_time) / 1024 / 1024
                    elapsed = now - start_time
                    remaining = (total_bytes - downloaded) / (speed * 1024 * 1024) if speed > 0 and total_bytes > 0 else 0
                    print(f"[DOWNLOAD] {downloaded / 1024 / 1024:.1f}/{total_bytes / 1024 / 1024:.1f} MB ({pct:.1f}%) | {speed:.2f} MB/s | ETA: {remaining:.0f}s")
                    last_log = now

        print(f"[DOWNLOAD] Download complete! Renaming to {FINAL_FILE}...")
        if os.path.exists(FINAL_FILE):
            os.remove(FINAL_FILE)
        os.rename(PART_FILE, FINAL_FILE)
        print(f"[DOWNLOAD] SUCCESS: {FINAL_FILE} ({os.path.getsize(FINAL_FILE) / 1024 / 1024:.2f} MB)")

except Exception as e:
    print(f"[DOWNLOAD ERROR] {e}")
    sys.exit(1)
