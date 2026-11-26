# -*- coding: utf-8 -*-
"""
app/kho_catalog.py
==================
Integration for https://anhkysuai.com/kho/ (1,295+ curated AI/Dev GitHub repos).

Provides:
- `search_kho(query, limit=5) -> list[dict]`: fast accent-aware search across repo names,
  Vietnamese descriptions, and keywords.
- `fetch_clean_markdown(url)`: crawl4ai-style HTML-to-Markdown extractor that strips
  scripts, navs, ads, footers, and sidebars.
- `register_routes(app)`: FastAPI endpoints:
  - `GET /api/kho/search`
  - `GET /api/kho/stats`
  - `POST /api/kho/refresh`
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from fastapi import FastAPI, Query

logger = logging.getLogger("kho_catalog")

ROOT_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT_DIR / "data" / "anhkysuai_kho_catalog.json"
KHO_BASE_URL = "https://anhkysuai.com/kho/"

_CATALOG_CACHE: Optional[List[Dict[str, Any]]] = None
_CATALOG_CACHE_KEY: Optional[Tuple[str, float]] = None

_NOISE_TAGS = frozenset({
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "iframe", "svg", "canvas", "button",
})
_NOISE_ATTR_RE = re.compile(
    r"\b(?:ad|ads|advert|advertisement|banner|cookie|consent|navbar|nav-bar|"
    r"sidebar|side-bar|menu|popup|modal|promo|sponsor|social-share|breadcrumb)\b",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    """Normalize Vietnamese/Unicode text to lowercase ASCII-friendly form."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").lower()


