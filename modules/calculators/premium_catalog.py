"""Catalog presentation only; all routes and calculations use existing engines."""
from contextlib import nullcontext
from html import escape
import streamlit as st


def render_sections(sections, items, ids, *, query='', group='전체'):
    from modules.calculators.catalog_browser import card_key, open_calculator, open_new_tab
    from modules.calculators.visuals import category_emoji, category_label
    from modules.calculators.ux_profiles import profile
    from modules.shared.premium_homes import footer, emoji_markup
    quick_name = '총 납입보험료계산기'
    with st.container(key='hp_calc_layout'):
        cols = [st.container()]
        with cols[0], st.container(key='hp_calc_catalog'):
            for index, (category, section_items) in enumerate(sections):
                if not section_items:
                    continue
                if group == '전체' and not query:
                    context = st.expander(category_label(category) + f' · {len(section_items)}개', expanded=index == 0)
                else:
                    context = nullcontext()
                    if category is not None:
                        st.markdown('##### ' + (category if category in ('이름 일치', '관련 계산기') else category_label(category)))
                with context:
                    for name, _, description in section_items:
                        summary = description.replace('계산 결과: ', '').split(' 적용 조건')[0]
                        meta = profile(name)
                        with st.container(key=card_key(name)):
                            copy, actions = st.columns([2.3, 1], gap='small', vertical_alignment='center')
                            copy.markdown(
                                f'<div class="hw-calc-card-copy"><span class="hw-calc-card-icon" aria-hidden="true">{emoji_markup(category_emoji(items[name][0]))}</span>'
                                f'<div><div class="hw-calc-card-title">{escape(name.removesuffix("계산기"))}</div>'
                                f'<div class="hw-calc-card-summary">{escape(summary)}</div>'
                                f'<div class="hw-calc-card-core">먼저 입력 · {escape(meta.get("core", "핵심 조건"))}</div></div></div>', unsafe_allow_html=True)
                            with actions.container(key='hwcalc_actions_'+card_key(name)):
                                st.button('현재 탭에서 열기 →', key=card_key(name)+'_open_here', on_click=open_calculator, args=(name,), use_container_width=True)
                                if st.button('새 탭에서 열기 ↗', key=card_key(name)+'_prepare_tab', use_container_width=True):
                                    open_new_tab(name, ids)
    footer('CALCULATOR')
