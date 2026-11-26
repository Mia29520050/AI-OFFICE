from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("manga_story")

# ==============================================================================
# 1. Pydantic Domain Schemas
# ==============================================================================

class SpeechRules(BaseModel):
    """Quy chuẩn khẩu khí và cách xưng hô của nhân vật bằng tiếng Việt."""
    first_person: str = Field(default="tôi", description="Đại từ nhân xưng ngôi thứ nhất (ví dụ: tôi, tớ, ta, mình, em, anh)")
    second_person: str = Field(default="cậu", description="Đại từ nhân xưng ngôi thứ hai (ví dụ: cậu, bạn, ngươi, anh, em, bác)")
    tone: str = Field(default="tự nhiên, điềm đạm", description="Sắc thái giọng điệu (ví dụ: lạnh lùng, năng nổ, kiêu ngạo, u buồn)")
    honorifics: list[str] = Field(default_factory=list, description="Kính ngữ hoặc cách gọi tôn xưng (ví dụ: tiền bối, đại ca, sensei)")
    catchphrases: list[str] = Field(default_factory=list, description="Câu cửa miệng hoặc thói quen phát ngôn đặc trưng")
    vocabulary_habits: list[str] = Field(default_factory=list, description="Từ ngữ hay lặp lại hoặc từ vựng ưa thích")
    forbidden_words: list[str] = Field(default_factory=list, description="Từ ngữ cấm kỵ mà nhân vật này không bao giờ nói")
    sample_dialogues: list[str] = Field(default_factory=list, description="Các câu thoại mẫu thể hiện đúng linh hồn nhân vật")


class CharacterLockedTraits(BaseModel):
    """Đặc điểm ngoại hình cố định (locked traits) để giữ tính nhất quán khi sinh ảnh AI."""
    gender: str = Field(default="unspecified", description="Giới tính (nam, nữ, phi giới tính)")
    age_appearance: str = Field(default="teen", description="Độ tuổi ước chừng (ví dụ: 16 tuổi, trung niên, trẻ em)")
    hair_style: str = Field(default="", description="Kiểu tóc cố định (ví dụ: tóc ngắn rối, tóc dài buộc đuôi ngựa)")
    hair_color: str = Field(default="", description="Màu tóc (ví dụ: đen, bạch kim, vàng hoe)")
    eye_color: str = Field(default="", description="Màu mắt (ví dụ: đỏ thẫm, xanh thẳm, hổ phách)")
    facial_features: list[str] = Field(default_factory=list, description="Đặc điểm khuôn mặt (ví dụ: vết sẹo má trái, nốt ruồi dưới mắt, đeo kính gọng tròn)")
    signature_outfit: str = Field(default="", description="Trang phục đặc trưng (ví dụ: áo gakuran đen cài cúc kín, áo choàng phép thuật trắng)")
    accessories: list[str] = Field(default_factory=list, description="Phụ kiện cố định (ví dụ: dây chuyền bạc mặt trăng, bao tay hở ngón)")
    color_scheme: list[str] = Field(default_factory=list, description="Bảng màu chủ đạo của nhân vật")
    diffusion_positive_tags: str = Field(default="", description="Prompt tags tiếng Anh tối ưu hóa cho 2D anime/manga diffusion")
    diffusion_negative_tags: str = Field(default="", description="Negative prompt tags để tránh biến dạng ngoại hình nhân vật")
    custom_attributes: dict[str, str] = Field(default_factory=dict, description="Thuộc tính ngoại hình bổ sung")


class CharacterProfile(BaseModel):
    """Hồ sơ hoàn chỉnh của một nhân vật trong Manga Studio."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    series_id: str | None = Field(default=None, description="ID của bộ manga trực thuộc")
    name: str = Field(..., description="Tên nhân vật (ví dụ: Kurogane Ren)")
    japanese_name: str | None = Field(default=None, description="Tên Kanji/Katakana nếu có (ví dụ: 黒鉄 レン)")
    role: Literal["protagonist", "antagonist", "supporting", "mentor", "rival", "comic_relief", "extra"] = Field(
        default="supporting", description="Vai trò kịch bản trong cốt truyện"
    )
    one_line_summary: str = Field(default="", description="Một dòng tóm tắt định danh nhân vật")
    personality: str = Field(default="", description="Mô tả tâm lý, nội tâm, động cơ và triết lý sống")
    backstory: str = Field(default="", description="Tiểu sử và quá khứ quan trọng")
    strengths: list[str] = Field(default_factory=list, description="Thế mạnh, năng lực hoặc kỹ năng vượt trội")
    weaknesses: list[str] = Field(default_factory=list, description="Điểm yếu, vết thương lòng hoặc nỗi sợ")
    speech_rules: SpeechRules = Field(default_factory=SpeechRules)
    locked_traits: CharacterLockedTraits = Field(default_factory=CharacterLockedTraits)
    relationships: list[dict[str, str]] = Field(
        default_factory=list,
        description="Mối quan hệ với nhân vật khác (ví dụ: [{'target': 'Luna', 'relation': 'đồng minh tin cậy', 'dynamic': 'vừa đấu khẩu vừa che chở'}])"
    )
    arc_goal: str = Field(default="", description="Mục tiêu hoặc biến chuyển tâm lý trong diễn biến truyện")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CanonFact(BaseModel):
    """Quy tắc thế giới và chân lý bất biến (Canon) không được phép vi phạm."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    series_id: str | None = Field(default=None)
    category: Literal["world_rule", "magic_system", "history", "organization", "technology", "taboo", "character_secret"] = Field(
        default="world_rule", description="Phân loại luật thế giới"
    )
    title: str = Field(..., description="Tiêu đề quy tắc (ví dụ: Giới hạn của Ma pháp Hắc Nguyệt)")
    fact: str = Field(..., description="Nội dung chi tiết của quy tắc thế giới")
    severity: Literal["immutable", "hard_rule", "soft_guideline", "secret"] = Field(
        default="immutable", description="Mức độ nghiêm ngặt: immutable (bất khả xâm phạm), hard_rule, soft_guideline, secret"
    )
    related_characters: list[str] = Field(default_factory=list, description="Tên các nhân vật liên đới")
    related_locations: list[str] = Field(default_factory=list, description="Các địa điểm chịu tác động")
    is_revealed: bool = Field(default=True, description="Đã tiết lộ cho độc giả hay đang là bí mật")
    notes: str | None = Field(default=None)


