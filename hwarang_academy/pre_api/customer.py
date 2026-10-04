"""Deterministic conditional customer generator. No external API is used."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import random
from typing import Any

from .constants import CUSTOMER_GENERATOR_VERSION, MAX_CUSTOMER_AGE, MIN_CUSTOMER_AGE, VOICE_PROFILE_VERSION
from .training import FOCUSES, validate_training_focus

_MALE_NAMES = ("김민준", "박준호", "이도윤", "최현우", "정우진", "한지훈", "윤성민", "오지환")
_FEMALE_NAMES = ("김서연", "박수진", "이민지", "최은정", "정하윤", "한지혜", "윤소영", "오유진")
_OCCUPATIONS = {
    "office_worker": ("회사원", 3300000, 6200000),
    "public_worker": ("공무원", 3000000, 5200000),
    "professional": ("전문직", 5500000, 12000000),
    "self_employed": ("자영업자", 2800000, 9000000),
    "freelancer": ("프리랜서", 2500000, 6500000),
    "sales": ("영업직", 3000000, 8000000),
    "production": ("생산직", 3000000, 5200000),
    "homemaker": ("전업주부", 0, 0),
    "retired": ("은퇴자", 1500000, 4500000),
}


def _weighted_age(rng: random.Random) -> int:
    decade = rng.choices([30, 40, 50, 60, 70], weights=[28, 28, 23, 15, 6], k=1)[0]
    upper = 79 if decade == 70 else decade + 9
    return rng.randint(decade, upper)


def _life_stage(age: int, married: bool, child_count: int, retired: bool) -> str:
    if retired or age >= 65:
        return "RETIREMENT"
    if not married:
        return "SINGLE_MID" if age >= 40 else "SINGLE_EARLY"
    if child_count == 0:
        return "NEWLY_MARRIED" if age < 45 else "COUPLE_MID"
    if age < 43:
        return "YOUNG_FAMILY"
    if age < 55:
        return "CHILD_EDUCATION"
    return "PRE_RETIREMENT"


def _voice_profile(gender: str, age: int, rng: random.Random) -> dict[str, Any]:
    speed = rng.choices(["slow", "normal", "fast"], weights=[20 if age >= 60 else 8, 68, 12 if age >= 60 else 24], k=1)[0]
    tone = rng.choice(("calm", "cautious", "warm", "blunt"))
    return {
        "version": VOICE_PROFILE_VERSION,
        "presentation": "masculine" if gender == "male" else "feminine",
        "age_band": f"{(age // 10) * 10}s" if age < 70 else "70plus",
        "speaking_speed": speed,
        "energy": rng.choice(("low", "normal", "normal", "high")),
        "tone": tone,
        "voice_id": None,
    }


def _capacity(monthly_income: int, monthly_fixed: int, monthly_savings: int, debt: int) -> str:
    if monthly_income <= 0:
        return "constrained"
    free = monthly_income - monthly_fixed - monthly_savings
    ratio = free / monthly_income
    if ratio < 0.05 or debt > monthly_income * 55:
        return "constrained"
    if ratio < 0.12:
        return "tight"
    if ratio < 0.25:
        return "stable"
    if ratio < 0.42:
        return "comfortable"
    return "affluent"


@dataclass(frozen=True)
class CustomerProfile:
    version: str
    seed: int
    alias: str
    age: int
    gender: str
    life_stage: str
    ground_truth: dict[str, Any]
    customer_beliefs: dict[str, Any]
    personality: dict[str, Any]
    motivations: dict[str, Any]
    relationship: dict[str, Any]
    voice_profile: dict[str, Any]
    public_state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_customer(seed: int, *, training_focus: str = "comprehensive", difficulty: str = "standard") -> CustomerProfile:
    focus = validate_training_focus(training_focus)
    rng = random.Random(int(seed))
    age = _weighted_age(rng)
    age = max(MIN_CUSTOMER_AGE, min(MAX_CUSTOMER_AGE, age))
    gender = rng.choice(("male", "female"))
    alias = rng.choice(_MALE_NAMES if gender == "male" else _FEMALE_NAMES)

    if age >= 70:
        married_prob = 0.72
    elif age >= 40:
        married_prob = 0.82
    else:
        married_prob = 0.58
    married = rng.random() < married_prob
    child_count = 0
    if married:
        child_count = rng.choices([0, 1, 2, 3], weights=[18, 38, 36, 8], k=1)[0]
    child_ages: list[int] = []
    if child_count:
        max_child = min(35, max(1, age - 23))
        for _ in range(child_count):
            child_ages.append(rng.randint(0, max_child))
        child_ages.sort(reverse=True)

    retired = age >= 65 and rng.random() < 0.72
    occupation_keys = list(_OCCUPATIONS)
    weights = [34, 10, 8, 16, 8, 8, 8, 3, 5]
    if retired:
        occupation = "retired"
    else:
        occupation = rng.choices(occupation_keys, weights=weights, k=1)[0]
        if occupation == "retired":
            occupation = "office_worker"
    occupation_name, income_low, income_high = _OCCUPATIONS[occupation]
    own_income = rng.randint(income_low // 100000, income_high // 100000) * 100000 if income_high else 0

    spouse_income = 0
    spouse_working = False
    if married:
        spouse_working = rng.random() < (0.68 if age < 60 else 0.42)
        if spouse_working:
            spouse_income = rng.randint(2200000 // 100000, 6500000 // 100000) * 100000

    household_income = own_income + spouse_income
    if household_income <= 0:
        household_income = rng.randint(1800000 // 100000, 3500000 // 100000) * 100000

    housing = rng.choice(("own_with_loan", "own_no_loan", "jeonse_with_loan", "jeonse_no_loan", "monthly_rent"))
    base_expense = 1400000 + child_count * 550000 + (350000 if married else 0)
    living_expense = int((base_expense + rng.randint(0, 1500000)) // 10000 * 10000)
    loan_payment = 0 if housing in {"own_no_loan", "jeonse_no_loan"} else rng.randint(25, 140) * 10000
    debt = 0 if loan_payment == 0 else rng.randint(1500, 26000) * 10000
    monthly_savings = max(0, min(int(household_income * rng.uniform(0.04, 0.28)), max(0, household_income-living_expense-loan_payment-200000)))
    emergency_fund = rng.randint(1, 15) * max(500000, living_expense // 2)
    assets = max(0, rng.randint(1000, 80000) * 10000 + (age - 30) * rng.randint(300, 1800) * 10000)
    monthly_fixed = living_expense + loan_payment
    financial_capacity = _capacity(household_income, monthly_fixed, monthly_savings, debt)

    focus_mod = FOCUSES[focus].customer_modifiers
    difficulty_base = {"easy": -1, "standard": 0, "hard": 1}.get(difficulty, 0)
    sales_resistance = max(0, min(4, rng.randint(1, 3) + difficulty_base + int(focus_mod.get("sales_resistance", 0))))
    disclosure_resistance = max(0, min(4, rng.randint(0, 2) + difficulty_base + int(focus_mod.get("disclosure_resistance", 0))))
    decision_inertia = max(0, min(4, rng.randint(0, 2) + difficulty_base + int(focus_mod.get("decision_inertia", 0))))
    insurance_knowledge_level = max(0, min(4, rng.randint(0, 3) + int(focus_mod.get("insurance_knowledge", 0))))

    risk_attitude = rng.choice(("risk_averse", "balanced", "balanced", "risk_tolerant"))
    insurance_attitude = rng.choice(("positive", "neutral", "neutral", "skeptical", "negative"))
    surface_candidates = ["보험료 부담", "현재 보험이 적절한지 확인", "암 보장 걱정", "가족의 생활비 위험", "보장 중복 점검", "노후 보험료 부담"]
    surface_need = rng.choice(surface_candidates)
    if child_count and age < 55:
        latent_candidates = ["소득상실 시 가족생활 유지", "자녀 성장기 사망보장", "치료 중 생활비 공백", "보험료 구조 비효율"]
    elif age >= 60:
        latent_candidates = ["은퇴 후 보험료 지속 가능성", "간병·장기요양 위험", "현금흐름 훼손 방지", "오래된 보장 범위 점검"]
    else:
        latent_candidates = ["치료 중 소득공백", "노후자금 훼손 위험", "보장공백", "보험료 구조 비효율"]
    latent_need = rng.choice(latent_candidates)

    if married:
        decision_structure = rng.choices(("joint_with_spouse", "self_led_spouse_consult", "self_decision"), weights=(58, 30, 12), k=1)[0]
    else:
        decision_structure = rng.choice(("self_decision", "self_decision", "family_consult"))

    public_state = {
        "customer_alias": alias,
        "age": age,
        "occupation": occupation_name,
        "relationship": "소개 고객",
        "known_note": surface_need if rng.random() < 0.62 else "보험 관련 내용을 한번 점검해보고 싶다고 함",
    }

    return CustomerProfile(
        version=CUSTOMER_GENERATOR_VERSION,
        seed=int(seed), alias=alias, age=age, gender=gender,
        life_stage=_life_stage(age, married, child_count, retired),
        ground_truth={
            "identity": {"age": age, "gender": gender},
            "family": {"married": married, "child_count": child_count, "child_ages": child_ages},
            "occupation": {"code": occupation, "name": occupation_name, "retired": retired},
            "financial": {
                "own_monthly_income_won": own_income,
                "spouse_monthly_income_won": spouse_income,
                "household_monthly_income_won": household_income,
                "living_expense_won": living_expense,
                "loan_payment_won": loan_payment,
                "monthly_savings_won": monthly_savings,
                "emergency_fund_won": emergency_fund,
                "assets_won": assets,
                "debt_won": debt,
                "housing": housing,
                "financial_capacity": financial_capacity,
            },
            "decision_structure": decision_structure,
        },
        customer_beliefs={
            "insurance_knowledge_level": insurance_knowledge_level,
            "insurance_knowledge": ("very_low", "low", "medium", "high", "very_high")[insurance_knowledge_level],
            "risk_attitude": risk_attitude,
            "insurance_attitude": insurance_attitude,
            "financial_perception": rng.choice(("insurance_feels_expensive", "manageable", "not_sure")),
        },
        personality={
            "sales_resistance": sales_resistance,
            "disclosure_resistance": disclosure_resistance,
            "decision_inertia": decision_inertia,
            "verbosity": max(0, min(4, rng.randint(1, 3) + int(focus_mod.get("verbosity", 0)))),
            "question_reason_sensitivity": max(0, min(4, rng.randint(0, 2) + int(focus_mod.get("question_reason_sensitivity", 0)))),
            "financial_sensitivity": max(0, min(4, rng.randint(0, 2) + int(focus_mod.get("financial_sensitivity", 0)))),
            "objection_tendency": max(0, min(4, rng.randint(0, 2) + int(focus_mod.get("objection_tendency", 0)))),
            "risk_underestimation": max(0, min(4, rng.randint(0, 2) + int(focus_mod.get("risk_underestimation", 0)))),
        },
        motivations={
            "surface_needs": [surface_need],
            "latent_needs": [latent_need],
            "priorities": rng.sample(["보험료", "암", "뇌·심장", "가족생활", "노후", "간병"], k=3),
            "fears": rng.sample(["보험료 증가", "큰 질병", "소득 중단", "불필요한 가입", "노후 현금흐름"], k=2),
        },
        relationship={
            "trust": "cautious",
            "interest": "low" if sales_resistance >= 3 else "medium",
            "pressure_level": "none",
            "pressure_quality": "unrated",
            "engagement": "reserved" if disclosure_resistance >= 3 else "neutral",
        },
        voice_profile=_voice_profile(gender, age, rng),
        public_state=public_state,
    )
