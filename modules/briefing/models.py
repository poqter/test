from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

FreshnessTier = Literal["core_window", "light_window", "stale", "undated"]
ProfileCode = Literal["INSURANCE", "MARKET", "NEWS"]


@dataclass(slots=True)
class SourceCandidate:
    title: str
    url: str
    source_name: str
    collector_provider: str
    source_kind: str
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    publisher_name: str | None = None
    publisher_domain: str | None = None
    source_code: str | None = None
    source_family_code: str | None = None
    source_tier: str | None = None
    endpoint_role: str | None = None
    description: str = ""
    canonical_url: str | None = None
    content_fingerprint: str | None = None
    freshness_tier: FreshnessTier = "undated"
    routed_profiles: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryUsage:
    model_name: str | None = None
    service_tier: str | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    web_tool_calls: int = 0
    search_actions: int = 0
    search_retry_count: int = 0
    verification_search_actions: int = 0


@dataclass(slots=True)
class DiscoveryLaneResult:
    lane_code: str
    profile_code: str
    candidates: list[SourceCandidate]
    usage: DiscoveryUsage
    search_performed: bool
    retry_used: bool = False
    raw_response_id: str | None = None


@dataclass(slots=True)
class SharedEventCandidate:
    event_key: str
    canonical_title: str
    candidates: list[SourceCandidate]
    routed_profiles: set[str]
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PhaseBResult:
    as_of: datetime
    candidates: list[SourceCandidate]
    events: list[SharedEventCandidate]
    discovery_lanes: list[DiscoveryLaneResult]
    excluded_counts: dict[str, int]
    source_health: dict[str, dict[str, Any]] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisUsage:
    model_name: str | None = None
    service_tier: str | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass(slots=True)
class ProfileEventAnalysis:
    event_key: str
    profile_code: str
    importance_score: float
    selection_tier: str
    evidence_status: str
    validation_status: str
    category: str
    issue_status: str
    title: str
    summary: str
    why_important: str
    impact_summary: str
    action_state: str
    communication_state: str
    audience_segments: list[str] = field(default_factory=list)
    conversation_payload: dict[str, Any] = field(default_factory=dict)
    workspace_actions: list[dict[str, Any]] = field(default_factory=list)
    profile_payload: dict[str, Any] = field(default_factory=dict)
    escalation_required: bool = False


@dataclass(slots=True)
class PhaseCResult:
    analyses: list[ProfileEventAnalysis]
    usage_by_profile: dict[str, AnalysisUsage]
    omitted_by_profile: dict[str, int]
    eligible_analyses: list[ProfileEventAnalysis] = field(default_factory=list)

    def profile_rows(self, profile_code: str) -> list[ProfileEventAnalysis]:
        return [row for row in self.analyses if row.profile_code == profile_code]
