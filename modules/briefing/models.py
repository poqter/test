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
