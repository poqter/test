"""Defensive input and resource validation, separate from business rules."""
from __future__ import annotations

import io
import math
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO


MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_SESSION_UPLOAD_BYTES = 60 * 1024 * 1024
MAX_XLSX_MEMBERS = 5_000
MAX_XLSX_UNCOMPRESSED = 200 * 1024 * 1024
MAX_XLSX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_XLSX_RATIO = 100
ALLOWED_EXTENSIONS = frozenset({".xlsx", ".pdf"})


class ValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class UploadInfo:
    filename: str
    extension: str
    size: int


def validate_money(value: object, *, minimum: Decimal = Decimal("0"), maximum: Decimal = Decimal("1000000000000")) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError("INVALID_NUMBER", "숫자로 입력해 주세요.") from exc
    if not amount.is_finite():
        raise ValidationError("INVALID_NUMBER", "유한한 숫자로 입력해 주세요.")
    if amount < minimum or amount > maximum:
        raise ValidationError("OUT_OF_RANGE", f"{minimum} 이상 {maximum} 이하로 입력해 주세요.")
    return amount


def validate_date_order(start: date, end: date) -> tuple[date, date]:
    if start > end:
        raise ValidationError("DATE_ORDER", "시작일은 종료일보다 늦을 수 없습니다.")
    return start, end


def _bytes(data: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data[: MAX_FILE_BYTES + 1])
    position = data.tell() if hasattr(data, "tell") else None
    try:
        if hasattr(data, "seek"):
            data.seek(0)
        return data.read(MAX_FILE_BYTES + 1)
    finally:
        if position is not None and hasattr(data, "seek"):
            data.seek(position)


def validate_upload(filename: str, data: bytes | bytearray | BinaryIO, *, session_total: int = 0) -> UploadInfo:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("UPLOAD_FORMAT_INVALID", "XLSX 또는 PDF 파일만 사용할 수 있습니다.")
    content = _bytes(data)
    size = len(content)
    if not size:
        raise ValidationError("UPLOAD_EMPTY", "빈 파일은 사용할 수 없습니다.")
    if size > MAX_FILE_BYTES or session_total + size > MAX_SESSION_UPLOAD_BYTES:
        raise ValidationError("UPLOAD_TOO_LARGE", "업로드 처리 한도를 넘었습니다.")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValidationError("UPLOAD_FORMAT_INVALID", "PDF 파일 시그니처를 확인해 주세요.")
    if extension == ".xlsx":
        if not content.startswith(b"PK"):
            raise ValidationError("UPLOAD_FORMAT_INVALID", "XLSX 파일 시그니처를 확인해 주세요.")
        _validate_xlsx_archive(content)
    return UploadInfo(filename=Path(filename).name, extension=extension, size=size)


def _validate_xlsx_archive(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            items = archive.infolist()
            if len(items) > MAX_XLSX_MEMBERS:
                raise ValidationError("UPLOAD_ARCHIVE_LIMIT", "XLSX 내부 항목 수가 처리 한도를 넘었습니다.")
            total = 0
            for item in items:
                total += item.file_size
                if item.file_size > MAX_XLSX_MEMBER_BYTES:
                    raise ValidationError("UPLOAD_ARCHIVE_LIMIT", "XLSX 내부 단일 항목이 처리 한도를 넘었습니다.")
                ratio = item.file_size / max(item.compress_size, 1)
                if math.isfinite(ratio) and ratio > MAX_XLSX_RATIO:
                    raise ValidationError("UPLOAD_ARCHIVE_LIMIT", "XLSX 압축 비율이 처리 한도를 넘었습니다.")
            if total > MAX_XLSX_UNCOMPRESSED:
                raise ValidationError("UPLOAD_ARCHIVE_LIMIT", "XLSX 압축 해제 크기가 처리 한도를 넘었습니다.")
    except zipfile.BadZipFile as exc:
        raise ValidationError("UPLOAD_FORMAT_INVALID", "손상되었거나 올바르지 않은 XLSX 파일입니다.") from exc
