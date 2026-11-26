# -*- coding: utf-8 -*-
"""
app/library_service.py
======================
Unified Media & Assets Library Service for AI Office.
Supports ChatGPT/Gemini-style asset management:
- AI Generated Images (Chat generated & Studio generated)
- User Uploaded Images & Files (chat_attachments)
- Document & Code attachments
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("library_service")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "office.db"
CHAT_IMAGES_DIR = DATA_DIR / "manga" / "chat_generated"
CHAT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _format_timestamp(ts: float) -> str:
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def list_library_items(
    filter_type: str = "all",
    search: str = ""
) -> List[Dict[str, Any]]:
    """
    Scans and aggregates:
    1. Generated images in data/manga/chat_generated/ and key studio directories.
    2. Uploaded attachments stored in SQLite chat_attachments.
    """
    items: List[Dict[str, Any]] = []
    search_lower = (search or "").strip().lower()

    # -----------------------------------------------------------------------
    # 1. AI Generated Images
    # -----------------------------------------------------------------------
    candidate_folders = [
        (CHAT_IMAGES_DIR, "Ảnh tạo từ Chat", "chat_generated"),
        (DATA_DIR / "manga" / "genshin_panels", "Genshin Studio", "studio"),
        (DATA_DIR / "manga" / "blood_princess_panels", "Blood Princess", "studio"),
        (DATA_DIR / "manga" / "raiden_tests", "Raiden Benchmark", "studio"),
    ]

    for folder, category_label, source in candidate_folders:
        if not folder.exists():
            continue
        for p in folder.glob("*.png"):
            if not p.is_file():
                continue
            fname = p.name
            stat = p.stat()
            size_bytes = stat.st_size
            created_at_str = _format_timestamp(stat.st_mtime)

            # Determine human-friendly title
            title = fname
            if "hutao" in fname.lower():
                title = "Hu Tao (Genshin Impact)"
            elif "raiden" in fname.lower():
                title = "Raiden Shogun (Genshin Impact)"
            elif "carmilla" in fname.lower():
                title = "Carmilla (Blood Princess)"
            elif "kaelen" in fname.lower():
                title = "Kaelen (Blood Knight)"
            elif "cathedral" in fname.lower():
                title = "Thánh Điện Tàn Tích"
            else:
                title = fname.replace("_", " ").replace(".png", "").title()

            # URL
            url = f"/api/chat/images/{fname}"

            item = {
                "id": f"gen_{fname}",
                "name": fname,
                "title": title,
                "category": "generated",
                "category_label": category_label,
                "source": source,
                "type": "image",
                "media_type": "image/png",
                "url": url,
                "thumbnail_url": url,
                "size_bytes": size_bytes,
                "created_at": created_at_str,
                "mtime": stat.st_mtime,
                "can_delete": True,
            }
            items.append(item)

    # -----------------------------------------------------------------------
    # 2. Uploaded Attachments from SQLite chat_attachments
    # -----------------------------------------------------------------------
    try:
        with get_db() as db:
            rows = db.execute(
                """
                SELECT a.id, a.message_id, a.name, a.media_type, a.content, a.data_base64,
                       m.conversation_id, m.created_at
                FROM chat_attachments a
                JOIN messages m ON a.message_id = m.id
                ORDER BY a.id DESC
                """
            ).fetchall()

            for r in rows:
                att_id = r["id"]
                att_name = r["name"]
                media_type = (r["media_type"] or "application/octet-stream").lower()
                is_img = media_type.startswith("image/")
                size_est = len(r["data_base64"]) * 3 // 4 if r["data_base64"] else len(r["content"].encode("utf-8"))
                created_raw = r["created_at"] or ""
                # Parse created_at
                created_disp = created_raw[:16].replace("T", " ") if created_raw else ""

                url = f"/api/library/attachments/{att_id}"
                thumb_url = url if is_img else ""

                item = {
                    "id": f"att_{att_id}",
                    "name": att_name,
                    "title": att_name,
                    "category": "upload",
                    "category_label": "Tệp đính kèm người dùng",
                    "source": "upload",
                    "type": "image" if is_img else "document",
                    "media_type": media_type,
                    "url": url,
                    "thumbnail_url": thumb_url,
                    "size_bytes": size_est,
                    "created_at": created_disp,
                    "mtime": 0.0,
                    "can_delete": True,
                    "message_id": r["message_id"],
                    "conversation_id": r["conversation_id"],
                }
                items.append(item)
    except Exception as e:
        logger.error(f"[Library] Error querying chat_attachments: {e}")

    # -----------------------------------------------------------------------
    # Filtering & Sorting
    # -----------------------------------------------------------------------
    filtered: List[Dict[str, Any]] = []
    for it in items:
        # Search match
        if search_lower:
            match = (
                search_lower in it["name"].lower()
                or search_lower in it["title"].lower()
                or search_lower in it["category_label"].lower()
            )
            if not match:
                continue

        # Type filter
        if filter_type == "all":
            filtered.append(it)
        elif filter_type == "generated" and it["category"] == "generated":
            filtered.append(it)
        elif filter_type == "uploads" and it["category"] == "upload":
            filtered.append(it)
        elif filter_type == "images" and it["type"] == "image":
            filtered.append(it)
        elif filter_type == "documents" and it["type"] == "document":
            filtered.append(it)

    # Sort newest first
    filtered.sort(key=lambda x: x.get("mtime", 0) or 0, reverse=True)
    return filtered


def get_attachment_payload(attachment_id: int) -> Tuple[bytes, str, str]:
    """
    Retrieves attachment raw bytes, mime_type, filename.
    Raises FileNotFoundError if not found.
    """
    with get_db() as db:
        row = db.execute(
            "SELECT name, media_type, content, data_base64 FROM chat_attachments WHERE id=?",
            (attachment_id,)
        ).fetchone()

        if not row:
            raise FileNotFoundError(f"Attachment {attachment_id} not found")

        name = row["name"] or f"attachment_{attachment_id}"
        m_type = row["media_type"] or "application/octet-stream"

        if row["data_base64"]:
            try:
                raw_bytes = base64.b64decode(row["data_base64"])
                return raw_bytes, m_type, name
            except Exception:
                pass

        raw_bytes = (row["content"] or "").encode("utf-8")
        return raw_bytes, m_type, name


def delete_library_item(item_id: str) -> bool:
    """Deletes an item by its id prefix ('gen_' or 'att_')."""
    if item_id.startswith("gen_"):
        fname = item_id[4:]
        target = CHAT_IMAGES_DIR / fname
        if target.is_file():
            target.unlink()
            return True
        return False
    elif item_id.startswith("att_"):
        try:
            att_id = int(item_id[4:])
            with get_db() as db:
                db.execute("DELETE FROM chat_attachments WHERE id=?", (att_id,))
                db.commit()
            return True
        except Exception:
            return False
    return False
