"""Session-only calendar viewing preference; account authority stays intact."""
import json
import streamlit as st

KEY = 'calendar_view_scope'
LABELS = {'daily': '일상 업무 · 내 소속과 직책', 'all': '전체 점검 · 최고관리자'}

def current():
    profile = st.session_state.get('hwarang_auth', {}).get('profile', {})
    if profile.get('role') != 'super_admin':
        return 'daily'
    value = st.session_state.get(KEY, 'daily')
    return value if isinstance(value, str) and value.startswith('{') else 'daily'

def switch(mode):
    profile = st.session_state.get('hwarang_auth', {}).get('profile', {})
    if profile.get('role') != 'super_admin' or not (mode == 'daily' or isinstance(mode, str) and mode.startswith('{')):
        return
    from modules.activity import read_state
    read_state.invalidate()
    generation = st.session_state.get('calendar_scope_generation', 0)
    for key in list(st.session_state):
        if key.startswith(('sales_persistent_', 'sales_host_', 'sales_route', 'sales_overview_', 'sales_member_', 'calendar_scope_', 'sales_period_cache', 'activity_live_', 'manager_selected', 'manager_date_member')) or key in ('sales_calendar_member', 'sales_calendar_team', 'sales_interactive_calendar'):
            st.session_state.pop(key, None)
    st.session_state[KEY] = mode
    st.session_state['calendar_scope_generation'] = generation + 1

def render_settings(prefix):
    profile = st.session_state.get('hwarang_auth', {}).get('profile', {})
    if profile.get('role') != 'super_admin':
        return
    st.caption('현재 보기: ' + st.session_state.get('calendar_view_label', '내 소속 · 내 직책'))
    with st.expander('설정 · 보기 범위'):
        st.caption('조회 기준만 변경하며 실제 소속과 직책은 유지됩니다.')
        if st.button('내 소속·직책으로 돌아가기', key=prefix+'_scope_daily'):
            st.session_state.pop('calendar_view_label', None)
            switch('daily')
            st.rerun()
        if st.button('조회 기준 선택', key=prefix+'_scope_open'):
            st.session_state[prefix+'_scope_edit'] = True
        if not st.session_state.get(prefix+'_scope_edit'):
            return
        from modules.shared.hwarang_auth import HwarangAuthService, SupabaseConfig, HwarangAuthError
        try:
            auth = HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))
            catalog = auth._request('POST', '/rest/v1/rpc/sales_view_catalog',
                access_token=st.session_state['hwarang_auth']['access_token'], json={})
        except HwarangAuthError as exc:
            st.error(str(exc))
            return
        positions = {r['code']: r['display_name'] for r in catalog['positions']}
        units = {r['id']: r for r in catalog['units']}
        role = st.selectbox('조회 기준 직책', list(positions),
            index=list(positions).index(profile['position_code']) if profile.get('position_code') in positions else 0,
            format_func=positions.get, key=prefix+'_view_position')
        parents = [u for u,r in units.items() if r['unit_type'] in ('root','head_unit')]
        own = units.get(profile.get('organization_unit_id'), {})
        parent_default = own.get('parent_id') if own.get('unit_type') == 'branch' else own.get('id')
        parent = st.selectbox('상위조직', parents, index=parents.index(parent_default) if parent_default in parents else 0,
            format_func=lambda u: units[u]['name'], key=prefix+'_view_parent')
        children = [u for u,r in units.items() if r['parent_id'] == parent and r['unit_type'] == 'branch']
        options = [parent] + children
        unit = st.selectbox('직할 / 지점', options,
            index=options.index(profile.get('organization_unit_id')) if profile.get('organization_unit_id') in options else 0,
            format_func=lambda u: '상위조직 전체' if u == parent else units[u]['name'], key=prefix+'_view_unit_'+parent)
        subject = None
        if role not in ('chief_representative','division_head','branch_manager'):
            people = {r['id']:r['display_name'] for r in catalog['people'] if r['organization_unit_id']==unit and r['position_code']==role}
            if not people:
                st.info('선택한 조직·직책에 해당하는 구성원이 없습니다.')
            else:
                subject = st.selectbox('조회 기준 구성원', list(people),
                    index=list(people).index(profile['id']) if profile['id'] in people else 0,
                    format_func=people.get, key=prefix+'_view_subject_'+unit+'_'+role)
        valid = role in ('chief_representative','division_head','branch_manager') or subject is not None
        if st.button('선택한 범위 적용', key=prefix+'_scope_apply', disabled=not valid, type='primary'):
            switch(json.dumps(dict(position=role, unit=unit, subject=subject), sort_keys=True))
            st.session_state['calendar_view_label'] = units[unit]['name']+' · '+positions[role]
            st.session_state[prefix+'_scope_edit'] = False
            st.rerun()
        st.caption('이 접속에서만 유지되며, 새로 로그인하면 내 소속·직책으로 돌아갑니다.')
