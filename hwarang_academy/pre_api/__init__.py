"""HWARANG ACADEMY pre-API simulator core.

This package contains deterministic customer/insurance/analysis/proposal logic.
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

__all__ = [
    "GeneratedCase", "create_case", "case_to_supabase_record",
    "CustomerProfile", "generate_customer",
    "InsurancePortfolio", "generate_insurance_portfolio",
    "CoverageAnalysis", "analyze_coverage", "EXCEL_COVERAGE_ROWS",
    "ProposalState", "generate_proposals",
    "build_coverage_analysis_xlsx", "workbook_payload", "suggested_filename",
    "FOCUSES", "MODE_POLICIES", "focus_policy", "mode_policy", "public_focus_catalog",
    "make_turn_evidence",
]
