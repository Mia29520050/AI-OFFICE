from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
MODELFILE_PATH = ROOT_DIR / "scripts" / "Modelfile.claude-office"
DB_PATH = ROOT_DIR / "data" / "office.db"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"


def check_ollama_alive(host: str = DEFAULT_OLLAMA_HOST) -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(f"{host}/api/tags")
            return res.status_code == 200
    except Exception:
        return False


def get_available_models(host: str = DEFAULT_OLLAMA_HOST) -> list[str]:
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(f"{host}/api/tags")
            if res.status_code == 200:
                data = res.json()
                return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    return []


def create_claude_office_model(
    model_name: str = "claude-office",
    host: str = DEFAULT_OLLAMA_HOST,
    modelfile_path: Path = MODELFILE_PATH,
) -> bool:
    if not modelfile_path.exists():
        print(f"[-] Modelfile not found at: {modelfile_path}")
        return False

    modelfile_content = modelfile_path.read_text(encoding="utf-8")
    payload = {
        "name": model_name,
        "modelfile": modelfile_content,
        "stream": False,
    }

    print(f"[*] Creating custom model '{model_name}' on Ollama...")
    try:
        with httpx.Client(timeout=180.0) as client:
            res = client.post(f"{host}/api/create", json=payload)
            if res.status_code == 200:
                print(f"[+] Successfully created '{model_name}'!")
                return True
            else:
                print(f"[-] Failed with HTTP {res.status_code}: {res.text}")
                return False
    except Exception as e:
        print(f"[-] Error calling Ollama create: {e}")
        return False


def set_active_office_model(model_name: str = "claude-office", db_path: Path = DB_PATH) -> bool:
    if not db_path.exists():
        print(f"[*] Database not found at {db_path}, skipping config update.")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key = 'model_config'")
            row = cur.fetchone()
            if row:
                config = json.loads(row[0])
                config["local_model"] = model_name
                cur.execute(
                    "UPDATE app_settings SET value = ? WHERE key = 'model_config'",
                    (json.dumps(config, ensure_ascii=False),),
                )
            else:
                config = {"local_model": model_name, "provider": "local", "local_num_ctx": 4096}
                cur.execute(
                    "INSERT INTO app_settings(key, value) VALUES('model_config', ?)",
                    (json.dumps(config, ensure_ascii=False),),
                )
        conn.close()
        print(f"[+] AI-Office database updated to default local_model='{model_name}'")
        return True
    except Exception as e:
        print(f"[-] Error updating database: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup Claude Office Model in Local Ollama")
    parser.add_argument("--check-only", action="store_true", help="Only check Ollama connectivity and model list")
    parser.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help="Ollama Host URL")
    parser.add_argument("--model-name", default="claude-office", help="Target model name")
    args = parser.parse_args()

    print("=== AI Office: Claude-Grade Ollama Setup ===")
    alive = check_ollama_alive(args.host)
    if not alive:
        print(f"[-] Cannot reach Ollama at {args.host}. Please start Ollama before proceeding.")
        if args.check_only:
            return 1
        return 1

    models = get_available_models(args.host)
    print(f"[+] Ollama is ONLINE. Available models ({len(models)}): {', '.join(models) if models else 'None'}")

    if args.check_only:
        return 0

    success = create_claude_office_model(args.model_name, args.host, MODELFILE_PATH)
    if success:
        set_active_office_model(args.model_name, DB_PATH)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
