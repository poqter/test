from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from modules.shared.identity_state import reconcile_identity
from modules.shared import admin_assets, admin_center_ui
from modules.shared.hwarang_auth import HwarangAuthError


def identity(uid='one', role='super_admin', unit='branch'):
    return dict(profile=dict(id=uid,role=role,organization_unit_id=unit,position_code='team_leader',is_active=True),
                app_access={'workspace':True},feature_permissions=['sales_activity'])


@pytest.mark.parametrize('field,value',[('role','user'),('organization_unit_id','other'),('position_code','fp')])
def test_authorization_change_removes_all_work_and_keeps_same_device(field,value):
    old=identity();new=deepcopy(old);new['profile'][field]=value
    state={'draft':'customer','hw_admin_read_cache_v1':{'secret':1},'calendar_view_scope':'all',
           'device_handle':'same','device_restored':True,'_calendar_deployment':True}
    assert reconcile_identity(state,old,new)
    assert state=={'device_handle':'same','device_restored':True,'_calendar_deployment':True}


def test_account_switch_removes_device_and_token_rotation_preserves_work():
    old=identity();new={**old,'access_token':'rotated','profile_checked_at':999}
    state={'draft':'keep','device_handle':'one'}
    assert not reconcile_identity(state,old,new)
    assert state['draft']=='keep'
    assert reconcile_identity(state,old,identity('two'))
    assert state=={'device_action':'clear'}


def test_feature_revocation_clears_work():
    old=identity();new={**old,'feature_permissions':[]}
    state={'hwcalc_result':500}
    assert reconcile_identity(state,old,new) and not state


def response(body,status='success'):
    return dict(request_id=body['p_request_id'],requested_count=len(body['p_target_user_ids']),
                success_count=len(body['p_target_user_ids']) if status=='success' else 0,
                failed_count=0 if status=='success' else len(body['p_target_user_ids']),
                results=[dict(user_id=uid,status=status) for uid in body['p_target_user_ids']])


def test_lost_response_blocks_new_write_then_recovers_without_another_write():
    state={'login_profile':{'id':'admin'}}
    payload=dict(p_actor_user_id='admin',p_target_user_ids=['a','b'],p_operation='grant',p_amount=100,p_source_type='purchase')
    auth=SimpleNamespace(_request=Mock(side_effect=HwarangAuthError('offline')))
    with pytest.raises(HwarangAuthError):admin_assets.apply(auth,state,'admin_bulk_adjust_hwarang_purchased_credits',payload)
    body=deepcopy(state[admin_assets.PENDING]);auth._request.reset_mock()
    with pytest.raises(HwarangAuthError):admin_assets.prepare(state,'admin_bulk_adjust_hwarang_purchased_credits',payload)
    auth._request.assert_not_called()
    auth._request.side_effect=None;auth._request.return_value=response(body)
    assert admin_assets.resolve(auth,state)['success_count']==2
    assert auth._request.call_args.args[1].endswith('admin_get_hwarang_asset_request')
    assert admin_assets.PENDING not in state


@pytest.mark.parametrize('value',[None,{},[],{'success_count':0,'failed_count':0},
    {'requested_count':2,'success_count':2,'failed_count':0,'results':[{'user_id':'a','status':'success'}]},
    {'requested_count':2,'success_count':2,'failed_count':0,'results':[{'user_id':'a','status':'success'},{'user_id':'a','status':'success'}]}])
def test_invalid_results_never_become_success(value):
    with pytest.raises(HwarangAuthError):admin_assets.validate_result(value,['a','b'])


def test_safe_retry_reuses_original_payload_and_request_id():
    body=dict(p_actor_user_id='admin',p_request_id='id',p_target_user_ids=['a'],p_asset='voice',p_amount=5,p_operation='grant',p_source_type='purchase',p_note='')
    state={'login_profile':{'id':'admin'},admin_assets.PENDING:deepcopy(body)}
    auth=SimpleNamespace(_request=Mock(return_value=None))
    assert admin_assets.resolve(auth,state) is None
    auth._request.return_value=response(body)
    admin_assets.resolve(auth,state,send=True)
    assert auth._request.call_args.kwargs['json']==body


