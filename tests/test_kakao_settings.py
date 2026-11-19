from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from streamlit.testing.v1 import AppTest
from modules.activity.kakao_settings import connection_url
from modules.shared.hwarang_auth import HwarangAuthError


def app(status=None, flag=True, admin_rows=None, history=None, regions=None, catalog_error=False, test_status=None):
    if regions is None: regions=[{'region_key':'seoul-songpa','display_name':'서울특별시 송파구'}]
    status = status or {'connection_status':'connected','enabled':False,'time':'08:00','days':[1,2,3,4,5],'send_empty':True,'weather_region_key':'seoul-songpa'}
    return AppTest.from_string(f'''
import streamlit as st
from unittest.mock import patch
from modules.activity.kakao_settings import render_panel
st.session_state.setdefault('hwarang_auth',{{'access_token':'test'}})
def call(method,path,**kwargs):
    st.session_state.setdefault('calls',[]).append((path,kwargs))
    if path.endswith('kakao_my_status'): return {{**{status!r}, **st.session_state.get('weather_saved', {{}})}}
    if path.endswith('kakao_weather_regions'):
        if {catalog_error}:
            from modules.shared.hwarang_auth import HwarangAuthError
            raise HwarangAuthError('private backend detail')
        return {regions!r}
    if path.endswith('kakao_save_weather_region'):
        st.session_state['weather_saved']={{'weather_region_key':kwargs['json']['p_region_key']}}
        return {{}}
    if path.endswith('kakao_my_test_status'): return {test_status!r}
    if path.endswith('kakao_request_test'): return {{'id':kwargs['json']['p_request_id'],'status':'queued'}}
    if path.endswith('kakao_admin_status'): return {admin_rows!r}
    if path.endswith('kakao_admin_history'): return {history!r}
    return {{}}
with patch('modules.activity.kakao_settings.enabled',return_value={flag}), patch('modules.activity.kakao_settings.client') as c:
    c.return_value[0]._request.side_effect=call
    c.return_value=(c.return_value[0], 'test')
    render_panel()
''').run()


def test_disabled_has_no_api_calls():
    at=app(flag=False)
    assert not at.exception
    assert 'calls' not in at.session_state
    assert not at.button


def test_preferences_uses_self_authenticated_rpc_without_owner():
    at=app()
    assert not at.exception
    at.toggle[0].set_value(True)
    at.button(key='FormSubmitter:kakao_preferences-저장').click().run()
    assert not at.exception
    writes=[c for c in at.session_state['calls'] if c[0].endswith('kakao_save_preferences')]
    assert writes[0][1]['json']=={'p_enabled':True,'p_time':'08:00','p_days':[1,2,3,4,5],'p_send_empty':True}
    assert writes[0][1]['access_token']=='test'
    assert not any('admin' in c[0] for c in at.session_state['calls'])


def test_no_days_cannot_save():
    at=app()
    at.toggle[0].set_value(True)
    at.multiselect[0].set_value([])
    at.button(key='FormSubmitter:kakao_preferences-저장').click().run()
    assert not at.exception
    assert not any(c[0].endswith('kakao_save_preferences') for c in at.session_state['calls'])


def test_revoke_requires_explicit_action():
    at=app()
    assert not any(c[0].endswith('kakao_disconnect') for c in at.session_state['calls'])
    at.checkbox(key='kakao_disconnect_confirm').check().run()
    at.button(key='kakao_disconnect').click().run()
    assert not at.exception
    assert len([c for c in at.session_state['calls'] if c[0].endswith('kakao_disconnect')])==1


def test_connection_url_rejects_external_or_wrong_routes():
    svc=Mock(config=SimpleNamespace(url='https://project.supabase.co'))
    for url in ['https://evil.example/start','https://project.supabase.co/functions/v1/other/start','javascript:alert(1)','https://project.supabase.co@evil.example/functions/v1/hwarang-kakao/start']:
        svc._request.return_value={'url':url}
        with pytest.raises(HwarangAuthError): connection_url(svc,'token')
    valid='https://project.supabase.co/functions/v1/hwarang-kakao/start?ticket=abc'
    svc._request.return_value={'url':valid}
    assert connection_url(svc,'token')==valid


