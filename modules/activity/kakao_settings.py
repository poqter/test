"""Opt-in Kakao self-memo settings; identity and authorization remain server-owned."""
from datetime import time
import hashlib
import re
import uuid
from urllib.parse import urlsplit
import streamlit as st
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService, SupabaseConfig

DAYS = {1: '월', 2: '화', 3: '수', 4: '목', 5: '금', 6: '토', 0: '일'}
STATUSES = {'connected': '연결됨', 'disconnected': '미연결', 'revoked': '연결 해제됨', 'reauth_required': '재연결 필요', 'connecting': '연결 확인 중', 'pending_confirmation': '본인 연결 확인 필요'}
OUTCOMES = {'welcome_day_reserved': '첫 브리핑 처리일 · 정기 중복 생략', 'schedule_missed': '예정 시간 경과 · 미발송', 'api_accepted': '카카오 접수 완료', 'setup_failed': '발송 준비 실패', 'outcome_uncertain': '결과 확인 필요', 'reauth_required': '재연결 필요', 'revoked': '연결 해제로 중단', 'paused': '발송 중지', 'quota_held': '무료 한도 확인 대기', 'empty_day_skipped': '일정 없어 생략', 'scope_changed': '권한 변경으로 중단', 'accepted': '카카오 접수 완료', 'failed': '발송 실패', 'uncertain': '결과 확인 필요', 'queued': '대기', 'sending': '발송 중', 'skipped': '발송 생략', 'cancelled': '취소'}


def outcome_label(row, fallback='확인 필요'):
    outcome = row.get('last_outcome') or row.get('outcome') or row.get('status')
    accepted, total = row.get('accepted_parts'), row.get('total_parts')
    if outcome == 'schedule_missed' and isinstance(accepted, int) and not isinstance(accepted, bool) and isinstance(total, int) and not isinstance(total, bool) and 0 < accepted < total <= 9007199254740991:
        return f'일부 발송 · {accepted}/{total}건, 나머지 시간 경과'
    if outcome == 'schedule_missed' and accepted not in (None, 0):
        return '발송 상태 확인 필요'
    return OUTCOMES.get(outcome, fallback)


def enabled():
    try:
        return st.secrets.get('HWARANG_KAKAO_MULTI_ENABLED', False) is True
    except (FileNotFoundError, KeyError):
        return False


def client():
    token = st.session_state.get('hwarang_auth', {}).get('access_token')
    if not token:
        raise HwarangAuthError('다시 로그인해 주세요.')
    return HwarangAuthService(SupabaseConfig.from_mapping(st.secrets)), token


def rpc(service, token, name, payload=None):
    return service._request('POST', '/rest/v1/rpc/' + name, access_token=token, json=payload or {})


def connection_url(service, token):
    result = service._request('POST', '/functions/v1/hwarang-kakao/connect', access_token=token, json={})
    url = result.get('url', '') if isinstance(result, dict) else ''
    parsed, base = urlsplit(url), urlsplit(service.config.url)
    if parsed.scheme != 'https' or parsed.netloc != base.netloc or parsed.path != '/functions/v1/hwarang-kakao/start' or parsed.username or parsed.fragment:
        raise HwarangAuthError('연결 주소를 확인하지 못했습니다. 다시 시도해 주세요.')
    return url


def _local_time(value):
    try:
        hours, minutes = str(value or '08:00').split(':')[:2]
        return time(int(hours), int(minutes))
    except (ValueError, TypeError):
        return time(8)


def confirm_connection(service, token, code):
    if not re.fullmatch(r'[a-f0-9]{64}', code or ''):
        raise ValueError('Invalid confirmation code')
    return rpc(service, token, 'kakao_confirm_connection', {'p_receipt_hash': hashlib.sha256(code.encode('ascii')).hexdigest()})


