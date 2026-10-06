"""Bounded publication metadata enrichment; no model, search, or article storage."""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import time
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests

from .models import SourceCandidate
from .normalize import canonicalize_url, is_safe_url, publisher_domain
from .source_policy import OFFICIAL_DOMAINS, INDUSTRY_DOMAINS, INSURANCE_MEDIA, NEWS_BROADCAST, NEWS_MEDIA

KST = ZoneInfo("Asia/Seoul")
_KOREAN_COM = ("fnnews.com", "mt.co.kr", "mk.co.kr", "hankyung.com", "chosun.com", "donga.com", "hani.co.kr", "newsis.com", "ytn.co.kr", "sbs.co.kr", "etoday.co.kr")
_PUBLISHED_KEYS = {"article:published_time", "og:article:published_time", "datepublished", "pubdate", "publishdate", "parsely-pub-date"}
_ARTICLE_TYPES = {"Article", "NewsArticle", "Report", "BlogPosting", "AnalysisNewsArticle", "ReportageNewsArticle"}


def parse_publication_date(value: object, *, url: str = "") -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    # Explicit absolute dates only; crawled/modified/relative dates are never used.
    raw = re.sub(r"^(입력|등록|게시)\s*[:：]?\s*", "", raw)
    raw = re.sub(r"^(\d{4})[./](\d{2})[./](\d{2})", r"\1-\2-\3", raw)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
        except (ValueError, TypeError, OverflowError):
            return None
    if not dt.tzinfo:
        host = publisher_domain(url) or ""
        if not (host.endswith(".kr") or any(host == h or host.endswith("." + h) for h in _KOREAN_COM)):
            return None
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(timezone.utc)


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dates: list[str] = []
        self.title = ""
        self.description = ""
        self.scripts: list[str] = []
        self._script: list[str] | None = None
        self._time = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
        if tag == "meta":
            content = a.get("content") or ""
            if key in _PUBLISHED_KEYS:
                self.dates.append(content)
            elif key == "og:title":
                self.title = content[:300]
            elif key in {"og:description", "description"} and not self.description:
                self.description = content[:1000]
        if tag == "time" and (key == "datepublished" or any(t in (a.get("class") or "").lower() for t in ("published", "pubdate"))):
            self._time = True
            if a.get("datetime"):
                self.dates.append(a["datetime"])
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._script = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)
        if self._time:
            self.dates.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.scripts.append("".join(self._script))
            self._script = None
        if tag == "time":
            self._time = False


@dataclass(frozen=True)
class PublicationMetadata:
    published_at: datetime | None = None
    title: str = ""
    description: str = ""
    status: str = "unconfirmed"


def extract_publication_metadata(html: str, *, url: str) -> PublicationMetadata:
    parser = _MetadataParser()
    parser.feed(html)
    dates = list(parser.dates)

    def visit(node):
        if isinstance(node, list):
            for value in node:
                visit(value)
        elif isinstance(node, dict):
            types = node.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list) and _ARTICLE_TYPES.intersection(types):
                identity = node.get("url") or node.get("mainEntityOfPage")
                if isinstance(identity, dict):
                    identity = identity.get("@id")
                if not identity or canonicalize_url(str(identity)) == canonicalize_url(url):
                    if node.get("datePublished"):
                        dates.append(str(node["datePublished"]))
            if "@graph" in node:
                visit(node["@graph"])

    for raw in parser.scripts:
        try:
            visit(json.loads(raw))
        except (ValueError, TypeError, RecursionError):
            continue
    parsed = [dt for raw in dates if (dt := parse_publication_date(raw, url=url))]
    # Conflicting explicit publication dates fail closed rather than refreshing old news.
    if parsed and (max(parsed) - min(parsed)).total_seconds() > 86400:
        return PublicationMetadata(title=parser.title, description=parser.description, status="conflicting_dates")
    return PublicationMetadata(min(parsed) if parsed else None, parser.title, parser.description, "confirmed" if parsed else "unconfirmed")


