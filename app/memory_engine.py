"""AI Office - Long-Term & Self-Learning Memory Engine.

Stores and recalls user preferences, corrections, facts, web knowledge, and character styles
using SQLite WAL in DATA_DIR / "office.db".
Lightweight design tailored for small local LLMs (e.g. Qwen 4B) with compact memory context blocks (< 500 chars).
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from app.config import DATA_DIR
except ImportError:
    from config import DATA_DIR

logger = logging.getLogger("memory_engine")

VALID_CATEGORIES = {
    "preference",
    "fact",
    "correction",
    "web_knowledge",
    "character_style",
    "golden_template",
    "qa_feedback",
}

# Stopwords to filter out when generating search keywords
STOPWORDS = {
    "là", "và", "của", "cho", "thì", "có", "rằng", "được", "với", "trong",
    "các", "những", "một", "này", "đó", "khi", "để", "như", "nào", "gì",
    "anh", "em", "tôi", "mình", "bạn", "giúp", "hãy", "nhớ", "nhé",
    "the", "a", "an", "is", "are", "and", "or", "to", "in", "of", "for",
}


def get_db_path() -> Path:
    """Get the target SQLite database path."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "office.db"


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Create a SQLite connection with WAL journal mode enabled."""
    target = Path(db_path) if db_path else get_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_memory_db(db_path: Optional[Path | str] = None) -> None:
    """Initialize the learned_memories table, migrations, and indexes."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'chat',
                    importance INTEGER NOT NULL DEFAULT 3,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            # Safe migration for existing databases lacking QA/Golden Template columns
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(learned_memories)").fetchall()
            }
            if "success_count" not in existing_cols:
                conn.execute(
                    "ALTER TABLE learned_memories ADD COLUMN success_count INTEGER NOT NULL DEFAULT 0;"
                )
            if "fail_count" not in existing_cols:
                conn.execute(
                    "ALTER TABLE learned_memories ADD COLUMN fail_count INTEGER NOT NULL DEFAULT 0;"
                )
            if "metadata_json" not in existing_cols:
                conn.execute(
                    "ALTER TABLE learned_memories ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';"
                )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learned_memories_cat ON learned_memories(category);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learned_memories_imp ON learned_memories(importance);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learned_memories_upd ON learned_memories(updated_at);"
            )
    finally:
        conn.close()


def extract_keywords(text: str, max_words: int = 10) -> str:
    """Extract significant keywords from text for matching."""
    tokens = re.findall(r"[\w\d]+", text.lower())
    filtered = [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]
    # Preserve order while deduplicating
    seen = set()
    result = []
    for t in filtered:
        if t not in seen:
            seen.add(t)
            result.append(t)
        if len(result) >= max_words:
            break
    return " ".join(result)


def normalize_content(text: str) -> str:
    """Normalize text content for duplicate detection."""
    return re.sub(r"\s+", " ", text.strip().lower())


