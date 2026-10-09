from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .clustering import cluster_candidates
from .config import DISCOVERY_LANES, SHARED_DISCOVERY_HARD_LIMIT
from .direct_sources import DirectSourceSpec, collect_direct_sources
from .discovery_budget import DiscoveryBudget, DiscoveryBudgetError
from .gates import passes_common_gate, route_profiles, insurance_routing_evidence
from .models import PhaseBResult, SourceCandidate
from .normalize import normalize_candidate
from .openai_discovery import OpenAIWebDiscoveryClient
from .publication import PublicationDateEnricher
from .source_policy import source_identity


class PhaseBBudgetError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def candidate_diagnostic(row: SourceCandidate) -> dict[str, Any]:
    return {"title": row.title[:300], "url": row.canonical_url or row.url,
            "description": row.description[:700], "source_name": row.source_name[:160],
            "collector_provider": row.collector_provider, "source_kind": row.source_kind,
            "source_code": row.source_code, "source_tier": row.source_tier,
            "lane_code": row.metadata.get("lane_code"),
            "profile_hint": row.metadata.get("profile_hint"),
            "profile_hints": row.metadata.get("profile_hints", []),
            "routed_profiles": sorted(row.routed_profiles),
            "insurance_routing": insurance_routing_evidence(row),
            "publication_status": row.metadata.get("publication_status"),
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "freshness_tier": row.freshness_tier}


def _hint(candidate: SourceCandidate) -> str | None:
    value = candidate.metadata.get("profile_hint")
    if value:
        return str(value)
    hints = candidate.metadata.get("profile_hints")
    if isinstance(hints, list) and len(hints) == 1:
        return str(hints[0])
    return None


