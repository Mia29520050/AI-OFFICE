#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inspect Catalog Recommendations for AI Office
=============================================
Filters and ranks the most impactful repos from anhkysuai.com/kho for:
1. Selective Web Search & Anti-Hallucination
2. Model Context Protocol (MCP) Integration
3. Local LLM & Reasoning Engines
4. Autonomous Agent Tooling & Browser Execution
"""

import json
from pathlib import Path

CATALOG_PATH = Path("data/anhkysuai_kho_catalog.json")

def main():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        repos = json.load(f)

    print(f"Total repos loaded: {len(repos)}\n")

    targets = [
        ("selective_search_and_anti_hallucination", "1. SELECTIVE WEB SEARCH & ANTI-HALLUCINATION"),
        ("mcp_servers_and_protocol", "2. MODEL CONTEXT PROTOCOL (MCP) SERVERS & PROTOCOL"),
        ("local_llm_and_inference", "3. LOCAL LLM & INFERENCE RUNTIMES"),
        ("knowledge_rag_and_vector", "4. KNOWLEDGE RAG & VECTOR RETRIEVAL"),
        ("ai_agents_and_orchestration", "5. AGENT ORCHESTRATION & BROWSER AUTOMATION")
    ]

    for cat_key, cat_title in targets:
        matched = [r for r in repos if r["category"] == cat_key]
        print("=" * 75)
        print(f"{cat_title} ({len(matched)} repos)")
        print("=" * 75)
        for i, r in enumerate(matched[:15], 1):
            name = r["full_name"]
            stars = r["stars_str"] or f"★ {r['stars']}"
            desc = r["description_vi"]
            print(f"{i:2d}. {name:38s} | {stars:10s}")
            print(f"    Mô tả: {desc}")
            print(f"    GitHub: {r['github_url']}")
            print()

if __name__ == "__main__":
    main()


def inspect_mcp_and_search_specifics():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        repos = json.load(f)

    print("\n" + "=" * 75)
    print("TOP REPOS FOR SELECTIVE SEARCH, MCP & ANTI-HALLUCINATION")
    print("=" * 75)
    
    specific_keywords = ["crawl4ai", "firecrawl", "searxng", "langextract", "mcp", "browser-use", "tavily", "rerank", "grounding"]
    seen = set()
    selected = []

    for r in repos:
        full_text = f"{r['full_name']} {r['description_vi']} {r['search_keywords']}".lower()
        for kw in specific_keywords:
            if kw in full_text and r['full_name'] not in seen:
                seen.add(r['full_name'])
                selected.append((kw, r))
                break

    selected.sort(key=lambda x: x[1]['stars'], reverse=True)
    for kw, r in selected[:25]:
        print(f"[{kw.upper():12s}] {r['full_name']:35s} | {r['stars_str']:10s}")
        print(f"  Mô tả: {r['description_vi']}")
        print(f"  Link:  {r['github_url']}")
        print()

if __name__ == "__main__":
    inspect_mcp_and_search_specifics()
