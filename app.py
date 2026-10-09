"""HWARANG WORKSPACE entrypoint: unified account, registry, navigation, and dispatch."""
from __future__ import annotations

import streamlit as st

from modules.shell.app_registry import APP_DEFINITIONS, USER_PERMISSIONS
from modules.shell.navigation import allowed_ids, dispatch, logout as clear_workspace_session, navigate, normalize_route
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService, SupabaseConfig
from modules.shared.account_security import recovery_dialog, account_dialog, render_recovery_entry
from modules.shared.ui_components import inject_global_styles
from modules.shared.workbench import render_workbench, restore_page_draft
from modules.shell.workspace_v2 import render_home, render_sidebar


st.set_page_config(page_title="화랑WORKSPACE", page_icon="H", layout="wide", initial_sidebar_state="expanded")
st.set_option("client.toolbarMode", "minimal")
inject_global_styles()

NOTICE = {
    "date": "2026.10.09",
    "title": "뉴스 브리핑과 계정 기능을 개선했습니다",
    "items": [
        "종합·보험·경제 뉴스를 다양한 언론사 피드에서 수집합니다.",
        "경제 지표와 흐름 해설, 모바일 읽기와 PDF를 개선했습니다.",
        "고객 공유에는 링크를 만든 설계사의 등록 이름과 직책을 표시합니다.",
        "자동 공개와 고객 공유는 조직 승인 및 검수를 통과한 자료에 적용됩니다.",
    ],
    "important": "비밀번호는 내 계정에서 변경하고, 잊었을 때는 로그인 화면에서 이메일로 재설정할 수 있습니다.",
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

    # Login telemetry is intentionally minimal: the post-auth RPC records only
    # LOGIN_SUCCESS and profiles.last_login_at. Migration 17 returns no platform
    # presence-session id; older databases may still return one and are tolerated.
    st.session_state["hw_platform_session_id"] = (
        str(state.get("platform_session_id") or "").strip() or None
    )

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
                if st.button("비밀번호를 잊으셨나요?", key="hw_open_recovery", use_container_width=True):
                    recovery_dialog(auth)
                st.markdown(
                    f'<div class="hw-auth-help"><span>이메일을 사용할 수 없으신가요?</span>'
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
        auth.sign_out(state)
    except HwarangAuthError:
        pass

    # Normal-user telemetry is login-only. Streamlit supplies the callback rerun.
    clear_workspace_session(state=st.session_state, rerun=lambda: None)
    st.session_state["hw_platform_session_id"] = None
    st.session_state["hw_admin_center_open"] = False
    st.session_state["hw_admin_center_page"] = "dashboard"


def _open_admin_center() -> None:
    st.session_state["hw_admin_center_open"] = True
    st.session_state["hw_admin_center_page"] = "dashboard"


def main() -> None:
    initialize_state()
    try:
        auth = auth_service()
    except HwarangAuthError as exc:
        st.error(str(exc))
        st.info("Streamlit Secrets에서 SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY / SUPABASE_SECRET_KEY를 확인해 주세요.")
        return

    if st.query_params.get("briefing"):
        from modules.briefing.repository import BriefingRepository, BriefingRepositoryError
        from modules.briefing.display import render_public_entry
        try:
            if render_public_entry(BriefingRepository(auth.config.url, auth.config.secret_key)):
                st.stop()
        except BriefingRepositoryError:
            st.error("공유 브리핑을 확인하지 못했습니다. 잠시 후 다시 열어 주세요.")
            st.stop()

    if render_recovery_entry(auth):
        st.stop()
    flash = st.session_state.pop("hw_account_flash", "")
    if flash:
        st.success(flash)
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


    permission_role = st.session_state.get("login_user")
    permitted = allowed_ids(permission_role)
    st.session_state["ws_allowed_ids"] = permitted
    active = normalize_route(st.session_state.get("active_app"), permission_role, allowed=permitted)
    st.session_state["active_app"] = active

    profile = st.session_state.get("login_profile") or {}
    is_super_admin = profile.get("role") == "super_admin"
    admin_center_open = bool(st.session_state.get("hw_admin_center_open")) and is_super_admin

    # Administrator Center is a dedicated console. Read-only navigation is not activity telemetry.
    if admin_center_open:
        from modules.shared.admin_center_ui import (
            render as render_admin_center,
            render_sidebar as render_admin_sidebar,
        )

        render_admin_sidebar()
        render_admin_center(auth)
        return


    render_sidebar(permitted, navigate, workspace_logout, NOTICE)
    from modules.shared.build_info import BUILD_ID

    with st.sidebar:
        if st.button("내 계정 · 비밀번호 변경", key="hw_my_account", use_container_width=True):
            account_dialog(auth)
        st.caption("버전 " + BUILD_ID)
        if is_super_admin:
            st.button("관리자 센터 →", key="hw_open_admin_center", use_container_width=True,
                      on_click=_open_admin_center)

    if active == "home":
        render_home(permitted, navigate, NOTICE)
        return

    restore_page_draft(active)
    with st.container(key="hw_task_page"):
        st.markdown('<div class="hw-task-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
        render_workbench(active, permitted, navigate)
        dispatch(active, role=permission_role, allowed=permitted)


if __name__ == "__main__":
    main()
