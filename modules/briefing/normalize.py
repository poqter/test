from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import hashlib
import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import CORE_FRESHNESS_HOURS, LIGHT_FRESHNESS_HOURS
from .models import SourceCandidate

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}
_TITLE_SPACE_RE = re.compile(r"\s+")


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1
        elif tag in {"p", "div", "br", "li", "tr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif tag in {"p", "div", "li", "tr"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden_depth:
            self.parts.append(data)


def visible_text(value: str, *, limit: int = 12000) -> str:
    """Use bounded article text, never HTML attributes or embedded scripts."""
    parser = _VisibleText()
    parser.feed(str(value or "")[:100000])
    return _TITLE_SPACE_RE.sub(" ", "".join(parser.parts)).strip()[:limit]


def is_safe_url(url: str) -> bool:
    try:
        parts = urlsplit((url or "").strip())
        if parts.hostname in {"localhost", "localhost.localdomain"}:
            return False
        try:
            if not ipaddress.ip_address(parts.hostname or "").is_global:
                return False
        except ValueError:
            pass
        return bool(parts.scheme in {"http", "https"} and parts.hostname
                    and not parts.username and not parts.password
                    and parts.port in {None, 80, 443}
                    and not re.search(r"[\s\\\x00-\x1f]", url))
    except (ValueError, TypeError):
        return False


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw or not is_safe_url(raw):
        return ""
    parts = urlsplit(raw)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        low = key.lower()
        if low in _TRACKING_KEYS or any(low.startswith(prefix) for prefix in _TRACKING_PREFIXES):
            continue
        query.append((key, value))
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def publisher_domain(url: str) -> str | None:
    host = urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_title(title: str) -> str:
    return _TITLE_SPACE_RE.sub(" ", (title or "").strip())


def fingerprint(candidate: SourceCandidate) -> str:
    raw = "|".join(
        [
            candidate.canonical_url or canonicalize_url(candidate.url),
            normalize_title(candidate.title).casefold(),
            (candidate.publisher_domain or "").casefold(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def classify_freshness(published_at: datetime | None, as_of: datetime) -> str:
    if published_at is None:
        return "undated"
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    local = as_of.astimezone(ZoneInfo("Asia/Seoul"))
    start = (local - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if published_at > as_of:
        return "undated"
    return "core_window" if published_at >= start else "stale"


def normalize_candidate(candidate: SourceCandidate, *, as_of: datetime) -> SourceCandidate:
    candidate.title = normalize_title(candidate.title)
    candidate.description = visible_text(candidate.description)
    candidate.canonical_url = canonicalize_url(candidate.url)
    candidate.publisher_domain = candidate.publisher_domain or publisher_domain(candidate.canonical_url)
    candidate.freshness_tier = classify_freshness(candidate.published_at, as_of)
    candidate.content_fingerprint = candidate.content_fingerprint or fingerprint(candidate)
    return candidate
