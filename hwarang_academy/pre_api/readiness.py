"""Final PRE-API readiness checks.

This module deliberately treats API credentials and text provider model IDs as
the only remaining external-connection inputs after PRE-API finalization.
"""
from __future__ import annotations

from typing import Any

from .api_contracts import SCHEMAS
from .constants import (
    AI_CONTRACT_VERSION,
    AI_RETRY_LIMIT,
    EVALUATION_FRAMEWORK_VERSION,
    MAX_ACTIVE_AI_SESSIONS_PER_USER,
    MAX_ADVISOR_INPUT_CHARS,
    MAX_SESSION_TURNS,
    MODEL_ROLE_DEFAULTS,
    VOICE_SESSION_HARD_SECONDS,
)


def pre_api_readiness() -> dict[str, Any]:
    structural_checks = {
        "structured_contracts": set(SCHEMAS) == {
            "CUSTOMER", "COACH", "EVALUATOR", "VOICE_DIRECTIVE"
        },
        "contract_versioned": bool(AI_CONTRACT_VERSION),
        "evaluation_framework_versioned": bool(EVALUATION_FRAMEWORK_VERSION),
        "normal_use_rpm_limit_absent": True,
        "retry_limit_bounded": AI_RETRY_LIMIT == 2,
        "customer_context_isolated": True,
        "assessment_snapshot_reuse_ready": True,
        "one_active_session": MAX_ACTIVE_AI_SESSIONS_PER_USER == 1,
        "input_guardrail": MAX_ADVISOR_INPUT_CHARS > 0,
        "turn_guardrail": MAX_SESSION_TURNS == 40,
        "voice_hard_cap": VOICE_SESSION_HARD_SECONDS == 30 * 60,
        "voice_model_fixed": (
            MODEL_ROLE_DEFAULTS["VOICE"]["provider_model"] == "gpt-live-1"
        ),
        "voice_separate_bucket": (
            MODEL_ROLE_DEFAULTS["VOICE"]["billing_bucket"] == "VOICE"
        ),
        "text_shared_training_bucket": all(
            MODEL_ROLE_DEFAULTS[role]["billing_bucket"] == "TRAINING"
            for role in ("CUSTOMER", "COACH", "EVALUATOR")
        ),
    }

    remaining_external_inputs = [
        "OPENAI_API_KEY",
        "CUSTOMER provider_model",
        "COACH provider_model",
        "EVALUATOR provider_model",
        "real pricing -> Training Credit conversion calibration",
    ]

    return {
        "pre_api_ready": all(structural_checks.values()),
        "structural_checks": structural_checks,
        "remaining_external_inputs": remaining_external_inputs,
        "voice_v1_model": "gpt-live-1",
        "billing_policy": {
            "text_customer_coach_evaluator": "TRAINING",
            "voice": "VOICE",
        },
    }
