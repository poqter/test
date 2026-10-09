from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Callable, Protocol

from .evidence import infer_evidence_status, is_high_risk
from .models import AnalysisUsage, PhaseBResult, PhaseCResult, ProfileEventAnalysis, SharedEventCandidate
from .openai_analysis import OpenAIAnalysisClient
from .profile_rules import PROFILE_RULES, light_digest_limit
from .tool_policy import validated_tool_actions


class Analyzer(Protocol):
    def analyze(self, profile_code: str, events: list[SharedEventCandidate]) -> tuple[list[dict], AnalysisUsage]: ...


def _freshness_allows_core(event: SharedEventCandidate) -> bool:
    return any(row.freshness_tier == "core_window" for row in event.candidates)


def _selection_for(score: float, event: SharedEventCandidate, profile_code: str, evidence_status: str) -> str:
    rule = PROFILE_RULES[profile_code]
    if evidence_status == "conflicted":
        return "excluded"
    if score >= rule.core_threshold and _freshness_allows_core(event):
        return "core"
    if rule.light_floor <= score <= rule.light_ceiling or (score >= rule.core_threshold and not _freshness_allows_core(event)):
        return "light_digest"
    return "excluded"


def _apply_caps(rows: list[ProfileEventAnalysis], profile_code: str) -> None:
    rule = PROFILE_RULES[profile_code]
    core = sorted((x for x in rows if x.selection_tier == "core"), key=lambda x: x.importance_score, reverse=True)
    for row in core[rule.max_core:]:
        row.profile_payload["original_selection_tier"] = "core"
        row.selection_tier = "light_digest" if row.importance_score >= rule.light_floor else "excluded"

    core_count = sum(1 for x in rows if x.selection_tier == "core")
    light_limit = light_digest_limit(core_count, profile_code)
    light = sorted((x for x in rows if x.selection_tier == "light_digest"), key=lambda x: x.importance_score, reverse=True)
    for row in light[light_limit:]:
        row.selection_tier = "excluded"


def run_phase_c(
    phase_b: PhaseBResult,
    *,
    analyzer: Analyzer | None = None,
    max_events_per_profile: int = 20,
    profile_codes: tuple[str, ...] | None = None,
    on_analysis_response: Callable[[dict[str, Any]], None] | None = None,
) -> PhaseCResult:
    client = analyzer or OpenAIAnalysisClient(on_response=on_analysis_response)
    by_profile: dict[str, list[SharedEventCandidate]] = defaultdict(list)
    for event in phase_b.events:
        for profile_code in sorted(event.routed_profiles):
            if any(c.metadata.get("lane_code") == "broker_research" for c in event.candidates):
                continue
            if profile_code in PROFILE_RULES and (profile_codes is None or profile_code in profile_codes):
                by_profile[profile_code].append(event)

    analyses: list[ProfileEventAnalysis] = []
    usage_by_profile: dict[str, AnalysisUsage] = {}
    omitted_by_profile: dict[str, int] = {}

    for profile_code, events in sorted(by_profile.items()):
        prioritized = sorted(
            events,
            key=lambda e: (
                0 if any(row.freshness_tier == "core_window" for row in e.candidates) else 1,
                -(e.last_seen_at.timestamp() if e.last_seen_at else 0),
            ),
        )
        selected_events = prioritized[:max_events_per_profile]
        omitted_by_profile[profile_code] = max(0, len(prioritized) - len(selected_events))
        raw_rows, usage = client.analyze(profile_code, selected_events)
        usage_by_profile[profile_code] = usage
        raw_by_key = {str(row.get("event_key") or ""): row for row in raw_rows}

        for event in selected_events:
            raw = raw_by_key.get(event.event_key, {})
            score = max(0.0, min(100.0, float(raw.get("importance_score") or 0)))
            evidence_status = infer_evidence_status(event)
            high_risk = is_high_risk(event, profile_code)
            confidence = str(raw.get("confidence") or "low")
            validation_status = "ok"
            if high_risk and evidence_status not in {"official_confirmed", "multi_source_confirmed"}:
                validation_status = "required"
            if confidence == "low" and score >= PROFILE_RULES[profile_code].core_threshold:
                validation_status = "required"

            selection_tier = _selection_for(score, event, profile_code, evidence_status)
            if validation_status != "ok":
                selection_tier = "excluded"

            analyses.append(ProfileEventAnalysis(
                event_key=event.event_key,
                profile_code=profile_code,
                importance_score=score,
                selection_tier=selection_tier,
                evidence_status=evidence_status,
                validation_status=validation_status,
                category=str(raw.get("category") or ""),
                issue_status=str(raw.get("issue_status") or ""),
                title=str(raw.get("title") or event.canonical_title),
                summary=str(raw.get("summary") or ""),
                why_important=str(raw.get("why_important") or ""),
                impact_summary=str(raw.get("impact_summary") or ""),
                action_state=str(raw.get("action_state") or "watch"),
                communication_state=str(raw.get("communication_state") or "internal_check"),
                audience_segments=[str(x) for x in (raw.get("audience_segments") or [])],
                conversation_payload={
                    "recommended_expression": str(raw.get("recommended_expression") or ""),
                    "check_first": str(raw.get("check_first") or ""),
                    "avoid_expression": str(raw.get("avoid_expression") or ""),
                },
                workspace_actions=validated_tool_actions(raw.get("workspace_tool_codes")),
                profile_payload={"next_step": str(raw.get("next_step") or ""), "confidence": confidence},
                escalation_required=(high_risk and validation_status != "ok") or confidence == "low",
            ))

    eligible = deepcopy([r for r in analyses if r.selection_tier in {"core", "light_digest"} and r.validation_status == "ok"])
    for profile_code in PROFILE_RULES:
        _apply_caps([x for x in analyses if x.profile_code == profile_code], profile_code)

    return PhaseCResult(
        analyses=analyses,
        usage_by_profile=usage_by_profile,
        omitted_by_profile=omitted_by_profile,
        eligible_analyses=eligible,
    )
