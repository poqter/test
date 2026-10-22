"""Regressions reproduced from the 2026-10-14 deployed UI audit; offline."""
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from test_briefing_release import bundle
from modules.briefing.repository import BriefingRepository
from modules.briefing.costs import cost_summary_label, usage_summary
from modules.shared.local_time import today_kst


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('No network or AI')))


@pytest.mark.parametrize('instant,expected', [
    ('2026-10-13T14:59:59+00:00', date(2026, 10, 13)),
    ('2026-10-13T15:00:00+00:00', date(2026, 10, 14)),
    ('2026-10-14T08:56:00+09:00', date(2026, 10, 14)),
])
def test_korean_business_day_boundary(instant, expected):
    assert today_kst(datetime.fromisoformat(instant)) == expected


def test_explicit_naive_clock_is_rejected():
    with pytest.raises(ValueError):
        today_kst(datetime(2026, 10, 13))


def test_export_cache_rolls_at_kst_midnight(monkeypatch):
    from modules.shared import runtime_cache as cache
    monkeypatch.setattr(cache, '_session', lambda: {})
    state = {}
    monkeypatch.setattr(cache, '_session', lambda: state)
    monkeypatch.setattr('modules.shared.organization.current_brand_fingerprint', lambda: 'same-brand')
    clock = [date(2026, 10, 13)]
    monkeypatch.setattr(cache, 'today_kst', lambda: clock[0])
    calls = []
    @cache.session_export('clock-test', name_arg=False)
    def export():
        calls.append(clock[0])
        return str(clock[0]).encode()
    assert export() == b'2026-10-13'
    assert export() == b'2026-10-13'
    assert len(calls) == 1
    clock[0] = date(2026, 10, 14)
    assert export() == b'2026-10-14'
    assert len(calls) == 2


def test_credit_html_is_a_single_html_block_and_quotas_unchanged():
    app = AppTest.from_string('''
from modules.shared.academy_credit_ui import render_training_credit_strip
from modules.shared.ai_guardrails import TrainingCreditStatus
render_training_credit_strip(TrainingCreditStatus(service_enabled=True, text_enabled=True,
    voice_enabled=True, available_credits=1500, monthly_available_credits=1000,
    purchased_available_credits=500, remaining_percent=100,
    voice_available_seconds=1800, voice_allocation_seconds=1800, voice_remaining_percent=100))
''').run()
    assert not app.exception
    markup = app.markdown[0].value
    assert '\n' not in markup
    assert markup.startswith('<style>') and '<div class="hw-credit-shell">' in markup
    assert '1,500' in markup and '30분' in markup and '기본 1,000 · 구매 크레딧 500' in markup
    assert len(app.code) == 0


def test_credit_service_off_stays_hidden():
    app = AppTest.from_string('''
from modules.shared.academy_credit_ui import render_training_credit_strip
from modules.shared.ai_guardrails import TrainingCreditStatus
render_training_credit_strip(TrainingCreditStatus(service_enabled=False, available_credits=1500))
''').run()
    assert not app.exception and not app.markdown


def repository(saved):
    repo = BriefingRepository('https://example.org', 'synthetic')
    repo.history = Mock(side_effect=lambda code, **kw: saved.get(code, []))
    return repo


def test_reproduce_missing_market_intersection_then_offer_news_insurance():
    repo = repository({'NEWS': [bundle('NEWS', '2026-10-12')],
                       'INSURANCE': [bundle('INSURANCE', '2026-10-12')]})
    # This is the old early-return cause, independently of OpenAI or Reader.
    assert repo.latest_complete_customer_date() is None
    assert repo.latest_available_customer_date() == '2026-10-12'


def test_fallback_never_combines_dates_or_picks_newer_draft():
    draft = bundle('MARKET', '2026-10-14')
    draft['revision']['publication_status'] = 'draft'
    repo = repository({'MARKET': [draft], 'NEWS': [bundle('NEWS', '2026-10-12')],
                       'INSURANCE': [bundle('INSURANCE', '2026-10-11')]})
    assert repo.latest_complete_customer_date() is None
    assert repo.latest_available_customer_date() == '2026-10-12'


def test_quality_blocked_published_day_is_for_explanation_not_permission():
    saved = bundle('NEWS', '2026-10-12')
    saved['revision']['external_share_allowed'] = False
    repo = repository({'NEWS': [saved]})
    assert repo.latest_available_customer_date() == '2026-10-12'
    from modules.briefing.experience import sharing_blockers
    assert sharing_blockers(saved, {'external_sharing_approved': True}, {'position_name': '팀장'})


