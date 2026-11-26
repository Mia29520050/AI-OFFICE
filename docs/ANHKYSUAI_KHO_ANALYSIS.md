# Báo cáo Phân tích Tài nguyên từ Kho Repo Anh Kỹ Sư AI (anhkysuai.com/kho)
## Tích hợp Chống Ảo Giác, Tra Cứu Web Có Chọn Lọc và Mở Rộng Kỹ Năng Agent trong AI Office

---

## 1. Tổng quan & Thống kê Thu thập Dữ liệu (Data Extraction)

Toàn bộ kho tài nguyên từ **https://anhkysuai.com/kho/** (Kho lưu trữ GitHub chọn lọc của Anh Kỹ Sư AI) đã được script [scripts/crawl_anhkysuai_kho.py](file:///f:/AI-Office/scripts/crawl_anhkysuai_kho.py) thu thập, chuẩn hóa và xuất ra 2 tập dữ liệu cấu trúc:
- **JSON Catalog**: [data/anhkysuai_kho_catalog.json](file:///f:/AI-Office/data/anhkysuai_kho_catalog.json) (1,003.5 KB, 1,295 repositories).
- **JSONL Stream**: [data/anhkysuai_kho_catalog.jsonl](file:///f:/AI-Office/data/anhkysuai_kho_catalog.jsonl) (917.5 KB).

### Phân bố 1,295 Repo theo Trục Kiến trúc AI Office:
- **Developer Tools & Frameworks**: 885 repos
- **AI Agents & Orchestration**: 185 repos
- **Multimodal & Creative (Image/Audio/Manga)**: 90 repos
- **Knowledge RAG & Vector Retrieval**: 59 repos
- **Model Context Protocol (MCP) Servers**: 50 repos
- **Selective Search & Anti-Hallucination**: 16 repos
- **Local LLM & Inference Runtimes**: 10 repos

---

## 2. Bảng Xếp hạng & Đánh giá các Repo Tiềm năng Nhất

### 2.1. Tra Cứu Web Có Chọn Lọc (Selective Search & Clean Scraping)
| Repository | Stars | Mô tả & Điểm mạnh kỹ thuật | Khả năng tích hợp vào AI Office |
| :--- | :---: | :--- | :--- |
| [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | ★ 87.631 | Thu thập, trích xuất web chuyên dụng cho AI Agent, tự động chuyển đổi HTML thành Markdown siêu sạch, loại bỏ quảng cáo/rác, hỗ trợ LLM extraction. | **Cực cao (Hạng 1)**: Là công cụ lý tưởng để nạp dữ liệu sạch vào prompt của Local LLM (Ollama) mà không tốn context window. |
| [searxng/searxng](https://github.com/searxng/searxng) | ★ 39.787 | Công cụ siêu tìm kiếm meta-search tổng hợp kết quả từ Google, Bing, DuckDuckGo, ArXiv, Wikipedia qua API JSON nội bộ. Không quảng cáo, không rate limit. | **Cực cao (Hạng 1)**: Triển khai local docker hoặc gọi API, giúp AI Office tìm kiếm không phụ thuộc vào API trả phí của Google/Bing. |
| [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | ★ 205.847 | Hạ tầng tri thức chuyển đổi website thành định dạng Markdown có cấu trúc, tìm kiếm và truy xuất sâu qua 1 API. | **Cao**: Phù hợp cho tra cứu tài liệu kỹ thuật dài hoặc toàn bộ domain. |
| [google/langextract](https://github.com/google/langextract) | ★ 39.348 | Thư viện trích xuất thông tin có cấu trúc từ văn bản không cấu trúc, có đối soát chỉ rõ đoạn nguồn (grounding spans). | **Cao**: Dùng làm lớp Grounding Verifier để phát hiện và triệt tiêu ảo giác (Anti-Hallucination). |

### 2.2. Model Context Protocol (MCP) & Mở rộng Kỹ năng Agent
| Repository | Stars | Mô tả & Điểm mạnh kỹ thuật | Khả năng tích hợp vào AI Office |
| :--- | :---: | :--- | :--- |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | ★ 39.968 | Máy chủ MCP chính thức từ Microsoft cho phép Agent điều khiển trình duyệt headless: click, snapshot, đọc DOM thực thi JavaScript. | **Cực cao**: Mở rộng kỹ năng cho AI Office tương tác với web động, form đăng nhập, web app SPA. |
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | ★ 58.638 | Máy chủ MCP kết nối Chrome DevTools cho Agent kiểm tra mạng, DOM và gỡ lỗi giao diện trực tiếp. | **Cao**: Hỗ trợ bộ phận QA và kiểm thử giao diện AI Office. |
| [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | ★ 78.284 | Đồ thị tri thức mã nguồn cục bộ qua MCP, giúp agent truy vấn hàm/class/module thay vì đọc duyệt tuần tự tệp tin. Tiết kiệm token context. | **Cực cao**: Tăng tốc độ đọc hiểu codebase `F:\AI-Office` cho local model. |
| [anthropics/skills](https://github.com/anthropics/skills) | ★ 199.012 | Kho chuẩn kỹ năng của Anthropic theo định dạng `SKILL.md` (metadata, logic, examples). | **Cực cao**: Khớp 100% với hệ thống `skills/` đang vận hành trong AI Office. |

---

## 3. Kiến trúc Đề xuất: "Selective Search & Anti-Hallucination Pipeline"

Để AI Office tra cứu web thông minh, không bị lãng phí token và loại bỏ triệt để hiện tượng bịa đặt thông tin (ảo giác), quy trình 4 giai đoạn sau được đề xuất:

```
[Người dùng đặt câu hỏi]
           │
           ▼
┌──────────────────────────────────────────────┐
│ 1. SELECTIVE SEARCH CLASSIFIER (Cổng chọn lọc)│
│    Mô hình CoT phân tích: Có cần dữ liệu web? │
│    - Nếu câu hỏi logic, code nội bộ -> BỎ QUA │
│    - Nếu cần sự kiện mới, URL, sự thật -> BẬT│
└──────────────────────┬───────────────────────┘
                       │ (Cần tra cứu)
                       ▼
┌──────────────────────────────────────────────┐
│ 2. CLEAN META-RETRIEVAL (SearXNG + Crawl4AI) │
│    - SearXNG: Lấy top 3-5 URL chuẩn xác      │
│    - Crawl4AI: Trích xuất Markdown sạch      │
│    - Cắt lọc tối đa 1.500 từ cốt lõi         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 3. GROUNDED REASONING CoT (<think> Trích dẫn) │
│    - Đối chiếu luận điểm với đoạn trích nguồn│
│    - Đánh dấu [Nguồn: URL / Trích đoạn X]    │
│    - Bác bỏ các giả định không có bằng chứng │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 4. FACT-CHECKING & RESPONSE EMISSION         │
│    - Trả lời kèm trích dẫn nguồn minh bạch   │
│    - Không suy diễn ngoài dữ kiện thực tế    │
└──────────────────────────────────────────────┘
```

---

## 4. Hành động Tiếp theo & Bàn giao Phối hợp

1. **Cho `@trainer`**:
   - Sử dụng bộ dữ liệu mẫu suy luận [data/training/reasoning_cot_train.jsonl](file:///f:/AI-Office/data/training/reasoning_cot_train.jsonl) đã sẵn sàng.
   - Bổ sung định dạng mẫu phản biện tra cứu có trích dẫn nguồn `[Source: ...]` vào pha tinh chỉnh LoRA tiếp theo.

2. **Cho `@evaluator`**:
   - Kết hợp danh mục repo từ [data/anhkysuai_kho_catalog.json](file:///f:/AI-Office/data/anhkysuai_kho_catalog.json) để xây dựng thang điểm Matrix: Tính chọn lọc của công cụ tìm kiếm, tỷ lệ nén Markdown của Crawl4AI, và độ trễ phản hồi qua MCP.

3. **Cho `@coordinator`**:
   - Toàn bộ dữ liệu crawl, catalog JSON/JSONL và báo cáo kiến trúc đã sẵn sàng tích hợp vào AI Office backend.
