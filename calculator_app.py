"""Protected, separately deployed entrypoint for HWARANG CALCULATOR."""
from __future__ import annotations

import html
import streamlit as st

from modules.calculators.calculator_shell import render_sidebar
from modules.calculators.jarvia_calculator_center import ITEMS, ITEM_IDS
from modules.calculators.calculator_theme import apply as apply_calculator_theme
from modules.shared.external_apps import workspace_url
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService, SupabaseConfig
from modules.shared.ui_components import inject_global_styles

st.set_page_config(
    page_title="종합 계산기 센터 (88개) | 화랑",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="auto",
)
st.set_option("client.toolbarMode", "minimal")


@st.cache_resource(show_spinner=False)
def auth_service() -> HwarangAuthService:
    return HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except AttributeError:
        raw = None
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None
    return str(raw).strip() if raw else ""


def _remove_query_param(key: str) -> None:
    try:
        if key in st.query_params:
            del st.query_params[key]
    except (AttributeError, KeyError, TypeError):
        pass


def _render_workspace_gate(message: str | None = None) -> None:
    inject_global_styles()
    st.markdown('<div class="hw-auth-bg" aria-hidden="true"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"]{display:none!important}
        [data-testid="stMainBlockContainer"]{max-width:980px!important;padding-top:50px!important}
        .calc-gate{padding:44px 46px;border:1px solid #d6e3ef;border-radius:24px;background:linear-gradient(135deg,#fff,#edf5fc);box-shadow:0 18px 48px rgba(20,57,87,.08)}
        .calc-gate h1{margin:10px 0 12px;color:#153451;font-size:42px;letter-spacing:-.05em}.calc-gate p{color:#5f768c;line-height:1.75}.calc-gate small{color:#6688a8;font-weight:800;letter-spacing:.12em}.calc-gate b{color:#2468b0}
        .calc-gate-note{margin:16px 0;padding:13px 15px;border:1px solid #dbe6ef;border-radius:12px;background:#fff;color:#60788e}
        </style>
        <section class="calc-gate"><small>HWARANG PLATFORM</small><h1>CALCULATOR는<br><b>HWARANG WORKSPACE에서 시작됩니다.</b></h1><p>WORKSPACE에서 로그인한 뒤 CALCULATOR를 열어 주세요. 별도의 CALCULATOR 로그인은 필요하지 않습니다.</p></section>
        """,
        unsafe_allow_html=True,
    )
    if message:
        st.markdown(f'<div class="calc-gate-note">{html.escape(message)}</div>', unsafe_allow_html=True)
    target = workspace_url()
    if target:
        st.link_button("HWARANG WORKSPACE로 이동 →", target, type="primary", use_container_width=True)
    else:
        st.info("CALCULATOR 앱의 Streamlit Secrets에 external_apps.workspace_url을 설정해 주세요.")
    st.caption("Planned & Built by 박병선 팀장")


def _consume_workspace_launch(auth: HwarangAuthService) -> dict | None:
    state = st.session_state.get("_hwarang_calculator_identity")
    raw = _query_value("launch")
    if not state and raw:
        try:
            state = auth.consume_launch_ticket(raw, "calculator")
        except HwarangAuthError as exc:
            _remove_query_param("launch")
            _render_workspace_gate(str(exc))
            st.stop()
        st.session_state["_hwarang_calculator_identity"] = state
        _remove_query_param("launch")
    if not state:
        return None
    try:
        state = auth.refresh_launch_identity(state, "calculator")
    except HwarangAuthError as exc:
        st.session_state.pop("_hwarang_calculator_identity", None)
        _render_workspace_gate(str(exc))
        st.stop()
    st.session_state["_hwarang_calculator_identity"] = state
    st.session_state["hw_feature_permissions"] = set(state.get("feature_permissions") or ())
    st.session_state["hw_app_access"] = dict(state.get("app_access") or {})
    return state


def _is_isolated_view() -> bool:
    return _query_value("view").casefold() in {"single", "standalone", "isolated"}


def _apply_calculator_deep_link() -> bool:
    value = _query_value("calc")
    if not value:
        st.session_state.pop("hw.calculator.last_deep_link", None)
        return False
    name = value if value in ITEMS else ITEM_IDS.get(value, "")
    if not name:
        _remove_query_param("calc")
        return False
    if not _is_isolated_view() and st.session_state.get("hw.calculator.last_deep_link") == value:
        return True
    st.session_state["hw.calculator.last_deep_link"] = value
    st.session_state["jc_open"] = name
    st.session_state["jc_selected"] = name
    st.session_state["jc_catalog_last"] = name
    return True


def _isolated_brand() -> None:
    st.markdown(
        '<div class="hw-calc-isolated-brand"><span>H</span><div><strong>화랑</strong><small>CALCULATOR</small></div></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    try:
        auth = auth_service()
    except HwarangAuthError as exc:
        _render_workspace_gate(str(exc))
        return

    identity = _consume_workspace_launch(auth)
    if not identity:
        _render_workspace_gate()
        return

    isolated = _is_isolated_view()
    valid_deep_link = _apply_calculator_deep_link()

    inject_global_styles()
    apply_calculator_theme()
    st.markdown('<div class="hw-calculator-standalone" aria-hidden="true"></div>', unsafe_allow_html=True)

    if isolated:
        st.session_state["jc_isolated_single"] = True
        st.markdown('<div class="hw-auth-bg hw-calc-isolated-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
        with st.container(key="hw_calc_isolated_shell"):
            _isolated_brand()
            if not valid_deep_link or not st.session_state.get("jc_open"):
                st.error("유효한 계산기 링크가 아닙니다. 계산기 센터에서 다시 열어주세요.")
            else:
                from modules.calculators.calculator_center import run
                run(isolated=True, fixed_name=st.session_state.get("jc_open"))
            from modules.shared.build_info import BUILD_ID
            st.markdown(f'<div class="hw-calc-isolated-footer">Planned &amp; Built by 박병선 팀장 · {BUILD_ID}</div>', unsafe_allow_html=True)
        return

    st.session_state["jc_isolated_single"] = False
    render_sidebar()
    with st.container(key="hw_calc_shell"):
        from modules.calculators.calculator_center import run
        run()


if __name__ == "__main__":
    main()
