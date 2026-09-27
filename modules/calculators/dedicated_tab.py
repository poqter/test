"""Authenticated launch bridge and calculator-only application branch."""
from pathlib import Path
from html import escape
import re
import secrets
import streamlit as st
from modules.calculators.tab_access import access_store

ROOT = Path(__file__).with_name('components')
launcher = st.components.v2.component('hw_calculator_launcher',
    html='<div role="status" style="font-size:12px;color:#59738c"></div>',
    js=(ROOT/'launcher.js').read_text(encoding='utf-8'))
receiver = st.components.v2.component('hw_calculator_receiver',
    html='<div role="status" style="font-size:13px;color:#59738c"></div>',
    js=(ROOT/'receiver.js').read_text(encoding='utf-8'))


def launch_button(name):
    st.markdown(f'<button class="hw-calculator-newtab" data-hw-calculator-launch="{escape(name, quote=True)}" type="button">새 탭으로 열기 ↗</button>', unsafe_allow_html=True)


def _on_launch():
    from modules.shell.navigation import allowed_ids
    from modules.calculators.jarvia_calculator_center import ITEMS
    value = st.session_state.get('hw_calc_launcher', {})
    request = value.get('request') if hasattr(value, 'get') else None
    if not isinstance(request, dict): return
    name, tab = request.get('calculator'), request.get('tab')
    if not st.session_state.get('password_correct') or st.session_state.get('hw_calc_locked'):
        return
    if not isinstance(name, str) or 'quick_calculators' not in allowed_ids(st.session_state.get('login_user')) or name not in ITEMS:
        return
    if not isinstance(tab, str) or not re.fullmatch(r'[a-f0-9-]{36}', tab): return
    old = st.session_state.get('hw_calc_launch_response')
    if old and old.get('tab') == tab: return
    owner = st.session_state.setdefault('hw_calc_owner', secrets.token_urlsafe(32))
    token, _ = access_store().issue(owner, name, tab)
    st.session_state['hw_calc_launch_response'] = {'tab':tab, 'token':token}


def render_launcher(names):
    if st.session_state.get('hw_calc_locked'): return
    st.markdown('<style>.hw-calculator-newtab{background:#fff;color:#456381;font-family:inherit;font-size:12px;font-weight:600;line-height:1.4;border:1px solid #cbd9e7;border-radius:8px;min-height:38px;padding:9px 12px;cursor:pointer;white-space:nowrap}.hw-calculator-newtab:hover{background:#edf3fa}</style>',unsafe_allow_html=True)
    launcher(data={'allowed':list(names), 'response':st.session_state.get('hw_calc_launch_response')},
             key='hw_calc_launcher', on_request_change=_on_launch)


def _credential():
    value = st.session_state.get('hw_calc_receiver', {})
    event = value.get('credential') if hasattr(value, 'get') else None
    if not isinstance(event, dict): return
    name = st.session_state.get('hw_calc_name')
    tab = st.session_state.get('hw_calc_tab')
    if event.get('kind') == 'grant':
        result = access_store().redeem(event.get('token'), name, tab)
        if result:
            token, _ = result
            st.session_state['hw_calc_lease'] = token
            return
    elif event.get('kind') == 'lease':
        token = event.get('token')
        if access_store().validate(token, name, tab):
            st.session_state['hw_calc_lease'] = token
            return
    st.session_state['hw_calc_denied'] = True


def reset_calculator():
    from modules.shared.session_store import reset_page
    reset_page('quick_calculators')


def current_grant():
    return access_store().validate(st.session_state.get('hw_calc_lease'),
        st.session_state.get('hw_calc_name'), st.session_state.get('hw_calc_tab'))


@st.fragment(run_every='10s')
def _expiry_guard():
    grant = current_grant()
    if not grant:
        st.session_state['hw_calc_denied'] = True
        st.rerun(scope='app')
    # Keep the expiry check active without rendering a countdown.


def _render_requested():
    """Run before normal login/navigation. Never grants general app credentials."""
    requested = st.query_params.get('calc_view')
    if not requested and not st.session_state.get('hw_calc_locked'): return False
    from modules.calculators.jarvia_calculator_center import ITEMS, run
    st.session_state['hw_calc_locked'] = True
    st.markdown('''<style>
    [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
    [data-testid="stToolbar"],[data-testid="stHeader"],#MainMenu,footer{display:none!important}
    body:has(.hw-calculator-only) [data-testid="stMainBlockContainer"]{max-width:1150px!important;margin-inline:auto!important;padding:24px 24px 32px!important}
    body:has(.hw-calculator-only) .st-key-hw_task_page [class*="st-key-hw_calc_"] [data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border-radius:16px!important}
    body:has(.hw-calculator-only) .st-key-hw_calc_connection{display:none!important}
    @media(max-width:640px){body:has(.hw-calculator-only) [data-testid="stMainBlockContainer"]{padding:16px 12px 24px!important}}
    </style>''', unsafe_allow_html=True)
    tab = st.query_params.get('calc_tab','')
    if 'hw_calc_name' not in st.session_state:
        st.session_state['hw_calc_name'] = requested
        st.session_state['hw_calc_tab'] = tab
    name = st.session_state.get('hw_calc_name')
    if name not in ITEMS or requested != name or tab != st.session_state.get('hw_calc_tab'):
        st.session_state['hw_calc_denied'] = True
    token = st.session_state.get('hw_calc_lease')
    grant = current_grant() if token else None
    if token and not grant: st.session_state['hw_calc_denied'] = True
    denied = bool(st.session_state.get('hw_calc_denied'))
    with st.container(key='hw_calc_connection'):
        receiver(data={'tab':st.session_state.get('hw_calc_tab',''), 'lease':token if grant and not denied else None,
                       'denied':denied, 'attempt':st.session_state.setdefault('hw_calc_attempt',secrets.token_hex(16))},
                 key='hw_calc_receiver', on_credential_change=_credential)
    if denied:
        st.warning('이용 권한이 만료되었거나 유효하지 않습니다. 원래 워크스페이스에서 계산기를 다시 열어주세요.')
        return True
    if not grant:
        st.info('계산기를 준비하고 있습니다. 잠시만 기다려주세요.', icon='⏳')
        return True
    _expiry_guard()
    # The validated lease, not the URL or client widget, determines the route.
    st.session_state['jc_open'] = grant.calculator
    st.session_state.pop('jc_valuation_transfer',None)
    st.session_state.pop('jc_link_entry',None)
    st.session_state.pop('jc_home_entry',None)
    run(run_legacy=lambda:None)
    st.button('입력 초기화', on_click=reset_calculator, key='hw_calc_reset')
    return True


def render_if_requested():
    """Use the same task theme as the main app, with no dedicated-tab chrome."""
    if not st.query_params.get('calc_view') and not st.session_state.get('hw_calc_locked'):
        return False
    from modules.shared.ui_components import inject_global_styles
    with st.container(key='hw_task_page'):
        st.markdown('<div class="hw-task-marker hw-calculator-only" aria-hidden="true"></div>', unsafe_allow_html=True)
        with st.container(key='hw_calc_paper'):
            result = _render_requested()
    # Reapply the shared palette after any calculator-specific legacy styling.
    inject_global_styles()
    from modules.calculators.dedicated_theme import apply
    apply()
    return result
