"""Coverage aggregation/mapping and training-only objective analysis."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .constants import COVERAGE_ANALYSIS_VERSION, COVERAGE_MAPPING_VERSION
from .insurance import training_target

# Exact row order of the user-approved '보장 분석' Excel template.
EXCEL_COVERAGE_ROWS: tuple[tuple[str, str | None], ...] = (
    ("일반 사망", None),
    ("질병 사망", "DEATH_DISEASE"),
    ("재해(상해) 사망", "DEATH_ACCIDENT"),
    ("질병 후유장해 3%일 경우", "DISABILITY_DISEASE_3"),
    ("상해 후유장해 3%일 경우", "DISABILITY_ACCIDENT_3"),
    ("일반 암", "CANCER_GENERAL"),
    ("유사 암", "CANCER_MINOR"),
    ("뇌 혈관", "BRAIN_VASCULAR"),
    ("뇌 졸중", "BRAIN_STROKE"),
    ("뇌 출혈", "BRAIN_HEMORRHAGE"),
    ("허혈성 심장 질환", "HEART_ISCHEMIC"),
    ("급성 심근경색증", "HEART_AMI"),
    ("질병 수술", "SURGERY_DISEASE"),
    ("질병 종 수술(1~5종)", "SURGERY_DISEASE_CLASS"),
    ("상해 수술", "SURGERY_ACCIDENT"),
    ("상해 종 수술(1~5종)", "SURGERY_ACCIDENT_CLASS"),
    ("뇌혈관 질환 수술", "SURGERY_BRAIN"),
    ("허혈성 심장 질환 수술", "SURGERY_HEART"),
    ("질병 입원", "HOSP_DISEASE"),
    ("상해 입원", "HOSP_ACCIDENT"),
    ("간병인 지원(질병)", "CAREGIVER_DISEASE"),
    ("간병인 지원(상해)", "CAREGIVER_ACCIDENT"),
    ("간호간병통합입원(상해)", "NURSING_ACCIDENT"),
    ("간호간병통합입원(질병)", "NURSING_DISEASE"),
    ("교통사고 처리 지원금", "DRIVER_SETTLEMENT"),
    ("교통사고 처리 지원금(6주 미만)", "DRIVER_SETTLEMENT_UNDER6"),
    ("변호사 선임 비용", "DRIVER_LAWYER"),
    ("운전자 벌금(대인)", "DRIVER_FINE_PERSON"),
    ("운전자 벌금(대물)", "DRIVER_FINE_PROPERTY"),
    ("자동차사고 부상 위로금", "DRIVER_INJURY"),
    ("일상생활 배상책임", "LIABILITY_DAILY"),
    ("치아 보철 치료비", "DENTAL_PROSTHETIC"),
    ("치아 보존 치료비", "DENTAL_CONSERVATIVE"),
    ("골절 진단비", "DIAG_FRACTURE"),
    ("질병 입원(실손)", "INDEMNITY_DISEASE_IN"),
    ("질병 통원(실손)", "INDEMNITY_DISEASE_OUT"),
    ("상해 입원(실손)", "INDEMNITY_ACCIDENT_IN"),
    ("상해 통원(실손)", "INDEMNITY_ACCIDENT_OUT"),
    ("기타", None),
)

KEY_ANALYSIS_CODES = (
    "DEATH_DISEASE", "CANCER_GENERAL", "CANCER_MINOR", "BRAIN_VASCULAR", "HEART_ISCHEMIC",
    "SURGERY_DISEASE", "CAREGIVER_DISEASE", "INDEMNITY_DISEASE_IN",
)


def coverage_totals_from_contracts(insurance_state: dict[str, Any]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for contract in insurance_state.get("contracts", []):
        for coverage in contract.get("coverages", []):
            code = str(coverage.get("coverage_code") or "")
            amount = int(coverage.get("amount_manwon") or 0)
            if code and amount > 0:
                totals[code] = totals.get(code, 0) + amount
    return totals


def excel_contract_matrix(insurance_state: dict[str, Any]) -> dict[str, list[int | None]]:
    contracts = list(insurance_state.get("contracts", []))
    result: dict[str, list[int | None]] = {}
    for _, code in EXCEL_COVERAGE_ROWS:
        if not code:
            continue
        row: list[int | None] = []
        for contract in contracts:
            amount = 0
            for coverage in contract.get("coverages", []):
                if coverage.get("coverage_code") == code:
                    amount += int(coverage.get("amount_manwon") or 0)
            row.append(amount if amount > 0 else None)
        result[code] = row
    return result


def _status(total: int, target: int) -> str:
    if total <= 0:
        return "absent"
    if target <= 0:
        return "present"
    ratio = total / target
    if ratio < 0.40:
        return "low"
    if ratio < 0.80:
        return "moderate"
    if ratio <= 1.35:
        return "sufficient"
    return "high"


def _priority_for(code: str, customer: dict[str, Any]) -> str:
    priorities = " ".join(customer.get("motivations", {}).get("priorities", []))
    latent = " ".join(customer.get("motivations", {}).get("latent_needs", []))
    surface = " ".join(customer.get("motivations", {}).get("surface_needs", []))
    text = " ".join((priorities, latent, surface))
    if code in {"CANCER_GENERAL", "CANCER_MINOR"} and "암" in text:
        return "high"
    if code in {"BRAIN_VASCULAR", "HEART_ISCHEMIC"} and any(x in text for x in ("뇌", "심장", "큰 질병")):
        return "high"
    if code == "DEATH_DISEASE" and any(x in text for x in ("가족", "사망", "소득상실", "생활비")):
        return "high"
    if code == "CAREGIVER_DISEASE" and any(x in text for x in ("간병", "노후")):
        return "high"
    return "medium"


@dataclass(frozen=True)
class CoverageAnalysis:
    version: str
    mapping_version: str
    coverage_totals: dict[str, int]
    objective: dict[str, dict[str, Any]]
    affordability: dict[str, Any]
    portfolio_flags: list[str]
    training_reference_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_coverage(customer: dict[str, Any], insurance_state: dict[str, Any]) -> CoverageAnalysis:
    totals = coverage_totals_from_contracts(insurance_state)
    objective: dict[str, dict[str, Any]] = {}
    for code in KEY_ANALYSIS_CODES:
        target = training_target(code, customer)
        total = int(totals.get(code, 0))
        objective[code] = {
            "amount_manwon": total,
            "training_reference_manwon": target,
            "objective_coverage": _status(total, target),
            "customer_priority": _priority_for(code, customer),
        }

    monthly = int(insurance_state.get("total_monthly_premium_won") or sum(int(c.get("premium_won") or 0) for c in insurance_state.get("contracts", [])))
    income = int(customer.get("ground_truth", {}).get("financial", {}).get("household_monthly_income_won") or 1)
    ratio = monthly / max(income, 1)
    financial_capacity = customer.get("ground_truth", {}).get("financial", {}).get("financial_capacity", "stable")
    affordability_state = "comfortable" if ratio < 0.05 else "manageable" if ratio < 0.10 else "tight" if ratio < 0.15 else "burdensome"
    if financial_capacity == "constrained" and affordability_state == "manageable":
        affordability_state = "tight"

    flags: list[str] = []
    archetype = str(insurance_state.get("archetype") or "")
    if archetype:
        flags.append(archetype.lower())
    if ratio >= 0.12:
        flags.append("premium_load_high")
    if sum(1 for x in objective.values() if x["objective_coverage"] in {"absent", "low"}) >= 2:
        flags.append("multiple_gaps")
    if sum(1 for x in objective.values() if x["objective_coverage"] == "high") >= 2:
        flags.append("possible_overcoverage")

    return CoverageAnalysis(
        version=COVERAGE_ANALYSIS_VERSION,
        mapping_version=COVERAGE_MAPPING_VERSION,
        coverage_totals=totals,
        objective=objective,
        affordability={
            "monthly_premium_won": monthly,
            "household_monthly_income_won": income,
            "premium_to_income_ratio": round(ratio, 4),
            "financial_capacity": financial_capacity,
            "state": affordability_state,
        },
        portfolio_flags=flags,
    )
