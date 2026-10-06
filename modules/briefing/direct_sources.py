from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from typing import Iterable
from xml.etree import ElementTree as ET

import requests

from .models import SourceCandidate
from .normalize import is_safe_url
from .publication import parse_publication_date


@dataclass(frozen=True, slots=True)
class DirectSourceSpec:
    source_code: str
    source_name: str
    url: str
    source_kind: str = "official"
    source_family_code: str | None = None
    source_tier: str | None = None
    profile_hints: tuple[str, ...] = ()
    timeout_seconds: float = 10.0


def load_direct_source_specs_from_env() -> list[DirectSourceSpec]:
    """Load verified Direct Source endpoints without hard-coding unstable URLs.

    BRIEFING_DIRECT_SOURCES_JSON must be a JSON array. Endpoint URLs are intentionally
    deployment configuration because the uploaded SPEC defines source families but does
    not contain verified feed URLs.
    """
    raw = os.getenv("BRIEFING_DIRECT_SOURCES_JSON", "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("BRIEFING_DIRECT_SOURCES_JSON must be a JSON array")
    specs: list[DirectSourceSpec] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        specs.append(
            DirectSourceSpec(
                source_code=str(item["source_code"]),
                source_name=str(item["source_name"]),
                url=str(item["url"]),
                source_kind=str(item.get("source_kind") or "official"),
                source_family_code=str(item.get("source_family_code") or "") or None,
                source_tier=str(item.get("source_tier") or "") or None,
                profile_hints=tuple(str(v) for v in (item.get("profile_hints") or [])),
                timeout_seconds=float(item.get("timeout_seconds") or 10.0),
            )
        )
    return specs


def _text(node: ET.Element | None, *names: str) -> str:
    if node is None:
        return ""
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _parse_dt(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _rss_candidates(root: ET.Element, spec: DirectSourceSpec, retrieved_at: datetime) -> list[SourceCandidate]:
    rows: list[SourceCandidate] = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link", "guid")
        description = _text(item, "description")
        published = parse_publication_date(_text(item, "pubDate", "published"), url=link)
        if title and link:
            rows.append(SourceCandidate(
                title=title, url=link, description=description, published_at=published,
                retrieved_at=retrieved_at, source_name=spec.source_name,
                collector_provider="direct_rss", source_kind=spec.source_kind,
                source_code=spec.source_code, source_family_code=spec.source_family_code,
                source_tier=spec.source_tier, endpoint_role="primary",
                metadata={"profile_hints": list(spec.profile_hints)},
            ))
    return rows


def _atom_candidates(root: ET.Element, spec: DirectSourceSpec, retrieved_at: datetime) -> list[SourceCandidate]:
    rows: list[SourceCandidate] = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", ns):
        title = _text(entry, "{http://www.w3.org/2005/Atom}title")
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_node.get("href") if link_node is not None else "") or ""
        description = _text(entry, "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content")
        published = parse_publication_date(_text(entry, "{http://www.w3.org/2005/Atom}published"), url=link)
        if title and link:
            rows.append(SourceCandidate(
                title=title, url=link, description=description, published_at=published,
                retrieved_at=retrieved_at, source_name=spec.source_name,
                collector_provider="direct_atom", source_kind=spec.source_kind,
                source_code=spec.source_code, source_family_code=spec.source_family_code,
                source_tier=spec.source_tier, endpoint_role="primary",
                metadata={"profile_hints": list(spec.profile_hints)},
            ))
    return rows


def collect_direct_source(spec: DirectSourceSpec, *, session: requests.Session | None = None) -> list[SourceCandidate]:
    if not is_safe_url(spec.url):
        raise ValueError("Invalid Direct Source URL")
    http = session or requests.Session()
    response = http.get(spec.url, timeout=spec.timeout_seconds, headers={"User-Agent": "HWARANG-Briefing/1.6"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    retrieved_at = datetime.now(timezone.utc)
    rows = _rss_candidates(root, spec, retrieved_at)
    if rows:
        return rows
    return _atom_candidates(root, spec, retrieved_at)


def collect_direct_sources(specs: Iterable[DirectSourceSpec]) -> tuple[list[SourceCandidate], dict[str, str]]:
    candidates: list[SourceCandidate] = []
    status: dict[str, str] = {}
    session = requests.Session()
    for spec in specs:
        try:
            rows = collect_direct_source(spec, session=session)
            candidates.extend(rows)
            status[spec.source_code] = "ok" if rows else "empty_valid"
        except (requests.RequestException, ET.ParseError, ValueError):
            status[spec.source_code] = "failed"
    return candidates, status
