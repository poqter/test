"""Versioned evidence-log helpers for future AI/customer/evaluator integration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .constants import EVIDENCE_LOG_VERSION


def make_turn_evidence(
    *,
    turn_no: int,
    advisor_text: str,
    customer_text: str,
    disclosed_information: list[dict[str, Any]] | None = None,
    state_delta: dict[str, Any] | None = None,
    goal_delta: dict[str, Any] | None = None,
    training_focus: str = "comprehensive",
    assist_used: bool = False,
    scenario_version: str | None = None,
    prompt_version: str | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_LOG_VERSION,
        "turn_no": int(turn_no),
        "advisor_text": str(advisor_text),
        "customer_text": str(customer_text),
        "disclosed_information": list(disclosed_information or []),
        "state_delta": dict(state_delta or {}),
        "goal_delta": dict(goal_delta or {}),
        "training_focus": str(training_focus),
        "assist_used": bool(assist_used),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "scenario_version": scenario_version,
        "prompt_version": prompt_version,
        "model_version": model_version,
    }
