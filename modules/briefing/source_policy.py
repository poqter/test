"""Server-owned source identity. Search text cannot declare itself official."""
from __future__ import annotations

from .normalize import publisher_domain

OFFICIAL_DOMAINS = (
    "fsc.go.kr", "fss.or.kr", "korea.kr", "law.go.kr", "mohw.go.kr", "nts.go.kr",
    "mois.go.kr", "molit.go.kr", "moel.go.kr", "moe.go.kr", "msit.go.kr",
    "scourt.go.kr", "ccourt.go.kr", "police.go.kr", "nfa.go.kr", "kdca.go.kr",
    "bok.or.kr", "kostat.go.kr",
)
INDUSTRY_DOMAINS = ("klia.or.kr", "knia.or.kr", "kidi.or.kr", "kiri.or.kr")
INSURANCE_MEDIA = (
    "insjournal.co.kr", "insnews.co.kr", "insweek.co.kr", "fnnews.com", "mt.co.kr",
    "mk.co.kr", "hankyung.com", "edaily.co.kr", "sedaily.com", "asiae.co.kr",
    "news1.kr", "yna.co.kr", "newsis.com",
)
NEWS_BROADCAST = ("yna.co.kr", "news1.kr", "newsis.com", "kbs.co.kr", "imbc.com", "ytn.co.kr")
NEWS_MEDIA = (
    "jtbc.co.kr", "sbs.co.kr", "chosun.com", "joongang.co.kr", "donga.com",
    "hani.co.kr", "khan.co.kr", "hankyung.com", "mk.co.kr", "edaily.co.kr",
    "sedaily.com", "mt.co.kr", "fnnews.com", "asiae.co.kr", "etoday.co.kr",
)
LANE_DOMAINS = {
    "official_industry": OFFICIAL_DOMAINS[:6] + INDUSTRY_DOMAINS,
    "trusted_media": INSURANCE_MEDIA,
    "official_wire_broadcast": OFFICIAL_DOMAINS + NEWS_BROADCAST,
    "general_economic_media": NEWS_MEDIA,
}


def domain_matches(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def source_identity(url: str) -> tuple[str, str] | None:
    host = publisher_domain(url) or ""
    if domain_matches(host, OFFICIAL_DOMAINS):
        return "official", "A"
    if domain_matches(host, INDUSTRY_DOMAINS):
        return "industry_official", "B"
    if domain_matches(host, INSURANCE_MEDIA + NEWS_BROADCAST + NEWS_MEDIA):
        return "news", "C"
    return None
