"""Catalog presentation only; all routes and calculations use existing engines."""
from contextlib import nullcontext
from html import escape
import streamlit as st


def render_sections(sections, items, ids, *, query='', group='전체'):
    from modules.calculators.catalog_browser import card_key, open_calculator, open_new_tab
    from modules.calculators.visuals import category_emoji, category_label
    from modules.calculators.ux_profiles import profile
    from modules.shared.premium_homes import footer, emoji_markup
    st.markdown("""<style>
    [class*="st-key-hw_calc_row_"] .hw-calc-card-copy{min-height:130px;align-items:flex-start}
    .hw-calc-card-title{min-height:3em;line-height:1.5;overflow-wrap:anywhere}
    .hw-calc-card-summary{min-height:3.2em;line-height:1.6;overflow-wrap:anywhere}
    [class*="st-key-hwcalc_actions_"] button{min-height:44px}
    @media(max-width:767px){[class*="st-key-hw_calc_row_"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
    [class*="st-key-hw_calc_row_"] [data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important}
    [class*="st-key-hw_calc_row_"] .hw-calc-card-copy{min-height:0}}
    </style>""", unsafe_allow_html=True)
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
                    for offset in range(0, len(section_items), 2):
                        with st.container(key=f'hw_calc_row_{index}_{offset}'):
                            columns = st.columns(2, gap='medium')
                            for column, (name, _, description) in zip(columns, section_items[offset:offset+2]):
                                summary = description.replace('계산 결과: ', '').split(' 적용 조건')[0]
                                meta = profile(name)
                                with column, st.container(key=card_key(name)):
                                    st.markdown(
                                        f'<div class="hw-calc-card-copy"><span class="hw-calc-card-icon" aria-hidden="true">{emoji_markup(category_emoji(items[name][0]))}</span>'
                                        f'<div><div class="hw-calc-card-title">{escape(name.removesuffix("계산기"))}</div>'
                                        f'<div class="hw-calc-card-summary">{escape(summary)}</div>'
                                        f'<div class="hw-calc-card-core">먼저 입력 · {escape(meta.get("core", "핵심 조건"))}</div></div></div>', unsafe_allow_html=True)
                                    with st.container(key='hwcalc_actions_'+card_key(name)):
                                        st.button('현재 탭에서 열기 →', key=card_key(name)+'_open_here', on_click=open_calculator, args=(name,), use_container_width=True)
                                        if st.button('새 탭에서 열기 ↗', key=card_key(name)+'_prepare_tab', use_container_width=True):
                                            open_new_tab(name, ids)
    footer('CALCULATOR')
