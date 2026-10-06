from __future__ import annotations

import re

from .models import SourceCandidate
from .normalize import is_safe_url, visible_text
from .source_policy import source_identity

_INSURANCE_POSITIVE = {
    "보험", "실손", "생명보험", "손해보험", "보험료", "보험금", "보험사", "설계사", "종신보험",
    "연금보험", "자동차보험", "암보험", "건강보험", "금감원", "금융감독원", "생보협회", "손보협회",
}
_INSURANCE_FALSE_POSITIVE = {
    "국민건강보험료", "건강보험료 계산", "4대보험 계산", "사회보험료", "고용보험료 계산", "산재보험료 계산",
}
_NEWS_EXCLUDE = {
    "연예인", "열애", "예능", "드라마 시청률", "경기 결과", "득점", "프로야구 결과", "프로축구 결과",
}
_LOW_QUALITY = {"광고", "sponsored", "협찬", "보도자료 배포 서비스"}


def _blob(candidate: SourceCandidate) -> str:
    return f"{candidate.title} {visible_text(candidate.description)}".casefold()


def insurance_routing_evidence(candidate: SourceCandidate) -> dict:
    blob = _blob(candidate)
    match = next((token for token in sorted(_INSURANCE_POSITIVE) if token in blob), None)
    if not match and re.search(r"(?<![a-z0-9])ga(?![a-z0-9])", blob):
        match = "ga"
    excluded = next((token for token in sorted(_INSURANCE_FALSE_POSITIVE) if token in blob), None)
    pos = blob.find(match) if match else 0
    return {"matched_token": match, "excluded_token": excluded,
            "matched_text": blob[max(0, pos-40):pos+100] if match else None}


def passes_common_gate(candidate: SourceCandidate) -> tuple[bool, str | None]:
    if not candidate.title or not candidate.url:
        return False, "missing_identity"
    if not is_safe_url(candidate.url):
        return False, "unsafe_url"
    if candidate.collector_provider == "openai_web_search" and not source_identity(candidate.url):
        return False, "untrusted_source"
    if candidate.freshness_tier in {"stale", "undated"}:
        return False, candidate.freshness_tier
    blob = _blob(candidate)
    if any(token in blob for token in _LOW_QUALITY):
        return False, "low_quality"
    return True, None


def route_profiles(candidate: SourceCandidate, hinted_profile: str | None = None) -> set[str]:
    blob = _blob(candidate)
    routed: set[str] = set()

    insurance = insurance_routing_evidence(candidate)
    if hinted_profile == "INSURANCE" or insurance["matched_token"]:
        if not insurance["excluded_token"]:
            routed.add("INSURANCE")

    if hinted_profile == "NEWS":
        if not any(token in blob for token in _NEWS_EXCLUDE):
            routed.add("NEWS")
    elif not any(token in blob for token in _NEWS_EXCLUDE):
        # Cross-profile reuse: broad public-policy / social-impact keywords may also route to NEWS.
        if re.search(r"정책|법률|시행|정부|국회|재난|안전|주거|고용|의료|교육|통신|개인정보|산업", blob):
            routed.add("NEWS")

    if hinted_profile == "MARKET":
        routed.add("MARKET")
    elif re.search(r"금리|채권|환율|달러|원화|코스피|코스닥|증시|주식시장|국채|기준금리|물가|cpi|연준|fed|한국은행|원자재|유가", blob):
        routed.add("MARKET")

    return routed
