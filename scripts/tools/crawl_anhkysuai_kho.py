#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl & Analyze Anh Kỹ Sư AI Repository Catalog (https://anhkysuai.com/kho/)
=============================================================================
Extracts all curated repositories, parses metadata (stars, license, description, tags),
categorizes them for AI Office integration (MCP, Search/Scraping, Local LLM, Agents),
and exports structured JSON / JSONL catalogs.
"""

import os
import re
import sys
import json
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional

SOURCE_URL = "https://anhkysuai.com/kho/"
CACHE_DIR = Path("data/cache")
OUTPUT_JSON = Path("data/anhkysuai_kho_catalog.json")
OUTPUT_JSONL = Path("data/anhkysuai_kho_catalog.jsonl")


def fetch_html(url: str = SOURCE_URL) -> str:
    """Fetches HTML with caching support."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "anhkysuai_kho.html"

    if cache_file.exists() and cache_file.stat().st_size > 100_000:
        print(f"[*] Reading cached HTML from: {cache_file} ({cache_file.stat().st_size / 1024:.1f} KB)")
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    print(f"[*] Fetching HTML from {url}...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Office/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8", errors="ignore")

    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Cached HTML to {cache_file} ({len(content) / 1024:.1f} KB)")
    return content


def parse_star_count(star_str: str) -> int:
    """Parses Vietnamese formatted star strings, e.g., '★ 50.500' -> 50500 or '★ 1.2k' -> 1200."""
    cleaned = star_str.replace("★", "").strip().lower()
    if not cleaned:
        return 0
    try:
        if "k" in cleaned:
            val = float(cleaned.replace("k", "").strip())
            return int(val * 1000)
        # Vietnamese format often uses dots as thousands separators: 50.500 -> 50500
        if "." in cleaned and len(cleaned.split(".")[-1]) == 3:
            return int(cleaned.replace(".", ""))
        return int(cleaned)
    except Exception:
        # Fallback numeric extraction
        digits = re.sub(r"[^\d]", "", cleaned)
        return int(digits) if digits else 0


def categorize_repo(full_name: str, desc: str, search_text: str) -> str:
    """Classifies a repo into key architectural pillars for AI Office."""
    text = f"{full_name} {desc} {search_text}".lower()

    if any(k in text for k in ["mcp", "model context protocol", "modelcontextprotocol"]):
        return "mcp_servers_and_protocol"

    if any(k in text for k in [
        "crawl4ai", "firecrawl", "searxng", "spider", "scraper", "crawling",
        "web search", "search engine", "tavily", "serp", "anti-hallucination",
        "fact check", "grounding", "web extraction", "headless browser"
    ]):
        return "selective_search_and_anti_hallucination"

    if any(k in text for k in [
        "ollama", "vllm", "llama.cpp", "localai", "lm studio", "unsloth",
        "open-webui", "text-generation-webui", "quantiz", "gguf", "qlora",
        "exllamav2", "tgi", "sglang"
    ]):
        return "local_llm_and_inference"

    if any(k in text for k in [
        "rag", "vector", "embedding", "chroma", "qdrant", "milvus", "lancedb",
        "ragflow", "fastgpt", "knowledge base", "hybrid search", "bm25", "rerank"
    ]):
        return "knowledge_rag_and_vector"

    if any(k in text for k in [
        "agent", "autogen", "crewai", "dify", "flowise", "langchain", "langgraph",
        "browser-use", "open-interpreter", "chatdev", "metagpt", "multi-agent",
        "swarm", "autonomous"
    ]):
        return "ai_agents_and_orchestration"

    if any(k in text for k in [
        "comfyui", "stable-diffusion", "flux", "whisper", "tts", "voice",
        "audio", "video", "motion comic", "manga", "anime", "vision", "ocr"
    ]):
        return "multimodal_and_creative"

    return "developer_tools_and_frameworks"


def extract_cards(html: str) -> List[Dict[str, Any]]:
    """Extracts all repository cards from HTML."""
    pattern = re.compile(
        r'<a class=["\']the-kho["\'][^>]*href=["\']([^"\']+)["\'][^>]*data-tim=["\']([^"\']*)["\'][^>]*>'
        r'.*?<span class=["\']tk-chu["\'][^>]*>([^<]*)</span>'
        r'<strong[^>]*>([^<]*)</strong>'
        r'.*?<p class=["\']tk-mo["\'][^>]*>(.*?)</p>'
        r'.*?<div class=["\']tk-so["\'][^>]*>(.*?)</div>',
        re.DOTALL
    )

    matches = pattern.findall(html)
    items: List[Dict[str, Any]] = []

    for href, data_tim, owner_raw, name_raw, desc_raw, stats_raw in matches:
        owner = owner_raw.strip().rstrip("/")
        name = name_raw.strip()
        full_name = f"{owner}/{name}" if owner else name
        github_url = f"https://github.com/{full_name}"
        desc = re.sub(r"\s+", " ", desc_raw).strip()

        # Extract stats inside tk-so (stars, license, update)
        stat_spans = re.findall(r'<span[^>]*>(.*?)</span>', stats_raw)
        star_str = ""
        license_str = ""
        updated_str = ""

        for span in stat_spans:
            s_clean = span.strip()
            if "★" in s_clean:
                star_str = s_clean
            elif "Cập nhật" in s_clean:
                updated_str = s_clean
            else:
                license_str = s_clean

        stars = parse_star_count(star_str)
        category = categorize_repo(full_name, desc, data_tim)

        items.append({
            "owner": owner,
            "name": name,
            "full_name": full_name,
            "github_url": github_url,
            "anhkysuai_url": f"https://anhkysuai.com{href}",
            "description_vi": desc,
            "search_keywords": data_tim.strip(),
            "stars_str": star_str,
            "stars": stars,
            "license": license_str,
            "updated_at": updated_str,
            "category": category
        })

    # Sort descending by stars
    items.sort(key=lambda x: x["stars"], reverse=True)
    return items


def main():
    html = fetch_html()
    repos = extract_cards(html)
    print(f"[+] Total repositories extracted: {len(repos)}")

    # Category counts
    cat_counts: Dict[str, int] = {}
    for r in repos:
        c = r["category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    print("\n" + "=" * 65)
    print("REPOSITORIES BREAKDOWN BY CATEGORY")
    print("=" * 65)
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  - {cat:45s}: {count:4d} repos")
    print("=" * 65)

    # Save to JSON & JSONL
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(repos, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for r in repos:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[+] Exported JSON catalog to:  {OUTPUT_JSON} ({OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")
    print(f"[+] Exported JSONL catalog to: {OUTPUT_JSONL} ({OUTPUT_JSONL.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