def _public_destination(url: str) -> bool:
    if not is_safe_url(url):
        return False
    parts = urlsplit(url)
    if parts.port not in {None, 80, 443}:
        return False
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(row[4][0]).is_global for row in addresses)
    except (OSError, ValueError):
        return False


_CACHE: OrderedDict[str, tuple[float, PublicationMetadata]] = OrderedDict()


class PublicationDateEnricher:
    def __init__(self, *, session=None, max_requests=24, total_seconds=35.0, timeout_seconds=5.0, clock=time.monotonic, destination_check=_public_destination):
        self.http = session or requests.Session()
        self.http.trust_env = False
        self.max_requests = max_requests
        self.deadline = clock() + total_seconds
        self.timeout = timeout_seconds
        self.clock = clock
        self.destination_check = destination_check
        self.stats: Counter = Counter()
        self.requests = 0

    def _fetch(self, url: str) -> PublicationMetadata:
        if urlsplit(url).path in {"", "/"}:
            return PublicationMetadata(status="listing_page")
        def publisher_key(value):
            host = publisher_domain(value) or ""
            return next((d for d in OFFICIAL_DOMAINS + INDUSTRY_DOMAINS + INSURANCE_MEDIA + NEWS_BROADCAST + NEWS_MEDIA if host == d or host.endswith("."+d)), host)
        original_publisher = publisher_key(url)
        for _ in range(3):
            remaining = self.deadline - self.clock()
            if self.requests >= self.max_requests or remaining <= 0:
                return PublicationMetadata(status="budget_exhausted")
            if not self.destination_check(url):
                return PublicationMetadata(status="unsafe_destination")
            if publisher_key(url) != original_publisher:
                return PublicationMetadata(status="cross_publisher_redirect")
            self.requests += 1
            self.stats["http_requests"] += 1
            try:
                response = self.http.get(url, timeout=min(self.timeout, remaining), headers={"User-Agent": "HWARANG-Briefing/1.7-stage1"}, stream=True, allow_redirects=False)
                with response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("Location", ""))
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get("Content-Type", "").lower():
                        return PublicationMetadata(status="not_html")
                    body = bytearray()
                    for chunk in response.iter_content(8192):
                        if self.clock() >= self.deadline:
                            return PublicationMetadata(status="budget_exhausted")
                        body.extend(chunk)
                        if len(body) > 512_000:
                            return PublicationMetadata(status="too_large")
                    encoding = response.encoding if response.encoding and response.encoding.lower() != "iso-8859-1" else "utf-8"
                    return extract_publication_metadata(body.decode(encoding, errors="replace"), url=url)
            except (requests.RequestException, ValueError, LookupError):
                return PublicationMetadata(status="fetch_failed")
        return PublicationMetadata(status="redirect_limit")

    def enrich(self, row: SourceCandidate) -> None:
        self.stats["input"] += 1
        if not is_safe_url(row.url):
            self.stats["unsafe_url"] += 1
            row.metadata["publication_status"] = "unsafe_url"
            return
        if row.published_at is not None and row.title:
            self.stats["existing_date"] += 1
            row.metadata.setdefault("publication_status", "existing_date")
            return
        key = canonicalize_url(row.url)
        cached = _CACHE.get(key)
        if cached and cached[0] > self.clock():
            result = cached[1]
            self.stats["cache_hits"] += 1
        else:
            result = self._fetch(row.url)
            if result.status != "budget_exhausted":
                _CACHE[key] = (self.clock() + (21600 if result.published_at else 1200), result)
                _CACHE.move_to_end(key)
                while len(_CACHE) > 256:
                    _CACHE.popitem(last=False)
        if row.published_at is None:
            row.published_at = result.published_at
        row.title = row.title or result.title
        row.description = row.description or result.description
        row.metadata["publication_status"] = result.status
        row.metadata["publication_date_source"] = "html_metadata" if result.published_at else "unconfirmed"
        self.stats[result.status] += 1
