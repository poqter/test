"""HWARANG ACADEMY pre-API simulator core.

This package contains deterministic customer/insurance/analysis/proposal logic
plus the finalized provider-agnostic AI contracts/runtime.
No OpenAI or other paid API is called here.
"""
from .case_engine import GeneratedCase, create_case, case_to_supabase_record
from .customer import CustomerProfile, generate_customer
from .insurance import InsurancePortfolio, generate_insurance_portfolio
from .coverage import CoverageAnalysis, analyze_coverage, EXCEL_COVERAGE_ROWS
from .proposal import ProposalState, generate_proposals
from .excel import build_coverage_analysis_xlsx, workbook_payload, suggested_filename
from .training import FOCUSES, MODE_POLICIES, focus_policy, mode_policy, public_focus_catalog
from .evidence import make_turn_evidence
from .disclosure import (
    build_customer_disclosure_source,
    build_customer_insurance_memory,
    build_customer_model_context,
)
from .retry_policy import RetryDecision, retry_decision

from .api_contracts import (
    CUSTOMER_RESPONSE_SCHEMA,
    COACH_RESPONSE_SCHEMA,
    EVALUATOR_RESPONSE_SCHEMA,
    VOICE_BACKEND_DIRECTIVE_SCHEMA,
    validate_contract,
)
from .prompt_builder import (
    build_customer_request,
    build_coach_request,
    build_evaluator_request,
    build_live_session_spec,
)
from .state_validator import (
    ValidatedCustomerTurn,
    validate_customer_turn,
    apply_conversation_state,
)
from .mock_ai import MockAIAdapter
from .readiness import pre_api_readiness
from .runtime import (
    AIAdapter,
    PreAPIRuntime,
    CustomerTurnResult,
    CoachResult,
    EvaluationResult,
    assessment_snapshot_hash,
    voice_directive_from_customer_turn,
)

__all__ = [
    "GeneratedCase", "create_case", "case_to_supabase_record",
    "CustomerProfile", "generate_customer",
    "InsurancePortfolio", "generate_insurance_portfolio",
    "CoverageAnalysis", "analyze_coverage", "EXCEL_COVERAGE_ROWS",
    "ProposalState", "generate_proposals",
    "build_coverage_analysis_xlsx", "workbook_payload", "suggested_filename",
    "FOCUSES", "MODE_POLICIES", "focus_policy", "mode_policy", "public_focus_catalog",
    "make_turn_evidence",
    "build_customer_disclosure_source", "build_customer_insurance_memory",
    "build_customer_model_context", "RetryDecision", "retry_decision",
    "CUSTOMER_RESPONSE_SCHEMA", "COACH_RESPONSE_SCHEMA",
    "EVALUATOR_RESPONSE_SCHEMA", "VOICE_BACKEND_DIRECTIVE_SCHEMA",
    "validate_contract",
    "build_customer_request", "build_coach_request",
    "build_evaluator_request", "build_live_session_spec",
    "ValidatedCustomerTurn", "validate_customer_turn", "apply_conversation_state",
    "MockAIAdapter", "AIAdapter", "PreAPIRuntime",
    "CustomerTurnResult", "CoachResult", "EvaluationResult",
    "assessment_snapshot_hash", "voice_directive_from_customer_turn",
    "pre_api_readiness",
]
