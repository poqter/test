"""Published home status is background work, never a navigation prerequisite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='home-briefing')
_lock = Lock()
_jobs = {}


def summary_job(config):
    # Server-only key. Published summaries are identical for all home readers.
    key = (config.url, config.secret_key)
    with _lock:
        previous = _jobs.get(key)
        if previous and (not previous[1].done() or monotonic() - previous[0] < 30):
            return previous[1]
        job = _pool.submit(_load, config.url, config.secret_key)
        _jobs[key] = (monotonic(), job)
        return job


def _load(url, key):
    from datetime import datetime
    from modules.briefing.repository import BriefingRepository
    from modules.briefing.briefing_center import PROFILE_ORDER, KST, home_briefing_summary
    items = BriefingRepository(url, key).latest_summaries(PROFILE_ORDER, include_draft=False)
    today = str(datetime.now(KST).date())
    ready = [c for c in PROFILE_ORDER if str(((items.get(c) or {}).get('briefing') or {}).get('briefing_date')) == today]
    status = '오늘 자료 공개' if len(ready) == 3 else '최신 자료 공개' if any(items.get(c) for c in PROFILE_ORDER) else '준비 중'
    return status, home_briefing_summary(items)