def load_catalog(
    catalog_path: Optional[Path] = None,
    force_reload: bool = False,
) -> List[Dict[str, Any]]:
    """Load and cache the anhkysuai.com/kho JSON catalog."""
    global _CATALOG_CACHE, _CATALOG_CACHE_KEY
    target = Path(catalog_path) if catalog_path else CATALOG_PATH
    if not target.is_file():
        logger.warning("Kho catalog not found at %s", target)
        return []

    mtime = target.stat().st_mtime
    cache_key = (str(target.resolve()), mtime)
    if not force_reload and _CATALOG_CACHE is not None and _CATALOG_CACHE_KEY == cache_key:
        return _CATALOG_CACHE

    with target.open("r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else []
    _CATALOG_CACHE = items
    _CATALOG_CACHE_KEY = cache_key
    return items


def search_kho(
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
    catalog_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Search the anhkysuai.com/kho catalog by repo name, Vietnamese description, or keywords.
    Returns up to `limit` matching repo dicts sorted by relevance then stars.
    """
    if limit <= 0:
        return []

    items = load_catalog(catalog_path=catalog_path)
    if category:
        cat_norm = category.strip().lower()
        items = [r for r in items if str(r.get("category", "")).lower() == cat_norm]

    q_raw = (query or "").strip().lower()
    if not q_raw:
        return sorted(items, key=lambda r: int(r.get("stars", 0) or 0), reverse=True)[:limit]

    q_ascii = _strip_accents(q_raw)
    tokens_raw = [t for t in re.split(r"[\s,/]+", q_raw) if len(t) >= 2]
    tokens_ascii = [t for t in re.split(r"[\s,/]+", q_ascii) if len(t) >= 2]
    if not tokens_raw:
        tokens_raw = [q_raw]
        tokens_ascii = [q_ascii]

    scored: List[tuple[float, int, Dict[str, Any]]] = []
    for repo in items:
        name = str(repo.get("name", "")).lower()
        full_name = str(repo.get("full_name", "")).lower()
        desc_vi = str(repo.get("description_vi", "")).lower()
        keywords = str(repo.get("search_keywords", "")).lower()
        cat = str(repo.get("category", "")).lower()

        desc_ascii = _strip_accents(desc_vi)
        kw_ascii = _strip_accents(keywords)

        score = 0.0
        if q_raw == full_name or q_raw == name:
            score += 120.0
        if q_raw in name:
            score += 60.0
        if q_raw in full_name:
            score += 50.0
        if q_raw in desc_vi or (q_ascii and q_ascii in desc_ascii):
            score += 40.0
        if q_raw in keywords or (q_ascii and q_ascii in kw_ascii):
            score += 25.0

        token_hits = 0
        for tok, tok_a in zip(tokens_raw, tokens_ascii):
            hit = False
            if tok in name or tok in full_name:
                score += 22.0
                hit = True
            if tok in desc_vi or (tok_a and tok_a in desc_ascii):
                score += 14.0
                hit = True
            if tok in keywords or (tok_a and tok_a in kw_ascii):
                score += 9.0
                hit = True
            if tok in cat:
                score += 6.0
                hit = True
            if hit:
                token_hits += 1

        if score > 0 and token_hits > 0:
            # Bonus when all query tokens match
            if token_hits == len(tokens_raw):
                score += 20.0
            stars = int(repo.get("stars", 0) or 0)
            scored.append((score, stars, repo))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:limit]]


def get_kho_stats(catalog_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return summary statistics for the local anhkysuai.com/kho catalog."""
    items = load_catalog(catalog_path=catalog_path)
    categories: Dict[str, int] = {}
    for repo in items:
        cat = str(repo.get("category") or "uncategorized")
        categories[cat] = categories.get(cat, 0) + 1

    top_repo = max(items, key=lambda r: int(r.get("stars", 0) or 0), default=None)
    return {
        "source_url": KHO_BASE_URL,
        "catalog_path": str(catalog_path or CATALOG_PATH),
        "total_repos": len(items),
        "categories_count": len(categories),
        "categories": categories,
        "top_repo": top_repo.get("full_name") if top_repo else None,
    }


def html_to_clean_markdown(html_content: str, base_url: str = "") -> str:
    """
    Convert raw HTML into clean Markdown (crawl4ai-style), stripping scripts,
    styles, navigation bars, footers, sidebars, and ad blocks.
    """
    if not html_content or not html_content.strip():
        return ""

    try:
        from lxml import html as lxml_html  # type: ignore

        doc = lxml_html.fromstring(html_content)
        # Remove noise tags
        for el in list(doc.iter()):
            tag = str(el.tag).lower() if isinstance(el.tag, str) else ""
            if tag in _NOISE_TAGS:
                el.drop_tree()
                continue
            attr_blob = f"{el.get('id', '')} {el.get('class', '')} {el.get('role', '')}"
            if attr_blob.strip() and _NOISE_ATTR_RE.search(attr_blob):
                # Avoid dropping root html/body if they happen to have a generic class
                if tag not in ("html", "body", "main", "article"):
                    el.drop_tree()

        root = doc.find(".//main")
        if root is None:
            root = doc.find(".//article")
        if root is None:
            root = doc.find(".//body")
        if root is None:
            root = doc

        lines: List[str] = []

        def _inline_text(node: Any) -> str:
            parts: List[str] = []
            if node.text:
                parts.append(node.text)
            for child in node:
                ctag = str(child.tag).lower() if isinstance(child.tag, str) else ""
                if ctag == "a":
                    label = _inline_text(child).strip()
                    href = (child.get("href") or "").strip()
                    if href and base_url and not href.startswith(("http://", "https://", "mailto:", "#")):
                        href = urljoin(base_url, href)
                    if label and href:
                        parts.append(f"[{label}]({href})")
                    elif label:
                        parts.append(label)
                elif ctag == "code":
                    code_txt = "".join(child.itertext()).strip()
                    if code_txt:
                        parts.append(f"`{code_txt}`")
                elif ctag == "br":
                    parts.append("\n")
                else:
                    parts.append(_inline_text(child))
                if child.tail:
                    parts.append(child.tail)
            return "".join(parts)

        def _walk(node: Any) -> None:
            tag = str(node.tag).lower() if isinstance(node.tag, str) else ""
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(tag[1])
                txt = re.sub(r"\s+", " ", _inline_text(node)).strip()
                if txt:
                    lines.append(f"{'#' * level} {txt}")
                    lines.append("")
                return
            if tag == "pre":
                code_txt = "".join(node.itertext()).strip("\n")
                if code_txt.strip():
                    lines.append("```")
                    lines.append(code_txt)
                    lines.append("```")
                    lines.append("")
                return
            if tag == "li":
                txt = re.sub(r"\s+", " ", _inline_text(node)).strip()
                if txt:
                    lines.append(f"- {txt}")
                return
            if tag in ("p", "blockquote"):
                txt = re.sub(r"\s+", " ", _inline_text(node)).strip()
                if txt:
                    prefix = "> " if tag == "blockquote" else ""
                    lines.append(f"{prefix}{txt}")
                    lines.append("")
                return

            # Container element: recurse into children; capture direct text if leaf-like
            if len(node) == 0:
                txt = re.sub(r"\s+", " ", (node.text or "")).strip()
                if txt:
                    lines.append(txt)
            else:
                for child in node:
                    _walk(child)

        _walk(root)
        md = "\n".join(lines)
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        if md:
            return md
    except Exception as exc:
        logger.debug("lxml markdown extraction fallback triggered: %s", exc)

    # Regex/stdlib fallback
    cleaned = re.sub(r"<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", html_content, flags=re.I | re.S)
    cleaned = re.sub(r"<(h[1-6])[^>]*>(.*?)</\1>", lambda m: f"\n\n{'#' * int(m.group(1)[1])} {re.sub(r'<[^>]+>', '', m.group(2)).strip()}\n\n", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: f"\n- {re.sub(r'<[^>]+>', '', m.group(1)).strip()}", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html_lib.unescape(cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def fetch_clean_markdown(url: str, timeout: float = 15.0) -> str:
    """
    Fetch a web page (e.g., https://anhkysuai.com/kho/ or documentation) and
    return clean Markdown with scripts, navs, and ads removed.
    """
    target_url = (url or "").strip()
    if not target_url:
        raise ValueError("URL must not be empty")

    headers = {
        "User-Agent": "AI-Office-KhoReader/1.0 (+https://anhkysuai.com/kho/)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    html_text = ""
    try:
        import httpx

        resp = httpx.get(target_url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        html_text = resp.text
    except ImportError:
        import urllib.request

        req = urllib.request.Request(target_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_text = resp.read().decode("utf-8", errors="replace")

    return html_to_clean_markdown(html_text, base_url=target_url)


def refresh_catalog(
    catalog_path: Optional[Path] = None,
    fetch_remote: bool = False,
) -> Dict[str, Any]:
    """
    Reload the catalog from disk (and optionally verify remote anhkysuai.com/kho/).
    """
    remote_checked = False
    remote_ok = False
    if fetch_remote:
        remote_checked = True
        try:
            md = fetch_clean_markdown(KHO_BASE_URL, timeout=10.0)
            remote_ok = bool(md)
        except Exception as exc:
            logger.warning("Remote refresh check failed: %s", exc)

    items = load_catalog(catalog_path=catalog_path, force_reload=True)
    return {
        "status": "ok",
        "total_repos": len(items),
        "remote_checked": remote_checked,
        "remote_ok": remote_ok,
        "source_url": KHO_BASE_URL,
    }


def register_routes(app: FastAPI) -> None:
    """Register /api/kho/* endpoints on the FastAPI application."""

    @app.get("/api/kho/search")
    async def api_kho_search(
        q: str = Query("", description="Search query for repos"),
        limit: int = Query(5, ge=1, le=50, description="Max results"),
        category: Optional[str] = Query(None, description="Optional category filter"),
    ) -> Dict[str, Any]:
        results = search_kho(q, limit=limit, category=category)
        return {
            "query": q,
            "count": len(results),
            "results": results,
        }

    @app.get("/api/kho/stats")
    async def api_kho_stats() -> Dict[str, Any]:
        return get_kho_stats()

    @app.post("/api/kho/refresh")
    async def api_kho_refresh(fetch_remote: bool = False) -> Dict[str, Any]:
        return refresh_catalog(fetch_remote=fetch_remote)
