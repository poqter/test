from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from modules.briefing.direct_sources import DirectSourceSpec, _atom_candidates, _rss_candidates
from modules.briefing.models import DiscoveryLaneResult, DiscoveryUsage, SourceCandidate
from modules.briefing.normalize import classify_freshness, is_safe_url
from modules.briefing.openai_discovery import OpenAIWebDiscoveryClient
from modules.briefing.config import DISCOVERY_LANES
from modules.briefing.phase_b import run_phase_b
from modules.briefing.publication import PublicationDateEnricher, _CACHE, extract_publication_metadata, parse_publication_date

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)
URL = "https://www.fsc.go.kr/no010101/123"


@pytest.mark.parametrize("html", [
    '<meta property="article:published_time" content="2026-10-05T21:30:00+09:00">',
    '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-10-05T21:30:00+09:00"}</script>',
    '<script type="application/ld+json">{"@graph":[{"@type":"NewsArticle","datePublished":"2026-10-05T21:30:00+09:00"}]}</script>',
    '<time itemprop="datePublished" datetime="2026-10-05T21:30:00+09:00"></time>',
])
def test_explicit_publication_metadata(html):
    result = extract_publication_metadata(html, url=URL)
    assert result.published_at.isoformat() == "2026-10-05T12:30:00+00:00"
    assert classify_freshness(result.published_at, NOW) == "core_window"


@pytest.mark.parametrize("html", [
    '<meta property="article:modified_time" content="2026-10-06T08:00:00+09:00">',
    '<script type="application/ld+json">{"@type":"NewsArticle","dateModified":"2026-10-06T08:00:00+09:00"}</script>',
    '<script type="application/ld+json">{"@type":"WebSite","datePublished":"2026-10-06T08:00:00+09:00"}</script>',
    '<time>2026-10-06</time><p>확인 시각 2026-10-06</p>',
    '<script type="application/ld+json">broken JSON</script>',
    '<script type="application/ld+json">{"@type":"NewsArticle","url":"https://www.fsc.go.kr/other","datePublished":"2026-10-06T08:00:00+09:00"}</script>',
])
def test_modified_site_and_unrelated_dates_are_not_publication(html):
    assert extract_publication_metadata(html, url=URL).published_at is None


def test_conflicting_dates_fail_closed():
    html = '<meta property="article:published_time" content="2026-09-01T01:00:00+09:00"><script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-10-06T08:00:00+09:00"}</script>'
    result = extract_publication_metadata(html, url=URL)
    assert result.published_at is None and result.status == "conflicting_dates"


def test_korean_naive_date_uses_kst_and_unknown_timezone_is_rejected():
    assert parse_publication_date("입력 2026.10.05 21:30", url="https://fnnews.com/news/123").hour == 12
    assert parse_publication_date("2026-10-05T21:30", url="https://unknown.com/a") is None
    assert parse_publication_date("Crawled: today", url=URL) is None


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "https://user:pass@fsc.go.kr/a", "file:///a", "https://fsc.go.kr:bad/a", "https://fsc.go.kr/a\nX"])
def test_unsafe_url_rejected(url):
    assert not is_safe_url(url)


def test_feed_updated_only_is_not_publication():
    spec = DirectSourceSpec("x", "기관", URL)
    rss = ET.fromstring('<rss><channel><item><title>제도 변경</title><link>https://www.fsc.go.kr/a</link><updated>2026-10-06T00:00:00Z</updated></item></channel></rss>')
    atom = ET.fromstring('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>제도 변경</title><link href="https://www.fsc.go.kr/a"/><updated>2026-10-06T00:00:00Z</updated></entry></feed>')
    assert _rss_candidates(rss, spec, NOW)[0].published_at is None
    assert _atom_candidates(atom, spec, NOW)[0].published_at is None


class Response:
    status_code = 200
    encoding = "utf-8"
    headers = {"Content-Type": "text/html; charset=utf-8"}
    def __init__(self, content=None):
        self.content = content or b'<meta property="og:title" content="Insurance policy"><meta property="article:published_time" content="2026-10-05T21:30:00+09:00">'
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, size): yield self.content


