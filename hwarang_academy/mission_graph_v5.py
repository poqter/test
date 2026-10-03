"""Goal graph + GUIDE route planner for the C07 Golden Scenario (V5.5).

Mission completion and training quality are intentionally separate:
- Any valid free-conversation route may reach the final goal early.
- GUIDE recommendations use a *training route* so STANDARD/DEEP sessions do
  enough meaningful work before scheduling.
- The customer never needs to volunteer the advisor's next move; follow-up
  scheduling is progressively negotiated by the advisor.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import re

from .training_policy_v55 import (
    training_route_id, training_route, ROUTE_NAMES, milestone_done,
    material_route_done, meaningful_step_count, guide_training_ready,
    open_loops, loop_diagnostics, TRAINING_BUDGET,
)

FINAL_GOAL_FLAG = "followup_confirmed"
FINAL_GOAL_TEXT = "분석 결과를 설명할 다음 상담 일정 또는 구체적인 후속 연락 시점을 확정한다."

INTERMEDIATE = [
    ("premium", "현재 월 보험료 확인"),
    ("contract", "주요·부담 계약 확인"),
    ("trigger", "보험료 부담이 커진 이유 확인"),
    ("preference", "유지하고 싶은 보장·조건 확인"),
    ("reduction_preference", "원하는 보험료 절감 기준 확인"),
    ("material_route", "증권 확인 또는 추후 자료 확보 경로 합의"),
    ("analysis_handoff", "사무실 상세 분석 및 재설명 합의"),
]

GOAL_GRAPH = {
    "START": {"DISCOVER_PREMIUM", "DISCOVER_REASON", "MATERIAL_ROUTE", "FOLLOWUP_PLAN"},
    "DISCOVER_PREMIUM": {"DISCOVER_CONTRACT", "DISCOVER_REASON", "ALIGN", "MATERIAL_ROUTE", "FOLLOWUP_PLAN"},
    "DISCOVER_CONTRACT": {"DISCOVER_REASON", "ALIGN", "MATERIAL_ROUTE", "FOLLOWUP_PLAN"},
    "DISCOVER_REASON": {"ALIGN", "MATERIAL_ROUTE", "ANALYSIS_HANDOFF", "FOLLOWUP_PLAN"},
    "ALIGN": {"MATERIAL_ROUTE", "ANALYSIS_HANDOFF", "FOLLOWUP_PLAN"},
    "MATERIAL_ROUTE": {"DOCUMENT_NOW", "DOCUMENT_LATER", "ANALYSIS_HANDOFF", "FOLLOWUP_PLAN"},
    "DOCUMENT_NOW": {"ANALYSIS_HANDOFF", "FOLLOWUP_PLAN"},
    "DOCUMENT_LATER": {"ANALYSIS_HANDOFF", "FOLLOWUP_PLAN"},
    "ANALYSIS_HANDOFF": {"FOLLOWUP_PLAN", "FINAL"},
    "FOLLOWUP_PLAN": {"FINAL"},
    "FINAL": set(),
}


@dataclass(frozen=True)
class GuideAction:
    action_id: str
    hint: str
    recommended: str
    adequate: str
    purpose: str
    expected_flags: tuple[str, ...] = ()
    alternatives: tuple[tuple[str, str], ...] = ()
    rescue: bool = False
    expected_next_state: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["alternatives"] = [{"label": label, "text": text} for label, text in self.alternatives]
        # compatibility with the previous UI / engine field name
        d["reason"] = self.purpose
        return d


def validate_goal_graph() -> None:
    if "FINAL" not in GOAL_GRAPH:
        raise RuntimeError("C07 goal graph requires FINAL node")
    for start in GOAL_GRAPH:
        seen = set(); stack = [start]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(GOAL_GRAPH.get(node, set()) - seen)
        if "FINAL" not in seen:
            raise RuntimeError(f"Dead-end mission node: {start}")


def _document(session: Any) -> dict:
    return getattr(session, "world", {}).get("document", {})


def _availability(session: Any) -> list[str]:
    return list(getattr(session, "world", {}).get("availability", {}).get("followup_options") or [])


def _weekday_options(session: Any) -> list[str]:
    days = []
    for opt in _availability(session):
        m = re.search(r"(월요일|화요일|수요일|목요일|금요일|토요일|일요일|주말)", opt)
        if m and m.group(1) not in days:
            days.append(m.group(1))
    return days


def _time_for_day(session: Any, day: str | None) -> str | None:
    if not day:
        return None
    for opt in _availability(session):
        if day in opt:
            tail = opt.split(day, 1)[1].strip()
            return tail or None
    return None


def _exact_schedule_for_day(session: Any, day: str | None) -> str | None:
    if not day:
        return None
    for opt in _availability(session):
        if day in opt:
            # "이후" is an availability boundary.  Propose the boundary time
            # itself as a concrete candidate instead of making the customer do it.
            return re.sub(r"\s*이후\s*$", "", opt).strip()
    return None


def goal_status(session: Any) -> dict:
    flags = set(getattr(session, "flags", {}))
    state = getattr(session, "v5_state", None)
    intermediate = []
    for key, label in INTERMEDIATE:
        intermediate.append({"id": key, "label": label, "done": milestone_done(session, key)})
    final = FINAL_GOAL_FLAG in flags
    agreement = state.agreements.get("followup_schedule") if state else None
    ending = state.agreements.get("completion_path") if state else None
    return {
        "final_complete": final,
        "final_goal": FINAL_GOAL_TEXT,
        "intermediate": intermediate,
        "followup_schedule": agreement,
        "completion_path": ending,
        "missing": [x["id"] for x in intermediate if not x["done"]],
        "open_loops": open_loops(session),
    }


def _future_document_text(session: Any) -> str:
    d = _document(session)
    if d.get("access") == "spouse_managed":
        return "지금 확인이 어렵다면 배우자분께 증권을 받으신 뒤 저에게 전달해주실 수 있을까요?"
    if d.get("access") == "partial_mobile":
        return "지금 없는 계약 자료는 나중에 준비해서 함께 전달해주실 수 있을까요?"
    return "지금 바로 확인하기 어렵다면 증권을 준비하신 뒤 저에게 전달해주실 수 있을까요?"


def _milestone_action(session: Any, key: str) -> GuideAction | None:
    d = _document(session)
    if key == "premium":
        return GuideAction(
            "ask_total_premium", "현재 부담의 크기를 구체화해 보세요.",
            "전체로 한 달에 내시는 보험료는 어느 정도 되실까요?",
            "현재 보험료는 어느 정도 내고 계세요?",
            "현재 보험료를 알아야 고객이 느끼는 부담의 규모를 다른 정보와 연결할 수 있습니다.",
            ("premium",), expected_next_state="DISCOVER_PREMIUM",
        )
    if key == "contract":
        return GuideAction(
            "ask_burdensome_policy", "전체 보험료 중 특히 부담되는 계약이 있는지 확인하세요.",
            "그중 어떤 계약이 가장 부담되세요?", "어떤 보험이 특히 신경 쓰이세요?",
            "총액만으로는 어떤 계약을 우선 분석해야 하는지 알기 어렵기 때문입니다.",
            ("contract",), expected_next_state="DISCOVER_CONTRACT",
        )
    if key == "trigger":
        return GuideAction(
            "ask_burden_reason", "보험료가 '지금' 더 부담스러운 배경을 확인하세요.",
            "잘 납입하시다가 최근 더 부담스럽게 느껴진 이유가 있을까요?",
            "최근 보험료 부담이 커진 계기가 있으실까요?",
            "같은 보험료라도 소득·지출 변화에 따라 고객이 원하는 해결 방향이 달라질 수 있습니다.",
            ("trigger",), expected_next_state="DISCOVER_REASON",
        )
    if key == "preference":
        return GuideAction(
            "ask_preference", "줄이는 것과 함께 반드시 지키고 싶은 기준을 확인하세요.",
            "보험료를 조정하더라도 꼭 유지하고 싶은 보장이나 조건이 있을까요?",
            "줄이고 싶지 않은 보장도 있으실까요?",
            "보험료 절감만 좇으면 고객이 중요하게 생각하는 보장을 훼손할 수 있습니다.",
            ("preference",), expected_next_state="ALIGN",
        )
    if key == "reduction_preference":
        return GuideAction(
            "ask_reduction_target", "고객이 기대하는 절감 수준이나 기준을 확인하세요.",
            "어느 정도 줄어들면 부담이 덜하실까요? 정확한 금액이 아니어도 괜찮습니다.",
            "보험료를 줄인다면 어느 정도를 기대하세요?",
            "목표 금액·감축 폭·우선기준 중 하나라도 알아야 분석안의 방향을 잡을 수 있습니다.",
            ("reduction_preference",), expected_next_state="ALIGN",
        )
    if key == "material_route":
        if d.get("can_open_now"):
            return GuideAction(
                "review_document_now", "지금 확인 가능한 자료 범위를 확인하세요.",
                "증권이나 계약 자료를 같이 확인해도 괜찮을까요?", "가능한 자료부터 같이 확인해보죠.",
                "기억과 실제 계약 정보를 구분해 이후 분석의 근거를 확보하기 위해서입니다.",
                ("material_consent",),
                (("자료를 가져가 분석", "오늘 바로 결론내리기보다 자료를 제가 자세히 분석한 뒤 다시 설명드려도 될까요?"),),
                expected_next_state="DOCUMENT_NOW",
            )
        if d.get("can_send_later") or d.get("access") in {"spouse_managed", "partial_mobile"}:
            return GuideAction(
                "plan_document_later", "지금 자료를 볼 수 없다면 추후 확보 방법을 합의하세요.",
                _future_document_text(session), "오늘은 기억나는 범위까지만 보고, 자료가 준비되면 보내주셔도 됩니다.",
                "자료가 지금 없다는 이유로 상담을 막지 않고, 분석 가능한 다음 경로를 만드는 단계입니다.",
                ("document_delivery_planned",),
                (("다음 상담을 먼저 준비", "그럼 오늘은 기억나는 내용까지만 정리하고, 증권이 준비되면 분석해서 다시 설명드려도 될까요?"),),
                True, "DOCUMENT_LATER",
            )
        return GuideAction(
            "bypass_document", "현재 자료 확보가 어렵습니다. 자료 없이도 후속 분석 경로를 만들 수 있습니다.",
            "그럼 오늘은 기억나는 내용까지만 정리하고, 증권이 준비되면 분석해서 다시 설명드려도 될까요?",
            "자료가 준비되는 시점에 다시 확인해도 괜찮을까요?",
            "현재 불가능한 자료 확인을 반복하지 않고, 분석·후속상담이라는 대체 경로로 전환합니다.",
            ("analysis_handoff",), rescue=True, expected_next_state="ANALYSIS_HANDOFF",
        )
    if key == "analysis_handoff":
        return GuideAction(
            "analysis_handoff", "현장에서 변경을 확정하지 말고 상세 분석 후 재설명에 동의를 구하세요.",
            "오늘 바로 결론내리기보다 제가 자료를 자세히 분석한 뒤 다시 설명드려도 될까요?",
            "자료를 정리해서 다음 상담에서 비교해드려도 될까요?",
            "C07의 목적은 즉석 계약이 아니라 고객 기준에 맞춘 분석안을 준비해 다시 설명하는 것입니다.",
            ("analysis_handoff",), expected_next_state="ANALYSIS_HANDOFF",
        )
    return None


def _scheduling_action(session: Any) -> GuideAction:
    state = getattr(session, "v5_state", None)
    agreements = state.agreements if state else {}
    # 1) Advisor first proposes *having* a follow-up; customer does not volunteer a date.
    if not agreements.get("followup_permission"):
        return GuideAction(
            "invite_followup", "분석 후 다시 설명하기로 했다면 이제 후속 상담 자체에 동의를 구하세요.",
            "그럼 분석 결과를 설명드릴 다음 상담 일정도 같이 정해볼까요?",
            "다음에 다시 설명드릴 일정도 잡아둘까요?",
            "고객이 먼저 날짜를 제안하게 하지 않고, 상담사가 후속상담을 제안하는 훈련 단계입니다.",
            ("followup_planning_started",), expected_next_state="FOLLOWUP_PERMISSION",
        )
    # 2) Ask day only.  Customer will reveal only day candidates.
    if not agreements.get("followup_day_options") and not agreements.get("followup_day"):
        return GuideAction(
            "ask_followup_day", "후속 상담에 동의했습니다. 이번에는 가능한 날짜·요일 범위만 확인하세요.",
            "다음 주 중에는 어느 요일이 편하실까요?", "어느 날이 가장 편하세요?",
            "일정을 한 번에 고객이 정하게 하지 않고 날짜 → 시간 순서로 협의하는 연습입니다.",
            expected_next_state="FOLLOWUP_DAY_OPTIONS",
        )
    # 3) Advisor selects/proposes one of the offered days.
    if not agreements.get("followup_day"):
        days = list(agreements.get("followup_day_options") or _weekday_options(session))
        day = days[0] if days else "다음 주 중 편한 날"
        return GuideAction(
            "select_followup_day", "고객이 말한 가능한 요일 중 하나를 상담사가 구체적으로 제안하세요.",
            f"그럼 {day}은 괜찮으실까요?", f"{day}으로 잡아볼까요?",
            "고객이 먼저 전체 일정을 완성하는 대신 상담사가 한 단계씩 조율하는 훈련입니다.",
            expected_next_state="FOLLOWUP_DAY_SELECTED",
        )
    # 4) Ask time within selected day.
    if not agreements.get("followup_time_window"):
        day = agreements.get("followup_day")
        return GuideAction(
            "ask_followup_time", f"{day} 일정은 가능하다고 확인했습니다. 이제 시간 범위를 물어보세요.",
            f"{day}은 몇 시쯤 괜찮으실까요?", "그날은 어느 시간대가 편하세요?",
            "날짜와 시간을 분리해 협의하면 상담사가 일정 조율 과정을 직접 수행하게 됩니다.",
            expected_next_state="FOLLOWUP_TIME_WINDOW",
        )
    # 5) Advisor proposes exact schedule. Final goal completes only now.
    day = agreements.get("followup_day")
    exact = _exact_schedule_for_day(session, day)
    if not exact:
        tw = agreements.get("followup_time_window") or "말씀하신 시간대"
        exact = f"{day} {str(tw).replace('이후','').strip()}".strip()
    return GuideAction(
        "confirm_followup", "날짜와 시간 범위를 확인했습니다. 상담사가 구체적인 시간을 제안해 확정하세요.",
        f"그럼 {exact}에 다시 상담할까요?", f"{exact}로 정해도 괜찮으실까요?",
        "구체적인 후속 일정이 확정되는 순간 C07의 Final Goal이 완료됩니다.",
        (FINAL_GOAL_FLAG,), expected_next_state="FINAL",
    )


def next_best_actions(session: Any) -> list[GuideAction]:
    if getattr(session, "ended", False) or FINAL_GOAL_FLAG in getattr(session, "flags", {}):
        return [GuideAction(
            "complete", "최종 목표를 달성했습니다.", "다음 상담 일정이 확정되었습니다.",
            "상담을 종료하고 복기합니다.", "빠진 중간 목표는 결과에서 상담 완성도로 따로 평가합니다.",
            expected_next_state="FINAL",
        )]

    diagnostics = loop_diagnostics(session)
    flags = set(getattr(session, "flags", {}))

    # Runtime rescue: repeated customer replies/stagnation should never keep GUIDE
    # serving the same recommendation indefinitely.
    if diagnostics["repeated_customer_reply"] >= 3 or diagnostics["stagnant_context_turns"] >= 4:
        if "analysis_handoff" in flags:
            a = _scheduling_action(session)
            return [GuideAction(
                a.action_id, "같은 흐름이 반복되고 있습니다. 이전 질문을 반복하지 말고 후속 상담 경로로 전환하세요.",
                a.recommended, a.adequate, a.purpose, a.expected_flags, a.alternatives, True, a.expected_next_state,
            )]
        a = _milestone_action(session, "analysis_handoff")
        if a:
            return [GuideAction(
                a.action_id, "같은 답변이 반복되어 복구 경로로 전환합니다. 현재 확보한 내용까지만 바탕으로 분석 후 재상담을 제안하세요.",
                a.recommended, a.adequate, a.purpose, a.expected_flags, a.alternatives, True, a.expected_next_state,
            )]

    # GUIDE training route: choose one of several validated orders.  Free input is
    # not restricted to this order; it exists only to prevent a 2~3 minute button-
    # clicking completion in STANDARD/DEEP.
    route = training_route(session)
    for key in route:
        if key == "followup_planning":
            continue
        if not milestone_done(session, key):
            action = _milestone_action(session, key)
            if action:
                return [action]

    # The advisor has accumulated the training-route evidence.  Follow-up is
    # progressively negotiated rather than volunteered by the customer.
    return [_scheduling_action(session)]


def guide_plan(session: Any) -> dict:
    actions = next_best_actions(session)
    primary = actions[0]
    d = primary.to_dict()
    d["remaining_goal"] = FINAL_GOAL_TEXT
    d["status"] = goal_status(session)
    d["training_route_id"] = training_route_id(session)
    d["training_route_name"] = ROUTE_NAMES[training_route_id(session)]
    d["meaningful_steps"] = meaningful_step_count(session)
    d["training_ready"] = guide_training_ready(session)
    d["target_minutes"] = TRAINING_BUDGET[getattr(session, "session_length", "STANDARD")]["target_minutes"]
    d["loop_diagnostics"] = loop_diagnostics(session)
    d["open_loops"] = open_loops(session)
    return d


def validate_session_route(session: Any) -> dict:
    actions = next_best_actions(session)
    diagnostics = loop_diagnostics(session)
    ok = bool(actions) and (
        getattr(session, "ended", False)
        or bool(actions[0].recommended)
    ) and not diagnostics.get("dead_end")
    return {
        "ok": ok,
        "next_action": actions[0].action_id if actions else None,
        "final_goal": FINAL_GOAL_TEXT,
        "diagnostics": diagnostics,
    }


validate_goal_graph()
