"""Release gates, financial identity, privacy and idempotency; no paid services."""
import json
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from unittest.mock import Mock
from io import BytesIO
from pathlib import Path
import pytest
from launch_fixtures import AS_OF,observations,content,packet
from modules.briefing.business_calendar import calendar_rows,is_business_day
from modules.briefing.market_metrics import validated_metrics
from modules.briefing.market_providers import eod_observation,treasury_observation,ecos_observation,collect_provider_observations
from modules.briefing.public_body import customer_body,staff_body,public_html,metric_change,metric_date
from modules.briefing.costs import estimate_cost,usage_summary
from modules.briefing.repository import BriefingRepository,BriefingRepositoryError
from modules.briefing.scheduler import generate_group,publish_ready
from modules.briefing.corrections import corrected_content,apply_correction

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('Unexpected HTTP')))

@pytest.mark.parametrize('day,expected',[(date(2026,10,9),False),(date(2026,10,5),False),(date(2026,10,10),False),(date(2026,10,8),True),(date(2026,6,3),False)])
def test_korean_holiday_observation_days(day,expected):assert is_business_day(day)==expected

def test_temporary_holiday_excluded(monkeypatch):
    monkeypatch.setenv('BRIEFING_EXTRA_HOLIDAYS_JSON','["2026-10-08"]');assert not is_business_day(date(2026,10,8))

@pytest.mark.parametrize('field,value',[('value',float('nan')),('value',0),('instrument_code','QQQ'),('unit','USD'),('observed_at','2026-10-10T10:00:00+00:00'),('previous_observed_at','2026-10-10T10:00:00+00:00'),('source_url','http://127.0.0.1/')])
def test_bad_observation_does_not_complete_six(field,value):
    rows=observations();rows[0][field]=value;result=validated_metrics(rows,AS_OF)
    assert not result['complete'] and 'KOSPI' in result['missing']

def test_conflicting_same_observation_is_not_arbitrarily_chosen():
    rows=observations();different={**rows[0],'value':12000};result=validated_metrics(rows+[different],AS_OF)
    assert 'KOSPI' in result['conflicted'] and not result['complete']

def test_license_missing_keeps_internal_values_and_closes_customer():
    result=validated_metrics(observations(False),AS_OF);assert result['complete'] and not result['external_complete']
    source=content('MARKET',8,False);assert len(staff_body(source)['market_metrics'])==6
    assert customer_body(source)['market_metrics']==[]

def test_change_units_and_daily_date_precision():
    rows=validated_metrics(observations(),AS_OF)['items']
    assert metric_change(rows[-1]).endswith('%p') and metric_change(rows[-2]).endswith('원')
    assert metric_change(rows[0]).endswith('%')
    assert metric_date({**rows[-1],'as_of_precision':'date'})=='2026-10-08 관측일'

@pytest.mark.parametrize('code,zone', [('KOSPI','+09:00'),('SP500','-04:00'),('NASDAQ_COMPOSITE','-04:00')])
def test_provider_closes_use_the_actual_market_zone(code,zone):
    row=eod_observation(code,[{'date':'2026-10-08','close':120},{'date':'2026-10-07','close':100}],AS_OF,source_url='https://example.org')
    assert row['observed_at'].endswith(zone) and row['previous_value']==100

def test_future_close_not_taken_and_us_dst_winter():
    row=eod_observation('SP500',[{'date':'2026-11-03','close':300},{'date':'2026-11-02','close':120},{'date':'2026-10-30','close':100}],datetime(2026,11,3,12,tzinfo=timezone.utc))
    assert row['observed_at'].startswith('2026-11-02') and row['observed_at'].endswith('-05:00')

def treasury_xml(points):
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:d="urn:d">'+''.join(f'<entry><d:NEW_DATE>{day}T00:00:00</d:NEW_DATE><d:BC_10YEAR>{value}</d:BC_10YEAR></entry>' for day,value in points)+'</feed>').encode()

def test_treasury_handles_zero_and_daily_precision():
    row=treasury_observation(treasury_xml([('2026-10-07',0),('2026-10-08',.1)]),AS_OF)
    assert row['previous_value']==0 and row['as_of_precision']=='date' and not row['external_allowed']

