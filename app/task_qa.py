from __future__ import annotations

import re
from typing import Any


def deterministic_task_qa(
    draft_text: str,
    project_files: list[dict[str, Any]],
    web_sources: list[dict[str, Any]],
    *,
    project_required: bool,
    web_required: bool,
    evidence_text: str,
    current_date: str,
) -> list[str]:
    """Machine-verifiable QA gates. Model PASS can never override these failures."""
    findings: list[str] = []
    if "[PROJECT: path]" in draft_text or "[PROJECT: relative/path]" in draft_text:
        findings.append("Báo cáo còn placeholder citation project thay vì đường dẫn tệp thật.")
    if "[WEB: URL]" in draft_text or "[WEB: https://...]" in draft_text:
        findings.append("Báo cáo còn placeholder citation web thay vì URL nguồn thật.")
    allowed_paths = {str(item.get("path", "")).replace("\\", "/") for item in project_files}
    allowed_urls = {str(item.get("url", "")).rstrip("/") for item in web_sources if item.get("url")}

    project_refs = [x.strip().replace("\\", "/") for x in re.findall(r"\[PROJECT:\s*([^\]]+)\]", draft_text)]
    web_refs = [x.strip().rstrip(".,;:)" + chr(96)) for x in re.findall(r"\[WEB:\s*(https?://[^\]\s]+)\s*\]", draft_text)]

    if project_required and not project_refs:
        findings.append("Thiếu citation [PROJECT: path] trong phần báo cáo của Agent; danh sách nguồn đính kèm cuối báo cáo không được tính.")
    invalid_paths = sorted({x for x in project_refs if x not in allowed_paths})
    if invalid_paths:
        findings.append("Citation project không nằm trong manifest đã đọc: " + ", ".join(invalid_paths[:5]))

    if web_required and not web_refs:
        findings.append("Thiếu citation [WEB: URL] trong phần báo cáo của Agent; danh sách nguồn đính kèm cuối báo cáo không được tính.")
    invalid_urls = sorted({x for x in web_refs if x.rstrip("/") not in allowed_urls})
    if invalid_urls:
        findings.append("Citation web không nằm trong danh sách trang Browser đã mở: " + ", ".join(invalid_urls[:5]))

    # Reject incomplete or invented publication/report dates. Current task date is trusted,
    # but another date must be present in the actual project/web evidence.
    date_pattern = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|20\d{2}-\d{2}-\d{2})\b")
    for line in draft_text.splitlines():
        if re.search(r"(?i)\b(?:ngày|date)\s*[:：]", line):
            if re.search(r"(?i)không xác định|chưa xác định|unknown|not specified", line):
                continue
            dates = date_pattern.findall(line)
            if not dates:
                findings.append("Có trường Ngày/Date nhưng không ghi ngày đầy đủ, có thể là ngày bịa hoặc văn bản bị cắt: " + line.strip()[:160])
                continue
            for date_value in dates:
                if date_value == current_date:
                    continue
                if date_value not in evidence_text:
                    findings.append("Ngày trong báo cáo không được bằng chứng project/web hỗ trợ: " + date_value)

    return findings




def parse_qa_verdict(raw: str) -> tuple[str, list[str]]:
    """Parse only an explicit first-line PASS/FAIL; malformed output always fails closed."""
    lines = [line.strip() for line in str(raw or "").splitlines() if line.strip()]
    first_line = lines[0].strip("* ") if lines else ""
    first_token = first_line.split()[0].upper().rstrip(":.,") if first_line else ""
    if first_token == "PASS":
        return "pass", []
    if first_token == "FAIL":
        findings = lines[1:4]
        return "fail", findings or ["QA model từ chối báo cáo."]
    return "fail", ["QA không trả dòng đầu PASS/FAIL hợp lệ; không xác nhận chất lượng."]
