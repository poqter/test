"""Local reference lookup; never infer surgery classes from partial matches."""
from functools import lru_cache
from pathlib import Path
import json
import re
import unicodedata
from html import escape


RESULT_CSS = '''<style>
.st-key-surgery_search_box input::placeholder{color:#9aa5b4!important;font-weight:400!important;opacity:1!important}
.hw-surgery-results{color:#213149;background:#fff}
.hw-surgery-row{display:grid;grid-template-columns:minmax(0,1fr) 174px;gap:24px;align-items:center;padding:18px 4px;border-bottom:1px solid #edf0f4}
.hw-surgery-name{font-size:16px;font-weight:500;line-height:1.75;overflow-wrap:anywhere;word-break:keep-all;min-width:0}
.hw-surgery-grades{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.hw-surgery-grade{display:flex;flex-direction:column;gap:8px;align-items:center}
.hw-surgery-label{font-size:12px;color:#748095;white-space:nowrap}
.hw-surgery-badge{font-size:14px;font-weight:600;border-radius:8px;min-width:52px;padding:7px 12px;text-align:center;background:#f0f2f5;color:#5d697a}
.hw-surgery-c2{background:#edf3ff;color:#426ba6}.hw-surgery-c3{background:#f1edfc;color:#7553a5}
.hw-surgery-c4{background:#fff1e5;color:#9c570f}.hw-surgery-c5{background:#e5f4f1;color:#236b62}
.hw-surgery-na{background:#fafbfc;border:1px solid #e2e6ed;color:#697586}
@media(max-width:600px){.hw-surgery-row{grid-template-columns:minmax(0,1fr);gap:10px;padding:16px 0}.hw-surgery-grades{display:flex;flex-wrap:wrap;gap:20px}.hw-surgery-grade{flex-direction:row;gap:8px}.hw-surgery-badge{min-width:44px;padding:5px 9px}.hw-surgery-name{font-size:15px}}
</style>'''


def render_results(rows):
    """Escape dataset text before placing it in the responsive result list."""
    cards = []
    for row in rows:
        badges = []
        for key, label in [('class3', '1~3종 기준'), ('class5', '1~5종 기준')]:
            value = row[key]
            tone = 'c' + value[0] if value in {'1종', '2종', '3종', '4종', '5종'} else 'na'
            badges.append(f'<div class="hw-surgery-grade"><span class="hw-surgery-label">{label}</span><span class="hw-surgery-badge hw-surgery-{tone}">{escape(value)}</span></div>')
        cards.append(f'<article class="hw-surgery-row"><div class="hw-surgery-name">{escape(row["name"])}</div><div class="hw-surgery-grades">{"".join(badges)}</div></article>')
    return '<div class="hw-surgery-results">' + ''.join(cards) + '</div>'


def normalize(value):
    return re.sub(r'[^\w가-힣]', '', unicodedata.normalize('NFKC', value).casefold()).replace('_', '')


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).resolve().parents[2]/'data/surgery_reference.json').read_text(encoding='utf-8'))


def search(rows, query='', class3='전체', class5='전체'):
    terms=[normalize(x) for x in query.split() if normalize(x)]
    key=normalize(query)
    found=[r for r in rows if all(t in normalize(r['name']) for t in terms)
           and (class3=='전체' or r['class3']==class3)
           and (class5=='전체' or r['class5']==class5)]
    return sorted(found,key=lambda r:(normalize(r['name'])!=key,not normalize(r['name']).startswith(key),r['name'].casefold()))


def _change_page(offset):
    import streamlit as st
    st.session_state['surgery_page'] += offset


def run():
    import streamlit as st
    from modules.shared.ui_components import page_header

    page_header('고객 전달자료', '수술명·수술종별 검색',
                '수술명으로 찾고, 두 가지 종별 분류를 함께 확인하세요.', '🔎')
    st.markdown(RESULT_CSS, unsafe_allow_html=True)
    with st.container(key='surgery_search_box'):
        query = st.text_input('수술명 검색', placeholder='수술명 또는 영문명 검색',
                              key='surgery_query', label_visibility='collapsed')
    if st.session_state.get('surgery_context') != query:
        st.session_state['surgery_page'] = 1
        st.session_state['surgery_context'] = query
    if not normalize(query):
        st.caption('찾으실 수술명을 입력해 주세요.')
        return

    rows = search(catalog()['rows'], query)
    st.caption(f'검색 결과 {len(rows):,}개')
    if not rows:
        st.info('일치하는 수술명이 없습니다. 짧은 핵심 단어나 다른 표기로 다시 검색해 보세요.')
    else:
        total_pages = max(1, (len(rows) + 49) // 50)
        page = min(max(1, st.session_state.get('surgery_page', 1)), total_pages)
        st.session_state['surgery_page'] = page
        start = (page - 1) * 50
        st.markdown(render_results(rows[start:start + 50]), unsafe_allow_html=True)
        if total_pages > 1:
            prev, position, next_page = st.columns([1, 2, 1])
            prev.button('이전', key='surgery_prev', disabled=page == 1,
                        on_click=_change_page, args=(-1,), use_container_width=True)
            position.caption(f'{page} / {total_pages} 페이지 · 50개씩 보기')
            next_page.button('다음', key='surgery_next', disabled=page == total_pages,
                             on_click=_change_page, args=(1,), use_container_width=True)
    st.caption('참고용 분류이며, 실제 지급 기준은 가입 상품의 약관에 따라 달라집니다.')
    with st.expander('분류 확인 시 참고사항'):
        st.write('생명보험 종 수술 참고 분류입니다. 같은 수술명도 부위·수술 방법·악성 여부에 따라 분류가 달라질 수 있습니다.')
        st.write('“비해당” 또는 검색 결과 없음이 모든 수술비 담보의 미지급을 뜻하지는 않습니다.')


