from uuid import uuid4
from hwarang_academy.engine import start_session, commit, stage, completion_gate
from hwarang_academy.service import AppState, handle
from hwarang_academy.scenario_v2 import eligible_events


def evt(kind, **kwargs):
    return dict(kind=kind, event_id=uuid4().hex, **kwargs)


def say(s, text):
    if s.mode in ('GUIDE','COACH'):
        stage(s, text, assist=s.mode=='GUIDE')
        return commit(s, uuid4().hex, expected_turn=len(s.turns)+1)
    return commit(s, uuid4().hex, text=text, expected_turn=len(s.turns)+1)


def test_service_start_exposes_mission_length_and_guide_panel():
    a=AppState(independent=True)
    p=handle(a,evt('start',scenario_id='C07-S01',mode='GUIDE',session_length='STANDARD',avoid_profiles=[]))
    assert p['phase']=='session'
    assert p['session']['session_length']=='STANDARD'
    assert '최종' not in p['session']['mission'] or p['session']['mission']
    assert 'guide_panel' in p
    assert p['guide_panel']['recommended']


def test_guide_send_directly_commits():
    a=AppState(independent=True)
    p=handle(a,evt('start',scenario_id='C07-S01',mode='GUIDE',session_length='STANDARD'))
    p=handle(a,evt('send',text='보험료는 한 달에 얼마 정도 내세요?',expected_turn=1,assist_used=False))
    assert p['session']['next_turn']==2
    assert not p['session']['has_draft']


def test_coach_send_stages_until_commit():
    a=AppState(independent=True)
    handle(a,evt('start',scenario_id='C07-S01',mode='COACH',session_length='STANDARD'))
    p=handle(a,evt('send',text='보험료는 한 달에 얼마 정도 내세요?',expected_turn=1))
    assert p['session']['next_turn']==1
    assert p['session']['has_draft']
    assert 'coaching' in p
    rev=p['coaching']['revision']
    p=handle(a,evt('commit',expected_turn=1,draft_revision=rev))
    assert p['session']['next_turn']==2


def test_context_amount_question_and_wrong_total_with_indemnity():
    s=start_session('C07-S01','SOLO',seed=2,session_length='STANDARD',vary_profile=True)
    t=say(s,'혹시 얼마 정도 납입하고 계실까요?')
    assert '43' in t.response_text or '38' in t.response_text or '51' in t.response_text or '55' in t.response_text
    actual=s.facts['total_monthly_premium_won']
    wrong=300000 if actual!=300000 else 400000
    t=say(s,f'{wrong//10000}만원중에 실손 의료비가 얼마정도 되시나요?')
    assert (f"{actual:,}" in t.response_text) or (f"{actual//10000}만원" in t.response_text)
    assert '실손 보험료' in t.response_text
    assert '기억' in t.response_text or '증권' in t.response_text


def test_document_possession_check_method_sequence():
    s=start_session('C07-S01','SOLO',seed=2,session_length='STANDARD',vary_profile=True)
    t=say(s,'증권 가지고 계신가요?')
    assert '증권' in t.response_text or '자료' in t.response_text
    t=say(s,'자료 확인해주세요')
    assert any(x in t.response_text for x in ['열었','확인','자료','증권'])
    t=say(s,'어떻게 확인할 수 있을까요')
    assert any(x in t.response_text for x in ['휴대폰','증권','자료','배우자','앱'])


def test_profile_avoid_works_for_c07():
    a=start_session('C07-S01','SOLO',seed=1,session_length='STANDARD',vary_profile=True)
    b=start_session('C07-S01','SOLO',seed=1,session_length='STANDARD',avoid_profiles=[a.profile_id],vary_profile=True)
    assert b.profile_id != a.profile_id


def test_events_exist_in_guide_and_coach_but_are_bounded():
    assert eligible_events('C07-S01','GUIDE','STANDARD')
    assert eligible_events('C07-S01','COACH','STANDARD')
    assert len(eligible_events('C07-S01','GUIDE','DEEP')) <= len(eligible_events('C07-S01','SOLO','DEEP'))


def test_completion_gate_differs_by_length():
    q=start_session('C07-S01','SOLO',session_length='QUICK')
    st=start_session('C07-S01','SOLO',session_length='STANDARD')
    d=start_session('C07-S01','SOLO',session_length='DEEP')
    assert completion_gate(q)['total'] < completion_gate(d)['total']
    assert completion_gate(st)['total'] <= completion_gate(d)['total']


def test_solo_customer_can_exit_after_accumulated_serious_risk():
    s=start_session('C07-S01','SOLO',session_length='DEEP')
    for n in range(1,8):
        if s.ended:break
        say(s,'그럼 기존 보험은 바로 해지하고 새로 가입하세요.')
    assert s.ended
    assert s.end_reason=='customer_exit'


def test_same_customer_retry_preserves_profile_and_new_customer_can_change():
    a=AppState(independent=True)
    p=handle(a,evt('start',scenario_id='C07-S01',mode='SOLO',session_length='QUICK',avoid_profiles=[]))
    pid=p['session']['profile_id']
    handle(a,evt('finish'))
    p=handle(a,evt('retry'))
    assert p['session']['profile_id']==pid
    handle(a,evt('finish'))
    p=handle(a,evt('retry_new',avoid_profiles=[pid]))
    assert p['session']['profile_id']!=pid