def _dedupe(candidates: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    by_key: dict[str, SourceCandidate] = {}
    for row in candidates:
        key = row.canonical_url or row.url
        if key not in by_key:
            by_key[key] = row
            continue
        current = by_key[key]
        current.routed_profiles.update(row.routed_profiles)
        hints = set(current.metadata.get("profile_hints") or []) | set(row.metadata.get("profile_hints") or [])
        hints.update(str(c.metadata["profile_hint"]) for c in (current, row) if c.metadata.get("profile_hint"))
        current.metadata["profile_hints"] = sorted(hints)
        if not current.description and row.description:
            current.description = row.description
    return list(by_key.values())


def run_phase_b(
    *,
    as_of: datetime | None = None,
    direct_sources: Iterable[DirectSourceSpec] = (),
    discovery_client: OpenAIWebDiscoveryClient | None = None,
    enable_web_discovery: bool = True,
    date_enricher: PublicationDateEnricher | None = None,
    on_discovery_response: Callable[[dict[str, Any]], None] | None = None,
    profile_codes: tuple[str, ...] | None = None,
    previous_lanes: list | None = None,
    on_lane_complete: Callable | None = None,
    retry_missing_search: bool = True,
    supplement_only: bool = False,
    include_research: bool = True,
) -> PhaseBResult:
    as_of = as_of or datetime.now(timezone.utc)
    direct_sources = list(direct_sources)
    direct_details: dict[str, Any] = {}
    direct_candidates, direct_health = collect_direct_sources(direct_sources, diagnostics=direct_details)
    lanes = list(previous_lanes or [])
    web_candidates: list[SourceCandidate] = []
    budget = DiscoveryBudget(on_response=on_discovery_response)
    skipped_lanes: list[dict[str, str]] = []
    if enable_web_discovery:
        client = discovery_client or OpenAIWebDiscoveryClient()
        client.as_of = as_of
        try:
            # Finish all primary lanes before spending the two spare requests on
            # no-search retries. A retry may never silently crowd out later lanes.
            for lane in DISCOVERY_LANES:
                if lane.lane_code=="broker_research" and not include_research:
                    skipped_lanes.append({"lane_code":lane.lane_code,"reason":"optional_research_disabled"});continue
                if profile_codes is not None and lane.profile_code not in profile_codes:
                    continue
                if any(done.lane_code == lane.lane_code for done in lanes):
                    continue
                if supplement_only and lane.lane_code!='broker_research':
                    eligible=[]
                    for candidate in direct_candidates:
                        if not candidate.published_at or not candidate.title:continue
                        normalize_candidate(candidate,as_of=as_of)
                        ok,_=passes_common_gate(candidate)
                        hints=candidate.metadata.get('profile_hints') or []
                        routed=set().union(*(route_profiles(candidate,h) for h in hints)) if hints else route_profiles(candidate)
                        if ok and lane.profile_code in routed:eligible.append(candidate)
                    publishers={c.publisher_domain for c in eligible}
                    if len(eligible)>=12 and len(publishers)>=2:
                        skipped_lanes.append({'lane_code':lane.lane_code,'reason':'sufficient_publisher_feeds'})
                        continue
                if not budget.can_request():
                    skipped_lanes.append({"lane_code": lane.lane_code, "reason": "budget_exhausted"})
                    continue
                result = client.run_lane(lane, budget=budget, allow_retry=False)
                lanes.append(result)
                if on_lane_complete: on_lane_complete(lanes)
                if sum(item.usage.search_actions for item in lanes) > SHARED_DISCOVERY_HARD_LIMIT:
                    raise DiscoveryBudgetError("Shared Discovery hard limit exceeded; further calls stopped")
            for result in lanes if retry_missing_search else []:
                if result.search_performed:
                    continue
                if not budget.can_request():
                    skipped_lanes.append({"lane_code": result.lane_code, "reason": "retry_budget_exhausted"})
                    continue
                lane = next(l for l in DISCOVERY_LANES if l.lane_code == result.lane_code)
                extra = client.run_lane(lane, budget=budget, allow_retry=False, retry=True)
                for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens",
                              "web_tool_calls", "search_actions", "search_retry_count"):
                    setattr(result.usage, field, getattr(result.usage, field) + getattr(extra.usage, field))
                result.candidates.extend(extra.candidates)
                result.search_performed = extra.search_performed
                result.retry_used = True
                result.raw_response_id = extra.raw_response_id
                result.request_diagnostics.extend(extra.request_diagnostics)
                if sum(item.usage.search_actions for item in lanes) > SHARED_DISCOVERY_HARD_LIMIT:
                    raise DiscoveryBudgetError("Shared Discovery hard limit exceeded; further calls stopped")
        except Exception as exc:
            details = {"stage": "web_discovery", "discovery_budget": budget.snapshot(),
                       "raw_direct_candidates": len(direct_candidates), "direct_source_health": direct_health,
                       "direct_source_details": direct_details,
                       "completed_lanes": [l.lane_code for l in lanes], "skipped_lanes": skipped_lanes,
                       "partial_candidates": [candidate_diagnostic(c) for c in direct_candidates[:80]],
                       "candidate_sample_limit": 80}
            if isinstance(exc, DiscoveryBudgetError):
                raise PhaseBBudgetError(str(exc), details) from exc
            exc.diagnostics = details
            raise
        web_candidates = [c for lane in lanes for c in lane.candidates]

    excluded: dict[str, int] = {}
    accepted: list[SourceCandidate] = []
    enricher = date_enricher or PublicationDateEnricher()
    # Interleave lanes so one publisher/lane cannot exhaust the HTTP allowance.
    ordered_web = [row for i in range(max((len(l.candidates) for l in lanes), default=0)) for l in lanes if i < len(l.candidates) for row in [l.candidates[i]]]
    for candidate in [*direct_candidates, *ordered_web]:
        if candidate.collector_provider != "openai_web_search" or source_identity(candidate.url):
            enricher.enrich(candidate)
        normalize_candidate(candidate, as_of=as_of)
        ok, reason = passes_common_gate(candidate)
        if not ok:
            excluded[reason or "excluded"] = excluded.get(reason or "excluded", 0) + 1
            continue
        candidate.routed_profiles = route_profiles(candidate, _hint(candidate))
        for hint in candidate.metadata.get("profile_hints", []):
            candidate.routed_profiles.update(route_profiles(candidate, str(hint)))
        if not candidate.routed_profiles:
            excluded["out_of_scope"] = excluded.get("out_of_scope", 0) + 1
            continue
        accepted.append(candidate)

    lane_health = []
    for lane in lanes:
        usable = [c for c in accepted if c.metadata.get("lane_code") == lane.lane_code and lane.profile_code in c.routed_profiles]
        lane_health.append({"lane_code": lane.lane_code, "profile_code": lane.profile_code,
                            "search_performed": lane.search_performed, "raw_candidates": len(lane.candidates),
                            "usable_candidates": len(usable), "search_actions": lane.usage.search_actions})
    health = {s.source_code: {**direct_details.get(s.source_code, {}), "status": direct_health.get(s.source_code, "failed"), "profiles": list(s.profile_hints),
                             "source_kind": s.source_kind, "usable_candidates": sum(c.source_code == s.source_code for c in accepted)} for s in direct_sources}
    accepted = _dedupe(accepted)
    events = cluster_candidates(accepted)
    excluded.update({f"direct_health:{key}:{value}": 1 for key, value in direct_health.items() if value != "ok"})
    return PhaseBResult(as_of=as_of, candidates=accepted, events=events, discovery_lanes=lanes, excluded_counts=excluded,
                        source_health=health, diagnostics={"raw_direct_candidates": len(direct_candidates), "raw_web_candidates": len(web_candidates),
                        "publication": dict(enricher.stats), "lanes": lane_health,
                        "discovery_budget": budget.snapshot(), "skipped_lanes": skipped_lanes,
                        "candidate_sample": [candidate_diagnostic(c) for c in [*ordered_web, *direct_candidates][:80]],
                        "candidate_sample_limit": 80})