def test_legacy_personal_preserved_no_new_connection_or_subscription():
    at=app({'connection_status':'disconnected','legacy_personal':True,'can_manage':True})
    assert not at.exception
    assert any('기존 개인용' in x.value for x in at.info)
    assert not at.toggle
    assert not any(b.key in ['kakao_connect','kakao_disconnect'] for b in at.button)
    assert any(c.key=='kakao_admin_load' for c in at.checkbox)
    assert all(c[0].endswith('kakao_my_status') for c in at.session_state['calls'])


@pytest.mark.parametrize('outcome,label',[
    ('api_accepted','카카오 접수 완료'),('setup_failed','발송 준비 실패'),
    ('outcome_uncertain','결과 확인 필요'),('reauth_required','재연결 필요'),
    ('revoked','연결 해제로 중단'),('paused','발송 중지'),
    ('quota_held','무료 한도 확인 대기'),('empty_day_skipped','일정 없어 생략'),
    ('scope_changed','권한 변경으로 중단'),
])
def test_backend_outcome_codes_have_safe_labels(outcome,label):
    at=app({'connection_status':'connected','last_outcome':outcome})
    assert not at.exception
    assert any(c.value=='최근 발송: '+label for c in at.caption)


def test_save_does_not_claim_delivery_started():
    at=app()
    at.button(key='FormSubmitter:kakao_preferences-저장').click().run()
    assert any('실제 발송은 서비스 운영 상태와 무료 한도' in x.value for x in at.success)


def test_pending_confirmation_is_masked_and_blocks_subscriptions():
    at=app({'connection_status':'pending_confirmation'})
    assert not at.exception
    assert at.text_input(key='kakao_confirmation_code').proto.type==1
    assert not at.toggle
    assert not any(b.key=='kakao_connect' for b in at.button)


def test_invalid_confirmation_cleared_and_never_sent():
    at=app({'connection_status':'pending_confirmation'})
    at.text_input(key='kakao_confirmation_code').input('not-a-code')
    at.button(key='kakao_confirm').click().run()
    assert not at.exception
    assert at.text_input(key='kakao_confirmation_code').value==''
    assert not any(c[0].endswith('kakao_confirm_connection') for c in at.session_state['calls'])


def test_valid_confirmation_only_hash_transmitted():
    import hashlib
    at=app({'connection_status':'pending_confirmation'})
    code='a'*64
    at.text_input(key='kakao_confirmation_code').input(code)
    service=Mock()
    with patch('modules.activity.kakao_settings.client', return_value=(service,'test')):
        at.button(key='kakao_confirm').click().run()
    assert not at.exception
    service._request.assert_called_once_with('POST','/rest/v1/rpc/kakao_confirm_connection',access_token='test',json={'p_receipt_hash':hashlib.sha256(code.encode()).hexdigest()})
    assert at.text_input(key='kakao_confirmation_code').value==''
    assert code not in str(at.session_state['calls'])
    assert not any(code in x.value for x in list(at.caption)+list(at.error)+list(at.success))


def test_pending_cancel_clears_code_and_only_disconnects():
    at=app({'connection_status':'pending_confirmation'})
    at.text_input(key='kakao_confirmation_code').input('a'*64)
    service=Mock()
    with patch('modules.activity.kakao_settings.client',return_value=(service,'test')):
        at.button(key='kakao_cancel_pending').click().run()
    assert not at.exception
    service._request.assert_called_once_with('POST','/rest/v1/rpc/kakao_disconnect',access_token='test',json={})
    assert at.text_input(key='kakao_confirmation_code').value==''
    assert not any('send' in call[0] for call in at.session_state['calls'])


def test_pending_reconnect_is_explicit_and_lifetime_visible():
    at=app({'connection_status':'pending_confirmation'})
    assert not at.exception
    assert at.button(key='kakao_reconnect').label=='기존 신청 대신 다시 연결'
    assert any('10분' in c.value for c in at.caption)
    assert all(c[0].endswith('kakao_my_status') for c in at.session_state['calls'])


def test_pending_reconnect_clears_code_then_creates_new_link():
    at=app({'connection_status':'pending_confirmation'})
    at.text_input(key='kakao_confirmation_code').input('a'*64)
    with patch('modules.activity.kakao_settings.connection_url',return_value='https://project.supabase.co/functions/v1/hwarang-kakao/start?ticket=test') as connect:
        at.button(key='kakao_reconnect').click().run()
    assert not at.exception
    connect.assert_called_once()
    assert at.text_input(key='kakao_confirmation_code').value==''
    assert not any(c[0].endswith('kakao_confirm_connection') for c in at.session_state['calls'])


