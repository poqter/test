"""Exercise app-launch lifecycle and empty admin pages without live requests."""
import pytest
from streamlit.testing.v1 import AppTest

from modules.shell import workspace_v2 as shell
from modules.shell.app_registry import APP_BY_ID


def _launch_test_code(*, dialog=False, permitted=True, fail=False):
    view = "ui._external_launch_dialog('quick_calculators')" if dialog else "ui._launch_widget(APP_BY_ID['quick_calculators'], '계산기', key='fixture_open')"
    return f'''
import streamlit as st
from unittest.mock import patch
from modules.shell import workspace_v2 as ui
from modules.shell.app_registry import APP_BY_ID
from modules.shared.hwarang_auth import HwarangAuthError
st.session_state.setdefault('hwarang_auth', {{'profile': {{'id': 'fixture-user'}}}})
st.session_state.setdefault('hw_app_access', {{'calculator': {permitted!r}}})
st.session_state.setdefault('ws_allowed_ids', ['quick_calculators'])
class Auth:
    def __init__(self, config): pass
    def create_launch_ticket(self, **kwargs):
        n=st.session_state.get('issued', 0)+1
        st.session_state['issued']=n
        if {fail!r}: raise HwarangAuthError('Fixture connection failure')
        return 'https://example.com/calculator?launch=fixture-'+str(n)
with patch.object(ui, 'external_app_url', return_value='https://example.com/calculator'), \\
     patch.object(ui, 'HwarangAuthService', Auth), \\
     patch.object(ui.SupabaseConfig, 'from_mapping', return_value=None):
    {view}
st.caption('issued:'+str(st.session_state.get('issued',0)))
'''


def test_render_does_not_issue_ticket_until_app_open_click():
    app = AppTest.from_string(_launch_test_code()).run()
    assert not app.exception
    assert 'issued' not in app.session_state
    assert not app.get('link_button')
    app.button(key='fixture_open').click().run()
    assert not app.exception
    assert app.session_state['issued'] == 1
    assert app.get('link_button')[0].proto.url.endswith('fixture-1')


def test_refresh_replaces_one_time_link_even_inside_cache_ttl():
    app = AppTest.from_string(_launch_test_code(dialog=True)).run()
    assert not app.exception
    assert app.get('link_button')[0].proto.url.endswith('fixture-1')
    app.button(key='hw_refresh_launch_quick_calculators').click().run()
    assert not app.exception
    assert app.session_state['issued'] == 2
    assert app.get('link_button')[0].proto.url.endswith('fixture-2')


def test_missing_permission_disables_open_without_issuing_ticket():
    app = AppTest.from_string(_launch_test_code(permitted=False)).run()
    assert not app.exception
    assert app.button(key='fixture_open').disabled
    assert 'issued' not in app.session_state
    assert not app.get('link_button')


def test_connection_failure_keeps_a_visible_retry_without_broken_link():
    app = AppTest.from_string(_launch_test_code(dialog=True, fail=True)).run()
    assert not app.exception
    assert app.error
    assert app.button(key='hw_refresh_launch_quick_calculators')
    assert not app.get('link_button')


def test_revoked_workspace_permission_blocks_dialog_without_issuing():
    code = _launch_test_code(dialog=True).replace("['quick_calculators']", "[]")
    app = AppTest.from_string(code).run()
    assert not app.exception
    assert 'issued' not in app.session_state
    assert app.error
    assert not app.get('link_button')


def test_explicit_open_never_reuses_consumed_ticket_and_preserves_user_scope(monkeypatch):
    state={'hwarang_auth': {'profile': {'id': 'u1'}}, 'hw_app_access': {'calculator': True}}
    monkeypatch.setattr(shell.st, 'session_state', state)
    monkeypatch.setattr(shell, 'external_app_url', lambda key: 'https://example.com/calculator')
    monkeypatch.setattr(shell.SupabaseConfig, 'from_mapping', lambda value: None)
    calls=[]
    class Auth:
        def __init__(self, config): pass
        def create_launch_ticket(self, **kwargs):
            calls.append(kwargs)
            return 'https://example.com/calculator?launch=' + str(len(calls))
    monkeypatch.setattr(shell, 'HwarangAuthService', Auth)
    app=APP_BY_ID['quick_calculators']
    first=shell._external_launch_url(app)
    assert shell._external_launch_url(app) == first
    assert shell._external_launch_url(app, fresh=True) != first
    state['hwarang_auth']['profile']['id']='u2'
    shell._external_launch_url(app)
    assert [call['user_id'] for call in calls] == ['u1','u1','u2']
    state['hw_app_access']['calculator']=False
    assert shell._external_launch_url(app, fresh=True) == ''
    assert len(calls) == 3


@pytest.mark.parametrize('page', [0, 1])
def test_empty_academy_page_has_message_and_preserves_back_navigation(page):
    app = AppTest.from_string(f'''
import streamlit as st
from modules.shared.admin_center_ui import _render_academy
st.session_state.setdefault('hw_academy_sessions_page', {page})
class Auth:
    def _request(self, *args, **kwargs): return []
_render_academy(Auth())
''').run()
    assert not app.exception
    assert any('상담 훈련 기록이 없습니다' in message.value for message in app.info)
    assert not app.dataframe
    if page:
        assert not app.button(key='hw_academy_sessions_prev').disabled
        assert app.button(key='hw_academy_sessions_next').disabled
    else:
        assert not any(button.label in ('← 이전', '다음 →') for button in app.button)