class Session:
    def __init__(self, response=None): self.calls = []; self.response = response or Response()
    def get(self, url, **kwargs): self.calls.append(url); return self.response


def test_url_only_source_enriched_and_cached_without_ai():
    _CACHE.clear(); http = Session()
    enricher = PublicationDateEnricher(session=http, destination_check=lambda _: True)
    row = SourceCandidate("", URL, "기관", "openai_web_search", "official")
    enricher.enrich(row)
    assert row.title == "Insurance policy" and row.published_at is not None
    another = SourceCandidate("", URL, "기관", "openai_web_search", "official")
    enricher.enrich(another)
    assert len(http.calls) == 1 and enricher.stats["cache_hits"] == 1


def test_request_budget_and_unsafe_destination_do_not_fetch():
    _CACHE.clear(); http = Session()
    enricher = PublicationDateEnricher(session=http, max_requests=0, destination_check=lambda _: True)
    row = SourceCandidate("보험", URL, "기관", "fixture", "official")
    enricher.enrich(row)
    assert not http.calls and row.published_at is None
    enricher = PublicationDateEnricher(session=http, destination_check=lambda _: False)
    enricher.enrich(row)
    assert not http.calls and row.metadata["publication_status"] == "unsafe_destination"


def test_redirect_is_rechecked_before_second_request():
    _CACHE.clear(); response = Response(); response.status_code = 302; response.headers = {"Location": "http://127.0.0.1/secrets"}
    http = Session(response)
    enricher = PublicationDateEnricher(session=http, destination_check=lambda url: url.startswith("https://www.fsc.go.kr"))
    row = SourceCandidate("보험", URL, "기관", "fixture", "official")
    enricher.enrich(row)
    assert len(http.calls) == 1 and row.metadata["publication_status"] == "unsafe_destination"


def test_existing_date_does_not_fetch_or_refresh():
    _CACHE.clear(); http = Session()
    old = NOW - timedelta(hours=200)
    row = SourceCandidate("보험", URL, "기관", "fixture", "official", published_at=old)
    PublicationDateEnricher(session=http).enrich(row)
    assert row.published_at == old and not http.calls


def test_phase_b_enriches_before_freshness_gate_and_reports_lanes():
    _CACHE.clear(); http = Session()
    row = SourceCandidate("보험 제도 변경", URL, "기관", "openai_web_search", "official", metadata={"profile_hint": "INSURANCE", "lane_code": "official_industry"})
    class Discovery:
        def run_lane(self, lane):
            return DiscoveryLaneResult(lane.lane_code, lane.profile_code, [row] if lane == DISCOVERY_LANES[0] else [], DiscoveryUsage(search_actions=1), True)
    with patch("modules.briefing.phase_b.collect_direct_sources", return_value=([], {})):
        result = run_phase_b(as_of=NOW, discovery_client=Discovery(), date_enricher=PublicationDateEnricher(session=http, destination_check=lambda _: True))
    assert len(result.events) == 1 and result.candidates[0].freshness_tier == "core_window"
    assert result.diagnostics["lanes"][0]["usable_candidates"] == 1
    assert result.diagnostics["publication"]["http_requests"] == 1


def test_url_only_and_annotation_metadata_merge():
    payload = {"output": [{"type": "web_search_call", "action": {"type": "search", "sources": [{"type": "url", "url": URL}]}}, {"type": "message", "content": [{"annotations": [{"type": "url_citation", "url": URL, "title": "보험 제도 변경"}]}]}]}
    rows = OpenAIWebDiscoveryClient._candidates(payload, DISCOVERY_LANES[0])
    assert len(rows) == 1 and rows[0].title == "보험 제도 변경" and rows[0].source_kind == "official"
    assert rows[0].published_at is None


def test_untrusted_domain_cannot_declare_itself_official():
    payload = {"output": [{"type": "web_search_call", "results": [{"url": "https://fsc.go.kr.fake.example/a", "title": "보험", "publisher": "금융위원회"}]}]}
    assert OpenAIWebDiscoveryClient._candidates(payload, DISCOVERY_LANES[0]) == []