def test_treasury_year_boundary_merges_observations(monkeypatch):
    monkeypatch.setenv('BRIEFING_MARKET_PROVIDER','fmp_treasury');monkeypatch.setenv('FMP_API_KEY','synthetic-only')
    from modules.briefing import market_providers as p
    def download(url,params=None,http=None):
        if 'index-list' in url:return json.dumps([{'symbol':s,'name':n} for s,n in [('^KS11','KOSPI'),('^KQ11','KOSDAQ'),('^GSPC','S&P 500'),('^IXIC','NASDAQ Composite')]]).encode()
        if 'treasury.gov' in url:return treasury_xml([('2026-12-31',4.1)] if params['field_tdr_date_value']=='2026' else [('2027-01-04',4.2)])
        return json.dumps([{'symbol':params['symbol'],'date':'2027-01-04','close':110},{'symbol':params['symbol'],'date':'2026-12-31','close':100}]).encode()
    monkeypatch.setattr(p,'_download',download)
    rows,details=p.collect_provider_observations(datetime(2027,1,4,23,tzinfo=timezone.utc))
    rate=next(r for r in rows if r['code']=='US10Y');assert rate['value']==4.2 and rate['previous_value']==4.1

def test_catalog_rejects_nasdaq100_substitution(monkeypatch):
    monkeypatch.setenv('BRIEFING_MARKET_PROVIDER','fmp_treasury');monkeypatch.setenv('FMP_API_KEY','synthetic-only')
    from modules.briefing import market_providers as p
    def download(url,params=None,http=None):
        if 'index-list' in url:return b'[{"symbol":"^NDX","name":"NASDAQ 100"}]'
        if 'treasury.gov' in url:return treasury_xml([('2026-10-07',4.1),('2026-10-08',4.2)])
        return b'[]'
    monkeypatch.setattr(p,'_download',download);rows,details=p.collect_provider_observations(AS_OF)
    assert details['metrics']['NASDAQ_COMPOSITE']=='instrument_not_verified' and not any(r['code']=='NASDAQ_COMPOSITE' for r in rows)

def test_ecos_ignores_today_and_wrong_instrument():
    row=ecos_observation({'StatisticSearch':{'row':[{'ITEM_CODE1':'0000001','TIME':d,'DATA_VALUE':v} for d,v in [('20261009','1400'),('20261008','1300'),('20261007','1290')]]}},AS_OF)
    assert row['value']==1300 and row['as_of_precision']=='date'

def test_customer_insurance_excludes_sales_and_internal_counsel():
    source=content('INSURANCE',4);source['issues'][0]['category']='영업·채널';source['issues'][1]['communication_state']='internal_check'
    safe=customer_body(source);assert len(safe['issues'])==2 and len(staff_body(source)['issues'])==4
    assert 'internal_secret' not in json.dumps(safe,ensure_ascii=False) and 'conversation_payload' not in json.dumps(safe)

def test_reader_escapes_names_article_text_and_has_first_response_og():
    p=packet();p['sender']['name']='<script>leak()</script>';p['body']['issues'][0]['summary']='<img onerror="leak()">'
    html=public_html(p,canonical_url='https://example.org/',image_url='https://example.org/image',pdf_url='https://example.org/pdf')
    assert '<script>leak()' not in html and '<img onerror=' not in html
    assert 'property="og:title"' in html and '&lt;script&gt;leak()&lt;/script&gt; 팀장' in html
    assert html.count('원문 읽기 ↗')==10 and '큰 글자로 읽기' in html and 'PDF 저장' in html
    assert 'internal_secret' not in html

def test_global_ai_off_stops_before_lock_or_source_call(monkeypatch):
    repo=Mock();repo.ai_generation_enabled.return_value=False
    result=generate_group(repo,date(2026,10,9),'DAILY')
    assert result['reason']=='platform_ai_service_disabled';repo.claim_run.assert_not_called();repo.reserve_request.assert_not_called()

