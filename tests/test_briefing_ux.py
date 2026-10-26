from unittest.mock import Mock
from streamlit.testing.v1 import AppTest
import pytest
from test_briefing_release import bundle
from modules.briefing import briefing_center as center
from modules.briefing.costs import usage_summary

@pytest.fixture
def repo(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('No network in UI test')))
    monkeypatch.setattr('modules.briefing.weather.get_weather', lambda region, day: {'status':'unavailable','region_name':'서울특별시','date':day})
    saved={code:bundle(code) for code in ('MARKET','NEWS','INSURANCE')}
    r=Mock()
    r._snapshot_for_revision.side_effect=lambda rid:next(x['snapshot'] for x in saved.values() if x['revision']['id']==rid)
    r.bundle_from_parts.side_effect=lambda b,v,s:{'briefing':b,'revision':v,'snapshot':s,'actions':[]}
    r.customer_bundle_for_share.side_effect=lambda code,day,**kwargs:saved[code]
    r.bundle_for_date.side_effect=lambda code,day,**kwargs:saved[code]
    r.latest_complete_customer_date.return_value='2026-10-09'
    r.public_base_url.return_value='https://example.org'
    r.staff_sender.return_value={'name':'테스트','position':'팀장'}
    r.operating_policy.return_value={'external_sharing_approved':True}
    r.ai_generation_enabled.return_value=True
    r.daily_run_status.return_value={}
    r.operation_status.return_value={'runs':[],'jobs':[]}
    r.cost_status.return_value={'today':usage_summary([]),'month':usage_summary([])}
    monkeypatch.setattr(center,'_repo',lambda:r)
    monkeypatch.setattr(center,'_latest_summaries',lambda *args:saved)
    monkeypatch.setattr(center,'_customer_date_cached',lambda:'2026-10-09')
    return r

def app(role='user'):
    return AppTest.from_string("""
import streamlit as st
from modules.briefing.briefing_center import run
st.session_state.setdefault('login_profile',{'id':'test-user','position_name':'팀장','role':ROLE})
run()
""".replace('ROLE',repr(role))).run()

def test_employee_navigation_and_reading_do_not_query_sharing_or_manage(repo):
    a=app();assert not a.exception
    menu=next(r for r in a.radio if r.key=='hw_briefing_page')
    assert menu.options==['오늘 브리핑','지난 브리핑','고객에게 공유']
    assert [t.label for t in a.tabs][:3]==['경제·금융 브리핑','종합뉴스 브리핑','보험업계 브리핑']
    assert not any(b.label=='이 브리핑 게시하기' for b in a.button)
    repo.operating_policy.assert_not_called();repo.create_combined_share.assert_not_called()
    repo.operation_status.assert_not_called();repo.reserve_request.assert_not_called()

def test_share_preview_requires_no_link_creation_or_api(repo):
    a=app();next(r for r in a.radio if r.key=='hw_briefing_page').set_value('고객에게 공유').run()
    assert not a.exception
    next(t for t in a.toggle if t.label=='고객 화면 미리보기').set_value(True).run()
    assert not a.exception
    repo.staff_sender.assert_called_once_with('test-user')
    repo.create_combined_share.assert_not_called();repo.reserve_request.assert_not_called()
    assert any('고객에게 보이는 본문' in t.value for t in a.subheader)

def test_manager_has_one_navigation_and_separate_operations(repo):
    a=app('super_admin');assert not a.exception
    next(r for r in a.radio if r.key=='hw_briefing_page').set_value('운영 관리').run()
    assert not a.exception
    assert any(t.value=='자동 운영' for t in a.subheader)
    assert any(t.value=='생성·게시 관리' for t in a.subheader)
    assert not any(b.label=='운영 설정' for b in a.button)
    repo.reserve_request.assert_not_called()

def test_history_reading_routes_share_to_same_day(repo):
    a=app();next(r for r in a.radio if r.key=='hw_briefing_page').set_value('지난 브리핑').run()
    assert not a.exception
    next(b for b in a.button if b.label=='고객에게 공유').click().run()
    assert not a.exception
    assert any('2026-10-09' in c.value for c in a.caption)
    assert next(r for r in a.radio if r.key=='hw_briefing_page').value=='지난 브리핑'
    assert any(c.label=='보험업계' and c.value is False for c in a.checkbox)
    repo.reserve_request.assert_not_called()
