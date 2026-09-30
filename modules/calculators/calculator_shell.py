"""Navigation shell for the separately deployed public Calculator app."""
from __future__ import annotations

import streamlit as st

from modules.calculators.jarvia_calculator_center import GROUPS
from modules.calculators.visuals import category_label


def _show_catalog(group: str = "전체") -> None:
    st.session_state.pop("jc_open", None)
    st.session_state.pop("jc_selected", None)
    try:
        if "calc" in st.query_params:
            del st.query_params["calc"]
    except (AttributeError, KeyError, TypeError):
        pass
    st.session_state["jc_catalog_group"] = group
    st.session_state["jc_catalog_query"] = ""
    st.session_state["jc_search"] = ""
    st.session_state["jc_catalog_restore"] = False


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="sig-brand"><span class="sig-mark">H</span><div><strong>화랑</strong><small>CALCULATOR</small></div></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "계산기 센터",
            icon=":material/calculate:",
            key="calc_sidebar_home",
            type="primary" if not st.session_state.get("jc_open") else "secondary",
            use_container_width=True,
        ):
            _show_catalog()
            st.rerun()
        st.caption("🗂️ 업무 분류")
        current = st.session_state.get("jc_catalog_group", "전체")
        for index, group in enumerate(GROUPS):
            label = category_label(group)
            if st.button(
                label,
                key=f"calc_sidebar_group_{index}",
                type="primary" if not st.session_state.get("jc_open") and current == group else "secondary",
                use_container_width=True,
            ):
                _show_catalog(group)
                st.rerun()
        st.divider()
        st.markdown(
            '<div class="hw-calc-sidebar-note">WORKSPACE에서 새 탭으로 열면<br>기존 업무 탭과 로그인 상태가 그대로 유지됩니다.</div>',
            unsafe_allow_html=True,
        )
        st.caption("Planned & Built by 박병선 팀장")
