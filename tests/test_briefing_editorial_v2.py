"""Editorial selection, late recovery and customer isolation with no paid calls."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock
import pytest
from test_briefing_analysis_recovery import event, row, NOW
from test_briefing_launch import content
from test_briefing_catch_up import Repo, at, edition, generate
from modules.briefing.models import PhaseBResult, AnalysisUsage
from modules.briefing.phase_c import run_phase_c
from modules.briefing.public_body import customer_body, public_html
from modules.briefing import scheduler


def analyze(count=20, profile='NEWS', patches=None):
    events=[event(i) for i in range(count)]
    for e in events:e.routed_profiles={profile}
    raw=[{**row(e),'importance_score':90-i,'category':'소비자·사회이슈' if profile=='INSURANCE' else '교육'} for i,e in enumerate(events)]
    for i,patch in (patches or {}).items():raw[i].update(patch)
    analyzer=Mock();analyzer.analyze.return_value=(raw,AnalysisUsage())
    return run_phase_c(PhaseBResult(NOW,[c for e in events for c in e.candidates],events,[],{}),analyzer=analyzer)


@pytest.mark.parametrize('profile,main',[('NEWS',10),('INSURANCE',7),('MARKET',6)])
def test_main_and_more_caps_and_identical_quality_floor(profile,main):
    result=analyze(20,profile,{0:{'essential_facts_complete':False},1:{'confidence':'low'}})
    assert all(r.selection_tier=='excluded' for r in result.analyses[:2])
    assert sum(r.selection_tier=='core' for r in result.analyses)==main
    assert sum(r.selection_tier=='light_digest' for r in result.analyses)==(6 if profile=='MARKET' else 8)
    assert all(r.validation_status=='ok' for r in result.analyses if r.selection_tier!='excluded')


def test_earnings_cap_and_promotion_exclusion_do_not_fill_quota():
    result=analyze(6,'INSURANCE',{0:{'editorial_kind':'earnings'},1:{'editorial_kind':'earnings'},2:{'editorial_kind':'promotion'},3:{'is_new_development':False}})
    selected=[r for r in result.analyses if r.selection_tier!='excluded']
    assert len(selected)==3
    assert sum(r.profile_payload['editorial_kind']=='earnings' for r in selected)==1


def test_shared_more_reading_visible_and_admin_payload_is_private():
    src=content('NEWS',3);src['editorial_version']=2
    for i,r in enumerate(src['issues']):r.update(selection_tier='light_digest' if i==2 else 'core',headline_sufficient=i==0)
    src['issues'][0]['summary']='숨겨야 할 중복 요약 검수 문장'
    src['eligible_analysis_pool']=[{'secret':'PRIVATE_AUDIT'}]
    body=customer_body(src)
    html=public_html({'body':body,'sender':{'name':'담당 설계사','position':'팀장'},'briefing_date':'2026-10-20'})
    assert html.count('더 읽을 기사')==1 and len(body['issues'])==3
    assert src['issues'][0]['summary'] not in html
    assert '<details class="more-reading">' in html and 'PRIVATE_AUDIT' not in html
    assert '담당 설계사 팀장' in html and 'role="tab"' in html
    assert src['issues'][0]['summary']  # Internal evidence is retained.


def test_independent_insurance_retry_does_not_regenerate_saved_news(generate):
    repo=Repo();repo.saved={'NEWS':edition('NEWS'),'MARKET':edition('MARKET')}
    result=scheduler.catch_up(repo,at('08:20:00'))
    assert result['status']=='published'
    assert [c.kwargs['profile_codes'] for c in generate.call_args_list]==[('INSURANCE',)]


def test_new_generation_stops_at_0850_but_saved_editions_publish(generate):
    repo=Repo();repo.saved={'NEWS':edition('NEWS')}
    result=scheduler.catch_up(repo,at('08:50:00'))
    generate.assert_not_called()
    assert repo.publications==['NEWS'] and result['status']=='incomplete'


def test_0840_recovery_is_saved_material_only(generate):
    repo=Repo();scheduler.catch_up(repo,at('08:40:00'))
    assert all(c.kwargs['saved_material_only'] for c in generate.call_args_list)


def test_legacy_daily_request_cannot_be_evaded_by_new_profile_key(generate):
    repo=Repo();repo.runs['DAILY']={'attempts':1,'status':'blocked'}
    repo.saved={'MARKET':edition('MARKET')}
    result=scheduler.catch_up(repo,at('08:20:00'))
    generate.assert_not_called()
    assert result['generation']['NEWS']['reason']=='legacy_daily_run_preserved'


def test_cutoff_is_0730_for_every_profile():
    for profile in scheduler.GROUPS:
        assert scheduler.cutoff(at('07:30:00').date(),profile)==at('07:30:00')


def test_saved_only_collection_never_fetches_or_discovers(monkeypatch):
    from modules.briefing.phase_b import run_phase_b
    from modules.briefing.checkpoints import encode
    e=event(1);c=e.candidates[0];c.metadata['profile_hints']=['NEWS']
    network=Mock(side_effect=AssertionError('No network after collection deadline'))
    monkeypatch.setattr('modules.briefing.phase_b.collect_direct_sources',network)
    enricher=Mock();enricher.stats={};enricher.enrich=network
    phase=run_phase_b(as_of=NOW,direct_sources=[],saved_material_only=True,
        seed_candidates=encode(PhaseBResult(NOW,[c],[],[],{}))['candidates'],date_enricher=enricher)
    network.assert_not_called();assert len(phase.candidates)==1


def test_future_source_is_never_admitted_to_delayed_edition():
    from modules.briefing.phase_b import run_phase_b
    from modules.briefing.checkpoints import encode
    e=event(1);e.candidates[0].published_at=NOW+timedelta(minutes=1)
    result=run_phase_b(as_of=NOW,saved_material_only=True,
        seed_candidates=encode(PhaseBResult(NOW,e.candidates,[],[],{}))['candidates'])
    assert not result.candidates and result.excluded_counts['after_cutoff']==1
