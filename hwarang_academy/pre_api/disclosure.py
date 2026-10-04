"""Customer-visible fact projection for the future AI customer.

The full Case contains facts that are useful to Coach/Evaluator but must never be
implicitly exposed to the customer model (for example coverage analysis and
proposal recommendations).  This module builds the only fact namespace that the
Customer AI may disclose.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


_ALLOWED_CONTRACT_FIELDS = {
    "insurer",
    "product_kind",
    "product_name",
    "premium_won",
    "payment_cycle",
    "payment_end",
    "coverage_end",
    "renewal_type",
}


def _contract_map(insurance_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(insurance_state.get("contracts") or [], start=1):
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("contract_id") or f"C{index:02d}")
        result[cid] = raw
    return result


def _set_nested(target: dict[str, Any], path: list[str], value: Any) -> None:
    node = target
    for part in path[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[path[-1]] = deepcopy(value)


def _apply_explicit_insurance_fields(
    memory: dict[str, Any],
    insurance_state: dict[str, Any],
    session_state: dict[str, Any],
) -> None:
    """Copy only Python-approved insurance fields into customer memory.

    Future conversation logic can add entries such as:
      contracts.C01.premium_won
      contracts.C01.product_name

    Coverage analysis/proposal state is intentionally not addressable here.
    """
    approved = session_state.get("approved_insurance_fields") or []
    if not isinstance(approved, list):
        return

    contracts = _contract_map(insurance_state)
    for raw_path in approved:
        path = str(raw_path or "").strip()
        parts = path.split(".")
        if len(parts) != 3 or parts[0] != "contracts":
            continue
        _, contract_id, field = parts
        if field not in _ALLOWED_CONTRACT_FIELDS:
            continue
        contract = contracts.get(contract_id)
        if not contract or field not in contract:
            continue
        _set_nested(memory, ["contracts", contract_id, field], contract[field])


def build_customer_insurance_memory(
    case: dict[str, Any],
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return insurance facts the fictional customer can reasonably know."""
    customer = case.get("customer_state") or {}
    beliefs = customer.get("customer_beliefs") or {}
    insurance = case.get("insurance_state") or {}
    state = session_state or {}

    memory: dict[str, Any] = {}

    known_premium = beliefs.get("known_monthly_premium_won")
    if known_premium is not None:
        memory["monthly_premium_won"] = deepcopy(known_premium)

    known_count = beliefs.get("known_contract_count")
    if known_count is not None:
        memory["contract_count"] = deepcopy(known_count)

    knowledge = int(beliefs.get("insurance_knowledge_level") or 0)
    if knowledge >= 3:
        contracts: dict[str, Any] = {}
        for cid, contract in _contract_map(insurance).items():
            contracts[cid] = {
                key: deepcopy(contract.get(key))
                for key in _ALLOWED_CONTRACT_FIELDS
                if contract.get(key) is not None
            }
        if contracts:
            memory["contracts"] = contracts

    _apply_explicit_insurance_fields(memory, insurance, state)
    return memory


def build_customer_disclosure_source(
    case: dict[str, Any],
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fact namespace accepted by Python disclosure validation.

    `insurance_state`, `coverage_analysis`, and `proposal_state` are never exposed
    directly. Insurance facts must enter through the bounded `insurance_memory`
    namespace above.
    """
    customer = case.get("customer_state") or {}
    return {
        "ground_truth": deepcopy(customer.get("ground_truth") or {}),
        "customer_beliefs": deepcopy(customer.get("customer_beliefs") or {}),
        "insurance_memory": build_customer_insurance_memory(case, session_state),
    }


def build_customer_model_context(
    case: dict[str, Any],
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sanitized context for the Customer role only."""
    customer = case.get("customer_state") or {}
    journey = case.get("journey_state") or {}

    return {
        "seed": case.get("seed"),
        "stage": case.get("stage"),
        "training_mode": case.get("training_mode"),
        "training_focus": case.get("training_focus"),
        "consultation_difficulty": case.get("consultation_difficulty"),
        "persona": {
            "alias": customer.get("alias"),
            "age": customer.get("age"),
            "gender": customer.get("gender"),
            "life_stage": customer.get("life_stage"),
            "personality": deepcopy(customer.get("personality") or {}),
            "motivations": deepcopy(customer.get("motivations") or {}),
            "relationship": deepcopy(customer.get("relationship") or {}),
            "voice_profile": deepcopy(customer.get("voice_profile") or {}),
        },
        "public_state": deepcopy(case.get("public_state") or {}),
        "journey_memory": {
            "current_stage": journey.get("current_stage"),
            "known_information": deepcopy(journey.get("known_information") or {}),
            "agreements": deepcopy(journey.get("agreements") or {}),
            "next_action": deepcopy(journey.get("next_action")),
        },
        "disclosure_source": build_customer_disclosure_source(case, session_state),
    }
