"""Lossless, explicit numeric parsing shared by input adapters and business tools."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real


class NumericInputError(ValueError):
    """A value is missing or invalid; the raw value is deliberately not echoed."""


def decimal_number(value: object, *, label: str = "금액", allow_empty: bool = False,
                   allow_negative: bool = True) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if allow_empty:
            return None
        raise NumericInputError(f"{label}: 값을 입력해 주세요. 실제 0인 경우 0을 입력합니다.")
    if isinstance(value, bool):
        raise NumericInputError(f"{label}: 숫자로 입력해 주세요.")
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("원"):
            text = text[:-1].strip()
        # Commas are thousands separators, not arbitrary characters to discard.
        if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", text):
            raise NumericInputError(f"{label}: 숫자 형식을 확인해 주세요. 예: 100,000")
        text = text.replace(",", "")
    else:
        text = str(value)
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        raise NumericInputError(f"{label}: 숫자로 입력해 주세요.") from None
    if not number.is_finite():
        raise NumericInputError(f"{label}: 유효한 숫자로 입력해 주세요.")
    if not allow_negative and number < 0:
        raise NumericInputError(f"{label}: 0 이상으로 입력해 주세요.")
    return number


def integer_won(value: object, *, label: str = "금액", allow_empty: bool = False,
                allow_negative: bool = True, maximum: int | None = None) -> int | None:
    number = decimal_number(value, label=label, allow_empty=allow_empty, allow_negative=allow_negative)
    if number is None:
        return None
    if number != number.to_integral_value():
        raise NumericInputError(f"{label}: 원 미만 금액은 입력할 수 없습니다. 원 단위 정수를 입력해 주세요.")
    if maximum is not None and abs(number) > maximum:
        raise NumericInputError(f"{label}: 허용 범위를 초과했습니다.")
    return int(number)
