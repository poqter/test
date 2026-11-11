"""Explicit, receipt-backed administrator writes; unknown results never become zero."""
from copy import deepcopy
from uuid import uuid4

from modules.shared.hwarang_auth import HwarangAuthError

PENDING = 'hw_admin_asset_request'
RESULT = 'hw_admin_asset_result'
RPC_NAMES = frozenset({
    'admin_adjust_hwarang_purchased_credits', 'admin_adjust_hwarang_voice_minutes',
    'admin_bulk_adjust_hwarang_purchased_credits', 'admin_bulk_adjust_hwarang_voice_minutes',
})


def validate_result(value, targets, request_id=None):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    expected = set(map(str, targets))
    if not isinstance(value, dict) or not expected:
        raise HwarangAuthError('처리 결과를 확인하지 못했습니다. 결과 확인을 먼저 진행해 주세요.')
    rows = value.get('results')
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise HwarangAuthError('대상별 처리 결과를 확인하지 못했습니다. 결과 확인을 먼저 진행해 주세요.')
    if any(not isinstance(row, dict) or row.get('status') not in ('success','failed') for row in rows):
        raise HwarangAuthError('대상별 처리 상태를 확인하지 못했습니다.')
    if {str(row.get('user_id')) for row in rows} != expected:
        raise HwarangAuthError('처리 대상과 응답이 일치하지 않습니다. 결과 확인이 필요합니다.')
    counts = {'requested_count':len(expected),
              'success_count':sum(row['status']=='success' for row in rows),
              'failed_count':sum(row['status']=='failed' for row in rows)}
    if any(type(value.get(k)) is not int or value[k] != n for k,n in counts.items()):
        raise HwarangAuthError('처리 인원과 대상별 결과가 일치하지 않습니다.')
    if request_id is not None and value.get('request_id') != request_id:
        raise HwarangAuthError('처리 요청을 확인하지 못했습니다.')
    return value


def prepare(session, rpc, payload):
    if session.get(PENDING):
        raise HwarangAuthError('확인이 끝나지 않은 자산 처리가 있습니다. 위의 결과 확인을 먼저 진행해 주세요.')
    targets = payload.get('p_target_user_ids') or [payload.get('p_target_user_id')]
    body = dict(p_actor_user_id=payload['p_actor_user_id'], p_request_id=str(uuid4()),
                p_asset='voice' if 'voice' in rpc else 'training_credit',
                p_target_user_ids=sorted(set(targets)), p_operation=payload['p_operation'],
                p_amount=payload.get('p_minutes',payload.get('p_amount')),
                p_source_type=payload['p_source_type'],p_note=payload.get('p_note') or '')
    session[PENDING] = deepcopy(body)
    session.pop(RESULT, None)
    return body


def resolve(auth, session, *, send=False):
    body = session[PENDING]
    actor = str((session.get('login_profile') or {}).get('id') or '')
    if actor != body['p_actor_user_id']:
        raise HwarangAuthError('현재 계정의 처리 요청이 아닙니다.')
    try:
        value = auth._request('POST', '/rest/v1/rpc/'+(
            'admin_apply_hwarang_asset_request' if send else 'admin_get_hwarang_asset_request'),
            admin=True, json=body if send else {
                'p_actor_user_id':actor,'p_request_id':body['p_request_id']})
        if value is None and not send:
            return None
        result = validate_result(value,body['p_target_user_ids'],body['p_request_id'])
    except HwarangAuthError as exc:
        raise HwarangAuthError('자산 처리 결과 확인이 필요합니다. 새 요청을 만들지 말고 결과 확인 또는 같은 요청 재시도를 이용해 주세요.') from exc
    session[RESULT] = {'request':deepcopy(body),'result':result}
    session.pop(PENDING, None)
    return result


def apply(auth, session, rpc, payload):
    prepare(session,rpc,payload)
    result = resolve(auth,session,send=True)
    if 'bulk' not in rpc and result['failed_count']:
        raise HwarangAuthError('자산 조정이 반영되지 않았습니다. 처리 결과를 확인해 주세요.')
    return result


def failure_message(code):
    return {
        'AI_ACTIVE_PURCHASED_RESERVATION':'사용 중인 크레딧 예약이 있어 조정할 수 없습니다.',
        'VOICE_ACTIVE_RESERVATION':'사용 중인 음성 예약이 있어 조정할 수 없습니다.',
        'PURCHASED_CREDIT_REVOKE_EXCEEDS_AVAILABLE':'차감할 수 있는 크레딧보다 요청량이 많습니다.',
        'VOICE_REVOKE_EXCEEDS_AVAILABLE':'차감할 수 있는 음성 이용량보다 요청량이 많습니다.',
        'TARGET_USER_NOT_FOUND':'대상 계정을 찾을 수 없습니다.',
    }.get(code,'처리되지 않았습니다. 계정 상태와 적용 수량을 확인해 주세요.')
