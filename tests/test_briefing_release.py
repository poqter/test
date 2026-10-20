"""Release behavior: article-only MARKET and same-date combined sharing, offline."""
from copy import deepcopy
from datetime import date, datetime, timezone
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
from launch_fixtures import content
from modules.briefing.sharing import build_combined_packet, combine_bodies
from modules.briefing.runtime import body_quality_ready
from modules.briefing.repository import BriefingRepository, BriefingRepositoryError
from modules.briefing.scheduler import generate_group, publish_ready


def bundle(code, day='2026-10-09'):
    body=content(code,3)
    for i,row in enumerate(body['issues']):
        row['event_key']=code+str(i)
        for src in row['sources']:src['url'] += '/'+code
    return {'briefing':{'id':code,'profile_code':code,'briefing_date':day},
        'revision':{'id':'rev-'+code,'revision_no':1,'publication_status':'published',
            'validation_status':'ok','coverage_status':'healthy','external_qa_passed':True,'external_share_allowed':True},
        'snapshot':{'id':'snap-'+code,'content_payload':body,
                    'qa_payload':{'internal_body_ready':True,'public_body_ready':True}}}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('Unexpected live HTTP')))


def test_combined_projection_deduplicates_and_excludes_internal_insurance():
    bundles=[bundle(code) for code in ('MARKET','NEWS','INSURANCE')]
    duplicate=deepcopy(bundles[0]['snapshot']['content_payload']['issues'][0])
    bundles[1]['snapshot']['content_payload']['issues'].append(duplicate)
    bundles[2]['snapshot']['content_payload']['issues'][0]['category']='영업·채널'
    packet=build_combined_packet(bundles,{'name':'검수용 이름','position':'팀장'},'https://example.org','x'*43)
    assert len(packet['body']['issues'])==8
    assert len(packet['components'])==3 and len(packet['body']['market_metrics'])==6
    assert 'internal_secret' not in str(packet) and 'conversation_payload' not in str(packet)
    assert '<details><summary>해설과 영향' not in packet['rendered_html']
    assert '배경과 영향' not in packet['rendered_html'] and '팀장' in packet['rendered_html']


def test_combined_dates_must_match():
    body=combine_bodies([bundle('NEWS'),bundle('MARKET','2026-10-08')])
    assert {s['briefing_date'] for s in body['sections']}=={'2026-10-08','2026-10-09'}


@pytest.mark.parametrize('defect',['empty','summary','source','date'])
def test_public_quality_never_passes_missing_evidence(defect):
    body=content('NEWS',1)
    if defect=='empty':body['issues']=[]
    elif defect=='summary':body['issues'][0]['summary']=''
    elif defect=='source':body['issues'][0]['sources'][0]['url']='javascript:alert(1)'
    else:body['issues'][0]['sources'][0]['published_at']=None
    assert not body_quality_ready(body)


def test_one_eligible_article_is_not_a_fill_quota():
    assert body_quality_ready(content('NEWS',1))


def test_latest_complete_date_intersection_does_not_mix_days():
    repo=BriefingRepository('https://example.org','synthetic')
    def history(code,**kwargs):
        return [bundle(code,day) for day in (['2026-10-09','2026-10-08'] if code!='INSURANCE' else ['2026-10-08'])]
    repo.history=history
    assert repo.latest_complete_customer_date()=='2026-10-08'


def test_create_combined_validates_saved_sections_and_uses_atomic_registration():
    repo=BriefingRepository('https://example.org','synthetic')
    repo.operating_policy=lambda:{'external_sharing_approved':True}
    repo.bundle_for_date=lambda code,day:bundle(code,day)
    repo.public_endpoint_ready=lambda:True
    repo.public_base_url=lambda:'https://example.org'
    repo._upload_share_assets=Mock()
    def request(method,path,**kwargs):
        if path.endswith('/profiles'):return [{'display_name':'검수용 이름','position_code':'TEAM','is_active':True}]
        if path.endswith('/positions'):return [{'display_name':'팀장'}]
        return []
    repo._request=Mock(side_effect=request)
    token,packet=repo.create_combined_share('2026-10-09',('NEWS','MARKET'),'user')
    assert len(packet['components'])==2
    registration=repo._request.call_args
    assert registration.args[1].endswith('hwarang_register_combined_share')
    assert registration.kwargs['json']['p_revisions']==['rev-MARKET','rev-NEWS']
    assert repo._upload_share_assets.call_count==1


