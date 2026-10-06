"""HWARANG WORKSPACE entrypoint: unified account, registry, navigation, and dispatch."""
from __future__ import annotations

import time

import streamlit as st

from modules.shell.app_registry import APP_DEFINITIONS, USER_PERMISSIONS
from modules.shell.navigation import allowed_ids, dispatch, logout as clear_workspace_session, navigate, normalize_route
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService, SupabaseConfig
from modules.shared.ui_components import inject_global_styles
from modules.shared.workbench import render_workbench, restore_page_draft
from modules.shell.workspace_v2 import render_home, render_sidebar


st.set_page_config(page_title="화랑WORKSPACE", page_icon="H", layout="wide", initial_sidebar_state="expanded")
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


@st.cache_resource(show_spinner=False)
def auth_service() -> HwarangAuthService:
    return HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))


def initialize_state() -> None:
    st.session_state.setdefault("password_correct", False)
    st.session_state.setdefault("login_user", None)  # current WORKSPACE permission bridge
    st.session_state.setdefault("login_profile", None)
    st.session_state.setdefault("hwarang_auth", None)
    st.session_state.setdefault("active_app", "home")
    st.session_state.setdefault("hw_app_access", {})
    st.session_state.setdefault("hw_feature_permissions", set())
    st.session_state.setdefault("hw_platform_session_id", None)
    st.session_state.setdefault("hw_last_heartbeat_at", 0.0)
    st.session_state.setdefault("hw_last_activity_app", None)
    st.session_state.setdefault("hw_admin_center_open", False)
    st.session_state.setdefault("hw_admin_center_page", "dashboard")


def _set_authenticated(auth: HwarangAuthService, state: dict) -> None:
    profile = dict(state.get("profile") or {})
    st.session_state["hwarang_auth"] = state
    st.session_state["login_profile"] = profile
    st.session_state["password_correct"] = True
    st.session_state["login_user"] = auth.workspace_permission_role(profile)
    st.session_state["hw_app_access"] = dict(state.get("app_access") or {})
    st.session_state["hw_feature_permissions"] = set(state.get("feature_permissions") or ())
    st.session_state["active_app"] = "home"

    # Migration 12 fast path creates the platform session inside the same
    # post-auth RPC that returns profile/permission context. No extra login-time
    # network call is needed here.
    platform_session_id = str(state.get("platform_session_id") or "").strip() or None

    # Compatibility fallback only: if code is deployed before migration 12,
    # preserve the older behavior rather than breaking login.
    if not platform_session_id:
        try:
            from modules.shared.platform_activity import open_session

            uid = str(profile.get("id") or "")
            if uid:
                platform_session_id = open_session(auth, uid, "workspace")
        except Exception:
            platform_session_id = None

    st.session_state["hw_platform_session_id"] = platform_session_id

    # The platform session was just created, so an immediate heartbeat is
    # redundant. Start the five-minute heartbeat window from now.
    st.session_state["hw_last_heartbeat_at"] = time.time() if platform_session_id else 0.0

    # LOGIN_SUCCESS already records the initial HOME entry. Skip the redundant
    # APP_OPENED/home request; subsequent page changes are still logged.
    st.session_state["hw_last_activity_app"] = "home"

    for key in ("hw_signup_branches", "hw_signup_verified_code"):
        st.session_state.pop(key, None)


