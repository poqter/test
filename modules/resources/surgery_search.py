"""Local reference lookup; never infer surgery classes from partial matches."""
from functools import lru_cache
from pathlib import Path
import json
import re
import unicodedata


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



def _set_query(value):
    import streamlit as st
    st.session_state['surgery_query'] = value
    st.session_state['surgery_page'] = 1


def _reset_search():
    import streamlit as st
    _set_query('')
    st.session_state['surgery_class3'] = '전체'
    st.session_state['surgery_class5'] = '전체'


def _change_page(offset):
    import streamlit as st
    st.session_state['surgery_page'] += offset


def run():
    import streamlit as st
    from modules.shared.ui_components import page_header

    page_header('고객 전달자료', '수술명·수술종별 검색',
                '수술명으로 찾고, 두 가지 종별 분류를 한눈에 비교하세요.', '🔎')
    data = catalog()
    with st.container(border=True):
        query = st.text_input('어떤 수술을 찾으시나요?',
                              placeholder='수술명 또는 영문명을 입력하세요', key='surgery_query')
        st.caption('빠른 검색')
        st.pills('빠른 검색', ['백내장', '용종', '골절', '관상동맥'],
                 key='surgery_quick', label_visibility='collapsed',
                 on_change=_quick_search)
        left, right = st.columns(2)
        c3 = left.selectbox('1~3종 분류', ['전체', '1종', '2종', '3종', '비해당'], key='surgery_class3')
        c5 = right.selectbox('1~5종 분류', ['전체', '1종', '2종', '3종', '4종', '5종', '비해당'], key='surgery_class5')
        st.button('검색 초기화', on_click=_reset_search, key='surgery_reset', type='tertiary')

    # A quick search callback runs before this render, so query and filters stay in sync.
    rows = search(data['rows'], query, c3, c5)
    context = (query, c3, c5)
    if st.session_state.get('surgery_context') != context:
        st.session_state['surgery_page'] = 1
        st.session_state['surgery_context'] = context
    total_pages = max(1, (len(rows) + 49) // 50)
    page = min(max(1, st.session_state.get('surgery_page', 1)), total_pages)
    st.session_state['surgery_page'] = page
    st.markdown(f"### 검색 결과 · {len(rows):,}개")
    if not rows:
        st.info('일치하는 수술명이 없습니다. 짧은 핵심 단어나 다른 표기로 다시 검색해 보세요.')
    else:
        start = (page - 1) * 50
        end = min(start + 50, len(rows))
        st.caption(f"전체 {len(data['rows']):,}개 중 검색 · {start + 1:,}–{end:,}번째 결과")
        st.dataframe(
            [{'수술명': r['name'], '1~3종': r['class3'], '1~5종': r['class5']} for r in rows[start:end]],
            hide_index=True, width='stretch', height=min(600, 38 + (end - start) * 35),
            row_height=35,
            column_config={'수술명': st.column_config.TextColumn(width='large'),
                           '1~3종': st.column_config.TextColumn(width='small'),
                           '1~5종': st.column_config.TextColumn(width='small')},
        )
        if total_pages > 1:
            prev, position, next_page = st.columns([1, 2, 1])
            prev.button('이전', key='surgery_prev', disabled=page == 1,
                        on_click=_change_page, args=(-1,), use_container_width=True)
            position.caption(f'{page} / {total_pages} 페이지 · 50개씩 보기')
            next_page.button('다음', key='surgery_next', disabled=page == total_pages,
                             on_click=_change_page, args=(1,), use_container_width=True)
    st.caption('생명보험 종 수술 참고 분류 · 실제 지급 기준은 가입 상품의 약관에 따라 달라집니다.')
    with st.expander('분류 확인 시 참고사항'):
        st.write('같은 수술명도 부위·수술 방법·악성 여부에 따라 분류가 달라질 수 있습니다.')
        st.write('“비해당” 또는 검색 결과 없음이 모든 수술비 담보의 미지급을 뜻하지는 않습니다.')


def _quick_search():
    import streamlit as st
    value = st.session_state.get('surgery_quick')
    if value:
        _set_query(value)
    st.session_state['surgery_quick'] = None
