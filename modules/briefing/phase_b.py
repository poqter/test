from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .clustering import cluster_candidates
from .config import DISCOVERY_LANES, SHARED_DISCOVERY_HARD_LIMIT
from .direct_sources import DirectSourceSpec, collect_direct_sources
from .gates import passes_common_gate, route_profiles
from .models import PhaseBResult, SourceCandidate
from .normalize import normalize_candidate
from .openai_discovery import OpenAIWebDiscoveryClient
from .publication import PublicationDateEnricher
from .source_policy import source_identity


class PhaseBBudgetError(RuntimeError):
    pass


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
) -> PhaseBResult:
    as_of = as_of or datetime.now(timezone.utc)
    direct_sources = list(direct_sources)
    direct_candidates, direct_health = collect_direct_sources(direct_sources)
    lanes = []
    web_candidates: list[SourceCandidate] = []
    if enable_web_discovery:
        client = discovery_client or OpenAIWebDiscoveryClient()
        client.as_of = as_of
        for lane in DISCOVERY_LANES:
            result = client.run_lane(lane)
            lanes.append(result)
            web_candidates.extend(result.candidates)
        if sum(item.usage.search_actions for item in lanes) > SHARED_DISCOVERY_HARD_LIMIT:
            raise PhaseBBudgetError("Shared Discovery hard limit exceeded")

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
    health = {s.source_code: {"status": direct_health.get(s.source_code, "failed"), "profiles": list(s.profile_hints),
                             "source_kind": s.source_kind, "usable_candidates": sum(c.source_code == s.source_code for c in accepted)} for s in direct_sources}
    accepted = _dedupe(accepted)
    events = cluster_candidates(accepted)
    excluded.update({f"direct_health:{key}:{value}": 1 for key, value in direct_health.items() if value != "ok"})
    return PhaseBResult(as_of=as_of, candidates=accepted, events=events, discovery_lanes=lanes, excluded_counts=excluded,
                        source_health=health, diagnostics={"raw_direct_candidates": len(direct_candidates), "raw_web_candidates": len(web_candidates),
                        "publication": dict(enricher.stats), "lanes": lane_health,
                        "candidate_sample": [{"title": c.title[:300], "url": c.canonical_url or c.url, "lane_code": c.metadata.get("lane_code"),
                            "source_kind": c.source_kind, "publication_status": c.metadata.get("publication_status"),
                            "published_at": c.published_at.isoformat() if c.published_at else None,
                            "freshness_tier": c.freshness_tier} for c in [*ordered_web, *direct_candidates][:16]]})
