# AI Office Agent Skills (`skills/`)

Thư mục `skills/` và `.agents/skills/` chứa các tệp định nghĩa kỹ năng (`SKILL.md`) cho từng vai trò agent trong hệ thống **AI Office**. Mỗi tệp `SKILL.md` quy định vai trò, mục tiêu, nguyên tắc hoạt động và công cụ được phép sử dụng. Mọi AI Agent **bắt buộc phải đọc kỹ Skill tương ứng** trước khi thao tác thực tế.

---

## Danh mục Toàn bộ Kỹ năng (Skills Directory)

| Thư mục | Vai trò / Năng lực | Tệp cấu hình | Mục tiêu chính |
| :--- | :--- | :--- | :--- |
| `voice/` | Voice Engine & Audio | `SKILL.md` | Neural TTS lồng tiếng anime/manga, procedural SFX và xuất phụ đề tự động (lưu `Export/Audio/`). |
| `vtuber_companion/` | VTuber & Live2D Companion | `SKILL.md` | Tương tác trợ lý ảo Live2D/3D Avatar, biểu cảm gương mặt, đồng bộ môi thời gian thực. |
| `game_translator/` | Game & Manga Translator | `SKILL.md` | Nhận diện chữ trên màn hình (OCR) và bản địa hóa ngữ cảnh game/visual novel sang tiếng Việt. |
| `blender_3d/` | Blender 3D Automation | `SKILL.md` | Tự động hóa Blender Python, tạo phối cảnh 3D không gian cho manga/anime (lưu `Export/3D/`). |
| `video_gen/` | Video Gen & Motion Comic | `SKILL.md` | Sản xuất Motion Comic 16:9 / 9:16, chuyển cảnh Ken Burns, phối âm và render (lưu `Export/Video/`). |
| `game_agent/` | Game Agent & Computer Vision | `SKILL.md` | Nhận thức thị giác màn hình game, thực thi playbook chiến thuật tương tác an toàn. |
| `weekly_radar/` | Weekly Tech Radar | `SKILL.md` | Thu thập, tổng hợp xu hướng AI mã nguồn mở, Anime/Manga model mới hàng tuần. |
| `image_gen_ref/` | Image Generation & Ref Lock | `SKILL.md` | Sinh ảnh ComfyUI chất lượng cao, khóa vóc dáng/khuôn mặt qua AnimaRefAdapter (lưu `Export/Images/`). |
| `motion/` | UI Motion & Animation | `SKILL.md` | Nguyên lý hoạt hình Disney, easing curves, animation 60fps mượt mà cho Desktop UI. |
| `orchestration/` | CEO / Coordinator | `SKILL.md` | Lập kế hoạch tổng thể, điều phối nhiệm vụ, phân công cho các agent chuyên trách. |
| `coding/` | Developer Agent | `SKILL.md` | Lập trình, thiết kế kiến trúc, refactoring và viết unit test. |
| `qa/` | Quality Assurance Agent | `SKILL.md` | Kiểm tra điều kiện chấp nhận (acceptance criteria), thẩm định kết quả và kiểm thử lỗi. |
| `workspace/` | Workspace Editor Agent | `SKILL.md` | Đọc tệp UTF-8, tạo đề xuất chỉnh sửa unified diff và thực hiện cập nhật an toàn. |
| `research/` | Research Agent | `SKILL.md` | Tìm kiếm tài liệu cục bộ, tổng hợp tri thức và trích xuất thông tin. |
| `writing/` | Technical Writer Agent | `SKILL.md` | Viết tài liệu kỹ thuật, báo cáo, hướng dẫn và kịch bản nội dung. |
| `analysis/` | Data & Logic Analyst | `SKILL.md` | Phân tích số liệu, cấu trúc logic, so sánh và đánh giá dữ liệu. |
| `browser/` | Web Browser Agent | `SKILL.md` | Điều hướng web an toàn, đọc DOM, chuẩn bị proposal thao tác link/nút/input. |
| `computer/` | Computer Use Agent | `SKILL.md` | Đề xuất từng bước thao tác ứng dụng máy tính dựa trên screenshot và UIA tree. |

---

## Nguyên tắc Vận hành
1. **Skill-First:** Luôn đọc `SKILL.md` liên quan trước khi triển khai bất kỳ tác vụ nào.
2. **Hardware Lock:** Tuân thủ cấu hình 6GB VRAM / 12GB RAM, serialize inference.
3. **Export Strict:** Mọi file thành phẩm đầu ra phải lưu tại đúng thư mục con trong `F:\AI-Office\Export\`.
