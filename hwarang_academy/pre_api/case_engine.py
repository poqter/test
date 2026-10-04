"""Pre-API Case factory: customer + insurance + analysis + proposal, one source of truth."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any

from .constants import (
    CASE_ENGINE_VERSION, CUSTOMER_GENERATOR_VERSION, INSURANCE_GENERATOR_VERSION,
    COVERAGE_MAPPING_VERSION, COVERAGE_ANALYSIS_VERSION, EXCEL_TEMPLATE_VERSION,
    PROPOSAL_GENERATOR_VERSION, INTERACTION_MODES, CONSULTATION_DIFFICULTIES,
)
from .customer import generate_customer
from .insurance import generate_insurance_portfolio
from .coverage import analyze_coverage
from .proposal import generate_proposals
from .training import focus_policy, mode_policy, validate_training_focus, validate_training_mode


@dataclass(frozen=True)
class GeneratedCase:
    schema_version: str
    seed: int
    stage: str
    training_mode: str
    training_focus: str
    consultation_difficulty: str
    interaction_mode: str
    customer_state: dict[str, Any]
    public_state: dict[str, Any]
    insurance_state: dict[str, Any]
    coverage_analysis: dict[str, Any]
    proposal_state: dict[str, Any]
    journey_state: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        raw = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()


def create_case(
    seed: int,
    *,
    stage: str = "TA",
    training_mode: str = "GUIDE",
    training_focus: str = "comprehensive",
    consultation_difficulty: str = "standard",
    interaction_mode: str = "TEXT",
    insurance_known: bool = False,
    forced_archetype: str | None = None,
) -> GeneratedCase:
    mode = validate_training_mode(training_mode)
    focus = validate_training_focus(training_focus)
    difficulty = str(consultation_difficulty or "standard").lower()
    if difficulty not in CONSULTATION_DIFFICULTIES:
        raise ValueError(f"unsupported consultation difficulty: {difficulty}")
    interaction = str(interaction_mode or "TEXT").upper()
    if interaction not in INTERACTION_MODES:
        raise ValueError(f"unsupported interaction mode: {interaction}")

    customer_obj = generate_customer(int(seed), training_focus=focus, difficulty=difficulty)
    customer = customer_obj.to_dict()
    insurance_obj = generate_insurance_portfolio(int(seed), customer, forced_archetype=forced_archetype)
    insurance = insurance_obj.to_dict()
    analysis_obj = analyze_coverage(customer, insurance)
    analysis = analysis_obj.to_dict()
    proposal_obj = generate_proposals(int(seed), customer, insurance, analysis)
    proposals = proposal_obj.to_dict()

    # Customer belief is intentionally not identical to actual insurance data.
    knowledge = int(customer.get("customer_beliefs", {}).get("insurance_knowledge_level", 1))
    actual_premium = int(insurance.get("total_monthly_premium_won") or 0)
    if knowledge >= 3:
        premium_belief = actual_premium
    elif knowledge == 2:
        premium_belief = round(actual_premium / 10000) * 10000
    else:
        premium_belief = None
    customer["customer_beliefs"]["known_monthly_premium_won"] = premium_belief
    customer["customer_beliefs"]["known_contract_count"] = len(insurance.get("contracts", [])) if knowledge >= 3 else None

    public_state = dict(customer_obj.public_state)
    public_state["insurance_information_known_at_start"] = bool(insurance_known)
    if insurance_known:
        public_state["insurance_contract_count"] = len(insurance.get("contracts", []))
        public_state["coverage_excel_available"] = True
    else:
        public_state["coverage_excel_available"] = False

    return GeneratedCase(
        schema_version=CASE_ENGINE_VERSION,
        seed=int(seed),
        stage=str(stage or "TA").upper(),
        training_mode=mode,
        training_focus=focus,
        consultation_difficulty=difficulty,
        interaction_mode=interaction,
        customer_state=customer,
        public_state=public_state,
        insurance_state=insurance,
        coverage_analysis=analysis,
        proposal_state=proposals,
        journey_state={
            "current_stage": str(stage or "TA").upper(),
            "sessions": [],
            "known_information": {},
            "agreements": {},
            "next_action": None,
        },
        metadata={
            "versions": {
                "case_engine": CASE_ENGINE_VERSION,
                "customer_generator": CUSTOMER_GENERATOR_VERSION,
                "insurance_generator": INSURANCE_GENERATOR_VERSION,
                "coverage_mapping": COVERAGE_MAPPING_VERSION,
                "coverage_analysis": COVERAGE_ANALYSIS_VERSION,
                "excel_template": EXCEL_TEMPLATE_VERSION,
                "proposal_generator": PROPOSAL_GENERATOR_VERSION,
                "prompt_version": None,
                "model_version": None,
                "evaluation_framework_version": None,
            },
            "training_mode_policy": mode_policy(mode),
            "training_focus_policy": focus_policy(focus),
            "voice_ready": True,
            "synthetic_training_data": True,
        },
    )


def case_to_supabase_record(case: GeneratedCase, *, owner_user_id: str, title: str | None = None) -> dict[str, Any]:
    d = case.to_dict()
    return {
        "owner_user_id": owner_user_id,
        "status": "active",
        "current_stage": case.stage,
        "title": title or f"{case.customer_state['alias']} · {case.stage}",
        "customer_alias": case.customer_state["alias"],
        "customer_seed": case.seed,
        "customer_state": case.customer_state,
        "public_state": case.public_state,
        "insurance_state": case.insurance_state,
        "journey_state": case.journey_state,
        "coverage_analysis": case.coverage_analysis,
        "proposal_state": case.proposal_state,
        "customer_generator_version": case.metadata["versions"]["customer_generator"],
        "insurance_generator_version": case.metadata["versions"]["insurance_generator"],
        "coverage_mapping_version": case.metadata["versions"]["coverage_mapping"],
        "excel_template_version": case.metadata["versions"]["excel_template"],
        "proposal_generator_version": case.metadata["versions"]["proposal_generator"],
        "metadata": case.metadata,
    }
