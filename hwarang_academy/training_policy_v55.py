"""Training-depth, turn-ownership and loop-detection policy for C07 V5.5.

This module keeps the *mission* separate from the *training path*.
- A skilled learner may reach the final goal early.
- GUIDE recommendations intentionally cover enough meaningful consultation steps
  to produce a useful STANDARD/DEEP session instead of rushing to scheduling.
- Customer information is progressively disclosed; the customer should not do
  the advisor's job by volunteering a full plan or exact appointment too early.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
import re

TRAINING_BUDGET = {
    "QUICK": {
        "target_minutes": "3~5분",
        "min_meaningful_steps": 3,
        "recommended_steps": 4,
        "max_recommended_turns": 10,
    },
    "STANDARD": {
        "target_minutes": "8~12분",
        "min_meaningful_steps": 7,
        "recommended_steps": 9,
        "max_recommended_turns": 22,
    },
    "DEEP": {
        "target_minutes": "12~20분",
        "min_meaningful_steps": 9,
        "recommended_steps": 12,
        "max_recommended_turns": 30,
    },
}

# Same final goal, different validated learning routes.  These are GUIDE
# recommendation orders, never hard gates for free conversation.
TRAINING_ROUTES = {
    "premium_first": [
        "premium", "contract", "trigger", "preference", "reduction_preference",
        "material_route", "analysis_handoff", "followup_planning",
    ],
    "reason_first": [
        "trigger", "premium", "contract", "preference", "reduction_preference",
        "material_route", "analysis_handoff", "followup_planning",
    ],
    "document_aware": [
        "premium", "contract", "material_route", "trigger", "preference",
        "reduction_preference", "analysis_handoff", "followup_planning",
    ],
}

ROUTE_NAMES = {
    "premium_first": "보험료 구조부터 확인",
    "reason_first": "부담 원인부터 탐색",
    "document_aware": "자료 가능 범위를 함께 확인",
}


def _pick(seed: int, key: str, n: int) -> int:
    if n <= 1:
        return 0
    raw = int(sha256(f"{seed}:v55:{key}".encode()).hexdigest()[:8], 16)
    return raw % n


def training_route_id(session: Any) -> str:
    ids = list(TRAINING_ROUTES)
    return ids[_pick(int(getattr(session, "seed", 1)), "guide-route", len(ids))]


def training_route(session: Any) -> list[str]:
    route = list(TRAINING_ROUTES[training_route_id(session)])
    length = getattr(session, "session_length", "STANDARD")
    if length == "QUICK":
        # Quick still ends in a follow-up but does not force every discovery step.
        keep = {"premium", "trigger", "material_route", "analysis_handoff", "followup_planning"}
        route = [x for x in route if x in keep]
    elif length == "STANDARD":
        # Standard keeps the complete core arc.
        pass
    elif length == "DEEP":
        # Deep uses the same core arc; events/portfolio exploration create depth.
        pass
    return route


def material_route_done(session: Any) -> bool:
    flags = set(getattr(session, "flags", {}))
    d = getattr(session, "world", {}).get("document", {})
    return bool(
        {"material_consent", "document_opened", "document_transfer_agreed", "document_delivery_planned"} & flags
        or d.get("opened") or d.get("shared") or d.get("delivery_planned")
    )


def milestone_done(session: Any, key: str) -> bool:
    flags = set(getattr(session, "flags", {}))
    state = getattr(session, "v5_state", None)
    if key == "material_route":
        return material_route_done(session)
    if key == "followup_planning":
        if not state:
            return False
        return bool(
            state.agreements.get("followup_permission")
            or state.agreements.get("followup_day")
            or state.agreements.get("followup_schedule")
            or "followup_pending" in flags
        )
    return key in flags


def meaningful_step_count(session: Any) -> int:
    keys = [
        "premium", "contract", "trigger", "preference", "reduction_preference",
        "material_route", "analysis_handoff", "followup_planning",
    ]
    return sum(1 for k in keys if milestone_done(session, k))


def guide_training_ready(session: Any) -> bool:
    """Whether GUIDE has delivered enough useful learning before suggesting close.

    This never blocks a learner who independently reaches the final goal.  It only
    controls *recommendations* so GUIDE does not complete a STANDARD session in
    two or three minutes.
    """
    budget = TRAINING_BUDGET.get(getattr(session, "session_length", "STANDARD"), TRAINING_BUDGET["STANDARD"])
    return meaningful_step_count(session) >= int(budget["min_meaningful_steps"])


def open_loops(session: Any) -> list[dict]:
    """Return public-safe unresolved consultation loops in priority order."""
    flags = set(getattr(session, "flags", {}))
    state = getattr(session, "v5_state", None)
    loops: list[dict] = []
    if "analysis_handoff" in flags and not material_route_done(session):
        loops.append({"id": "material", "label": "분석에 필요한 자료 확보 방법 미확정", "priority": 2})
    if state:
        if state.agreements.get("document_delivery_later") and not (
            state.agreements.get("document_transfer_method") or getattr(session, "world", {}).get("document", {}).get("shared")
        ):
            loops.append({"id": "delivery", "label": "증권 전달 방법 또는 시점 미확정", "priority": 2})
        if state.agreements.get("analysis_followup") and not state.agreements.get("followup_schedule"):
            loops.append({"id": "followup", "label": "분석 결과를 설명할 후속 일정 미확정", "priority": 1})
        pending = state.top_pending() if hasattr(state, "top_pending") else None
        if pending:
            loops.append({"id": "pending", "label": f"고객의 마지막 확인 요청({pending.kind}) 미해결", "priority": 0})
    return sorted(loops, key=lambda x: (x["priority"], x["id"]))


def pacing(session: Any) -> dict:
    length = getattr(session, "session_length", "STANDARD")
    budget = TRAINING_BUDGET.get(length, TRAINING_BUDGET["STANDARD"])
    turns = len(getattr(session, "turns", []))
    steps = meaningful_step_count(session)
    final = "followup_confirmed" in set(getattr(session, "flags", {}))
    if final and steps < budget["min_meaningful_steps"]:
        status = "too_fast"
        note = "최종 목표는 달성했지만 분석 방향을 잡기 위한 핵심 확인이 충분하지 않았습니다."
    elif turns > budget["max_recommended_turns"]:
        status = "long"
        note = "필요한 정보가 확보된 뒤에도 대화가 길어졌는지 복기해 보세요."
    else:
        status = "balanced"
        note = "훈련 길이와 의미 있는 상담 단계가 설정 범위 안에서 진행되었습니다."
    return {
        "status": status,
        "turns": turns,
        "meaningful_steps": steps,
        "target_minutes": budget["target_minutes"],
        "recommended_steps": budget["recommended_steps"],
        "note": note,
    }


def _same_customer_reply_count(session: Any) -> int:
    turns = list(getattr(session, "turns", []))[-4:]
    texts = [re.sub(r"\s+", " ", str(getattr(t, "response_text", "") or "").strip()) for t in turns]
    texts = [x for x in texts if x]
    if len(texts) < 3:
        return 0
    last = texts[-1]
    return sum(1 for x in texts[-3:] if x == last)


def _stagnant_context_count(session: Any) -> int:
    turns = list(getattr(session, "turns", []))[-5:]
    if len(turns) < 4:
        return 0
    sigs = []
    for t in turns:
        c = getattr(t, "v5_context_after", {}) or {}
        sigs.append((c.get("stage"), c.get("active_topic"), c.get("active_policy_id"), c.get("active_section")))
    if len(set(sigs)) == 1:
        return len(sigs)
    return 0


def loop_diagnostics(session: Any) -> dict:
    repeated = _same_customer_reply_count(session)
    stagnant = _stagnant_context_count(session)
    loops = open_loops(session)
    dead_end = False
    reasons = []
    if repeated >= 3:
        reasons.append("동일한 고객 답변이 연속 반복되었습니다.")
    if stagnant >= 4 and len(getattr(session, "turns", [])) >= 4:
        reasons.append("상담 상태가 여러 턴 동안 변하지 않았습니다.")
    # A route is considered recoverable as long as the mission is unfinished and
    # at least one open loop/action remains.  The mission graph performs static
    # reachability; this catches runtime stagnation.
    if reasons and not loops and "followup_confirmed" not in set(getattr(session, "flags", {})):
        dead_end = True
        reasons.append("현재 상태에서 명시적인 미해결 과제가 없어 복구 경로 계산이 필요합니다.")
    return {
        "repeated_customer_reply": repeated,
        "stagnant_context_turns": stagnant,
        "open_loops": loops,
        "dead_end": dead_end,
        "reasons": reasons,
    }


def customer_disclosure_mode(session: Any) -> str:
    """How proactive the customer may be in this training mode."""
    mode = getattr(session, "mode", "GUIDE")
    if mode == "GUIDE":
        return "REACTIVE"
    if mode == "COACH":
        return "REACTIVE_NORMAL"
    return "NORMAL"
