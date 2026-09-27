"""Small privacy defaults for UI, errors, and exported field selection.

These helpers reduce accidental disclosure; they do not claim to detect or
remove every kind of personal information.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Mapping


ANONYMOUS_LABEL = "고객 A"
ENVIRONMENT_LABELS = {"test": "테스트 서버", "production": "운영 서버", "local": "로컬 실행"}
DEFAULT_EXPORT_FIELDS = frozenset({
    "항목", "구분", "유형", "단위", "변경 전", "변경 후", "차이", "메모",
    "가정", "기준일", "결과", "설명", "확인사항",
})
_ERROR_MESSAGES = {
    "UPLOAD_FORMAT_INVALID": "지원하는 파일 형식을 확인한 뒤 다시 올려 주세요.",
    "UPLOAD_TOO_LARGE": "파일이 처리 한도를 넘었습니다. 파일을 나누거나 관리자에게 문의해 주세요.",
    "UPLOAD_PARSE_FAILED": "파일을 읽지 못했습니다. 형식과 암호화 여부를 확인해 주세요.",
    "EXPORT_FAILED": "결과 파일을 만들지 못했습니다. 입력을 확인한 뒤 다시 시도해 주세요.",
}


def non_identifying_label(value: str | None = None) -> str:
    value = (value or "").strip()
    return value if value else ANONYMOUS_LABEL


def permitted_export_fields(
    record: Mapping[str, object],
    allowed: Iterable[str] = DEFAULT_EXPORT_FIELDS,
) -> dict[str, object]:
    allowset = frozenset(allowed)
    return {key: value for key, value in record.items() if key in allowset}


def safe_error(code: str, _error: BaseException | None = None) -> str:
    """Map an internal error code without echoing parser or customer text."""
    return _ERROR_MESSAGES.get(code, "작업을 완료하지 못했습니다. 입력을 확인한 뒤 다시 시도해 주세요.")


def environment_notice(environment: str = "test") -> str:
    label = ENVIRONMENT_LABELS.get(environment, "서버 환경 미확인")
    return f"{label} · 입력과 업로드 자료는 현재 세션의 서버 메모리에서 처리됩니다."


def safe_filename(tool_id: str, extension: str, date_stamp: str) -> str:
    safe_tool = re.sub(r"[^a-z0-9_-]", "_", tool_id.lower()).strip("_") or "result"
    safe_ext = re.sub(r"[^a-z0-9]", "", extension.lower().lstrip(".")) or "bin"
    safe_date = re.sub(r"[^0-9]", "", date_stamp)[:8] or "undated"
    return str(Path(f"hwarang_{safe_tool}_{safe_date}.{safe_ext}").name)
