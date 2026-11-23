# AI Office Documentation Index (`docs/`)

Thư mục `docs/` chứa toàn bộ tài liệu kiến trúc, khảo sát (audit), kế hoạch triển khai và đặc tả kỹ thuật của dự án **AI Office**.

---

## 1. Cấu trúc thư mục tài liệu

```
docs/
├── anime_intelligence/       # Đặc tả Anime Intelligence, bộ nhớ lorebook & visual benchmark
│   ├── ANIME_INTELLIGENCE_BENCHMARK_PROMPTS.md
│   ├── ANIME_INTELLIGENCE_RESEARCH_AND_MEMORY_ARCHITECTURE.md
│   └── ANIME_INTELLIGENCE_VISUAL_QUALITY_AND_CONTINUITY.md
├── audit/                    # Báo cáo kiểm định kiến trúc định kỳ
│   └── 2026-11-07/           # Audit kiến trúc nền tảng ban đầu
│       ├── AGENT_INVENTORY.md
│       ├── ARCHITECTURE_AUDIT.md
│       ├── IMPLEMENTATION_ROADMAP.md
│       ├── README.md
│       ├── SECURITY_POLICY.md
│       ├── TOOL_REGISTRY.md
│       └── WORKFLOW_DESIGN.md
├── manga_studio/             # Tài liệu thiết kế & lộ trình tính năng Manga Studio
│   ├── MANGA_STUDIO_AUDIT.md
│   └── MANGA_STUDIO_IMPLEMENTATION_PLAN.md
└── README.md                 # Chỉ mục tài liệu này
```

---

## 2. Mô tả chi tiết từng tài liệu

### 2.1. Anime Intelligence (`docs/anime_intelligence/`)
- [ANIME_INTELLIGENCE_RESEARCH_AND_MEMORY_ARCHITECTURE.md](file:///f:/AI-Office/docs/anime_intelligence/ANIME_INTELLIGENCE_RESEARCH_AND_MEMORY_ARCHITECTURE.md):
  Kiến trúc bộ nhớ phân tầng (Short-term context, Epodic memory, Canon lorebook), hồ sơ nhân vật với Locked Traits, và cơ chế Speech Rules.
- [ANIME_INTELLIGENCE_VISUAL_QUALITY_AND_CONTINUITY.md](file:///f:/AI-Office/docs/anime_intelligence/ANIME_INTELLIGENCE_VISUAL_QUALITY_AND_CONTINUITY.md):
  Quy chuẩn mỹ thuật manga/anime: tỷ lệ khung hình, kiểm soát halftone screentone, xử lý font chữ tiếng Việt (Inter-Variable) và thuật toán phát hiện bất đồng nhất (Continuity QA).
- [ANIME_INTELLIGENCE_BENCHMARK_PROMPTS.md](file:///f:/AI-Office/docs/anime_intelligence/ANIME_INTELLIGENCE_BENCHMARK_PROMPTS.md):
  Bộ prompt và kịch bản thử thách benchmark đa phong cách (Shonen, Shoujo, Cyberpunk, Slice-of-Life).

### 2.2. Manga Studio (`docs/manga_studio/`)
- [MANGA_STUDIO_AUDIT.md](file:///f:/AI-Office/docs/manga_studio/MANGA_STUDIO_AUDIT.md):
  Báo cáo audit Phase 0 về tài nguyên phần cứng (VRAM 6GB, RAM 16GB), dịch vụ nền (Ollama, ComfyUI), cấu trúc database và tương thích hệ điều hành Windows 11.
- [MANGA_STUDIO_IMPLEMENTATION_PLAN.md](file:///f:/AI-Office/docs/manga_studio/MANGA_STUDIO_IMPLEMENTATION_PLAN.md):
  Kế hoạch kỹ thuật 5 pha: Data Model & Story Engine, ComfyUI Pipeline & Resource Lock, Manga Compositor, UI Integration và E2E QA Verification.

### 2.3. System Architecture Audit (`docs/audit/2026-11-07/`)
- [ARCHITECTURE_AUDIT.md](file:///f:/AI-Office/docs/audit/2026-11-07/ARCHITECTURE_AUDIT.md):
  Phân tích kiến trúc tổng thể AI Office: kết nối WebView2 - FastAPI - SQLite - Ollama.
- [SECURITY_POLICY.md](file:///f:/AI-Office/docs/audit/2026-11-07/SECURITY_POLICY.md):
  Chính sách ranh giới an toàn: cách ly workspace, bắt buộc phê duyệt (Human-in-the-loop) cho mọi thao tác ghi/sửa tệp, desktop action và browser action.
- [AGENT_INVENTORY.md](file:///f:/AI-Office/docs/audit/2026-11-07/AGENT_INVENTORY.md):
  Định nghĩa 9 vai trò agent cốt lõi và phạm vi quyền hạn của từng agent.
- [TOOL_REGISTRY.md](file:///f:/AI-Office/docs/audit/2026-11-07/TOOL_REGISTRY.md):
  Danh mục các công cụ hệ thống tích hợp (File Editor, Browser Runner, Computer Use Controller, Task Tracker).
- [WORKFLOW_DESIGN.md](file:///f:/AI-Office/docs/audit/2026-11-07/WORKFLOW_DESIGN.md):
  Thiết kế luồng tương tác giữa CEO, Workspace Editor, Developer, Researcher và QA.
