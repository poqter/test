"""Python-side validator for AI-proposed customer state changes.

The AI may propose conversational state deltas, but it can never mutate
ground-truth customer/insurance facts directly.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .api_contracts import validate_contract


_ALLOWED_STATE_KEYS = {
    "trust_delta",
    "interest_delta",
    "decision_readiness_delta",
    "pressure_response",
    "objection_state",
    "should_end",
}


@dataclass(frozen=True)
class ValidatedCustomerTurn:
    customer_text: str
    state_delta: dict[str, Any]
    disclosures: list[dict[str, Any]]
    signals: list[str]
    objection: dict[str, Any] | None
    goal_evidence: list[dict[str, Any]]
    conversation_control: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_text": self.customer_text,
            "state_delta": deepcopy(self.state_delta),
            "disclosures": deepcopy(self.disclosures),
            "signals": list(self.signals),
            "objection": deepcopy(self.objection),
            "goal_evidence": deepcopy(self.goal_evidence),
            "conversation_control": deepcopy(self.conversation_control),
        }


def _resolve_path(customer_state: dict[str, Any], path: str) -> Any:
    root_name, _, tail = path.partition(".")
    if root_name not in {"ground_truth", "customer_beliefs"} or not tail:
        raise ValueError(f"unsupported disclosure path: {path}")

    value: Any = customer_state.get(root_name)
    for part in tail.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"unknown disclosure path: {path}")
        value = value[part]
    return value


def _numeric_close(actual: float, proposed: float) -> bool:
    tolerance = max(abs(float(actual)) * 0.15, 10_000.0)
    return abs(float(actual) - float(proposed)) <= tolerance


def _validate_disclosure(
    customer_state: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    source_value = _resolve_path(customer_state, str(row["path"]))
    precision = str(row["precision"])
    proposed = row.get("value")

    if precision == "uncertain":
        # Uncertain speech is allowed, but Python never replaces the source fact.
        return {
            "path": str(row["path"]),
            "value": proposed,
            "precision": precision,
            "source_value": source_value,
            "validated": True,
        }

    if precision == "exact":
        if proposed != source_value:
            raise ValueError(f"exact disclosure conflicts with source: {row['path']}")
    elif precision == "approximate":
        if isinstance(source_value, (int, float)) and isinstance(proposed, (int, float)):
            if not _numeric_close(float(source_value), float(proposed)):
                raise ValueError(f"approximate disclosure outside tolerance: {row['path']}")
        elif proposed != source_value:
            raise ValueError(f"non-numeric approximate disclosure conflicts with source: {row['path']}")

    return {
        "path": str(row["path"]),
        "value": proposed,
        "precision": precision,
        "source_value": source_value,
        "validated": True,
    }


def validate_customer_turn(
    *,
    customer_state: dict[str, Any],
    payload: dict[str, Any],
    allowed_goal_codes: set[str] | None = None,
) -> ValidatedCustomerTurn:
    validate_contract("CUSTOMER", payload)

    state_delta = {
        k: deepcopy(v)
        for k, v in payload["state_proposals"].items()
        if k in _ALLOWED_STATE_KEYS
    }

    disclosures = [
        _validate_disclosure(customer_state, row)
        for row in payload["disclosures"]
    ]

    allowed = set(allowed_goal_codes or ())
    goal_evidence: list[dict[str, Any]] = []
    for row in payload["goal_evidence"]:
        code = str(row["goal_code"])
        if allowed and code not in allowed:
            # Unknown goal evidence is ignored rather than allowed to mutate the Goal Graph.
            continue
        goal_evidence.append(deepcopy(row))

    return ValidatedCustomerTurn(
        customer_text=str(payload["customer_text"]),
        state_delta=state_delta,
        disclosures=disclosures,
        signals=[str(x) for x in payload["signals"]],
        objection=deepcopy(payload["objection"]),
        goal_evidence=goal_evidence,
        conversation_control=deepcopy(payload["conversation_control"]),
    )


def apply_conversation_state(
    session_state: dict[str, Any],
    turn: ValidatedCustomerTurn,
) -> dict[str, Any]:
    """Apply only bounded conversational state; never mutate Case ground truth."""
    result = deepcopy(session_state or {})
    state = dict(result.get("customer_runtime") or {})

    for key in ("trust", "interest", "decision_readiness"):
        state.setdefault(key, 0)

    state["trust"] = max(-10, min(10, int(state["trust"]) + int(turn.state_delta["trust_delta"])))
    state["interest"] = max(-10, min(10, int(state["interest"]) + int(turn.state_delta["interest_delta"])))
    state["decision_readiness"] = max(
        -10,
        min(
            10,
            int(state["decision_readiness"])
            + int(turn.state_delta["decision_readiness_delta"]),
        ),
    )
    state["pressure_response"] = turn.state_delta["pressure_response"]
    state["objection_state"] = turn.state_delta["objection_state"]
    state["should_end"] = bool(turn.state_delta["should_end"])

    result["customer_runtime"] = state
    result["last_signals"] = list(turn.signals)
    result["last_objection"] = deepcopy(turn.objection)
    return result