def test_admin_reads_do_not_cache_failure_or_cross_accounts(monkeypatch):
    state={'login_profile':{'id':'a'}}
    monkeypatch.setattr(admin_center_ui,'st',SimpleNamespace(session_state=state))
    loader=Mock(side_effect=[None,'A','B'])
    assert admin_center_ui._cached_admin_read('same',60,loader) is None
    assert admin_center_ui._cached_admin_read('same',60,loader)=='A'
    assert admin_center_ui._cached_admin_read('same',60,loader)=='A'
    state['login_profile']={'id':'b'}
    assert admin_center_ui._cached_admin_read('same',60,loader)=='B'
    auth=SimpleNamespace(_request=Mock(return_value={'error':'invalid'}))
    with pytest.raises(HwarangAuthError):admin_center_ui._safe_rows(auth,'/test',params={})


def test_recovery_ui_keeps_input_and_recovers_committed_result_once():
    from streamlit.testing.v1 import AppTest
    source='''import streamlit as st
from modules.shared import admin_assets, admin_center_ui as ui
from modules.shared.hwarang_auth import HwarangAuthError
st.session_state['login_profile']={'id':'admin'}
class Auth:
 def _request(self,method,path,**kw):
  body=kw['json']
  if path.endswith('admin_get_hwarang_asset_request'):
   return st.session_state.get('receipt')
  st.session_state['write_count']=st.session_state.get('write_count',0)+1
  st.session_state['receipt']={'request_id':body['p_request_id'],'requested_count':1,'success_count':1,'failed_count':0,'results':[{'user_id':'target','status':'success'}]}
  raise HwarangAuthError('response lost')
auth=Auth()
ui._render_asset_recovery(auth)
with st.form('apply'):
 note=st.text_input('사유',key='note')
 submit=st.form_submit_button('가상 지급')
if submit:
 try:ui._safe_rpc(auth,'admin_adjust_hwarang_purchased_credits',{'p_actor_user_id':'admin','p_target_user_id':'target','p_operation':'grant','p_amount':100,'p_source_type':'purchase','p_note':note})
 except HwarangAuthError as exc:st.error(str(exc))
'''
    app=AppTest.from_string(source).run()
    app.text_input(key='note').input('입력 보존 확인')
    next(b for b in app.button if b.label=='가상 지급').click().run()
    assert not app.exception and app.error
    assert app.session_state['write_count']==1
    app.run()
    next(b for b in app.button if b.label=='처리 결과 확인').click().run()
    assert not app.exception
    assert app.text_input(key='note').value=='입력 보존 확인'
    assert app.session_state['write_count']==1
    assert any('성공 1명 / 실패 0명' in i.value for i in app.info)


def test_scope_switch_invalidates_period_and_realtime_state_but_keeps_own_draft(monkeypatch):
    from modules.activity import view_scope, read_state
    state={'hwarang_auth':identity(),'sales_period_cache':{'old':1},'activity_live_ack':'old',
           'manager_selected':'old-person','draft_content':'own draft','calendar_scope_generation':2}
    fake=SimpleNamespace(session_state=state)
    monkeypatch.setattr(view_scope,'st',fake);monkeypatch.setattr(read_state,'st',fake)
    view_scope.switch('daily')
    assert 'sales_period_cache' not in state and 'activity_live_ack' not in state
    assert 'manager_selected' not in state and state['draft_content']=='own draft'
    assert state['calendar_scope_generation']==3


def test_rotation_persistence_failure_retains_new_token_and_retries_copy(monkeypatch):
    import ast
    from pathlib import Path
    from modules.activity import device
    tree=ast.parse(Path('app.py').read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='refresh_authenticated')
    old={**identity(),'refresh_token':'old'};new={**identity(),'refresh_token':'new'}
    state={'hwarang_auth':old,'device_handle':'device','draft':'unsaved'}
    namespace={'st':SimpleNamespace(session_state=state),'reconcile_identity':reconcile_identity,'HwarangAuthError':HwarangAuthError}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'app.py','exec'),namespace)
    save=Mock(side_effect=[HwarangAuthError('offline',code='transport_error'),None])
    monkeypatch.setattr(device,'save_rotation',save)
    auth=SimpleNamespace(refresh=Mock(return_value=new),workspace_permission_role=lambda p:'Admin')
    with pytest.raises(HwarangAuthError):namespace['refresh_authenticated'](auth)
    assert state['hwarang_auth']['refresh_token']=='new' and state['device_rotation_pending']
    namespace['refresh_authenticated'](auth)
    assert save.call_count==2 and 'device_rotation_pending' not in state
    assert state['draft']=='unsaved'
