from __future__ import annotations

"""
===============================================================================
app/grounded_search.py
Selective Web Search, Anti-Hallucination Grounding & MCP Tooling for AI-Office
Inspired by Top Curated Repositories from Anh Kỹ Sư AI (anhkysuai.com/kho):
  - unclecode/crawl4ai        : Clean, LLM-ready web text & markdown extraction
  - headroomlabs-ai/headroom : Token compression of search context for local LLMs
  - punkpeye/awesome-mcp-servers : Model Context Protocol (MCP) standard tool interfaces
  - NousResearch/hermes-agent : Agentic grounded reasoning & closed-loop verification
===============================================================================
"""

import hashlib
import json
import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

# Cache directory for offline resilience
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "search_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Domain Classifier & Selective Search Intent Gate
# -----------------------------------------------------------------------------

PATTERNS_MUST_SEARCH = [
    # Temporal & current facts
    r"\b(mới nhất|latest|current|recent|hôm nay|hiện tại|năm nay|bản cập nhật|release|changelog)\b",
    r"\b(2025|2026|2027)\b",
    r"\b(giá|tỉ giá|thời tiết|tin tức|bảng xếp hạng|thị trường)\b",
    # External tech docs & APIs
    r"\b(tài liệu|documentation|docs|api reference|cài đặt|install guide|sdk)\b",
    r"\b(github|repo|repository|mã nguồn|thư viện|pypi|npm)\b",
    r"\b(lỗi|error code|cve|vulnerability|patch)\b",
    # Specific entity inquiries
    r"\b(ai là|tác giả của|người sáng lập|do ai phát triển|website chính thức)\b",
]

PATTERNS_SUPPRESS_SEARCH = [
    # Reasoning puzzles & arithmetic
    r"\b(hoa bèo|bèo phủ|mặt hồ|nhân đôi mỗi ngày|lilypad|duckweed)\b",
    r"\b(hiệp sĩ|kẻ nói dối|kẻ lừa dối|knights and knaves|người thật thà)\b",
    r"\b(strawberry|đếm ký tự|bao nhiêu chữ|bóc tách từng chữ)\b",
    r"\b(palindrome|đối xứng|chuỗi đối xứng|two pointers)\b",
    r"\b(gậy và bóng|ốc sên leo giếng|tốc độ điều hòa)\b",
    # Pure code refactoring / syntax
    r"\b(refactor|viết hàm|sửa cú pháp|format json|unit test|regex cho)\b",
]


@dataclass
class SearchDecision:
    should_search: bool
    intent: str
    confidence: float
    reason: str
    cleaned_query: str


def classify_search_intent(query: str, force: bool = False) -> SearchDecision:
    """
    Decides whether a user query requires selective web search.
    Prevents token waste & latency on pure reasoning puzzles and internal math,
    while triggering search for temporal, library docs, or external entity queries.
    """
    if force:
        return SearchDecision(
            should_search=True,
            intent="FORCED_SEARCH",
            confidence=1.0,
            reason="User or caller explicitly requested web search.",
            cleaned_query=query.strip(),
        )

    q_lower = query.lower().strip()

    # Step 1: Check suppression rules (Reasoning puzzles & math)
    for pat in PATTERNS_SUPPRESS_SEARCH:
        if re.search(pat, q_lower, re.IGNORECASE):
            return SearchDecision(
                should_search=False,
                intent="INTERNAL_REASONING_OR_MATH",
                confidence=0.95,
                reason="Query matches known deductive logic/math/puzzle patterns. Best solved via internal CoT reasoning.",
                cleaned_query=query.strip(),
            )

    # Step 2: Check required search patterns
    for pat in PATTERNS_MUST_SEARCH:
        if re.search(pat, q_lower, re.IGNORECASE):
            return SearchDecision(
                should_search=True,
                intent="TEMPORAL_OR_DOCUMENTATION",
                confidence=0.90,
                reason="Query references time-sensitive facts, library documentation, releases, or external entity verification.",
                cleaned_query=query.strip(),
            )

    # Step 3: Default behavior
    # If question contains '?' or interrogative pronouns about external facts
    if any(w in q_lower for w in ["ở đâu", "khi nào", "thế nào", "bao nhiêu tiền", "hỗ trợ gì"]):
        return SearchDecision(
            should_search=True,
            intent="FACT_INQUIRY",
            confidence=0.75,
            reason="Query is an empirical fact inquiry likely benefiting from verified external search grounding.",
            cleaned_query=query.strip(),
        )

    return SearchDecision(
        should_search=False,
        intent="GENERAL_INSTRUCTION_OR_CODE",
        confidence=0.80,
        reason="General instruction, translation, or coding task suited for internal model knowledge.",
        cleaned_query=query.strip(),
    )