@st.dialog("HWARANG 회원가입", width="large")
def render_signup_dialog(auth: HwarangAuthService) -> None:
    st.caption("화랑 가입코드를 확인한 뒤 소속과 계정을 등록해 주세요.")
    verify_col, button_col = st.columns([1, 0.34], gap="small", vertical_alignment="bottom")
    with verify_col:
        join_code = st.text_input("가입코드", placeholder="가입코드", key="hw_signup_code")
    with button_col:
        verify = st.button("가입코드 확인", type="secondary", use_container_width=True, key="hw_signup_verify")

    if verify:
        try:
            branches = auth.joinable_branches(join_code)
            if not branches:
                raise HwarangAuthError("가입코드를 확인해 주세요.")
            st.session_state["hw_signup_branches"] = branches
            st.session_state["hw_signup_verified_code"] = join_code.strip()
            st.success("가입코드가 확인되었습니다. 소속을 선택해 가입을 완료해 주세요.")
        except HwarangAuthError as exc:
            st.session_state.pop("hw_signup_branches", None)
            st.session_state.pop("hw_signup_verified_code", None)
            st.error(str(exc))

    branches = st.session_state.get("hw_signup_branches") or []
    verified_code = str(st.session_state.get("hw_signup_verified_code") or "")
    if not branches:
        return

    labels = {
        branch["code"]: f"{branch.get('parent') or '화랑'} · {branch['name']}"
        for branch in branches
    }
    with st.form("hw_signup_form", clear_on_submit=False):
        login_id = st.text_input("아이디", placeholder="아이디")
        password = st.text_input("비밀번호", type="password", placeholder="비밀번호")
        password_confirm = st.text_input("비밀번호 확인", type="password", placeholder="비밀번호 확인")
        display_name = st.text_input("이름", placeholder="이름")
        email = st.text_input("이메일", placeholder="이메일")
        org_code = st.selectbox(
            "소속",
            options=[branch["code"] for branch in branches],
            format_func=lambda code: labels.get(code, code),
        )
        submitted = st.form_submit_button("회원가입", type="primary", use_container_width=True)

    if submitted:
        if password != password_confirm:
            st.error("비밀번호 확인이 일치하지 않습니다.")
            return
        try:
            state = auth.sign_up(
                login_id=login_id,
                password=password,
                display_name=display_name,
                email=email,
                join_code=verified_code,
                organization_code=org_code,
            )
            _set_authenticated(auth, state)
            st.success("가입이 완료되었습니다.")
            st.rerun()
        except HwarangAuthError as exc:
            st.error(str(exc))


def render_login(auth: HwarangAuthService) -> bool:
    if st.session_state.get("hwarang_auth") and st.session_state.get("password_correct"):
        return True
    st.markdown('<div class="hw-auth-bg" aria-hidden="true"></div>', unsafe_allow_html=True)
    with st.container(key="hw_auth_shell"):
        st.markdown('<div class="hw-auth-brand"><span>H</span> 화랑 <strong>WORKSPACE</strong></div>', unsafe_allow_html=True)
        copy_col, login_col = st.columns([1.18, 1], gap="large", vertical_alignment="center")
        with copy_col:
            st.markdown("""<div class="hw-auth-copy"><span>HWARANG WORKSPACE</span>
            <h1>보험 업무의 복잡함,<br>더 간단하게.</h1>
            <p>상담과 관리에 필요한 도구를 한 공간에.</p><i></i></div>""", unsafe_allow_html=True)
        with login_col:
            with st.container(key="hw_auth_card"):
                st.markdown('<div class="hw-auth-card-heading"><small>WELCOME BACK</small><h2>로그인</h2><p>아이디와 비밀번호를 입력해 시작하세요.</p></div>', unsafe_allow_html=True)
                with st.form("login_form", clear_on_submit=False):
                    login_id = st.text_input("아이디", placeholder="아이디")
                    password = st.text_input("비밀번호", type="password", placeholder="비밀번호")
                    submitted = st.form_submit_button("워크스페이스 시작 →", type="primary", use_container_width=True)
                login_feedback = st.empty()
                if st.button("회원가입", key="hw_open_signup", use_container_width=True):
                    render_signup_dialog(auth)
                st.markdown(
                    f'<div class="hw-auth-help"><span>변경된 비밀번호가 필요하신가요?</span>'
                    f'<a href="{NOTICE["contact_url"]}" target="_blank" rel="noopener noreferrer">박병선 팀장에게 문의해 주세요 ↗</a></div>',
                    unsafe_allow_html=True,
                )
            if submitted:
                try:
                    _set_authenticated(auth, auth.sign_in(login_id, password))
                    st.rerun()
                except HwarangAuthError as exc:
                    login_feedback.error(str(exc), icon="⚠️")
        st.markdown('<div class="hw-auth-footer">Planned &amp; Built by 박병선 팀장</div>', unsafe_allow_html=True)
    return False


def allowed_app_ids() -> list[str]:
    """Compatibility wrapper retained for existing checks."""
    return allowed_ids(st.session_state.get("login_user"))


def workspace_logout() -> None:
    state = st.session_state.get("hwarang_auth")
    auth = auth_service()

    try:
        profile = (state or {}).get("profile") or {}
        uid = str(profile.get("id") or "")
        if uid:
            from modules.shared.platform_activity import close_session

            close_session(
                auth,
                platform_session_id=st.session_state.get("hw_platform_session_id"),
                user_id=uid,
            )
    except Exception:
        pass

    try:
        auth.sign_out(state)
    except HwarangAuthError:
        pass

    clear_workspace_session()
    st.session_state["hw_platform_session_id"] = None
    st.session_state["hw_last_heartbeat_at"] = 0.0
    st.session_state["hw_last_activity_app"] = None
    st.session_state["hw_admin_center_open"] = False
    st.session_state["hw_admin_center_page"] = "dashboard"


