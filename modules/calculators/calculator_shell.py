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
    """Compatibility name; independent calculator navigation now lives at the top."""
    from modules.shared.premium_homes import apply, identity_header
    apply('calculator')
    identity = st.session_state.get('_hwarang_calculator_identity') or {}
    owner = str((identity.get('profile') or {}).get('id') or '')
    if st.session_state.get('hp_quick_owner') != owner:
        for key in ('hp_quick_values', 'hp_quick_transfer', 'hp_quick_premium', 'hp_quick_years'):
            st.session_state.pop(key, None)
        st.session_state['hp_quick_owner'] = owner
    identity_header('CALCULATOR', identity.get('profile') or {})
    permissions = set(st.session_state.get('hw_feature_permissions') or ())
    allowed_groups = [g for g in GROUPS if CALCULATOR_GROUP_PERMISSION.get(g) in permissions]
    current = st.session_state.get('hwcalc_catalog_group', '전체')
    if current not in {'전체', *allowed_groups}:
        _show_catalog()
        current = '전체'
    if not st.session_state.get('hwcalc_open'):
        st.markdown('<section class="hp-calculator-intro"><span class="hp-kicker">FINANCIAL TOOLS, CLEAR ANSWERS</span><h1>필요한 계산을, 명확하게.</h1><p>계산기를 찾고 조건을 입력해 상담의 근거를 준비하세요.</p></section>', unsafe_allow_html=True)
    with st.container(key='hp_calc_navigation', horizontal=True):
        st.button('🗂️ 전체 계산기', key='calc_sidebar_home', type='primary' if current=='전체' and not st.session_state.get('hwcalc_open') else 'secondary', on_click=_show_catalog)
        for index, group in enumerate(allowed_groups):
            st.button(category_label(group, GROUP_COUNTS.get(group)), key=f'calc_sidebar_group_{index}', type='primary' if current==group and not st.session_state.get('hwcalc_open') else 'secondary', on_click=_show_catalog, args=(group,))
