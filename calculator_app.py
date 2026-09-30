"""Public, separately deployed entrypoint for the 80-calculator center."""
from __future__ import annotations

import streamlit as st

from modules.calculators.calculator_shell import render_sidebar
from modules.calculators.calculator_theme import apply as apply_calculator_theme
from modules.shared.ui_components import inject_global_styles

st.set_page_config(
    page_title="화랑 CALCULATOR",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="auto",
)
st.set_option("client.toolbarMode", "minimal")


def main() -> None:
    inject_global_styles()
    apply_calculator_theme()
    st.markdown('<div class="hw-calculator-standalone" aria-hidden="true"></div>', unsafe_allow_html=True)
    render_sidebar()
    with st.container(key="hw_calc_shell"):
        from modules.calculators.calculator_center import run
        run()
    inject_global_styles()
    apply_calculator_theme()


if __name__ == "__main__":
    main()
