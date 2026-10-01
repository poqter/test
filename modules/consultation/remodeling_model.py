"""Remodeling value models and lossless numeric helpers.

Extracted from the existing implementation; public facade names are preserved.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from openpyxl.styles import Side

APP_VERSION = "1.0.1"

APP_TITLE = "보험 리모델링 비교 제안서"

NAVY = "17365D"

NAVY2 = "245889"

GOLD = "C9A24D"

GOLD_LIGHT = "FFF4D6"

BLUE_LIGHT = "EAF2F8"

GREEN_LIGHT = "E8F4F2"

SOFT = "F7F9FC"

WHITE = "FFFFFF"

INK = "25364A"

MUTED = "667085"

GREEN = "24745A"

RED = "C00000"

LINE = "B8C2CF"

THIN = Side(style="thin", color=LINE)

CONTRACT_ACTIONS = ["유지", "감액", "해지", "변경", "검토"]

ACTION_HELP = {
    "유지": "예: 현재 계약과 보장을 그대로 유지",
    "감액": "예: 고객센터를 통해 불필요한 특약 감액 요청",
    "해지": "예: 고객센터 상담원 연결 후 계약 해지 요청",
    "변경": "예: 갱신형 특약 또는 보장금액 변경 요청",
    "검토": "예: 보험회사에 계약조건 확인 후 처리 방향 결정",
}

ACTION_STYLE = {
    "유지": ("E8F4F2", "24745A"),
    "감액": ("FFF1D6", "9A6700"),
    "해지": ("FDECEC", "B42318"),
    "변경": ("EAF2FF", "1769DC"),
    "검토": ("F2ECFF", "6941C6"),
}

@dataclass
class NewPlan:
    name: str = ""
    monthly: int = 0
    years: int = 20
    custom_months: int = 0

    @property
    def months(self) -> int:
        return self.custom_months if self.custom_months > 0 else self.years * 12

    @property
    def fixed_total(self) -> int:
        return self.monthly * self.months

@dataclass
class ExistingContract:
    company: str = ""
    product: str = ""
    action: str = "유지"
    detail: str = ""

@dataclass
class Person:
    name: str
    old_monthly: int
    old_total: int
    retained_monthly: int
    retained_total: int
    plans: list[NewPlan] = field(default_factory=list)
    coverage: str = ""
    contracts: list[ExistingContract] = field(default_factory=list)

    @property
    def new_plan_monthly(self) -> int:
        return sum(p.monthly for p in self.plans)

    @property
    def after_monthly(self) -> int:
        return self.retained_monthly + self.new_plan_monthly

    @property
    def after_total(self) -> int:
        return self.retained_total + sum(p.fixed_total for p in self.plans)

    @property
    def monthly_change(self) -> int:
        return self.after_monthly - self.old_monthly

    @property
    def total_change(self) -> int:
        return self.after_total - self.old_total

def money(value: object) -> int:
    from modules.shared.numeric import integer_won
    # Blank optional preview fields remain blank/zero until the existing
    # completion gate allows an export. Non-empty invalid values are rejected.
    amount = integer_won(value, allow_empty=True, allow_negative=False)
    return 0 if amount is None else amount

def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def safe_filename(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", value).strip() or "보험리모델링_비교안"

def won(value: int) -> str:
    return f"{int(value):,}원"

def rate(old: int, new: int) -> float | None:
    return (old - new) / old if old > new and old else None

def change_amount(old: int, new: int) -> str:
    if old > new:
        return f"{old-new:,}원 절감"
    if old < new:
        return f"{new-old:,}원 증가"
    return "변동 없음"

def change_rate(old: int, new: int) -> str:
    r = rate(old, new)
    return f"{r:.1%} 감소" if r is not None else ""

def combined(people: list[Person]) -> dict[str, int]:
    return {
        "old_monthly": sum(p.old_monthly for p in people),
        "after_monthly": sum(p.after_monthly for p in people),
        "old_total": sum(p.old_total for p in people),
        "after_total": sum(p.after_total for p in people),
    }
