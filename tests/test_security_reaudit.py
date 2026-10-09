"""Offline regressions: synthetic credentials, fake Auth, no email/API/DB calls."""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from modules.shared.account_security import password_validation_error, request_recovery
from modules.shared.hwarang_auth import HwarangAuthService, HwarangAuthError, SupabaseConfig
from modules.briefing.normalize import classify_freshness
from modules.briefing.market_metrics import collect_metrics, validated_metrics, METRICS
from modules.briefing.public_body import customer_body, public_html, public_pdf
from modules.briefing.diagnostics import build_info

ACCOUNT_SCRIPT = '''
import streamlit as st
from modules.shared.account_security import account_dialog
from modules.shared.hwarang_auth import HwarangAuthError
class FakeAuth:
    def _request(self, method, path, **kwargs):
        st.session_state.setdefault('fake_calls', []).append((method,path))
        if method == 'GET': return {'id':'synthetic-user','email':'test@example.org'}
        if st.session_state.get('backend_failure') and method == 'PUT':
            raise HwarangAuthError('새 비밀번호가 계정 서버의 보안 기준을 충족하지 않습니다.', status=422,code='weak_password')
        return {'id':'synthetic-user'}
    def sign_in(self, login_id, current):
        st.session_state.setdefault('fake_calls', []).append(('VERIFY',login_id))
        if current != 'CurrentExample1!': raise HwarangAuthError('아이디 또는 비밀번호를 확인해 주세요.',status=400,code='invalid_credentials')
        return {'access_token':'synthetic-token','profile':{'id':st.session_state.get('verified_id','synthetic-user')}}
if st.session_state.get('hw_account_flash'):
    st.success(st.session_state['hw_account_flash'])
else:
    st.session_state.setdefault('hwarang_auth', {'access_token':'synthetic-token','profile':{'id':'synthetic-user','login_id':'synthetic'}})
    account_dialog(FakeAuth())
'''

RECOVERY_SCRIPT = '''
import streamlit as st
from modules.shared.account_security import recovery_dialog
from modules.shared.hwarang_auth import HwarangAuthError
class FakeAuth:
    def _request(self, method, path, **kwargs):
        st.session_state.setdefault('fake_calls', []).append((method,path))
        if st.session_state.get('backend_failure'):
            raise HwarangAuthError('계정 서버가 메일을 발송하지 못했습니다. SMTP 발송 설정과 Auth 로그를 확인해야 합니다.',status=500,code='unexpected_failure')
        return {}
recovery_dialog(FakeAuth())
'''

RESET_SCRIPT = '''
import streamlit as st
from modules.shared.account_security import render_recovery_entry
class FakeAuth:
    def _request(self, method, path, **kwargs):
        st.session_state.setdefault('fake_calls', []).append((method,path))
        if path.endswith('/verify'): return {'access_token':'synthetic-token','expires_in':600,'user':{'id':'synthetic-user'}}
        return {'id':'synthetic-user'}
if not render_recovery_entry(FakeAuth()): st.success(st.session_state.get('hw_account_flash','Login screen'))
'''

def click(at, label):
    return next(b for b in at.button if b.label == label).click().run()

def fill_account(at, current='CurrentExample1!', new='NewExample2!', confirm=None):
    at.text_input(key='hw_account_current_password').input(current)
    at.text_input(key='hw_account_new_password').input(new)
    at.text_input(key='hw_account_confirm_password').input(new if confirm is None else confirm)
    return click(at,'비밀번호 변경')

@pytest.mark.parametrize('current,new,confirm,expected', [
    ('','NewExample2!','NewExample2!','현재 비밀번호'),
    ('CurrentExample1!','Short2','Short2','8~128자'),
    ('CurrentExample1!','123456789','123456789','영문'),
    ('CurrentExample1!','OnlyLetters!','OnlyLetters!','숫자'),
    ('CurrentExample1!','NewExample2!','OtherExample3!','일치'),
    ('CurrentExample1!','CurrentExample1!','CurrentExample1!','현재와 다른'),
])
def test_invalid_password_does_not_update(current,new,confirm,expected):
    at=AppTest.from_string(ACCOUNT_SCRIPT).run()
    fill_account(at,current,new,confirm)
    assert not at.exception
    assert expected in at.error[0].value
    assert not any(method in {'PUT','VERIFY'} for method,path in at.session_state['fake_calls'])

def test_valid_change_clears_login_and_calls_global_logout():
    at=AppTest.from_string(ACCOUNT_SCRIPT).run()
    fill_account(at)
    assert not at.exception
    assert '다시 로그인' in at.success[0].value
    assert 'hwarang_auth' not in at.session_state

def test_wrong_current_password_is_not_policy_error():
    at=AppTest.from_string(ACCOUNT_SCRIPT).run()
    fill_account(at,current='WrongExample1!')
    assert not at.exception
    assert '아이디 또는 비밀번호' in at.error[0].value
    assert not any(method=='PUT' for method,path in at.session_state['fake_calls'])

def test_verified_identity_must_match():
    at=AppTest.from_string(ACCOUNT_SCRIPT).run()
    at.session_state['verified_id']='different-synthetic-user'
    fill_account(at)
    assert not at.exception
    assert '현재 로그인한 계정' in at.error[0].value
    assert not any(method=='PUT' for method,path in at.session_state['fake_calls'])

def test_backend_error_is_visible_and_login_preserved():
    at=AppTest.from_string(ACCOUNT_SCRIPT).run()
    at.session_state['backend_failure']=True
    fill_account(at)
    assert not at.exception
    assert 'HTTP 422' in at.error[0].value and 'weak_password' in at.error[0].value
    assert 'hwarang_auth' in at.session_state

