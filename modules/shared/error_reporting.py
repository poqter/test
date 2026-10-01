"""User-safe error references and diagnostic code locations, never raw messages."""
from __future__ import annotations
import logging
import re
import traceback
from pathlib import Path
from uuid import uuid4


def record_error(error: BaseException, component: str) -> str:
    reference = uuid4().hex[:10]
    # A fixed/validated component tag and code filenames only. No arguments,
    # exception message, uploaded filename, repr, local variables or traceback text.
    tag = re.sub(r"[^A-Za-z0-9_.-]", "_", component)[:60]
    frames = traceback.extract_tb(error.__traceback__)
    locations = " > ".join(f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames[-6:])
    logging.getLogger("hwarang.errors").error(
        "PROCESS_FAILED ref=%s component=%s type=%s locations=%s",
        reference, tag, type(error).__name__, locations,
    )
    return reference


def user_message(reference: str) -> str:
    return f"자료를 처리하지 못했습니다. 파일 형식과 입력을 확인한 뒤 다시 시도해 주세요. 오류 번호: {reference}"
