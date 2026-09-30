"""Small, consistent visual cues for the standalone calculator experience."""
from __future__ import annotations

CATEGORY_VISUALS: dict[str, tuple[str, str]] = {
    "개인 · 세금": ("🧾", "세금"),
    "개인 · 연금·은퇴": ("🌅", "연금·은퇴"),
    "개인 · 보장·설계": ("🛡️", "보장·설계"),
    "개인 · 재무계산": ("📈", "재무계산"),
    "법인 · 대표 의사결정": ("🧭", "대표 의사결정"),
    "법인 · 세무 실무": ("🏢", "세무 실무"),
}

PURPOSE_EMOJIS: dict[str, str] = {
    "보험료가 부담돼요": "💸",
    "노후를 준비해요": "🌅",
    "자녀에게 물려줘요": "🎁",
    "치료비가 걱정돼요": "🩺",
    "대표 보수를 정해요": "👔",
    "목돈을 모으고 싶어요": "🎯",
}


def category_emoji(group: str) -> str:
    return CATEGORY_VISUALS.get(group, ("🧮", group.split(" · ")[-1]))[0]


def category_short_name(group: str) -> str:
    return CATEGORY_VISUALS.get(group, ("🧮", group.split(" · ")[-1]))[1]


def category_label(group: str) -> str:
    if group == "전체":
        return "🧮 전체"
    return f"{category_emoji(group)} {category_short_name(group)}"


def purpose_label(label: str) -> str:
    return f"{PURPOSE_EMOJIS.get(label, '💡')} {label}"


def calculator_title(name: str, group: str) -> str:
    return f"{category_emoji(group)} {name}"