def learn_fact(
    content: str,
    category: str = "fact",
    source: str = "chat",
    importance: int = 3,
    keywords: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Save or update a learned memory with auto-deduplication.

    Args:
        content: The factual content or instruction to remember.
        category: One of ('preference', 'fact', 'correction', 'web_knowledge', 'character_style').
        source: Origin of memory ('chat', 'web_search', 'manual', etc.).
        importance: Integer priority from 1 to 5.
        keywords: Optional custom keywords.
        db_path: Optional custom db path (used for tests).

    Returns:
        Dict representing the saved memory record, or None if content is empty.
    """
    cleaned_content = content.strip()
    if not cleaned_content:
        return None

    init_memory_db(db_path)

    if category not in VALID_CATEGORIES:
        category = "fact"

    importance = max(1, min(5, int(importance)))
    kw_str = (keywords or "").strip() or extract_keywords(cleaned_content)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    norm_content = normalize_content(cleaned_content)

    conn = get_connection(db_path)
    try:
        with conn:
            # Check for existing memory with identical or near-identical content
            cur = conn.cursor()
            cur.execute(
                "SELECT id, category, content, keywords, source, importance, created_at, updated_at "
                "FROM learned_memories WHERE category = ?",
                (category,),
            )
            rows = cur.fetchall()

            matched_id = None
            for row in rows:
                if normalize_content(row["content"]) == norm_content:
                    matched_id = row["id"]
                    break

            if matched_id is not None:
                # Update existing record
                new_importance = max(row["importance"], importance)
                combined_kw = list(
                    dict.fromkeys(
                        (row["keywords"] + " " + kw_str).strip().split()
                    )
                )
                final_kw = " ".join(combined_kw[:12])
                conn.execute(
                    """
                    UPDATE learned_memories
                    SET content = ?,
                        keywords = ?,
                        source = ?,
                        importance = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (cleaned_content, final_kw, source, new_importance, now_iso, matched_id),
                )
                cur.execute("SELECT * FROM learned_memories WHERE id = ?", (matched_id,))
                updated_row = cur.fetchone()
                return dict(updated_row)
            else:
                # Insert new record
                cur.execute(
                    """
                    INSERT INTO learned_memories (category, content, keywords, source, importance, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (category, cleaned_content, kw_str, source, importance, now_iso, now_iso),
                )
                new_id = cur.lastrowid
                cur.execute("SELECT * FROM learned_memories WHERE id = ?", (new_id,))
                new_row = cur.fetchone()
                return dict(new_row)
    finally:
        conn.close()


def detect_and_learn_from_turn(
    user_msg: str,
    assistant_msg: str = "",
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Automatically extract facts, preferences, corrections, or web knowledge from a chat turn.

    Looks for trigger phrases such as:
      - "nhớ giúp anh", "ghi nhớ giúp", "học ghi nhớ", "nhớ nhé"
      - "từ nay", "sau này đừng", "đừng bao giờ", "không được"
      - "anh thích", "tôi thích", "mình thích"
      - Grounded web search summaries in assistant turn.
    """
    learned: List[Dict[str, Any]] = []
    if not user_msg and not assistant_msg:
        return learned

    user_text = user_msg.strip()
    user_lower = user_text.lower()

    # 1. User preferences ("anh thích...", "tôi thích...", "mình thích...")
    pref_patterns = [
        r"(?:anh|tôi|em|mình)\s+thích\s+([^.!?\n,]+(?:\s+[^.!?\n,]+)*)",
        r"(?:sở thích của (?:anh|tôi|em|mình) là)\s+([^.!?\n]+)",
    ]
    for pattern in pref_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            detail = match.group(1).strip()
            if len(detail) > 2:
                fact_text = f"Người dùng thích: {detail}"
                saved = learn_fact(
                    content=fact_text,
                    category="preference",
                    source="chat",
                    importance=4,
                    db_path=db_path,
                )
                if saved:
                    learned.append(saved)
                break

    # 2. User dislikes / negative preferences
    dislike_patterns = [
        r"(?:anh|tôi|em|mình)\s+(?:không thích|ghét)\s+([^.!?\n,]+(?:\s+[^.!?\n,]+)*)",
    ]
    for pattern in dislike_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            detail = match.group(1).strip()
            if len(detail) > 2:
                fact_text = f"Người dùng không thích: {detail}"
                saved = learn_fact(
                    content=fact_text,
                    category="preference",
                    source="chat",
                    importance=4,
                    db_path=db_path,
                )
                if saved:
                    learned.append(saved)
                break

    # 3. Corrections / Operational Rules ("từ nay đừng...", "sau này đừng...", "không được...")
    correction_patterns = [
        r"(?:từ nay|từ giờ|sau này)\s+(?:đừng|không được|hãy|luôn)\s+([^.!?\n]+)",
        r"(?:đừng bao giờ|không bao giờ được)\s+([^.!?\n]+)",
        r"(?:sửa lại|chú ý):\s*([^.!?\n]+)",
    ]
    for pattern in correction_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            rule_text = match.group(0).strip()
            saved = learn_fact(
                content=rule_text,
                category="correction",
                source="chat",
                importance=5,
                db_path=db_path,
            )
            if saved:
                learned.append(saved)
            break

    # 4. Explicit memory requests ("nhớ giúp anh...", "ghi nhớ giúp...", "học ghi nhớ...")
    explicit_remember_patterns = [
        r"(?:nhớ giúp (?:anh|em|tôi)|ghi nhớ giúp|hãy ghi nhớ|học ghi nhớ|nhớ nhé|nhớ rằng|hãy nhớ)\s*(?:rằng|là)?\s*[:,-]?\s*([^.!?\n]+)",
    ]
    for pattern in explicit_remember_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            memory_detail = match.group(1).strip()
            if len(memory_detail) > 3:
                saved = learn_fact(
                    content=memory_detail,
                    category="fact",
                    source="chat",
                    importance=4,
                    db_path=db_path,
                )
                if saved:
                    learned.append(saved)
                break

    # 5. Character Style / Manga / Visual attributes
    character_style_patterns = [
        r"(?:phong cách|style|vóc dáng|tạo hình|ngoại hình)\s*(?:của nhân vật|nhân vật)?\s*(?:là|:)\s*([^.!?\n]+)",
    ]
    for pattern in character_style_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            char_detail = match.group(1).strip()
            if len(char_detail) > 3:
                saved = learn_fact(
                    content=f"Tạo hình/phong cách: {char_detail}",
                    category="character_style",
                    source="chat",
                    importance=4,
                    db_path=db_path,
                )
                if saved:
                    learned.append(saved)
                break

    # 6. Web knowledge detection from assistant response (grounded search markers)
    if assistant_msg:
        web_markers = ["[Nguồn tra cứu", "[Nguồn:", "🔍 Tìm kiếm", "[Kết quả tra cứu]", "Grounding:"]
        has_web_grounding = any(m in assistant_msg for m in web_markers)
        if has_web_grounding:
            lines = [line.strip() for line in assistant_msg.splitlines() if line.strip()]
            summary_candidates = []
            for line in lines:
                if any(m in line for m in web_markers):
                    continue
                if line.startswith(("-", "*", "•")):
                    summary_candidates.append(line.lstrip("-*• ").strip())
                elif len(line) > 20 and not summary_candidates:
                    summary_candidates.append(line)
                if len(summary_candidates) >= 2:
                    break

            if summary_candidates:
                combined_knowledge = "; ".join(summary_candidates)
                if len(combined_knowledge) > 200:
                    combined_knowledge = combined_knowledge[:200] + "..."
                saved = learn_fact(
                    content=combined_knowledge,
                    category="web_knowledge",
                    source="web_search",
                    importance=3,
                    db_path=db_path,
                )
                if saved:
                    learned.append(saved)

    return learned


def save_golden_template(
    task_key: str,
    template_content: str,
    keywords: Optional[str] = None,
    source: str = "auto_qa",
    importance: int = 5,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Store or reinforce a reusable high-priority Golden Template (workflow/prompt/fix).

    Deduplicates by normalized content within 'golden_template', increments success_count,
    and merges metadata/keywords so proven patterns rank highest in recall.
    """
    cleaned_key = (task_key or "").strip()
    cleaned_body = (template_content or "").strip()
    if not cleaned_body:
        return None

    formatted_content = (
        cleaned_body
        if cleaned_body.lower().startswith("[golden template")
        else (f"[Golden Template: {cleaned_key}] {cleaned_body}" if cleaned_key else f"[Golden Template] {cleaned_body}")
    )

    extra_kw = " ".join(
        filter(None, [extract_keywords(cleaned_key), (keywords or "").strip(), extract_keywords(cleaned_body)])
    )
    saved = learn_fact(
        content=formatted_content,
        category="golden_template",
        source=source,
        importance=max(4, min(5, int(importance))),
        keywords=extra_kw or None,
        db_path=db_path,
    )
    if not saved:
        return None

    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE learned_memories
                SET success_count = success_count + 1,
                    metadata_json = CASE WHEN ? != '{}' THEN ? ELSE metadata_json END,
                    updated_at = ?
                WHERE id = ?
                """,
                (meta_json, meta_json, now_iso, saved["id"]),
            )
            cur = conn.execute("SELECT * FROM learned_memories WHERE id = ?", (saved["id"],))
            row = cur.fetchone()
            return dict(row) if row else saved
    finally:
        conn.close()


def record_qa_feedback(
    task_key: str,
    success: bool,
    details: str = "",
    template_content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Record Auto-QA pass/fail feedback into memory_engine.

    - On pass: promotes/reinforces `template_content` as a Golden Template (or logs QA pass).
    - On fail: logs diagnostic `qa_feedback` with incremented `fail_count` and demotes any
      matching Golden Template whose failures exceed successes.
    """
    cleaned_key = (task_key or "task").strip()
    cleaned_details = (details or "").strip()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if success:
        if template_content and template_content.strip():
            merged_meta = dict(metadata or {})
            if cleaned_details:
                merged_meta.setdefault("qa_note", cleaned_details)
            return save_golden_template(
                task_key=cleaned_key,
                template_content=template_content,
                source="auto_qa",
                importance=5,
                metadata=merged_meta,
                db_path=db_path,
            )

        msg = f"[QA Pass: {cleaned_key}] {cleaned_details or 'Output verified successfully'}"
        saved = learn_fact(
            content=msg,
            category="qa_feedback",
            source="auto_qa",
            importance=3,
            keywords=extract_keywords(f"{cleaned_key} {cleaned_details}"),
            db_path=db_path,
        )
        if not saved:
            return None
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE learned_memories SET success_count = success_count + 1, updated_at = ? WHERE id = ?",
                    (now_iso, saved["id"]),
                )
                row = conn.execute("SELECT * FROM learned_memories WHERE id = ?", (saved["id"],)).fetchone()
                return dict(row) if row else saved
        finally:
            conn.close()

    # Failure path: record qa_feedback and demote matching unreliable golden_template if any
    fail_msg = f"[QA Fail: {cleaned_key}] {cleaned_details or 'Verification failed'}"
    saved_fail = learn_fact(
        content=fail_msg,
        category="qa_feedback",
        source="auto_qa",
        importance=4,
        keywords=extract_keywords(f"{cleaned_key} {cleaned_details}"),
        db_path=db_path,
    )
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    conn = get_connection(db_path)
    try:
        with conn:
            if saved_fail:
                conn.execute(
                    """
                    UPDATE learned_memories
                    SET fail_count = fail_count + 1,
                        metadata_json = CASE WHEN ? != '{}' THEN ? ELSE metadata_json END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (meta_json, meta_json, now_iso, saved_fail["id"]),
                )
            if template_content and template_content.strip():
                norm_body = normalize_content(template_content)
                rows = conn.execute(
                    "SELECT id, content, importance, success_count, fail_count FROM learned_memories WHERE category = 'golden_template'"
                ).fetchall()
                for row in rows:
                    if norm_body in normalize_content(row["content"]):
                        new_fails = int(row["fail_count"]) + 1
                        new_imp = row["importance"]
                        if new_fails > int(row["success_count"]):
                            new_imp = max(2, int(row["importance"]) - 1)
                        conn.execute(
                            "UPDATE learned_memories SET fail_count = ?, importance = ?, updated_at = ? WHERE id = ?",
                            (new_fails, new_imp, now_iso, row["id"]),
                        )
            if saved_fail:
                row = conn.execute("SELECT * FROM learned_memories WHERE id = ?", (saved_fail["id"],)).fetchone()
                return dict(row) if row else saved_fail
    finally:
        conn.close()
    return None


def recall_golden_templates(
    query: str = "",
    limit: int = 3,
    min_net_score: int = -1,
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-performing Golden Templates matching `query`, ordered by reliability and score."""
    candidates = recall_relevant_memories(
        query=query,
        limit=max(1, limit * 3),
        category="golden_template",
        db_path=db_path,
    )
    reliable = [
        item for item in candidates
        if (int(item.get("success_count", 0)) - int(item.get("fail_count", 0))) >= min_net_score
    ]
    reliable.sort(
        key=lambda item: (
            int(item.get("success_count", 0)) - int(item.get("fail_count", 0)),
            int(item.get("importance", 3)),
            item.get("updated_at", ""),
        ),
        reverse=True,
    )
    return reliable[:max(1, limit)]


def recall_relevant_memories(
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve memories most relevant to the query based on keyword overlap and importance.

    Args:
        query: User input query or topic.
        limit: Max number of memories to return (default 5).
        category: Optional category filter.
        db_path: Optional custom db path.

    Returns:
        List of memory dicts ordered by relevance and importance.
    """
    init_memory_db(db_path)
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if category and category in VALID_CATEGORIES:
            cur.execute(
                "SELECT id, category, content, keywords, source, importance, success_count, fail_count, metadata_json, created_at, updated_at "
                "FROM learned_memories WHERE category = ?",
                (category,),
            )
        else:
            cur.execute(
                "SELECT id, category, content, keywords, source, importance, success_count, fail_count, metadata_json, created_at, updated_at "
                "FROM learned_memories"
            )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    if not rows:
        return []

    q_clean = query.strip().lower()
    q_tokens = [t for t in re.findall(r"[\w\d]+", q_clean) if len(t) >= 2 and t not in STOPWORDS]

    # If no significant query tokens (e.g. wildcard or generic query), return by importance and recency
    if not q_tokens:
        rows.sort(key=lambda x: (x["importance"], x["updated_at"]), reverse=True)
        return rows[:limit]

    scored: List[tuple[float, Dict[str, Any]]] = []
    for r in rows:
        content_lower = r["content"].lower()
        kw_lower = r.get("keywords", "").lower()
        score = 0.0

        # Exact phrase bonus
        if q_clean in content_lower:
            score += 15.0

        # Token overlap in content and keywords
        matched_tokens = 0
        for token in q_tokens:
            if token in content_lower:
                matched_tokens += 1
                score += 5.0
            elif token in kw_lower:
                matched_tokens += 1
                score += 3.0

        # Category relevance
        if r["category"] == "golden_template":
            net_success = int(r.get("success_count", 0)) - int(r.get("fail_count", 0))
            score += 8.0 + max(-6.0, min(6.0, float(net_success) * 1.5))
        elif r["category"] == "correction":
            score += 2.0  # Corrections and rules have slight priority

        # Importance multiplier
        score += float(r.get("importance", 3)) * 1.5

        # Only include if there is at least one keyword match or exact match
        if matched_tokens > 0 or q_clean in content_lower:
            scored.append((score, r))

    # Sort descending by score, then importance, then updated_at
    scored.sort(
        key=lambda item: (item[0], item[1]["importance"], item[1]["updated_at"]),
        reverse=True,
    )
    return [item[1] for item in scored[:limit]]


def build_memory_context_block(
    query: str,
    limit: int = 5,
    db_path: Optional[Path | str] = None,
) -> str:
    """Format recalled memories into a compact text block (< 500 chars) for system prompt.

    Ensures that small models (e.g. Qwen 4B) are informed of crucial user preferences
    and facts without bloating the prompt context.
    """
    memories = recall_relevant_memories(query=query, limit=limit, db_path=db_path)
    if not memories:
        return ""

    category_labels = {
        "preference": "Sở thích",
        "fact": "Thông tin",
        "correction": "Lưu ý",
        "web_knowledge": "Kiến thức",
        "character_style": "Tạo hình",
        "golden_template": "Mẫu chuẩn",
        "qa_feedback": "QA",
    }

    header = "[Ký ức & Sở thích người dùng]:"
    lines = [header]
    total_len = len(header) + 1

    for m in memories:
        cat_label = category_labels.get(m.get("category", ""), "Ghi nhớ")
        content = m.get("content", "").strip()
        line = f"- [{cat_label}] {content}"

        # Guard against exceeding 500 characters limit
        if total_len + len(line) + 1 > 480:
            remaining = 475 - total_len
            if remaining > 20:
                truncated_line = f"- [{cat_label}] {content[:remaining]}..."
                lines.append(truncated_line)
            break

        lines.append(line)
        total_len += len(line) + 1

    res = "\n".join(lines).strip()
    return res if len(res) <= 500 else res[:497] + "..."


def list_memories(
    category: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """List all stored memories, optionally filtered by category."""
    init_memory_db(db_path)
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if category and category in VALID_CATEGORIES:
            cur.execute(
                "SELECT * FROM learned_memories WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (category, max(1, limit)),
            )
        else:
            cur.execute(
                "SELECT * FROM learned_memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (max(1, limit),),
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_memory(item_id: int | str, db_path: Optional[Path | str] = None) -> bool:
    """Delete a memory record by ID. Returns True if deleted, False if not found."""
    init_memory_db(db_path)
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM learned_memories WHERE id = ?", (item_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FastAPI Router and Routes Registration
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/memory", tags=["Memory Engine"])


class MemoryLearnRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Content to learn/remember")
    category: str = Field(default="fact", description="Category of memory")
    source: str = Field(default="chat", description="Origin of memory")
    importance: int = Field(default=3, ge=1, le=5, description="Importance level 1-5")
    keywords: Optional[str] = Field(default=None, description="Optional custom keywords")


@router.get("")
def get_memories(
    category: Optional[str] = Query(None, description="Filter by category"),
    query: Optional[str] = Query(None, description="Search term for semantic recall"),
    limit: int = Query(50, ge=1, le=200, description="Max memories to return"),
):
    """Retrieve memories, supporting optional keyword search or category filter."""
    if query and query.strip():
        items = recall_relevant_memories(query=query.strip(), limit=limit, category=category)
    else:
        items = list_memories(category=category, limit=limit)
    return {"status": "success", "memories": items, "count": len(items)}


@router.post("/learn")
def api_learn_fact(req: MemoryLearnRequest):
    """Learn a new fact, rule, or preference."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty.")

    saved = learn_fact(
        content=req.content,
        category=req.category,
        source=req.source,
        importance=req.importance,
        keywords=req.keywords,
    )
    if not saved:
        raise HTTPException(status_code=400, detail="Failed to save memory item.")
    return {"status": "success", "memory": saved}


@router.delete("/{item_id}")
def api_delete_memory(item_id: int):
    """Delete a memory by its ID."""
    deleted = delete_memory(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return {"status": "success", "deleted_id": item_id}


class GoldenTemplateRequest(BaseModel):
    task_key: str = Field(..., min_length=1, description="Task or workflow key")
    template_content: str = Field(..., min_length=1, description="Reusable prompt, workflow, or fix")
    keywords: Optional[str] = Field(default=None, description="Optional custom keywords")
    source: str = Field(default="manual", description="Origin of template")
    importance: int = Field(default=5, ge=1, le=5, description="Importance level 1-5")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured parameters")


@router.get("/templates")
def get_golden_templates(
    query: str = Query("", description="Optional search term"),
    limit: int = Query(5, ge=1, le=50, description="Max templates to return"),
):
    """Retrieve high-priority Golden Templates."""
    items = recall_golden_templates(query=query.strip(), limit=limit)
    return {"status": "success", "templates": items, "count": len(items)}


@router.post("/templates")
def api_save_golden_template(req: GoldenTemplateRequest):
    """Save or reinforce a Golden Template."""
    saved = save_golden_template(
        task_key=req.task_key,
        template_content=req.template_content,
        keywords=req.keywords,
        source=req.source,
        importance=req.importance,
        metadata=req.metadata,
    )
    if not saved:
        raise HTTPException(status_code=400, detail="Failed to save golden template.")
    return {"status": "success", "template": saved}


def register_routes(app: FastAPI) -> None:
    """Register memory engine routes to main FastAPI application."""
    app.include_router(router)
