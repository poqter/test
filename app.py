"""HWARANG WORKSPACE entrypoint: auth, registry, navigation, and dispatch."""
from __future__ import annotations

import hmac

import streamlit as st

from modules.shell.app_registry import APP_DEFINITIONS, USER_PERMISSIONS
from modules.shell.navigation import allowed_ids, dispatch, logout, navigate, normalize_route
from modules.shared.ui_components import inject_global_styles
from modules.shared.workbench import render_workbench, restore_page_draft
from modules.shell.workspace_v2 import render_home, render_sidebar


st.set_page_config(page_title="화랑WORKSPACE", page_icon="H", layout="wide", initial_sidebar_state="auto")
st.set_option("client.toolbarMode", "minimal")


inject_global_styles()

NOTICE = {
    "date": "2026.09.21",
    "title": "공통 작업 기반을 정리했습니다",
    "items": [
        "페이지 권한과 이동 경로를 하나의 레지스트리로 통합했습니다.",
        "도구별 초기화와 전체 작업 초기화 범위를 구분했습니다.",
        "현재 16개 업무 도구와 원수사 홈 검색을 그대로 제공합니다.",
    ],
    "important": "비밀번호 또는 이용 권한은 관리자에게 문의해 주세요.",
    "contact_url": "https://open.kakao.com/o/sFxdv4Rf",
}


def initialize_state() -> None:
    st.session_state.setdefault("password_correct", False)
    st.session_state.setdefault("login_user", None)
    st.session_state.setdefault("active_app", "home")




def render_login() -> bool:
    if st.session_state["password_correct"]:
        return True
    st.markdown('<div class="hw-auth-bg" aria-hidden="true"></div>', unsafe_allow_html=True)
    with st.container(key="hw_auth_shell"):
        st.markdown('<div class="hw-auth-brand"><span>H</span> 화랑 <strong>WORKSPACE</strong></div>', unsafe_allow_html=True)
        copy_col, login_col = st.columns([1.18, 1], gap="large", vertical_alignment="center")
        with copy_col:
            st.markdown('''<div class="hw-auth-copy"><span>HWARANG WORKSPACE</span>
            <h1>보험 업무의 복잡함,<br>더 간단하게.</h1>
            <p>상담과 관리에 필요한 도구를 한 공간에.</p><i></i></div>''', unsafe_allow_html=True)
        with login_col:
            with st.container(key="hw_auth_card"):
                st.markdown('<div class="hw-auth-card-heading"><small>WELCOME BACK</small><h2>로그인</h2><p>비밀번호를 입력해 시작하세요.</p></div>', unsafe_allow_html=True)
                with st.form("login_form", clear_on_submit=True):
                    password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
                    submitted = st.form_submit_button("워크스페이스 시작 →", type="primary", use_container_width=True)
                login_feedback = st.empty()
                st.markdown(
                    f'<div class="hw-auth-help"><span>변경된 비밀번호가 필요하신가요?</span>'
                    f'<a href="{NOTICE["contact_url"]}" target="_blank" rel="noopener noreferrer">박병선 팀장에게 문의해 주세요 ↗</a></div>',
                    unsafe_allow_html=True,
                )
            if submitted:
                try:
                    passwords = dict(st.secrets["passwords"])
                except (FileNotFoundError, KeyError, TypeError, ValueError):
                    login_feedback.error("로그인 설정을 확인해야 합니다. 아래 카카오톡으로 문의해 주세요.", icon="⚠️")
                    return False
                matched_user = next(
                    (name for name, saved in passwords.items() if name in USER_PERMISSIONS and isinstance(saved, str)
                     and saved and password and hmac.compare_digest(password.encode("utf-8"), saved.encode("utf-8"))),
                    None,
                )
                if matched_user:
                    st.session_state["password_correct"] = True
                    st.session_state["login_user"] = matched_user
                    st.session_state["active_app"] = "home"
                    st.rerun()
                else:
                    login_feedback.error("비밀번호가 일치하지 않습니다. 다시 입력해 주세요.", icon="⚠️")
        st.markdown('<div class="hw-auth-footer">Planned &amp; Built by 박병선 팀장</div>', unsafe_allow_html=True)
    return False


def allowed_app_ids() -> list[str]:
    """Compatibility wrapper retained for existing checks."""
    return allowed_ids(st.session_state.get("login_user"))


def main() -> None:
    initialize_state()
    if not render_login():
        st.stop()
    role = st.session_state.get("login_user")
    permitted = allowed_ids(role)
    st.session_state["ws_allowed_ids"] = permitted
    active = normalize_route(st.session_state.get("active_app"), role)
    st.session_state["active_app"] = active
    render_sidebar(permitted, navigate, logout, NOTICE)
    from modules.shared.build_info import BUILD_ID
    with st.sidebar:
        st.caption("버전 " + BUILD_ID)
        if role == "Admin":
            settings_open = st.toggle("운영 설정", key="hw_admin_settings_open")
        else:
            settings_open = False
    if settings_open:
        from modules.shared.organization_ui import render as render_settings
        render_settings()
        return
    if active == "home":
        render_home(permitted, navigate, NOTICE)
        return
    restore_page_draft(active)
    with st.container(key="hw_task_page"):
        st.markdown('<div class="hw-task-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
        render_workbench(active, permitted, navigate)
        dispatch(active, role=role)
    # Legacy page CSS may be injected during run(); restore the shared tokens.
    inject_global_styles()


if __name__ == "__main__":
    main()
