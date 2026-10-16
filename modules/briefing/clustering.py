from __future__ import annotations

from datetime import datetime
import hashlib
import re

from .models import SharedEventCandidate, SourceCandidate

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_STOP = {"관련", "대한", "오늘", "최근", "정부", "발표", "기준", "위해", "통해", "대한민국"}


def _tokens(title: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(title) if token.casefold() not in _STOP}


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _event_key(title: str, domain: str | None) -> str:
    base = "|".join(sorted(_tokens(title))) + "|" + (domain or "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def cluster_candidates(candidates: list[SourceCandidate], *, threshold: float = 0.72) -> list[SharedEventCandidate]:
    clusters: list[list[SourceCandidate]] = []
    for candidate in sorted(candidates, key=lambda row: row.published_at or row.retrieved_at or datetime.min, reverse=True):
        target = None
        for cluster in clusters:
            if _similarity(candidate.title, cluster[0].title) >= threshold:
                target = cluster
                break
        if target is None:
            clusters.append([candidate])
        else:
            target.append(candidate)

    events: list[SharedEventCandidate] = []
    for cluster in clusters:
        head = cluster[0]
        times = [row.published_at for row in cluster if row.published_at is not None]
        profiles: set[str] = set()
        for row in cluster:
            profiles.update(row.routed_profiles)
        events.append(SharedEventCandidate(
            event_key=_event_key(head.title, head.publisher_domain),
            canonical_title=head.title,
            candidates=cluster,
            routed_profiles=profiles,
            first_seen_at=min(times) if times else None,
            last_seen_at=max(times) if times else None,
            metadata={"cluster_method": "title_jaccard_v1", "candidate_count": len(cluster)},
        ))
    return events