def test_market_missing_rechecked_without_spending_api(monkeypatch):
    monkeypatch.setenv('BRIEFING_MARKET_OBSERVATIONS_JSON','[]');repo=Mock();repo.ai_generation_enabled.return_value=True
    repo.claim_run.return_value={'claimed':True,'checkpoint':{'market_observations':{'complete':False,'missing':['KOSPI']}}}
    result=generate_group(repo,date(2026,10,9),'MARKET',retry=True)
    assert result['reason']=='market_observations_incomplete';repo.reserve_request.assert_not_called()

def test_uncertain_request_blocks_recovery(monkeypatch):
    repo=Mock();repo.ai_generation_enabled.return_value=True;repo.claim_run.return_value={'claimed':True,'checkpoint':{'pending_request':{'kind':'analysis'}}}
    assert generate_group(repo,date(2026,10,9),'DAILY',retry=True)['reason']=='unconfirmed_api_request'
    repo.reserve_request.assert_not_called()

def test_org_approval_off_does_not_change_shadow_or_publish():
    repo=Mock();repo.profiles.return_value=[{'profile_code':'NEWS','run_mode':'shadow'}];repo.operating_policy.return_value={'automatic_publication_enabled':False}
    repo.bundle_for_date.return_value={'briefing':{'id':'b'},'revision':{'id':'r','publication_status':'draft','validation_status':'ok','coverage_status':'healthy'},
        'snapshot':{'content_payload':content(),'qa_payload':{'internal_body_ready':True}}}
    result=publish_ready(repo,date(2026,10,8),('NEWS',));assert result[0]['status']=='organization_approval_required'
    repo.publish_revision.assert_not_called();repo._request.assert_not_called()

def test_cost_counts_reasoning_as_part_of_output_and_cached_input_once(monkeypatch):
    rate={'input_per_million':2,'cached_input_per_million':1,'output_per_million':4,'search_per_thousand':10,
          'source_url':'https://example.org/pricing','checked_at':'2026-10-09'}
    monkeypatch.setenv('BRIEFING_PRICE_TABLE_JSON',json.dumps({'synthetic-model':rate}))
    result=estimate_cost({'model_name':'synthetic-model','input_tokens':1000,'cached_input_tokens':200,'output_tokens':500,'reasoning_tokens':300,'search_actions':1})
    assert result==pytest.approx(.0138)
    monkeypatch.delenv('BRIEFING_PRICE_TABLE_JSON');assert estimate_cost({'model_name':'synthetic-model'}) is None
    assert usage_summary([{'metadata':{'charge_uncertain':True}}])['unknown_cost_requests']==1

def test_correction_does_not_mutate_original_evidence():
    original=content();copy=deepcopy(original);updated=corrected_content(original,'event-0',{'summary':'정정된 요약'},'오탈자 수정')
    assert original==copy and updated['issues'][0]['summary']=='정정된 요약'
    assert updated['issues'][0]['sources']==original['issues'][0]['sources'] and updated['as_of']==original['as_of']
    with pytest.raises(ValueError):corrected_content(original,'event-0',{'sources':[]},'사유')
    with pytest.raises(ValueError):corrected_content(original,'event-0',{'summary':'정정'},'')

def test_repository_latest_summaries_and_cost_status_are_separate():
    repo=BriefingRepository('https://example.org','synthetic-key');repo._request=Mock(return_value=[])
    assert repo.latest_summaries(['NEWS'])=={'NEWS':None}
    assert repo.cost_status()['today']['requests']==0
    assert repo._request.call_args.kwargs['params']['select'].startswith('profile_code,model_name')

def test_share_policy_blocks_before_assets():
    repo=BriefingRepository('https://example.org','synthetic-key');repo.operating_policy=Mock(return_value={'external_sharing_approved':False});repo._request=Mock()
    with pytest.raises(BriefingRepositoryError):repo.create_share('r','u',{'body':'untrusted'})
    repo._request.assert_not_called()

def test_share_reads_live_rpc_not_a_stale_snapshot():
    repo=BriefingRepository('https://example.org','synthetic-key');repo._request=Mock(return_value=None)
    assert repo.public_share('x'*43) is None
    assert repo._request.call_args.args[1]=='/rest/v1/rpc/hwarang_read_public_briefing'
    repo._request.reset_mock();assert repo.public_share('invalid') is None;repo._request.assert_not_called()

