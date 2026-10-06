"""Small, bounded fallback for the verified FSC press-release board."""
from __future__ import annotations

from html.parser import HTMLParser
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from .models import SourceCandidate
from .normalize import classify_freshness, normalize_title, publisher_domain
from .publication import parse_publication_date

BOARD_URL = "https://www.fsc.go.kr/no010101"
MAX_REQUESTS = 8
MAX_DETAILS = 6


class _Node:
    def __init__(self, tag="root", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, _Node):
                yield from child.walk()

    def find(self, *, cls=None, tag=None):
        return next((n for n in self.walk() if (cls is None or cls in n.attrs.get("class", "").split())
                     and (tag is None or n.tag == tag)), None)

    def text(self):
        if self.tag in {"script", "style", "noscript"} or "newbbs-span" in self.attrs.get("class", "").split():
            return ""
        value = "".join(child.text() if isinstance(child, _Node) else child for child in self.children)
        return f" {value} " if self.tag in {"div", "p", "br", "li", "tr", "td"} else value


class _Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = _Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def supports_feed(url):
    parts = urlsplit(url)
    return (publisher_domain(url) == "fsc.go.kr" and parts.path.rstrip("/") == "/about/fsc_bbs_rss"
            and parse_qsl(parts.query, keep_blank_values=True) == [("fid", "0111")])


def _article_url(href):
    url = urljoin(BOARD_URL, href)
    parts = urlsplit(url)
    if publisher_domain(url) != "fsc.go.kr" or not re.fullmatch(r"/no010101/\d+", parts.path):
        return None
    # Keep the board's public search parameters in its canonical link order.
    values = dict(parse_qsl(parts.query, keep_blank_values=True))
    keys = ("curPage", "srchBeginDt", "srchCtgry", "srchEndDt", "srchKey", "srchText")
    query = urlencode([(key, values.get(key, "")) for key in keys])
    return urlunsplit(("https", "www.fsc.go.kr", parts.path, query, ""))


def parse_board(html, spec, retrieved_at):
    board = _Tree(html).root.find(cls="board-list-wrap")
    items = board.find(tag="ul") if board else None
    if items is None:
        raise ValueError("fsc_board_layout_changed")
    rows = []
    for item in items.children:
        if not isinstance(item, _Node) or item.tag != "li":
            continue
        subject, day = item.find(cls="subject"), item.find(cls="day")
        link = subject.find(tag="a") if subject else None
        url = _article_url(link.attrs.get("href", "")) if link else None
        if not url or day is None:
            continue
        title = normalize_title(link.attrs.get("title") or link.text())[:300]
        published = parse_publication_date(normalize_title(day.text()), url=url)
        if not title or published is None:
            continue
        rows.append(SourceCandidate(title, url, spec.source_name, "direct_fsc_board", spec.source_kind,
                    description="", published_at=published, retrieved_at=retrieved_at,
                    source_code=spec.source_code, source_family_code=spec.source_family_code,
                    source_tier=spec.source_tier, endpoint_role="primary",
                    metadata={"profile_hints": list(spec.profile_hints), "insurance_requires_topic": True,
                              "publication_status": "official_board_date", "publication_date_source": "official_board_row",
                              "direct_fallback": True}))
    if not rows and any(isinstance(n, _Node) and n.tag == "li" for n in items.children):
        raise ValueError("fsc_board_layout_changed")
    return rows


def article_body(html, row):
    page = _Tree(html).root.find(cls="board-view-wrap")
    header = page.find(cls="header") if page else None
    title = header.find(cls="subject") if header else None
    day = header.find(cls="day") if header else None
    body = page.find(cls="body") if page else None
    content = body.find(cls="cont") if body else None
    if title is None or day is None or content is None:
        raise ValueError("fsc_article_layout_changed")
    dates = re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", day.text())
    published = parse_publication_date(dates[0], url=row.url) if len(set(dates)) == 1 else None
    if published != row.published_at or normalize_title(title.text()) != normalize_title(row.title):
        raise ValueError("fsc_article_identity_mismatch")
    text = normalize_title(content.text())[:12000]
    if len(text) < 80:
        raise ValueError("fsc_article_body_missing")
    return text


def collect_board(spec, *, session, destination_check, as_of, diagnostics, clock=time.monotonic):
    deadline = clock() + 30.0
    attempts = diagnostics.setdefault("http_attempts", [])

    def fetch(url):
        for _ in range(3):
            remaining = deadline - clock()
            if len(attempts) >= MAX_REQUESTS or remaining <= 0:
                raise ValueError("fsc_board_http_budget")
            if publisher_domain(url) != "fsc.go.kr" or not destination_check(url):
                raise ValueError("unsafe_destination")
            attempt = {"endpoint": url, "http_status": None}
            attempts.append(attempt)
            with session.get(url, timeout=min(8.0, remaining), stream=True, allow_redirects=False,
                             headers={"User-Agent": "HWARANG-Briefing/1.7-stage1"}) as response:
                attempt["http_status"] = response.status_code
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = urljoin(url, response.headers.get("Location", ""))
                    continue
                response.raise_for_status()
                if "html" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError("fsc_board_not_html")
                body = bytearray()
                for chunk in response.iter_content(8192):
                    body.extend(chunk)
                    if len(body) > 512000 or clock() >= deadline:
                        raise ValueError("fsc_board_http_budget")
                return body.decode("utf-8", errors="replace")
        raise ValueError("redirect_limit")

    rows = parse_board(fetch(BOARD_URL), spec, as_of)
    diagnostics.update({"board_candidates": len(rows), "board_endpoint": BOARD_URL,
                        "detail_failures": [], "detail_limit": MAX_DETAILS, "http_request_limit": MAX_REQUESTS})
    accepted, detailed = [], 0
    for row in rows:
        if classify_freshness(row.published_at, as_of) not in {"core_window", "light_window"}:
            continue
        if detailed >= MAX_DETAILS:
            break
        detailed += 1
        try:
            row.description = article_body(fetch(row.url), row)
            row.metadata["article_body_status"] = "verified"
            accepted.append(row)
        except (requests.RequestException, ValueError) as exc:
            reason = str(exc) if type(exc) is ValueError and str(exc).startswith("fsc_") else type(exc).__name__
            diagnostics["detail_failures"].append({"endpoint": row.url, "reason": reason})
    diagnostics["verified_articles"] = len(accepted)
    if not accepted and diagnostics["detail_failures"]:
        raise ValueError("fsc_article_bodies_unavailable")
    return accepted
