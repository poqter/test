"""Deterministic mock AI adapter for PRE-API integration tests.

This module spends no money and makes no network calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .api_contracts import validate_contract
from .constants import AI_CONTRACT_VERSION, EVALUATION_COMPETENCIES


@dataclass
class MockAIAdapter:
    """Simple schema-valid adapter used before a real OpenAI client exists."""

    def customer(self, request: dict[str, Any]) -> dict[str, Any]:
        text = str(request["input"]["advisor_utterance"])
        low = text.casefold()

        if any(k in low for k in ("보험료", "얼마", "납입")):
            customer_text = "정확한 금액은 잘 모르겠는데, 생각보다 많이 나가는 것 같아서 부담돼요."
            signals = ["price_concern", "interest"]
            objection = {
                "surface": "보험료 부담",
                "possible_cause": "현재 고정지출 대비 보험료가 높다고 느낌",
                "intensity": 2,
            }
        elif any(k in low for k in ("배우자", "남편", "아내")):
            customer_text = "저 혼자 바로 결정하기보다는 배우자랑도 한번 얘기해보고 싶어요."
            signals = ["spouse_consult", "delay_signal"]
            objection = {
                "surface": "배우자와 상의 필요",
                "possible_cause": "공동 의사결정",
                "intensity": 2,
            }
        else:
            customer_text = "네, 그 부분은 조금 더 설명을 들어보고 싶어요."
            signals = ["interest"]
            objection = None

        payload = {
            "contract_version": AI_CONTRACT_VERSION,
            "customer_text": customer_text,
            "state_proposals": {
                "trust_delta": 1,
                "interest_delta": 1,
                "decision_readiness_delta": 0,
                "pressure_response": "neutral",
                "objection_state": "active" if objection else "none",
                "should_end": False,
            },
            "disclosures": [],
            "signals": signals,
            "objection": objection,
            "goal_evidence": [],
            "conversation_control": {
                "ask_back": False,
                "pace": "normal",
                "topic_shift": None,
            },
        }
        return validate_contract("CUSTOMER", payload)

    def coach(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "contract_version": AI_CONTRACT_VERSION,
            "summary": "고객의 말을 이어받아 상담을 계속할 수 있는 답변입니다.",
            "what_worked": ["고객의 현재 관심사에 반응했습니다."],
            "improve_next": ["다음 질문은 한 번에 한 가지 정보만 확인해 보세요."],
            "suggested_direction": "고객의 이유를 먼저 확인한 뒤 필요한 정보를 단계적으로 질문하세요.",
            "example_response": "보험료가 부담스럽다고 느끼신 계기가 최근에 따로 있으셨을까요?",
            "evidence_turns": [],
        }
        return validate_contract("COACH", payload)

    def evaluator(self, request: dict[str, Any]) -> dict[str, Any]:
        transcript = list(request["input"].get("transcript") or [])
        advisor_turns = [
            int(row.get("turn") or 0)
            for row in transcript
            if row.get("role") == "advisor" and int(row.get("turn") or 0) > 0
        ]
        evidence = advisor_turns[-2:] if advisor_turns else [1]

        competencies = [
            {
                "code": code,
                "score": 70,
                "rationale": "PRE-API mock evaluator의 기준 점수입니다.",
                "evidence_turns": evidence,
            }
            for code in EVALUATION_COMPETENCIES
        ]
        payload = {
            "contract_version": AI_CONTRACT_VERSION,
            "overall_score": 70,
            "grade": "B",
            "consultation_quality": {
                "score": 72,
                "summary": "상담 흐름은 안정적이나 질문의 우선순위를 더 선명하게 만들 여지가 있습니다.",
            },
            "sales_outcome": {
                "status": "decision_advanced",
                "summary": "고객의 판단을 한 단계 진전시킨 것으로 가정한 PRE-API mock 결과입니다.",
            },
            "competencies": competencies,
            "strengths": [
                {
                    "title": "대화 지속",
                    "detail": "고객 반응을 받아 상담 흐름을 유지했습니다.",
                    "evidence_turns": evidence,
                }
            ],
            "development_areas": [
                {
                    "title": "질문 우선순위",
                    "detail": "핵심 정보를 더 짧고 순차적으로 확인할 수 있습니다.",
                    "how_to_improve": "한 번에 하나의 목적만 가진 질문으로 상담을 진행하세요.",
                    "evidence_turns": evidence,
                }
            ],
            "missed_opportunities": [],
            "pressure_evaluation": {
                "level": "moderate",
                "quality": "appropriate",
                "rationale": "PRE-API mock 기준으로 고객 자율성을 해치지 않는 수준으로 분류했습니다.",
            },
            "sales_conversion_summary": {
                "sale_blockers": ["추가 정보 확인 필요"],
                "decision_advancement": "고객의 관심을 유지하며 다음 판단 단계로 이동했습니다.",
                "next_best_action": "핵심 미확인 정보를 확인한 뒤 다음 행동을 구체적으로 합의하세요.",
            },
            "coaching_plan": {
                "immediate": "다음 상담에서는 질문 목적을 하나씩 분리하세요.",
                "practice": "정보탐색과 클로징 Focus를 반복 훈련하세요.",
                "field_application": "실전에서도 고객 답변 직후 다음 질문의 목적을 한 문장으로 정리해보세요.",
            },
            "recommended_training": [
                {
                    "focus_code": "information_discovery",
                    "reason": "질문 우선순위와 정보 탐색 정교화를 위해 추천합니다.",
                }
            ],
        }
        return validate_contract("EVALUATOR", payload)