def main() -> None:
    initialize_state()
    try:
        auth = auth_service()
    except HwarangAuthError as exc:
        st.error(str(exc))
        st.info("Streamlit Secrets에서 SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY / SUPABASE_SECRET_KEY를 확인해 주세요.")
        return

    state = st.session_state.get("hwarang_auth")
    if state:
        try:
            state = auth.refresh(state)
            st.session_state["hwarang_auth"] = state
            # Periodic profile revalidation can change role/organization while
            # the user is signed in. Keep the UI and permission bridge in sync.
            refreshed_profile = dict(state.get("profile") or {})
            if refreshed_profile:
                st.session_state["login_profile"] = refreshed_profile
                st.session_state["login_user"] = auth.workspace_permission_role(refreshed_profile)
                st.session_state["hw_app_access"] = dict(state.get("app_access") or {})
                st.session_state["hw_feature_permissions"] = set(state.get("feature_permissions") or ())
        except HwarangAuthError:
            clear_workspace_session()
            st.warning("로그인 시간이 만료되었거나 계정 권한이 변경되었습니다. 다시 로그인해 주세요.")

    if not render_login(auth):
        st.stop()

    # Sparse presence heartbeat. This is not click-level tracking.
    try:
        from modules.shared.platform_activity import heartbeat

        profile = st.session_state.get("login_profile") or {}
        uid = str(profile.get("id") or "")
        if uid:
            st.session_state["hw_last_heartbeat_at"] = heartbeat(
                auth,
                platform_session_id=st.session_state.get("hw_platform_session_id"),
                user_id=uid,
                last_heartbeat_at=st.session_state.get("hw_last_heartbeat_at", 0.0),
                interval_seconds=300,
            )
    except Exception:
        pass

    permission_role = st.session_state.get("login_user")
    permitted = allowed_ids(permission_role)
    st.session_state["ws_allowed_ids"] = permitted
    active = normalize_route(st.session_state.get("active_app"), permission_role)
    st.session_state["active_app"] = active

    profile = st.session_state.get("login_profile") or {}
    is_super_admin = profile.get("role") == "super_admin"
    admin_center_open = bool(st.session_state.get("hw_admin_center_open")) and is_super_admin

    # Administrator Center is a dedicated console. While it is open, replace the
    # normal WORKSPACE sidebar instead of stacking a second navigation system on
    # top of it.
    if admin_center_open:
        try:
            from modules.shared.platform_activity import log_activity

            uid = str(profile.get("id") or "")
            if uid and st.session_state.get("hw_last_activity_app") != "__admin_center__":
                log_activity(
                    auth,
                    user_id=uid,
                    platform_session_id=st.session_state.get("hw_platform_session_id"),
                    app_code="platform",
                    event_code="ADMIN_CENTER_OPENED",
                    feature_code="admin_center",
                )
                st.session_state["hw_last_activity_app"] = "__admin_center__"
        except Exception:
            pass

        from modules.shared.admin_center_ui import (
            render as render_admin_center,
            render_sidebar as render_admin_sidebar,
        )

        render_admin_sidebar()
        render_admin_center(auth)
        return

    # Record meaningful WORKSPACE page changes only, not every Streamlit rerun.
    if st.session_state.get("hw_last_activity_app") != active:
        try:
            from modules.shared.platform_activity import log_activity

            uid = str(profile.get("id") or "")
            if uid:
                log_activity(
                    auth,
                    user_id=uid,
                    platform_session_id=st.session_state.get("hw_platform_session_id"),
                    app_code="workspace",
                    event_code="APP_OPENED",
                    feature_code=active,
                )
        except Exception:
            pass
        st.session_state["hw_last_activity_app"] = active

    render_sidebar(permitted, navigate, workspace_logout, NOTICE)
    from modules.shared.build_info import BUILD_ID

    with st.sidebar:
        st.caption("버전 " + BUILD_ID)
        if is_super_admin:
            if st.button("관리자 센터 →", key="hw_open_admin_center", use_container_width=True):
                st.session_state["hw_admin_center_open"] = True
                st.session_state["hw_admin_center_page"] = "dashboard"
                st.rerun()

    if active == "home":
        render_home(permitted, navigate, NOTICE)
        return

    restore_page_draft(active)
    with st.container(key="hw_task_page"):
        st.markdown('<div class="hw-task-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
        render_workbench(active, permitted, navigate)
        dispatch(active, role=permission_role)
    inject_global_styles()


if __name__ == "__main__":
    main()