class TimelineEvent(BaseModel):
    """Sự kiện dòng thời gian trong lịch sử thế giới hoặc diễn biến cốt truyện."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    series_id: str | None = Field(default=None)
    era_or_arc: str = Field(default="Hiện tại", description="Thời kỳ, Arc hoặc mốc thời gian")
    order_index: int = Field(default=1, description="Thứ tự thời gian tuyến tính")
    timestamp_label: str = Field(default="", description="Nhãn thời gian hiển thị (ví dụ: 10 năm trước, Đêm Trăng Đỏ)")
    title: str = Field(..., description="Tên sự kiện quan trọng")
    description: str = Field(..., description="Chi tiết diễn biến sự kiện")
    characters_involved: list[str] = Field(default_factory=list, description="Nhân vật tham gia")
    location: str = Field(default="", description="Nơi diễn ra sự kiện")
    causality_prerequisites: list[str] = Field(default_factory=list, description="Tiền đề sự kiện bắt buộc xảy ra trước")
    consequences: list[str] = Field(default_factory=list, description="Hệ quả để lại cho hiện tại")
    chapter_id: str | None = Field(default=None)


class DialogueLine(BaseModel):
    """Một lời thoại hoặc suy nghĩ trong bóng thoại manga."""
    speaker: str = Field(..., description="Tên nhân vật phát ngôn hoặc 'Người dẫn chuyện'")
    text: str = Field(..., description="Câu thoại tiếng Việt tự nhiên, phù hợp khung bóng thoại (dưới 35 từ)")
    bubble_type: Literal["speech", "thought", "shout", "whisper", "scream", "narrator", "sfx"] = Field(
        default="speech", description="Loại bóng thoại: speech (thoại tròn), thought (suy nghĩ có bọt), shout (gắt nhọn), whisper (nét đứt), narrator (hộp thoại), sfx (chữ tượng thanh)"
    )
    emotion: str = Field(default="neutral", description="Cảm xúc đi kèm (ví dụ: tức giận, sợ hãi, mỉa mai, ngạc nhiên)")
    position_hint: Literal["top-left", "top-right", "bottom-left", "bottom-right", "center", "auto"] = Field(
        default="auto", description="Gợi ý vị trí đặt bóng thoại trên panel"
    )
    vietnamese_pronouns_used: str | None = Field(default=None, description="Cặp đại từ nhân xưng đã dùng (ví dụ: 'tớ - cậu')")

    @field_validator("bubble_type", mode="before")
    @classmethod
    def _norm_bubble_type(cls, v: Any) -> str:
        val = str(v or "speech").lower().strip()
        if val in {"speech", "thought", "shout", "whisper", "scream", "narrator", "sfx"}:
            return val
        if "narrat" in val or "caption" in val:
            return "narrator"
        if "thought" in val or "think" in val:
            return "thought"
        if "shout" in val or "yell" in val:
            return "shout"
        if "whisper" in val:
            return "whisper"
        return "speech"

    @field_validator("position_hint", mode="before")
    @classmethod
    def _norm_position_hint(cls, v: Any) -> str:
        val = str(v or "auto").lower().strip()
        if val in {"top-left", "top-right", "bottom-left", "bottom-right", "center", "auto"}:
            return val
        return "auto"


class PanelSFX(BaseModel):
    """Hiệu ứng âm thanh chữ tượng thanh (Sound Effects / Onomatopoeia)."""
    text: str = Field(..., description="Từ tượng thanh tiếng Việt/Nhật (ví dụ: RẦM!, VÙÙ!, XOẸT!, DOKI DOKI)")
    meaning: str = Field(default="", description="Ý nghĩa hành động hoặc tiếng động")
    visual_style: Literal["impact", "ambient", "motion", "comic"] = Field(
        default="impact", description="Phong cách vẽ chữ SFX"
    )

    @field_validator("visual_style", mode="before")
    @classmethod
    def _norm_visual_style(cls, v: Any) -> str:
        val = str(v or "impact").lower().strip()
        if val in {"impact", "ambient", "motion", "comic"}:
            return val
        if val in {"subtle", "ethereal", "magic", "whisper", "soft", "glow"}:
            return "ambient"
        if val in {"fast", "speed", "wind", "whoosh"}:
            return "motion"
        return "impact"


class PanelPlan(BaseModel):
    """Kế hoạch chi tiết cho 1 ô tranh manga (panel)."""
    panel_number: int = Field(default=1, description="Số thứ tự ô tranh trên trang")
    layout_hint: Literal["standard", "wide", "tall", "splash", "small"] = Field(
        default="standard", description="Kích thước và hình dạng ô tranh"
    )
    camera_angle: Literal[
        "close_up", "extreme_close_up", "medium_shot", "wide_shot", "full_shot",
        "low_angle", "high_angle", "over_the_shoulder", "dutch_angle"
    ] = Field(default="medium_shot", description="Góc quay và cỡ cảnh")
    visual_description: str = Field(..., description="Mô tả chi tiết bố cục, hành động, nét mặt, hậu cảnh để sinh ảnh")
    characters_in_panel: list[str] = Field(default_factory=list, description="Tên các nhân vật xuất hiện trong ô này")
    characters_present: list[str] = Field(default_factory=list, description="Tên nhân vật có mặt (alias của characters_in_panel)")
    diffusion_prompt_en: str = Field(default="", description="Prompt tiếng Anh dịch sẵn tích hợp locked traits nhân vật")
    diffusion_negative_prompt: str = Field(default="", description="Negative prompt cho ô tranh này")
    dialogues: list[DialogueLine] = Field(default_factory=list, description="Danh sách lời thoại đặt trong ô tranh")
    sfx: list[PanelSFX] = Field(default_factory=list, description="Chữ tượng thanh SFX nếu có")
    focus_element: str = Field(default="", description="Trọng tâm thị giác của khung hình")
    lighting_and_atmosphere: str = Field(default="high contrast, dramatic manga shading", description="Ánh sáng và không khí cảnh")

    @field_validator("layout_hint", mode="before")
    @classmethod
    def _norm_layout_hint(cls, v: Any) -> str:
        val = str(v or "standard").lower().strip()
        return val if val in {"standard", "wide", "tall", "splash", "small"} else "standard"

    @field_validator("camera_angle", mode="before")
    @classmethod
    def _norm_camera_angle(cls, v: Any) -> str:
        val = str(v or "medium_shot").lower().strip().replace("-", "_").replace(" ", "_")
        allowed = {
            "close_up", "extreme_close_up", "medium_shot", "wide_shot", "full_shot",
            "low_angle", "high_angle", "over_the_shoulder", "dutch_angle"
        }
        return val if val in allowed else "medium_shot"

    @field_validator("dialogues", mode="before")
    @classmethod
    def _clean_dialogues(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        out = []
        for item in v:
            if isinstance(item, BaseModel):
                out.append(item)
                continue
            if isinstance(item, dict) and str(item.get("text", "")).strip():
                d = dict(item)
                if not str(d.get("speaker", "")).strip():
                    d["speaker"] = "Nhân vật"
                out.append(d)
        return out

    @field_validator("sfx", mode="before")
    @classmethod
    def _clean_sfx(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        return [
            item for item in v
            if isinstance(item, BaseModel) or (isinstance(item, dict) and str(item.get("text", "")).strip())
        ]


class ScenePlan(BaseModel):
    """Kế hoạch một phân cảnh trong chương."""
    scene_number: int = Field(default=1, description="Số thứ tự phân cảnh trong chương")
    title: str = Field(..., description="Tiêu đề phân cảnh (ví dụ: Cuộc gặp gỡ nơi gác chuông)")
    location: str = Field(..., description="Địa điểm diễn ra")
    time_of_day: Literal["morning", "day", "sunset", "night", "indoor", "dark"] = Field(
        default="day", description="Thời điểm trong ngày"
    )
    summary: str = Field(..., description="Tóm tắt nội dung và biến chuyển trong cảnh")
    characters_present: list[str] = Field(default_factory=list, description="Danh sách nhân vật có mặt tại hiện trường")
    emotional_beat: Literal["tension", "comedic", "dramatic", "resolution", "mystery", "action", "romance"] = Field(
        default="tension", description="Nhịp cảm xúc cốt lõi của cảnh"
    )
    conflict: str = Field(default="", description="Mâu thuẫn hoặc thách thức cần giải quyết")
    outcome: str = Field(default="", description="Kết quả phân cảnh dẫn dắt tới cảnh kế tiếp")
    panels: list[PanelPlan] = Field(default_factory=list, description="Các ô tranh triển khai phân cảnh này")

    @field_validator("time_of_day", mode="before")
    @classmethod
    def _norm_time_of_day(cls, v: Any) -> str:
        val = str(v or "day").lower().strip()
        return val if val in {"morning", "day", "sunset", "night", "indoor", "dark"} else "indoor"

    @field_validator("emotional_beat", mode="before")
    @classmethod
    def _norm_emotional_beat(cls, v: Any) -> str:
        val = str(v or "tension").lower().strip()
        return val if val in {"tension", "comedic", "dramatic", "resolution", "mystery", "action", "romance"} else "dramatic"

    @field_validator("panels", mode="before")
    @classmethod
    def _clean_panels(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        cleaned = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, BaseModel):
                cleaned.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item = dict(item)
            if not item.get("visual_description"):
                desc = item.get("diffusion_prompt_en") or item.get("focus_element")
                if not desc and isinstance(item.get("dialogues"), list) and item["dialogues"]:
                    desc = item["dialogues"][0].get("text", "")
                if not desc:
                    continue
                item["visual_description"] = str(desc)
            if not item.get("panel_number"):
                item["panel_number"] = idx
            cleaned.append(item)
        return cleaned


class ChapterPlan(BaseModel):
    """Dàn ý hoàn chỉnh của một chương manga."""
    chapter_number: int = Field(default=1, description="Số thứ tự chương")
    title: str = Field(..., description="Tựa đề chương (ví dụ: Chương 1: Đêm Trăng Đen Khai Giảng)")
    synopsis: str = Field(..., description="Tóm tắt cốt truyện toàn bộ chương")
    central_conflict: str = Field(default="", description="Mâu thuẫn trung tâm của chương")
    climax: str = Field(default="", description="Cao trào của chương")
    cliffhanger_or_ending: str = Field(default="", description="Đoạn kết hoặc cái kết lửng (cliffhanger) kích thích đọc tiếp")
    scenes: list[ScenePlan] = Field(default_factory=list, description="Danh sách phân cảnh chi tiết")
    estimated_pages: int = Field(default=4, description="Số trang manga dự kiến")
    canon_references_used: list[str] = Field(default_factory=list, description="Các luật canon được áp dụng trong chương")
    character_arcs_progressed: list[str] = Field(default_factory=list, description="Sự tiến triển của các nhân vật")

    @field_validator("scenes", mode="before")
    @classmethod
    def _clean_scenes(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        cleaned = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, BaseModel):
                cleaned.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item = dict(item)
            if not item.get("title"):
                item["title"] = f"Cảnh {idx}"
            if not item.get("location"):
                item["location"] = "Tháp Ký Ức"
            if not item.get("summary"):
                item["summary"] = item["title"]
            cleaned.append(item)
        return cleaned


class ContinuityIssue(BaseModel):
    """Phát hiện lỗi vi phạm tính nhất quán cốt truyện hoặc nhân vật."""
    issue_type: Literal[
        "character_trait_violation",
        "speech_rule_violation",
        "timeline_contradiction",
        "canon_fact_contradiction",
        "appearance_conflict",
        "location_jump",
        "relationship_break"
    ] = Field(..., description="Phân loại lỗi tính nhất quán")
    severity: Literal["critical", "warning", "suggestion"] = Field(
        default="warning", description="Mức độ nghiêm trọng của lỗi"
    )
    entity_affected: str = Field(..., description="Nhân vật, địa điểm hoặc sự kiện bị ảnh hưởng")
    description: str = Field(..., description="Mô tả cụ thể vi phạm bằng tiếng Việt")
    quote_or_location: str = Field(default="", description="Trích dẫn câu thoại hoặc vị trí cảnh vi phạm")
    fix_suggestion: str = Field(default="", description="Gợi ý cách sửa đổi chuẩn xác")


class ContinuityReport(BaseModel):
    """Báo cáo kiểm định tính nhất quán (Continuity Check) toàn diện."""
    is_consistent: bool = Field(default=True, description="Toàn bộ chương có đạt chuẩn nhất quán không")
    score: int = Field(default=100, ge=0, le=100, description="Điểm số nhất quán từ 0 đến 100")
    critical_count: int = Field(default=0, description="Số lượng lỗi nghiêm trọng")
    warning_count: int = Field(default=0, description="Số lượng cảnh báo")
    issues: list[ContinuityIssue] = Field(default_factory=list, description="Danh sách các vấn đề phát hiện được")
    summary: str = Field(default="", description="Nhận xét tổng quan của Biên kịch Manga AI")
    recommendations: list[str] = Field(default_factory=list, description="Các khuyến nghị cải thiện cốt truyện")


class StoryGenerationRequest(BaseModel):
    """Tham số yêu cầu sinh kịch bản chương manga bằng Ollama."""
    series_title: str = Field(..., description="Tên bộ truyện")
    genre: str = Field(default="Shonen Manga", description="Thể loại (ví dụ: Shonen Siêu Nhiên, Seinen Tâm Lý, Shoujo Học Đường)")
    art_style: Literal["b_w", "color"] = Field(default="b_w", description="Phong cách manga: b_w (Đen trắng cổ điển) hoặc color (Màu anime)")
    premise: str = Field(..., description="Ý tưởng hoặc tiền đề kịch bản muốn triển khai")
    chapter_number: int = Field(default=1, description="Số thứ tự chương cần viết")
    chapter_title: str | None = Field(default=None, description="Tên chương nếu đã định trước")
    characters: list[CharacterProfile] = Field(default_factory=list, description="Hồ sơ các nhân vật tham gia")
    canon_facts: list[CanonFact] = Field(default_factory=list, description="Quy tắc thế giới bắt buộc tuân thủ")
    timeline_events: list[TimelineEvent] = Field(default_factory=list, description="Dòng sự kiện liên quan")
    user_instructions: str | None = Field(default=None, description="Chỉ đạo bổ sung của tác giả")
    target_scene_count: int = Field(default=3, ge=1, le=8, description="Số phân cảnh mong muốn")
    target_panels_per_scene: int = Field(default=3, ge=1, le=8, description="Số ô tranh trên mỗi phân cảnh")


class StoryGenerationResponse(BaseModel):
    """Kết quả sinh kịch bản chương manga."""
    chapter_plan: ChapterPlan
    raw_model_response: str | None = None
    mode_used: Literal["ollama", "cloud", "fallback_template"] = "ollama"
    model_name: str = "qwen3.5:4b"
    generation_time_ms: int = 0


class ContinuityCheckRequest(BaseModel):
    """Tham số kiểm tra tính nhất quán cho một chương."""
    chapter_plan: ChapterPlan
    characters: list[CharacterProfile] = Field(default_factory=list)
    canon_facts: list[CanonFact] = Field(default_factory=list)
    timeline_events: list[TimelineEvent] = Field(default_factory=list)


class ContinuityCheckResponse(BaseModel):
    """Kết quả kiểm tra tính nhất quán."""
    report: ContinuityReport
    mode_used: Literal["hybrid", "deterministic_only", "llm_only"] = "hybrid"
    model_name: str = "qwen3.5:4b"


class ReaderChoice(BaseModel):
    """Một lựa chọn tương tác dành cho người đọc hoặc nhân vật chính."""
    choice_id: str = Field(default_factory=lambda: f"choice_{uuid.uuid4().hex[:6]}")
    route_target: str = Field(..., description="ID của route mục tiêu (ví dụ: route_a, route_b, route_c)")
    text: str = Field(..., description="Nội dung quyết định của người đọc (ví dụ: Đột kích trực diện vào trung tâm ma trận)")
    intent_tone: Literal["aggressive", "stealthy", "diplomatic", "mysterious", "defensive", "tactical"] = Field(
        default="tactical", description="Sắc thái hành động"
    )
    consequence_hint: str = Field(default="", description="Gợi ý ngắn gọn về hệ quả tiềm tàng")
    risk_reward: str = Field(default="", description="Đánh giá rủi ro và phần thưởng")

    @field_validator("intent_tone", mode="before")
    @classmethod
    def _norm_tone(cls, v: Any) -> str:
        val = str(v or "tactical").lower().strip()
        allowed = {"aggressive", "stealthy", "diplomatic", "mysterious", "defensive", "tactical"}
        return val if val in allowed else "tactical"


class StoryBranch(BaseModel):
    """Một nhánh cốt truyện cụ thể (Route A, Route B, Route C...)."""
    route_id: str = Field(..., description="Mã định danh nhánh: route_a, route_b, route_c...")
    route_name: str = Field(..., description="Tên nhánh truyện (ví dụ: Route A: Đột Kích Tiên Phong)")
    branch_type: Literal[
        "action_heroic", "stealth_investigation", "dark_mystery",
        "tactical_compromise", "tragic_sacrifice", "forbidden_alliance", "custom"
    ] = Field(default="action_heroic", description="Phân loại phong cách nhánh truyện")
    choice_trigger: str = Field(..., description="Lựa chọn hoặc hành động kích hoạt nhánh này")
    synopsis: str = Field(..., description="Tóm tắt kịch bản diễn biến nhánh truyện")
    central_conflict: str = Field(default="", description="Mâu thuẫn trọng tâm trong nhánh này")
    key_twist: str = Field(default="", description="Cú twist hoặc biến cố bất ngờ xảy ra ở nhánh này")
    character_impacts: dict[str, str] = Field(
        default_factory=dict,
        description="Tác động tâm lý/vị thế nhân vật (ví dụ: {'Ren': 'Giải phóng 30% ấn chú, mệt mỏi thể xác'})"
    )
    consequences: list[str] = Field(
        default_factory=list,
        description="Hệ quả trực tiếp và lâu dài đối với thế giới và cốt truyện"
    )
    scenes: list[ScenePlan] = Field(
        default_factory=list,
        description="Danh sách các phân cảnh chi tiết triển khai nhánh truyện"
    )
    cliffhanger: str = Field(default="", description="Điểm kết lửng kích thích người đọc chọn tiếp")
    next_decision_prompt: str | None = Field(default=None, description="Gợi ý ngã rẽ quyết định tiếp theo")

    @field_validator("branch_type", mode="before")
    @classmethod
    def _norm_branch_type(cls, v: Any) -> str:
        val = str(v or "action_heroic").lower().strip().replace("-", "_").replace(" ", "_")
        allowed = {
            "action_heroic", "stealth_investigation", "dark_mystery",
            "tactical_compromise", "tragic_sacrifice", "forbidden_alliance", "custom"
        }
        return val if val in allowed else "action_heroic"

    @field_validator("scenes", mode="before")
    @classmethod
    def _clean_branch_scenes(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        cleaned = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, BaseModel):
                cleaned.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item = dict(item)
            if not item.get("title"):
                item["title"] = f"Phân đoạn {idx}"
            if not item.get("location"):
                item["location"] = "Hiện trường phân nhánh"
            if not item.get("summary"):
                item["summary"] = item["title"]
            cleaned.append(item)
        return cleaned


class BranchingProgression(BaseModel):
    """Cấu trúc diễn tiến phân nhánh đa chiều của chương manga (Route A, Route B, Route C)."""
    series_title: str = Field(default="", description="Tên bộ truyện")
    chapter_number: int = Field(default=1, description="Số thứ tự chương gốc")
    decision_point: str = Field(..., description="Nút thắt quyết định nơi cốt truyện chia nhánh")
    decision_context: str = Field(default="", description="Bối cảnh và tiền đề trước khi người đọc đưa ra lựa chọn")
    routes: list[StoryBranch] = Field(..., description="Danh sách các nhánh rẽ (Route A, Route B, Route C...)")
    reader_choices: list[ReaderChoice] = Field(
        default_factory=list,
        description="Danh sách các lựa chọn tương ứng mở khóa từng nhánh"
    )
    divergence_analysis: str = Field(
        default="",
        description="Phân tích sự khác biệt tư tưởng, nhịp điệu và hệ quả giữa các route"
    )
    recommended_route: str = Field(default="route_a", description="Route khuyến nghị bởi Story Director")


class BranchingProgressionRequest(BaseModel):
    """Tham số yêu cầu sinh cốt truyện phân nhánh đa chiều."""
    series_title: str = Field(..., description="Tên bộ truyện")
    genre: str = Field(default="Shonen Manga", description="Thể loại bộ truyện")
    art_style: Literal["b_w", "color"] = Field(default="b_w", description="Phong cách tranh manga")
    premise: str = Field(..., description="Tiền đề cốt truyện hoặc tóm tắt chương hiện tại")
    chapter_number: int = Field(default=1, description="Số thứ tự chương")
    chapter_title: str | None = Field(default=None, description="Tên chương")
    current_scene_context: str = Field(default="", description="Bối cảnh cảnh hiện tại dẫn tới nút thắt")
    decision_prompt: str = Field(
        default="Đứng trước tình thế ngàn cân treo sợi tóc, hãy chọn hướng đi:",
        description="Câu hỏi ngã rẽ đặt ra"
    )
    characters: list[CharacterProfile] = Field(default_factory=list, description="Hồ sơ nhân vật tham gia")
    canon_facts: list[CanonFact] = Field(default_factory=list, description="Luật thế giới bắt buộc tuân thủ")
    timeline_events: list[TimelineEvent] = Field(default_factory=list, description="Dòng sự kiện")
    branch_count: int = Field(default=3, ge=2, le=5, description="Số lượng nhánh cần tạo (mặc định 3: Route A, B, C)")
    scenes_per_branch: int = Field(default=2, ge=1, le=4, description="Số phân cảnh trong mỗi nhánh")
    panels_per_scene: int = Field(default=2, ge=1, le=4, description="Số panel trong mỗi phân cảnh")
    user_instructions: str | None = Field(default=None, description="Chỉ đạo bổ sung của tác giả")


class BranchingProgressionResponse(BaseModel):
    """Kết quả sinh cấu trúc phân nhánh đa chiều."""
    progression: BranchingProgression
    raw_model_response: str | None = None
    mode_used: Literal["ollama", "cloud", "fallback_template"] = "ollama"
    model_name: str = "qwen3.5:4b"
    generation_time_ms: int = 0


class PlotTwistSuggestion(BaseModel):
    """Gợi ý nút thắt bất ngờ (Plot Twist) cho cốt truyện."""
    id: str = Field(default_factory=lambda: f"twist_{uuid.uuid4().hex[:6]}")
    title: str = Field(..., description="Tiêu đề nút thắt (ví dụ: Thân Phận Kẻ Phản Bội)")
    twist_type: Literal[
        "identity_reveal", "betrayal", "false_victory",
        "hidden_motive", "world_rule_inversion", "forbidden_origin", "tragic_sacrifice"
    ] = Field(default="identity_reveal", description="Phân loại nút thắt cốt truyện")
    summary: str = Field(..., description="Chi tiết cú twist và tác động đến câu chuyện")
    impact_level: Literal["subtle", "moderate", "seismic"] = Field(
        default="moderate", description="Mức độ chấn động: subtle (tinh tế), moderate (vừa phải), seismic (đảo lộn đại cục)"
    )
    foreshadowing_clues: list[str] = Field(
        default_factory=list,
        description="Các chi tiết cài cắm manh mối (foreshadowing) ở các phân đoạn trước"
    )
    character_reactions: dict[str, str] = Field(
        default_factory=dict,
        description="Phản ứng tâm lý và hành động của từng nhân vật khi nút thắt bộc lộ"
    )
    compatible_routes: list[str] = Field(
        default_factory=list,
        description="Các nhánh route phù hợp lồng ghép nút thắt này (ví dụ: ['route_b', 'route_c'])"
    )

    @field_validator("twist_type", mode="before")
    @classmethod
    def _norm_twist_type(cls, v: Any) -> str:
        val = str(v or "identity_reveal").lower().strip().replace("-", "_").replace(" ", "_")
        allowed = {
            "identity_reveal", "betrayal", "false_victory",
            "hidden_motive", "world_rule_inversion", "forbidden_origin", "tragic_sacrifice"
        }
        return val if val in allowed else "identity_reveal"

    @field_validator("impact_level", mode="before")
    @classmethod
    def _norm_impact(cls, v: Any) -> str:
        val = str(v or "moderate").lower().strip()
        return val if val in {"subtle", "moderate", "seismic"} else "moderate"


class CharacterConflict(BaseModel):
    """Mâu thuẫn hoặc xung đột giữa các nhân vật (Character Conflict)."""
    id: str = Field(default_factory=lambda: f"conflict_{uuid.uuid4().hex[:6]}")
    characters_involved: list[str] = Field(..., description="Danh sách nhân vật trong cuộc đối đầu")
    conflict_type: Literal[
        "ideological", "personal_grudge", "resource_or_power", "loyalty_dilemma", "clashing_methods"
    ] = Field(default="ideological", description="Phân loại xung đột")
    core_friction: str = Field(..., description="Điểm va chạm mâu thuẫn cốt lõi")
    escalation_triggers: list[str] = Field(
        default_factory=list,
        description="Những sự kiện hoặc lời nói đẩy xung đột lên cao trào"
    )
    resolution_paths: list[str] = Field(
        default_factory=list,
        description="Các hướng giải quyết khả dĩ cho mâu thuẫn này"
    )
    narrative_tension_score: int = Field(default=7, ge=1, le=10, description="Mức độ căng thẳng trên thang 1-10")

    @field_validator("conflict_type", mode="before")
    @classmethod
    def _norm_conflict_type(cls, v: Any) -> str:
        val = str(v or "ideological").lower().strip().replace("-", "_").replace(" ", "_")
        allowed = {"ideological", "personal_grudge", "resource_or_power", "loyalty_dilemma", "clashing_methods"}
        return val if val in allowed else "ideological"


class PlotTwistAndChoiceRequest(BaseModel):
    """Yêu cầu gợi ý nút thắt cốt truyện, xung đột nhân vật và lựa chọn độc giả."""
    series_title: str = Field(..., description="Tên bộ truyện")
    genre: str = Field(default="Shonen Manga", description="Thể loại")
    current_context: str = Field(..., description="Tình huống và bối cảnh hiện tại của cốt truyện")
    characters: list[CharacterProfile] = Field(default_factory=list, description="Nhân vật tham gia")
    canon_facts: list[CanonFact] = Field(default_factory=list, description="Luật canon thế giới")
    num_twists: int = Field(default=3, ge=1, le=6, description="Số lượng plot twists mong muốn")
    num_conflicts: int = Field(default=2, ge=1, le=5, description="Số lượng xung đột nhân vật")
    num_choices: int = Field(default=3, ge=1, le=6, description="Số lượng lựa chọn độc giả")
    user_instructions: str | None = Field(default=None, description="Định hướng của tác giả")


class PlotTwistAndChoiceResponse(BaseModel):
    """Kết quả gợi ý nút thắt cốt truyện, xung đột nhân vật và lựa chọn người đọc."""
    plot_twists: list[PlotTwistSuggestion] = Field(default_factory=list)
    character_conflicts: list[CharacterConflict] = Field(default_factory=list)
    reader_choices: list[ReaderChoice] = Field(default_factory=list)
    editor_notes: str = Field(default="", description="Nhận định của Biên kịch Manga Studio")
    mode_used: Literal["ollama", "cloud", "fallback_template"] = "ollama"
    model_name: str = "qwen3.5:4b"
    generation_time_ms: int = 0


# ==============================================================================
# 2. JSON Extraction & Robust Parsing Utilities
# ==============================================================================

def extract_json_payload(raw_text: str) -> dict[str, Any]:
    """
    Trích xuất và sửa chữa JSON từ phản hồi LLM (kể cả khi model có <think>, code block hoặc text rác).
    """
    cleaned = raw_text.strip()

    # Bỏ qua khối suy nghĩ <think>...</think> nếu có từ Qwen reasoning
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE).strip()

    # Nếu có khối markdown ```json ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if code_block_match:
        cleaned = code_block_match.group(1).strip()

    # Tìm vị trí bắt đầu { và kết thúc }
    start_brace = cleaned.find("{")
    end_brace = cleaned.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        json_candidate = cleaned[start_brace : end_brace + 1]
    else:
        json_candidate = cleaned

    try:
        return json.loads(json_candidate)
    except json.JSONDecodeError:
        pass

    # Sửa một số lỗi JSON thường gặp của mô hình 4B
    # 1. Bỏ dấu phẩy thừa trước dấu đóng ngoặc
    repaired = re.sub(r",\s*([}\]])", r"\1", json_candidate)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 2. Xóa các ký tự điều khiển ASCII không hợp lệ
    repaired = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as err:
        # 3. Cứu dữ liệu JSON bị cắt ngang hoặc thiếu dấu đóng ngoặc
        # Cắt bỏ phần đuôi lỗi tại dấu '}' hợp lệ gần nhất và tự đóng stack ngoặc mở
        stack: list[str] = []
        in_str = False
        esc = False
        valid_cut_points: list[tuple[int, list[str]]] = []
        for idx, ch in enumerate(repaired):
            if esc:
                esc = False
                continue
            if ch == "\\" and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch in "{[":
                    stack.append("}" if ch == "{" else "]")
                elif ch in "}]":
                    if stack and stack[-1] == ch:
                        stack.pop()
                    if ch == "}":
                        valid_cut_points.append((idx + 1, list(stack)))

        for cut_idx, rem_stack in reversed(valid_cut_points):
            candidate = repaired[:cut_idx].rstrip(", \t\r\n") + "".join(reversed(rem_stack))
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                res = json.loads(candidate)
                if isinstance(res, dict) and res.get("scenes"):
                    logger.info("Recovered truncated/malformed JSON cleanly up to char %d", cut_idx)
                    return res
            except json.JSONDecodeError:
                continue

        logger.warning(f"Failed to parse JSON after repairs: {err}. Snippet: {repaired[:150]}")
        raise ValueError(f"Không thể giải mã cấu trúc JSON từ mô hình: {err}") from err


# ==============================================================================
# 3. ComfyUI 2D Diffusion Prompt Builder
# ==============================================================================

CAMERA_PROMPTS: dict[str, str] = {
    "close_up": "close-up shot, intense facial expression, face focus",
    "extreme_close_up": "extreme close-up, expressive eyes, dramatic detail",
    "medium_shot": "medium shot, waist up, dynamic character pose",
    "wide_shot": "wide shot, full scene, environmental storytelling, dramatic composition",
    "full_shot": "full body shot, heroic stance, clear action silhouette",
    "low_angle": "low angle shot, looking up, imposing presence, dramatic perspective",
    "high_angle": "high angle shot, looking down, bird's eye view, vulnerable perspective",
    "over_the_shoulder": "over the shoulder shot, dialogue framing, cinematic composition",
    "dutch_angle": "dutch angle, tilted camera angle, psychological tension, dynamic manga frame",
}

STYLE_PROMPTS: dict[str, str] = {
    "b_w": "masterpiece, best quality, ultra-detailed manga drawing, black and white manga, screentone, ink lines, hatching, clean lineart, shonen manga aesthetic, comic page layout",
    "color": "masterpiece, best quality, vibrant japanese anime aesthetic, clean cel shading, high quality anime coloring, crisp lineart, digital illustration",
}

NEGATIVE_DEFAULT: str = (
    "bad anatomy, bad hands, extra limbs, missing fingers, deformed, blurry, low quality, "
    "realistic, photorealistic, 3d render, watermark, signature, speech bubbles, text, letters, border, split panel"
)


def build_panel_diffusion_prompt(
    panel: PanelPlan,
    characters: list[CharacterProfile],
    art_style: str = "b_w"
) -> tuple[str, str]:
    """
    Sinh cặp (positive_prompt, negative_prompt) chuẩn cho ComfyUI 2D Manga Diffusion
    dựa trên locked traits của nhân vật, góc quay và phong cách truyện.
    """
    char_map = {c.name.strip().lower(): c for c in characters}
    positive_parts: list[str] = []

    # 1. Style cốt lõi
    positive_parts.append(STYLE_PROMPTS.get(art_style, STYLE_PROMPTS["b_w"]))

    # 2. Góc máy
    cam_tag = CAMERA_PROMPTS.get(panel.camera_angle, "medium shot, dynamic composition")
    positive_parts.append(cam_tag)

    # 3. Locked traits của các nhân vật xuất hiện trong panel
    char_tags: list[str] = []
    neg_tags: list[str] = [NEGATIVE_DEFAULT]

    for char_name in panel.characters_in_panel:
        key = char_name.strip().lower()
        if key in char_map:
            c = char_map[key]
            lt = c.locked_traits
            traits_list: list[str] = []
            if lt.diffusion_positive_tags:
                traits_list.append(lt.diffusion_positive_tags)
            else:
                if lt.gender != "unspecified":
                    traits_list.append(f"1{lt.gender}" if lt.gender in ("boy", "girl", "man", "woman") else lt.gender)
                if lt.hair_color:
                    traits_list.append(f"{lt.hair_color} hair")
                if lt.hair_style:
                    traits_list.append(lt.hair_style)
                if lt.eye_color:
                    traits_list.append(f"{lt.eye_color} eyes")
                if lt.signature_outfit:
                    traits_list.append(lt.signature_outfit)
                if lt.facial_features:
                    traits_list.extend(lt.facial_features)

            if traits_list:
                char_tags.append(", ".join(traits_list))

            if lt.diffusion_negative_tags:
                neg_tags.append(lt.diffusion_negative_tags)

    if char_tags:
        positive_parts.append(" ; ".join(char_tags))

    # 4. Mô tả hình ảnh chi tiết và không khí
    if panel.visual_description:
        positive_parts.append(panel.visual_description.strip().rstrip("."))
    if panel.lighting_and_atmosphere:
        positive_parts.append(panel.lighting_and_atmosphere)

    final_positive = ", ".join(p for p in positive_parts if p)
    final_negative = ", ".join(n for n in neg_tags if n)
    return final_positive, final_negative


# ==============================================================================
# 4. Deterministic Continuity Engine (Machine-verifiable QA)
# ==============================================================================

def check_deterministic_continuity(
    chapter: ChapterPlan,
    characters: list[CharacterProfile],
    canon_facts: list[CanonFact],
    timeline_events: list[TimelineEvent]
) -> list[ContinuityIssue]:
    """
    Kiểm tra tính nhất quán có thể kiểm chứng được bằng thuật toán tất định (deterministic rules).
    Đảm bảo phát hiện lỗi chắc chắn kể cả khi không gọi LLM hoặc LLM bị thiếu sót.
    """
    issues: list[ContinuityIssue] = []
    char_dict = {c.name.strip(): c for c in characters}
    char_names_lower = {c.name.strip().lower(): c for c in characters}

    # 1. Kiểm tra từng phân cảnh và ô tranh
    for scene in chapter.scenes:
        scene_chars = {name.strip().lower() for name in scene.characters_present}

        for panel in scene.panels:
            # 1.1 Nhân vật nói thoại có mặt trong scene không?
            for dia in panel.dialogues:
                spk = dia.speaker.strip()
                if spk in ("Người dẫn chuyện", "Dẫn chuyện", "Narrator", "Voice", "Tiếng động", "Giọng nói"):
                    continue

                spk_lower = spk.lower()
                if spk_lower in char_names_lower and spk_lower not in scene_chars:
                    issues.append(
                        ContinuityIssue(
                            issue_type="location_jump",
                            severity="critical",
                            entity_affected=spk,
                            description=f"Nhân vật '{spk}' phát ngôn trong cảnh '{scene.title}' nhưng không có tên trong danh sách nhân vật có mặt tại hiện trường.",
                            quote_or_location=f"Cảnh {scene.scene_number}, Panel {panel.panel_number}: '{dia.text[:60]}...'",
                            fix_suggestion=f"Thêm '{spk}' vào danh sách nhân vật có mặt của cảnh hoặc đổi người phát ngôn."
                        )
                    )

                # 1.2 Kiểm tra quy tắc khẩu khí (Speech Rules) và từ cấm
                if spk_lower in char_names_lower:
                    c_profile = char_names_lower[spk_lower]
                    rules = c_profile.speech_rules

                    # Kiểm tra từ cấm (forbidden words)
                    for fword in rules.forbidden_words:
                        if fword.lower() in dia.text.lower():
                            issues.append(
                                ContinuityIssue(
                                    issue_type="speech_rule_violation",
                                    severity="critical",
                                    entity_affected=spk,
                                    description=f"Nhân vật '{spk}' sử dụng từ cấm kỵ '{fword}' vi phạm hồ sơ SpeechRules.",
                                    quote_or_location=f"Cảnh {scene.scene_number}: \"{dia.text}\"",
                                    fix_suggestion=f"Thay thế từ '{fword}' bằng cách diễn đạt phù hợp phong thái nhân vật."
                                )
                            )

                    # Kiểm tra xưng hô ngôi thứ nhất nếu đã khóa chặt
                    # Ví dụ: Nhân vật quy định xưng "tớ" nhưng lại xưng "ta" hoặc "bản tọa"
                    if rules.first_person in ("tớ", "em", "cháu") and re.search(r"\b(ta|bản tọa|lão phu|trẫm)\b", dia.text, re.IGNORECASE):
                        issues.append(
                            ContinuityIssue(
                                issue_type="speech_rule_violation",
                                severity="warning",
                                entity_affected=spk,
                                description=f"Nhân vật '{spk}' quy định xưng hô ngôi thứ nhất là '{rules.first_person}' nhưng trong thoại lại xưng đại từ cao ngạo trái tính cách.",
                                quote_or_location=dia.text[:80],
                                fix_suggestion=f"Sửa xưng hô ngôi thứ nhất thành '{rules.first_person}'."
                            )
                        )

            # 1.3 Kiểm tra Locked Traits trong Prompt hình ảnh và Mô tả thị giác
            chars_in_p = list(getattr(panel, "characters_in_panel", []))
            for extra_attr in ("characters_present", "characters"):
                if hasattr(panel, extra_attr) and getattr(panel, extra_attr):
                    chars_in_p.extend(getattr(panel, extra_attr))
            for c_name in char_names_lower:
                if c_name in panel.visual_description.lower() or any(c_name == (d.speaker or "").lower() for d in panel.dialogues):
                    if c_name not in [x.lower() for x in chars_in_p]:
                        chars_in_p.append(c_name)

            for p_char in chars_in_p:
                p_key = p_char.strip().lower()
                if p_key in char_names_lower:
                    c_profile = char_names_lower[p_key]
                    lt = c_profile.locked_traits

                    # 1.3.1 Tóc: Ví dụ tóc đen nhưng mô tả blonde/vàng/bạc
                    if lt.hair_color and lt.hair_color.lower() in ("black", "đen"):
                        if re.search(r"\b(blonde|yellow|white)\s+hair\b", panel.diffusion_prompt_en, re.IGNORECASE) or \
                           re.search(r"tóc\s+(vàng|bạch kim|trắng|đỏ)", panel.visual_description, re.IGNORECASE):
                            issues.append(
                                ContinuityIssue(
                                    issue_type="appearance_conflict",
                                    severity="critical",
                                    entity_affected=c_profile.name,
                                    description=f"Panel {panel.panel_number} mô tả tóc khác với Locked Trait ({lt.hair_color}) của nhân vật '{c_profile.name}'.",
                                    quote_or_location=panel.visual_description[:90] or panel.diffusion_prompt_en[:90],
                                    fix_suggestion=f"Đồng bộ lại: dùng tóc màu '{lt.hair_color}'."
                                )
                            )

                    # 1.3.2 Mắt: Ví dụ mắt hổ phách nhưng mô tả mắt đỏ rực / xanh
                    if lt.eye_color:
                        lt_eye = lt.eye_color.lower()
                        if "hổ phách" in lt_eye or "amber" in lt_eye:
                            if re.search(r"mắt\s+(màu\s+)?(đỏ|xanh|đen)", panel.visual_description, re.IGNORECASE) or \
                               re.search(r"\b(red|blue|crimson)\s+eyes\b", panel.diffusion_prompt_en, re.IGNORECASE):
                                issues.append(
                                    ContinuityIssue(
                                        issue_type="appearance_conflict",
                                        severity="critical",
                                        entity_affected=c_profile.name,
                                        description=f"Panel {panel.panel_number} mô tả mắt khác với Locked Trait mắt '{lt.eye_color}' của nhân vật '{c_profile.name}'.",
                                        quote_or_location=panel.visual_description[:90] or panel.diffusion_prompt_en[:90],
                                        fix_suggestion=f"Đồng bộ lại màu mắt: dùng mắt '{lt.eye_color}'."
                                    )
                                )
                        elif "đen" in lt_eye or "black" in lt_eye:
                            if re.search(r"mắt\s+(màu\s+)?(đỏ|xanh|vàng)", panel.visual_description, re.IGNORECASE):
                                issues.append(
                                    ContinuityIssue(
                                        issue_type="appearance_conflict",
                                        severity="critical",
                                        entity_affected=c_profile.name,
                                        description=f"Panel {panel.panel_number} mô tả mắt khác với Locked Trait mắt '{lt.eye_color}' của nhân vật '{c_profile.name}'.",
                                        quote_or_location=panel.visual_description[:90],
                                        fix_suggestion=f"Đồng bộ lại màu mắt: dùng mắt '{lt.eye_color}'."
                                    )
                                )

    # 2. Kiểm tra xung đột quy tắc thế giới (Canon Facts)
    for fact in canon_facts:
        if fact.severity == "immutable":
            # Ví dụ: "không thể hồi sinh người chết"
            forbidden_patterns = []
            if "không thể" in fact.fact.lower():
                forbidden_patterns.append(fact.fact)

            for scene in chapter.scenes:
                for panel in scene.panels:
                    for dia in panel.dialogues:
                        # Kiểm tra mâu thuẫn trực tiếp với từ khóa cấm kỵ
                        if "hồi sinh người chết" in fact.fact.lower() and "hồi sinh người chết thành công" in dia.text.lower():
                            issues.append(
                                ContinuityIssue(
                                    issue_type="canon_fact_contradiction",
                                    severity="critical",
                                    entity_affected=fact.title,
                                    description=f"Tình tiết mâu thuẫn trực tiếp với Canon Fact bất biến: '{fact.fact}'",
                                    quote_or_location=dia.text,
                                    fix_suggestion="Điều chỉnh thoại hoặc biến cố để không vi phạm luật thế giới bất biến."
                                )
                            )

    return issues


# ==============================================================================
# 5. Deterministic Fallback Generator (Offline / Mock Safe)
# ==============================================================================

def generate_fallback_chapter(req: StoryGenerationRequest) -> ChapterPlan:
    """
    Sinh dàn ý kịch bản manga tiếng Việt hoàn chỉnh theo mẫu chuẩn
    khi Ollama offline hoặc khi đang chạy unit test tự động.
    """
    c_p1 = req.characters[0] if req.characters else CharacterProfile(name="Kurogane Ren", one_line_summary="Học sinh mang dấu ấn cấm thuật")
    c_p2 = req.characters[1] if len(req.characters) > 1 else CharacterProfile(name="Shirakawa Luna", one_line_summary="Hội trưởng học sinh gương mẫu")

    ch_num = req.chapter_number
    ch_title = req.chapter_title or f"Chương {ch_num}: Khởi Đầu Bí Ẩn"

    # Xưng hô chuẩn theo SpeechRules của từng nhân vật
    p1_first = c_p1.speech_rules.first_person or "tớ"
    p1_sec = c_p1.speech_rules.second_person or "cậu"
    p2_first = c_p2.speech_rules.first_person or "tôi"
    p2_sec = c_p2.speech_rules.second_person or "bạn"

    scenes: list[ScenePlan] = []

    # Scene 1: Mở màn và thiết lập bối cảnh
    p1_1 = PanelPlan(
        panel_number=1,
        layout_hint="wide",
        camera_angle="wide_shot",
        visual_description=f"Toàn cảnh sân trường dưới bầu trời nhá nhem tối. Gió thổi tung những chiếc lá phong, tạo cảm giác tĩnh mịch.",
        characters_in_panel=[c_p1.name],
        diffusion_prompt_en=f"masterpiece, wide shot, school campus at dusk, windy autumn atmosphere, dramatic lighting, monochrome manga, screentone",
        dialogues=[
            DialogueLine(speaker="Người dẫn chuyện", text=f"Thời khắc giao thoa giữa ánh sáng và bóng tối luôn ẩn chứa những bí mật không lời đáp...", bubble_type="narrator"),
            DialogueLine(speaker=c_p1.name, text=f"{p1_sec.capitalize()} có nghe thấy tiếng chuông gác mái vừa reo không?", bubble_type="speech")
        ],
        sfx=[PanelSFX(text="VÙÙÙ...", meaning="Tiếng gió rít qua gác chuông")]
    )
    p1_2 = PanelPlan(
        panel_number=2,
        layout_hint="standard",
        camera_angle="medium_shot",
        visual_description=f"{c_p2.name} đứng khoanh tay dưới tán cây anh đào cổ thụ, ánh mắt nghiêm nghị quan sát {c_p1.name}.",
        characters_in_panel=[c_p2.name],
        diffusion_prompt_en=f"masterpiece, medium shot, female student standing under ancient tree, stern expression, wind blowing hair, clean lineart",
        dialogues=[
            DialogueLine(speaker=c_p2.name, text=f"Giờ này {p2_sec} vẫn chưa về ký túc xá sao? Nội quy nghiêm cấm bén mảng tới khu cấm địa này.", bubble_type="speech")
        ]
    )
    p1_3 = PanelPlan(
        panel_number=3,
        layout_hint="tall",
        camera_angle="close_up",
        visual_description=f"Cận cảnh nụ cười bí ẩn của {c_p1.name}, bàn tay khẽ chạm vào vết bùa phong ấn trên cổ tay.",
        characters_in_panel=[c_p1.name],
        diffusion_prompt_en=f"masterpiece, close-up shot, confident young man smiling mysteriously, glowing seal on wrist, intense gaze",
        dialogues=[
            DialogueLine(speaker=c_p1.name, text=f"Nội quy chỉ áp dụng cho người bình thường thôi, {c_p2.name} à.", bubble_type="speech")
        ],
        sfx=[PanelSFX(text="XOẸT!", meaning="Tia sáng ma lực phát ra từ phong ấn")]
    )
    scenes.append(
        ScenePlan(
            scene_number=1,
            title="Cuộc Gặp Gỡ Lúc Hoàng Hôn",
            location="Khuôn viên Học Viện Cổ",
            time_of_day="sunset",
            summary=f"{c_p1.name} và {c_p2.name} chạm mặt nhau tại khu vực cấm trước khi màn đêm buông xuống.",
            characters_present=[c_p1.name, c_p2.name],
            emotional_beat="tension",
            conflict="Nguy cơ bị phát hiện vi phạm giờ giới nghiêm",
            outcome="Hai người nhận ra cả hai cùng đang truy tìm một bí mật chung",
            panels=[p1_1, p1_2, p1_3]
        )
    )

    # Scene 2: Bước ngoặt / Khám phá
    p2_1 = PanelPlan(
        panel_number=1,
        layout_hint="standard",
        camera_angle="low_angle",
        visual_description="Cánh cửa sắt của căn phòng cấm rỉ sét từ từ hé mở, luồng khói đen bí ẩn cuồn cuộn tràn ra sàn đá.",
        characters_in_panel=[c_p1.name, c_p2.name],
        diffusion_prompt_en="masterpiece, low angle, ancient iron door opening, mystical dark smoke pouring out, high contrast ink lines",
        dialogues=[
            DialogueLine(speaker=c_p2.name, text="Coi chừng! Có dòng ma lực dị thường đang dao động!", bubble_type="shout")
        ],
        sfx=[PanelSFX(text="KẸT... ẦM!", meaning="Cánh cửa nặng nề bật mở")]
    )
    p2_2 = PanelPlan(
        panel_number=2,
        layout_hint="splash",
        camera_angle="wide_shot",
        visual_description="Bên trong căn phòng là phiến đá cổ khắc đầy ký tự phát sáng. Một bóng đen khổng lồ đang thức tỉnh.",
        characters_in_panel=[c_p1.name, c_p2.name],
        diffusion_prompt_en="masterpiece, splash page, monumental glowing ancient monolith, shadowy beast awakening, breathtaking manga scale",
        dialogues=[
            DialogueLine(speaker=c_p1.name, text=f"Đúng như suy đoán của {p1_first}... Dấu vết phong ấn 10 năm trước nằm ở đây!", bubble_type="thought")
        ]
    )
    scenes.append(
        ScenePlan(
            scene_number=2,
            title="Cánh Cửa Bị Nguyền Rủa",
            location="Căn hầm thư viện cấm",
            time_of_day="night",
            summary="Cả hai cùng tiến vào căn hầm bí mật và đối mặt với thực thể bóng tối thức tỉnh.",
            characters_present=[c_p1.name, c_p2.name],
            emotional_beat="mystery",
            conflict="Bóng ma bảo vệ phong ấn xuất hiện tấn công",
            outcome="Phát hiện sự thật lịch sử của sự kiện Đêm Trăng Đỏ",
            panels=[p2_1, p2_2]
        )
    )

    # Đảm bảo mỗi panel đều có diffusion prompts đầy đủ
    for sc in scenes:
        for p in sc.panels:
            auto_pos, auto_neg = build_panel_diffusion_prompt(
                p, req.characters, req.art_style
            )
            if not p.diffusion_prompt_en:
                p.diffusion_prompt_en = auto_pos
            if not p.diffusion_negative_prompt:
                p.diffusion_negative_prompt = auto_neg

    return ChapterPlan(
        chapter_number=ch_num,
        title=ch_title,
        synopsis=f"Chương mở màn của {req.series_title}. {c_p1.name} và {c_p2.name} phát hiện bí mật bị che giấu tại học viện.",
        central_conflict=f"Mâu thuẫn giữa luật lệ học viện và sự thật đen tối mà {c_p1.name} đang kiếm tìm.",
        climax="Cánh cửa thư viện cấm bật mở, đánh thức bóng đen từ sự kiện quá khứ.",
        cliffhanger_or_ending="Thực thể bóng tối cất lời gọi tên thật của nhân vật chính, kết thúc chương trong hồi hộp.",
        scenes=scenes,
        estimated_pages=4,
        canon_references_used=[f.title for f in req.canon_facts[:3]],
        character_arcs_progressed=[c_p1.name, c_p2.name]
    )


def generate_fallback_branching_progression(req: BranchingProgressionRequest) -> BranchingProgression:
    """
    Sinh cấu trúc diễn tiến phân nhánh đa chiều hoàn chỉnh (Route A, Route B, Route C)
    theo chuẩn kịch bản Manga Studio khi offline hoặc khi chạy test tự động.
    """
    c_p1 = req.characters[0] if req.characters else CharacterProfile(name="Kurogane Ren", one_line_summary="Học sinh mang dấu ấn cấm thuật")
    c_p2 = req.characters[1] if len(req.characters) > 1 else CharacterProfile(name="Shirakawa Luna", one_line_summary="Hội trưởng học sinh gương mẫu")

    p1_first = c_p1.speech_rules.first_person or "tớ"
    p1_sec = c_p1.speech_rules.second_person or "cậu"
    p2_first = c_p2.speech_rules.first_person or "tôi"
    p2_sec = c_p2.speech_rules.second_person or "bạn"

    ch_num = req.chapter_number
    context_desc = req.current_scene_context or f"Tại tầng sâu nhất của gác chuông cấm, thực thể bóng tối thức tỉnh trước sự ngỡ ngàng của {c_p1.name} và {c_p2.name}."
    decision_pt = req.decision_prompt or "Thời khắc định đoạt số phận: Đối mặt trực diện, thâm nhập bóng tối, hay đàm phán cấm thuật?"

    # ==================== ROUTE A: Heroic Action Assault ====================
    route_a_panels = [
        PanelPlan(
            panel_number=1,
            layout_hint="wide",
            camera_angle="low_angle",
            visual_description=f"{c_p1.name} bước lên phía trước, giải phóng luồng hắc lôi bao bọc lấy cánh tay. Ánh mắt rực lửa quyết tâm bảo vệ {c_p2.name}.",
            characters_in_panel=[c_p1.name, c_p2.name],
            diffusion_prompt_en=f"masterpiece, low angle, brave young man unleashing black lightning from arm, glowing red eyes, heroic stance, female ally watching in awe",
            dialogues=[
                DialogueLine(speaker=c_p1.name, text=f"{p1_sec.capitalize()} lùi lại phía sau đi! Trận chiến này cứ để {p1_first} lo liệu!", bubble_type="shout"),
                DialogueLine(speaker=c_p2.name, text=f"Đừng liều mạng! Dòng ma lực đó sẽ xé toạc linh hồn {p2_sec} mất!", bubble_type="shout")
            ],
            sfx=[PanelSFX(text="XOẸT XOẸT! ĐÙNG!", meaning="Tiếng sét hắc ám bùng nổ")]
        ),
        PanelPlan(
            panel_number=2,
            layout_hint="splash",
            camera_angle="close_up",
            visual_description=f"Cú đấm bóng tối của {c_p1.name} va chạm trực diện với lõi năng lượng của quái thú. Vết nứt không gian xuất hiện, để lộ lõi bùa phong ấn trùng khớp với cấm ấn trên tay.",
            characters_in_panel=[c_p1.name],
            diffusion_prompt_en="masterpiece, dynamic impact, close up, dark energy punch colliding with glowing core, space cracking, intense shonen manga climax",
            dialogues=[
                DialogueLine(speaker=c_p1.name, text=f"Tan biến đi! {p1_first} sẽ không để bất kỳ ai phải hy sinh vô ích nữa!", bubble_type="shout")
            ],
            sfx=[PanelSFX(text="ẦM ẦM ẦM!", meaning="Sóng xung kích cực đại dội khắp căn phòng")]
        )
    ]
    scene_a = ScenePlan(
        scene_number=1,
        title="Tia Sét Xuyên Thủng Màn Đêm",
        location="Đấu trường Gác Chuông",
        time_of_day="night",
        summary=f"{c_p1.name} bung toả 50% sức mạnh cấm ấn, đánh tan hộ vệ hắc ám và phá vỡ kết giới tầng ngoài.",
        characters_present=[c_p1.name, c_p2.name],
        emotional_beat="action",
        conflict="Thể lực tiêu hao nghiêm trọng và sự hoài nghi của Luna về nguồn gốc cấm thuật",
        outcome="Tiêu diệt hộ vệ nhưng đánh động toàn bộ hệ thống báo động học viện",
        panels=route_a_panels
    )

    branch_a = StoryBranch(
        route_id="route_a",
        route_name="Route A: Đột Kích Tiên Phong (Heroic Assault)",
        branch_type="action_heroic",
        choice_trigger=f"{c_p1.name} quyết định dồn toàn lực đột kích trực diện, đối đầu trực tiếp với kẻ thù.",
        synopsis=f"Tuyến truyện hành động kịch tính: {c_p1.name} bộc phá sức mạnh cứu nguy tức thời, nhưng phải trả giá bằng việc cấm ấn thức tỉnh nhanh hơn.",
        central_conflict=f"Áp lực sinh tử đè nặng và nỗi sợ mất kiểm soát bản thân khi giải phóng ma lực cấm.",
        key_twist="Lõi của quái vật cấm địa thực chất chứa một mảnh linh hồn của người bạn thời thơ ấu đã mất tích 10 năm trước.",
        character_impacts={
            c_p1.name: "Cấm ấn bộc phát 45%, thể lực suy kiệt nhưng đạt được niềm tin từ Luna.",
            c_p2.name: "Tận mắt chứng kiến sức mạnh hủy diệt, vừa cảm phục vừa cảnh giác trước hiểm họa."
        },
        consequences=[
            "Hạ gục Hộ vệ Cổ Đại trong thời gian kỷ lục.",
            "Chuông báo động học viện vang lên, đặt hai người vào tầm ngắm của Hội đồng Trưởng lão."
        ],
        scenes=[scene_a],
        cliffhanger="Cánh cửa bảo mật cuối cùng mở ra, nhưng bên trong là một căn phòng rỗng cùng lời nhắn bí ẩn bằng máu.",
        next_decision_prompt="Nên phá hủy lời nhắn để che giấu dấu vết hay mang nó về phân tích?"
    )

    # ==================== ROUTE B: Stealth Investigation ====================
    route_b_panels = [
        PanelPlan(
            panel_number=1,
            layout_hint="standard",
            camera_angle="wide_shot",
            visual_description=f"{c_p2.name} kéo tay {c_p1.name} nấp sau dãy cột đá La Mã cổ đại. Nàng triển khai màng tàng hình ánh trăng thanh tẩy giấu kín hơi thở của cả hai.",
            characters_in_panel=[c_p1.name, c_p2.name],
            diffusion_prompt_en="masterpiece, wide shot, two students hiding behind ancient marble pillars, soft moonlight cloak concealing them, dark shadowy beast patrolling",
            dialogues=[
                DialogueLine(speaker=c_p2.name, text=f"Suỵt! Im lặng đi. Sinh vật đó chỉ phản ứng với dao động nhiệt và âm thanh thôi.", bubble_type="whisper"),
                DialogueLine(speaker=c_p1.name, text=f"{p1_sec.capitalize()} phát hiện ra đường vòng phía sau giá sách cấm rồi sao?", bubble_type="whisper")
            ],
            sfx=[PanelSFX(text="Gừừừ...", visual_style="ambient", meaning="Tiếng thở gầm gừ nặng nề của quái vật tuần tra")]
        ),
        PanelPlan(
            panel_number=2,
            layout_hint="tall",
            camera_angle="over_the_shoulder",
            visual_description=f"Góc nhìn qua vai {c_p2.name}: {c_p1.name} phát hiện một cuốn cổ tịch bìa da rồng phát sáng yếu ớt dưới khe đá bí mật.",
            characters_in_panel=[c_p1.name, c_p2.name],
            diffusion_prompt_en="masterpiece, over the shoulder shot, discovering glowing ancient leatherbound grimoire inside stone niche, intricate arcane symbols",
            dialogues=[
                DialogueLine(speaker=c_p1.name, text=f"Nhật ký của Viện trưởng đời thứ ba... Nó viết rằng phong ấn này dùng để che chở bí mật chứ không phải phong tỏa!", bubble_type="thought")
            ],
            sfx=[PanelSFX(text="TÁCH!", visual_style="motion", meaning="Chốt cơ quan đá khẽ nảy lên")]
        )
    ]
    scene_b = ScenePlan(
        scene_number=1,
        title="Lối Đi Giữa Những Chiếc Bóng",
        location="Hành lang Mật Thất Thư Viện",
        time_of_day="night",
        summary=f"{c_p2.name} và {c_p1.name} sử dụng chiến thuật luồn lách qua các góc khuất, giải mã thành công sơ đồ mật đạo ngầm.",
        characters_present=[c_p1.name, c_p2.name],
        emotional_beat="mystery",
        conflict="Nguy cơ bị phát hiện bởi bẫy âm thanh cổ xưa nếu di chuyển sơ suất",
        outcome="Thu thập hồ sơ mật thất mà không kích hoạt chuông cảnh báo",
        panels=route_b_panels
    )

    branch_b = StoryBranch(
        route_id="route_b",
        route_name="Route B: Xâm Nhập Trong Bóng Tối (Stealth Investigation)",
        branch_type="stealth_investigation",
        choice_trigger=f"Ẩn nấp vào bóng tối, tận dụng địa hình để điều tra và tránh giao tranh trực diện.",
        synopsis=f"Tuyến truyện trinh thám huyền bí: Hai nhân vật âm thầm tìm ra chân tướng lịch sử bị chôn vùi mà không gây đổ máu hay kinh động học viện.",
        central_conflict=f"Thời gian có hạn trước khi màn đêm kết thúc và câu đố cơ quan ma thuật ngày một hiểm hóc.",
        key_twist="Tài liệu bí mật chỉ ra rằng chính gia tộc danh giá Shirakawa là người đã tài trợ nghiên cứu cấm thuật 10 năm trước.",
        character_impacts={
            c_p1.name: "Hiểu rõ hơn về cội nguồn vết ấn trên cổ tay mình.",
            c_p2.name: "Tâm lý dao động dữ dội khi phát hiện gia tộc mình có dính líu đến thảm họa đen tối."
        },
        consequences=[
            "Giữ kín hoàn toàn tung tích, không ai hay biết cả hai đã vào khu cấm.",
            "Nắm giữ bằng chứng tài liệu có thể làm rung chuyển giới lãnh đạo học viện."
        ],
        scenes=[scene_b],
        cliffhanger="Một giọng nói trầm ấm cất lên từ góc tối nhất: 'Các em tìm kiếm điều đó lâu chưa?'",
        next_decision_prompt="Đối thoại để thăm dò đối phương hay sử dụng bom khói tẩu thoát ngay lập tức?"
    )

    # ==================== ROUTE C: Forbidden Alliance ====================
    route_c_panels = [
        PanelPlan(
            panel_number=1,
            layout_hint="wide",
            camera_angle="medium_shot",
            visual_description=f"{c_p1.name} hạ kiếm xuống, vươn tay ra và đọc vang chuỗi cổ ngữ phát sáng màu tím lam. Quái thú bóng tối khựng lại, đôi mắt hung bạo chuyển sang vẻ hoài niệm.",
            characters_in_panel=[c_p1.name, c_p2.name],
            diffusion_prompt_en="masterpiece, medium shot, young sorcerer chanting glowing runes with outstretched hand, colossal beast hesitating, mystical bonds forming",
            dialogues=[
                DialogueLine(speaker=c_p1.name, text="Hỡi linh hồn canh gác! Ta biết nỗi oan khuất của ngươi... Hãy lập khế ước tương thông!", bubble_type="speech"),
                DialogueLine(speaker=c_p2.name, text=f"{c_p1.name}, dừng lại! Khế ước cổ ngữ sẽ đồng hóa linh hồn của {p2_sec} vào bóng tối đấy!", bubble_type="shout")
            ],
            sfx=[PanelSFX(text="OONG... OONG...", visual_style="ambient", meaning="Cộng hưởng tần số ma pháp cổ xưa")]
        ),
        PanelPlan(
            panel_number=2,
            layout_hint="standard",
            camera_angle="dutch_angle",
            visual_description=f"Thực thể bóng tối phủ phục xuống trước mặt hai người, biến hóa thành một đốm sáng linh thể ký gửi trên chuôi kiếm của {c_p2.name}.",
            characters_in_panel=[c_p1.name, c_p2.name],
            diffusion_prompt_en="masterpiece, dutch angle, giant monster condensing into glowing spirit wisp, infusing into silver rapier, dramatic manga panel",
            dialogues=[
                DialogueLine(speaker=c_p2.name, text=f"Thanh kiếm của gia tộc... đang tiếp nhận năng lượng này sao? Chuyện này rốt cuộc là thế nào?!", bubble_type="thought")
            ],
            sfx=[PanelSFX(text="KENG!", meaning="Vũ khí được ban phước ma thuật bóng tối")]
        )
    ]
    scene_c = ScenePlan(
        scene_number=1,
        title="Hiệp Ước Của Kẻ Bị Nguyền Rủa",
        location="Trận Pháp Cổ Ngữ Trung Tâm",
        time_of_day="night",
        summary=f"{c_p1.name} mạo hiểm đàm phán thành công với linh thú hộ vệ, mở ra liên minh bất ngờ nhưng chịu ràng buộc khế ước.",
        characters_present=[c_p1.name, c_p2.name],
        emotional_beat="dramatic",
        conflict="Sự phản đối quyết liệt của Luna trước việc sử dụng ma thuật cấm kỵ",
        outcome="Linh thú trở thành đồng minh hộ thể nhưng đòi hỏi một cái giá trong tương lai",
        panels=route_c_panels
    )

    branch_c = StoryBranch(
        route_id="route_c",
        route_name="Route C: Đồng Minh Bất Đắc Dĩ (Forbidden Alliance)",
        branch_type="forbidden_alliance",
        choice_trigger="Thi triển cổ ngữ cấm kỵ để đàm phán khế ước hiệp ước với thực thể canh gác.",
        synopsis="Tuyến truyện kịch tính đầy mâu thuẫn đạo đức: Lựa chọn con đường thỏa hiệp với bóng tối để mở khóa sức mạnh mới và những bí ẩn chưa từng tiết lộ.",
        central_conflict=f"Xung đột sâu sắc giữa quy tắc danh dự của {c_p2.name} và tinh thần thực dụng sinh tồn của {c_p1.name}.",
        key_twist="Linh thú thực chất là hộ vệ do chính mẹ của Ren phong ấn để làm vệ binh bảo vệ cậu vào đúng sinh nhật 16 tuổi.",
        character_impacts={
            c_p1.name: "Ký thác linh hồn một phần vào khế ước, tăng 100% năng lực ma pháp hắc ám.",
            c_p2.name: "Đứng trước ngã ba đường: Báo cáo hành vi cấm thuật của Ren hay trở thành tòng phạm bảo vệ cậu."
        },
        consequences=[
            "Thu phục được linh thú thượng cổ làm trợ thủ đắc lực.",
            "Cả hai bị liên kết bởi lời thề máu, nếu một người bị thương người kia cũng chịu ảnh hưởng."
        ],
        scenes=[scene_c],
        cliffhanger="Dấu ấn khế ước đỏ rực xuất hiện trên mu bàn tay của cả Ren và Luna cùng một lúc.",
        next_decision_prompt="Nên cùng nhau tìm cách giải phong ấn hay chấp nhận sức mạnh này để đương đầu với kẻ thù sắp tới?"
    )

    routes = [branch_a, branch_b, branch_c]

    # Cập nhật prompt diffusion tự động cho mọi ô tranh trong các route
    for rt in routes:
        for sc in rt.scenes:
            for p in sc.panels:
                pos, neg = build_panel_diffusion_prompt(p, req.characters, req.art_style)
                if not p.diffusion_prompt_en:
                    p.diffusion_prompt_en = pos
                if not p.diffusion_negative_prompt:
                    p.diffusion_negative_prompt = neg

    # Reader Choices tương ứng
    choices = [
        ReaderChoice(
            choice_id="choice_route_a",
            route_target="route_a",
            text=f"Rút kiếm giải phóng Cấm Ấn, trực diện đập tan quái thú bóng tối!",
            intent_tone="aggressive",
            consequence_hint="Chiến thắng nhanh chóng nhưng tiêu hao thể lực và báo động toàn trường.",
            risk_reward="Rủi ro: Rất cao | Phần thưởng: Uy danh vang dội và cứu nguy tức thì."
        ),
        ReaderChoice(
            choice_id="choice_route_b",
            route_target="route_b",
            text="Ẩn nấp sau màng tàng hình, giải mã mật thất và thu thập tài liệu trong im lặng.",
            intent_tone="stealthy",
            consequence_hint="Bảo toàn sức lực và phát hiện bí mật đen tối của gia tộc lãnh đạo.",
            risk_reward="Rủi ro: Trung bình | Phần thưởng: Lợi thế thông tin tình báo tuyệt đối."
        ),
        ReaderChoice(
            choice_id="choice_route_c",
            route_target="route_c",
            text="Niệm cổ ngữ cấm kỵ, đàm phán lập hiệp ước ma pháp với thực thể thức tỉnh.",
            intent_tone="mysterious",
            consequence_hint="Khai mở sức mạnh bóng tối thượng thừa nhưng vướng vào lời nguyền khế ước đôi.",
            risk_reward="Rủi ro: Cực cao | Phần thưởng: Sức mạnh hộ mệnh vô song."
        )
    ]

    divergence_notes = (
        f"Phân tích phân kỳ kịch bản Manga: Tuyến truyện mở ra 3 triết lý đối lập:\n"
        f"1. Route A (Shonen Action): Ca ngợi sự dũng cảm và đột phá giới hạn bản thân trước hiểm nguy.\n"
        f"2. Route B (Seinen Mystery): Đi sâu vào giải đố, thuyết âm mưu và góc khuất chính trị học viện.\n"
        f"3. Route C (Dark Fantasy): Thử thách ranh giới thiện ác, đặt nhân vật vào thế tiến thoái lưỡng nan của sức mạnh bị nguyền rủa."
    )

    return BranchingProgression(
        series_title=req.series_title,
        chapter_number=ch_num,
        decision_point=decision_pt,
        decision_context=context_desc,
        routes=routes,
        reader_choices=choices,
        divergence_analysis=divergence_notes,
        recommended_route="route_a"
    )


def generate_fallback_plot_twists_and_choices(req: PlotTwistAndChoiceRequest) -> PlotTwistAndChoiceResponse:
    """
    Sinh các gợi ý Plot Twists chấn động, xung đột nhân vật sâu sắc và lựa chọn độc giả
    chuẩn cấu trúc Manga khi offline hoặc dùng làm dữ liệu kiểm thử.
    """
    c_p1_name = req.characters[0].name if req.characters else "Kurogane Ren"
    c_p2_name = req.characters[1].name if len(req.characters) > 1 else "Shirakawa Luna"

    twists = [
        PlotTwistSuggestion(
            id=f"twist_{uuid.uuid4().hex[:6]}",
            title="Thân Phận Thực Sự Của Kẻ Phản Bội",
            twist_type="identity_reveal",
            summary=f"Người thầy cố vấn hoặc đồng minh đáng tin cậy nhất của {c_p1_name} thực chất chính là Đại Tư Tế của Hội Trăng Đỏ ẩn thân suốt 10 năm.",
            impact_level="seismic",
            foreshadowing_clues=[
                "Chiếc đồng hồ quả quýt của người thầy luôn chạy chậm đúng 10 phút — mốc thời gian xảy ra thảm họa cổ.",
                "Lời khuyên tránh xa gác chuông thực chất là để ngăn phong ấn bị kích hoạt sớm."
            ],
            character_reactions={
                c_p1_name: "Bàng hoàng, sụp đổ niềm tin và tự trách vì đã để lộ bí mật phong ấn cho kẻ thù.",
                c_p2_name: "Nhanh chóng lấy lại lý trí, giương kiếm bảo vệ đồng đội và phong tỏa hiện trường."
            },
            compatible_routes=["route_a", "route_b"]
        ),
        PlotTwistSuggestion(
            id=f"twist_{uuid.uuid4().hex[:6]}",
            title="Nghịch Đảo Bản Chất Cấm Ấn Hắc Nguyệt",
            twist_type="world_rule_inversion",
            summary="Cấm ấn trên cổ tay không phải là lời nguyền hủy diệt, mà là chiếc chìa khóa phong tỏa một vết rách không gian có thể nuốt chửng cả lục địa.",
            impact_level="seismic",
            foreshadowing_clues=[
                "Mỗi khi cấm ấn đau nhức, các vết nứt địa chấn xung quanh học viện lại thu nhỏ lại.",
                "Ký tự bùa chú dùng chữ viết cổ của nền văn minh hộ quốc chứ không phải ma quỷ."
            ],
            character_reactions={
                c_p1_name: "Nhận thức được trách nhiệm to lớn, biến nỗi mặc cảm thành động lực chiến đấu.",
                c_p2_name: "Nhận ra định kiến của gia tộc mình về cấm thuật là hoàn toàn sai lầm."
            },
            compatible_routes=["route_b", "route_c"]
        ),
        PlotTwistSuggestion(
            id=f"twist_{uuid.uuid4().hex[:6]}",
            title="Chiến Thắng Trong Trận Trận Ảo Giác",
            twist_type="false_victory",
            summary=f"Sau khi tiêu diệt quái thú, hai nhân vật nhận ra họ chưa hề rời khỏi căn phòng đầu tiên; toàn bộ trận đánh chỉ là một bài sát hạch tâm trí do Viện trưởng thiết lập.",
            impact_level="moderate",
            foreshadowing_clues=[
                "Bóng đổ của các vật thể trong trận đánh luôn hướng về phía ngược lại với nguồn sáng đuốc.",
                "Mùi trầm hương thoang thoảng chỉ có trong phòng thiền viện trưởng."
            ],
            character_reactions={
                c_p1_name: "Cười nhạt nhận ra bài kiểm tra, thu hồi ma lực.",
                c_p2_name: "Tức giận vì cảm thấy phẩm giá học sinh bị đem ra đùa cợt."
            },
            compatible_routes=["route_a", "route_c"]
        )
    ]

    conflicts = [
        CharacterConflict(
            id=f"conflict_{uuid.uuid4().hex[:6]}",
            characters_involved=[c_p1_name, c_p2_name],
            conflict_type="ideological",
            core_friction=f"Xung đột giữa chủ nghĩa tuân thủ quy tắc nghiêm ngặt của {c_p2_name} và bản năng sinh tồn vượt rào của {c_p1_name}.",
            escalation_triggers=[
                f"{c_p1_name} tự ý phá hủy phong ấn cấm địa mà không chờ lệnh cấp trên.",
                f"{c_p2_name} đe dọa sẽ bắt giữ và giao nộp {c_p1_name} cho Hội đồng Kỷ luật."
            ],
            resolution_paths=[
                "Cùng đối mặt với mối nguy chung buộc phải đặt niềm tin sinh tử lên nhau.",
                "Một cuộc tỉ thí kiếm thuật công bằng để giải tỏa bức bối và thấu hiểu lý tưởng của đối phương."
            ],
            narrative_tension_score=8
        ),
        CharacterConflict(
            id=f"conflict_{uuid.uuid4().hex[:6]}",
            characters_involved=[c_p2_name, "Gia tộc Shirakawa"],
            conflict_type="loyalty_dilemma",
            core_friction=f"Mâu thuẫn giữa việc giữ tròn chữ hiếu bảo vệ danh dự gia tộc và lương tâm chính nghĩa khi phát hiện vết nhơ lịch sử.",
            escalation_triggers=[
                "Trưởng lão gia tộc ra tối hậu thư yêu cầu thủ tiêu mọi nhân chứng của thảm họa 10 năm trước.",
                "Bằng chứng tội ác của gia tộc rơi vào tay đối thủ cạnh tranh."
            ],
            resolution_paths=[
                f"{c_p2_name} đứng lên cải tổ gia tộc từ bên trong, chuộc lại lỗi lầm của tiền nhân.",
                "Chấp nhận từ bỏ quyền thừa kế để đứng về phía sự thật cùng nhóm bạn."
            ],
            narrative_tension_score=9
        )
    ]

    choices = [
        ReaderChoice(
            choice_id="choice_twist_assault",
            route_target="route_a",
            text=f"{c_p1_name} chọn liều lĩnh kích nổ phong ấn để mở đường máu đưa {c_p2_name} thoát hiểm.",
            intent_tone="aggressive",
            consequence_hint="Tạo ra cơ hội sống sót cao nhưng phá hủy hoàn toàn hiện trường mật thất.",
            risk_reward="Rủi ro: Mất đi manh mối quá khứ | Phần thưởng: Bảo vệ an toàn đồng đội."
        ),
        ReaderChoice(
            choice_id="choice_twist_infiltrate",
            route_target="route_b",
            text=f"Tiếp tục đóng kịch như chưa hề hay biết, âm thầm theo dõi hành tung của Kẻ Phản Bội.",
            intent_tone="tactical",
            consequence_hint="Giữ thế chủ động trong bóng tối nhưng phải chịu đựng cảm giác đồng hành cùng kẻ thù.",
            risk_reward="Rủi ro: Bị kẻ phản bội phát giác và gài bẫy | Phần thưởng: Bắt trọn ổ thế lực bóng tối."
        ),
        ReaderChoice(
            choice_id="choice_twist_contract",
            route_target="route_c",
            text="Công khai toàn bộ sự thật về cấm ấn trước toàn thể học sinh trong buổi lễ khai giảng.",
            intent_tone="diplomatic",
            consequence_hint="Gây chấn động dư luận, làm tê liệt mưu đồ ám sát của Trưởng lão.",
            risk_reward="Rủi ro: Trở thành tâm điểm tranh cãi | Phần thưởng: Thu hút sự bảo vệ từ công chúng."
        )
    ]

    return PlotTwistAndChoiceResponse(
        plot_twists=twists[:req.num_twists],
        character_conflicts=conflicts[:req.num_conflicts],
        reader_choices=choices[:req.num_choices],
        editor_notes="Các nút thắt và xung đột được thiết kế để tạo chiều sâu tâm lý đa diện và tăng tính hấp dẫn cho kịch bản phân nhánh.",
        mode_used="fallback_template",
        model_name="fallback",
        generation_time_ms=10
    )


# ==============================================================================
# 6. Story Studio AI Engine (Ollama / Qwen3.5:4B Bridge)
# ==============================================================================

DEFAULT_CHAPTER_NUM_PREDICT = 8192


def _compute_chapter_num_predict(scene_count: int, panels_per_scene: int) -> int:
    """Tính ngân sách token đầu ra đủ cho tối thiểu 2 trang (6-8+ ô) kèm reasoning."""
    total_panels = max(1, int(scene_count)) * max(1, int(panels_per_scene))
    return min(16384, max(DEFAULT_CHAPTER_NUM_PREDICT, total_panels * 750 + 2500))


def get_active_model_manager() -> Any:
    """Cố gắng tìm kiếm MODEL_MANAGER từ main.py nếu đã được nạp."""
    try:
        from main import MODEL_MANAGER
        return MODEL_MANAGER
    except Exception:
        try:
            from app.main import MODEL_MANAGER
            return MODEL_MANAGER
        except Exception:
            return None


class MangaStoryEngine:
    """
    Trái tim của Story Studio: Quản lý nhân vật, canon, dòng thời gian,
    sinh kịch bản chương và kiểm định tính nhất quán bằng tiếng Việt qua Ollama (qwen3.5:4b).
    """

    def __init__(self, model_manager: Any = None, default_model: str = "qwen3.5:4b") -> None:
        self._model_manager = model_manager
        self.default_model = default_model

    @property
    def model_manager(self) -> Any:
        if self._model_manager is not None:
            return self._model_manager
        return get_active_model_manager()

    @model_manager.setter
    def model_manager(self, mgr: Any) -> None:
        self._model_manager = mgr

    async def is_llm_ready(self) -> bool:
        """Kiểm tra xem Ollama/Cloud LLM có sẵn sàng suy luận hay không."""
        mgr = self.model_manager
        if mgr is None:
            return False
        try:
            ready, _ = await mgr.runtime_ready()
            return ready
        except Exception:
            return False

    async def generate_chapter(self, req: StoryGenerationRequest) -> StoryGenerationResponse:
        """
        Sinh kịch bản chi tiết cho 1 chương manga (phân cảnh, góc máy, thoại tiếng Việt, ComfyUI prompts).
        Tự động fallback an toàn nếu Ollama chưa chạy.
        """
        start_time = time.time()
        mgr = self.model_manager
        can_call_llm = False

        if mgr is not None:
            try:
                ready, _ = await mgr.runtime_ready()
                can_call_llm = ready
            except Exception:
                can_call_llm = False

        if not can_call_llm:
            logger.info("Ollama/LLM chưa sẵn sàng, kích hoạt deterministic template fallback.")
            fallback_plan = generate_fallback_chapter(req)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return StoryGenerationResponse(
                chapter_plan=fallback_plan,
                raw_model_response=None,
                mode_used="fallback_template",
                model_name=self.default_model,
                generation_time_ms=elapsed_ms
            )

        # Chuẩn bị Prompt hướng dẫn Qwen 3.5:4B
        system_prompt = (
            "Bạn là Giám đốc Biên kịch Manga Chuyên nghiệp (Manga Story Director & Editor).\n"
            "Nhiệm vụ: Lên kế hoạch kịch bản chi tiết cho một chương manga xuất sắc bằng TIẾNG VIỆT.\n"
            "QUY TẮC CỐT LÕI:\n"
            "1. Lời thoại tiếng Việt phải tự nhiên, ngắn gọn, phù hợp bóng thoại manga (dưới 30 từ/bong bóng).\n"
            "2. Tuyệt đối tuân thủ xưng hô (ngôi 1, ngôi 2), kính ngữ và cấm kỵ của từng nhân vật theo hồ sơ SpeechRules.\n"
            "3. Mỗi ô tranh (panel) phải có camera_angle hợp lệ (close_up, extreme_close_up, medium_shot, wide_shot, full_shot, low_angle, high_angle, over_the_shoulder, dutch_angle) và visual_description rõ ràng.\n"
            "4. Sinh kèm diffusion_prompt_en (tiếng Anh) miêu tả chi tiết nhân vật, trang phục, hành động, ánh sáng, bối cảnh.\n"
            "5. Định dạng đầu ra: Bắt buộc là JSON HỢP LỆ có đủ mảng 'scenes' khớp cấu trúc sau:\n"
            '{\n'
            '  "chapter_number": 1,\n'
            '  "title": "Chương 1: ...",\n'
            '  "synopsis": "Tóm tắt ngắn gọn chương",\n'
            '  "scenes": [\n'
            '    {\n'
            '      "scene_number": 1,\n'
            '      "title": "Tên cảnh",\n'
            '      "location": "Địa điểm",\n'
            '      "time_of_day": "night",\n'
            '      "summary": "Tóm tắt diễn biến cảnh",\n'
            '      "characters_present": ["Tên NV"],\n'
            '      "emotional_beat": "mystery",\n'
            '      "panels": [\n'
            '        {\n'
            '          "panel_number": 1,\n'
            '          "camera_angle": "medium_shot",\n'
            '          "visual_description": "Mô tả hình ảnh tiếng Việt",\n'
            '          "characters_in_panel": ["Tên NV"],\n'
            '          "diffusion_prompt_en": "Detailed English colored anime illustration prompt...",\n'
            '          "dialogues": [{"speaker": "Tên NV", "text": "Lời thoại", "bubble_type": "speech", "position_hint": "top-left"}],\n'
            '          "sfx": [{"text": "XOẠT!", "visual_style": "impact"}]\n'
            '        }\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            '}\n'
            "Giá trị hợp lệ: time_of_day in [morning,day,sunset,night,indoor,dark]; "
            "emotional_beat in [tension,comedic,dramatic,resolution,mystery,action,romance]; "
            "bubble_type in [speech,thought,shout,whisper,narrator,sfx]; "
            "visual_style in [impact,ambient,motion,comic]; "
            "position_hint in [top-left,top-right,bottom-left,bottom-right,center,auto].\n"
            "BẮT BUỘC mảng 'scenes' phải có ĐÚNG target_scene_count phần tử, mỗi scene có ĐÚNG target_panels_per_scene panels, mỗi trường viết súc tích dưới 25 từ. "
            "Không dùng dấu ngoặc kép \" bên trong chuỗi giá trị (hãy dùng ngoặc đơn ').\n"
        )

        char_summaries = []
        for c in req.characters:
            char_summaries.append(
                f"- Tên: {c.name} | Vai trò: {c.role} | Xưng hô ngôi 1: '{c.speech_rules.first_person}', ngôi 2: '{c.speech_rules.second_person}' | "
                f"Giọng điệu: {c.speech_rules.tone} | Locked traits: tóc {c.locked_traits.hair_color} {c.locked_traits.hair_style}, mắt {c.locked_traits.eye_color}, trang phục {c.locked_traits.signature_outfit}"
            )

        canon_summaries = [f"- [{f.severity}] {f.title}: {f.fact}" for f in req.canon_facts]
        timeline_summaries = [f"- [{ev.timestamp_label}] {ev.title}: {ev.description}" for ev in req.timeline_events]

        user_content = {
            "series_title": req.series_title,
            "genre": req.genre,
            "art_style": req.art_style,
            "chapter_number": req.chapter_number,
            "chapter_title": req.chapter_title or f"Chương {req.chapter_number}",
            "premise": req.premise,
            "characters": char_summaries,
            "canon_facts": canon_summaries,
            "timeline_events": timeline_summaries,
            "user_instructions": req.user_instructions or "Tập trung vào nhịp truyện lôi cuốn, cao trào kịch tính.",
            "target_scene_count": req.target_scene_count,
            "target_panels_per_scene": req.target_panels_per_scene,
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Hãy sinh dàn ý chương manga theo định dạng JSON:\n{json.dumps(user_content, ensure_ascii=False, indent=2)}"
            }
        ]

        target_num_predict = _compute_chapter_num_predict(
            req.target_scene_count, req.target_panels_per_scene
        )

        try:
            raw_reply = await mgr.chat(
                messages,
                json_mode=True,
                num_predict=target_num_predict,
                temperature=0.35
            )
            parsed_data = extract_json_payload(raw_reply)
            chapter_plan = ChapterPlan.model_validate(parsed_data)

            if not chapter_plan.scenes:
                retry_messages = messages + [
                    {"role": "assistant", "content": raw_reply},
                    {"role": "user", "content": f"Mảng 'scenes' đang bị thiếu hoặc rỗng! Hãy trả về lại JSON đầy đủ với ĐÚNG {req.target_scene_count} scenes, mỗi scene có {req.target_panels_per_scene} panels."}
                ]
                raw_reply = await mgr.chat(
                    retry_messages,
                    json_mode=True,
                    num_predict=target_num_predict,
                    temperature=0.3
                )
                parsed_data = extract_json_payload(raw_reply)
                chapter_plan = ChapterPlan.model_validate(parsed_data)

            if not chapter_plan.scenes:
                raise ValueError("LLM không trả về phân cảnh (scenes) hợp lệ.")

            # Đảm bảo các panel có prompt ComfyUI
            for sc in chapter_plan.scenes:
                for p in sc.panels:
                    auto_pos, auto_neg = build_panel_diffusion_prompt(
                        p, req.characters, req.art_style
                    )
                    if not p.diffusion_prompt_en:
                        p.diffusion_prompt_en = auto_pos
                    if not p.diffusion_negative_prompt:
                        p.diffusion_negative_prompt = auto_neg

            elapsed_ms = int((time.time() - start_time) * 1000)
            return StoryGenerationResponse(
                chapter_plan=chapter_plan,
                raw_model_response=raw_reply,
                mode_used="ollama",
                model_name=mgr.active_route().get("model", self.default_model),
                generation_time_ms=elapsed_ms
            )
        except Exception as exc:
            logger.warning(f"Lỗi khi gọi LLM sinh kịch bản ({exc}), chuyển sang template an toàn.")
            fallback_plan = generate_fallback_chapter(req)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return StoryGenerationResponse(
                chapter_plan=fallback_plan,
                raw_model_response=f"Fallback due to: {str(exc)}",
                mode_used="fallback_template",
                model_name=self.default_model,
                generation_time_ms=elapsed_ms
            )

    async def check_continuity(self, req: ContinuityCheckRequest) -> ContinuityCheckResponse:
        """
        Kiểm tra tính nhất quán (Continuity Check) toàn diện:
        Kết hợp thuật toán kiểm tra tất định (Deterministic Engine) và LLM Deep Review.
        """
        # 1. Chạy Deterministic Engine
        deterministic_issues = check_deterministic_continuity(
            chapter=req.chapter_plan,
            characters=req.characters,
            canon_facts=req.canon_facts,
            timeline_events=req.timeline_events
        )

        llm_issues: list[ContinuityIssue] = []
        mgr = self.model_manager
        can_call_llm = False

        if mgr is not None:
            try:
                ready, _ = await mgr.runtime_ready()
                can_call_llm = ready
            except Exception:
                can_call_llm = False

        if can_call_llm:
            sys_prompt = (
                "Bạn là Tổng Biên Tập Manga Chuyên Nghiệp (Senior Continuity Editor).\n"
                "Nhiệm vụ: Soát lỗi tính nhất quán (Continuity) trong chương manga tiếng Việt.\n"
                "Hãy kiểm tra nghiêm ngặt:\n"
                "1. Tính cách và lời thoại: Nhân vật có nói sai giọng điệu, xưng hô sai hoặc phạm từ cấm không?\n"
                "2. Ngoại hình (Locked traits): Có ô tranh nào miêu tả nhân vật sai đặc điểm cố định không?\n"
                "3. Quy tắc thế giới (Canon Facts): Có chi tiết nào vi phạm quy tắc bất biến không?\n"
                "4. Dòng thời gian: Có chi tiết nào vô lý về thứ tự nhân quả không?\n"
                "Định dạng đầu ra JSON: { 'issues': [ { 'issue_type': '...', 'severity': '...', 'entity_affected': '...', 'description': '...', 'quote_or_location': '...', 'fix_suggestion': '...' } ], 'summary': '...' }\n"
            )

            user_payload = {
                "chapter_plan": req.chapter_plan.model_dump(),
                "characters": [c.model_dump() for c in req.characters],
                "canon_facts": [f.model_dump() for f in req.canon_facts],
                "timeline_events": [t.model_dump() for t in req.timeline_events],
            }

            try:
                raw_reply = await mgr.chat(
                    [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"Kiểm tra nhất quán cho kịch bản sau:\n{json.dumps(user_payload, ensure_ascii=False)}"}
                    ],
                    json_mode=True,
                    num_predict=1500,
                    temperature=0.2
                )
                parsed = extract_json_payload(raw_reply)
                for item in parsed.get("issues", []):
                    try:
                        llm_issues.append(ContinuityIssue.model_validate(item))
                    except Exception:
                        pass
            except Exception as err:
                logger.warning(f"LLM continuity check failed or timed out: {err}")

        # Hợp nhất danh sách lỗi và loại bỏ trùng lặp
        all_issues = list(deterministic_issues)
        seen_keys = {f"{iss.entity_affected}:{iss.description[:30]}" for iss in all_issues}
        for iss in llm_issues:
            key = f"{iss.entity_affected}:{iss.description[:30]}"
            if key not in seen_keys:
                all_issues.append(iss)
                seen_keys.add(key)

        crit_count = sum(1 for i in all_issues if i.severity == "critical")
        warn_count = sum(1 for i in all_issues if i.severity == "warning")

        # Tính điểm nhất quán (100 là hoàn hảo)
        score = max(0, 100 - (crit_count * 25) - (warn_count * 10))
        is_consistent = crit_count == 0

        summary = (
            f"Kiểm định hoàn tất: {len(all_issues)} vấn đề được ghi nhận ({crit_count} nghiêm trọng, {warn_count} cảnh báo). "
            f"Điểm số nhất quán: {score}/100. "
            + ("Kịch bản đạt chuẩn nhất quán để xuất bản/sinh ảnh." if is_consistent else "Cần khắc phục các lỗi nghiêm trọng trước khi sản xuất.")
        )

        recommendations: list[str] = []
        if crit_count > 0:
            recommendations.append("Ưu tiên sửa các lỗi sai đại từ xưng hô và vi phạm locked traits ngoại hình nhân vật.")
        if warn_count > 0:
            recommendations.append("Rà soát lại danh sách nhân vật có mặt tại hiện trường để tránh cảm giác nhân vật đột ngột xuất hiện.")
        if not recommendations:
            recommendations.append("Kịch bản rất mượt mà và tuân thủ chặt chẽ hồ sơ nhân vật.")

        report = ContinuityReport(
            is_consistent=is_consistent,
            score=score,
            critical_count=crit_count,
            warning_count=warn_count,
            issues=all_issues,
            summary=summary,
            recommendations=recommendations
        )

        return ContinuityCheckResponse(
            report=report,
            mode_used="hybrid" if can_call_llm else "deterministic_only",
            model_name=mgr.active_route().get("model", self.default_model) if mgr else self.default_model
        )

    async def generate_branching_progression(self, req: BranchingProgressionRequest) -> BranchingProgressionResponse:
        """
        Sinh kịch bản phân nhánh đa chiều (Multi-branch Progression: Route A, Route B, Route C).
        Hỗ trợ tích hợp LLM Qwen3.5:4B và tự động fallback sang deterministic template.
        """
        start_time = time.time()
        mgr = self.model_manager
        can_call_llm = False

        if mgr is not None:
            try:
                ready, _ = await mgr.runtime_ready()
                can_call_llm = ready
            except Exception:
                can_call_llm = False

        if not can_call_llm:
            logger.info("LLM không khả dụng, sử dụng bộ sinh phân nhánh tất định cao cấp (deterministic fallback).")
            fallback_prog = generate_fallback_branching_progression(req)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return BranchingProgressionResponse(
                progression=fallback_prog,
                raw_model_response=None,
                mode_used="fallback_template",
                model_name=self.default_model,
                generation_time_ms=elapsed_ms
            )

        sys_prompt = (
            "Bạn là Giám đốc Biên kịch Manga Tương tác Chuyên nghiệp (Interactive Manga Director).\n"
            "Nhiệm vụ: Thiết kế diễn biến phân nhánh đa chiều (Route A, Route B, Route C) cho một chương manga tiếng Việt.\n"
            "QUY TẮC CỐT LÕI:\n"
            "1. Bắt buộc tạo ít nhất 3 routes độc lập rõ rệt: Route A (Hành động trực diện), Route B (Thâm nhập trinh thám), Route C (Đàm phán hoặc bóng tối).\n"
            "2. Mỗi route phải có: route_id ('route_a', 'route_b', 'route_c'), route_name, branch_type, choice_trigger, synopsis, central_conflict, key_twist, character_impacts (dict), consequences (list), scenes (danh sách scenes với panels, dialogues, sfx), cliffhanger, next_decision_prompt.\n"
            "3. Lựa chọn của độc giả ('reader_choices') phải tương ứng mở khóa Route A, B, C với rủi ro và phần thưởng rõ ràng.\n"
            "4. Tuân thủ nghiêm ngặt tính cách, khẩu khí, xưng hô của nhân vật.\n"
            "5. Đầu ra BẮT BUỘC là JSON hợp lệ theo cấu trúc:\n"
            "{\n"
            '  "series_title": "...",\n'
            '  "chapter_number": 1,\n'
            '  "decision_point": "...",\n'
            '  "decision_context": "...",\n'
            '  "routes": [\n'
            '    {\n'
            '      "route_id": "route_a",\n'
            '      "route_name": "Route A: ...",\n'
            '      "branch_type": "action_heroic",\n'
            '      "choice_trigger": "...",\n'
            '      "synopsis": "...",\n'
            '      "central_conflict": "...",\n'
            '      "key_twist": "...",\n'
            '      "character_impacts": {"Tên NV": "..."},\n'
            '      "consequences": ["..."],\n'
            '      "scenes": [\n'
            '        {\n'
            '          "scene_number": 1,\n'
            '          "title": "...",\n'
            '          "location": "...",\n'
            '          "time_of_day": "night",\n'
            '          "summary": "...",\n'
            '          "characters_present": ["..."],\n'
            '          "emotional_beat": "action",\n'
            '          "panels": [\n'
            '            {\n'
            '              "panel_number": 1,\n'
            '              "camera_angle": "medium_shot",\n'
            '              "visual_description": "...",\n'
            '              "characters_in_panel": ["..."],\n'
            '              "diffusion_prompt_en": "...",\n'
            '              "dialogues": [{"speaker": "...", "text": "...", "bubble_type": "speech"}],\n'
            '              "sfx": [{"text": "...", "visual_style": "impact"}]\n'
            '            }\n'
            '          ]\n'
            '        }\n'
            '      ],\n'
            '      "cliffhanger": "...",\n'
            '      "next_decision_prompt": "..."\n'
            '    }\n'
            '  ],\n'
            '  "reader_choices": [\n'
            '    {"choice_id": "choice_a", "route_target": "route_a", "text": "...", "intent_tone": "aggressive", "consequence_hint": "...", "risk_reward": "..."}\n'
            '  ],\n'
            '  "divergence_analysis": "...",\n'
            '  "recommended_route": "route_a"\n'
            "}\n"
        )

        char_summaries = [f"{c.name} ({c.role}): xưng '{c.speech_rules.first_person}' - '{c.speech_rules.second_person}'" for c in req.characters]
        user_payload = {
            "series_title": req.series_title,
            "genre": req.genre,
            "chapter_number": req.chapter_number,
            "premise": req.premise,
            "decision_prompt": req.decision_prompt,
            "current_scene_context": req.current_scene_context,
            "characters": char_summaries,
            "branch_count": req.branch_count,
            "scenes_per_branch": req.scenes_per_branch,
            "panels_per_scene": req.panels_per_scene,
            "user_instructions": req.user_instructions
        }

        try:
            raw_reply = await mgr.chat(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Hãy xây dựng kịch bản phân nhánh theo JSON:\n{json.dumps(user_payload, ensure_ascii=False)}"}
                ],
                json_mode=True,
                num_predict=DEFAULT_CHAPTER_NUM_PREDICT,
                temperature=0.4
            )
            parsed = extract_json_payload(raw_reply)
            progression = BranchingProgression.model_validate(parsed)

            if len(progression.routes) < 2:
                raise ValueError("Số lượng nhánh tạo ra không đủ tiêu chuẩn đa chiều.")

            # Đảm bảo ComfyUI diffusion prompt có mặt trên tất cả các ô tranh
            for rt in progression.routes:
                for sc in rt.scenes:
                    for p in sc.panels:
                        pos, neg = build_panel_diffusion_prompt(p, req.characters, req.art_style)
                        if not p.diffusion_prompt_en:
                            p.diffusion_prompt_en = pos
                        if not p.diffusion_negative_prompt:
                            p.diffusion_negative_prompt = neg

            elapsed_ms = int((time.time() - start_time) * 1000)
            return BranchingProgressionResponse(
                progression=progression,
                raw_model_response=raw_reply,
                mode_used="ollama",
                model_name=mgr.active_route().get("model", self.default_model),
                generation_time_ms=elapsed_ms
            )
        except Exception as exc:
            logger.warning(f"Lỗi khi gọi LLM sinh kịch bản phân nhánh ({exc}), kích hoạt fallback template an toàn.")
            fallback_prog = generate_fallback_branching_progression(req)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return BranchingProgressionResponse(
                progression=fallback_prog,
                raw_model_response=f"Fallback due to: {str(exc)}",
                mode_used="fallback_template",
                model_name=self.default_model,
                generation_time_ms=elapsed_ms
            )

    async def suggest_plot_twists_and_choices(self, req: PlotTwistAndChoiceRequest) -> PlotTwistAndChoiceResponse:
        """
        Gợi ý nút thắt cốt truyện (plot twists), xung đột nhân vật (character conflicts)
        và lựa chọn của độc giả (reader choices) bằng LLM hoặc template fallback.
        """
        start_time = time.time()
        mgr = self.model_manager
        can_call_llm = False

        if mgr is not None:
            try:
                ready, _ = await mgr.runtime_ready()
                can_call_llm = ready
            except Exception:
                can_call_llm = False

        if not can_call_llm:
            fallback_res = generate_fallback_plot_twists_and_choices(req)
            fallback_res.generation_time_ms = int((time.time() - start_time) * 1000)
            return fallback_res

        sys_prompt = (
            "Bạn là Chuyên gia Tư vấn Cốt truyện Manga (Manga Story Consultant).\n"
            "Nhiệm vụ: Gợi ý các nút thắt bất ngờ (plot twists), xung đột tâm lý (character conflicts) "
            "và các lựa chọn kịch tính cho độc giả (reader choices) bằng tiếng Việt.\n"
            "Định dạng JSON bắt buộc:\n"
            "{\n"
            '  "plot_twists": [\n'
            '    {\n'
            '      "id": "twist_1",\n'
            '      "title": "...",\n'
            '      "twist_type": "identity_reveal",\n'
            '      "summary": "...",\n'
            '      "impact_level": "seismic",\n'
            '      "foreshadowing_clues": ["..."],\n'
            '      "character_reactions": {"Tên NV": "..."},\n'
            '      "compatible_routes": ["route_a", "route_b"]\n'
            '    }\n'
            '  ],\n'
            '  "character_conflicts": [\n'
            '    {\n'
            '      "id": "conflict_1",\n'
            '      "characters_involved": ["NV A", "NV B"],\n'
            '      "conflict_type": "ideological",\n'
            '      "core_friction": "...",\n'
            '      "escalation_triggers": ["..."],\n'
            '      "resolution_paths": ["..."],\n'
            '      "narrative_tension_score": 8\n'
            '    }\n'
            '  ],\n'
            '  "reader_choices": [\n'
            '    {\n'
            '      "choice_id": "choice_1",\n'
            '      "route_target": "route_a",\n'
            '      "text": "...",\n'
            '      "intent_tone": "aggressive",\n'
            '      "consequence_hint": "...",\n'
            '      "risk_reward": "..."\n'
            '    }\n'
            '  ],\n'
            '  "editor_notes": "..."\n'
            "}\n"
        )

        user_content = {
            "series_title": req.series_title,
            "genre": req.genre,
            "current_context": req.current_context,
            "characters": [c.name for c in req.characters],
            "num_twists": req.num_twists,
            "num_conflicts": req.num_conflicts,
            "num_choices": req.num_choices,
            "user_instructions": req.user_instructions
        }

        try:
            raw_reply = await mgr.chat(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Hãy gợi ý plot twists, xung đột và lựa chọn:\n{json.dumps(user_content, ensure_ascii=False)}"}
                ],
                json_mode=True,
                num_predict=2500,
                temperature=0.45
            )
            parsed = extract_json_payload(raw_reply)
            resp = PlotTwistAndChoiceResponse.model_validate(parsed)
            resp.mode_used = "ollama"
            resp.model_name = mgr.active_route().get("model", self.default_model)
            resp.generation_time_ms = int((time.time() - start_time) * 1000)
            return resp
        except Exception as exc:
            logger.warning(f"Lỗi khi gợi ý twists qua LLM ({exc}), dùng fallback template.")
            fallback_res = generate_fallback_plot_twists_and_choices(req)
            fallback_res.generation_time_ms = int((time.time() - start_time) * 1000)
            return fallback_res


# ==============================================================================
# 7. Singleton & Convenience Helper Functions
# ==============================================================================

_DEFAULT_ENGINE: MangaStoryEngine | None = None


def get_default_story_engine(model_manager: Any = None) -> MangaStoryEngine:
    """Lấy hoặc khởi tạo instance mặc định của MangaStoryEngine."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = MangaStoryEngine(model_manager=model_manager)
    elif model_manager is not None:
        _DEFAULT_ENGINE.model_manager = model_manager
    return _DEFAULT_ENGINE


