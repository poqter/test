"""A stable calendar mount outside the replaceable workspace page body."""
from datetime import datetime
import logging
from uuid import uuid4
import streamlit as st
from modules.shared.hwarang_auth import HwarangAuthError


@st.fragment
def render(active, args=None):
    from modules.activity import center, calendar_service
    args = dict(args or {})
    state = st.session_state
    uid = state['hwarang_auth']['profile']['id']
    pending = state.get('sales_host_calendar')
    reply = state.get('sales_host_reply')
    if state.get('sales_host_owner') != uid:
        state['sales_host_owner'] = uid
        state.pop('sales_host_reply', None)
        state.pop('sales_host_nonce', None)
        reply = None
    if active and isinstance(pending, dict) and pending.get('nonce') != state.get('sales_host_nonce'):
        state['sales_host_nonce'] = pending.get('nonce')
        if pending.get('action') == 'reauth':
            st.rerun()
        if pending.get('action') == 'rpc':
            try:
                db = center.Records()  # Revalidate access for every command.
                request = pending['value']
                result = calendar_service.command(db, request['op'], request.get('args', {}))
                reply = dict(nonce=pending['nonce'], ok=True, result=result)
            except (HwarangAuthError, ValueError, KeyError, TypeError) as exc:
                reply = dict(nonce=pending['nonce'], ok=False, error=str(exc))
            except Exception:
                logging.getLogger(__name__).exception('Workspace calendar command failed')
                reply = dict(nonce=pending['nonce'], ok=False, error='요청을 완료하지 못했습니다. 입력은 유지됩니다. 다시 시도해 주세요.')
            state['sales_host_reply'] = reply
    args.update(hosted=True, hostTick=str(uuid4()), hostActive=active, hostUid=uid,
                hostToday=str(datetime.now(center.KST).date()), hostError=state.get("sales_host_error"), reply=reply if active else None)
    if not active:
        args.pop('boot', None)
        args.pop('mobileSession', None)
    elif args.get('mobileSession'):
        args['mobileSession'] = {**args['mobileSession'], 'token':state['hwarang_auth']['access_token']}
    center.calendar_view(**args, key='sales_host_calendar', default=None)
