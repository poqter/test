"""Cross-app login uses consumed tickets and fresh, least-privilege user sessions."""
from unittest.mock import Mock
import pytest
from modules.activity.launch import accept_launch
from modules.shared.hwarang_auth import HwarangAuthError

UID = '00000000-0000-4000-8000-000000000001'

@pytest.fixture
def auth():
    a = Mock()
    context = {'profile': {'id': UID, 'is_active': True}, 'app_access': {'workspace': True},
               'feature_permissions': ['workspace.sales_activity']}
    a.consume_launch_ticket.return_value = context
    a._complete_workspace_login.return_value = context
    a._auth_user_by_id.return_value = {'id': UID, 'email': 'fixture@example.invalid', 'email_confirmed_at': '2026-01-01'}
    a._request.side_effect = [
        {'id': UID, 'hashed_token': 'single-use-hash'},
        {'user': {'id': UID}, 'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 3600},
    ]
    return a


def test_new_session_is_not_workspace_refresh_token(auth):
    result = accept_launch(auth, 'ticket')
    auth.consume_launch_ticket.assert_called_once_with('ticket', 'workspace')
    assert result['access_token'] == 'new-access'
    assert result['refresh_token'] == 'new-refresh'
    assert 'launch_authenticated' not in result
    assert auth._request.call_args_list[1].kwargs == {'json': {'type': 'magiclink', 'token_hash': 'single-use-hash'}}


def test_expired_ticket_cannot_mint_session(auth):
    auth.consume_launch_ticket.side_effect = HwarangAuthError('expired')
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'expired')
    auth._auth_user_by_id.assert_not_called()
    auth._request.assert_not_called()


def test_feature_permission_required_before_mint(auth):
    auth.consume_launch_ticket.return_value = {'profile': {'id': UID}, 'feature_permissions': []}
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket')
    auth._request.assert_not_called()


def test_existing_same_account_keeps_own_session(auth):
    current = {'profile': {'id': UID}, 'refresh_token': 'own-existing'}
    auth.refresh.return_value = current
    assert accept_launch(auth, 'ticket', current) is current
    auth._request.assert_not_called()


def test_other_logged_in_account_is_not_overwritten(auth):
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket', {'profile': {'id': 'other'}})
    auth._request.assert_not_called()


@pytest.mark.parametrize('user', [{}, {'id': 'other', 'email': 'fixture@example.invalid'},
    {'id': UID, 'email': 'fixture@example.invalid'},
    {'id': UID, 'email': 'fixture@example.invalid', 'email_confirmed_at': 'today', 'factors': [{'status': 'verified'}]}])
def test_no_signup_unconfirmed_or_mfa_bypass(auth, user):
    auth._auth_user_by_id.return_value = user
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket')
    auth._request.assert_not_called()


def test_generated_identity_mismatch_rejected_before_verify(auth):
    auth._request.side_effect = [{'id': 'other', 'hashed_token': 'hash'}]
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket')
    assert auth._request.call_count == 1


def test_verified_identity_mismatch_revokes_new_session(auth):
    auth._request.side_effect = [{'id': UID, 'hashed_token': 'hash'},
        {'user': {'id': 'other'}, 'access_token': 'new-access', 'refresh_token': 'new-refresh'}]
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket')
    auth.sign_out.assert_called_once()


def test_revoked_permission_during_exchange_revokes_new_session(auth):
    auth._complete_workspace_login.return_value = {'profile': {'id': UID, 'is_active': True}, 'feature_permissions': []}
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket')
    auth.sign_out.assert_called_once()


def test_workspace_calendar_destination_and_permission_gate(monkeypatch):
    import streamlit as st
    from modules.shell.workspace_v2 import _external_launch_context
    from modules.shell.app_registry import APP_BY_ID
    state = {'hwarang_auth': {'profile': {'id': UID}, 'access_token': 'source-token',
             'feature_permissions': ['workspace.sales_activity']},
             'hw_app_access': {'workspace': True}, 'ws_allowed_ids': ['sales_activity']}
    monkeypatch.setattr(st, 'session_state', state)
    monkeypatch.setattr(st, 'secrets', {})
    monkeypatch.delenv('HW_CALENDAR_URL', raising=False)
    app = APP_BY_ID['sales_activity']
    assert _external_launch_context(app) == ('workspace', UID, 'https://hwarang-calendar.streamlit.app')
    state['hwarang_auth']['feature_permissions'] = []
    assert _external_launch_context(app) is None


