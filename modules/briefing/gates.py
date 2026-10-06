from __future__ import annotations

import re

from .models import SourceCandidate

_INSURANCE_POSITIVE = {
    "보험", "실손", "생명보험", "손해보험", "보험료", "보험금", "보험사", "설계사", "ga", "종신보험",
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
    return f"{candidate.title} {candidate.description}".casefold()


def passes_common_gate(candidate: SourceCandidate) -> tuple[bool, str | None]:
    if not candidate.title or not candidate.url:
        return False, "missing_identity"
    if candidate.freshness_tier in {"stale", "undated"}:
        return False, candidate.freshness_tier
    blob = _blob(candidate)
    if any(token in blob for token in _LOW_QUALITY):
        return False, "low_quality"
    return True, None


def route_profiles(candidate: SourceCandidate, hinted_profile: str | None = None) -> set[str]:
    blob = _blob(candidate)
    routed: set[str] = set()

    if hinted_profile == "INSURANCE" or any(token in blob for token in _INSURANCE_POSITIVE):
        if not any(token in blob for token in _INSURANCE_FALSE_POSITIVE):
            routed.add("INSURANCE")

    if hinted_profile == "NEWS":
        if not any(token in blob for token in _NEWS_EXCLUDE):
            routed.add("NEWS")
    elif not any(token in blob for token in _NEWS_EXCLUDE):
        # Cross-profile reuse: broad public-policy / social-impact keywords may also route to NEWS.
        if re.search(r"정책|법률|시행|정부|국회|재난|안전|주거|고용|의료|교육|통신|개인정보|산업", blob):
            routed.add("NEWS")

    return routed
