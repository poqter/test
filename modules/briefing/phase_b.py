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
) -> PhaseBResult:
    as_of = as_of or datetime.now(timezone.utc)
    direct_candidates, direct_health = collect_direct_sources(direct_sources)
    lanes = []
    web_candidates: list[SourceCandidate] = []
    if enable_web_discovery:
        client = discovery_client or OpenAIWebDiscoveryClient()
        for lane in DISCOVERY_LANES:
            result = client.run_lane(lane)
            lanes.append(result)
            web_candidates.extend(result.candidates)
        if sum(item.usage.search_actions for item in lanes) > SHARED_DISCOVERY_HARD_LIMIT:
            raise PhaseBBudgetError("Shared Discovery hard limit exceeded")

    excluded: dict[str, int] = {}
    accepted: list[SourceCandidate] = []
    for candidate in [*direct_candidates, *web_candidates]:
        normalize_candidate(candidate, as_of=as_of)
        ok, reason = passes_common_gate(candidate)
        if not ok:
            excluded[reason or "excluded"] = excluded.get(reason or "excluded", 0) + 1
            continue
        candidate.routed_profiles = route_profiles(candidate, _hint(candidate))
        if not candidate.routed_profiles:
            excluded["out_of_scope"] = excluded.get("out_of_scope", 0) + 1
            continue
        accepted.append(candidate)

    accepted = _dedupe(accepted)
    events = cluster_candidates(accepted)
    excluded.update({f"direct_health:{key}:{value}": 1 for key, value in direct_health.items() if value != "ok"})
    return PhaseBResult(as_of=as_of, candidates=accepted, events=events, discovery_lanes=lanes, excluded_counts=excluded)
