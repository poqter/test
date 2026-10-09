from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ProfileRule:
    profile_code: str
    core_threshold: int
    light_floor: int
    light_ceiling: int
    max_core: int
    categories: tuple[str, ...]
    importance_weights: tuple[tuple[str, int], ...]


PROFILE_RULES: Final[dict[str, ProfileRule]] = {
    "INSURANCE": ProfileRule(
        profile_code="INSURANCE",
        core_threshold=50,
        light_floor=20,
        light_ceiling=49,
        max_core=8,
        categories=(
            "제도·규제", "상품·보험료", "보험금·보상", "세제·재무",
            "영업·채널", "보험사·시장", "소비자·사회이슈", "참고·통계",
        ),
        importance_weights=(("FP 업무 영향도", 30), ("고객 영향도", 20), ("시급성", 15), ("영향 범위", 15), ("확정성·신뢰도", 10), ("지속성", 10)),
    ),
    "NEWS": ProfileRule(
        profile_code="NEWS",
        core_threshold=50,
        light_floor=20,
        light_ceiling=49,
        max_core=1,
        categories=(
            "정치·행정", "법·제도", "사회·안전", "생활경제·주거", "노동·고용",
            "보건·복지", "교육", "과학·기술·산업", "국제·안보",
        ),
        importance_weights=(("국민 영향 범위", 25), ("정책·제도 중요성", 20), ("시급성", 15), ("사회적 파급력", 15), ("영향 지속성", 10), ("업무·생활 관련성", 10), ("정보 신뢰도", 5)),
    ),
    "MARKET": ProfileRule(
        profile_code="MARKET",
        core_threshold=55,
        light_floor=30,
        light_ceiling=54,
        max_core=1,
        categories=("국내증시", "해외증시", "금리·채권", "환율", "원자재", "경제지표", "기업·산업", "시장리스크"),
        importance_weights=(("시장 영향 범위", 25), ("한국시장 관련성", 20), ("영향 지속성", 15), ("정책·거시 중요성", 15), ("실제 시장 반응", 15), ("FP·고객 활용성", 10)),
    ),
}


def light_digest_limit(core_count: int = 0, profile_code: str = "INSURANCE") -> int:
    """Display cap is independent of core count; first five are shown in the UI."""
    return {"NEWS": 10, "MARKET": 8, "INSURANCE": 15}.get(profile_code, 15) - core_count