def _confirm_action():
    code = st.session_state.get('kakao_confirmation_code', '')
    # Remove the raw code before any network call or exception; never retain it in feedback.
    st.session_state['kakao_confirmation_code'] = ''
    try:
        service, token = client()
        confirm_connection(service, token, code)
        st.session_state['kakao_confirmation_feedback'] = 'confirmed'
    except ValueError:
        st.session_state['kakao_confirmation_feedback'] = 'invalid'
    except HwarangAuthError:
        st.session_state['kakao_confirmation_feedback'] = 'failed'


def _clear_confirmation():
    st.session_state['kakao_confirmation_code'] = ''
    st.session_state.pop('kakao_connect_url', None)
    st.session_state.pop('kakao_confirmation_feedback', None)


def _cancel_pending():
    _clear_confirmation()
    try:
        service, token = client()
        rpc(service, token, 'kakao_disconnect')
        st.session_state['kakao_cancel_feedback'] = 'cancelled'
    except HwarangAuthError:
        st.session_state['kakao_cancel_feedback'] = 'failed'


def render_weather_region(service, token, status):
    try:
        rows = rpc(service, token, 'kakao_weather_regions')
    except HwarangAuthError:
        rows = []
    regions = {row['region_key']: row['display_name'] for row in rows if isinstance(row, dict) and isinstance(row.get('region_key'), str) and row['region_key'] and isinstance(row.get('display_name'), str)} if isinstance(rows, list) else {}
    saved = status.get('weather_region_key')
    if not regions:
        st.info('날씨 지역 목록을 준비 중이거나 불러오지 못했습니다. 잠시 후 다시 확인해 주세요. 발송 일시중지는 가능합니다.')
        return False
    labels = {'': '지역을 선택해 주세요', **regions}
    if st.session_state.get('kakao_weather_region', '') not in labels:
        st.session_state.pop('kakao_weather_region', None)
    with st.form('kakao_weather'):
        selected = st.selectbox('브리핑 날씨 지역', list(labels), index=list(labels).index(saved) if saved in labels else 0, format_func=labels.get, key='kakao_weather_region')
        st.caption('시·도 대표 지점 기준입니다. 시·군·구 또는 현재 위치의 정확한 날씨가 아니며, 지역 내 차이가 있을 수 있습니다.')
        if st.form_submit_button('날씨 지역 저장'):
            if selected not in regions:
                st.error('날씨 지역을 직접 선택해 주세요.')
            else:
                rpc(service, token, 'kakao_save_weather_region', {'p_region_key': selected})
                st.rerun()
    return saved in regions



def render_welcome_status(status):
    """Owner-only onboarding progress; never expose backend errors or ticket details."""
    welcome = status.get('welcome')
    if not isinstance(welcome, dict):
        return
    state = welcome.get('status')
    if not state or state == 'legacy_excluded':
        return
    if state == 'waiting_setup' and welcome.get('reason') in ('service_unavailable_resave', 'budget_unavailable_resave'):
        st.info('첫 브리핑은 운영 상태 또는 무료 사용량 확인 때문에 아직 대기 중입니다. 운영이 재개되면 아래 신청 설정을 다시 저장해 주세요.')
    elif state == 'waiting_setup':
        st.info('첫 브리핑 준비: 아래에서 날씨 지역을 저장하고 정기 브리핑 받기를 켜 주세요. 설정이 완료되면 오늘의 일정·날씨를 한 번 보냅니다.')
        st.caption('정기 브리핑을 켜기 전에는 발송하지 않습니다. 이후에는 다음날부터 선택한 요일과 한국 시간에 받습니다.')
    elif state in ('queued', 'processing', 'reserved', 'sending'):
        st.info('첫 브리핑을 처리하고 있습니다. 다시 연결하거나 시험 발송을 누를 필요가 없습니다.')
        st.caption('오늘 정기 브리핑과 중복 발송하지 않으며, 이후에는 다음날부터 선택한 요일과 시간에 받습니다.')
    elif state == 'accepted':
        st.success('첫 브리핑을 카카오에서 접수했습니다. 실제 수신은 나와의 채팅에서 확인해 주세요.')
        st.caption('정기 브리핑은 다음날부터 선택한 요일과 한국 시간에 받습니다.')
    elif state in ('uncertain', 'failed', 'expired', 'cancelled'):
        st.warning('첫 브리핑이 완료되지 않았거나 결과 확인이 필요합니다. 일부 메시지가 도착했을 수 있어 자동으로 다시 보내지 않습니다.')
        st.caption('정기 브리핑은 다음날부터 저장된 요일과 시간에 따릅니다. 연결이나 권한 문제가 있다면 먼저 해결해 주세요.')
    elif state == 'suppressed_existing_delivery':
        st.caption('오늘의 브리핑 기록이 있어 첫 브리핑을 추가 발송하지 않았습니다.')
    if st.button('첫 브리핑 상태 새로고침', key='kakao_welcome_refresh'):
        st.rerun()


