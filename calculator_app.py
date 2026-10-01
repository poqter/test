"""Public, separately deployed entrypoint for the 88-calculator center."""
from __future__ import annotations

import streamlit as st

from modules.calculators.calculator_shell import render_sidebar
from modules.calculators.jarvia_calculator_center import ITEMS, ITEM_IDS
from modules.calculators.calculator_theme import apply as apply_calculator_theme
from modules.shared.ui_components import inject_global_styles

st.set_page_config(
    page_title="종합 계산기 센터 (88개) | 화랑",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="auto",
)
st.set_option("client.toolbarMode", "minimal")


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except AttributeError:
        raw = None
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None
    return str(raw).strip() if raw else ""


def _is_isolated_view() -> bool:
    return _query_value("view").casefold() in {"single", "standalone", "isolated"}


def _apply_calculator_deep_link() -> bool:
    value = _query_value("calc")
    if not value:
        st.session_state.pop("hw.calculator.last_deep_link", None)
        return False
    name = value if value in ITEMS else ITEM_IDS.get(value, "")
    if not name:
        try:
            del st.query_params["calc"]
        except (AttributeError, KeyError, TypeError):
            pass
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
    isolated = _is_isolated_view()
    valid_deep_link = _apply_calculator_deep_link()

    inject_global_styles()
    apply_calculator_theme()
    st.markdown('<div class="hw-calculator-standalone" aria-hidden="true"></div>', unsafe_allow_html=True)

    if isolated:
        # 로그인 화면과 같은 배경 위에 선택한 계산기만 띄우는 독립 실행 화면입니다.
        st.session_state["jc_isolated_single"] = True
        st.markdown('<div class="hw-auth-bg hw-calc-isolated-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
        with st.container(key="hw_calc_isolated_shell"):
            _isolated_brand()
            if not valid_deep_link or not st.session_state.get("jc_open"):
                st.error("유효한 계산기 링크가 아닙니다. 계산기 센터에서 새 탭으로 다시 열어주세요.")
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
