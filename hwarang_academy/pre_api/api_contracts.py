"""Strict structured-output contracts for future OpenAI integration.

These schemas are intentionally provider-agnostic. The real API adapter can pass
these JSON Schemas to Structured Outputs later, while the PRE-API runtime uses
the same schemas for mock and regression validation.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from .constants import AI_CONTRACT_VERSION, EVALUATION_COMPETENCIES


_SIGNAL_CODES = (
    "trust_up",
    "trust_down",
    "interest",
    "price_concern",
    "need_recognized",
    "proposal_interest",
    "buying_signal",
    "delay_signal",
    "spouse_consult",
    "comparison_request",
    "objection",
    "close_resistance",
    "next_action_ready",
)

_GOAL_STRENGTH = ("weak", "partial", "sufficient", "strong")
_PRESSURE_RESPONSE = ("comfortable", "neutral", "tense", "resistant")
_OBJECTION_STATE = ("none", "surface", "active", "resolved", "deferred")


CUSTOMER_RESPONSE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HWARANG Customer AI Response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "customer_text",
        "state_proposals",
        "disclosures",
        "signals",
        "objection",
        "goal_evidence",
        "conversation_control",
    ],
    "properties": {
        "contract_version": {"const": AI_CONTRACT_VERSION},
        "customer_text": {"type": "string", "minLength": 1, "maxLength": 1800},
        "state_proposals": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "trust_delta",
                "interest_delta",
                "decision_readiness_delta",
                "pressure_response",
                "objection_state",
                "should_end",
            ],
            "properties": {
                "trust_delta": {"type": "integer", "minimum": -2, "maximum": 2},
                "interest_delta": {"type": "integer", "minimum": -2, "maximum": 2},
                "decision_readiness_delta": {"type": "integer", "minimum": -2, "maximum": 2},
                "pressure_response": {"enum": list(_PRESSURE_RESPONSE)},
                "objection_state": {"enum": list(_OBJECTION_STATE)},
                "should_end": {"type": "boolean"},
            },
        },
        "disclosures": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "value", "precision"],
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 180,
                        "pattern": "^(ground_truth|customer_beliefs|insurance_memory)\\.",
                    },
                    "value": {},
                    "precision": {"enum": ["exact", "approximate", "uncertain"]},
                },
            },
        },
        "signals": {
            "type": "array",
            "uniqueItems": True,
            "maxItems": 8,
            "items": {"enum": list(_SIGNAL_CODES)},
        },
        "objection": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["surface", "possible_cause", "intensity"],
                    "properties": {
                        "surface": {"type": "string", "minLength": 1, "maxLength": 240},
                        "possible_cause": {"type": "string", "minLength": 1, "maxLength": 240},
                        "intensity": {"type": "integer", "minimum": 0, "maximum": 4},
                    },
                },
            ]
        },
        "goal_evidence": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["goal_code", "strength", "evidence"],
                "properties": {
                    "goal_code": {"type": "string", "minLength": 1, "maxLength": 80},
                    "strength": {"enum": list(_GOAL_STRENGTH)},
                    "evidence": {"type": "string", "minLength": 1, "maxLength": 320},
                },
            },
        },
        "conversation_control": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ask_back", "pace", "topic_shift"],
            "properties": {
                "ask_back": {"type": "boolean"},
                "pace": {"enum": ["short", "normal", "detailed"]},
                "topic_shift": {
                    "anyOf": [
                        {"type": "null"},
                        {"type": "string", "minLength": 1, "maxLength": 120},
                    ]
                },
            },
        },
    },
}


COACH_RESPONSE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HWARANG Coach AI Response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "summary",
        "what_worked",
        "improve_next",
        "suggested_direction",
        "example_response",
        "evidence_turns",
    ],
    "properties": {
        "contract_version": {"const": AI_CONTRACT_VERSION},
        "summary": {"type": "string", "minLength": 1, "maxLength": 700},
        "what_worked": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string", "minLength": 1, "maxLength": 300},
        },
        "improve_next": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {"type": "string", "minLength": 1, "maxLength": 300},
        },
        "suggested_direction": {"type": "string", "minLength": 1, "maxLength": 600},
        "example_response": {"type": "string", "minLength": 1, "maxLength": 900},
        "evidence_turns": {
            "type": "array",
            "uniqueItems": True,
            "maxItems": 8,
            "items": {"type": "integer", "minimum": 1},
        },
    },
}


EVALUATOR_RESPONSE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HWARANG Formal Evaluator Response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "overall_score",
        "grade",
        "consultation_quality",
        "sales_outcome",
        "competencies",
        "strengths",
        "development_areas",
        "missed_opportunities",
        "pressure_evaluation",
        "sales_conversion_summary",
        "coaching_plan",
        "recommended_training",
    ],
    "properties": {
        "contract_version": {"const": AI_CONTRACT_VERSION},
        "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
        "grade": {"type": "string", "minLength": 1, "maxLength": 30},
        "consultation_quality": {
            "type": "object",
            "additionalProperties": False,
            "required": ["score", "summary"],
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 100},
                "summary": {"type": "string", "minLength": 1, "maxLength": 800},
            },
        },
        "sales_outcome": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "summary"],
            "properties": {
                "status": {
                    "enum": [
                        "no_progress",
                        "relationship_advanced",
                        "need_advanced",
                        "proposal_advanced",
                        "decision_advanced",
                        "next_action_secured",
                        "sale_completed",
                    ]
                },
                "summary": {"type": "string", "minLength": 1, "maxLength": 800},
            },
        },
        "competencies": {
            "type": "array",
            "minItems": len(EVALUATION_COMPETENCIES),
            "maxItems": len(EVALUATION_COMPETENCIES),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "score", "rationale", "evidence_turns"],
                "properties": {
                    "code": {"enum": list(EVALUATION_COMPETENCIES)},
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                    "rationale": {"type": "string", "minLength": 1, "maxLength": 700},
                    "evidence_turns": {
                        "type": "array",
                        "uniqueItems": True,
                        "maxItems": 10,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
        "strengths": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "evidence_turns"],
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 120},
                    "detail": {"type": "string", "minLength": 1, "maxLength": 700},
                    "evidence_turns": {
                        "type": "array",
                        "uniqueItems": True,
                        "maxItems": 10,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
        "development_areas": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "how_to_improve", "evidence_turns"],
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 120},
                    "detail": {"type": "string", "minLength": 1, "maxLength": 700},
                    "how_to_improve": {"type": "string", "minLength": 1, "maxLength": 800},
                    "evidence_turns": {
                        "type": "array",
                        "uniqueItems": True,
                        "maxItems": 10,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
        "missed_opportunities": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["turn_no", "opportunity", "better_action"],
                "properties": {
                    "turn_no": {"type": "integer", "minimum": 1},
                    "opportunity": {"type": "string", "minLength": 1, "maxLength": 600},
                    "better_action": {"type": "string", "minLength": 1, "maxLength": 700},
                },
            },
        },
        "pressure_evaluation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["level", "quality", "rationale"],
            "properties": {
                "level": {"enum": ["low", "moderate", "high"]},
                "quality": {"enum": ["appropriate", "effective", "excessive", "manipulative"]},
                "rationale": {"type": "string", "minLength": 1, "maxLength": 800},
            },
        },
        "sales_conversion_summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["sale_blockers", "decision_advancement", "next_best_action"],
            "properties": {
                "sale_blockers": {
                    "type": "array",
                    "maxItems": 6,
                    "items": {"type": "string", "minLength": 1, "maxLength": 400},
                },
                "decision_advancement": {"type": "string", "minLength": 1, "maxLength": 800},
                "next_best_action": {"type": "string", "minLength": 1, "maxLength": 800},
            },
        },
        "coaching_plan": {
            "type": "object",
            "additionalProperties": False,
            "required": ["immediate", "practice", "field_application"],
            "properties": {
                "immediate": {"type": "string", "minLength": 1, "maxLength": 800},
                "practice": {"type": "string", "minLength": 1, "maxLength": 800},
                "field_application": {"type": "string", "minLength": 1, "maxLength": 800},
            },
        },
        "recommended_training": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["focus_code", "reason"],
                "properties": {
                    "focus_code": {"type": "string", "minLength": 1, "maxLength": 80},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 600},
                },
            },
        },
    },
}


VOICE_BACKEND_DIRECTIVE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HWARANG GPT-Live Backend Directive",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "allowed_facts",
        "forbidden_facts",
        "speaking_goal",
        "tone_shift",
        "max_spoken_sentences",
        "should_wait",
    ],
    "properties": {
        "contract_version": {"const": AI_CONTRACT_VERSION},
        "allowed_facts": {
            "type": "array",
            "maxItems": 12,
            "items": {"type": "string", "maxLength": 500},
        },
        "forbidden_facts": {
            "type": "array",
            "maxItems": 12,
            "items": {"type": "string", "maxLength": 500},
        },
        "speaking_goal": {"type": "string", "minLength": 1, "maxLength": 700},
        "tone_shift": {
            "enum": ["keep", "warmer", "more_cautious", "more_resistant", "more_open", "more_decisive"]
        },
        "max_spoken_sentences": {"type": "integer", "minimum": 1, "maximum": 6},
        "should_wait": {"type": "boolean"},
    },
}


SCHEMAS = {
    "CUSTOMER": CUSTOMER_RESPONSE_SCHEMA,
    "COACH": COACH_RESPONSE_SCHEMA,
    "EVALUATOR": EVALUATOR_RESPONSE_SCHEMA,
    "VOICE_DIRECTIVE": VOICE_BACKEND_DIRECTIVE_SCHEMA,
}


class ContractValidationError(ValueError):
    pass


def schema_for(kind: str) -> dict[str, Any]:
    key = str(kind or "").upper()
    if key not in SCHEMAS:
        raise KeyError(f"unknown AI contract: {kind}")
    return deepcopy(SCHEMAS[key])


def validate_contract(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    key = str(kind or "").upper()
    if key not in SCHEMAS:
        raise ContractValidationError(f"unknown AI contract: {kind}")

    errors = sorted(
        Draft202012Validator(SCHEMAS[key]).iter_errors(payload),
        key=lambda e: list(e.path),
    )
    if errors:
        first = errors[0]
        where = ".".join(str(x) for x in first.path) or "<root>"
        raise ContractValidationError(f"{key} contract invalid at {where}: {first.message}")

    if key == "EVALUATOR":
        codes = [row["code"] for row in payload["competencies"]]
        if len(codes) != len(set(codes)):
            raise ContractValidationError("EVALUATOR competencies contain duplicate codes")
        missing = set(EVALUATION_COMPETENCIES) - set(codes)
        extra = set(codes) - set(EVALUATION_COMPETENCIES)
        if missing or extra:
            raise ContractValidationError(
                "EVALUATOR competency coverage mismatch: "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )

    return payload
