from datetime import datetime, timezone
import pytest
from modules.briefing.execution_policy import checkpoint_identity, retry_guidance, budget_notice, request_plan
from modules.briefing.costs import usage_summary
from modules.briefing.staff_exports import staff_packet, team_summary, staff_pdf
from modules.briefing.public_body import customer_body

def bundle():
    return {'briefing': {'briefing_date':'2026-10-13'}, 'revision':{'id':'r1','revision_no':2},
        'snapshot':{'content_payload':{'profile_code':'NEWS','profile_label':'종합뉴스','as_of':'2026-10-13T07:30:00+09:00',
            'issues':[{'event_key':'event1','title':'가상 기사','summary':'검증용 사실 요약','representative':True,
                'sources':[{'url':'https://www.mk.co.kr/news/123','published_at':'2026-10-13T06:00:00+09:00','source_name':'검증용'}]}]}},
        'actions':[{'title':'가상 기사','communication_state':'consultation_reference','conversation_payload':
                    {'recommended_expression':'INTERNAL_SENTINEL','check_first':'확인할 조건','avoid_expression':'피할 표현'}}]}

def test_internal_export_never_leaks_customer():
    item=bundle();packet=staff_packet(item,{'name':'테스트','position':'팀장'})
    assert packet['body']['consultations'][0]['fields'][0]['text']=='INTERNAL_SENTINEL'
    assert 'INTERNAL_SENTINEL' not in str(customer_body(packet['body']))
    assert packet['edition']['number']==2
    assert '직원 내부용' in team_summary(item)
    assert staff_pdf(item,{'name':'테스트','position':'팀장'}).startswith(b'%PDF')

def test_costs_do_not_double_count_estimate_and_actual():
    s=usage_summary([{'actual_cost_usd':.2,'estimated_cost_usd':.3,'metadata':{'execution_purpose':'validation'}},
                     {'estimated_cost_usd':.1,'metadata':{'execution_purpose':'operation'}},{}])
    assert s['accounted_known_usd']==pytest.approx(.3)
    assert s['unknown_cost_requests']==1
    assert s['purpose_requests']=={'operation':1,'validation':1,'recovery':0,'legacy':1}

@pytest.mark.parametrize('status',[400,401,403,404,422])
def test_configuration_errors_do_not_retry(status):
    assert retry_guidance({'http_status':status})['retryable'] is False

@pytest.mark.parametrize('status',[429,500,503])
def test_transient_errors_are_conditional(status):
    assert retry_guidance({'http_status':status})['retryable'] is True

def test_reuse_identity_changes_with_cutoff_and_model(monkeypatch):
    day=datetime(2026,10,13,0,tzinfo=timezone.utc)
    first=checkpoint_identity(day,('NEWS','INSURANCE'))
    assert first==checkpoint_identity(day,('INSURANCE','NEWS'))
    assert first!=checkpoint_identity(day.replace(minute=30),('NEWS','INSURANCE'))
    monkeypatch.setenv('BRIEFING_ROUTINE_MODEL','changed')
    assert first!=checkpoint_identity(day,('NEWS','INSURANCE'))

def test_budget_is_advisory(monkeypatch):
    monkeypatch.setenv('BRIEFING_DAY_BUDGET_USD','1')
    assert budget_notice({'accounted_known_usd':.85},'day')['state']=='near'
    assert budget_notice({'accounted_known_usd':1.1},'day')['state']=='exceeded'
    monkeypatch.setenv('BRIEFING_DAY_BUDGET_USD','nan')
    assert budget_notice({},'day')['state']=='invalid'

def test_plan_is_not_false_total_cost_cap(monkeypatch):
    monkeypatch.setenv('BRIEFING_ENABLE_RESEARCH','true')
    assert request_plan('MARKET')['analysis_requests_max']==2
    assert '총비용 상한은 아닙니다' in request_plan('DAILY')['note']

def test_changed_article_content_blocks_paid_response_replay(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-test-key")
    monkeypatch.setenv("BRIEFING_ROUTINE_MODEL","synthetic-model")
    from test_briefing_analysis_recovery import event, row, client_with_http
    from modules.briefing.openai_analysis import OpenAIAnalysisClient, BriefingAnalysisError
    from unittest.mock import Mock
    e=event(1);record=[]
    client=client_with_http([row(e)], on_response=lambda r: record.append(deepcopy_record(r)))
    client.analyze('NEWS',[e])
    saved=record[0];saved['usage_logged']=True;saved['charge_uncertain']=False
    replay=OpenAIAnalysisClient(model=client.model, api_key='synthetic-test-key')
    replay.http=Mock();replay.cached_response=saved
    e.candidates[0].description='changed evidence'
    with pytest.raises(BriefingAnalysisError): replay.analyze('NEWS',[e])
    replay.http.post.assert_not_called()

def deepcopy_record(value):
    from copy import deepcopy
    return deepcopy(value)

def test_free_feed_checkpoint_is_reused_only_at_same_cutoff(monkeypatch):
    from modules.briefing.phase_b import run_phase_b
    from unittest.mock import Mock
    collect=Mock(return_value=([],{}));monkeypatch.setattr('modules.briefing.phase_b.collect_direct_sources',collect)
    saved={};at=datetime(2026,10,13,0,tzinfo=timezone.utc)
    run_phase_b(as_of=at,enable_web_discovery=False,direct_checkpoint=saved)
    run_phase_b(as_of=at,enable_web_discovery=False,direct_checkpoint=saved)
    assert collect.call_count==1
    run_phase_b(as_of=at.replace(minute=30),enable_web_discovery=False,direct_checkpoint=saved)
    assert collect.call_count==2
