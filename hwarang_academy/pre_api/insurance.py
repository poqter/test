"""Deterministic fictional insurance-portfolio generator for training cases.

All products and amounts are synthetic simulation data. The module never queries
insurers or represents current product availability.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
import random
from typing import Any

from .constants import INSURANCE_GENERATOR_VERSION, MAX_CONTRACTS_V1, PORTFOLIO_ARCHETYPES, SIMULATION_REFERENCE_DATE

_REFERENCE_DATE = date.fromisoformat(SIMULATION_REFERENCE_DATE)

_INSURERS = (
    ("현대해상", "nonlife"), ("DB손보", "nonlife"), ("KB손보", "nonlife"),
    ("삼성화재", "nonlife"), ("한화손보", "nonlife"),
    ("한화생명", "life"), ("삼성생명", "life"), ("교보생명", "life"), ("신한라이프", "life"),
)

_CORE_CODES = (
    "DEATH_DISEASE", "DEATH_ACCIDENT", "DISABILITY_DISEASE_3", "DISABILITY_ACCIDENT_3",
    "CANCER_GENERAL", "CANCER_MINOR", "BRAIN_VASCULAR", "BRAIN_STROKE", "BRAIN_HEMORRHAGE",
    "HEART_ISCHEMIC", "HEART_AMI", "SURGERY_DISEASE", "SURGERY_DISEASE_CLASS",
    "SURGERY_ACCIDENT", "SURGERY_ACCIDENT_CLASS", "SURGERY_BRAIN", "SURGERY_HEART",
    "HOSP_DISEASE", "HOSP_ACCIDENT", "CAREGIVER_DISEASE", "CAREGIVER_ACCIDENT",
    "LIABILITY_DAILY", "DIAG_FRACTURE",
)

_INDEMNITY_CODES = ("INDEMNITY_DISEASE_IN", "INDEMNITY_DISEASE_OUT", "INDEMNITY_ACCIDENT_IN", "INDEMNITY_ACCIDENT_OUT")
_DRIVER_CODES = ("DRIVER_SETTLEMENT", "DRIVER_SETTLEMENT_UNDER6", "DRIVER_LAWYER", "DRIVER_FINE_PERSON", "DRIVER_FINE_PROPERTY", "DRIVER_INJURY")

# Synthetic training reference bands (만원). They are NOT sales or suitability standards.
_BASE_TARGETS = {
    "DEATH_DISEASE": 8000,
    "DEATH_ACCIDENT": 10000,
    "DISABILITY_DISEASE_3": 300,
    "DISABILITY_ACCIDENT_3": 300,
    "CANCER_GENERAL": 5000,
    "CANCER_MINOR": 1000,
    "BRAIN_VASCULAR": 3000,
    "BRAIN_STROKE": 3000,
    "BRAIN_HEMORRHAGE": 3000,
    "HEART_ISCHEMIC": 3000,
    "HEART_AMI": 3000,
    "SURGERY_DISEASE": 50,
    "SURGERY_DISEASE_CLASS": 1000,
    "SURGERY_ACCIDENT": 100,
    "SURGERY_ACCIDENT_CLASS": 1000,
    "SURGERY_BRAIN": 1000,
    "SURGERY_HEART": 1000,
    "HOSP_DISEASE": 10,
    "HOSP_ACCIDENT": 10,
    "CAREGIVER_DISEASE": 10,
    "CAREGIVER_ACCIDENT": 10,
    "LIABILITY_DAILY": 10000,
    "DIAG_FRACTURE": 30,
    "DRIVER_SETTLEMENT": 20000,
    "DRIVER_SETTLEMENT_UNDER6": 1000,
    "DRIVER_LAWYER": 5000,
    "DRIVER_FINE_PERSON": 3000,
    "DRIVER_FINE_PROPERTY": 500,
    "DRIVER_INJURY": 30,
    "INDEMNITY_DISEASE_IN": 5000,
    "INDEMNITY_DISEASE_OUT": 30,
    "INDEMNITY_ACCIDENT_IN": 5000,
    "INDEMNITY_ACCIDENT_OUT": 30,
}


def training_target(code: str, customer: dict[str, Any]) -> int:
    value = int(_BASE_TARGETS.get(code, 0))
    age = int(customer.get("age") or customer.get("ground_truth", {}).get("identity", {}).get("age", 40))
    family = customer.get("ground_truth", {}).get("family", {})
    child_count = int(family.get("child_count") or 0)
    if code == "DEATH_DISEASE":
        if child_count:
            value += 2000 + 1000 * min(child_count, 2)
        if age >= 60:
            value = max(3000, value - 3000)
    return value


def _round_amount(value: float, *, step: int = 10) -> int:
    if value <= 0:
        return 0
    return max(step, int(round(value / step) * step))


def _target_multiplier(archetype: str, code: str, rng: random.Random, gap_code: str | None) -> float:
    if archetype == "BALANCED":
        return rng.uniform(0.85, 1.25)
    if archetype == "UNDERINSURED":
        return rng.uniform(0.15, 0.65)
    if archetype == "OVERINSURED":
        return rng.uniform(1.25, 2.1)
    if archetype == "DUPLICATED":
        return rng.uniform(1.35, 2.25) if code in {"CANCER_GENERAL", "CANCER_MINOR", "HOSP_DISEASE", "HOSP_ACCIDENT"} else rng.uniform(0.75, 1.2)
    if archetype == "OUTDATED":
        if code in {"BRAIN_VASCULAR", "HEART_ISCHEMIC", "CAREGIVER_DISEASE", "CAREGIVER_ACCIDENT"}:
            return rng.uniform(0.0, 0.35)
        if code in {"BRAIN_STROKE", "BRAIN_HEMORRHAGE", "HEART_AMI"}:
            return rng.uniform(0.8, 1.35)
        return rng.uniform(0.65, 1.05)
    if archetype == "RENEWAL_HEAVY":
        return rng.uniform(0.75, 1.35)
    if archetype == "GAP_SPECIFIC":
        if code == gap_code:
            return rng.uniform(0.0, 0.35)
        return rng.uniform(0.8, 1.3)
    # MIXED
    return rng.choice((rng.uniform(0.25, 0.65), rng.uniform(0.85, 1.25), rng.uniform(1.25, 1.75)))


def _premium_ratio_range(archetype: str) -> tuple[float, float]:
    return {
        "BALANCED": (0.045, 0.085),
        "UNDERINSURED": (0.018, 0.050),
        "OVERINSURED": (0.10, 0.19),
        "DUPLICATED": (0.075, 0.13),
        "OUTDATED": (0.045, 0.10),
        "RENEWAL_HEAVY": (0.055, 0.12),
        "GAP_SPECIFIC": (0.045, 0.095),
        "MIXED": (0.05, 0.12),
    }[archetype]


def _contract_count(archetype: str, rng: random.Random) -> int:
    if archetype in {"OVERINSURED", "DUPLICATED", "RENEWAL_HEAVY"}:
        return rng.randint(5, MAX_CONTRACTS_V1)
    if archetype == "UNDERINSURED":
        return rng.randint(2, 4)
    return rng.randint(3, MAX_CONTRACTS_V1)


def _year_for_contract(age: int, rng: random.Random, index: int) -> tuple[int, int]:
    current_year = _REFERENCE_DATE.year
    max_years = max(1, age - 20)
    years_ago = min(max_years, max(1, rng.randint(1, min(18, max_years)) + index // 2))
    start_year = current_year - years_ago
    start_age = age - years_ago
    return start_year, start_age


def _coverage_split(total: int, n: int, rng: random.Random) -> list[int]:
    if total <= 0 or n <= 0:
        return [0] * n
    weights = [rng.uniform(0.35, 1.4) for _ in range(n)]
    s = sum(weights)
    raw = [_round_amount(total * w / s, step=10) for w in weights]
    diff = total - sum(raw)
    raw[0] = max(0, raw[0] + diff)
    return raw


def _product_name(kind: str, year: int, index: int) -> str:
    yy = str(year)[-2:]
    names = {
        "health": f"(가상) 종합건강보험 {yy}{index+1:02d}",
        "life": f"(가상) 종신보험 {yy}{index+1:02d}",
        "driver": f"(가상) 운전자상해보험 {yy}{index+1:02d}",
        "indemnity": f"(가상) 4세대 실손의료비보험 {yy}{index+1:02d}",
    }
    return names[kind]


@dataclass(frozen=True)
class InsurancePortfolio:
    version: str
    seed: int
    archetype: str
    complexity: str
    gap_code: str | None
    total_monthly_premium_won: int
    contracts: list[dict[str, Any]]
    coverage_totals: dict[str, int]
    synthetic_training_data: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_insurance_portfolio(seed: int, customer: dict[str, Any], *, forced_archetype: str | None = None) -> InsurancePortfolio:
    rng = random.Random(int(seed) ^ 0x51A2C3)
    archetype = forced_archetype or rng.choice(PORTFOLIO_ARCHETYPES)
    if archetype not in PORTFOLIO_ARCHETYPES:
        raise ValueError(f"unknown portfolio archetype: {archetype}")

    age = int(customer.get("age") or customer.get("ground_truth", {}).get("identity", {}).get("age", 40))
    financial = customer.get("ground_truth", {}).get("financial", {})
    household_income = int(financial.get("household_monthly_income_won") or 3500000)
    ratio_low, ratio_high = _premium_ratio_range(archetype)
    target_premium = max(45000, int(household_income * rng.uniform(ratio_low, ratio_high)))

    gap_code = None
    if archetype == "GAP_SPECIFIC":
        gap_code = rng.choice(("CANCER_GENERAL", "BRAIN_VASCULAR", "HEART_ISCHEMIC", "DEATH_DISEASE", "CAREGIVER_DISEASE"))

    totals: dict[str, int] = {}
    for code in _CORE_CODES:
        target = training_target(code, customer)
        multiplier = _target_multiplier(archetype, code, rng, gap_code)
        totals[code] = _round_amount(target * multiplier, step=10)
        if rng.random() < 0.05 and code not in {"CANCER_GENERAL", "DEATH_DISEASE"}:
            totals[code] = 0

    # Indemnity is common but not universal; generated as current 4th-generation-like training data.
    has_indemnity = rng.random() < 0.86
    for code in _INDEMNITY_CODES:
        totals[code] = _BASE_TARGETS[code] if has_indemnity else 0

    has_driver = age <= 69 and rng.random() < 0.70
    for code in _DRIVER_CODES:
        totals[code] = _BASE_TARGETS[code] if has_driver else 0

    count = _contract_count(archetype, rng)
    kinds: list[str] = ["health"] * count
    if has_indemnity:
        kinds[-1] = "indemnity"
    if has_driver and count >= 3:
        kinds[-2] = "driver"
    if count >= 4 and rng.random() < 0.60:
        kinds[1] = "life"

    selected_insurers = rng.sample(_INSURERS, k=min(count, len(_INSURERS)))
    if len(selected_insurers) < count:
        selected_insurers += [rng.choice(_INSURERS) for _ in range(count-len(selected_insurers))]

    contract_coverages: list[dict[str, int]] = [dict() for _ in range(count)]
    for code, total in totals.items():
        if total <= 0:
            continue
        if code in _INDEMNITY_CODES:
            eligible = [i for i,k in enumerate(kinds) if k == "indemnity"]
        elif code in _DRIVER_CODES:
            eligible = [i for i,k in enumerate(kinds) if k == "driver"]
        elif code.startswith("DEATH_"):
            eligible = [i for i,k in enumerate(kinds) if k in {"health", "life"}]
        else:
            eligible = [i for i,k in enumerate(kinds) if k == "health"]
        if not eligible:
            eligible = [0]
        max_pieces = min(len(eligible), 2 if archetype not in {"DUPLICATED", "OVERINSURED"} else 3)
        pieces = rng.randint(1, max_pieces)
        recipients = rng.sample(eligible, k=pieces)
        split = _coverage_split(total, pieces, rng)
        for idx, amount in zip(recipients, split):
            if amount:
                contract_coverages[idx][code] = contract_coverages[idx].get(code, 0) + amount

    raw_weights = []
    for kind in kinds:
        raw_weights.append({"health": 1.0, "life": 1.15, "driver": 0.22, "indemnity": 0.18}[kind] * rng.uniform(0.75, 1.25))
    weight_sum = sum(raw_weights)
    premiums = [max(9000, int(target_premium * w / weight_sum // 100 * 100)) for w in raw_weights]
    premium_diff = target_premium - sum(premiums)
    premiums[0] = max(9000, premiums[0] + premium_diff)

    contracts: list[dict[str, Any]] = []
    for i in range(count):
        insurer, insurer_type = selected_insurers[i]
        kind = kinds[i]
        start_year, start_age = _year_for_contract(age, rng, i)
        start_month = rng.randint(1, 12)
        start_day = rng.randint(1, 28)
        paid_months = max(1, (_REFERENCE_DATE.year - start_year) * 12 + _REFERENCE_DATE.month - start_month)
        if kind == "indemnity":
            total_months = 120
            pay_term_text = "갱신"
            coverage_end = "갱신"
            renewal = "renewal"
        else:
            total_months = rng.choice((120, 180, 240, 240, 360))
            pay_term_years = total_months // 12
            pay_term_text = str(start_year + pay_term_years)
            if kind == "life":
                coverage_end = "종신"
            else:
                cover_age = rng.choice((80, 90, 100))
                coverage_end = str(start_year + max(1, cover_age - start_age))
            renewal = "renewal" if archetype == "RENEWAL_HEAVY" and rng.random() < 0.72 else "nonrenewal"
        paid_months = min(paid_months, total_months)
        premium = int(premiums[i])
        contract = {
            "contract_id": f"C{i+1:02d}",
            "insurer": insurer,
            "insurer_type": insurer_type,
            "product_kind": kind,
            "product_name": _product_name(kind, start_year, i),
            "start_date": f"{start_year:04d}.{start_month:02d}.{start_day:02d}",
            "start_age": start_age,
            "premium_won": premium,
            "payment_cycle": "월납",
            "paid_months": paid_months,
            "total_payment_months": total_months,
            "payment_end": pay_term_text,
            "coverage_end": coverage_end,
            "renewal_type": renewal,
            "coverages": [
                {"coverage_code": code, "amount_manwon": amount}
                for code, amount in sorted(contract_coverages[i].items()) if amount > 0
            ],
        }
        contract["paid_amount_won"] = premium * paid_months
        contract["future_amount_won"] = premium * max(0, total_months-paid_months)
        contract["total_amount_won"] = premium * total_months
        contracts.append(contract)

    # Recalculate from contract rows to guarantee one source of truth.
    recomputed: dict[str, int] = {}
    for contract in contracts:
        for cov in contract["coverages"]:
            recomputed[cov["coverage_code"]] = recomputed.get(cov["coverage_code"], 0) + int(cov["amount_manwon"])
    total_monthly = sum(int(c["premium_won"]) for c in contracts)
    complexity = "low" if count <= 3 else "medium" if count <= 5 else "high"

    return InsurancePortfolio(
        version=INSURANCE_GENERATOR_VERSION,
        seed=int(seed), archetype=archetype, complexity=complexity, gap_code=gap_code,
        total_monthly_premium_won=total_monthly, contracts=contracts, coverage_totals=recomputed,
    )
