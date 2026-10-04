"""Deterministic validation harness for the pre-API simulation core."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any

from .case_engine import create_case
from .coverage import coverage_totals_from_contracts
from .excel import workbook_payload
from .constants import MIN_CUSTOMER_AGE, MAX_CONTRACTS_V1, PORTFOLIO_ARCHETYPES


FIXED_CASES = (
    {"id": "TEST-01", "seed": 738291, "archetype": "MIXED", "focus": "comprehensive", "difficulty": "standard"},
    {"id": "TEST-02", "seed": 314159, "archetype": "BALANCED", "focus": "information_discovery", "difficulty": "easy"},
    {"id": "TEST-03", "seed": 271828, "archetype": "OVERINSURED", "focus": "closing", "difficulty": "hard"},
    {"id": "TEST-04", "seed": 161803, "archetype": "OUTDATED", "focus": "coverage_analysis", "difficulty": "standard"},
    {"id": "TEST-05", "seed": 141421, "archetype": "GAP_SPECIFIC", "focus": "objection_diagnosis", "difficulty": "hard"},
)


@dataclass
class ValidationReport:
    cases_checked: int
    failures: list[str]
    age_min: int
    age_max: int
    archetype_counts: dict[str, int]
    complexity_counts: dict[str, int]
    training_focus_counts: dict[str, int]
    seed_reproducibility_passed: bool
    fixed_cases_passed: bool

    @property
    def passed(self) -> bool:
        return not self.failures and self.seed_reproducibility_passed and self.fixed_cases_passed

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


def _check_case(case: Any, label: str, failures: list[str]) -> None:
    customer = case.customer_state
    insurance = case.insurance_state
    age = int(customer["age"])
    if age < MIN_CUSTOMER_AGE:
        failures.append(f"{label}: customer age below minimum: {age}")
    contracts = list(insurance.get("contracts", []))
    if not (2 <= len(contracts) <= MAX_CONTRACTS_V1):
        failures.append(f"{label}: contract count out of range: {len(contracts)}")
    for c in contracts:
        if int(c.get("start_age") or 0) < 20 or int(c.get("start_age") or 0) > age:
            failures.append(f"{label}: invalid start age {c.get('start_age')} for age {age}")
        if int(c.get("premium_won") or 0) <= 0:
            failures.append(f"{label}: non-positive premium")
        if int(c.get("paid_months") or 0) > int(c.get("total_payment_months") or 0):
            failures.append(f"{label}: paid months exceed total")
        for cov in c.get("coverages", []):
            if int(cov.get("amount_manwon") or 0) <= 0:
                failures.append(f"{label}: zero/negative stored coverage")
    recomputed = coverage_totals_from_contracts(insurance)
    if recomputed != insurance.get("coverage_totals"):
        failures.append(f"{label}: coverage totals mismatch")
    payload = workbook_payload(customer, insurance)
    if payload["total_monthly_premium_won"] != insurance.get("total_monthly_premium_won"):
        failures.append(f"{label}: Excel payload premium mismatch")
    for row in payload["coverage_rows"]:
        if any(v == 0 for v in row["values"] if v is not None):
            failures.append(f"{label}: zero leaked into Excel payload")
        expected = sum(int(v or 0) for v in row["values"])
        if (expected or None) != row["total_manwon"]:
            failures.append(f"{label}: Excel row total mismatch at {row['row']}")


def run_validation(case_count: int = 1000) -> ValidationReport:
    failures: list[str] = []
    archetypes: Counter[str] = Counter()
    complexities: Counter[str] = Counter()
    focuses: Counter[str] = Counter()
    ages: list[int] = []
    focus_cycle = ("comprehensive", "information_discovery", "closing", "coverage_analysis", "persuasion", "objection_handling")
    difficulty_cycle = ("easy", "standard", "hard")

    for i in range(case_count):
        seed = 100000 + i * 7919
        focus = focus_cycle[i % len(focus_cycle)]
        difficulty = difficulty_cycle[i % len(difficulty_cycle)]
        case = create_case(seed, training_focus=focus, consultation_difficulty=difficulty, insurance_known=(i % 2 == 0))
        _check_case(case, f"RANDOM-{i+1:04d}", failures)
        ages.append(int(case.customer_state["age"]))
        archetypes[str(case.insurance_state["archetype"])] += 1
        complexities[str(case.insurance_state["complexity"])] += 1
        focuses[case.training_focus] += 1

    # Determinism check across the complete Case representation.
    a = create_case(987654321, training_focus="closing", consultation_difficulty="hard", insurance_known=True)
    b = create_case(987654321, training_focus="closing", consultation_difficulty="hard", insurance_known=True)
    reproducible = a.digest() == b.digest()
    if not reproducible:
        failures.append("seed reproducibility failed")

    fixed_ok = True
    for spec in FIXED_CASES:
        c = create_case(
            spec["seed"], training_focus=spec["focus"], consultation_difficulty=spec["difficulty"],
            insurance_known=True, forced_archetype=spec["archetype"],
        )
        _check_case(c, spec["id"], failures)
        if c.insurance_state["archetype"] != spec["archetype"]:
            fixed_ok = False
            failures.append(f"{spec['id']}: forced archetype mismatch")

    missing = set(PORTFOLIO_ARCHETYPES) - set(archetypes)
    if missing:
        failures.append("random generation did not cover archetypes: " + ",".join(sorted(missing)))

    return ValidationReport(
        cases_checked=case_count,
        failures=failures,
        age_min=min(ages) if ages else 0,
        age_max=max(ages) if ages else 0,
        archetype_counts=dict(archetypes),
        complexity_counts=dict(complexities),
        training_focus_counts=dict(focuses),
        seed_reproducibility_passed=reproducible,
        fixed_cases_passed=fixed_ok,
    )