def test_schedule_missed_without_attempt_is_not_success_or_no_record():
    at=app({'connection_status':'connected','last_outcome':'schedule_missed','last_attempt_at':None})
    assert not at.exception
    assert any(c.value=='최근 발송: 예정 시간 경과 · 미발송' for c in at.caption)
    assert not at.success
    assert not any('발송 기록 없음' in c.value for c in at.caption)


def test_admin_schedule_missed_without_attempt_and_history():
    at=app({'connection_status':'connected','can_manage':True}, admin_rows=[{'owner_id':'user','label':'테스트','connection_status':'connected','last_outcome':'schedule_missed','last_attempt_at':None}], history=[{'day':'2026-11-16','part':None,'status':'skipped','outcome':'schedule_missed','claimed_at':None,'completed_at':None}])
    at.checkbox(key='kakao_admin_load').check().run()
    assert not at.exception
    assert any('예정 시간 경과 · 미발송' in c.value for c in at.caption)
    assert not any('발송 기록 없음' in c.value for c in at.caption)
    at.button(key='kakao_admin_history').click().run()
    assert not at.exception
    assert any(c.value=='2026-11-16 · 전체 · 예정 시간 경과 · 미발송' for c in at.caption)
    assert not at.success


def test_partial_deadline_status_preserves_accepted_count():
    at=app({'connection_status':'connected','last_outcome':'schedule_missed','accepted_parts':1,'total_parts':3})
    assert not at.exception
    assert any(c.value=='최근 발송: 일부 발송 · 1/3건, 나머지 시간 경과' for c in at.caption)
    assert not at.success


def test_partial_deadline_admin_status_preserves_accepted_count():
    at=app({'connection_status':'connected','can_manage':True},admin_rows=[{'owner_id':'user','label':'테스트','connection_status':'connected','last_outcome':'schedule_missed','accepted_parts':2,'total_parts':3}])
    at.checkbox(key='kakao_admin_load').check().run()
    assert not at.exception
    assert any('일부 발송 · 2/3건, 나머지 시간 경과' in c.value for c in at.caption)
    assert not at.success


def test_partial_outcome_label_only_trusts_valid_counts():
    from modules.activity.kakao_settings import outcome_label
    for accepted,total in [(0,3),(1,None),(True,3),(1,0),(3,3),(4,3),(1,9007199254740992)]:
        assert outcome_label({'last_outcome':'schedule_missed','accepted_parts':accepted,'total_parts':total})==('예정 시간 경과 · 미발송' if accepted==0 else '발송 상태 확인 필요')
    assert outcome_label({'last_outcome':'api_accepted','accepted_parts':1,'total_parts':1})=='카카오 접수 완료'


def test_more_than_three_parts_are_shown_without_truncation():
    at=app({'connection_status':'connected','last_outcome':'schedule_missed','accepted_parts':4,'total_parts':8})
    assert not at.exception
    assert any(c.value=='최근 발송: 일부 발송 · 4/8건, 나머지 시간 경과' for c in at.caption)
    assert not at.success

def test_admin_history_uses_days_rpc_contract():
    at=app({'connection_status':'disconnected','can_manage':True}, admin_rows=[{'owner_id':'other','label':'Other','connection_status':'connected'}], history=[])
    at.checkbox(key='kakao_admin_load').check().run()
    at.button(key='kakao_admin_history').click().run()
    calls=[c for c in at.session_state['calls'] if c[0].endswith('kakao_admin_history')]
    assert calls[-1][1]['json']=={'p_owner_id':'other','p_days':7}


def test_dispatch_off_is_explicit_without_changing_subscription():
    at=app({'connection_status':'connected','dispatch_ready':False,'enabled':True,'time':'08:00','days':[1],'send_empty':True})
    assert not at.exception
    assert any('자동 발송이 꺼져' in i.value for i in at.info)
    assert all(c[0].endswith(('kakao_my_status', 'kakao_weather_regions', 'kakao_my_test_status')) for c in at.session_state['calls'])


