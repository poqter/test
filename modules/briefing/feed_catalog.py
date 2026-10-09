"""Publisher-published RSS endpoints, not scraped news-list URLs.

Catalog checked 2026-10-09 against each publisher's RSS guide. These are
collection inputs for short attributed summaries, not article/photo licenses.
Personal-reader-only feeds (e.g. SBS) are deliberately not in this catalog.
"""
CATALOG = (
    ("hk_politics", "한국경제", "https://www.hankyung.com/feed/politics", ("NEWS",)),
    ("hk_society", "한국경제", "https://www.hankyung.com/feed/society", ("NEWS",)),
    ("hk_international", "한국경제", "https://www.hankyung.com/feed/international", ("NEWS", "MARKET")),
    ("hk_economy", "한국경제", "https://www.hankyung.com/feed/economy", ("NEWS", "MARKET")),
    ("hk_finance", "한국경제", "https://www.hankyung.com/feed/finance", ("MARKET",)),
    ("mk_headlines", "매일경제", "https://www.mk.co.kr/rss/30000001/", ("NEWS",)),
    ("mk_economy", "매일경제", "https://www.mk.co.kr/rss/30100041/", ("NEWS", "MARKET")),
    ("insurance_journal", "보험저널", "https://www.insjournal.co.kr/rss/allArticle.xml", ("INSURANCE",)),
)

GUIDES = (
    "https://www.hankyung.com/feed",
    "https://www.mk.co.kr/rss",
    "https://www.insjournal.co.kr/rssIndex.html",
)