def set_default_story_engine(engine: MangaStoryEngine) -> None:
    """Thiết lập instance engine mặc định."""
    global _DEFAULT_ENGINE
    _DEFAULT_ENGINE = engine


async def generate_chapter_plan(req: StoryGenerationRequest, model_manager: Any = None) -> StoryGenerationResponse:
    """Hàm tiện ích cấp module để sinh kịch bản chương."""
    engine = get_default_story_engine(model_manager)
    return await engine.generate_chapter(req)


async def run_continuity_check(req: ContinuityCheckRequest, model_manager: Any = None) -> ContinuityCheckResponse:
    """Hàm tiện ích cấp module để chạy kiểm định tính nhất quán."""
    engine = get_default_story_engine(model_manager)
    return await engine.check_continuity(req)


async def generate_story_branching(req: BranchingProgressionRequest, model_manager: Any = None) -> BranchingProgressionResponse:
    """Hàm tiện ích cấp module để sinh kịch bản phân nhánh cốt truyện (Route A, Route B, Route C)."""
    engine = get_default_story_engine(model_manager)
    return await engine.generate_branching_progression(req)


async def suggest_plot_twists_and_choices(req: PlotTwistAndChoiceRequest, model_manager: Any = None) -> PlotTwistAndChoiceResponse:
    """Hàm tiện ích cấp module để gợi ý nút thắt cốt truyện, xung đột nhân vật và lựa chọn độc giả."""
    engine = get_default_story_engine(model_manager)
    return await engine.suggest_plot_twists_and_choices(req)