def test_new_dispatch_off_does_not_mislabel_preserved_personal_briefing():
    at=app({'connection_status':'disconnected','dispatch_ready':False,'legacy_personal':True})
    assert not at.exception
    assert any('기존 개인용' in i.value for i in at.info)
    assert not any('자동 발송이 꺼져' in i.value for i in at.info)


def test_personal_owner_is_not_mislabeled_disconnected():
    at=app({'connection_status':'disconnected','legacy_personal':True,'dispatch_ready':False})
    assert not at.exception
    assert any('연결 방식: 기존 개인용' in m.value for m in at.markdown)
    assert not any('카카오 연결: 미연결' in m.value for m in at.markdown)


def test_weather_requires_explicit_blank_selection_and_no_inference():
    at=app({'connection_status':'connected','enabled':False})
    assert at.selectbox(key='kakao_weather_region').value==''
    at.toggle[0].set_value(True)
    at.button(key='FormSubmitter:kakao_preferences-저장').click().run()
    assert not any(c[0].endswith('kakao_save_preferences') for c in at.session_state['calls'])
    assert any('날씨 지역을 먼저' in e.value for e in at.error)


def test_weather_valid_selection_persists_only_key_to_self_rpc():
    at=app({'connection_status':'connected','enabled':False})
    at.selectbox(key='kakao_weather_region').select('seoul-songpa')
    at.button(key='FormSubmitter:kakao_weather-날씨 지역 저장').click().run()
    assert not at.exception
    calls=[c for c in at.session_state['calls'] if c[0].endswith('kakao_save_weather_region')]
    assert len(calls)==1
    assert calls[0][1]=={'access_token':'test','json':{'p_region_key':'seoul-songpa'}}
    assert at.session_state['weather_saved']=={'weather_region_key':'seoul-songpa'}
    at.toggle[0].set_value(True)
    at.button(key='FormSubmitter:kakao_preferences-저장').click().run()
    assert any(c[0].endswith('kakao_save_preferences') for c in at.session_state['calls'])


def test_weather_empty_and_unknown_region_not_saved_or_inferred():
    at=app({'connection_status':'connected','weather_region_key':'not-in-catalog'})
    assert at.selectbox(key='kakao_weather_region').value==''
    at.button(key='FormSubmitter:kakao_weather-날씨 지역 저장').click().run()
    assert not at.exception
    assert not any(c[0].endswith('kakao_save_weather_region') for c in at.session_state['calls'])


@pytest.mark.parametrize('catalog_error',[False,True])
def test_unavailable_weather_catalog_still_allows_pause(catalog_error):
    at=app({'connection_status':'connected','enabled':True,'days':[]},regions=[],catalog_error=catalog_error)
    assert not at.exception
    assert any('날씨 지역 목록' in i.value for i in at.info)
    assert not any('private backend' in e.value for e in at.error)
    at.toggle[0].set_value(False)
    at.button(key='FormSubmitter:kakao_preferences-저장').click().run()
    assert not at.exception
    assert any(c[0].endswith('kakao_save_preferences') and c[1]['json']['p_enabled'] is False for c in at.session_state['calls'])


def test_weather_not_added_to_admin_personal_data_display():
    at=app({'connection_status':'connected','can_manage':True},admin_rows=[{'owner_id':'other','label':'동료','connection_status':'connected','weather_region_key':'private-region','display_name':'private-location'}])
    at.checkbox(key='kakao_admin_load').check().run()
    assert not at.exception
    text=' '.join(x.value for x in list(at.caption)+list(at.markdown)+list(at.info))
    assert 'private-region' not in text and 'private-location' not in text
    assert not any(c[0].endswith('kakao_save_weather_region') for c in at.session_state['calls'])


def test_repeat_test_uses_authenticated_id_only_and_keeps_id_after_unknown_response():
    at=app()
    service=Mock()
    service._request.side_effect=HwarangAuthError('unknown response with private detail')
    with patch('modules.activity.kakao_settings.client',return_value=(service,'test')):
        at.button(key='kakao_test_send').click().run()
    assert not at.exception
    request_id=at.session_state['kakao_test_request_id']
    with patch('modules.activity.kakao_settings.client',return_value=(service,'test')):
        at.button(key='kakao_test_send').click().run()
    assert service._request.call_count==2
    for call in service._request.call_args_list:
        assert call.args==('POST','/rest/v1/rpc/kakao_request_test')
        assert call.kwargs=={'access_token':'test','json':{'p_request_id':request_id}}
    assert not any('private detail' in w.value for w in at.warning)
    assert not any(c[0].endswith('kakao_save_preferences') for c in at.session_state['calls'])


