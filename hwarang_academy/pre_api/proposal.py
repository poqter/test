"""Training-only proposal-option generator for M2 preparation."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import random
from typing import Any

from .constants import PROPOSAL_GENERATOR_VERSION


def _add_action(actions: list[dict[str, Any]], action: str, code: str, reason: str, amount: int | None = None) -> None:
    row = {"action": action, "coverage_code": code, "reason": reason}
    if amount is not None:
        row["target_change_manwon"] = int(amount)
    actions.append(row)


@dataclass(frozen=True)
class ProposalState:
    version: str
    options: list[dict[str, Any]]
    fp_can_modify: bool = True
    actual_quote: bool = False
    note: str = "교육용 가상 제안안이며 실제 보험료/인수/상품조건 견적이 아닙니다."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_proposals(seed: int, customer: dict[str, Any], insurance_state: dict[str, Any], analysis: dict[str, Any]) -> ProposalState:
    rng = random.Random(int(seed) ^ 0xA771)
    objective = analysis.get("objective", {})
    affordability = analysis.get("affordability", {})
    monthly = int(affordability.get("monthly_premium_won") or insurance_state.get("total_monthly_premium_won") or 0)
    capacity = str(affordability.get("financial_capacity") or "stable")

    gaps = [code for code, row in objective.items() if row.get("objective_coverage") in {"absent", "low", "moderate"}]
    high = [code for code, row in objective.items() if row.get("objective_coverage") == "high"]
    preferred = [code for code, row in objective.items() if row.get("customer_priority") == "high"]

    maintain_actions: list[dict[str, Any]] = []
    for code in gaps[:2]:
        _add_action(maintain_actions, "add_or_increase", code, "객관적 보장 공백/취약 영역 보완", 1000 if "SURGERY" not in code else 50)
    option_a_delta = (18000 + 7000 * len(maintain_actions)) if maintain_actions else 0

    efficiency_actions: list[dict[str, Any]] = []
    for code in high[:2]:
        _add_action(efficiency_actions, "review_or_reduce", code, "중복·과다 가능 영역의 효율 점검")
    for code in gaps[:2]:
        _add_action(efficiency_actions, "reallocate", code, "절감 여력을 우선순위 보장으로 재배치", 1000)
    if high:
        option_b_delta = -rng.randint(3, 18) * 1000
    elif gaps:
        option_b_delta = rng.randint(0, 8) * 1000
    else:
        option_b_delta = -rng.randint(0, 10) * 1000

    preference_actions = list(maintain_actions)
    # Sufficient coverage can still be increased when personal priority and affordability support it.
    extra_candidates = [code for code in preferred if objective.get(code, {}).get("objective_coverage") in {"sufficient", "high"}]
    if extra_candidates and capacity in {"stable", "comfortable", "affluent"}:
        code = extra_candidates[0]
        _add_action(preference_actions, "optional_increase", code, "객관적으로 부족하지 않지만 고객 개인 우선순위와 경제여력을 반영한 선택", 1000)
    option_c_delta = option_a_delta + (22000 if len(preference_actions) > len(maintain_actions) else 9000)

    no_change_reason = "현재 구조의 장점을 유지하면서 필요한 부분만 확인"
    if not gaps and not high:
        no_change_reason = "객관적 보장공백이 크지 않아 무리한 변경보다 현 계약 유지가 우선"

    options = [
        {
            "option_id": "A",
            "name": "유지·핵심보완안",
            "strategy": "기존 계약을 최대한 유지하고 확인된 취약 영역만 보완",
            "actions": maintain_actions,
            "estimated_monthly_delta_won": option_a_delta,
            "rationale": no_change_reason,
        },
        {
            "option_id": "B",
            "name": "효율·재배치안",
            "strategy": "중복·과다 가능 영역을 점검하고 고객 우선순위로 보험료를 재배치",
            "actions": efficiency_actions,
            "estimated_monthly_delta_won": option_b_delta,
            "rationale": "보험료 효율과 보장 균형을 함께 검토",
        },
        {
            "option_id": "C",
            "name": "고객우선 확대안",
            "strategy": "보장분석 기준뿐 아니라 고객의 강한 개인적 우선순위를 적극 반영",
            "actions": preference_actions,
            "estimated_monthly_delta_won": option_c_delta,
            "rationale": "충분한 보장도 고객의 위험선호·가족력·경제여력에 따라 합리적으로 추가할 수 있음",
        },
    ]
    if not gaps:
        options[0]["estimated_monthly_delta_won"] = 0
        options[0]["actions"] = [{"action": "maintain", "coverage_code": "PORTFOLIO", "reason": no_change_reason}]

    for option in options:
        option["estimated_new_monthly_premium_won"] = max(0, monthly + int(option["estimated_monthly_delta_won"]))
        option["synthetic_estimate"] = True
    return ProposalState(version=PROPOSAL_GENERATOR_VERSION, options=options)