def test_invalid_email_never_calls_backend():
    auth=Mock()
    with pytest.raises(HwarangAuthError): request_recovery(auth,'not-an-email')
    auth._request.assert_not_called()

def test_recovery_smtp_error_keeps_server_diagnostic():
    at=AppTest.from_string(RECOVERY_SCRIPT).run()
    at.session_state['backend_failure']=True
    at.text_input[0].input('test@example.org')
    click(at,'재설정 메일 받기')
    assert not at.exception
    assert 'HTTP 500' in at.error[0].value and 'SMTP' in at.error[0].value
    assert '이메일 형식' not in at.error[0].value

def test_recovery_success_and_cooldown_no_double_send():
    at=AppTest.from_string(RECOVERY_SCRIPT).run()
    at.text_input[0].input('test@example.org');click(at,'재설정 메일 받기')
    assert not at.exception and len(at.session_state['fake_calls'])==1
    click(at,'재설정 메일 받기')
    assert not at.exception and len(at.session_state['fake_calls'])==1
    assert at.info

def test_reset_link_requires_explicit_verification_and_clears_token():
    at=AppTest.from_string(RESET_SCRIPT)
    at.query_params['recovery_token']='a'*32
    at.run()
    assert not at.exception and 'fake_calls' not in at.session_state
    click(at,'인증 확인하고 계속')
    assert not at.exception and 'recovery_token' not in at.query_params
    at.text_input(key='hw_reset_new_password').input('ResetExample3!')
    at.text_input(key='hw_reset_confirm_password').input('ResetExample3!')
    click(at,'새 비밀번호 저장')
    assert not at.exception and '변경했습니다' in at.success[0].value
    assert 'hw_password_recovery' not in at.session_state

@pytest.mark.parametrize('code,status,text',[
    ('email_address_not_authorized',400,'발송 서비스'),
    ('over_email_send_rate_limit',429,'한도'),
    ('same_password',422,'현재와 다른'),
    ('weak_password',422,'보안 기준'),
    ('reauthentication_needed',422,'다시 로그인'),
])
def test_auth_error_codes(code,status,text):
    assert text in HwarangAuthService._friendly_error(status,'opaque server message',code)

def test_auth_failure_logs_no_server_payload(caplog):
    auth=HwarangAuthService(SupabaseConfig('https://example.org','synthetic-public','synthetic-secret'))
    response=Mock(status_code=500)
    response.json.return_value={'msg':'Error sending recovery email test@example.org','error_code':'unexpected_failure'}
    auth.http=Mock();auth.http.request.return_value=response
    with pytest.raises(HwarangAuthError) as caught:auth._request('POST','/auth/v1/recover',json={'email':'test@example.org'})
    assert caught.value.code=='unexpected_failure' and caught.value.status==500
    assert 'test@example.org' not in caplog.text

def test_holiday_news_uses_previous_calendar_day_not_business_day():
    as_of=datetime(2026,10,8,22,30,tzinfo=timezone.utc) # Oct 9 07:30 KST
    assert classify_freshness(datetime(2026,10,7,15,tzinfo=timezone.utc),as_of)=='core_window'
    assert classify_freshness(datetime(2026,10,7,14,59,tzinfo=timezone.utc),as_of)=='stale'
    assert classify_freshness(as_of+timedelta(seconds=1),as_of)=='undated'

def test_market_can_use_last_confirmed_day_and_reject_future():
    as_of=datetime(2026,10,8,22,tzinfo=timezone.utc)
    rows=[]
    for code,(label,unit) in METRICS.items():
        rows.append(dict(code=code,instrument_code=code,value=100,previous_value=99,unit=unit,
            observed_at=(as_of-timedelta(days=1)).isoformat(),source_url='https://example.org/market',
            source_name='Synthetic source',display_allowed=True,external_allowed=True,
            observation_kind='nominal_treasury_yield' if code=='US10Y' else 'spot_exchange_rate' if code=='USDKRW' else 'closing_index'))
    result=validated_metrics(rows,as_of)
    assert result['complete'] and all(r['observed_at']!=as_of.isoformat() for r in result['items'])
    rows[0]['observed_at']=(as_of+timedelta(days=1)).isoformat()
    assert 'KOSPI' in validated_metrics(rows,as_of)['missing']

def test_market_missing_config_is_explicit(monkeypatch):
    for name in ('BRIEFING_MARKET_OBSERVATIONS_JSON','BRIEFING_MARKET_OBSERVATIONS_FILE','BRIEFING_MARKET_OBSERVATIONS_URL'):monkeypatch.delenv(name,raising=False)
    result=collect_metrics(datetime.now(timezone.utc))
    assert result['collection_status']=='not_configured' and len(result['missing'])==6

def test_customer_body_excludes_internal_actions_and_names_sender():
    body=customer_body({'profile_code':'NEWS','profile_label':'종합뉴스 브리핑','issues':[],
         'conversation_payload':{'private':'INTERNAL_ONLY'},'eligible_analysis_pool':['INTERNAL_ONLY']})
    assert 'INTERNAL_ONLY' not in str(body)
    rendered=public_html({'briefing_date':'2026-10-09','sender':{'name':'테스트 사용자','position':'팀장'},'body':body})
    assert 'og:title' in rendered and '테스트 사용자 팀장' in rendered
    assert public_pdf({'briefing_date':'2026-10-09','sender':{'name':'테스트 사용자','position':'팀장'},'body':body}).startswith(b'%PDF')

def test_original_briefing_release_hashes_match():
    assert build_info()['code_matches_release']