def test_empty_history_has_no_candidate():
    assert repository({}).latest_available_customer_date() is None


def share_app(monkeypatch, saved, *, selected=None):
    from modules.briefing import briefing_center as center
    repo = repository(saved)
    by_date = {(b['briefing']['profile_code'], b['briefing']['briefing_date']): b
               for rows in saved.values() for b in rows}
    repo.bundle_for_date = Mock(side_effect=lambda code, day: by_date.get((code, str(day))))
    repo.operating_policy = Mock(return_value={'external_sharing_approved': True})
    repo.public_base_url = Mock(return_value='https://example.org')
    repo.create_combined_share = Mock(side_effect=AssertionError('Reading must not publish'))
    monkeypatch.setattr(center, '_repo', lambda: repo)
    script = '''
import streamlit as st
from modules.briefing.briefing_center import _combined_sharing, _repo
st.session_state.setdefault('login_profile', {'id':'test', 'position_name':'팀장'})
_combined_sharing(_repo(), SELECTED)
'''.replace('SELECTED', repr(selected))
    return AppTest.from_string(script).run(), repo


def test_partial_share_ui_shows_missing_reason_without_publication(monkeypatch):
    app, repo = share_app(monkeypatch, {'NEWS': [bundle('NEWS', '2026-10-12')],
                                      'INSURANCE': [bundle('INSURANCE', '2026-10-12')]})
    assert not app.exception
    checks = {c.label: c for c in app.checkbox}
    assert not checks['경제·금융 브리핑'].disabled and checks['경제·금융 브리핑'].value
    assert not checks['종합뉴스 브리핑'].disabled and not checks['보험업계'].disabled
    assert any('2개 영역' in item.value for item in app.info)
    assert any('아직 공유 가능한 브리핑이 없습니다' in item.value for item in app.caption)
    assert not next(b for b in app.button if b.label == '통합 공유 링크 만들기').disabled
    repo.create_combined_share.assert_not_called()
    assert {str(call.args[1]) for call in repo.bundle_for_date.call_args_list} == {'2026-10-12'}


def test_complete_older_day_keeps_priority_over_new_partial(monkeypatch):
    saved = {code: [bundle(code, '2026-10-11')] for code in ('MARKET', 'NEWS', 'INSURANCE')}
    saved['NEWS'].insert(0, bundle('NEWS', '2026-10-12'))
    app, repo = share_app(monkeypatch, saved)
    assert not app.exception
    assert {str(call.args[1]) for call in repo.bundle_for_date.call_args_list} == {'2026-10-11'}


def test_selected_date_is_not_replaced_by_fallback(monkeypatch):
    app, repo = share_app(monkeypatch, {'NEWS': [bundle('NEWS', '2026-10-12')]}, selected='2026-10-10')
    assert not app.exception
    assert next(b for b in app.button if b.label == '통합 공유 링크 만들기').disabled
    assert repo.history.call_count==0  # share only the explicitly requested date


@pytest.mark.parametrize('defect', ['public_body_ready', 'external_qa_passed', 'external_share_allowed'])
def test_all_blocked_ui_explains_and_disables_share(monkeypatch, defect):
    saved = bundle('NEWS', '2026-10-12')
    target = saved['snapshot']['qa_payload'] if defect == 'public_body_ready' else saved['revision']
    target[defect] = False
    app, repo = share_app(monkeypatch, {'NEWS': [saved]})
    assert not app.exception and app.warning
    assert next(b for b in app.button if b.label == '통합 공유 링크 만들기').disabled
    repo.create_combined_share.assert_not_called()


def test_all_unknown_cost_is_not_zero():
    label = cost_summary_label(usage_summary([{}] * 26))
    assert '총비용 확인 필요' in label and '26회' in label and '$0.0000' not in label


def test_partial_cost_displays_known_subtotal_not_total():
    label = cost_summary_label(usage_summary([{'actual_cost_usd': 1.2}, {}]))
    assert '총비용 확인 필요' in label and '$1.2000 (일부 기록)' in label


def test_no_requests_and_known_zero_remain_distinct():
    assert 'API 요청 없음' in cost_summary_label(usage_summary([]))
    assert '기록 기준 비용 합계 $0.0000' in cost_summary_label(usage_summary([{'actual_cost_usd': 0}]))
