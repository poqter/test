"""Separate Streamlit Academy production entrypoint."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

import streamlit as st
import streamlit.components.v1 as components

from hwarang_academy.auth_service import AcademyAuthError, AcademyAuthService, SupabaseConfig
from hwarang_academy.content import ROOT, SCENARIOS, MODES, validate_content
from hwarang_academy.service import AppState, handle, present


st.set_page_config(
    page_title="화랑 ACADEMY",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@lru_cache(maxsize=1)
def component():
    # Version the component name so Community Cloud does not retain an older front-end bundle.
    return components.declare_component("hwarang_academy_v57", path=str(ROOT / "frontend"))


def _secret_bool(name: str, default: bool = False) -> bool:
    try:
        value = st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@st.cache_resource(show_spinner=False)
def auth_service() -> AcademyAuthService:
    return AcademyAuthService(SupabaseConfig.from_mapping(st.secrets))


def _inject_shell_css(*, auth_page: bool = False, independent: bool = False) -> None:
    bg = "#0a233e" if independent else "#f4f7fb"
    auth_bg = "#f5f8fc" if auth_page else bg
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="stExpandSidebarButton"]{{display:none!important}}
        [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer{{display:none!important}}
        .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:{auth_bg}!important}}
        [data-testid="stMainBlockContainer"]{{max-width:{'1180px' if auth_page else '1600px'}!important;padding:{'28px 26px 46px' if auth_page else '0'}!important}}
        iframe[title*="hwarang_academy"]{{border:0!important;display:block;width:100%}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _auth_css() -> None:
    st.markdown(
        """
        <style>
        .academy-auth-brand{display:flex;align-items:center;gap:12px;margin:2px 0 18px;color:#15324e}
        .academy-auth-mark{display:grid;place-items:center;width:42px;height:44px;border-radius:12px;background:linear-gradient(145deg,#2162a8,#153c65);color:#fff;font-size:24px;font-weight:900;box-shadow:0 8px 22px #225b8a28}
        .academy-auth-brand strong{display:block;font-size:15px;letter-spacing:.055em;line-height:1.15}.academy-auth-brand small{display:block;margin-top:4px;color:#7890a9;font-size:11px;letter-spacing:.08em}
        .academy-auth-hero{position:relative;overflow:hidden;min-height:262px;margin-bottom:22px;padding:34px 38px;border:1px solid #d7e4f0;border-radius:24px;background:radial-gradient(circle at 85% 24%,#c8e0f7 0,transparent 30%),linear-gradient(120deg,#ffffff 10%,#edf5fd 58%,#dbeaf8);box-shadow:0 18px 50px #284f7310}
        .academy-auth-hero:before,.academy-auth-hero:after{content:"";position:absolute;right:-4%;bottom:-42%;width:60%;height:76%;background:linear-gradient(145deg,#aec9df,#718da8);clip-path:polygon(0 100%,24% 44%,37% 66%,55% 18%,68% 50%,79% 34%,100% 100%);opacity:.48}
        .academy-auth-hero:after{right:16%;bottom:-51%;width:48%;height:69%;background:#d4e4f0;opacity:.72}
        .academy-auth-hero>*{position:relative;z-index:2}.academy-auth-kicker{color:#5580a5;font-size:11px;font-weight:800;letter-spacing:.13em}.academy-auth-hero h1{margin:12px 0 12px;color:#12314f;font-size:clamp(30px,4vw,48px);line-height:1.18;letter-spacing:-.055em}.academy-auth-hero p{max-width:510px;margin:0;color:#526f88;font-size:14px;line-height:1.8}.academy-auth-hero b{color:#2369b8}
        .academy-auth-panel-title{margin:4px 0 4px;color:#173550;font-size:22px;font-weight:800;letter-spacing:-.035em}.academy-auth-panel-copy{margin:0 0 16px;color:#768aa0;font-size:13px}
        .academy-auth-note{padding:12px 14px;border:1px solid #dce7f2;border-radius:12px;background:#f8fbfe;color:#60788e;font-size:12px;line-height:1.6}
        .academy-auth-footer{margin-top:24px;color:#8b9daf;font-size:11px;text-align:center}.academy-auth-footer b{color:#607d98}
        div[data-testid="stForm"]{border:1px solid #dce6f0!important;border-radius:18px!important;background:#fff!important;padding:20px 20px 16px!important;box-shadow:0 12px 35px #243f5a0c!important}
        div[data-baseweb="input"]>div{border-radius:11px!important;background:#fbfdff!important;border-color:#d6e2ed!important}
        .stButton>button,.stFormSubmitButton>button{min-height:44px;border-radius:11px;font-weight:750}
        div[data-testid="stTabs"] button[role="tab"]{font-weight:750}
        @media(max-width:760px){.academy-auth-hero{padding:27px 23px;min-height:245px}.academy-auth-hero h1{font-size:32px}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _set_authenticated(state: dict) -> None:
    st.session_state["_academy_auth"] = state
    st.session_state.pop("_academy_signup_branches", None)
    st.session_state.pop("_academy_signup_verified_code", None)
    st.session_state.pop("_academy_route", None)
    st.session_state.pop("_academy_model", None)


def _branch_label(branch: dict) -> str:
    parent = branch.get("parent") or ""
    return f"{parent} · {branch['name']}" if parent else branch["name"]


def render_auth_page(auth: AcademyAuthService) -> None:
    _inject_shell_css(auth_page=True)
    _auth_css()
    st.markdown(
        """
        <div class="academy-auth-brand">
          <span class="academy-auth-mark">H</span>
          <div><strong>HWARANG ACADEMY</strong><small>LEARN · PRACTICE · GROW</small></div>
        </div>
        <section class="academy-auth-hero">
          <span class="academy-auth-kicker">HWARANG EDUCATION PLATFORM</span>
          <h1>배움이 성장을 만들고,<br><b>성장이 더 큰 가치를 만듭니다.</b></h1>
          <p>상담 역량부터 보험 실무까지. 화랑 ACADEMY는 FP의 오늘과 내일을 연결하는 통합 교육 플랫폼입니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    login_tab, signup_tab = st.tabs(["로그인", "회원가입"])

    with login_tab:
        left, right = st.columns([1.05, 0.95], gap="large")
        with left:
            st.markdown('<div class="academy-auth-panel-title">ACADEMY 로그인</div><p class="academy-auth-panel-copy">화랑 아이디와 비밀번호를 입력해 주세요.</p>', unsafe_allow_html=True)
            with st.form("academy_login_form", clear_on_submit=False):
                login_id = st.text_input("아이디", placeholder="아이디", key="academy_login_id")
                password = st.text_input("비밀번호", type="password", placeholder="비밀번호", key="academy_login_password")
                submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
            if submitted:
                try:
                    with st.spinner("계정을 확인하고 있습니다..."):
                        _set_authenticated(auth.sign_in(login_id, password))
                    st.rerun()
                except AcademyAuthError as exc:
                    st.error(str(exc))
        with right:
            st.markdown(
                """
                <div class="academy-auth-note">
                <b>처음 방문하셨나요?</b><br><br>
                회원가입 탭에서 본인의 아이디와 비밀번호를 직접 만들 수 있습니다.<br>
                화랑 가입코드를 확인한 뒤 현재 소속 지점을 선택하면 기본 직책은 FP로 등록됩니다.<br><br>
                가입 후 같은 아이디와 비밀번호로 ACADEMY의 모든 교육 기능을 이용할 수 있습니다.
                </div>
                """,
                unsafe_allow_html=True,
            )

    with signup_tab:
        st.markdown('<div class="academy-auth-panel-title">화랑 ACADEMY 회원가입</div><p class="academy-auth-panel-copy">가입코드를 먼저 확인하면 선택 가능한 소속이 표시됩니다.</p>', unsafe_allow_html=True)
        code_col, verify_col = st.columns([4, 1.15], vertical_alignment="bottom")
        with code_col:
            join_code = st.text_input("화랑 가입코드", placeholder="가입코드", key="academy_signup_join_code")
        with verify_col:
            verify = st.button("코드 확인", type="secondary", use_container_width=True, key="academy_verify_join_code")
        if verify:
            try:
                branches = auth.joinable_branches(join_code)
                if not branches:
                    raise AcademyAuthError("가입코드를 확인해 주세요.")
                st.session_state["_academy_signup_branches"] = branches
                st.session_state["_academy_signup_verified_code"] = join_code.strip()
                st.success("가입코드가 확인되었습니다. 소속을 선택해 주세요.")
            except AcademyAuthError as exc:
                st.session_state.pop("_academy_signup_branches", None)
                st.session_state.pop("_academy_signup_verified_code", None)
                st.error(str(exc))

        branches = st.session_state.get("_academy_signup_branches") or []
        verified_code = st.session_state.get("_academy_signup_verified_code", "")
        if branches:
            options = { _branch_label(b): b["code"] for b in branches }
            with st.form("academy_signup_form", clear_on_submit=False):
                c1, c2 = st.columns(2, gap="medium")
                with c1:
                    new_login_id = st.text_input("아이디", placeholder="영문·숫자 3~32자")
                    display_name = st.text_input("이름", placeholder="이름 입력")
                    email = st.text_input("이메일", placeholder="name@example.com")
                with c2:
                    password1 = st.text_input("비밀번호", type="password", placeholder="8자 이상 · 영문+숫자")
                    password2 = st.text_input("비밀번호 확인", type="password", placeholder="한 번 더 입력")
                    branch_label = st.selectbox("소속", list(options), index=0)
                agree = st.checkbox("화랑 ACADEMY 이용을 위한 계정 생성과 학습 데이터 저장에 동의합니다.")
                signup = st.form_submit_button("회원가입 및 ACADEMY 시작", type="primary", use_container_width=True)
            if signup:
                if join_code.strip() != verified_code:
                    st.error("가입코드가 변경되었습니다. 다시 코드 확인을 해주세요.")
                elif password1 != password2:
                    st.error("비밀번호 확인이 일치하지 않습니다.")
                elif not agree:
                    st.error("계정 생성을 위해 동의 항목을 확인해 주세요.")
                else:
                    try:
                        with st.spinner("화랑 ACADEMY 계정을 만들고 있습니다..."):
                            state = auth.sign_up(
                                login_id=new_login_id,
                                password=password1,
                                display_name=display_name,
                                email=email,
                                join_code=verified_code,
                                organization_code=options[branch_label],
                            )
                            _set_authenticated(state)
                        st.rerun()
                    except AcademyAuthError as exc:
                        st.error(str(exc))
        else:
            st.info("가입코드를 확인하면 회원정보와 소속 입력란이 열립니다.")

    if _secret_bool("ACADEMY_ALLOW_DEV_BYPASS", False):
        st.divider()
        if st.button("개발용 인증 우회", use_container_width=False):
            _set_authenticated(
                {
                    "access_token": "",
                    "refresh_token": "",
                    "expires_at": 0,
                    "profile": {
                        "login_id": "dev",
                        "display_name": "개발 테스트",
                        "role": "super_admin",
                        "position_name": "테스트",
                        "organization_name": "HWARANG",
                    },
                    "dev_bypass": True,
                }
            )
            st.rerun()

    st.markdown('<div class="academy-auth-footer">HWARANG ACADEMY · <b>Planned &amp; Built by 박병선 팀장</b></div>', unsafe_allow_html=True)


def base_url() -> str:
    try:
        raw = str(st.secrets.get("academy", {}).get("public_url", ""))
    except (FileNotFoundError, KeyError):
        raw = ""
    if not raw:
        try:
            raw = st.context.url
        except AttributeError:
            raw = ""
    if raw:
        parsed = urlsplit(raw)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return ""


def _logout(auth: AcademyAuthService) -> None:
    state = st.session_state.get("_academy_auth")
    if state and not state.get("dev_bypass"):
        auth.sign_out(state)
    for key in list(st.session_state):
        if key.startswith("_academy_") or key.startswith("academy_"):
            st.session_state.pop(key, None)
    st.query_params.clear()


def main() -> None:
    try:
        auth = auth_service()
    except AcademyAuthError as exc:
        _inject_shell_css(auth_page=True)
        st.error(str(exc))
        st.info("Streamlit Secrets에서 SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY / SUPABASE_SECRET_KEY를 확인해 주세요.")
        return

    state = st.session_state.get("_academy_auth")
    if not state:
        render_auth_page(auth)
        return

    if not state.get("dev_bypass"):
        try:
            state = auth.refresh(state)
            st.session_state["_academy_auth"] = state
        except AcademyAuthError:
            st.session_state.pop("_academy_auth", None)
            st.warning("로그인 시간이 만료되었습니다. 다시 로그인해 주세요.")
            render_auth_page(auth)
            return

    validate_content()
    independent = st.query_params.get("view") == "simulator"
    sid = st.query_params.get("scenario", "C07-S01")
    mode = st.query_params.get("mode", "GUIDE")
    if sid not in SCENARIOS:
        sid = "C07-S01"
    if mode not in MODES:
        mode = "GUIDE"

    route_key = (independent, sid)
    if st.session_state.get("_academy_route") != route_key:
        st.session_state["_academy_route"] = route_key
        st.session_state["_academy_model"] = AppState(independent=independent, selection=sid, mode=mode)
    app = st.session_state["_academy_model"]

    _inject_shell_css(auth_page=False, independent=independent)
    payload = present(app)
    payload["base_url"] = base_url()
    payload["viewer"] = {
        key: state.get("profile", {}).get(key)
        for key in (
            "login_id",
            "display_name",
            "role",
            "position_name",
            "organization_name",
        )
    }

    event = component()(model=payload, key="academy_engine_component_v57", default=None)
    if isinstance(event, dict) and event.get("event_id") != app.ack:
        if event.get("kind") == "auth_logout":
            _logout(auth)
            st.rerun()
        # The controller verifies mode, scenario, payload sizes and once-only commits.
        try:
            handle(app, event)
        except (ValueError, TypeError):
            app.error = "요청을 확인해 주세요."
            # Consume a malformed component event rather than rerunning forever.
            app.ack = event.get("event_id")
        st.rerun()


if __name__ == "__main__":
    main()
