"""Controlled variability and session-shape metadata for Academy simulator V2.

This module creates *fictional training variants*. It never alters the V1/V1.1
source JSON files. Core training goals remain stable while profile, expression,
minor circumstances, and eligible events can vary between sessions.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from typing import Iterable

SESSION_LENGTHS = {
    "QUICK": {
        "name": "QUICK · 핵심 훈련",
        "minutes": "약 3~5분",
        "description": "한 가지 핵심 행동과 짧은 마무리에 집중합니다.",
        "max_turns": 14,
        "event_budget": {"GUIDE": 1, "COACH": 1, "SOLO": 1, "ASSESSMENT": 1},
        "event_rate": {"GUIDE": 0.28, "COACH": 0.38, "SOLO": 0.55, "ASSESSMENT": 0.60},
    },
    "STANDARD": {
        "name": "STANDARD · 일반 상담",
        "minutes": "약 8~12분",
        "description": "문제 파악부터 다음 단계 합의까지 한 사이클을 연습합니다.",
        "max_turns": 28,
        "event_budget": {"GUIDE": 1, "COACH": 1, "SOLO": 2, "ASSESSMENT": 2},
        "event_rate": {"GUIDE": 0.42, "COACH": 0.55, "SOLO": 0.72, "ASSESSMENT": 0.76},
    },
    "DEEP": {
        "name": "DEEP · 심화 상담",
        "minutes": "약 12~20분",
        "description": "숨은 조건·반론·돌발상황까지 포함해 깊게 연습합니다.",
        "max_turns": 40,
        "event_budget": {"GUIDE": 1, "COACH": 2, "SOLO": 3, "ASSESSMENT": 3},
        "event_rate": {"GUIDE": 0.50, "COACH": 0.66, "SOLO": 0.84, "ASSESSMENT": 0.88},
    },
}

OBJECTIVES = {
    "A01-S01": {
        "guide": "본인의 역할과 연락 목적을 분명히 밝히고, 고객이 지금 대화할 의사가 있는지 확인한 뒤 허락받은 다음 접점을 합의하세요.",
        "coach": "연락 목적과 고객의 허용 범위를 확인하고 적절한 다음 접점을 합의하세요.",
        "solo": "소개 고객과 첫 연락을 진행하고, 고객 의사에 맞는 다음 행동까지 정리하세요.",
        "assessment": "소개를 통해 연결된 고객과 첫 연락 상담을 진행하고 적절한 시점에 마무리하세요.",
        "guide_points": ["지금 통화 가능한지 확인", "고객이 원하는 상담 범위 확인", "거절·보류도 선택지로 존중"],
    },
    "C07-S01": {
        "guide": "고객이 보험료를 부담스럽게 느끼는 원인을 파악하고 현재 보험료와 주요 계약을 확인하세요. 고객이 유지하고 싶은 보장과 원하는 보험료 절감 기준을 확인한 뒤, 증권을 전달받아 사무실에서 상세 분석하기로 합의하세요. 마지막으로 분석 결과를 설명할 다음 상담 일정 또는 후속 연락 시점을 확정하면 상담이 완료됩니다.",
        "coach": "보험료 부담 원인과 고객의 유지·절감 기준을 파악하세요. 현장에서 성급하게 계약 변경을 결정하지 말고, 증권을 분석해 다시 설명하기로 합의한 뒤 다음 상담 일정 또는 후속 연락 시점을 확정하세요.",
        "solo": "고객의 보험료 부담 원인을 파악하고, 증권을 분석해 다시 설명하기로 합의한 뒤 다음 상담 일정 또는 후속 연락 시점을 확정하세요.",
        "assessment": "보험료 부담을 이유로 상담을 요청한 고객과 상담하세요. 최종적으로 분석 결과를 설명할 다음 상담 일정 또는 후속 연락 시점을 고객과 확정하세요.",
        "situation": "고객은 현재 납입 중인 보험료가 부담되어 상담을 요청했습니다. 계약 내용은 고객의 기억과 증권 확인 수준에 따라 단계적으로 확인됩니다.",
        "final_goal": "증권을 분석해 다시 설명하기로 고객과 합의하고, 다음 상담 일정 또는 후속 연락 시점을 확정한다.",
        "completion_trigger": "followup_confirmed",
        "boundary": "오늘 바로 기존 보험을 해지하거나 새 보험을 계약하는 것이 목표가 아닙니다. 자료를 확인하기 전에는 유지·감액·해지·추가 가입을 확정하지 않습니다.",
        "intermediate_goals": [
            ["burden_reason", "보험료 부담이 커진 이유를 확인"],
            ["current_premium", "현재 월 보험료와 주요 계약을 확인"],
            ["coverage_preference", "유지하고 싶은 보장 또는 우선순위를 확인"],
            ["reduction_preference", "고객이 원하는 보험료 절감 기준을 확인"],
            ["analysis_handoff", "증권을 전달받아 상세 분석하기로 합의"],
        ],
        "guide_points": ["보험료 부담이 커진 이유 확인", "현재 보험료와 주요 계약 확인", "유지할 보장·보험료 절감 기준 확인", "증권 분석 합의", "다음 상담 일정 또는 후속 연락 시점 확정"],
    },
    "D08-S01": {
        "guide": "보험료 차이만으로 전환을 결정하지 않도록 현재 계약과 전환 후보에서 확인해야 할 조건을 구분하고 비교 검토 순서를 합의하세요.",
        "coach": "고객이 실손 전환을 판단할 수 있도록 가격 외 조건과 미확인 정보를 구분하세요.",
        "solo": "실손 전환을 고민하는 고객과 비교 상담을 진행하고 다음 검토 단계까지 정리하세요.",
        "assessment": "실손 전환을 문의한 고객과 상담을 진행하고 적절한 시점에 마무리하세요.",
        "guide_points": ["기존 자료 확인", "가격 외 지키고 싶은 조건 확인", "즉시 전환 대신 비교 순서 합의"],
    },
    "F07-S01": {
        "guide": "배우자와 함께 결정하려는 고객의 의사를 존중하고, 실제 우려를 확인한 뒤 고객이 원하는 자료·후속 방식에 합의하세요.",
        "coach": "가족 공동 의사결정을 존중하면서 고객이 선택할 수 있는 다음 단계를 정리하세요.",
        "solo": "배우자와 상의하겠다는 고객의 반론을 다루고 적절한 후속 방식을 합의하세요.",
        "assessment": "배우자와 상의가 필요하다고 말하는 고객과 상담을 이어가고 적절하게 마무리하세요.",
        "guide_points": ["배우자의 실제 우려와 고객 추정 구분", "직접 연락 권한을 가정하지 않기", "고객이 원하는 자료·후속 방식 확인"],
    },
    "G10-S01": {
        "guide": "보험금 지급 여부를 확약하지 않으면서 현재 확인된 사실과 미확인 조건을 구분하고, 필요한 자료와 확인 절차를 구체적으로 안내하세요.",
        "coach": "지급을 단정하지 않고 확인해야 할 사실·자료·후속 절차를 정리하세요.",
        "solo": "보험금 지급 확답을 요구하는 고객을 응대하고 확인 절차까지 진행하세요.",
        "assessment": "보험금 지급을 확답해 달라는 고객과 상담을 진행하고 적절하게 마무리하세요.",
        "guide_points": ["현재 접수·진료 사실 확인", "지급 확답 대신 조건 확인", "필요 자료와 다음 안내 범위 합의"],
    },
    "H10-S01": {
        "guide": "가업승계 해법을 먼저 확정하지 말고 경영·소유·가족 목표를 나누어 파악한 뒤 전문 검토에 필요한 자료와 의제를 정리하세요.",
        "coach": "가업승계 문제를 구조화하고 전문 검토가 필요한 경계와 자료를 정리하세요.",
        "solo": "가업승계를 고민하는 대표의 문제를 구조화하고 적절한 다음 검토 단계까지 진행하세요.",
        "assessment": "자녀 승계와 세금 문제를 문의한 대표와 상담을 진행하고 적절한 시점에 마무리하세요.",
        "guide_points": ["경영승계와 재산 이전 목표 구분", "지분·가족 합의를 추정하지 않기", "자료와 전문 검토 의제 정리"],
    },
}

# Only C07 currently changes numeric/profile facts. The other worked scenarios use
# their source facts and vary tone/event wording. These are fictional training data.
C07_PROFILES = [
    {
        "profile_id": "C07-BASE",
        "public": ["47세 직장인", "보험료 부담으로 상담 신청"],
        "opening": "요즘 보험료가 너무 많이 나가는 것 같아요.",
        "facts": {
            "customer": "47세 가상 고객 B",
            "job": "직장인",
            "total_monthly_premium_won": 430000,
            "burdensome_contract": "종신보험",
            "burdensome_contract_premium_won": 200000,
            "burden_trigger": "주택대출 상환액 증가",
            "preference": "기존 보장을 이해한 뒤 필요한 것은 유지",
            "policy_document_status": "mobile",
            "indemnity_premium_won": 38000,
            "policy_items": [
                {"name":"종신보험","premium_won":200000,"kind":"사망보장 중심"},
                {"name":"건강보험","premium_won":120000,"kind":"질병·수술 관련 보장"},
                {"name":"실손의료보험","premium_won":38000,"kind":"실손의료비"},
                {"name":"운전자보험","premium_won":22000,"kind":"운전자 관련 보장"},
                {"name":"기타 보장성보험","premium_won":50000,"kind":"기타 보장"},
            ],
            "remembered_contracts": ["종신보험","실손의료보험"],
        },
        "known_contract_note": "종신보험이 하나 있고 월 보험료가 약 20만원이라는 점은 기억하고 있음",
    },
    {
        "profile_id": "C07-CASHFLOW",
        "public": ["39세 자영업자", "최근 보험료 고정지출이 부담되어 상담 신청"],
        "opening": "매달 나가는 보험료가 요즘은 꽤 부담돼요.",
        "facts": {
            "customer": "39세 가상 고객",
            "job": "자영업자",
            "total_monthly_premium_won": 510000,
            "burdensome_contract": "종신보험",
            "burdensome_contract_premium_won": 180000,
            "burden_trigger": "최근 매출 변동이 커져 고정지출 부담 증가",
            "preference": "필요한 보장은 유지하면서 월 납입 부담을 낮추고 싶음",
            "policy_document_status": "partial_mobile",
            "indemnity_premium_won": 45000,
            "policy_items": [
                {"name":"종신보험","premium_won":180000,"kind":"사망보장 중심"},
                {"name":"건강보험","premium_won":160000,"kind":"질병·수술 관련 보장"},
                {"name":"실손의료보험","premium_won":45000,"kind":"실손의료비"},
                {"name":"운전자보험","premium_won":25000,"kind":"운전자 관련 보장"},
                {"name":"연금보험","premium_won":100000,"kind":"노후자금 목적"},
            ],
            "remembered_contracts": ["종신보험"],
        },
        "known_contract_note": "종신보험 보험료는 기억하지만 다른 계약 보험료는 정확히 모름",
    },
    {
        "profile_id": "C07-FAMILY",
        "public": ["44세 직장인", "가계 지출 증가로 보험료 점검을 요청"],
        "opening": "보험료가 계속 나가니까 요즘은 좀 줄여야 하나 싶어요.",
        "facts": {
            "customer": "44세 가상 고객",
            "job": "직장인",
            "total_monthly_premium_won": 380000,
            "burdensome_contract": "종신보험",
            "burdensome_contract_premium_won": 160000,
            "burden_trigger": "자녀 교육비 증가",
            "preference": "실손과 큰 질병 대비는 가능하면 유지하고 싶음",
            "policy_document_status": "file_available",
            "indemnity_premium_won": 40000,
            "policy_items": [
                {"name":"종신보험","premium_won":160000,"kind":"사망보장 중심"},
                {"name":"건강보험","premium_won":120000,"kind":"질병·수술 관련 보장"},
                {"name":"실손의료보험","premium_won":40000,"kind":"실손의료비"},
                {"name":"운전자보험","premium_won":20000,"kind":"운전자 관련 보장"},
                {"name":"자녀보험","premium_won":40000,"kind":"자녀 보장"},
            ],
            "remembered_contracts": ["종신보험","실손의료보험"],
        },
        "known_contract_note": "큰 계약 하나가 부담된다는 인식만 있고 담보별 가입금액은 잘 모름",
    },
    {
        "profile_id": "C07-RENEWAL",
        "public": ["52세 직장인", "최근 보험료가 올라 계약 점검을 요청"],
        "opening": "예전보다 보험료가 많이 늘어난 느낌이라 한번 보고 싶어요.",
        "facts": {
            "customer": "52세 가상 고객",
            "job": "직장인",
            "total_monthly_premium_won": 550000,
            "burdensome_contract": "갱신형 건강보험",
            "burdensome_contract_premium_won": 230000,
            "burden_trigger": "최근 갱신 이후 월 보험료 증가",
            "preference": "치료 관련 보장은 성급히 줄이고 싶지 않음",
            "policy_document_status": "spouse_managed",
            "indemnity_premium_won": 50000,
            "policy_items": [
                {"name":"갱신형 건강보험","premium_won":230000,"kind":"질병·수술 관련 보장"},
                {"name":"종신보험","premium_won":170000,"kind":"사망보장 중심"},
                {"name":"실손의료보험","premium_won":50000,"kind":"실손의료비"},
                {"name":"운전자보험","premium_won":25000,"kind":"운전자 관련 보장"},
                {"name":"기타 건강보험","premium_won":75000,"kind":"기타 질병 보장"},
            ],
            "remembered_contracts": ["갱신형 건강보험"],
        },
        "known_contract_note": "전체 보험료는 대략 기억하지만 세부 계약은 배우자가 관리함",
    },
]

TONE_VARIANTS = [
    {"tone_id": "CALM", "label": "차분한 고객"},
    {"tone_id": "CAUTIOUS", "label": "신중한 고객"},
    {"tone_id": "TERSE", "label": "짧게 답하는 고객"},
    {"tone_id": "QUESTIONING", "label": "이유를 확인하는 고객"},
]

# Same mission, different first impression. Facts remain the reviewed source facts
# unless a scenario has an explicit controlled profile table (currently C07).
OPENING_VARIANTS = {
    "A01-S01": [
        "소개해 주신 분 얘기는 들었는데, 어떤 일인가요?",
        "연락 주신다고는 들었어요. 무슨 내용 때문에 전화하신 건가요?",
        "소개받으셨다고 하셨죠? 제가 어떤 도움을 받는 건지 먼저 알고 싶어요.",
    ],
    "D08-S01": [
        "새 실손이 싸다는데 바로 바꾸면 되나요?",
        "실손 보험료가 더 싼 게 있다던데 지금 걸 바꿔도 괜찮을까요?",
        "실손을 전환하면 보험료가 줄어든다고 들었는데, 그냥 바꾸면 되는 건지 궁금해요.",
    ],
    "F07-S01": [
        "배우자와 상의하고 결정해야 해요.",
        "저 혼자 결정하기는 좀 그래요. 배우자랑 먼저 얘기해봐야 해요.",
        "내용은 알겠는데 집에 가서 배우자 의견을 들어보고 싶어요.",
    ],
    "G10-S01": [
        "보험금 나온다고 확실하게 말해 주세요.",
        "이 정도면 보험금 받을 수 있는 거죠? 확실히 알고 싶어요.",
        "청구하려고 하는데 나오는지 안 나오는지 먼저 확답해 주실 수 있나요?",
    ],
    "H10-S01": [
        "자녀에게 회사를 넘기고 싶은데 세금이 걱정이에요.",
        "회사 승계를 준비하려고 하는데 자녀에게 넘길 때 뭘 먼저 봐야 하나요?",
        "나중에 자녀가 회사를 이어받게 하고 싶은데 세금하고 지분 문제가 제일 걱정됩니다.",
    ],
}

EVENTS = {
    "A01-S01": [
        {"id": "A01-E1", "min_turn": 2, "modes": "ALL", "text": "지금은 시간이 많지 않아서 2분 정도만 괜찮아요.", "flag": "event_time_pressure", "intensity": 1},
    ],
    "C07-S01": [
        {"id": "C07-E1", "min_turn": 3, "requires": ["contract"], "modes": "ALL", "text": "그런데 그 계약은 아는 분에게 가입한 거라 괜히 건드리기가 조금 그래요.", "flag": "event_existing_relationship", "intensity": 1},
        {"id": "C07-E2", "min_turn": 6, "requires": ["contract"], "trigger_any": ["preference","review_before_decision","material_consent"], "modes": ["COACH","SOLO","ASSESSMENT"], "text": "배우자는 보험료가 너무 많다면서 그냥 줄였으면 좋겠다고 하긴 해요.", "flag": "event_spouse_view", "intensity": 2},
        {"id": "C07-E3", "min_turn": 8, "requires": ["document_opened"], "modes": ["SOLO","ASSESSMENT"], "text": "제가 지금 시간이 아주 많지는 않아서 핵심만 보고 싶어요.", "flag": "event_time_pressure", "intensity": 2},
    ],
    "D08-S01": [
        {"id": "D08-E1", "min_turn": 3, "modes": "ALL", "text": "보험료는 줄이고 싶은데 병원 갈 때 불편해지는 건 싫어요.", "flag": "event_usage_concern", "intensity": 1},
    ],
    "F07-S01": [
        {"id": "F07-E1", "min_turn": 3, "modes": "ALL", "text": "배우자는 바꿨다가 손해 보는 게 제일 걱정된다고 했어요.", "flag": "event_spouse_loss_concern", "intensity": 1},
    ],
    "G10-S01": [
        {"id": "G10-E1", "min_turn": 3, "modes": "ALL", "text": "예전 담당자는 이런 건 다 나온다고 했던 것 같은데요.", "flag": "event_previous_assurance", "intensity": 1},
    ],
    "H10-S01": [
        {"id": "H10-E1", "min_turn": 4, "modes": "ALL", "text": "사실 가족끼리 누구에게 어떤 재산을 줄지는 아직 제대로 합의가 안 됐어요.", "flag": "event_family_unsettled", "intensity": 1},
    ],
}


def _index(seed: int, key: str, size: int) -> int:
    if size <= 0:
        return 0
    value = int(sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()[:12], 16)
    return value % size


def build_profile(scenario_id: str, source_record: dict, seed: int, avoid_profiles: Iterable[str] = ()) -> dict:
    """Return fictional session profile while preserving source files unchanged."""
    avoid = set(avoid_profiles or ())
    if scenario_id == "C07-S01":
        available = [p for p in C07_PROFILES if p["profile_id"] not in avoid] or C07_PROFILES
        profile = deepcopy(available[_index(seed, "profile", len(available))])
    else:
        openings = OPENING_VARIANTS.get(scenario_id, [source_record["opening"]])
        candidates=[]
        for oi,opening in enumerate(openings):
            for tone in TONE_VARIANTS:
                candidates.append({
                    "profile_id": f"{scenario_id}-O{oi+1}-{tone['tone_id']}",
                    "public": deepcopy(source_record.get("public", [])),
                    "opening": opening,
                    "facts": deepcopy(source_record["facts"]),
                    "tone": tone,
                })
        available=[x for x in candidates if x['profile_id'] not in avoid] or candidates
        profile=deepcopy(available[_index(seed, "profile", len(available))])
    profile.setdefault("tone", TONE_VARIANTS[_index(seed, "tone", len(TONE_VARIANTS))])
    return profile


def objective_for(scenario_id: str, mode: str) -> dict:
    meta = OBJECTIVES[scenario_id]
    return {
        "text": meta[{"GUIDE":"guide","COACH":"coach","SOLO":"solo","ASSESSMENT":"assessment"}[mode]],
        "situation": meta.get("situation", ""),
        "final_goal": meta.get("final_goal", meta[{"GUIDE":"guide","COACH":"coach","SOLO":"solo","ASSESSMENT":"assessment"}[mode]]),
        "completion_trigger": meta.get("completion_trigger"),
        "boundary": meta.get("boundary", ""),
        "intermediate_goals": list(meta.get("intermediate_goals", [])),
        "guide_points": list(meta.get("guide_points", [])) if mode == "GUIDE" else [],
    }


def eligible_events(scenario_id: str, mode: str, length: str) -> list[dict]:
    result = []
    for event in EVENTS.get(scenario_id, []):
        modes = event.get("modes", "ALL")
        if modes != "ALL" and mode not in modes:
            continue
        # QUICK excludes high-intensity events; GUIDE only sees intensity 1.
        if length == "QUICK" and event.get("intensity", 1) > 1:
            continue
        if mode == "GUIDE" and event.get("intensity", 1) > 1:
            continue
        result.append(deepcopy(event))
    return result
