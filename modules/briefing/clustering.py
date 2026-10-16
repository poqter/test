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


def _macro_release(title):
    """Group the same explicitly dated CPI release, never just the same topic."""
    text=title.casefold()
    if not re.search(r'cpi|소비자물가',text):return None
    country=next((label for label,pattern in [('US',r'미국|美|\bus\b|\bu\.s\.'),('KR',r'한국|국내|韓'),('CN',r'중국|中') ] if re.search(pattern,text)),None)
    month=re.search(r'(?<!\d)(1[0-2]|[1-9])월',text)
    year=re.search(r'20\d{2}년',text)
    if not country or not month:return None
    # Outlooks and core CPI remain separate from actual headline release.
    if re.search(r'전망|예상|발표 앞|발표 전|근원|core',text):return None
    return country,year.group() if year else '',month.group(1)


def _same_release(left, right):
    a,b=_macro_release(left.title),_macro_release(right.title)
    if not a or a!=b:return False
    la,lb=left.published_at,right.published_at
    return bool(la and lb and abs((la-lb).total_seconds())<=48*3600)

def cluster_candidates(candidates: list[SourceCandidate], *, threshold: float = 0.72) -> list[SharedEventCandidate]:
    clusters: list[list[SourceCandidate]] = []
    for candidate in sorted(candidates, key=lambda row: row.published_at or row.retrieved_at or datetime.min, reverse=True):
        target = None
        for cluster in clusters:
            if _same_release(candidate, cluster[0]) or _similarity(candidate.title, cluster[0].title) >= threshold:
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
            metadata={"cluster_method": "title_jaccard_dated_cpi_v2", "candidate_count": len(cluster)},
        ))
    return events
