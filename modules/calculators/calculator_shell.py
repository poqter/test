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
    """Full calculator app sidebar; independent single-calculator windows omit it."""
    from modules.shared import brand_ui as ui
    ui.apply()
    identity = st.session_state.get('_hwarang_calculator_identity') or {}
    owner = str((identity.get('profile') or {}).get('id') or '')
    if st.session_state.get('hp_quick_owner') != owner:
        for key in ('hp_quick_values', 'hp_quick_transfer', 'hp_quick_premium', 'hp_quick_years'):
            st.session_state.pop(key, None)
        st.session_state['hp_quick_owner'] = owner
    permissions = set(st.session_state.get('hw_feature_permissions') or ())
    allowed_groups = [g for g in GROUPS if CALCULATOR_GROUP_PERMISSION.get(g) in permissions]
    from modules.calculators.hwarang_calculator_center import ITEMS
    active = st.session_state.get('hwcalc_open')
    active_group = ITEMS[active][0] if active in ITEMS else None
    current = st.session_state.get('hwcalc_catalog_group', '전체')
    if current not in {'전체', *allowed_groups}:
        _show_catalog()
        current = '전체'
    ui.identity('CALCULATOR', identity.get('profile') or {})
    with st.sidebar:
        st.markdown('### 화랑 CALCULATOR')
        st.caption('계산기 센터')
        st.button('전체 계산기',key='calc_sidebar_home',type='primary' if current=='전체' and not active_group else 'secondary',on_click=_show_catalog,use_container_width=True)
        for index,group in enumerate(allowed_groups):
            st.button(f'{group}  {GROUP_COUNTS.get(group,0)}',key=f'calc_sidebar_group_{index}',type='primary' if (active_group or current)==group else 'secondary',on_click=_show_catalog,args=(group,),use_container_width=True)
    with st.container(key='brand_mobile_category'):
        choices=['전체']+allowed_groups
        st.session_state['brand_mobile_group']=active_group or current
        def change(): _show_catalog(st.session_state['brand_mobile_group'])
        st.selectbox('현재 분류',choices,index=choices.index(current),key='brand_mobile_group',on_change=change)
