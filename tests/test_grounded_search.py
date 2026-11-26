from __future__ import annotations

from unittest.mock import patch

from app.grounded_search import (
    SearchResult,
    _clean_html_to_markdown,
    _compress_context_snippet,
    build_grounded_prompt,
    classify_search_intent,
    execute_web_search,
    handle_mcp_call,
    verify_hallucination_risk,
)


def test_classify_search_intent_suppression():
    # Pure reasoning, math puzzles and code refactoring should NOT search web
    puzzles = [
        "Nếu 1 cụm hoa bèo nhân đôi mỗi ngày phủ kín hồ trong 30 ngày...",
        "Có 4 cụm duckweed nở gấp đôi diện tích mặt hồ...",
        "Trên đảo có 2 người: Hiệp sĩ luôn nói thật và Kẻ nói dối...",
        "Đếm xem trong từ strawberry có bao nhiêu chữ r",
        "Kiểm tra xem chuỗi racecar có phải là palindrome không bằng two pointers",
        "Refactor hàm tính diện tích hình thang bằng python",
    ]
    for p in puzzles:
        decision = classify_search_intent(p)
        assert decision.should_search is False, f"Failed suppression for query: {p}"
        assert decision.confidence >= 0.80


def test_classify_search_intent_trigger():
    # Temporal, documentation, and external library questions MUST search web
    triggers = [
        "Phiên bản mới nhất của Crawl4AI năm 2026 hỗ trợ tính năng gì?",
        "Tài liệu hướng dẫn cài đặt Model Context Protocol MCP python sdk",
        "Changelog release notes của Ollama hôm nay",
        "Ai là tác giả của repo FastMCP trên GitHub?",
        "Thời tiết Hà Nội hiện tại bao nhiêu độ?",
    ]
    for t in triggers:
        decision = classify_search_intent(t)
        assert decision.should_search is True, f"Failed trigger for query: {t}"
        assert decision.confidence >= 0.70


def test_clean_html_to_markdown():
    dirty_html = """
    <html>
      <head><style>body { color: red; }</style></head>
      <body>
        <nav><a href="/home">Trang chủ</a><button>Menu</button></nav>
        <header>Banner quảng cáo</header>
        <main>
          <h1>Crawl4AI: Thư viện thu thập web cho AI Agent</h1>
          <p>Crawl4AI chuyển đổi các trang HTML phức tạp sang định dạng <b>Markdown</b> cực sạch.</p>
        </main>
        <footer>Bản quyền 2026. <script>console.log('track');</script></footer>
      </body>
    </html>
    """
    cleaned = _clean_html_to_markdown(dirty_html)
    assert "console.log" not in cleaned
    assert "body { color: red; }" not in cleaned
    assert "Crawl4AI: Thư viện thu thập web cho AI Agent" in cleaned
    assert "Markdown" in cleaned


def test_compress_context_snippet():
    long_text = (
        "Crawl4AI là một framework mã nguồn mở đỉnh cao với hơn 87.000 stars trên GitHub. "
        "Nó hỗ trợ trích xuất văn bản sạch từ mọi website. "
        "Ngoài ra nó còn có tính năng bypass bot detection và chụp screenshot. "
        "Đồng thời nó còn có chính sách cookie privacy terms of use vui lòng đọc kỹ trước khi đăng ký. "
        "Hỗ trợ tích hợp sâu với các AI Agent và Local LLM thông qua Model Context Protocol."
    )
    compressed = _compress_context_snippet(long_text, query="Crawl4AI stars GitHub", max_chars=180)
    assert len(compressed) <= 180
    assert "Crawl4AI" in compressed
    assert "cookie" not in compressed


def test_build_grounded_prompt():
    sources = [
        SearchResult(
            index=1,
            title="Crawl4AI Documentation",
            url="https://crawl4ai.com/docs",
            snippet="Crawl4AI v0.4.0 ra mắt tính năng async crawling.",
            compressed_text="Crawl4AI v0.4.0 ra mắt tính năng async crawling.",
            domain="crawl4ai.com",
        )
    ]
    sys_prompt, user_msg = build_grounded_prompt("Tính năng mới của Crawl4AI?", sources)
    assert "HIẾN PHÁP CHỐNG ẢO GIÁC" in sys_prompt
    assert "[Nguồn 1] Crawl4AI Documentation" in user_msg
    assert "https://crawl4ai.com/docs" in user_msg
    assert "<think>...</think>" in sys_prompt


def test_verify_hallucination_risk():
    sources = [
        SearchResult(
            index=1,
            title="FastMCP Release Notes",
            url="https://github.com/PrefectHQ/fastmcp",
            snippet="FastMCP version 2.5 was released in 2026 with 96% test coverage.",
            compressed_text="FastMCP version 2.5 was released in 2026 with 96% test coverage.",
            domain="github.com",
        )
    ]

    # Grounded response with citations and accurate numbers
    grounded_resp = (
        "<think>Kiểm tra nguồn 1 thấy phiên bản 2.5 ra mắt năm 2026.</think>\n"
        "Theo [1], phiên bản FastMCP 2.5 ra mắt vào năm 2026 với độ bao phủ 96% [1]."
    )
    verdict = verify_hallucination_risk(grounded_resp, sources)
    assert verdict.is_grounded is True
    assert verdict.hallucination_score <= 0.20
    assert 1 in verdict.cited_sources

    # Hallucinated response inventing fake numbers and no citations
    fake_resp = "FastMCP phiên bản 99.4 ra mắt năm 1985 với 14000 nhà phát triển."
    verdict_fake = verify_hallucination_risk(fake_resp, sources)
    assert verdict_fake.is_grounded is False
    assert verdict_fake.hallucination_score > 0.40
    assert len(verdict_fake.unsupported_numbers) > 0


def test_mcp_tool_execution():
    # Test selective_web_search MCP call with mock data
    mock_item = [{"title": "Repo Info", "url": "https://github.com/test", "snippet": "Test snippet info"}]
    with patch("app.grounded_search.execute_web_search", return_value=[SearchResult(1, "Repo", "https://t.co", "snippet", "snippet")]):
        res = handle_mcp_call("selective_web_search", {"query": "Tài liệu mới nhất 2026", "force": True})
        assert res["action"] == "EXECUTED_SEARCH"
        assert len(res["sources"]) == 1

    # Test skipped search for reasoning puzzle
    res_skipped = handle_mcp_call("selective_web_search", {"query": "Bài toán bèo 4 cụm phủ hồ"})
    assert res_skipped["action"] == "SKIPPED_SEARCH"