def test_share_uses_server_registered_name_and_private_assets():
    repo=BriefingRepository('https://example.org','synthetic-key');repo.operating_policy=Mock(return_value={'external_sharing_approved':True});repo.public_endpoint_ready=Mock(return_value=True)
    repo._snapshot_for_revision=Mock(return_value={'content_payload':content()});repo._upload_share_assets=Mock();repo.public_base_url=Mock(return_value='https://example.org/reader')
    saved={}
    def request(method,path,**kwargs):
        if path.endswith('hwarang_briefing_revisions'):return [{'id':'r','briefing_id':'b','publication_status':'published','external_share_allowed':True,'external_qa_passed':True,'revision_no':1}]
        if path.endswith('hwarang_briefings'):return [{'id':'b','briefing_date':'2026-10-09','current_published_revision_id':'r'}]
        if path.endswith('profiles'):return [{'display_name':'등록 이름','position_code':'team','is_active':True}]
        if path.endswith('positions'):return [{'display_name':'팀장'}]
        if method=='POST':saved.update(kwargs['json']);return None
        return []
    repo._request=request;token,p=repo.create_share('r','u',{'sender':{'name':'위조','position':'대표'}})
    assert p['sender']=={'name':'등록 이름','position':'팀장'} and '위조' not in p['rendered_html']
    assert saved['token']==token and len(p['asset_version'])==24
    repo._upload_share_assets.assert_called_once()

def test_rss_defaults_survive_legacy_official_only_config(monkeypatch):
    from modules.briefing.direct_sources import load_direct_source_specs_from_env
    monkeypatch.setenv('BRIEFING_DIRECT_SOURCES_JSON',json.dumps([{'source_code':'mois','source_name':'행안부','url':'https://www.mois.go.kr/rss/'}]))
    specs=load_direct_source_specs_from_env();assert len(specs)==9 and any(s.source_code=='insurance_journal' for s in specs)
    monkeypatch.setenv('BRIEFING_DEFAULT_NEWS_FEEDS','false');assert len(load_direct_source_specs_from_env())==1

