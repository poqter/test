"""Account/role/session contracts with fake transport; never touches live users."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from modules.shared.hwarang_auth import HwarangAuthService, HwarangAuthError, SupabaseConfig
from modules.activity import device

@pytest.fixture
def auth(monkeypatch):
    service=HwarangAuthService(SupabaseConfig('https://synthetic.invalid','public-test','secret-test'))
    monkeypatch.setattr('modules.shared.hwarang_auth.time.time',lambda:10000)
    service._request=Mock(side_effect=AssertionError('Unexpected network request'))
    service._assert_credential_current=Mock()
    return service

@pytest.mark.parametrize('position',['fp','team_leader','branch_manager','division_head'])
def test_position_does_not_grant_system_administration(auth,position):
    auth._profile_by_id=Mock(return_value={'id':'u','role':'user','position_code':position,'is_active':True})
    with pytest.raises(HwarangAuthError):auth._require_super_admin('u')
    auth._profile_by_id.return_value['role']='super_admin'
    assert auth._require_super_admin('u')['position_code']==position
    auth._profile_by_id.return_value['is_active']=False
    with pytest.raises(HwarangAuthError):auth._require_super_admin('u')

@pytest.mark.parametrize('active,access',[(False,True),(True,False)])
def test_periodic_revalidation_blocks_disabled_account_or_workspace(auth,active,access):
    auth._workspace_context=Mock(return_value={'profile':{'id':'u','is_active':active},'app_access':{'workspace':access},'feature_permissions':{}})
    state={'profile':{'id':'u'},'expires_at':11000,'profile_checked_at':9900}
    with pytest.raises(HwarangAuthError):auth.refresh(state)
    assert state['profile']=={'id':'u'}


def test_role_and_organization_refresh_independently_without_rotating_valid_token(auth):
    profile={'id':'u','role':'user','position_code':'team_leader','organization_unit_id':'new-unit','is_active':True}
    auth._workspace_context=Mock(return_value={'profile':profile,'app_access':{'workspace':True},'feature_permissions':{'calculator':True}})
    updated=auth.refresh({'profile':{'id':'u','role':'super_admin','organization_unit_id':'old-unit'},'expires_at':11000,'profile_checked_at':9900})
    assert updated['profile']==profile
    assert updated['profile_checked_at']==10000
    auth._request.assert_not_called()


def test_expiring_token_is_rotated_and_recent_profile_is_preserved(auth):
    auth._request=Mock(return_value={'access_token':'new-access','refresh_token':'new-refresh','expires_at':13600})
    state={'profile':{'id':'u'},'refresh_token':'old-refresh','expires_at':10010,'profile_checked_at':9999}
    updated=auth.refresh(state)
    assert updated['refresh_token']=='new-refresh'
    assert state['refresh_token']=='old-refresh'
    assert auth._request.call_args.kwargs['params']=={'grant_type':'refresh_token'}


def test_device_restore_uses_expiry_filter_and_keeps_credentials_server_side(auth,monkeypatch):
    state={};handle='h'*54
    monkeypatch.setattr(device,'st',SimpleNamespace(session_state=state))
    monkeypatch.setattr(device,'_bridge',lambda **kw:{'action':'read','token':handle})
    auth._request=Mock(side_effect=[[{'owner':'u','secret':device.cipher(auth).encrypt(b'old-refresh').decode(),'issued_at':'2026-11-01T00:00:00+00:00'}],None])
    auth.refresh=Mock(return_value={'profile':{'id':'u'},'refresh_token':'new-refresh'})
    authenticate=Mock()
    device.synchronize(auth,authenticate)
    get,patch=auth._request.call_args_list
    assert get.kwargs['params']['expires_at'].startswith('gt.')
    assert get.kwargs['params']['digest']=='eq.'+device.digest(handle)
    assert patch.kwargs['params']['owner']=='eq.u'
    assert device.cipher(auth).decrypt(patch.kwargs['json']['secret'].encode())==b'new-refresh'
    assert 'refresh_token' not in state
    assert state['device_restored'] and state['device_handle']==handle
    authenticate.assert_called_once()


def test_expired_or_revoked_handle_is_cleared_without_authentication(auth,monkeypatch):
    class Rerun(Exception):pass
    def rerun():raise Rerun()
    state={}
    monkeypatch.setattr(device,'st',SimpleNamespace(session_state=state,rerun=rerun))
    monkeypatch.setattr(device,'_bridge',lambda **kw:{'action':'read','token':'h'*54})
    auth._request=Mock(return_value=[]);authenticate=Mock()
    with pytest.raises(Rerun):device.synchronize(auth,authenticate)
    authenticate.assert_not_called()
    assert state['device_action']=='clear'


def test_logout_revokes_only_current_device_unless_all_requested(auth,monkeypatch):
    monkeypatch.setattr(device,'st',SimpleNamespace(session_state={'device_handle':'h'*54,'login_profile':{'id':'u'}}))
    auth._request=Mock()
    device.revoke(auth)
    assert auth._request.call_args.kwargs['params']=={'digest':'eq.'+device.digest('h'*54)}
    device.revoke(auth,all_devices=True)
    assert auth._request.call_args.kwargs['params']=={'owner':'eq.u'}
