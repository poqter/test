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
        cols = st.columns([1.15, 1], gap='large') if quick_name in items else [st.container()]
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
                                st.button('계산하기 →', key=card_key(name)+'_open_here', on_click=open_calculator, args=(name,), use_container_width=True)
                                if st.button('새 탭 ↗', key=card_key(name)+'_prepare_tab', use_container_width=True):
                                    open_new_tab(name, ids)
        if quick_name in items:
            with cols[1], st.container(key='hp_calc_quick'):
                st.markdown('<span class="hp-kicker">QUICK CALCULATION</span>', unsafe_allow_html=True)
                st.subheader('보험료 합계')
                st.caption('월 납입액과 기간을 바꾸면 합계를 확인할 수 있습니다. 초기 금액은 입력 예시입니다.')
                saved = st.session_state.get('hp_quick_values', {'premium': 100000, 'years': 20})
                premium = st.number_input('월 보험료 (원)', min_value=0, max_value=100000000, value=saved['premium'], step=1000, key='hp_quick_premium')
                years = st.number_input('납입 기간 (년)', min_value=1, max_value=100, value=saved['years'], step=1, key='hp_quick_years')
                st.session_state['hp_quick_values'] = {'premium': premium, 'years': years}
                from modules.calculators.calculator_core import calculate
                result = calculate('total', {'premium': premium, 'months': years*12, 'paid': 0})
                st.metric('총 납입 보험료', f'{result["총 납입 예정"]:,.0f}원')
                st.caption('월 보험료 × 12개월 × 납입 연수')
                with st.expander('산출 기준 확인'):
                    st.write('보험료가 변하지 않고 매월 납부하는 경우의 단순 합계입니다. 갱신·감액·중도해지 등의 변화는 반영하지 않습니다.')
                st.button('이 조건으로 상세 계산 →', key='hp_quick_full', on_click=_open_total, args=(premium, years), use_container_width=True)
    footer('CALCULATOR')


def _open_total(premium, years):
    """Explicit hand-off, consumed after draft activation."""
    from modules.calculators.catalog_browser import open_calculator
    open_calculator('총 납입보험료계산기')
    st.session_state['hp_quick_transfer'] = {'premium': int(premium), 'months': int(years)*12}
