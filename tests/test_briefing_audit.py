"""Policy and failure regression checks; no live paid requests."""
from datetime import date
from unittest.mock import Mock
import pytest
import requests
from modules.briefing.openai_analysis import OpenAIAnalysisClient
from modules.briefing.openai_discovery import OpenAIWebDiscoveryClient, BriefingDiscoveryError
from modules.briefing.discovery_budget import DiscoveryBudget
from modules.briefing.config import DISCOVERY_LANES
from modules.briefing.scheduler import publish_ready, run_scheduled
from modules.briefing.api_errors import request_diagnostic, request_message
from modules.briefing.public_body import customer_body
from launch_fixtures import content


@pytest.mark.parametrize('mode,approved,expected', [('shadow',True,'published'),('auto',True,'published'),('shadow',False,'organization_approval_required'),('manual',True,'manual_mode')])
def test_no_observation_day_gate(mode,approved,expected):
    repo=Mock();repo.profiles.return_value=[{'profile_code':'NEWS','run_mode':mode,'is_enabled':True}]
    repo.operating_policy.return_value={'automatic_publication_enabled':approved}
    repo.bundle_for_date.return_value={'briefing':{'id':'b'},'revision':{'id':'r','publication_status':'draft','validation_status':'ok','coverage_status':'healthy'},'snapshot':{'content_payload':content('NEWS',1),'qa_payload':{'internal_body_ready':True}}}
    assert publish_ready(repo,date(2026,10,9),('NEWS',))[0]['status']==expected
    repo.verified_business_days.assert_not_called();repo._request.assert_not_called()
    assert repo.publish_revision.called == (expected=='published')


