"""Versioned constants for the HWARANG ACADEMY pre-API simulator core."""
from __future__ import annotations

CUSTOMER_GENERATOR_VERSION = "1.0.0"
INSURANCE_GENERATOR_VERSION = "1.0.0"
COVERAGE_MAPPING_VERSION = "1.0.0"
COVERAGE_ANALYSIS_VERSION = "1.0.0"
EXCEL_TEMPLATE_VERSION = "coverage-v3-2026.10.04"
PROPOSAL_GENERATOR_VERSION = "1.0.0"
CASE_ENGINE_VERSION = "1.0.0"
EVIDENCE_LOG_VERSION = "1.0.0"
TRAINING_FOCUS_VERSION = "1.0.0"
MODE_CONTROLLER_VERSION = "1.0.0"
VOICE_PROFILE_VERSION = "1.0.0"

# Final PRE-API interface versions
AI_CONTRACT_VERSION = "pre-api-contract-v1"
CUSTOMER_PROMPT_VERSION = "customer-v1"
COACH_PROMPT_VERSION = "coach-v1"
EVALUATOR_PROMPT_VERSION = "evaluator-v1"
VOICE_PROMPT_VERSION = "voice-live-v1"
EVALUATION_FRAMEWORK_VERSION = "commercial-eval-v1"

MIN_CUSTOMER_AGE = 30
MAX_CUSTOMER_AGE = 79
SIMULATION_REFERENCE_DATE = "2026-10-04"
MAX_CONTRACTS_V1 = 7  # fixed to the approved 7-contract Excel template width (D:J)

PORTFOLIO_ARCHETYPES = (
    "BALANCED",
    "UNDERINSURED",
    "OVERINSURED",
    "DUPLICATED",
    "OUTDATED",
    "RENEWAL_HEAVY",
    "GAP_SPECIFIC",
    "MIXED",
)

CONSULTATION_DIFFICULTIES = ("easy", "standard", "hard")
INSURANCE_COMPLEXITIES = ("low", "medium", "high")
INTERACTION_MODES = ("TEXT", "VOICE")
TRAINING_MODES = ("GUIDE", "COACH", "SOLO", "ASSESSMENT")

# Guardrail defaults.
# Normal use intentionally has no requests-per-minute limit.
MAX_ADVISOR_INPUT_CHARS = 2400
MAX_SESSION_TURNS = 40
CUSTOMER_MAX_OUTPUT_TOKENS = 800
COACH_MAX_OUTPUT_TOKENS = 1200
EVALUATOR_MAX_OUTPUT_TOKENS = 6000
VOICE_SESSION_SOFT_SECONDS = 25 * 60
VOICE_SESSION_HARD_SECONDS = 30 * 60
AI_RETRY_LIMIT = 2
MAX_ACTIVE_AI_SESSIONS_PER_USER = 1

# Roles are stable logical contracts. Provider model IDs are deliberately
# unbound for text roles until the real OpenAI API connection is made.
MODEL_ROLE_DEFAULTS = {
    "CUSTOMER": {
        "provider_model": None,
        "billing_bucket": "TRAINING",
        "max_output_tokens": CUSTOMER_MAX_OUTPUT_TOKENS,
    },
    "COACH": {
        "provider_model": None,
        "billing_bucket": "TRAINING",
        "max_output_tokens": COACH_MAX_OUTPUT_TOKENS,
    },
    "EVALUATOR": {
        "provider_model": None,
        "billing_bucket": "TRAINING",
        "max_output_tokens": EVALUATOR_MAX_OUTPUT_TOKENS,
    },
    "VOICE": {
        "provider_model": "gpt-live-1",
        "billing_bucket": "VOICE",
        "max_output_tokens": None,
    },
}

EVALUATION_COMPETENCIES = (
    "rapport",
    "information_discovery",
    "needs_discovery",
    "financial_capacity",
    "insurance_information",
    "coverage_analysis",
    "analysis_explanation",
    "proposal_fit",
    "need_creation",
    "value_communication",
    "risk_visualization",
    "objection_diagnosis",
    "objection_handling",
    "persuasion",
    "buying_signal_detection",
    "closing_timing",
    "decision_advancement",
    "next_action",
)
