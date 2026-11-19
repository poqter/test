import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("page", ["dashboard", "accounts", "operations", "assets", "academy", "simulator_dashboard", "ai", "settings"])
def test_retained_admin_routes_with_simulator_removed(page, monkeypatch):
    from modules.shared import operations_ui
    monkeypatch.setattr(operations_ui, "_github", lambda: dict(runs=[], commits=[], history=[]))
    source = """
import streamlit as st
from modules.shared import admin_center_ui as ui
st.session_state['login_profile'] = {'id':'admin','role':'super_admin'}
class Auth:
    def _require_super_admin(self, actor):
        assert actor == 'admin'
    def _request(self, method, path, **kwargs):
        st.session_state.setdefault('reads', []).append((method, path))
        if path == '/rest/v1/profiles_admin_view':
            return [{'user_id':'a','display_name':'가상 계정','is_active':True}]
        if path in ['/rest/v1/hwarang_activity_log', '/rest/v1/hwarang_briefing_jobs',
                    '/rest/v1/hwarang_briefings', '/rest/v1/hwarang_briefing_daily_runs']:
            return []
        raise AssertionError(path)
ui.render_sidebar()
ui.render(Auth())
"""
    app = AppTest.from_string(source)
    app.session_state['hw_admin_center_page'] = page
    app.run()
    assert not app.exception
    paths = app.session_state['reads']
    assert paths and all(method == 'GET' for method, _ in paths)
    assert all('studio' not in path and 'asset' not in path for _, path in paths)
    assert app.session_state['hw_admin_center_page'] == ('dashboard' if page not in {'dashboard', 'accounts', 'operations'} else page)
    assert not any(b.label == 'Credit · Voice' for b in app.button)


def test_briefing_switch_uses_briefing_policy():
    app = AppTest.from_string("""
import streamlit as st
from modules.shared import admin_center_ui as ui
st.session_state.update(login_profile={'id':'admin','role':'super_admin'}, hw_admin_center_page='briefing_switch')
class Auth:
    def _require_super_admin(self, actor):
        assert actor == 'admin'
    def _request(self, method, path, **kwargs):
        enabled = st.session_state.get('enabled', True)
        if method == 'GET':
            assert path == '/rest/v1/hwarang_briefing_operating_policy'
            assert kwargs['params'] == {'select':'generation_enabled','policy_key':'eq.WORKSPACE'}
            return [{'generation_enabled': enabled}]
        assert path == '/rest/v1/rpc/admin_set_briefing_service_enabled'
        assert kwargs['json'] == {'p_actor':'admin','p_expected':enabled,'p_enabled':not enabled}
        st.session_state['enabled'] = not enabled
        return not enabled
ui.render(Auth())
""").run()
    assert not app.exception
    app.button(key='hw_briefing_switch_True').click().run()
    assert not app.exception and app.session_state['enabled'] is False
    app.button(key='hw_briefing_switch_False').click().run()
    assert not app.exception and app.session_state['enabled'] is True
