"""Separate Streamlit ACADEMY entrypoint reached through HWARANG WORKSPACE."""
from __future__ import annotations

from functools import lru_cache
import html
from urllib.parse import urlsplit, urlunsplit

import streamlit as st
import streamlit.components.v1 as components

from hwarang_academy.auth_service import AcademyAuthError, AcademyAuthService, SupabaseConfig
from hwarang_academy.content import ROOT, SCENARIOS, MODES, validate_content
from hwarang_academy.service import AppState, handle, present
from modules.shared.external_apps import workspace_url
from modules.shared.ai_guardrails import get_training_credit_status
from modules.shared.academy_credit_ui import render_training_credit_strip


st.set_page_config(
    page_title="화랑 ACADEMY",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@lru_cache(maxsize=1)
def component():
    return components.declare_component("hwarang_academy_v61", path=str(ROOT / "frontend"))


@lru_cache(maxsize=1)
def validate_academy_content() -> bool:
    """Validate static ACADEMY content once per process instead of every rerun."""
    validate_content()
    return True


@st.cache_resource(show_spinner=False)
def auth_service() -> AcademyAuthService:
    return AcademyAuthService(SupabaseConfig.from_mapping(st.secrets))


def _inject_shell_css(*, gate: bool = False, independent: bool = False) -> None:
    bg = "#0a233e" if independent else "#f4f7fb"
    page_bg = "#f5f8fc" if gate else bg
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="stExpandSidebarButton"]{{display:none!important}}
        [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer{{display:none!important}}
        .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:{page_bg}!important}}
        [data-testid="stMainBlockContainer"]{{max-width:{'1180px' if gate else '1600px'}!important;padding:{'34px 26px 54px' if gate else '0'}!important}}
        iframe[title*="hwarang_academy"]{{border:0!important;display:block;width:100%}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _gate_css() -> None:
    st.markdown(
        """
        <style>
        .academy-gate-brand{display:flex;align-items:center;gap:12px;margin:2px 0 22px;color:#15324e}
        .academy-gate-mark{display:grid;place-items:center;width:42px;height:44px;border-radius:12px;background:linear-gradient(145deg,#2162a8,#153c65);color:#fff;font-size:24px;font-weight:900;box-shadow:0 8px 22px #225b8a28}
        .academy-gate-brand strong{display:block;font-size:15px;letter-spacing:.055em;line-height:1.15}.academy-gate-brand small{display:block;margin-top:4px;color:#7890a9;font-size:11px;letter-spacing:.08em}
        .academy-gate-card{position:relative;overflow:hidden;padding:46px 48px;border:1px solid #d7e4f0;border-radius:26px;background:radial-gradient(circle at 88% 20%,#c8e0f7 0,transparent 29%),linear-gradient(120deg,#fff 10%,#edf5fd 58%,#dbeaf8);box-shadow:0 18px 50px #284f7310}
        .academy-gate-card:after{content:"";position:absolute;right:-3%;bottom:-44%;width:55%;height:78%;background:linear-gradient(145deg,#aec9df,#718da8);clip-path:polygon(0 100%,24% 44%,37% 66%,55% 18%,68% 50%,79% 34%,100% 100%);opacity:.42}
        .academy-gate-card>*{position:relative;z-index:2}.academy-gate-kicker{color:#5580a5;font-size:11px;font-weight:800;letter-spacing:.13em}.academy-gate-card h1{margin:12px 0 14px;color:#12314f;font-size:clamp(30px,4vw,48px);line-height:1.18;letter-spacing:-.055em}.academy-gate-card p{max-width:560px;margin:0;color:#526f88;font-size:14px;line-height:1.8}.academy-gate-card b{color:#2369b8}
        .academy-gate-note{margin:20px 0 0;padding:15px 17px;border:1px solid #dce7f2;border-radius:14px;background:#fff;color:#60788e;font-size:13px;line-height:1.7}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_workspace_gate(message: str | None = None) -> None:
    _inject_shell_css(gate=True)
    _gate_css()
    st.markdown(
        """
        <div class="academy-gate-brand">
          <span class="academy-gate-mark">H</span>
          <div><strong>HWARANG ACADEMY</strong><small>LEARN · PRACTICE · GROW</small></div>
        </div>
        <section class="academy-gate-card">
          <span class="academy-gate-kicker">HWARANG EDUCATION PLATFORM</span>
          <h1>ACADEMY는<br><b>HWARANG WORKSPACE에서 시작됩니다.</b></h1>
          <p>통합 HWARANG 계정으로 WORKSPACE에 로그인한 뒤 ACADEMY를 열어 주세요. 별도의 ACADEMY 로그인은 필요하지 않습니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if message:
        st.markdown(f'<div class="academy-gate-note">{html.escape(message)}</div>', unsafe_allow_html=True)
    target = workspace_url()
    if target:
        st.link_button("HWARANG WORKSPACE로 이동 →", target, type="primary", use_container_width=True)
    else:
        st.info("ACADEMY 앱의 Streamlit Secrets에 external_apps.workspace_url을 설정해 주세요.")
    st.caption("Planned & Built by 박병선 팀장")


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


def _remove_query_param(key: str) -> None:
    """Remove one query parameter while preserving future ACADEMY deep links."""
    try:
        if key in st.query_params:
            del st.query_params[key]
    except (AttributeError, KeyError, TypeError):
        pass


def _consume_workspace_launch(auth: AcademyAuthService) -> dict | None:
    state = st.session_state.get("_hwarang_launch_identity")
    raw = str(st.query_params.get("launch", "") or "").strip()
    if not state and raw:
        try:
            state = auth.consume_launch_ticket(raw, "academy")
        except AcademyAuthError as exc:
            _remove_query_param("launch")
            render_workspace_gate(str(exc))
            st.stop()
        st.session_state["_hwarang_launch_identity"] = state
        # Remove only the one-time credential. Scenario/view parameters remain.
        _remove_query_param("launch")
    if not state:
        return None
    try:
        state = auth.refresh_launch_identity(state, "academy")
    except AcademyAuthError as exc:
        st.session_state.pop("_hwarang_launch_identity", None)
        render_workspace_gate(str(exc))
        st.stop()
    st.session_state["_hwarang_launch_identity"] = state
    return state


def main() -> None:
    try:
        auth = auth_service()
    except AcademyAuthError as exc:
        render_workspace_gate(str(exc))
        return

    identity = _consume_workspace_launch(auth)
    if not identity:
        render_workspace_gate()
        return

    validate_academy_content()
    feature_permissions = set(identity.get("feature_permissions") or ())
    viewer_profile = identity.get("profile", {}) if isinstance(identity.get("profile"), dict) else {}
    viewer_user_id = str(viewer_profile.get("id") or "")
    credit_status = get_training_credit_status(auth, viewer_user_id) if viewer_user_id else None

    independent = st.query_params.get("view") == "simulator"
    if independent and "academy.simulator" not in feature_permissions:
        render_workspace_gate("이 계정에는 AI 상담 시뮬레이터 이용 권한이 없습니다.")
        return
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

    _inject_shell_css(gate=False, independent=independent)
    payload = present(app)
    payload["base_url"] = base_url()
    payload["workspace_url"] = workspace_url()
    payload["feature_permissions"] = sorted(feature_permissions)
    payload["viewer"] = {
        key: identity.get("profile", {}).get(key)
        for key in (
            "login_id",
            "display_name",
            "role",
            "position_name",
            "organization_name",
        )
    }

    if credit_status:
        payload["training_credit"] = {
            "allocation": credit_status.allocation_credits,
            "available": credit_status.available_credits,
            "remaining_percent": credit_status.remaining_percent,
            "monthly_period": credit_status.monthly_credit_period,
            "monthly_grant": credit_status.monthly_grant_credits,
            "monthly_available": credit_status.monthly_available_credits,
            "purchased_available": credit_status.purchased_available_credits,
            "warning_percent": credit_status.remaining_warning_percent,
            "low": credit_status.training_low,
            "service_enabled": credit_status.service_enabled,
        }
        payload["voice_usage"] = {
            "allocation_seconds": credit_status.voice_allocation_seconds,
            "available_seconds": credit_status.voice_available_seconds,
            "remaining_percent": credit_status.voice_remaining_percent,
            "warning_percent": credit_status.remaining_warning_percent,
            "low": credit_status.voice_low,
            "voice_enabled": credit_status.voice_enabled,
            "provider_model": "gpt-live-1",
        }

    if "academy.simulator" in feature_permissions:
        render_training_credit_strip(credit_status)

    event = component()(model=payload, key="academy_engine_component_v61", default=None)
    if isinstance(event, dict) and event.get("event_id") != app.ack:
        try:
            if event.get("kind") == "open_simulator" and "academy.simulator" not in feature_permissions:
                raise ValueError("AI 상담 시뮬레이터 이용 권한이 없습니다.")
            handle(app, event)
        except (ValueError, TypeError):
            app.error = "요청을 확인해 주세요."
            app.ack = event.get("event_id")
        st.rerun()


if __name__ == "__main__":
    main()