def test_provider_error_does_not_reveal_key(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','sk-synthetic-private')
    response=Mock(status_code=401,json=Mock(return_value={'error':{'code':'invalid_api_key','type':'invalid_request_error','message':'Bad key sk-synthetic-private Bearer secret-token https://example.org/?token=123'}}))
    details=request_diagnostic(response=response)
    message=request_message('analysis',details)
    assert details['http_status']==401 and details['provider_error_code']=='invalid_api_key'
    assert 'sk-synthetic-private' not in message and 'secret-token' not in message and 'token=123' not in message


def test_analysis_failure_is_recorded_before_protection_callback():
    from test_briefing_analysis_recovery import event
    seen=[]
    def protect(record):
        seen.append(dict(record));raise RuntimeError('usage protection')
    client=OpenAIAnalysisClient(api_key='synthetic',model='synthetic',on_response=protect)
    client.http=Mock();client.http.post.return_value=Mock(status_code=403,json=Mock(return_value={'error':{'code':'model_not_found','message':'Model unavailable'}}))
    with pytest.raises(RuntimeError,match='usage protection'):client.analyze('NEWS',[event(0)])
    assert seen[0]['status']=='request_failed' and seen[0]['http_status']==403
    assert seen[0]['provider_error_code']=='model_not_found' and 'HTTP 403' in seen[0]['failure_message']


def test_discovery_preserves_http_error_before_usage_callback():
    seen=[]
    def protect(record):seen.append(record);raise RuntimeError('usage protection')
    client=OpenAIWebDiscoveryClient(api_key='synthetic',model='synthetic');client.http=Mock()
    client.http.post.return_value=Mock(status_code=429,json=Mock(return_value={'error':{'code':'rate_limit_exceeded','message':'Rate limit'}}))
    with pytest.raises(RuntimeError,match='usage protection'):
        client.run_lane(DISCOVERY_LANES[0],budget=DiscoveryBudget(protect))
    assert seen[0]['http_status']==429 and seen[0]['provider_error_code']=='rate_limit_exceeded'


@pytest.mark.parametrize('state,marker,expected',[('not_applicable',True,1),('not_applicable',False,1),('unknown',True,1),('internal_check',True,1),('consultation_reference',True,1),('do_not_mention',False,1)])
def test_insurance_news_is_independent_of_private_consultation_state(state,marker,expected):
    source=content('INSURANCE',1);source['issues'][0].update(category='소비자·사회이슈',communication_state=state,customer_article_eligible=marker)
    body=customer_body(source);assert len(body['issues'])==expected
    assert all('customer_article_eligible' not in r and 'communication_state' not in r for r in body['issues'])


def test_recover_retains_each_group_failure_without_another_attempt(monkeypatch):
    from modules.briefing import scheduler
    from modules.briefing.runtime import BriefingRunError
    generate=Mock(side_effect=[BriefingRunError('OpenAI analysis HTTP 401',{'request_failure':{'http_status':401}}),BriefingRunError('OpenAI discovery HTTP 429',{'request_failure':{'http_status':429}})])
    monkeypatch.setattr(scheduler,'generate_group',generate);monkeypatch.setattr(scheduler,'publish_ready',lambda *a:[])
    result=run_scheduled('recover',repo=Mock())
    assert generate.call_count==3
    assert result['MARKET']['diagnostic']['diagnostics']['request_failure']['http_status']==401
    assert result['NEWS']['diagnostic']['diagnostics']['request_failure']['http_status']==429


def test_one_successful_collection_with_valid_article_is_not_a_source_count_hold():
    from modules.briefing.models import PhaseBResult, SourceCandidate
    from modules.briefing.runtime import _coverage_status
    from datetime import datetime,timezone
    now=datetime(2026,10,9,tzinfo=timezone.utc)
    row=SourceCandidate('가상 기사','https://example.org/article','가상','synthetic','news',published_at=now,freshness_tier='core_window',routed_profiles={'NEWS'},metadata={'profile_hints':['NEWS']})
    phase=PhaseBResult(now,[row],[],[],{},source_health={'feed':{'profiles':['NEWS'],'status':'ok'}})
    assert _coverage_status(phase,'NEWS',1)=='healthy'
    phase.source_health['feed']['status']='failed'
    assert _coverage_status(phase,'NEWS',1)!='healthy'


def test_exceptional_announcement_can_be_corrected_without_losing_sources():
    from modules.briefing.corrections import corrected_content
    source=content('NEWS',1)
    source['important_updates']=[{'event_key':'late-update','title':'추가 발표','summary':'추가 요약','sources':source['issues'][0]['sources']}]
    corrected=corrected_content(source,'late-update',{'summary':'정정 요약'},'발표 내용 수정')
    assert corrected['important_updates'][0]['summary']=='정정 요약'
    assert corrected['important_updates'][0]['sources']==source['important_updates'][0]['sources']
    assert source['important_updates'][0]['summary']=='추가 요약'


@pytest.mark.parametrize('state,confirm,expected',[('customer_ready',False,True),('consultation_reference',False,False),('consultation_reference',True,True),('internal_check',False,False),('do_not_mention',False,False),('not_applicable',False,False),('unknown',False,False)])
def test_internal_customer_copy_obeys_state_and_confirmation(state,confirm,expected):
    from streamlit.testing.v1 import AppTest
    script='''
import streamlit as st
from modules.briefing.briefing_center import _internal_actions
st.session_state['login_user']='unknown'
_internal_actions({'snapshot':{'id':'synthetic'},'actions':[{'id':'a','title':'가상 상담','communication_state':STATE,'conversation_payload':{'recommended_expression':'가상 고객 표현'},'workspace_actions':[]}]})
'''.replace('STATE',repr(state))
    app=AppTest.from_string(script).run()
    if confirm:app.checkbox[0].check().run()
    assert not app.exception
    assert bool(app.code)==expected


@pytest.mark.parametrize('cores',[0,1,5,8])
def test_insurance_compatibility_related_cap_never_expands_to_fifteen(cores):
    from modules.briefing.profile_rules import light_digest_limit
    assert light_digest_limit(cores,'INSURANCE')==8