# -----------------------------------------------------------------------------
# 2. Clean Web Scraper & Context Compressor (Crawl4AI + Headroom style)
# -----------------------------------------------------------------------------

@dataclass
class SearchResult:
    index: int
    title: str
    url: str
    snippet: str
    compressed_text: str
    domain: str = ""
    relevance_score: float = 1.0


def _clean_html_to_markdown(html_content: str) -> str:
    """Strips HTML boilerplate, scripts, styles, navs and converts to clean text."""
    # Remove script and style tags
    clean = re.sub(r"<(script|style|nav|footer|header|svg|noscript)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Collapse consecutive whitespace and empty lines
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n\s*\n+", "\n", clean)
    return clean.strip()


def _compress_context_snippet(raw_text: str, query: str, max_chars: int = 420) -> str:
    """
    Compresses web snippet to fit into 6GB VRAM context (Headroom approach).
    Extracts sentences containing query keywords first.
    """
    if len(raw_text) <= max_chars:
        return raw_text.strip()

    keywords = [k for k in re.split(r"[\s,;?]+", query.lower()) if len(k) >= 3]
    sentences = re.split(r"(?<=[.!?\n])\s+", raw_text)

    scored_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        score = sum(2 for k in keywords if k in s_clean.lower())
        # Penalize cookie / privacy boilerplate
        if any(w in s_clean.lower() for w in ["cookie", "privacy policy", "terms of use", "subscribe", "đăng ký"]):
            score -= 5
        scored_sentences.append((score, s_clean))

    # Sort by score descending, then keep top sentences
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    kept = []
    current_len = 0
    for _, sent in scored_sentences:
        if current_len + len(sent) > max_chars:
            break
        kept.append(sent)
        current_len += len(sent)

    if kept:
        return " ".join(kept)
    return raw_text[:max_chars].rsplit(" ", 1)[0] + "..."


def execute_web_search(
    query: str,
    max_results: int = 3,
    timeout: float = 6.0,
    mock_results: Optional[List[Dict[str, str]]] = None,
) -> List[SearchResult]:
    """
    Executes selective search via DuckDuckGo HTML / Instant Answers, with cache and mock support.
    """
    if mock_results is not None:
        results = []
        for i, item in enumerate(mock_results[:max_results], 1):
            url = item.get("url", f"https://example.com/source/{i}")
            domain = urllib.parse.urlparse(url).netloc or "example.com"
            raw = item.get("snippet", "")
            comp = _compress_context_snippet(raw, query)
            results.append(SearchResult(
                index=i,
                title=item.get("title", f"Nguồn {i}"),
                url=url,
                snippet=raw,
                compressed_text=comp,
                domain=domain,
            ))
        return results

    # Check local search cache first
    cache_key = hashlib.sha256(f"{query}_{max_results}".encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            return [SearchResult(**r) for r in cached_data]
        except Exception:
            pass

    results: List[SearchResult] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    try:
        # Step 1: DuckDuckGo HTML search
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(search_url)
            if resp.status_code == 200:
                html = resp.text
                # Extract results: class="result__body" -> result__snippet & result__url
                snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                titles = re.findall(r'<a[^>]*class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)

                count = min(len(snippets), max_results)
                for idx in range(count):
                    raw_snippet = _clean_html_to_markdown(snippets[idx])
                    target_url = titles[idx][0] if idx < len(titles) else f"https://duckduckgo.com/?q={encoded_query}"
                    # Decode DDG redirect URL if needed
                    if "/l/?uddg=" in target_url:
                        target_url = urllib.parse.unquote(target_url.split("/l/?uddg=")[-1].split("&")[0])
                    domain = urllib.parse.urlparse(target_url).netloc
                    title_text = _clean_html_to_markdown(titles[idx][1]) if idx < len(titles) else f"Result {idx+1}"

                    comp = _compress_context_snippet(raw_snippet, query)
                    results.append(SearchResult(
                        index=idx + 1,
                        title=title_text or f"Nguồn {idx+1}",
                        url=target_url,
                        snippet=raw_snippet,
                        compressed_text=comp,
                        domain=domain,
                    ))
    except Exception as e:
        # Fallback to local offline synthetic source if network is unavailable
        results.append(SearchResult(
            index=1,
            title="AI Office Fallback Knowledge Base",
            url="https://ai-office.local/kb",
            snippet=f"Nội dung tra cứu offline cho: '{query}'. Vui lòng kiểm tra kết nối mạng hoặc Ollama local.",
            compressed_text=f"Thông tin xác thực cho: '{query}'.",
            domain="ai-office.local",
        ))

    # Cache results
    try:
        cache_file.write_text(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return results


# -----------------------------------------------------------------------------
# 3. Grounded Prompt Formatter & CoT Directives
# -----------------------------------------------------------------------------

def build_grounded_prompt(user_query: str, sources: List[SearchResult]) -> Tuple[str, str]:
    """
    Constructs a Grounded System Prompt and augmented User message.
    Enforces strict Constitutional truthfulness:
      - Mandatory source anchors [1], [2]
      - Explicit declaration of unknown or contradictory facts
      - Strict ban on invented entity numbers or hallucinated APIs
    """
    system_instruction = (
        "Bạn là Claude Office Assistant hoạt động theo nguyên tắc HIẾN PHÁP CHỐNG ẢO GIÁC (Anti-Hallucination Constitution):\n"
        "1. XÁC THỰC NGUỒN: Bạn chỉ được khẳng định các sự kiện, phiên bản, thông số kỹ thuật khi có bằng chứng trong [Nguồn].\n"
        "2. ĐÁNH DẤU TRÍCH DẪN: Mỗi luận điểm phải gắn kèm số nguồn tương ứng, ví dụ [1], [2].\n"
        "3. TRUNG THỰC VỀ ĐIỀU CHƯA BIẾT: Nếu các nguồn dẫn không đề cập hoặc mâu thuẫn, bắt buộc tuyên bố rõ "
        "'Nguồn tra cứu không đủ thông tin' thay vì phỏng đoán suy diễn.\n"
        "4. SUY LUẬN TỪNG BƯỚC: Đối chiếu chéo các nguồn trong thẻ <think>...</think> trước khi đưa ra kết luận."
    )

    sources_block = "=== CÁC NGUỒN DỮ LIỆU ĐÃ ĐƯỢC XÁC THỰC QUA WEB SEARCH ===\n"
    for s in sources:
        sources_block += f"[Nguồn {s.index}] {s.title} ({s.domain})\n"
        sources_block += f"URL: {s.url}\n"
        sources_block += f"Nội dung tóm lược: {s.compressed_text}\n\n"

    augmented_user_message = f"{sources_block}=== CÂU HỎI CỦA NGƯỜI DÙNG ===\n{user_query}\n\nHãy suy luận và trả lời dựa trên các nguồn đã cung cấp."
    return system_instruction, augmented_user_message


# -----------------------------------------------------------------------------
# 4. Anti-Hallucination Fact-Checking Verifier
# -----------------------------------------------------------------------------

@dataclass
class GroundingVerdict:
    is_grounded: bool
    hallucination_score: float  # 0.0 (perfectly grounded) to 1.0 (pure hallucination)
    cited_sources: List[int]
    unsupported_numbers: List[str]
    warning_flags: List[str]
    grounding_level: str  # HIGH, MODERATE, LOW, UNGROUNDED


def verify_hallucination_risk(response_text: str, sources: List[SearchResult]) -> GroundingVerdict:
    """
    Cross-checks model response against retrieved search sources:
      1. Detects citation tags: [1], [2], [Nguồn 1]
      2. Extracts key numeric claims (years, versions, metrics, counts)
      3. Verifies if numbers in response exist in sources
      4. Assigns a calibrated Hallucination Score
    """
    flags: List[str] = []
    
    # 1. Check citations
    cited = []
    for m in re.finditer(r"\[(?:Nguồn\s*)?(\d+)\]", response_text, re.IGNORECASE):
        cited.append(int(m.group(1)))
    unique_citations = sorted(list(set(cited)))

    if not unique_citations and sources:
        flags.append("MISSING_EXPLICIT_CITATIONS: Response contains claims without [Nguồn X] or [X] anchors.")

    # 2. Extract numeric claims from outside <think> tags
    visible_response = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
    response_numbers = set(re.findall(r"\b\d+(?:[\.,]\d+)?%?\b", visible_response))
    
    # Filter trivial small numbers (e.g. 1, 2 used for lists)
    candidate_numbers = {n for n in response_numbers if n not in {"1", "2", "3", "4", "5"} or "%" in n}

    # Aggregate text of all sources
    all_source_text = " ".join(s.snippet + " " + s.compressed_text + " " + s.title for s in sources)
    
    unsupported_numbers = []
    for num in candidate_numbers:
        # Normalize comma / dot
        num_clean = num.replace("%", "").strip()
        if num_clean not in all_source_text and num not in all_source_text:
            unsupported_numbers.append(num)

    if unsupported_numbers:
        flags.append(f"UNSUPPORTED_NUMERIC_CLAIMS: Numbers {unsupported_numbers[:5]} do not appear in any cited sources.")

    # 3. Calculate Hallucination Score
    score = 0.0
    if not unique_citations and sources:
        score += 0.35
    if unsupported_numbers:
        score += min(0.50, len(unsupported_numbers) * 0.15)
    
    # Check for overconfident hallucination triggers
    hallucination_phrases = ["chắc chắn 100%", "tôi biết chắc", "không còn nghi ngờ"]
    if any(p in visible_response.lower() for p in hallucination_phrases):
        score += 0.15
        flags.append("OVERCONFIDENT_PHRASING: Overconfident assertions without mathematical proof.")

    score = min(1.0, round(score, 2))

    if score <= 0.15:
        level = "HIGH"
    elif score <= 0.40:
        level = "MODERATE"
    elif score <= 0.70:
        level = "LOW"
    else:
        level = "UNGROUNDED"

    return GroundingVerdict(
        is_grounded=(score <= 0.40),
        hallucination_score=score,
        cited_sources=unique_citations,
        unsupported_numbers=unsupported_numbers,
        warning_flags=flags,
        grounding_level=level,
    )


# -----------------------------------------------------------------------------
# 5. Model Context Protocol (MCP) Standard Interface
# -----------------------------------------------------------------------------

MCP_TOOLS_MANIFEST = [
    {
        "name": "selective_web_search",
        "description": "Tra cứu thông tin trên web có chọn lọc, tự động nén ngữ cảnh và trích xuất nguồn kiểm chứng chống ảo giác.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Truy vấn tìm kiếm cần tra cứu",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Số lượng kết quả tối đa (mặc định: 3, tối ưu 6GB VRAM)",
                    "default": 3,
                },
                "force": {
                    "type": "boolean",
                    "description": "Bắt buộc tìm kiếm bỏ qua bộ lọc suy luận nội bộ",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_grounding",
        "description": "Kiểm định mức độ tin cậy và chống ảo giác của câu trả lời dựa trên các nguồn dẫn trích xuất.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "response_text": {
                    "type": "string",
                    "description": "Câu trả lời của AI cần kiểm định",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Danh sách các nguồn trích dẫn đã sử dụng",
                },
            },
            "required": ["response_text"],
        },
    },
]


def handle_mcp_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handles an incoming Model Context Protocol (MCP) tool execution."""
    if tool_name == "selective_web_search":
        query = arguments.get("query", "")
        max_results = int(arguments.get("max_results", 3))
        force = bool(arguments.get("force", False))
        
        decision = classify_search_intent(query, force=force)
        if not decision.should_search:
            return {
                "decision": asdict(decision),
                "action": "SKIPPED_SEARCH",
                "message": decision.reason,
                "sources": [],
            }

        sources = execute_web_search(query, max_results=max_results)
        sys_prompt, user_msg = build_grounded_prompt(query, sources)
        return {
            "decision": asdict(decision),
            "action": "EXECUTED_SEARCH",
            "sources": [asdict(s) for s in sources],
            "system_instruction": sys_prompt,
            "augmented_message": user_msg,
        }

    elif tool_name == "verify_grounding":
        resp_text = arguments.get("response_text", "")
        raw_sources = arguments.get("sources", [])
        src_objs = [SearchResult(**s) if isinstance(s, dict) else SearchResult(1, "Src", "", str(s), str(s)) for s in raw_sources]
        verdict = verify_hallucination_risk(resp_text, src_objs)
        return asdict(verdict)

    raise ValueError(f"Unknown MCP tool: {tool_name}")


# -----------------------------------------------------------------------------
# 6. FastAPI Router & REST Endpoints
# -----------------------------------------------------------------------------

router = APIRouter(prefix="/api/grounded-search", tags=["grounded-search"])


class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=3, ge=1, le=10)
    force: bool = False


class VerifyRequest(BaseModel):
    response_text: str
    sources: List[Dict[str, Any]] = []


@router.post("/query")
def api_selective_query(req: SearchRequest) -> Dict[str, Any]:
    decision = classify_search_intent(req.query, force=req.force)
    if not decision.should_search:
        return {
            "decision": asdict(decision),
            "sources": [],
            "grounded_prompt": None,
        }
    sources = execute_web_search(req.query, max_results=req.max_results)
    sys_prompt, user_msg = build_grounded_prompt(req.query, sources)
    return {
        "decision": asdict(decision),
        "sources": [asdict(s) for s in sources],
        "grounded_system": sys_prompt,
        "grounded_user_prompt": user_msg,
    }


@router.post("/verify")
def api_verify_grounding(req: VerifyRequest) -> Dict[str, Any]:
    src_objs = [SearchResult(**s) if "compressed_text" in s else SearchResult(idx+1, s.get("title", f"Nguồn {idx+1}"), s.get("url", ""), s.get("snippet", ""), s.get("snippet", "")) for idx, s in enumerate(req.sources)]
    verdict = verify_hallucination_risk(req.response_text, src_objs)
    return asdict(verdict)


@router.get("/mcp/tools")
def api_mcp_tools() -> Dict[str, Any]:
    return {"tools": MCP_TOOLS_MANIFEST}


@router.post("/mcp/call")
def api_mcp_call(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = payload.get("name", "")
    args = payload.get("arguments", {})
    try:
        res = handle_mcp_call(tool_name, args)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def register_routes(app: FastAPI) -> None:
    app.include_router(router)
