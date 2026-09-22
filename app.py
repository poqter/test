"""HWARANG WORKSPACE entrypoint: auth, registry, navigation, and dispatch."""
from __future__ import annotations

import base64
import hmac
import textwrap
from pathlib import Path

import streamlit as st

from modules.app_registry import APP_DEFINITIONS, USER_PERMISSIONS
from modules.navigation import allowed_ids, dispatch, logout, navigate, normalize_route
from modules.ui_components import inject_global_styles
from modules.workbench import render_workbench, restore_page_draft
from modules.workspace_v2 import render_home, render_sidebar


st.set_page_config(page_title="화랑WORKSPACE", page_icon="H", layout="wide", initial_sidebar_state="auto")


@st.cache_data(show_spinner=False)
def _pretendard_font_data() -> str:
    font_path = Path(__file__).resolve().parent / "assets" / "fonts" / "PretendardVariable.ttf"
    return base64.b64encode(font_path.read_bytes()).decode("ascii") if font_path.is_file() else ""


def inject_pretendard_font() -> None:
    font_data = _pretendard_font_data()
    if font_data:
        st.markdown(
            f"<style>@font-face{{font-family:'Pretendard';src:url(data:font/ttf;base64,{font_data}) format('truetype');font-weight:100 900;font-style:normal;font-display:swap}}</style>",
            unsafe_allow_html=True,
        )


inject_pretendard_font()
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


def render_notice() -> None:
    st.markdown("### 공지사항")
    st.caption(f"최근 업데이트 · {NOTICE['date']}")
    with st.container(border=True):
        st.markdown(f"**{NOTICE['title']}**")
        for item in NOTICE["items"]:
            st.markdown(f"- {item}")
    st.markdown(
        textwrap.dedent(
            f'''<div class="hw-login-contact"><span>{NOTICE["important"]}</span>
            <a href="{NOTICE["contact_url"]}" target="_blank" rel="noopener noreferrer">문의하기 ↗</a></div>'''
        ),
        unsafe_allow_html=True,
    )


def render_login() -> bool:
    if st.session_state["password_correct"]:
        return True
    st.markdown(
        """<div class="hw-login-brand"><span class="hw-logo">H</span><div><strong>화랑 <b>WORKSPACE</b></strong><small>Insurance Consulting Support</small></div></div>
        <div class="hw-login-hero"><div class="hw-login-copy"><span class="hw-login-kicker"><i></i>HWARANG BUSINESS WORKSPACE</span>
        <h1><span class="hw-title-top">보험 업무의 복잡함을,</span><em class="hw-title-accent">더 간단하게.</em></h1>
        <p>상담자료 제작부터 실적 관리까지 필요한 업무를 한곳에서 이용하세요.</p></div></div>""",
        unsafe_allow_html=True,
    )
    login_col, notice_col = st.columns([1, 1.15], gap="large")
    with login_col:
        st.markdown("### 로그인")
        st.write("발급받은 비밀번호를 입력해 주세요.")
        with st.form("login_form", clear_on_submit=True):
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if submitted:
            try:
                passwords = dict(st.secrets["passwords"])
            except (FileNotFoundError, KeyError, TypeError, ValueError):
                st.error("로그인 설정이 준비되지 않았습니다. 관리자에게 테스트 서버의 passwords 설정 확인을 요청해 주세요.")
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
                st.error("입력한 비밀번호를 확인해 주세요.")
    with notice_col:
        render_notice()
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
    if active == "home":
        render_home(permitted, navigate, NOTICE)
        return
    restore_page_draft(active)
    render_workbench(active, permitted, navigate)
    dispatch(active, role=role)
    # Legacy page CSS may be injected during run(); restore the shared tokens.
    inject_global_styles()


if __name__ == "__main__":
    main()