def create_sample_story_data() -> dict[str, Any]:
    """
    Tạo dữ liệu mẫu chuẩn (Moonlight Classroom / Lớp Học Ánh Trăng)
    dùng cho khởi tạo ban đầu, demo hoặc chạy integration test.
    """
    ren = CharacterProfile(
        id="char-ren-001",
        name="Kurogane Ren",
        japanese_name="黒鉄 レン",
        role="protagonist",
        one_line_summary="Học sinh chuyển trường bí ẩn nắm giữ Cấm Ấn Hắc Nguyệt",
        personality="Trầm tĩnh, sắc sảo, bề ngoài lạnh lùng thờ ơ nhưng trọng tình cảm. Thường suy nghĩ trước khi hành động.",
        backstory="Sống sót sau thảm họa Đêm Trăng Đỏ 10 năm trước, mang trên cổ tay phong ấn ma thuật bị nguyền rủa.",
        strengths=["Khả năng phân tích chiến thuật siêu tốc", "Thao túng bóng tối ở cự ly gần", "Ý chí kiên định"],
        weaknesses=["Sức khỏe suy giảm khi dùng ma lực quá độ", "Ám ảnh tâm lý về quá khứ"],
        speech_rules=SpeechRules(
            first_person="tớ",
            second_person="cậu",
            tone="điềm đạm, hơi thờ ơ nhưng dứt khoát",
            honorifics=[],
            catchphrases=["Thật phiền phức...", "Không có gì là ngẫu nhiên."],
            vocabulary_habits=["phân tích", "phong ấn", "quy luật"],
            forbidden_words=["bản tọa", "đại ca", "tha mạng", "sợ hãi"],
            sample_dialogues=[
                "Tớ không quan tâm họ nghĩ gì, việc cần làm thì phải làm.",
                "Cậu lùi lại đi, khu vực này không an toàn đâu."
            ]
        ),
        locked_traits=CharacterLockedTraits(
            gender="boy",
            age_appearance="16 years old",
            hair_style="messy shonen hair",
            hair_color="black",
            eye_color="crimson red",
            facial_features=["scar on left cheek"],
            signature_outfit="black gakuran uniform with open collar",
            accessories=["silver ring on right thumb", "wrist bandages"],
            color_scheme=["black", "crimson", "dark grey"],
            diffusion_positive_tags="1boy, 16yo, messy black hair, crimson red eyes, scar on cheek, black gakuran, wrist bandages, intense gaze",
            diffusion_negative_tags="blonde hair, blue eyes, glasses, smiling widely, neat hair"
        ),
        arc_goal="Giải mã nguồn gốc Cấm Ấn và tìm lại ký ức đã mất về gia đình."
    )

    luna = CharacterProfile(
        id="char-luna-002",
        name="Shirakawa Luna",
        japanese_name="白川 ルナ",
        role="rival",
        one_line_summary="Hội trưởng Hội học sinh kiêm truyền nhân gia tộc Ngân Nguyệt",
        personality="Kiêu hãnh, quy tắc nghiêm ngặt, luôn theo đuổi sự hoàn hảo. Thích lẽ phải nhưng cứng nhắc.",
        backstory="Con gái trưởng của gia tộc Shirakawa danh giá, gánh trên vai trọng trách bảo vệ trật tự học viện.",
        strengths=["Ma pháp ánh sáng thanh tẩy", "Kiếm thuật cận chiến điêu luyện", "Uy tín lãnh đạo"],
        weaknesses=["Dễ nổi nóng khi bị xúc phạm gia quy", "Khó tin tưởng người khác"],
        speech_rules=SpeechRules(
            first_person="tôi",
            second_person="bạn",
            tone="trịnh trọng, sắc sảo, kiêu kỳ",
            honorifics=["-san", "tiểu thư"],
            catchphrases=["Tuyệt đối không thể chấp nhận!", "Luật lệ là trật tự."],
            vocabulary_habits=["trách nhiệm", "kỷ luật", "danh dự"],
            forbidden_words=["mày", "tao", "chịu thua"],
            sample_dialogues=[
                "Tôi cảnh cáo bạn lần cuối, đừng bước qua ranh giới đó!",
                "Trách nhiệm của Hội học sinh là bảo vệ mọi người, kể cả người bướng bỉnh như bạn."
            ]
        ),
        locked_traits=CharacterLockedTraits(
            gender="girl",
            age_appearance="16 years old",
            hair_style="long straight twin tails",
            hair_color="silver platinum",
            eye_color="sapphire blue",
            facial_features=[],
            signature_outfit="royal academy blazer with white pleated skirt and red ribbon",
            accessories=["crescent moon silver hairclip"],
            color_scheme=["white", "navy blue", "silver"],
            diffusion_positive_tags="1girl, 16yo, long silver twin tails, sapphire blue eyes, royal academy blazer, crescent moon hairclip, elegant, confident",
            diffusion_negative_tags="short hair, black hair, messy hair, casual clothes"
        ),
        arc_goal="Chứng minh năng lực của bản thân mà không cần dựa vào cái bóng của gia tộc."
    )

    fact_1 = CanonFact(
        id="fact-001",
        category="world_rule",
        title="Hiệu Ứng Trăng Đỏ (Blood Moon)",
        fact="Vào những đêm trăng đỏ, mọi phong ấn hắc ám suy yếu 50%, nhưng ma pháp ánh sáng cũng mất đi tính thanh tẩy tuyệt đối.",
        severity="immutable",
        related_characters=["Kurogane Ren", "Shirakawa Luna"]
    )

    fact_2 = CanonFact(
        id="fact-002",
        category="taboo",
        title="Luật Giới Nghiêm Gác Chuông Cổ",
        fact="Không học sinh nào được phép tiến vào gác chuông cổ sau 22h đêm. Người vi phạm sẽ bị trục xuất hoặc bị ma trận canh gác giam giữ.",
        severity="hard_rule"
    )

    timeline_1 = TimelineEvent(
        id="time-001",
        era_or_arc="Quá khứ 10 năm trước",
        order_index=1,
        timestamp_label="Năm 2036",
        title="Đêm Trăng Đỏ Đại Thảm Họa",
        description="Phong ấn cổ đại dưới lòng đất học viện bị phá vỡ, thiêu rụi khu nghiên cứu cũ và biến mất một phần lịch sử.",
        characters_involved=["Kurogane Ren"]
    )

    timeline_2 = TimelineEvent(
        id="time-002",
        era_or_arc="Hiện tại",
        order_index=2,
        timestamp_label="Học kỳ 1 - Khóa 42",
        title="Ren chuyển trường tới Học Viện",
        description="Ren nhập học với thân phận học sinh học bổng đặc biệt, chạm trán Luna ngay cổng trường.",
        characters_involved=["Kurogane Ren", "Shirakawa Luna"]
    )

    sample_branching_req = BranchingProgressionRequest(
        series_title="Lớp Học Ánh Trăng (Moonlight Classroom)",
        genre="Shonen Học Đường Siêu Nhiên",
        premise="Ren và Luna chạm trán thực thể bóng tối thức tỉnh tại gác chuông cấm.",
        chapter_number=1,
        characters=[ren, luna],
        canon_facts=[fact_1, fact_2],
        timeline_events=[timeline_1, timeline_2]
    )
    sample_branching = generate_fallback_branching_progression(sample_branching_req)

    sample_twist_req = PlotTwistAndChoiceRequest(
        series_title="Lớp Học Ánh Trăng (Moonlight Classroom)",
        genre="Shonen Học Đường Siêu Nhiên",
        current_context="Thực thể bóng tối thức tỉnh tại gác chuông cấm",
        characters=[ren, luna],
        canon_facts=[fact_1, fact_2]
    )
    sample_twists = generate_fallback_plot_twists_and_choices(sample_twist_req)

    return {
        "series": {
            "title": "Lớp Học Ánh Trăng (Moonlight Classroom)",
            "genre": "Shonen Học Đường Siêu Nhiên",
            "art_style": "b_w",
            "synopsis": "Tại học viện nơi ma thuật và kỷ luật đan xen, hai học sinh đối lập buộc phải hợp tác để ngăn chặn thảm họa đêm trăng đỏ tái diễn."
        },
        "characters": [ren, luna],
        "canon_facts": [fact_1, fact_2],
        "timeline_events": [timeline_1, timeline_2],
        "sample_branching": sample_branching,
        "sample_twists": sample_twists
    }
