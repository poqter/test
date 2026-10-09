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

SHARED_DISCOVERY_TARGET: Final[int] = 6
SHARED_DISCOVERY_SOFT_LIMIT: Final[int] = 6
SHARED_DISCOVERY_HARD_LIMIT: Final[int] = 6

DISCOVERY_LANES: Final[tuple[DiscoveryLaneSpec, ...]] = (
    DiscoveryLaneSpec("official_industry", "INSURANCE", "보험·GA 업계의 오늘 새 발표·제도·통계·소비자 정보를 수집한다. 공식 자료가 적으면 억지로 채우지 않는다."),
    DiscoveryLaneSpec("trusted_media", "INSURANCE", "보험·GA 업계의 새 뉴스 5~8개를 찾는다. 상품·보험료·보험금·영업채널·시장 동향 등 알아둘 만한 소식도 포함한다. 광고·행사·수상·반복 기사는 제외한다."),
    DiscoveryLaneSpec("official_wire_broadcast", "NEWS", "정책·사회·안전·생활·교육·기술·국제 분야의 새 사실을 담은 종합뉴스를 다양하게 찾는다. 매우 큰 사건만 고집하지 않으며 광고·가십·반복 논평은 제외한다."),
    DiscoveryLaneSpec("general_economic_media", "NEWS", "오늘 알아둘 만한 종합뉴스 5~8개를 다양한 발행사와 분야에서 수집한다. 모든 소식을 보험 상담에 연결하지 않는다. 오래된 재보도와 광고는 제외한다."),
    DiscoveryLaneSpec("market_news", "MARKET", "경제·금융·국내외 증시·환율·금리·산업의 새 뉴스 6~8개를 수집한다. 실제 발표와 사건 중심으로 찾고 투자 매수·매도 지시를 만들지 않는다."),
    DiscoveryLaneSpec("broker_research", "MARKET", "증권사·금융기관이 공개한 최신 리서치의 공개 요약·초록·발표 원문 7~8개를 찾는다. 기관명·자료명·발표일·공개 견해가 확인되는 자료만 수집한다. 자료가 없으면 없는 그대로 반환한다. 로그인·유료벽을 우회하지 않는다."),
)
