"""Goal-directed mission graph for the C07 Golden Scenario.

The graph separates *mission completion* from *consultation quality*.
C07 ends when a concrete follow-up consultation or contact time is agreed.
Intermediate goals improve the debrief score but never trap the learner in a
single scripted route.

GUIDE uses this module as a route planner: every recommended answer must map to
an executable next action and all validated customer worlds must retain at least
one path to FINAL_GOAL.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

FINAL_GOAL_FLAG = "followup_confirmed"
FINAL_GOAL_TEXT = "분석 결과를 설명할 다음 상담 일정 또는 후속 연락 시점을 확정한다."

INTERMEDIATE = [
    ("premium", "현재 월 보험료 확인"),
    ("contract", "주요·부담 계약 확인"),
    ("trigger", "보험료 부담이 커진 이유 확인"),
    ("preference", "유지하고 싶은 보장·조건 확인"),
    ("reduction_preference", "원하는 보험료 절감 기준 확인"),
    ("material_route", "증권 확인 또는 추후 자료 확보 경로 합의"),
    ("analysis_handoff", "사무실 상세 분석 및 재설명 합의"),
]

# The static graph is intentionally broader than one "correct" sequence.
# Edges represent valid progress, not a scoring rubric.
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
    reason: str
    expected_flags: tuple[str, ...] = ()
    alternatives: tuple[tuple[str, str], ...] = ()
    rescue: bool = False

    def to_dict(self) -> dict:
        d=asdict(self)
        d["alternatives"]=[{"label":label,"text":text} for label,text in self.alternatives]
        return d


def validate_goal_graph() -> None:
    """Fail fast if any declared graph node cannot reach FINAL."""
    if "FINAL" not in GOAL_GRAPH:
        raise RuntimeError("C07 goal graph requires FINAL node")
    for start in GOAL_GRAPH:
        seen=set();stack=[start]
        while stack:
            node=stack.pop()
            if node in seen:continue
            seen.add(node)
            stack.extend(GOAL_GRAPH.get(node,set())-seen)
        if "FINAL" not in seen:
            raise RuntimeError(f"Dead-end mission node: {start}")


def _pending_kind(session: Any) -> str|None:
    state=getattr(session,"v5_state",None)
    p=state.top_pending() if state else None
    return p.kind if p else None


def _availability(session: Any) -> list[str]:
    return list(getattr(session,"world",{}).get("availability",{}).get("followup_options") or [])


def _document(session: Any) -> dict:
    return getattr(session,"world",{}).get("document",{})


def material_route_done(session: Any) -> bool:
    flags=set(getattr(session,"flags",{}))
    d=_document(session)
    return bool(
        {"material_consent","document_opened","document_transfer_agreed","document_delivery_planned"} & flags
        or d.get("opened") or d.get("shared") or d.get("delivery_planned")
    )


def goal_status(session: Any) -> dict:
    flags=set(getattr(session,"flags",{}))
    state=getattr(session,"v5_state",None)
    intermediate=[]
    for key,label in INTERMEDIATE:
        done=material_route_done(session) if key=="material_route" else key in flags
        intermediate.append({"id":key,"label":label,"done":done})
    final=FINAL_GOAL_FLAG in flags
    agreement=(state.agreements.get("followup_schedule") if state else None)
    ending=(state.agreements.get("completion_path") if state else None)
    return {
        "final_complete":final,
        "final_goal":FINAL_GOAL_TEXT,
        "intermediate":intermediate,
        "followup_schedule":agreement,
        "completion_path":ending,
        "missing":[x["id"] for x in intermediate if not x["done"]],
    }


def _schedule_choice(session: Any) -> str:
    opts=_availability(session)
    if opts:
        # Use an offered time verbatim so the parser and availability checker agree.
        return f"그럼 {opts[0]}에 다시 상담할까요?"
    fallback=getattr(session,"world",{}).get("availability",{}).get("contact_fallback")
    if fallback:
        return f"그럼 {fallback}에 다시 연락드려도 될까요?"
    return "그럼 다음 상담 날짜와 시간을 정해볼까요?"


def _future_document_text(session: Any) -> str:
    d=_document(session)
    if d.get("access")=="spouse_managed":
        return "지금 확인이 어렵다면 배우자분께 증권을 받으신 뒤 저에게 전달해주실 수 있을까요?"
    if d.get("access")=="partial_mobile":
        return "지금 없는 계약 자료는 나중에 준비해서 함께 전달해주실 수 있을까요?"
    return "지금 바로 확인하기 어렵다면 증권을 준비하신 뒤 저에게 전달해주실 수 있을까요?"


def next_best_actions(session: Any) -> list[GuideAction]:
    """Return currently executable GUIDE actions ordered toward the Final Goal.

    The planner deliberately offers alternatives. It does not require all
    intermediate goals before the final schedule can be agreed.
    """
    if getattr(session,"ended",False) or FINAL_GOAL_FLAG in getattr(session,"flags",{}):
        return [GuideAction("complete","최종 목표를 달성했습니다.","다음 상담 일정이 확정되었습니다.","상담을 종료하고 복기합니다.","빠진 중간 목표는 결과에서 평가합니다.")]

    flags=set(getattr(session,"flags",{}));pending=_pending_kind(session);d=_document(session)

    # A customer question creates a conversational obligation. Resolve the ones
    # that are necessary for the current route before offering a new topic.
    if pending=="followup_schedule":
        text=_schedule_choice(session)
        return [GuideAction("confirm_followup","고객이 가능한 시간을 제시했습니다. 구체적인 하나를 선택해 확정하세요.",text,"제시된 시간 중 가능한 하나를 선택해도 됩니다.","일정이 확정되는 순간 C07의 Final Goal이 완료됩니다.",(FINAL_GOAL_FLAG,))]
    if pending=="transfer_method":
        return [GuideAction("confirm_transfer_channel","자료 전달 방법을 정해 분석 단계로 넘기세요.","카카오톡으로 보내주세요.","편한 방법으로 전달해주시면 됩니다.","전달 방법이 합의되면 자료 확보 경로가 명확해집니다.",("document_transfer_agreed",))]

    # Golden recommended route: useful evidence first, but never make it a hard
    # gate. The learner may reach the final goal earlier and the debrief scores
    # omitted evidence separately.
    if "premium" not in flags:
        return [GuideAction("ask_total_premium","현재 부담의 규모를 먼저 확인해 보세요.","전체로 한 달에 내시는 보험료는 어느 정도 되실까요?","보험료가 많이 부담되시는군요. 현재 어느 정도 내고 계세요?","현재 보험료를 확인하면 부담의 크기를 구체화할 수 있습니다.",("premium",),(("다른 시작","최근 보험료가 더 부담스럽게 느껴진 이유가 있을까요?"),))]
    if "contract" not in flags:
        return [GuideAction("ask_burdensome_policy","가장 부담되는 계약을 특정해 보세요.","그중 어떤 계약이 가장 부담되세요?","어떤 보험이 특히 신경 쓰이세요?","전체 금액과 특정 계약의 부담을 구분합니다.",("contract",))]
    if "trigger" not in flags:
        return [GuideAction("ask_burden_reason","보험료가 지금 더 부담스러워진 배경을 확인하세요.","잘 납입하시다가 최근 더 부담스럽게 느껴진 이유가 있을까요?","최근에 보험료 부담이 커진 계기가 있으실까요?","숫자 자체와 고객의 생활·현금흐름 변화를 구분합니다.",("trigger",))]
    if "preference" not in flags:
        return [GuideAction("ask_preference","줄이는 것만 보지 말고 고객이 지키고 싶은 기준을 확인하세요.","보험료를 조정하더라도 꼭 유지하고 싶은 보장이나 조건이 있을까요?","줄이고 싶지 않은 보장도 있으실까요?","고객의 유지 기준은 이후 분석 방향을 결정합니다.",("preference",))]
    if "reduction_preference" not in flags:
        return [GuideAction("ask_reduction_target","고객이 기대하는 절감 기준을 확인하세요.","어느 정도 줄어들면 부담이 덜하실까요? 정확한 금액이 아니어도 괜찮습니다.","보험료를 줄인다면 어느 정도를 기대하세요?","숫자를 강요하지 않고 목표 범위·감축액·우선기준 중 하나를 확인합니다.",("reduction_preference",))]

    if not material_route_done(session):
        if d.get("can_open_now"):
            return [GuideAction("review_document_now","현재 확인 가능한 증권을 활용해 분석 자료를 확보하세요.","증권이나 계약 자료를 같이 확인해도 괜찮을까요?","가능한 자료부터 같이 확인해보죠.","지금 자료를 열 수 있는 고객이므로 즉시 확인 경로가 가장 자연스럽습니다.",("material_consent",),(("바로 세부 분석으로 넘기기","오늘 바로 결론내리기보다 제가 자료를 자세히 분석한 뒤 다시 설명드려도 될까요?"),))]
        if d.get("can_send_later") or d.get("access") in {"spouse_managed","partial_mobile"}:
            return [GuideAction("plan_document_later","현재 증권을 바로 볼 수 없습니다. 지금 확인을 강요하지 말고 추후 확보 경로를 합의하세요.",_future_document_text(session),"오늘은 기억나는 범위까지만 보고, 자료가 준비되면 보내주셔도 됩니다.","증권 즉시 확인은 필수조건이 아닙니다. 추후 전달 경로가 합의되면 분석과 재상담으로 진행할 수 있습니다.",("document_delivery_planned",),(("일정부터 정하기","그럼 자료는 준비되시는 대로 받고, 분석 결과를 설명드릴 다음 상담 일정부터 정해볼까요?"),),True)]
        return [GuideAction("bypass_document","현재 자료 확보가 어렵습니다. 자료가 없어도 후속 분석 경로를 먼저 합의할 수 있습니다.","그럼 오늘은 기억나는 내용까지만 정리하고, 증권이 준비되면 분석해서 다시 설명드려도 될까요?","자료가 준비되는 시점에 다시 확인해도 괜찮을까요?","자료가 없는 상태를 Dead End로 만들지 않고 재상담 경로로 전환합니다.",("analysis_handoff",),rescue=True)]

    if "analysis_handoff" not in flags:
        return [GuideAction("analysis_handoff","현장에서 성급하게 변경을 확정하지 말고 상세 분석 후 재설명에 동의를 구하세요.","오늘 바로 결론내리기보다 제가 증권을 자세히 분석한 뒤 다시 설명드려도 될까요?","자료를 정리해서 다음 상담에서 비교해드려도 될까요?","C07의 정상적인 후속 분석 경로입니다.",("analysis_handoff",),(("빠르게 일정으로 전환","그럼 분석해서 다시 설명드릴 수 있도록 다음 상담 일정부터 정해볼까요?"),))]

    # Final step. First ask for availability; after the customer replies, the
    # pending followup branch above chooses one concrete option.
    return [GuideAction("ask_followup","이제 C07의 Final Goal을 완료하세요.","그럼 분석 결과를 설명드릴 다음 상담 날짜나 연락 시점을 정해볼까요?","언제 다시 설명드리면 좋을까요?","구체적인 다음 상담 일정 또는 후속 연락 시점이 확정되면 상담이 종료됩니다.",(FINAL_GOAL_FLAG,),(("후속 연락 시점으로 마무리","정확한 미팅 날짜가 어렵다면 언제 다시 연락드리면 좋을지 정해볼까요?"),))]


def guide_plan(session: Any) -> dict:
    actions=next_best_actions(session)
    primary=actions[0]
    d=primary.to_dict()
    # Dead-end / rescue metadata is visible only to GUIDE through service.py.
    d["remaining_goal"]=FINAL_GOAL_TEXT
    d["status"]=goal_status(session)
    return d


def validate_session_route(session: Any) -> dict:
    """Runtime reachability guard used by tests and GUIDE diagnostics."""
    actions=next_best_actions(session)
    ok=bool(actions) and (getattr(session,"ended",False) or bool(actions[0].recommended))
    return {"ok":ok,"next_action":actions[0].action_id if actions else None,"final_goal":FINAL_GOAL_TEXT}

validate_goal_graph()