def _request_test():
    # Keep the same id across uncertain HTTP responses; a retry must not create another send.
    request_id = st.session_state.setdefault('kakao_test_request_id', str(uuid.uuid4()))
    try:
        service, token = client()
        result = rpc(service, token, 'kakao_request_test', {'p_request_id': request_id})
        st.session_state['kakao_test_feedback'] = 'requested' if isinstance(result, dict) and result.get('id') else 'failed'
    except HwarangAuthError:
        st.session_state['kakao_test_feedback'] = 'failed'


def render_test_panel(service, token, status, weather_ready):
    with st.expander('시험 발송'):
        st.caption('지금 정기 브리핑과 같은 모양으로 나에게 보냅니다. 정기 발송 시간은 바뀌지 않습니다.')
        st.caption('한 번에 1개 메시지. 진행 중이거나 결과가 불확실한 요청은 다시 보내지 않습니다. 무료 사용량과 정기 발송 몫을 보호합니다.')
        try:
            last = rpc(service, token, 'kakao_my_test_status')
        except HwarangAuthError:
            st.info('시험 발송 상태를 확인하지 못했습니다. 잠시 후 다시 열어 주세요.')
            return
        last = last if isinstance(last, dict) else {}
        state = last.get('status')
        if state == 'none':
            state = None
        labels = {'queued': '대기 중', 'processing': '발송 중', 'accepted': '카카오 접수 완료', 'failed': '미발송', 'expired': '요청 만료', 'uncertain': '결과 확인 필요 · 재발송하지 않음'}
        if state:
            st.caption('최근 시험: ' + labels.get(state, '확인 필요'))
        if state in ('accepted', 'failed', 'expired') and last.get('id') == st.session_state.get('kakao_test_request_id'):
            st.session_state.pop('kakao_test_request_id', None)
        feedback = st.session_state.pop('kakao_test_feedback', None)
        if feedback == 'requested':
            st.success('시험 발송을 요청했습니다. 카카오 접수 상태와 실제 수신을 확인해 주세요.')
        elif feedback == 'failed':
            st.warning('시험 요청을 완료하지 못했습니다. 최근 상태, 연결과 무료 사용량을 확인해 주세요.')
        st.button('시험 메시지 보내기', key='kakao_test_send', on_click=_request_test,
                  disabled=not weather_ready or status.get('dispatch_ready') is False or state in ('queued', 'processing', 'uncertain'))
        if st.button('시험 상태 새로고침', key='kakao_test_refresh'):
            st.rerun()


