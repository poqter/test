"""Regression checks for private history, varied customers and launch recovery."""
import json
from uuid import UUID

import pytest
from streamlit.testing.v1 import AppTest

from hwarang_academy.engine import start_session, stage, commit, finish, guide
from hwarang_academy.service import AppState, present
from hwarang_academy.history import checkpoint, restore, TrainingHistory, public_history, save_history
from hwarang_academy.evaluation import report
from hwarang_academy.review_export import review_html
from modules.calculators import catalog_browser as catalog
from modules.shared.hwarang_auth import HwarangAuthError
from modules.shell import workspace_v2 as shell
from modules.shell.app_registry import APP_BY_ID

USER = '00000000-0000-0000-0000-000000000001'
OTHER = '00000000-0000-0000-0000-000000000002'


def _send(session, text, event):
    if session.mode in ('GUIDE', 'COACH'):
        stage(session, text, assist=session.mode == 'GUIDE')
        return commit(session, event, expected_turn=len(session.turns) + 1)
    return commit(session, event, text=text, expected_turn=len(session.turns) + 1)


@pytest.mark.parametrize('mode', ['GUIDE', 'COACH', 'SOLO', 'ASSESSMENT'])
@pytest.mark.parametrize('scenario', ['C07-S01', 'A01-S01', 'D08-S01', 'F07-S01', 'G10-S01', 'H10-S01'])
def test_checkpoint_roundtrip_preserves_customer_and_next_reply(mode, scenario):
    original = start_session(scenario, mode, seed=194, vary_profile=True)
    _send(original, '전체로 한 달에 내시는 보험료는 어느 정도 되실까요?', 'first')
    if mode == 'COACH':
        stage(original, '자료를 같이 확인해도 괜찮을까요?', assist=True)
    original.hint_turns.add(2)
    wire = json.loads(json.dumps(checkpoint(original, USER)['wire']))
    resumed = restore(wire, USER)
    assert checkpoint(resumed, USER)['wire'] == checkpoint(original, USER)['wire']
    if not original.ended:
        text = '지금 확인이 어렵다면 배우자분께 증권을 받으신 뒤 저에게 전달해주실 수 있을까요?'
        _send(original, text, 'second')
        _send(resumed, text, 'second')
        assert present(AppState(session=resumed, independent=True)) == present(AppState(session=original, independent=True))


def test_completed_result_survives_roundtrip():
    session = start_session(seed=302, vary_profile=True, session_length='QUICK')
    for turn in range(18):
        if session.ended:
            break
        hint = guide(session)
        _send(session, hint['recommended'], f'guide-{turn}')
    assert session.ended and report(session)['mission_outcome']['final_complete']
    restored = restore(checkpoint(session, USER)['wire'], USER)
    assert report(restored) == report(session)


def test_other_owner_and_unknown_record_type_are_rejected():
    wire = checkpoint(start_session(), USER)['wire']
    with pytest.raises(ValueError):
        restore(wire, OTHER)
    wire['session']['type'] = '__import__'
    with pytest.raises(ValueError):
        restore(wire, USER)


def test_checkpoint_cannot_reassign_another_owners_session():
    session = start_session()
    checkpoint(session, OTHER)
    with pytest.raises(ValueError, match='본인의 상담 기록'):
        checkpoint(session, USER)
    assert session.user_id == OTHER


def test_varied_premium_gate_uses_only_disclosed_facts():
    session = start_session(seed=4, vary_profile=True)
    session.disclosed = {'premium': {'label': '전체 월 보험료', 'value': '550,000원 · 고객 기억', 'turn': 2}}
    gate = next(r['gate'] for r in report(session)['rows'] if r['id'] == 'L2')
    assert '550,000원' in gate and '43만원' not in gate and '20만원' not in gate
    session.disclosed = {}
    gate = next(r['gate'] for r in report(session)['rows'] if r['id'] == 'L2')
    assert '550,000원' not in gate and '추정하지 않음' in gate


def test_private_state_does_not_enter_history_ui():
    state = {'available': True, 'rows': [{'id': 'x', 'user_id': USER, 'session_state': {'secret': 1}, 'metadata': {'hidden': 1}}]}
    ui = json.dumps(public_history(state))
    assert USER not in ui and 'session_state' not in ui and 'hidden' not in ui


def test_load_queries_owner_even_when_given_another_session_id():
    calls = []
    class Auth:
        def _request(self, *args, **kwargs):
            calls.append(kwargs)
            return []
    with pytest.raises(ValueError):
        TrainingHistory(Auth(), USER).load(OTHER)
    assert calls[0]['params']['user_id'] == 'eq.' + USER
    assert calls[0]['params']['metadata->>training_engine'] == 'eq.rules'


