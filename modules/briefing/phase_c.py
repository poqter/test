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


def _balanced_events(events: list[SharedEventCandidate]) -> list[SharedEventCandidate]:
    """Balance sections within each publisher, then publishers within the batch."""
    from .normalize import publisher_domain
    publishers = {}
    for event in events:
        source = next((c for c in event.candidates if c.source_kind == 'news'), None)
        host = publisher_domain(source.url) if source else 'official'
        section = (source.source_code or source.metadata.get('lane_code') or host) if source else 'official'
        publishers.setdefault(host, {}).setdefault(section, []).append(event)
    pools = []
    for sections in publishers.values():
        groups = list(sections.values())
        pools.append([group[i] for i in range(max(map(len, groups), default=0))
                      for group in groups if i < len(group)])
    return [pool[i] for i in range(max(map(len, pools), default=0))
            for pool in pools if i < len(pool)]


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
    """One quality floor for both lists; importance decides position, not truth."""
    rule = PROFILE_RULES[profile_code]
    eligible = sorted((r for r in rows if r.selection_tier != 'excluded'),
                      key=lambda r: (-r.importance_score, r.event_key))
    # Resolve duplicate chains/cycles to one strongest verified story.
    parent={r.event_key:r.event_key for r in eligible}
    def root(key):
        while parent[key]!=key:
            parent[key]=parent[parent[key]];key=parent[key]
        return key
    for r in eligible:
        other=r.profile_payload.get('duplicate_of')
        if other in parent:parent[root(other)]=root(r.event_key)
    winners={}
    for r in eligible:winners.setdefault(root(r.event_key),r.event_key)
    earnings = 0
    ranked = []
    for row in eligible:
        kind = row.profile_payload.get('editorial_kind')
        reason = None
        if winners[root(row.event_key)] != row.event_key:
            reason = 'same_event_duplicate'
        if row.profile_payload.get('is_new_development') is False:
            reason = 'unchanged_prior_day'
        if kind in {'promotion', 'opinion', 'weather'}:
            reason = 'not_main_news'  # weather requires a separate verified forecast block
        if profile_code == 'INSURANCE' and kind == 'earnings':
            earnings += 1
            if earnings > 1: reason = 'earnings_daily_cap'
        if reason:
            row.selection_tier = 'excluded'
            row.profile_payload['selection_decision'] = reason
        else:
            ranked.append(row)
    for index, row in enumerate(ranked):
        row.selection_tier = ('core' if index < rule.max_core else
                              'light_digest' if index < rule.max_core + 3 else 'excluded')
        row.profile_payload['selection_decision'] = (
            'main' if row.selection_tier == 'core' else
            'more' if row.selection_tier == 'light_digest' else 'capacity')


def run_phase_c(
    phase_b: PhaseBResult,
    *,
    analyzer: Analyzer | None = None,
    max_events_per_profile: int = 30,
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
        # Round-robin by publisher before analysis so a busy single feed cannot
        # occupy the entire paid input pool. Importance is still scored by facts.
        balanced = _balanced_events(prioritized)
        selected_events = balanced[:max_events_per_profile]
        omitted_by_profile[profile_code] = max(0, len(prioritized) - len(selected_events))
        raw_rows, usage = client.analyze(profile_code, selected_events)
        usage_by_profile[profile_code] = usage
        raw_by_key = {str(row.get("event_key") or ""): row for row in raw_rows}
        omitted_by_profile[profile_code] += sum(e.event_key not in raw_by_key for e in selected_events)

        for event in selected_events:
            raw = raw_by_key.get(event.event_key, {})
            score = max(0.0, min(100.0, float(raw.get("importance_score") or 0)))
            evidence_status = infer_evidence_status(event)
            high_risk = is_high_risk(event, profile_code)
            confidence = str(raw.get("confidence") or "low")
            validation_status = "ok"
            if high_risk and evidence_status not in {"official_confirmed", "multi_source_confirmed"}:
                validation_status = "required"
            if confidence == "low":
                validation_status = "required"

            selection_tier = _selection_for(score, event, profile_code, evidence_status)
            source_texts=[c.description.strip() for c in event.candidates]
            if (raw.get("essential_facts_complete") is False or not raw.get("summary")
                    or raw.get("essential_facts_complete") is True and not any(len(t)>40 for t in source_texts)) :
                validation_status = "required"
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
                profile_payload={"next_step": str(raw.get("next_step") or ""), "confidence": confidence,
                                 "analysis_missing": event.event_key not in raw_by_key,
                                 **{k: raw.get(k) for k in ('essential_facts_complete','headline_sufficient','editorial_kind','event_date','selection_reason','duplicate_of','is_new_development','scheduled_at')},
                                 "selection_decision": "quality_hold" if validation_status != "ok" else "below_importance_floor"},
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
