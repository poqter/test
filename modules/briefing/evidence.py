from __future__ import annotations

from .models import SharedEventCandidate

_HIGH_RISK = {
    "INSURANCE": ("비과세", "세법", "감독규정", "모집규제", "보험금 지급", "판매중지", "보험료 변경", "가입조건", "시행"),
    "NEWS": ("법률", "판결", "사망", "부상", "재난", "긴급", "국가경보", "수사", "기소", "확정판결", "시행"),
    "MARKET": ("금리결정", "기준금리", "환율 급등", "국채금리", "금융시스템", "서킷브레이커"),
}


def infer_evidence_status(event: SharedEventCandidate) -> str:
    if any(row.source_kind in {"official", "industry_official"} for row in event.candidates):
        return "official_confirmed"
    publishers = {
        (row.publisher_domain or row.publisher_name or row.source_name or "").strip().casefold()
        for row in event.candidates
        if (row.publisher_domain or row.publisher_name or row.source_name)
    }
    publishers.discard("")
    if len(publishers) >= 2:
        return "multi_source_confirmed"
    if event.candidates:
        return "reported" if any(row.source_kind in {"news", "discovery"} for row in event.candidates) else "single_source"
    return "single_source"


def is_high_risk(event: SharedEventCandidate, profile_code: str) -> bool:
    blob = " ".join([event.canonical_title, *[row.description for row in event.candidates]]).casefold()
    return any(token.casefold() in blob for token in _HIGH_RISK.get(profile_code, ()))