def test_market_scheduler_never_fetches_metrics(monkeypatch):
    collect=Mock(side_effect=AssertionError('Metrics removed'))
    monkeypatch.setattr('modules.briefing.market_metrics.collect_metrics',collect)
    repo=Mock();repo.operating_policy.return_value={'scheduled_generation_enabled':True}
    repo.claim_run.return_value={'claimed':True,'checkpoint':{}}
    generate=Mock(return_value=Mock(profiles=[]))
    monkeypatch.setattr('modules.briefing.scheduler.generate_and_store_briefings',generate)
    assert generate_group(repo,date(2026,10,9),'MARKET')['status']=='completed'
    collect.assert_not_called()


def test_article_market_publish_has_no_daily_manual_approval():
    repo=Mock();repo.profiles.return_value=[{'profile_code':'MARKET','run_mode':'auto'}]
    repo.operating_policy.return_value={'automatic_publication_enabled':True}
    saved=bundle('MARKET');saved['revision']['publication_status']='draft'
    saved['snapshot']['content_payload']['market_metrics']={}
    repo.bundle_for_date.return_value=saved
    assert publish_ready(repo,date(2026,10,9),('MARKET',))==[{'profile':'MARKET','status':'published'}]
    repo.publish_revision.assert_called_once_with('MARKET','rev-MARKET')


def test_combined_share_button_and_pdf_work_without_ai(monkeypatch):
    import modules.briefing.briefing_center as center
    saved=[bundle(code) for code in ('MARKET','NEWS','INSURANCE')]
    packet=build_combined_packet(saved,{'name':'검수用 이름','position':'팀장'},'https://example.org','x'*43)
    repo=Mock();repo.latest_complete_customer_date.return_value='2026-10-09'
    repo.public_base_url.return_value='https://example.org'
    repo.operating_policy.return_value={'external_sharing_approved':True}
    repo.customer_bundle_for_share.side_effect=lambda code,day:next(b for b in saved if b['briefing']['profile_code']==code)
    repo.create_combined_share.return_value=('x'*43,packet)
    monkeypatch.setattr(center,'_repo',lambda:repo)
    script="""
import streamlit as st
from modules.briefing.briefing_center import _combined_sharing,_repo
st.session_state.setdefault('login_profile',{'id':'synthetic','position_name':'팀장'})
_combined_sharing(_repo())
"""
    app=AppTest.from_string(script).run()
    assert not app.exception
    button=next(b for b in app.button if b.label=='통합 공유 링크 만들기')
    assert not button.disabled
    button.click().run()
    assert not app.exception and app.get('download_button')
    repo.create_combined_share.assert_called_once()
    repo.reserve_request.assert_not_called()


def test_official_update_is_separate_and_customer_projection_has_a_date():
    from modules.briefing.corrections import updated_content
    from modules.briefing.public_body import customer_body
    src=content('NEWS',10)
    update={'title':'검수용 공식 발표','summary':'확인된 가상 발표 요약','source_name':'검수용 기관',
        'url':'https://www.mois.go.kr/synthetic/notice','published_at':'2026-10-09T10:00:00+09:00','category':'사회·안전'}
    revised=updated_content(src,update,'중요 발표 추가')
    assert len(src['issues'])==10 and 'important_updates' not in src
    assert len(revised['issues'])==10 and len(revised['important_updates'])==1
    projected=customer_body(revised)
    assert projected['issues'][0]['important_update'] and projected['issues'][0]['added_at']
    with pytest.raises(ValueError):updated_content(src,{**update,'url':'https://example.org/fake'},'추가')
    with pytest.raises(ValueError):updated_content(revised,update,'중복')
