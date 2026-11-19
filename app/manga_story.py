from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field

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


class PanelSFX(BaseModel):
    """Hiệu ứng âm thanh chữ tượng thanh (Sound Effects / Onomatopoeia)."""
    text: str = Field(..., description="Từ tượng thanh tiếng Việt/Nhật (ví dụ: RẦM!, VÙÙ!, XOẸT!, DOKI DOKI)")
    meaning: str = Field(default="", description="Ý nghĩa hành động hoặc tiếng động")
    visual_style: Literal["impact", "ambient", "motion", "comic"] = Field(
        default="impact", description="Phong cách vẽ chữ SFX"
    )


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
    diffusion_prompt_en: str = Field(default="", description="Prompt tiếng Anh dịch sẵn tích hợp locked traits nhân vật")
    diffusion_negative_prompt: str = Field(default="", description="Negative prompt cho ô tranh này")
    dialogues: list[DialogueLine] = Field(default_factory=list, description="Danh sách lời thoại đặt trong ô tranh")
    sfx: list[PanelSFX] = Field(default_factory=list, description="Chữ tượng thanh SFX nếu có")
    focus_element: str = Field(default="", description="Trọng tâm thị giác của khung hình")
    lighting_and_atmosphere: str = Field(default="high contrast, dramatic manga shading", description="Ánh sáng và không khí cảnh")


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

            # 1.3 Kiểm tra Locked Traits trong Prompt hình ảnh
            for p_char in panel.characters_in_panel:
                p_key = p_char.strip().lower()
                if p_key in char_names_lower:
                    c_profile = char_names_lower[p_key]
                    lt = c_profile.locked_traits

                    # Ví dụ tóc đen nhưng prompt ghi blonde hair
                    if lt.hair_color and lt.hair_color.lower() in ("black", "đen"):
                        if re.search(r"\b(blonde|yellow|white)\s+hair\b", panel.diffusion_prompt_en, re.IGNORECASE):
                            issues.append(
                                ContinuityIssue(
                                    issue_type="appearance_conflict",
                                    severity="critical",
                                    entity_affected=c_profile.name,
                                    description=f"Prompt của Panel {panel.panel_number} mô tả tóc màu khác với Locked Trait ({lt.hair_color}) của nhân vật '{c_profile.name}'.",
                                    quote_or_location=panel.diffusion_prompt_en[:90],
                                    fix_suggestion=f"Đồng bộ lại prompt: dùng '{lt.hair_color} hair'."
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


# ==============================================================================
# 6. Story Studio AI Engine (Ollama / Qwen3.5:4B Bridge)
# ==============================================================================

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
            "3. Mỗi ô tranh (panel) phải có mô tả góc máy (camera_angle: close_up, medium_shot, wide_shot, etc.) và mô tả hình ảnh rõ ràng.\n"
            "4. Sinh kèm diffusion_prompt_en (tiếng Anh) ngắn gọn, kèm locked traits của nhân vật để sinh ảnh ComfyUI.\n"
            "5. Định dạng đầu ra: Bắt buộc là JSON HỢP LỆ khớp chính xác với cấu trúc ChapterPlan.\n"
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

        try:
            raw_reply = await mgr.chat(
                messages,
                json_mode=True,
                num_predict=2000,
                temperature=0.35
            )
            parsed_data = extract_json_payload(raw_reply)
            chapter_plan = ChapterPlan.model_validate(parsed_data)

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

    return {
        "series": {
            "title": "Lớp Học Ánh Trăng (Moonlight Classroom)",
            "genre": "Shonen Học Đường Siêu Nhiên",
            "art_style": "b_w",
            "synopsis": "Tại học viện nơi ma thuật và kỷ luật đan xen, hai học sinh đối lập buộc phải hợp tác để ngăn chặn thảm họa đêm trăng đỏ tái diễn."
        },
        "characters": [ren, luna],
        "canon_facts": [fact_1, fact_2],
        "timeline_events": [timeline_1, timeline_2]
    }
