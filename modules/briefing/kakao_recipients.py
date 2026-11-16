"""Conservative validation for user-provided Kakao search names.

This module does not inspect KakaoTalk and cannot verify a recipient's identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from collections import Counter
from typing import Iterable


@dataclass(frozen=True)
class Recipient:
    display_name: str
    search_name: str
    enabled: bool = True


@dataclass(frozen=True)
class Assessment:
    recipient: Recipient
    search_name: str
    state: str
    reason: str


def normalized_name(value: str) -> str:
    """Normalize equivalent Korean input, preserving case and inner spaces."""
    return unicodedata.normalize("NFC", value or "").strip()


def _valid_name(name: str) -> bool:
    return bool(name) and len(name) <= 100 and all(
        not unicodedata.category(c).startswith("C") for c in name
    )


def assess_recipients(recipients: Iterable[Recipient]) -> list[Assessment]:
    """Flag only duplicate entries in this saved list; never claim verified identity."""
    items = list(recipients)
    names = [normalized_name(r.search_name) for r in items]
    counts = Counter(n for r, n in zip(items, names) if r.enabled and _valid_name(n))
    results: list[Assessment] = []
    for recipient, name in zip(items, names):
        if not recipient.enabled:
            state, reason = "excluded", "발송 중지"
        elif not _valid_name(name):
            state, reason = "needs_review", "친구 검색 이름을 확인해 주세요"
        elif counts[name] > 1:
            state, reason = "needs_review", "저장된 명단에 같은 검색 이름이 있습니다"
        else:
            state, reason = "unverified", "카카오톡 친구 확인 전"
        results.append(Assessment(recipient, name, state, reason))
    return results
