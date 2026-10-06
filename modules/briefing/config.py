from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class DiscoveryLaneSpec:
    lane_code: str
    profile_code: str
    query: str


CORE_FRESHNESS_HOURS: Final[int] = 36
LIGHT_FRESHNESS_HOURS: Final[int] = 96

SHARED_DISCOVERY_TARGET: Final[int] = 4
SHARED_DISCOVERY_SOFT_LIMIT: Final[int] = 5
SHARED_DISCOVERY_HARD_LIMIT: Final[int] = 6

DISCOVERY_LANES: Final[tuple[DiscoveryLaneSpec, ...]] = (
    DiscoveryLaneSpec(
        "official_industry",
        "INSURANCE",
        (
            "대한민국 민영 보험업계에서 최근 발표되거나 변경된 중요한 공식 자료를 찾아라. "
            "금융위원회, 금융감독원, 법령, 생명보험협회, 손해보험협회, 보험개발원, 보험연구원, "
            "보험사 공식 공지·공시를 우선한다. 세제·감독규정·모집규제·보험금 지급기준·판매중지·"
            "보험료·가입조건처럼 FP와 소비자에게 실제 영향이 있는 변화 중심으로 검색한다."
        ),
    ),
    DiscoveryLaneSpec(
        "trusted_media",
        "INSURANCE",
        (
            "최근 대한민국 민영 보험업계의 중요한 새 이슈를 보험전문언론과 주요 경제언론에서 찾아라. "
            "단순 회사 홍보, 인사, 수상, 행사, 사회보험 계산기성 콘텐츠는 제외하고 규제·상품·보험료·"
            "보험금·세제·영업채널·소비자 영향이 있는 사건을 우선한다."
        ),
    ),
    DiscoveryLaneSpec(
        "official_wire_broadcast",
        "NEWS",
        (
            "최근 대한민국에서 국민생활·업무·사회에 실질적 영향이 큰 새 사건을 공식기관, 뉴스통신, "
            "주요 방송 중심으로 찾아라. 정책·법제도·재난안전·생활경제·노동·보건복지·교육·기술산업·"
            "대한민국에 직접 영향이 큰 국제안보 이슈를 우선한다. 단순 정치공방·연예가십·일반 스포츠 결과는 제외한다."
        ),
    ),
    DiscoveryLaneSpec(
        "general_economic_media",
        "NEWS",
        (
            "최근 대한민국에서 알아야 할 중요한 새 사건을 주요 종합언론과 경제언론에서 찾아라. "
            "국민 권리의무, 생활비, 주거, 고용, 의료, 교육, 디지털 규제, 산업, 재난안전에 실제 영향이 있는 사건을 우선하고 "
            "반복보도·단순 논평·기업 홍보·가십은 제외한다."
        ),
    ),
)
