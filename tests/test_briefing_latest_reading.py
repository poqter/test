"""Latest published reading must survive midnight and mixed publication dates."""
from contextlib import nullcontext
from types import SimpleNamespace
from datetime import datetime, timedelta
from modules.briefing import briefing_center as center
from modules.briefing import reading_state


def test_today_keeps_latest_published_per_profile(monkeypatch):
    today = datetime.now(center.KST).date()
    codes = center.PROFILE_ORDER
    items = {code: {'briefing': {'briefing_date': str(today-timedelta(days=i+1))},
                    'revision': {'id': code}} for i, code in enumerate(codes)}
    shown, notices = [], []
    monkeypatch.setattr(center, '_latest_summaries', lambda drafts: items)
    monkeypatch.setattr(center.st, 'tabs', lambda *a, **k: [nullcontext() for _ in codes])
    monkeypatch.setattr(center.st, 'info', notices.append)
    monkeypatch.setattr(reading_state, 'install_reading_state', lambda: None)
    monkeypatch.setattr(center, '_render_profile_detail', lambda repo, code, bundle, manage: shown.append((code, bundle)))
    repo = SimpleNamespace(_snapshot_for_revision=lambda rid: {'id': rid},
                           bundle_from_parts=lambda b, r, s: {'briefing': b, 'revision': r, 'snapshot': s})
    center._render_today(repo, False)
    assert [c for c, _ in shown] == list(codes)
    assert not notices
    assert [b['briefing']['briefing_date'] for _, b in shown] == [items[c]['briefing']['briefing_date'] for c in codes]
    # A newly published category replaces only its own older edition.
    items[codes[0]]['briefing']['briefing_date'] = str(today)
    shown.clear()
    center._render_today(repo, False)
    assert shown[0][1]['briefing']['briefing_date'] == str(today)
    assert len(shown) == len(codes)
    # No publication at all still gets an explicit empty state.
    items.clear(); shown.clear()
    center._render_today(repo, False)
    assert not shown
    assert len(notices) == len(codes)
