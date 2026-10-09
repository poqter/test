"""Regression checks for observed deployment failures; no external calls."""
from datetime import date, datetime, timezone
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
from modules.briefing.models import SourceCandidate, SharedEventCandidate, PhaseBResult, ProfileEventAnalysis
from modules.briefing.runtime import _content_payload, _display_coverage_status, _overall_validation, body_quality_ready
from modules.briefing.preflight import run_runtime_preflight, preflight_ready
from modules.briefing.scheduler import generate_group, publish_ready

AS_OF = datetime(2026, 10, 8, 22, 30, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def prohibit_external_calls(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('Offline test attempted HTTP')))

def sample(code='NEWS', hosts=('www.mois.go.kr', 'www.yna.co.kr'), tiers=None):
    rows=[]; events=[]; candidates=[]
    for i, host in enumerate(hosts):
        key=f'event-{i}'
        c=SourceCandidate(title=f'가상 기사 {i}',url=f'https://{host}/article/{i}',source_name=host,
            collector_provider='synthetic',source_kind='news',published_at=AS_OF,routed_profiles={code})
        candidates.append(c)
        events.append(SharedEventCandidate(key,c.title,[c],{code},AS_OF,AS_OF))
        rows.append(ProfileEventAnalysis(key,code,80-i,(tiers or ['core']*len(hosts))[i],
            'confirmed','ok','사회·안전','confirmed',c.title,'가상 요약','가상 중요성','가상 영향','watch','usable'))
    return rows, PhaseBResult(AS_OF,candidates,events,[],{})

@pytest.mark.parametrize('hosts,tiers,expected', [
    (('www.mois.go.kr',), ['core'], 'degraded'),
    (('www.mois.go.kr','www.yna.co.kr'), ['core','excluded'], 'degraded'),
    (('www.mois.go.kr','www.mois.go.kr'), ['core','light_digest'], 'degraded'),
    (('www.donga.com','sports.donga.com'), ['core','light_digest'], 'degraded'),
    (('www.mois.go.kr','www.yna.co.kr'), ['core','light_digest'], 'healthy'),
    (('www.mois.go.kr',), ['excluded'], 'insufficient'),
])
def test_quality_uses_displayed_articles_not_search_success(hosts,tiers,expected):
    rows, phase=sample(hosts=hosts,tiers=tiers)
    status=_display_coverage_status('NEWS',rows,phase,'healthy')
    assert status==expected
    assert _overall_validation(rows,status)==('ok' if expected=='healthy' else 'required')

def test_insurance_keeps_analysis_core_rows_but_only_one_representative():
    rows,phase=sample('INSURANCE',hosts=('insjournal.co.kr',)*3)
    content=_content_payload('INSURANCE',rows,phase,'healthy')
    assert content['core_count']==3 and len(content['issues'])==3
    assert sum(r['representative'] for r in content['issues'])==1
    assert content['issues'][0]['representative']

def configure_base(monkeypatch):
    for name in ('SUPABASE_URL','SUPABASE_SECRET_KEY','OPENAI_API_KEY','BRIEFING_DISCOVERY_MODEL'):
        monkeypatch.setenv(name,'synthetic-test-only')
    for name in ('BRIEFING_MARKET_OBSERVATIONS_JSON','BRIEFING_MARKET_OBSERVATIONS_FILE','BRIEFING_MARKET_OBSERVATIONS_URL'):
        monkeypatch.delenv(name,raising=False)

def test_missing_market_feed_blocks_market_but_preserves_daily(monkeypatch):
    configure_base(monkeypatch)
    daily=run_runtime_preflight(direct_sources=[],require_direct_sources=False)
    market=run_runtime_preflight(direct_sources=[],require_direct_sources=False,require_market_observations=True)
    assert preflight_ready(daily)
    assert not preflight_ready(market)
    assert next(c for c in market if c.code=='market_observations').required

def test_market_without_feed_stops_before_db_or_paid_request(monkeypatch):
    configure_base(monkeypatch); repo=Mock()
    result=generate_group(repo,date(2026,10,9),'MARKET')
    assert result=={'status':'configuration_required','reason':'market_observations_not_configured'}
    assert not repo.mock_calls

def test_old_one_article_healthy_snapshot_is_still_held():
    rows,phase=sample(hosts=('www.mois.go.kr',))
    body=_content_payload('NEWS',rows,phase,'healthy')|{'schema':'hwarang-public-v2'}
    repo=Mock();repo.profiles.return_value=[{'profile_code':'NEWS','run_mode':'auto'}]
    repo.bundle_for_date.return_value={'revision':{'id':'rev','publication_status':'draft','validation_status':'ok','coverage_status':'healthy'},
        'snapshot':{'external_content_payload':body,'qa_payload':{'public_body_ready':True}},'briefing':{'id':'brief'}}
    assert publish_ready(repo,date(2026,10,9),('NEWS',))==[{'profile':'NEWS','status':'quality_hold'}]
    repo.publish_revision.assert_not_called()
    repo.history.assert_not_called()

def test_old_one_article_manual_publish_button_is_disabled():
    script='''
import streamlit as st
from modules.briefing.briefing_center import _render_profile_detail
from unittest.mock import Mock
body={'schema':'hwarang-public-v2','profile_code':'NEWS','profile_label':'종합뉴스 브리핑','issues':[{'title':'가상 뉴스','summary':'가상 요약','sources':[{'title':'가상 기사','source_name':'가상 발행사','url':'https://www.mois.go.kr/article/1','published_at':'2026-10-08T03:00:00+00:00'}]}]}
bundle={'briefing':{'id':'brief','briefing_date':'2026-10-09'},'revision':{'id':'rev','publication_status':'draft','validation_status':'ok','coverage_status':'healthy'},'snapshot':{'id':'snap','external_content_payload':body,'content_payload':{'as_of':'2026-10-08T22:30:00+00:00'},'qa_payload':{'public_body_ready':True}}}
_render_profile_detail(Mock(),'NEWS',bundle,True)
'''
    at=AppTest.from_string(script).run()
    assert not at.exception
    assert next(b for b in at.button if b.label=='검수 완료 브리핑 공개').disabled