@pytest.mark.parametrize('raw,reason',[(b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///secret">]><rss/>','unsupported_xml_declaration'),(b'<html>not RSS</html>','not_rss_or_atom')])
def test_rss_entity_or_page_is_rejected(raw,reason):
    from modules.briefing.direct_sources import collect_direct_source,DirectSourceSpec
    response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.status_code=200;response.headers={};response.iter_content.return_value=[raw]
    session=Mock();session.get.return_value=response
    with pytest.raises(ValueError,match=reason):collect_direct_source(DirectSourceSpec('news','news','https://example.org/rss'),session=session,destination_check=lambda u:True)

def test_rss_korean_timestamp_and_cross_publisher_article():
    from modules.briefing.direct_sources import _rss_candidates,DirectSourceSpec
    from xml.etree import ElementTree as ET
    raw='<rss><channel><item><title>가상 기사</title><link>https://insjournal.co.kr/article/1</link><pubDate>2026-10-09 06:00:00</pubDate></item><item><title>다른 사이트</title><link>https://attacker.example.org/</link><pubDate>Fri, 09 Oct 2026 06:00:00 +0900</pubDate></item></channel></rss>'
    rows=_rss_candidates(ET.fromstring(raw),DirectSourceSpec('ins','보험저널','https://www.insjournal.co.kr/rss/allArticle.xml',source_kind='news'),AS_OF)
    assert len(rows)==1 and rows[0].published_at.isoformat()=='2026-10-08T21:00:00+00:00'

def test_publisher_round_robin_and_display_caps():
    from modules.briefing.phase_c import run_phase_c
    from modules.briefing.models import SourceCandidate,SharedEventCandidate,PhaseBResult,AnalysisUsage
    candidates=[];events=[]
    for i in range(36):
        host='hankyung.com' if i<30 else 'mk.co.kr'
        c=SourceCandidate(f'가상 문화 기사 {i}',f'https://{host}/article/{i}',host,'synthetic','news',published_at=AS_OF,
            publisher_domain=host,freshness_tier='core_window',routed_profiles={'NEWS'})
        candidates.append(c);events.append(SharedEventCandidate(str(i),c.title,[c],{'NEWS'},AS_OF,AS_OF))
    class Analyzer:
        def analyze(self,code,rows):
            self.rows=rows
            return [{'event_key':r.event_key,'importance_score':80,'category':'사회·안전','confidence':'high','summary':'가상 기사 요약'} for r in rows],AnalysisUsage()
    analyzer=Analyzer();result=run_phase_c(PhaseBResult(AS_OF,candidates,events,[],{}),analyzer=analyzer)
    assert len(analyzer.rows)==20 and sum(r.candidates[0].publisher_domain=='mk.co.kr' for r in analyzer.rows)==6
    assert sum(r.selection_tier=='core' for r in result.analyses)==1 and sum(r.selection_tier!='excluded' for r in result.analyses)==10

def test_full_three_profile_pipeline_saves_same_facts_and_resumes_without_ai(monkeypatch):
    from modules.briefing import runtime as rt
    from modules.briefing.models import SourceCandidate,SharedEventCandidate,PhaseBResult,AnalysisUsage
    from modules.briefing.openai_analysis import OpenAIAnalysisClient
    from dataclasses import asdict
    candidates=[];events=[]
    for code in ('NEWS','MARKET','INSURANCE'):
        for i in range(14):
            host='hankyung.com' if i%2 else 'mk.co.kr'
            c=SourceCandidate(f'검수용 가상 소식 {code} {i}',f'https://{host}/article/{code}/{i}',host,'synthetic','news',
                published_at=AS_OF-timedelta(hours=1),publisher_domain=host,freshness_tier='core_window',
                routed_profiles={code},canonical_url=f'https://{host}/article/{code}/{i}',metadata={'profile_hints':[code]})
            candidates.append(c);events.append(SharedEventCandidate(code+str(i),c.title,[c],{code},c.published_at,c.published_at))
    phase=PhaseBResult(AS_OF,candidates,events,[],{},source_health={code:{'profiles':[code],'status':'ok'} for code in ('NEWS','MARKET','INSURANCE')})
    monkeypatch.setattr(rt,'run_phase_b',Mock(return_value=phase));monkeypatch.setattr(rt,'collect_metrics',Mock(return_value=validated_metrics(observations(False),AS_OF)))
    calls=[]
    class Analyzer:
        market_metrics=[];market_flow=[];before_request=None
        def __init__(self,on_response=None):self.on_response=on_response
        def analyze(self,code,rows):
            calls.append(code)
            if code=='MARKET':self.market_flow=[{'text':str(i)+' 검수용 해설','fact_refs':['metric:KOSPI']} for i in range(3)]
            usage=AnalysisUsage('synthetic-model',input_tokens=100,output_tokens=30)
            self.on_response({'profile_code':code,'usage':asdict(usage),'usage_available':True,'status':'completed'})
            return [{'event_key':r.event_key,'importance_score':80-i,'confidence':'high','category':'소비자·사회이슈' if code=='INSURANCE' else '사회·안전',
                'title':r.canonical_title,'summary':'검수용 가상 기사 요약','why_important':'확인된 사실의 설명','impact_summary':'조건을 붙인 영향',
                'communication_state':'customer_ready','action_state':'watch'} for i,r in enumerate(rows)],usage
    monkeypatch.setattr('modules.briefing.openai_analysis.OpenAIAnalysisClient',Analyzer)
    repo=Mock();repo.ai_generation_enabled.return_value=True;repo.profiles.return_value=[{'profile_code':c,'is_enabled':True,'run_mode':'shadow'} for c in ('NEWS','MARKET','INSURANCE')]
    seq={'value':0};snaps=[]
    def insert(p):seq['value']+=1;return {'id':'id'+str(seq['value']),**p}
    repo.next_attempt_no.return_value=1;repo.next_revision_no.return_value=1
    repo.create_job.side_effect=insert;repo.create_revision.side_effect=insert;repo.upsert_event.side_effect=insert
    def snapshot(p):r=insert(p);snaps.append(r);return r
    repo.create_snapshot.side_effect=snapshot;repo.get_or_create_briefing.side_effect=lambda code,day,kind:{'id':code,'briefing_date':str(day)}
    for name in ('insert_sources','insert_issues','insert_actions'):getattr(repo,name).side_effect=lambda rows:[insert(r) for r in rows]
    saved={};result=rt.generate_and_store_briefings(repository=repo,profile_codes=('NEWS','MARKET','INSURANCE'),as_of=AS_OF,checkpoint=saved,save_checkpoint=lambda state:None)
    assert len(result.profiles)==3 and sorted(calls)==['INSURANCE','MARKET','NEWS']
    bycode={s['content_payload']['profile_code']:s for s in snaps}
    assert len(bycode['NEWS']['content_payload']['issues'])==10 and len(bycode['MARKET']['content_payload']['issues'])==8
    assert all(s['qa_payload']['internal_body_ready'] for s in snaps) and not bycode['MARKET']['qa_payload']['public_body_ready']
    assert len(bycode['MARKET']['content_payload']['market_flow'])==3
    assert len(bycode['MARKET']['content_payload']['market_metrics']['items'])==6
    calls.clear();snaps.clear();rt.generate_and_store_briefings(repository=repo,profile_codes=('NEWS','MARKET','INSURANCE'),as_of=AS_OF,checkpoint=saved,save_checkpoint=lambda state:None)
    assert not calls and not snaps;repo.publish_revision.assert_not_called()

def test_correction_new_revision_same_token_and_original_sender():
    repo=Mock();src=content(count=2);old=deepcopy(src)
    bundle={'briefing':{'id':'b','briefing_date':'2026-10-09'},'revision':{'id':'old','publication_status':'published','coverage_status':'healthy'},
        'snapshot':{'id':'snap','content_payload':src,'qa_payload':{'public_body_ready':True}},'issue_sources':[]}
    repo.next_revision_no.return_value=2;repo.create_revision.side_effect=lambda p:{'id':'new',**p};repo.create_snapshot.side_effect=lambda p:{'id':'new-snap',**p}
    repo.public_base_url.return_value='https://example.org/functions/v1/briefing-public'
    def request(method,path,**kwargs):
        if path.endswith('hwarang_briefings'):return [{'current_published_revision_id':'old'}]
        if method=='GET' and path.endswith('hwarang_briefing_public_shares'):return [{'token':'z'*43,'public_packet':{'sender':{'name':'최초 등록 이름','position':'설계사'}}}]
        return []
    repo._request.side_effect=request;repo._first.side_effect=BriefingRepository._first;repo.insert_sources.return_value=[];repo.insert_issues.return_value=[]
    apply_correction(repo,bundle,'event-0',{'summary':'정정된 요약'},'표현 정정','manager')
    assert src==old and repo.create_revision.call_args.args[0]['revision_type']=='correction'
    token,p=repo._upload_share_assets.call_args.args;assert token=='z'*43 and p['sender']['name']=='최초 등록 이름'
    assert p['body']['issues'][0]['summary']=='정정된 요약' and p['edition']['number']==2 and '정정 ' in p['rendered_html']
    assert any(call.args[0]=='PATCH' and call.kwargs['json'].get('revision_id')=='new' for call in repo._request.call_args_list)


def test_correction_form_can_submit_a_new_reason():
    from streamlit.testing.v1 import AppTest
    script='''
import streamlit as st
from unittest.mock import Mock
from modules.briefing.operations_ui import render_correction
bundle={'revision':{'id':'r','publication_status':'published'},'snapshot':{'content_payload':{'issues':[{'title':'소식','summary':'요약','event_key':'e'}]}}}
render_correction(Mock(),bundle)
'''
    app=AppTest.from_string(script).run();assert not app.exception
    assert not next(b for b in app.button if b.label=='새 정정판 공개').disabled

def test_disabled_profile_is_never_automatically_published():
    repo=Mock();repo.profiles.return_value=[{'profile_code':'NEWS','is_enabled':False,'run_mode':'auto'}];repo.operating_policy.return_value={'automatic_publication_enabled':True}
    assert publish_ready(repo,date(2026,10,8),('NEWS',))[0]['status']=='disabled'
    repo.bundle_for_date.assert_not_called();repo.publish_revision.assert_not_called()

def test_no_public_url_does_not_create_an_unusable_streamlit_link(monkeypatch):
    monkeypatch.delenv('BRIEFING_PUBLIC_BASE_URL',raising=False)
    repo=BriefingRepository('https://example.org','synthetic')
    assert not repo.public_endpoint_ready()
    with pytest.raises(BriefingRepositoryError,match='BRIEFING_PUBLIC_BASE_URL'):repo.public_base_url()

def test_unknown_usage_stops_before_next_profile(monkeypatch):
    from modules.briefing import runtime as rt
    from modules.briefing.models import SourceCandidate,SharedEventCandidate,PhaseBResult
    c=SourceCandidate('검수용 문화 소식','https://example.org/news','검수용 출처','synthetic','news',published_at=AS_OF,freshness_tier='core_window',routed_profiles={'NEWS','INSURANCE'})
    phase=PhaseBResult(AS_OF,[c],[SharedEventCandidate('event',c.title,[c],{'NEWS','INSURANCE'},AS_OF,AS_OF)],[],{})
    monkeypatch.setattr(rt,'run_phase_b',Mock(return_value=phase));calls=[]
    class Analyzer:
        before_request=None
        def __init__(self,on_response=None):self.callback=on_response
        def analyze(self,code,rows):
            calls.append(code);self.callback({'profile_code':code,'usage_available':False,'usage':None,'status':'completed'})
            raise AssertionError('Billing guard should already stop this request')
    monkeypatch.setattr('modules.briefing.openai_analysis.OpenAIAnalysisClient',Analyzer)
    repo=Mock();repo.ai_generation_enabled.return_value=True;repo.profiles.return_value=[{'profile_code':code,'is_enabled':True} for code in ('NEWS','INSURANCE')]
    repo.create_job.side_effect=lambda p:{'id':p['profile_code'],**p};repo.next_attempt_no.return_value=1
    saved={}
    with pytest.raises(rt.BriefingRunError,match='추가 유료 호출'):
        rt.generate_and_store_briefings(repository=repo,profile_codes=('NEWS','INSURANCE'),as_of=AS_OF,checkpoint=saved,save_checkpoint=lambda state:None)
    assert len(calls)==1 and saved['charge_uncertain'] and repo.log_api_usage.call_count==1
    repo.create_snapshot.assert_not_called()

@pytest.mark.parametrize('code,count',[('NEWS',10),('MARKET',8)])
def test_pdf_keeps_each_article_and_original_link_on_same_page(code,count):
    from modules.briefing.public_body import public_pdf
    from pypdf import PdfReader
    reader=PdfReader(BytesIO(public_pdf(packet(code,count))))
    seen=[]
    for page in reader.pages:
        text=page.extract_text() or ''
        urls=[str(a.get_object().get('/A',{}).get('/URI','')) for a in page.get('/Annots',[])]
        for i in range(count):
            if f'검수용 가상 소식 {i+1} ·' in text:
                seen.append(i);assert any(url.endswith('/article/'+str(i)) for url in urls)
    assert sorted(seen)==list(range(count)) and '검수용 이름 팀장' in reader.pages[0].extract_text()

@pytest.mark.parametrize('key,bearer',[('sb_secret_synthetic',False),('synthetic-legacy-jwt',True)])
def test_server_key_headers_follow_supabase_key_type(key,bearer):
    repo=BriefingRepository('https://example.org',key);headers=repo.server_headers()
    assert headers['apikey']==key and ('Authorization' in headers)==bearer

def test_one_paid_validation_does_not_enable_scheduled_generation():
    repo=Mock();repo.operating_policy.return_value={'scheduled_generation_enabled':False}
    result=generate_group(repo,date(2026,10,9),'DAILY')
    assert result=={'status':'skipped','reason':'scheduled_generation_paused'}
    repo.claim_run.assert_not_called();repo.reserve_request.assert_not_called();repo.ai_generation_enabled.assert_not_called()

@pytest.mark.parametrize('field',['previous_observed_at','provider','reference_definition'])
def test_incomplete_external_metric_contract_keeps_customer_closed(field):
    rows=observations();rows[0].pop(field);result=validated_metrics(rows,AS_OF)
    assert result['complete'] and not result['external_complete']
