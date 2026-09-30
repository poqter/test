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


def _apply_calculator_deep_link() -> None:
    try:
        raw = st.query_params.get("calc")
    except AttributeError:
        raw = None
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None
    value = str(raw).strip() if raw else ""
    if not value:
        return
    name = value if value in ITEMS else ITEM_IDS.get(value, "")
    if not name:
        try:
            del st.query_params["calc"]
        except (AttributeError, KeyError, TypeError):
            pass
        return
    st.session_state["jc_open"] = name
    st.session_state["jc_selected"] = name
    st.session_state["jc_catalog_last"] = name


def main() -> None:
    _apply_calculator_deep_link()
    inject_global_styles()
    apply_calculator_theme()
    st.markdown('<div class="hw-calculator-standalone" aria-hidden="true"></div>', unsafe_allow_html=True)
    render_sidebar()
    with st.container(key="hw_calc_shell"):
        from modules.calculators.calculator_center import run
        run()


if __name__ == "__main__":
    main()
