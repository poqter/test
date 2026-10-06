from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import requests

from .models import SourceCandidate
from .normalize import is_safe_url, visible_text, publisher_domain, classify_freshness
from .publication import parse_publication_date, _public_destination
from .fsc_board import supports_feed, collect_board

MAX_FEED_BYTES = 2_000_000


def diagnostic_endpoint(url: str) -> str | None:
    if not is_safe_url(url):
        return None
    parts = urlsplit(url)
    public_keys = {"fid", "bid", "id", "boardid", "board_id", "mode", "rss", "category", "cat", "ctxcd", "bbsid", "nttid"}
    query = [(key, value if key.casefold() in public_keys else "REDACTED")
             for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


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
    """Keep configured sources and supplement NEWS with one official RSS endpoint.

    The publisher lists the headline endpoint at https://www.mk.co.kr/rss
    (checked 2026-10-06). Disable with BRIEFING_NEWS_RSS_SUPPLEMENT=0.
    Empty/missing source configuration remains empty; deployment checks are preserved.
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
    if specs and os.getenv("BRIEFING_NEWS_RSS_SUPPLEMENT", "1").strip().casefold() not in {"0", "false", "off"}:
        endpoint = "https://www.mk.co.kr/rss/30000001/"
        duplicate = any(s.source_code == "news_mk_headlines" or
                        (publisher_domain(s.url) == "mk.co.kr" and urlsplit(s.url).path.rstrip("/") == "/rss/30000001")
                        for s in specs)
        if not duplicate:
            specs.append(DirectSourceSpec("news_mk_headlines", "매일경제 헤드라인", endpoint,
                                          source_kind="news", source_tier="C", profile_hints=("NEWS",), timeout_seconds=6))
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
        description = visible_text(_text(item, "description"))
        published = parse_publication_date(_text(item, "pubDate", "published"), url=link)
        if title and link:
            rows.append(SourceCandidate(
                title=title, url=link, description=description, published_at=published,
                retrieved_at=retrieved_at, source_name=spec.source_name,
                collector_provider="direct_rss", source_kind=spec.source_kind,
                source_code=spec.source_code, source_family_code=spec.source_family_code,
                source_tier=spec.source_tier, endpoint_role="primary",
                metadata={"profile_hints": list(spec.profile_hints), "insurance_requires_topic": supports_feed(spec.url)},
            ))
    return rows


def _atom_candidates(root: ET.Element, spec: DirectSourceSpec, retrieved_at: datetime) -> list[SourceCandidate]:
    rows: list[SourceCandidate] = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", ns):
        title = _text(entry, "{http://www.w3.org/2005/Atom}title")
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_node.get("href") if link_node is not None else "") or ""
        description = visible_text(_text(entry, "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"))
        published = parse_publication_date(_text(entry, "{http://www.w3.org/2005/Atom}published"), url=link)
        if title and link:
            rows.append(SourceCandidate(
                title=title, url=link, description=description, published_at=published,
                retrieved_at=retrieved_at, source_name=spec.source_name,
                collector_provider="direct_atom", source_kind=spec.source_kind,
                source_code=spec.source_code, source_family_code=spec.source_family_code,
                source_tier=spec.source_tier, endpoint_role="primary",
                metadata={"profile_hints": list(spec.profile_hints), "insurance_requires_topic": supports_feed(spec.url)},
            ))
    return rows


def collect_direct_source(spec: DirectSourceSpec, *, session: requests.Session | None = None,
                          diagnostics: dict[str, Any] | None = None,
                          destination_check=_public_destination) -> list[SourceCandidate]:
    detail = diagnostics if diagnostics is not None else {}
    detail.update({"configured_endpoint": diagnostic_endpoint(spec.url), "http_requests": 0})
    if not is_safe_url(spec.url):
        raise ValueError("invalid_url")
    http = session or requests.Session()
    http.trust_env = False
    url = spec.url
    original_host = publisher_domain(url)
    for redirect in range(3):
        if not destination_check(url):
            raise ValueError("unsafe_destination")
        if publisher_domain(url) != original_host:
            raise ValueError("cross_publisher_redirect")
        detail["http_requests"] += 1
        response = http.get(url, timeout=min(10.0, max(1.0, spec.timeout_seconds)),
                            headers={"User-Agent": "HWARANG-Briefing/1.7-stage1"},
                            stream=True, allow_redirects=False)
        with response:
            detail.update({"http_status": response.status_code,
                           "final_endpoint": diagnostic_endpoint(url),
                           "content_type": response.headers.get("Content-Type", "")[:100],
                           "redirect_count": redirect})
            if response.status_code in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > MAX_FEED_BYTES:
                    raise ValueError("feed_too_large")
            detail["response_bytes"] = len(body)
            # RSS and Atom do not need DTDs. Reject external-entity declarations.
            if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
                raise ValueError("unsupported_xml_declaration")
            root = ET.fromstring(body)
            if root.tag.split("}")[-1].casefold() not in {"rss", "rdf", "feed"}:
                raise ValueError("not_rss_or_atom")
            detail["feed_format"] = root.tag.split("}")[-1]
            break
    else:
        raise ValueError("redirect_limit")
    retrieved_at = datetime.now(timezone.utc)
    rows = _rss_candidates(root, spec, retrieved_at)
    if rows:
        return rows
    return _atom_candidates(root, spec, retrieved_at)


def collect_direct_sources(specs: Iterable[DirectSourceSpec], *, diagnostics: dict[str, Any] | None = None,
                           session=None, destination_check=_public_destination,
                           as_of: datetime | None = None) -> tuple[list[SourceCandidate], dict[str, str]]:
    candidates: list[SourceCandidate] = []
    status: dict[str, str] = {}
    session = session or requests.Session()
    as_of = as_of or datetime.now(timezone.utc)
    for spec in specs:
        detail: dict[str, Any] = {"profiles": list(spec.profile_hints), "source_kind": spec.source_kind}
        try:
            rows = collect_direct_source(spec, session=session, diagnostics=detail,
                                         destination_check=destination_check)
            candidates.extend(rows)
            status[spec.source_code] = "ok" if rows else "empty_valid"
            detail["raw_candidates"] = len(rows)
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            status[spec.source_code] = "failed"
            detail["error_type"] = type(exc).__name__
            # Never export exception text containing request URLs or credentials.
            known = {"invalid_url", "unsafe_destination", "cross_publisher_redirect", "feed_too_large",
                     "unsupported_xml_declaration", "not_rss_or_atom", "redirect_limit"}
            detail["failure_reason"] = str(exc) if type(exc) is ValueError and str(exc) in known else type(exc).__name__
            # Only this verified, public FSC feed has a registered HTML adapter.
            # Never turn arbitrary URLs or rejected destinations into fallback probes.
            unsafe = str(exc) in {"invalid_url", "unsafe_destination", "cross_publisher_redirect", "unsupported_xml_declaration"}
            if not unsafe and supports_feed(spec.url) and spec.source_kind == "official":
                primary = dict(detail)
                fallback: dict[str, Any] = {}
                detail.update({"primary": primary, "primary_status": "failed", "fallback_used": True,
                               "fallback": fallback})
                try:
                    rows = collect_board(spec, session=session, destination_check=destination_check,
                                         as_of=as_of, diagnostics=fallback)
                    candidates.extend(rows)
                    status[spec.source_code] = "ok" if rows else "empty_valid"
                    detail.update({"active_endpoint": fallback.get("board_endpoint"), "raw_candidates": len(rows)})
                    fallback["status"] = status[spec.source_code]
                except (requests.RequestException, ValueError) as fallback_exc:
                    fallback["status"] = "failed"
                    reason = str(fallback_exc)
                    fallback["failure_reason"] = reason if type(fallback_exc) is ValueError and reason.startswith("fsc_") else type(fallback_exc).__name__
                detail["http_requests"] = primary.get("http_requests", 0) + len(fallback.get("http_attempts", []))
        detail["status"] = status[spec.source_code]
        if diagnostics is not None:
            diagnostics[spec.source_code] = detail
    return candidates, status


def probe_direct_sources(specs: Iterable[DirectSourceSpec], *, as_of: datetime | None = None,
                         session=None, destination_check=_public_destination) -> dict[str, Any]:
    """Explicit public-feed HTTP check; no model construction or DB operation."""
    as_of = as_of or datetime.now(timezone.utc)
    details: dict[str, Any] = {}
    rows, _ = collect_direct_sources(specs, diagnostics=details, session=session,
                                     destination_check=destination_check, as_of=as_of)
    for code, detail in details.items():
        matching = [row for row in rows if row.source_code == code]
        detail["dated_candidates"] = sum(row.published_at is not None for row in matching)
        detail["fresh_candidates"] = sum(classify_freshness(row.published_at, as_of) in {"core_window", "light_window"} for row in matching)
        detail["latest_published_at"] = max((row.published_at for row in matching if row.published_at), default=None)
        if detail["latest_published_at"]:
            detail["latest_published_at"] = detail["latest_published_at"].isoformat()
    return {"status": "direct_source_probe", "generated_at": as_of.isoformat(),
            "project_openai_api_calls": 0, "db_writes": 0,
            "configured_source_count": len(details), "direct_sources": details,
            "sample_limit": 20, "candidate_sample": [{"source_code": row.source_code,
                "title": row.title[:300], "url": diagnostic_endpoint(row.url),
                "description": row.description[:700],
                "published_at": row.published_at.isoformat() if row.published_at else None}
                for row in rows[:20]]}
