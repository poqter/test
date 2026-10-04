"""Training mode/focus catalog used before the conversational API is attached."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .constants import MODE_CONTROLLER_VERSION, TRAINING_FOCUS_VERSION, TRAINING_MODES


@dataclass(frozen=True)
class TrainingFocus:
    code: str
    name: str
    description: str
    customer_modifiers: dict[str, Any]
    evaluation_weights: dict[str, float]


FOCUSES: dict[str, TrainingFocus] = {
    "comprehensive": TrainingFocus(
        "comprehensive", "종합 상담", "상담 전 과정을 균형 있게 훈련합니다.", {},
        {"discovery": 1.0, "needs": 1.0, "explanation": 1.0, "persuasion": 1.0, "closing": 1.0},
    ),
    "rapport": TrainingFocus(
        "rapport", "관계형성", "초기 경계와 불신을 낮추고 대화 기반을 만드는 훈련입니다.",
        {"sales_resistance": 1, "trust_threshold": 1}, {"rapport": 2.0, "customer_experience": 1.5},
    ),
    "information_discovery": TrainingFocus(
        "information_discovery", "정보 탐색·질문", "말수가 적거나 정보 공개가 느린 고객에게 필요한 정보를 얻는 훈련입니다.",
        {"disclosure_resistance": 2, "verbosity": -1, "question_reason_sensitivity": 1},
        {"discovery": 2.0, "listening": 1.5, "information_accuracy": 1.5},
    ),
    "needs_discovery": TrainingFocus(
        "needs_discovery", "니즈 발견", "표면 니즈 아래의 잠재 니즈를 발견하는 훈련입니다.",
        {"latent_need_depth": 2}, {"needs": 2.0, "listening": 1.5},
    ),
    "financial_capacity": TrainingFocus(
        "financial_capacity", "경제여력 파악", "민감한 재무정보를 맥락에 맞게 확인하는 훈련입니다.",
        {"financial_sensitivity": 2}, {"financial_capacity": 2.0, "question_quality": 1.4},
    ),
    "insurance_information": TrainingFocus(
        "insurance_information", "보험정보 파악", "고객이 정확히 알지 못하는 가입정보를 정리하는 훈련입니다.",
        {"insurance_knowledge": -2}, {"insurance_information": 2.0, "discovery": 1.4},
    ),
    "coverage_analysis": TrainingFocus(
        "coverage_analysis", "보장분석 능력", "보장분석표에서 유지·공백·중복을 정확히 읽는 훈련입니다.",
        {"insurance_complexity": 1}, {"analysis_accuracy": 2.0, "prioritization": 1.5},
    ),
    "analysis_explanation": TrainingFocus(
        "analysis_explanation", "보장분석 설명", "분석 결과를 고객의 언어와 니즈에 연결해 설명하는 훈련입니다.",
        {}, {"explanation": 2.0, "customer_fit": 1.5},
    ),
    "proposal": TrainingFocus(
        "proposal", "제안력", "유지·보완·절감·증액 등 복수 대안을 설계하고 비교하는 훈련입니다.",
        {}, {"proposal_fit": 2.0, "prioritization": 1.4},
    ),
    "persuasion": TrainingFocus(
        "persuasion", "설득력", "고객의 판단을 근거 있게 진전시키는 훈련입니다.",
        {"decision_inertia": 1}, {"persuasion": 2.0, "value_communication": 1.5},
    ),
    "risk_visualization": TrainingFocus(
        "risk_visualization", "위험 환기", "현실적인 위험과 행동하지 않을 때의 손실을 구체화하는 훈련입니다.",
        {"risk_underestimation": 2}, {"risk_visualization": 2.0, "truthfulness": 1.5},
    ),
    "objection_diagnosis": TrainingFocus(
        "objection_diagnosis", "반론 원인 진단", "표면 반론 뒤의 가격·신뢰·배우자·변화저항 원인을 찾는 훈련입니다.",
        {"objection_layers": 2}, {"objection_diagnosis": 2.0, "listening": 1.4},
    ),
    "objection_handling": TrainingFocus(
        "objection_handling", "반론 대응", "발견한 반론 원인에 맞게 설득과 대안을 사용하는 훈련입니다.",
        {"objection_tendency": 2}, {"objection_handling": 2.0, "persuasion": 1.4},
    ),
    "closing": TrainingFocus(
        "closing", "클로징", "필요성은 인정하지만 결정을 미루는 고객에게 적절한 시점에 결정을 요청하는 훈련입니다.",
        {"need_acceptance": 2, "decision_inertia": 2, "objection_tendency": 1},
        {"buying_signal": 1.7, "closing": 2.0, "decision_advancement": 1.7},
    ),
    "next_action": TrainingFocus(
        "next_action", "다음 행동 확정", "상담 종료 전에 다음 일정·자료·의사결정 행동을 명확히 합의하는 훈련입니다.",
        {}, {"next_action": 2.0, "flow": 1.4},
    ),
}


MODE_POLICIES = {
    "GUIDE": {
        "name": "가이드모드", "live_help": "proactive", "turn_feedback": "guided",
        "official_growth_score": False, "can_show_examples": True, "can_edit_before_commit": True,
    },
    "COACH": {
        "name": "코치모드", "live_help": "after_attempt", "turn_feedback": "immediate",
        "official_growth_score": False, "can_show_examples": True, "can_edit_before_commit": True,
    },
    "SOLO": {
        "name": "솔로모드", "live_help": "none", "turn_feedback": "after_session",
        "official_growth_score": False, "can_show_examples": False, "can_edit_before_commit": False,
    },
    "ASSESSMENT": {
        "name": "평가모드", "live_help": "none", "turn_feedback": "formal_after_session",
        "official_growth_score": True, "can_show_examples": False, "can_edit_before_commit": False,
    },
}


def validate_training_mode(mode: str) -> str:
    mode = str(mode or "").upper()
    if mode not in TRAINING_MODES:
        raise ValueError(f"unsupported training mode: {mode}")
    return mode


def validate_training_focus(code: str) -> str:
    code = str(code or "comprehensive").strip().lower()
    if code not in FOCUSES:
        raise ValueError(f"unsupported training focus: {code}")
    return code


def mode_policy(mode: str) -> dict[str, Any]:
    return {"version": MODE_CONTROLLER_VERSION, "mode": validate_training_mode(mode), **MODE_POLICIES[validate_training_mode(mode)]}


def focus_policy(code: str) -> dict[str, Any]:
    focus = FOCUSES[validate_training_focus(code)]
    return {"version": TRAINING_FOCUS_VERSION, **asdict(focus)}


def public_focus_catalog() -> list[dict[str, str]]:
    return [{"code": f.code, "name": f.name, "description": f.description} for f in FOCUSES.values()]
