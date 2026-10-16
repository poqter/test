"""Navigation shell for the protected HWARANG Calculator app."""
from __future__ import annotations

import streamlit as st

from modules.calculators.hwarang_calculator_center import GROUPS, GROUP_COUNTS
from modules.calculators.visuals import category_label
from modules.shared.permissions import CALCULATOR_GROUP_PERMISSION


def _show_catalog(group: str = "전체") -> None:
    st.session_state.pop("hwcalc_open", None)
    st.session_state.pop("hwcalc_selected", None)
    try:
        for query_key in ("calc", "view"):
            if query_key in st.query_params:
                del st.query_params[query_key]
    except (AttributeError, KeyError, TypeError):
        pass
    st.session_state["hwcalc_catalog_group"] = group
    st.session_state["hwcalc_catalog_query"] = ""
    st.session_state["hwcalc_search"] = ""
    st.session_state["hwcalc_catalog_restore"] = False


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="sig-brand"><span class="sig-mark">H</span><div><strong>화랑</strong><small>CALCULATOR</small></div></div>',
            unsafe_allow_html=True,
        )
        current = st.session_state.get("hwcalc_catalog_group", "전체")
        permissions = set(st.session_state.get("hw_feature_permissions") or ())
        allowed_groups = [group for group in GROUPS if CALCULATOR_GROUP_PERMISSION.get(group) in permissions]
        accessible_count = sum(GROUP_COUNTS.get(group, 0) for group in allowed_groups)
        if st.button(
            f"종합 계산기 센터 ({accessible_count}개)",
            icon=":material/calculate:",
            key="calc_sidebar_home",
            type="primary" if not st.session_state.get("hwcalc_open") and current == "전체" else "secondary",
            use_container_width=True,
        ):
            _show_catalog()
            st.rerun()
        st.caption("🗂️ 업무 분류")
        if current not in {"전체", *allowed_groups}:
            _show_catalog()
            current = "전체"
        for index, group in enumerate(allowed_groups):
            label = category_label(group, GROUP_COUNTS.get(group))
            if st.button(
                label,
                key=f"calc_sidebar_group_{index}",
                type="primary" if not st.session_state.get("hwcalc_open") and current == group else "secondary",
                use_container_width=True,
            ):
                _show_catalog(group)
                st.rerun()
        st.divider()
        st.markdown(
            '<div class="hw-calc-sidebar-note">새 탭 계산기는 인증용 링크를 준비한 뒤 열립니다.<br>기존 WORKSPACE와 계산기 센터 탭은 그대로 유지됩니다.</div>',
            unsafe_allow_html=True,
        )
        st.caption("Planned & Built by 박병선 팀장")
        from modules.shared.build_info import BUILD_ID
        st.caption("버전 " + BUILD_ID)
