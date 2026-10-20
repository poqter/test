"""Partial paid responses, strict identity and recovery; no live API calls."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest

from modules.briefing.models import AnalysisUsage, PhaseBResult, SharedEventCandidate, SourceCandidate
from modules.briefing.openai_analysis import BriefingAnalysisError, OpenAIAnalysisClient
from modules.briefing.phase_c import run_phase_c
from modules.briefing.repository import BriefingRepository
from modules.briefing.checkpoints import encode

NOW=datetime(2026,10,12,6,tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_paid_services(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('Unexpected HTTP')))
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-key')
    monkeypatch.setenv('BRIEFING_ROUTINE_MODEL','synthetic-model')


def event(i):
    host='mk.co.kr' if i%2 else 'hankyung.com'
    c=SourceCandidate(f'검수용 가상 문화 소식 {i}',f'https://{host}/synthetic/{i}',host,'synthetic','news',
        description='검수용 가상 뉴스의 본문입니다. 박물관의 전시 장소와 전시 기간 및 참여 작가 명단이 공개됐습니다.', published_at=NOW-timedelta(hours=1),freshness_tier='core_window',routed_profiles={'NEWS'},
        publisher_domain=host,canonical_url=f'https://{host}/synthetic/{i}')
    return SharedEventCandidate(f'{i:032x}',c.title,[c],{'NEWS'},c.published_at,c.published_at)


def row(e):
    return {'event_key':e.event_key,'importance_score':55,'category':'교육','issue_status':'보도',
        'title':e.canonical_title,'summary':'검수용 가상 기사입니다. 실제 보도가 아닙니다.',
        'why_important':'가상 배경 설명','impact_summary':'가상 영향 설명','action_state':'watch',
        'communication_state':'not_applicable','audience_segments':[],'recommended_expression':'',
        'check_first':'','avoid_expression':'','next_step':'','workspace_tool_codes':[],'confidence':'medium','essential_facts_complete':True,'headline_sufficient':False,
        'editorial_kind':'development','event_date':'','selection_reason':'검수 사실 확인',
        'duplicate_of':'','is_new_development':True,'scheduled_at':''}


def response(rows):
    return {'id':'synthetic-response','status':'completed','model':'synthetic-model',
        'usage':{'input_tokens':100,'output_tokens':50},
        'output_text':json.dumps({'events':rows,'market_flow':[]},ensure_ascii=False)}


def client_with_http(rows,on_response=None):
    client=OpenAIAnalysisClient(on_response=on_response)
    client.http=Mock()
    client.http.post.return_value=Mock(status_code=200,json=Mock(return_value=response(rows)))
    return client


def paid_record(events,rows):
    return {'profile_code':'NEWS','status':'validation_failed','provider_status':'completed',
        'requested_event_keys':[e.event_key for e in events],'usage_logged':True,'usage_available':True,
        'charge_uncertain':False,'usage':asdict(AnalysisUsage('synthetic-model',input_tokens=100,output_tokens=50)),
        'output_text_sample':response(rows)['output_text']}


def test_six_of_twenty_are_kept_once_without_fabricated_missing_articles():
    events=[event(i) for i in range(20)]
    selected=[row(e) for e in events[:6]]
    callback=Mock();client=client_with_http(selected,callback)
    phase=PhaseBResult(NOW,[c for e in events for c in e.candidates],events,[],{})
    result=run_phase_c(phase,analyzer=client,profile_codes=('NEWS',))
    assert len(result.analyses)==20 and len(result.eligible_analyses)==6
    missing=[r for r in result.analyses if r.profile_payload['analysis_missing']]
    assert len(missing)==14 and all(r.selection_tier=='excluded' and r.summary=='' for r in missing)
    assert result.omitted_by_profile['NEWS']==14
    client.http.post.assert_called_once();callback.assert_called_once()
    record=callback.call_args.args[0]
    assert record['result_status']=='partial' and len(record['missing_event_keys'])==14
    assert json.loads(record['output_text_sample'])['events']==selected
    schema=client.http.post.call_args.kwargs['json']['text']['format']['schema']['properties']['events']
    assert schema['minItems']==schema['maxItems']==20
    assert set(schema['items']['properties']['event_key']['enum'])=={e.event_key for e in events}


@pytest.mark.parametrize('bad',['duplicate','unknown','empty','category','blank','nan'])
def test_invalid_response_is_rejected_and_paid_output_is_retained(bad):
    events=[event(0),event(1)];rows=[row(e) for e in events]
    if bad=='duplicate':rows[1]['event_key']=rows[0]['event_key']
    if bad=='unknown':rows[1]['event_key']='unknown'
    if bad=='empty':rows=[]
    if bad=='category':rows[0]['category']='INVALID'
    if bad=='blank':rows[0]['summary']=' '
    if bad=='nan':rows[0]['importance_score']=float('nan')
    callback=Mock();client=client_with_http(rows,callback)
    with pytest.raises(BriefingAnalysisError):client.analyze('NEWS',events)
    callback.assert_called_once()
    assert callback.call_args.args[0]['output_text_sample']


def test_replay_revalidates_but_never_calls_or_logs_the_model_again():
    events=[event(i) for i in range(20)];cached=paid_record(events,[row(e) for e in events[:6]])
    before=deepcopy(cached);callback=Mock();client=OpenAIAnalysisClient(on_response=callback)
    client.cached_response=cached;client.http=Mock();client.before_request=Mock()
    rows,usage=client.analyze('NEWS',events)
    assert len(rows)==6 and usage.input_tokens==100 and cached==before
    client.http.post.assert_not_called();client.before_request.assert_not_called();callback.assert_not_called()


@pytest.mark.parametrize('bad',['identity','profile','billing','unlogged','unavailable','incomplete','truncated','invalid_json','unknown'])
def test_unusable_cache_cannot_trigger_a_replacement_paid_request(bad):
    events=[event(0),event(1)];cached=paid_record(events,[row(e) for e in events])
    if bad=='identity':cached['requested_event_keys']=['old-event']
    if bad=='profile':cached['profile_code']='INSURANCE'
    if bad=='billing':cached['charge_uncertain']=True
    if bad=='unlogged':cached['usage_logged']=False
    if bad=='unavailable':cached['usage_available']=False
    if bad=='incomplete':cached['provider_status']='incomplete'
    if bad=='truncated':cached['output_text_truncated']=True
    if bad=='invalid_json':cached['output_text_sample']='{"events":'
    if bad=='unknown':cached['output_text_sample']=response([{**row(events[0]),'event_key':'unknown'}])['output_text']
    callback=Mock();client=OpenAIAnalysisClient(on_response=callback);client.cached_response=cached
    client.http=Mock();client.before_request=Mock()
    with pytest.raises(BriefingAnalysisError):client.analyze('NEWS',events)
    client.http.post.assert_not_called();client.before_request.assert_not_called();callback.assert_not_called()


def test_empty_candidate_pool_is_free():
    client=OpenAIAnalysisClient();client.http=Mock()
    assert client.analyze('NEWS',[])[0]==[]
    client.http.post.assert_not_called()


def test_repository_recovers_legacy_paid_response_only_for_the_day_and_profile():
    events=[event(0),event(1)];cached=paid_record(events,[row(e) for e in events])
    repo=BriefingRepository('https://example.org','synthetic-key')
    repo._request=Mock(return_value=[{'metadata':{'failure_diagnostics':{'failure_details':{'analysis_response':cached}}}}])
    assert repo.analysis_recovery_response('2026-10-12','NEWS')==cached
    params=repo._request.call_args.kwargs['params']
    assert params['briefing_date']=='eq.2026-10-12' and params['profile_code']=='eq.NEWS'
    cached['charge_uncertain']=True
    assert repo.analysis_recovery_response('2026-10-12','NEWS') is None


@pytest.mark.parametrize('legacy',[False,True])
def test_runtime_reuses_paid_output_without_discovery_analysis_or_duplicate_usage(monkeypatch,legacy):
    from modules.briefing import runtime as rt
    events=[event(i) for i in range(20)]
    for e in events:e.candidates[0].metadata['profile_hints']=['NEWS']
    phase=PhaseBResult(NOW,[c for e in events for c in e.candidates],events,[],{},
        source_health={'feed_a':{'profiles':['NEWS'],'status':'ok'},'feed_b':{'profiles':['NEWS'],'status':'ok'}})
    cached=paid_record(events,[row(e) for e in events[:6]])
    saved={'phase_b':encode(phase)}
    if not legacy:saved['analysis_responses']={'NEWS':cached}
    repo=Mock();repo.ai_generation_enabled.return_value=True
    repo.profiles.return_value=[{'profile_code':'NEWS','is_enabled':True}]
    repo.create_job.return_value={'id':'job'};repo.next_attempt_no.return_value=1
    repo.analysis_recovery_response.return_value=cached if legacy else None
    counter=iter(range(1000))
    def insert(payload):return {'id':'synthetic-'+str(next(counter)),**payload}
    repo.get_or_create_briefing.return_value={'id':'b'};repo.next_revision_no.return_value=1
    repo.create_revision.side_effect=insert;repo.create_snapshot.side_effect=insert
    repo.upsert_event.side_effect=insert
    for name in ('insert_sources','insert_issues','insert_actions'):
        getattr(repo,name).side_effect=lambda rows:[insert(r) for r in rows]
    monkeypatch.setattr(rt,'run_phase_b',Mock(side_effect=AssertionError('Discovery must be reused')))
    monkeypatch.setattr(rt,'build_info',lambda:{'code_matches_release':True})
    before=Mock(side_effect=AssertionError('No paid reservation allowed'))
    result=rt.generate_and_store_briefings(repository=repo,profile_codes=('NEWS',),as_of=NOW,
        checkpoint=saved,save_checkpoint=lambda state:None,before_request=before)
    assert result.profiles[0].core_count==6 and 'NEWS' in saved['phase_c_by_profile']
    assert result.profiles[0].validation_status=='ok' and result.profiles[0].coverage_status=='healthy'
    snapshot=repo.create_snapshot.call_args.args[0]
    assert len(snapshot['content_payload']['issues'])==6
    assert all(i['summary'] for i in snapshot['content_payload']['issues'])
    assert len(snapshot['external_content_payload']['issues'])==6
    assert result.diagnostics['request_progress']['reused_analysis_profiles']==['NEWS']
    repo.log_api_usage.assert_not_called();before.assert_not_called();repo.create_snapshot.assert_called_once()
    repo.publish_revision.assert_not_called()


def test_usage_confirmed_response_enters_checkpoint_before_local_validation(monkeypatch):
    from modules.briefing import runtime as rt
    events=[event(0),event(1)]
    phase=PhaseBResult(NOW,[c for e in events for c in e.candidates],events,[],{})
    saved={'phase_b':encode(phase),'pending_request':{'kind':'analysis'}};copies=[]
    repo=Mock();repo.ai_generation_enabled.return_value=True
    repo.profiles.return_value=[{'profile_code':'NEWS','is_enabled':True}]
    repo.create_job.return_value={'id':'job'};repo.next_attempt_no.return_value=1
    repo.analysis_recovery_response.return_value=None
    bad=[{**row(events[0]),'event_key':'UNKNOWN'}]
    def create_client(on_response):return client_with_http(bad,on_response)
    monkeypatch.setattr('modules.briefing.openai_analysis.OpenAIAnalysisClient',create_client)
    monkeypatch.setattr(rt,'build_info',lambda:{'code_matches_release':True})
    with pytest.raises(rt.BriefingRunError):
        rt.generate_and_store_briefings(repository=repo,profile_codes=('NEWS',),as_of=NOW,
            checkpoint=saved,save_checkpoint=lambda state:copies.append(deepcopy(state)))
    assert any(s.get('analysis_responses',{}).get('NEWS',{}).get('usage_logged') for s in copies)
    assert not saved.get('pending_request') and not saved['charge_uncertain']
    assert saved['analysis_responses']['NEWS']['status']=='validation_failed'
    repo.log_api_usage.assert_called_once();repo.create_snapshot.assert_not_called()
