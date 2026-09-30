"""Small, consistent visual cues for the standalone calculator experience."""
from __future__ import annotations

CATEGORY_VISUALS: dict[str, tuple[str, str]] = {
    "보험 기본": ("🧾", "보험 기본"),
    "보장·생활자금": ("🛡️", "보장·생활자금"),
    "연금·은퇴": ("🌅", "연금·은퇴"),
    "재무·투자": ("📈", "재무·투자"),
    "개인·부동산 세금": ("🏠", "개인·부동산 세금"),
    "상속·증여·승계": ("🎁", "상속·증여·승계"),
    "법인·대표 전략": ("🧭", "법인·대표 전략"),
    "사업·법인 실무": ("🏢", "사업·법인 실무"),
}

PURPOSE_EMOJIS: dict[str, str] = {
    "보험료·계약을 계산해요": "🧾",
    "치료·생활자금을 준비해요": "🛡️",
    "노후를 준비해요": "🌅",
    "목돈을 모으고 싶어요": "🎯",
    "세금을 확인해요": "🏠",
    "상속·증여를 준비해요": "🎁",
    "대표 전략을 검토해요": "🧭",
    "사업 실무를 점검해요": "🏢",
}

# Results that are more representative than the generic "first monetary value" rule.
# Ordered alternatives support calculators whose output labels change by mode.
PRIMARY_RESULT_LABELS: dict[str, tuple[str, ...]] = {
    "적정보험료계산기": ("보장성 보험료 비중",),
    "수익률계산기": ("필요 연 수익률",),
    "해외금융계좌 신고계산기": ("신고 대상 판단",),
    "성실신고 대상판정계산기": ("수입금액 기준 판정",),
    "부가세 예정신고 선택계산기": ("예정신고 구분",),
    "정책자금 자격진단계산기": ("중소기업 사전 판정",),
    "법인 부동산 보유·양도 비교계산기": ("매각 국세 비교", "개인 매각 국세 추정"),
    "차등배당계산기": ("증여세 추정", "정산 추가 납부·환급 추정", "소득세·증여세 합계 추정"),
    "특정법인 증여의제계산기": ("특정법인 거래 증여세 추정", "일감몰아주기 증여세 추정"),
}


def primary_result_labels(name: str) -> tuple[str, ...]:
    return PRIMARY_RESULT_LABELS.get(name, ())


def category_emoji(group: str) -> str:
    return CATEGORY_VISUALS.get(group, ("🧮", group))[0]


def category_short_name(group: str) -> str:
    return CATEGORY_VISUALS.get(group, ("🧮", group))[1]


def category_label(group: str, count: int | None = None) -> str:
    if group == "전체":
        label = "🧮 전체"
    else:
        label = f"{category_emoji(group)} {category_short_name(group)}"
    return f"{label} · {count}" if count is not None else label


def purpose_label(label: str) -> str:
    return f"{PURPOSE_EMOJIS.get(label, '💡')} {label}"


def calculator_title(name: str, group: str) -> str:
    return f"{category_emoji(group)} {name}"