@pytest.mark.parametrize('state',['queued','processing','uncertain'])
def test_repeat_test_pending_or_uncertain_disables_new_send(state):
    at=app(test_status={'id':'request','status':state})
    assert not at.exception
    assert at.button(key='kakao_test_send').disabled
    assert not any(c[0].endswith('kakao_request_test') for c in at.session_state['calls'])


def test_repeat_test_disabled_until_region_and_dispatch_ready():
    for status in [{'connection_status':'connected','dispatch_ready':False,'weather_region_key':'seoul-songpa'}, {'connection_status':'connected','dispatch_ready':True}]:
        at=app(status)
        assert not at.exception
        assert at.button(key='kakao_test_send').disabled


def test_welcome_setup_guidance_does_not_send_when_off():
    at=app({'connection_status':'connected','enabled':False,'welcome':{'status':'waiting_setup'},'weather_region_key':'seoul-songpa'})
    assert not at.exception
    assert any('날씨 지역을 저장' in x.value for x in at.info)
    assert any('켜기 전에는 발송하지 않습니다' in x.value for x in at.caption)
    assert not any('welcome' in path or 'request_test' in path for path,_ in at.session_state['calls'])


def test_existing_user_has_no_welcome_prompt():
    at=app({'connection_status':'connected','enabled':True,'welcome':{'status':'legacy_excluded'},'weather_region_key':'seoul-songpa'})
    assert not at.exception
    assert not any('첫 브리핑' in x.value for x in list(at.info)+list(at.success)+list(at.warning))


@pytest.mark.parametrize('state',['queued','processing','accepted','uncertain','failed','expired'])
def test_welcome_progress_is_sanitized_and_never_resends(state):
    at=app({'connection_status':'connected','enabled':True,'welcome':{'status':state,'secret':'private-detail'},'weather_region_key':'seoul-songpa'})
    assert not at.exception
    text=' '.join(x.value for x in list(at.info)+list(at.success)+list(at.warning)+list(at.caption))
    assert '첫 브리핑' in text
    assert 'private-detail' not in text
    assert not any('welcome' in path or 'request_test' in path for path,_ in at.session_state['calls'])


def test_welcome_operational_hold_is_explicit_not_claimed_sending():
    at=app({'connection_status':'connected','enabled':True,'welcome':{'status':'waiting_setup','reason':'service_unavailable_resave'},'weather_region_key':'seoul-songpa'})
    assert not at.exception
    assert any('아직 대기 중' in x.value and '다시 저장' in x.value for x in at.info)
    assert not any('처리하고 있습니다' in x.value for x in at.info)

def test_member_preference_and_preview_are_self_scoped_and_do_not_send():
    at = AppTest.from_string("""
import streamlit as st
from unittest.mock import Mock
from modules.activity.kakao_settings import render_member_briefing
service=Mock()
def call(method,path,**kwargs):
    st.session_state.setdefault('member_calls',[]).append((path,kwargs))
    state={'eligible':True,'enabled':True,'branch':{'members':[{'name':'합성FP'}]}}
    if path.endswith('member-preview'):
        return {**state,'parts':['합성FP 1건']}
    return state
service._request.side_effect=call
render_member_briefing(service,'self-token')
""").run()
    assert not at.exception
    at.checkbox[0].uncheck()
    at.button(key='FormSubmitter:kakao_member_preferences-구성원 설정 저장').click().run()
    writes=[c for c in at.session_state['member_calls'] if c[0].endswith('kakao_save_member_briefing')]
    assert writes[-1][1]['json']=={'p_enabled':False}
    assert writes[-1][1]['access_token']=='self-token'
    at.button(key='kakao_member_preview').click().run()
    assert not at.exception
    assert at.code[0].value=='합성FP 1건'
    assert not any('request_test' in c[0] or 'send' in c[0] for c in at.session_state['member_calls'])