def render_panel():
    if not enabled():
        return
    owner = str(st.session_state.get('hwarang_auth', {}).get('profile', {}).get('id') or '')
    if st.session_state.get('kakao_ui_owner') != owner:
        for key in list(st.session_state):
            if key.startswith('kakao_'):
                del st.session_state[key]
        st.session_state['kakao_ui_owner'] = owner
    st.caption('내 카카오톡 ‘나와의 채팅’에 저장됩니다. 소리·팝업 알림은 오지 않습니다.')
    try:
        service, token = client()
        status = rpc(service, token, 'kakao_my_status')
        if not isinstance(status, dict):
            raise HwarangAuthError('설정을 확인하지 못했습니다.')
        if status.get('dispatch_ready') is False and not status.get('legacy_personal'):
            st.info('현재 자동 발송이 꺼져 있습니다. 연결·시간 설정만 저장되며, 카카오톡은 발송되지 않습니다.')
        if status.get('connection_status') == 'connected' and st.session_state.pop('kakao_confirmation_feedback', None) == 'confirmed':
            st.success('본인 연결을 확인했습니다. 아래에서 정기 브리핑을 신청할 수 있습니다.')
        cancel_feedback = st.session_state.pop('kakao_cancel_feedback', None)
        if cancel_feedback == 'cancelled':
            st.success('연결 신청을 취소했습니다. 필요할 때 다시 연결해 주세요.')
        elif cancel_feedback == 'failed':
            st.error('연결 취소를 처리하지 못했습니다. 다시 시도해 주세요.')
        if status.get('legacy_personal'):
            st.write('연결 방식: 기존 개인용 · 별도 관리')
        else:
            st.write('카카오 연결: ' + STATUSES.get(status.get('connection_status'), '확인 필요'))
        if status.get('admin_paused'):
            st.info('관리자가 발송을 중지한 상태입니다.')
        if status.get('last_outcome'):
            st.caption('최근 발송: ' + outcome_label(status))
        st.caption('접수 완료는 카카오 API의 처리 결과이며 실제 수신·읽음 확인은 아닙니다.')
        if status.get('legacy_personal'):
            st.info('기존 개인용 자동 브리핑을 그대로 유지합니다. 중복 발송을 막기 위해 여기서는 새 연결이나 신청을 하지 않습니다.')
        elif status.get('connection_status') == 'pending_confirmation':
            st.caption('카카오 인증 완료 화면의 확인 코드를 본인이 여기에 입력해 주세요. 다른 사람에게 공유하지 마세요.')
            st.caption('확인 코드는 10분 동안 유효합니다. 만료되었다면 아래에서 연결을 다시 시작해 주세요.')
            st.text_input('연결 확인 코드', type='password', key='kakao_confirmation_code')
            st.button('본인 연결 확인', key='kakao_confirm', on_click=_confirm_action)
            feedback = st.session_state.pop('kakao_confirmation_feedback', None)
            if feedback == 'invalid':
                st.error('인증 완료 화면의 64자리 확인 코드를 확인해 주세요.')
            elif feedback == 'failed':
                st.error('연결을 확인하지 못했습니다. 본인 계정으로 다시 시도해 주세요.')
            st.button('연결 취소', key='kakao_cancel_pending', on_click=_cancel_pending)
            if st.button('기존 신청 대신 다시 연결', key='kakao_reconnect', on_click=_clear_confirmation):
                link = connection_url(service, token)
                st.link_button('카카오 로그인으로 다시 연결하기', link, width='stretch')
                st.caption('새 인증을 시작합니다. 이전 확인 코드는 더 이상 사용할 수 없습니다.')
        elif status.get('connection_status') != 'connected':
            if st.button('내 카카오 계정 연결', key='kakao_connect'):
                link = connection_url(service, token)
                st.link_button('카카오 로그인으로 연결하기', link, width='stretch')
                st.caption('본인 계정으로 로그인하고 메시지 전송에 동의한 뒤 이 창으로 돌아와 새로고침하세요.')
            if st.button('연결 상태 새로고침', key='kakao_refresh'):
                st.session_state.pop('kakao_connect_url', None)
                st.rerun()
        else:
            st.session_state.pop('kakao_connect_url', None)
            render_welcome_status(status)
            weather_ready = render_weather_region(service, token, status)
            with st.form('kakao_preferences'):
                active = st.toggle('정기 브리핑 받기', value=bool(status.get('enabled')), key='kakao_enabled')
                send_time = st.time_input('받을 시간 · 한국 시간', value=_local_time(status.get('time')), step=60, key='kakao_time')
                days = st.multiselect('받을 요일', list(DAYS), default=[d for d in status.get('days', [1,2,3,4,5]) if d in DAYS], format_func=DAYS.get, key='kakao_days')
                empty = st.checkbox('일정이 없는 날에도 받기', value=bool(status.get('send_empty')), key='kakao_empty')
                if st.form_submit_button('저장', type='primary'):
                    if active and not weather_ready:
                        st.error('정기 브리핑을 받으려면 날씨 지역을 먼저 선택하고 저장해 주세요.')
                    elif active and not days:
                        st.error('받을 요일을 한 개 이상 선택해 주세요.')
                    else:
                        rpc(service, token, 'kakao_save_preferences', {'p_enabled': active, 'p_time': send_time.strftime('%H:%M'), 'p_days': days or status.get('days') or [1,2,3,4,5], 'p_send_empty': empty})
                        st.success('받을 시간과 신청 설정을 저장했습니다. 실제 발송은 서비스 운영 상태와 무료 한도에 따라 처리됩니다.')
                        if active and isinstance(status.get('welcome'), dict) and status['welcome'].get('status') == 'waiting_setup':
                            st.info('첫 브리핑 준비가 완료되면 오늘 내용을 한 번 보냅니다. 상태를 새로고침해 확인해 주세요.')
            render_test_panel(service, token, status, weather_ready)
            if st.checkbox('연결을 해제하고 앞으로의 발송을 중지합니다.', key='kakao_disconnect_confirm'):
                if st.button('카카오 연결 해제', key='kakao_disconnect'):
                    rpc(service, token, 'kakao_disconnect')
                    st.session_state.pop('kakao_connect_url', None)
                    st.success('연결을 해제했습니다. 다시 받으려면 직접 연결해 주세요.')
                    return
        if status.get('can_manage'):
            with st.expander('관리 · 연결 및 발송 상태'):
                if st.checkbox('관리 현황 보기', key='kakao_admin_load'):
                    rows = rpc(service, token, 'kakao_admin_status')
                    if isinstance(rows, list):
                        for row in rows:
                            st.write(str(row.get('label') or '이용자'))
                            st.caption(STATUSES.get(row.get('connection_status'), '확인 필요') + ' · ' + outcome_label(row, '발송 기록 없음'))
                        choices = {str(row['owner_id']): str(row.get('label') or '이용자') for row in rows if row.get('owner_id')}
                        if choices:
                            target = st.selectbox('확인할 이용자', list(choices), format_func=choices.get, key='kakao_admin_target')
                            if st.button('최근 발송 이력', key='kakao_admin_history'):
                                history = rpc(service, token, 'kakao_admin_history', {'p_owner_id': target, 'p_days': 7})
                                if isinstance(history, list):
                                    if not history:
                                        st.caption('발송 이력이 없습니다.')
                                    for item in history:
                                        st.caption(str(item.get('day') or '') + ' · ' + (('전체' if item.get('part') is None else str(item['part']) + '번째')) + ' · ' + outcome_label(item))
                            if st.button('선택 이용자 발송 중지', key='kakao_admin_pause'):
                                rpc(service, token, 'kakao_admin_pause', {'p_owner_id': target, 'p_paused': True})
                                st.success('발송을 중지했습니다.')
    except HwarangAuthError:
        # Never reflect backend error text: it may contain a token, URL, or message body.
        st.error('카카오 설정을 처리하지 못했습니다. 로그인 상태와 연결을 확인한 뒤 다시 시도해 주세요.')


@st.dialog('카카오 브리핑', width='small')
def settings_dialog():
    render_panel()
    if st.button('닫기', key='kakao_settings_close'):
        st.session_state.pop('kakao_connect_url', None)
        st.rerun()


def render_entry(prefix):
    if enabled() and st.button('카카오 브리핑', key=prefix + '_kakao_settings', width='stretch'):
        settings_dialog()
