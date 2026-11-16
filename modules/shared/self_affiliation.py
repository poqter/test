"""Self-service choices. System permissions are deliberately not editable here."""
from __future__ import annotations
import hashlib
import time
from copy import deepcopy

import streamlit as st

SIGNUP_POSITIONS = {
    'fp': 'FP', 'partner': '파트너', 'team_leader': '팀장',
    'deputy_branch_manager': '부지점장', 'branch_manager': '지점장',
    'division_head': '본부장',
}


# One entry per browser session, never a process-wide/person-shared cache.
SIGNUP_MANAGER_CACHE_KEY = "hw_signup_manager_candidates"
SIGNUP_MANAGER_CACHE_TTL = 30.0


def clear_signup_manager_cache(session):
    session.pop(SIGNUP_MANAGER_CACHE_KEY, None)


def signup_manager_candidates(auth, session, join_code, organization_code, position_code):
    """UI-only hint cache; auth.sign_up and the DB still validate every signup."""
    key = (hashlib.sha256(join_code.strip().encode()).hexdigest(),
           organization_code, position_code)
    now = time.monotonic()
    cached = session.get(SIGNUP_MANAGER_CACHE_KEY)
    if cached and cached['key'] == key and 0 <= now - cached['at'] < SIGNUP_MANAGER_CACHE_TTL:
        return deepcopy(cached['rows'])
    # Discard old scope before querying, including when the request fails.
    clear_signup_manager_cache(session)
    rows = auth.signup_managers(join_code, organization_code, position_code)
    session[SIGNUP_MANAGER_CACHE_KEY] = {'key': key, 'at': now, 'rows': deepcopy(rows)}
    return rows


def eligible_units(rows, position):
    if position not in SIGNUP_POSITIONS:
        return []
    kinds = {'head_unit'} if position == 'division_head' else {'branch', 'team'}
    return [r for r in rows if r.get('unit_type') in kinds]


def manager_fields(rows, *, key, selected=None):
    selected = selected or {}
    result = {}
    for field, position, label in (
        ('team_leader', 'team_leader', '담당 팀장'),
        ('deputy_manager', 'deputy_branch_manager', '담당 부지점장'),
    ):
        candidates = {r['id']: r for r in rows if r.get('position_code') == position}
        options = [None, *sorted(candidates, key=lambda u: (candidates[u]['display_name'], u))]
        old = selected.get(field)
        result[field] = st.selectbox(label, options,
            index=options.index(old) if old in options else 0,
            format_func=lambda u, c=candidates: '미지정' if u is None else c[u]['display_name'],
            key=key+'_'+field)
    st.caption('같은 소속의 재직 담당자만 선택할 수 있습니다. 없으면 미지정으로 두세요.')
    return result


def account_managers(auth, state):
    from .hwarang_auth import HwarangAuthError
    st.subheader('담당 팀장·부지점장')
    try:
        current = auth.my_reporting_managers(state)
    except HwarangAuthError as exc:
        st.error(str(exc)); return
    with st.form('hw_self_managers'):
        chosen = manager_fields(current.get('candidates') or [], key='hw_self_manager', selected=current)
        st.caption('저장하면 담당자의 내 활동 조회 범위와 지원 요청 대상에 즉시 반영됩니다.')
        save = st.form_submit_button('담당자 저장', type='primary')
    if save:
        try:
            auth.save_my_reporting_managers(state, **chosen)
            from modules.activity.read_state import invalidate
            invalidate()
            st.success('담당자를 저장했습니다.')
        except HwarangAuthError as exc:
            st.error(str(exc))