def test_failed_save_keeps_session_and_checkpoint_version():
    class Client:
        def save(self, session, version):
            raise HwarangAuthError('다른 접속에서 이 상담 기록이 변경됐습니다.')
    app = AppState(session=start_session())
    state = {'session_id': app.session.session_id, 'version': 5}
    assert not save_history(app, Client(), state)
    assert app.session is not None and state['version'] == 5
    assert '다른 접속에서' in state['error']


def test_review_export_contains_result_and_escapes_input():
    session = start_session()
    _send(session, '<script>alert(1)</script>', 'input')
    finish(session)
    text = review_html(present(AppState(session=session, independent=True)))
    assert '미션 결과' in text and '대화 복기' in text and '규칙 기반' in text
    assert '<script>' not in text and '&lt;script&gt;' in text
    with pytest.raises(ValueError):
        review_html(present(AppState(session=start_session(), independent=True)))


def test_each_calculator_dialog_preparation_issues_fresh_ticket(monkeypatch):
    monkeypatch.setattr(catalog.st, 'session_state', {'_hwarang_calculator_identity': {'profile': {'id': USER}}})
    monkeypatch.setattr(catalog.st, 'context', type('Context', (), {'url': 'https://example.com/?launch=old'})())
    monkeypatch.setattr(catalog.SupabaseConfig if hasattr(catalog, 'SupabaseConfig') else shell.SupabaseConfig, 'from_mapping', lambda _v: None)
    n = []
    def create(self, **kwargs):
        n.append(kwargs)
        return 'https://example.com/?launch=' + str(len(n))
    monkeypatch.setattr(shell.HwarangAuthService, 'create_launch_ticket', create)
    assert catalog.prepared_new_tab_url('総', {'総': 'calc-003'}) != catalog.prepared_new_tab_url('総', {'総': 'calc-003'})
    assert len(n) == 2 and all('calc=calc-003' in x['target_url'] for x in n)


def test_workspace_alias_preserves_calculator_purpose(monkeypatch):
    assert shell._matches('상령일', {'quick_calculators'})[0][1] == '보험나이·상령일'
    monkeypatch.setattr(shell, '_external_launch_context', lambda _app: ('calculator', USER, 'https://example.com/'))
    monkeypatch.setattr(shell.st, 'session_state', {})
    monkeypatch.setattr(shell.SupabaseConfig, 'from_mapping', lambda _v: None)
    targets = []
    monkeypatch.setattr(shell.HwarangAuthService, 'create_launch_ticket', lambda self, **kw: targets.append(kw['target_url']) or kw['target_url'])
    shell._external_launch_url(APP_BY_ID['quick_calculators'], fresh=True, mode='보험나이·상령일')
    assert 'search=' in targets[0]


def test_native_review_download_is_rendered_in_academy():
    code = f'''
import streamlit as st
from unittest.mock import patch
import academy_app as app
from hwarang_academy.service import AppState
from hwarang_academy.engine import start_session, finish
s=start_session();finish(s)
st.session_state['_academy_model']=AppState(session=s,independent=True)
st.session_state['_academy_route']=(False,'C07-S01')
st.session_state['_academy_history_state']={{'user_id':{USER!r},'available':True}}
identity={{'profile':{{'id':{USER!r}}},'feature_permissions':['academy.simulator']}}
with patch.object(app,'auth_service'), patch.object(app,'_consume_workspace_launch',return_value=identity), patch.object(app,'get_training_credit_status',return_value=None):
    app.main()
'''
    app = AppTest.from_string(code).run()
    assert not app.exception
    downloads = app.get('download_button')
    assert len(downloads) == 1 and '복기 HTML 저장' in downloads[0].proto.label


def test_account_change_clears_prior_session_before_presenting_history():
    code = f'''
import streamlit as st
from unittest.mock import patch
import academy_app as app
from hwarang_academy.service import AppState
from hwarang_academy.engine import start_session
from hwarang_academy.history import checkpoint
s=start_session();checkpoint(s,{OTHER!r})
st.session_state['_academy_model']=AppState(session=s,independent=True)
st.session_state['_academy_route']=(False,'C07-S01')
st.session_state['_academy_history_state']={{'user_id':{OTHER!r},'available':True}}
identity={{'profile':{{'id':{USER!r}}},'feature_permissions':['academy.simulator']}}
def render(**kwargs):
    assert kwargs['model']['phase']=='home'
    assert not kwargs['model']['simulator_status']['has_session']
    return None
with patch.object(app,'auth_service'), patch.object(app,'_consume_workspace_launch',return_value=identity), patch.object(app,'get_training_credit_status',return_value=None), patch.object(app,'initialize_history',return_value={{'available':True,'rows':[],'summary':{{}}}}), patch.object(app,'component',return_value=render):
    app.main()
assert st.session_state['_academy_model'].session is None
assert st.session_state['_academy_history_state']['user_id']=={USER!r}
'''
    app = AppTest.from_string(code).run()
    assert not app.exception