def test_calendar_url_can_be_overridden_without_changing_other_apps(monkeypatch):
    import streamlit as st
    from modules.shared.external_apps import external_app_url
    monkeypatch.setattr(st, 'secrets', {'external_apps': {'CALENDAR_URL': 'https://calendar.example.invalid/'}})
    assert external_app_url('calendar_url') == 'https://calendar.example.invalid'


def test_return_to_workspace_uses_workspace_access_without_calendar_permission(auth):
    context = {'profile': {'id': UID, 'is_active': True},
               'app_access': {'workspace': True}, 'feature_permissions': []}
    auth.consume_launch_ticket.return_value = context
    auth._complete_workspace_login.return_value = context
    assert accept_launch(auth, 'return-ticket', calendar=False)['profile']['id'] == UID


@pytest.mark.parametrize('calendar', [False, True])
def test_both_directions_reject_disabled_workspace(auth, calendar):
    auth.consume_launch_ticket.return_value['app_access']['workspace'] = False
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'ticket', calendar=calendar)
    auth._request.assert_not_called()


@pytest.mark.parametrize('calendar', [False, True])
def test_both_directions_reject_other_logged_in_identity(auth, calendar):
    with pytest.raises(HwarangAuthError):
        accept_launch(auth, 'ticket', {'profile': {'id': 'other'}}, calendar=calendar)
    auth._request.assert_not_called()


@pytest.mark.parametrize('calendar', [False, True])
def test_both_directions_reject_used_or_expired_ticket(auth, calendar):
    auth.consume_launch_ticket.side_effect = HwarangAuthError('invalid_or_expired_launch_ticket')
    with pytest.raises(HwarangAuthError): accept_launch(auth, 'used', calendar=calendar)
    auth._request.assert_not_called()


def test_return_source_refreshes_and_issues_only_workspace_ticket(auth):
    from modules.activity.launch import issue_workspace_launch
    state = {**auth._complete_workspace_login.return_value, 'refresh_token': 'source-refresh'}
    auth.refresh.return_value = state
    auth.create_launch_ticket.return_value = 'https://hwarang-workspace.streamlit.app/?launch=one-use'
    preserve = Mock()
    current, url = issue_workspace_launch(auth, state, on_refresh=preserve)
    assert current is state
    assert auth.refresh.call_args.args[0]['profile_checked_at'] == 0
    preserve.assert_called_once_with(state)
    auth.create_launch_ticket.assert_called_once_with(
        user_id=UID, target_app='workspace', target_url='https://hwarang-workspace.streamlit.app/')
    assert 'source-refresh' not in url


@pytest.mark.parametrize('state', [None, {}, {'profile': {'id': UID}}])
def test_return_without_session_cannot_issue_ticket(auth, state):
    from modules.activity.launch import issue_workspace_launch
    with pytest.raises(HwarangAuthError): issue_workspace_launch(auth, state)
    auth.create_launch_ticket.assert_not_called()


def test_return_denied_source_cannot_issue_ticket(auth):
    from modules.activity.launch import issue_workspace_launch
    state = {'profile': {'id': UID, 'is_active': True}, 'refresh_token': 'source'}
    auth.refresh.return_value = {**state, 'app_access': {'workspace': False}}
    with pytest.raises(HwarangAuthError): issue_workspace_launch(auth, state)
    auth.create_launch_ticket.assert_not_called()


def test_rotation_saved_even_when_return_ticket_service_fails(auth):
    from modules.activity.launch import issue_workspace_launch
    state = {**auth._complete_workspace_login.return_value, 'refresh_token': 'rotated'}
    auth.refresh.return_value = state
    auth.create_launch_ticket.side_effect = HwarangAuthError('unavailable')
    preserve = Mock()
    with pytest.raises(HwarangAuthError): issue_workspace_launch(auth, state, on_refresh=preserve)
    preserve.assert_called_once_with(state)


def test_workspace_entry_accepts_ticket_without_calendar_deployment():
    import ast
    from pathlib import Path
    tree = ast.parse(Path('app.py').read_text())
    entry = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "st.query_params.get('launch')")
    block = ast.unparse(entry)
    assert "del st.query_params['launch']" in block
    assert "calendar=bool(st.session_state.get('_calendar_deployment'))" in block
