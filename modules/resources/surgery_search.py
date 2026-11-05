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


def run():
    import streamlit as st
    from modules.shared.ui_components import page_header
    page_header('보험금 청구 참고','수술명·수술종별 검색','수술명을 검색하고 1~3종·1~5종 참고 분류를 비교합니다.','🔎')
    data=catalog()
    st.caption('생명보험 종 수술 참고 분류입니다. 지급 여부와 종별은 가입 상품의 약관·수술 방법에 따라 확인해 주세요. “비해당”은 이 참고표의 분류이며 모든 수술비 담보의 미지급을 뜻하지 않습니다.')
    query=st.text_input('수술명 검색',placeholder='예: 백내장, 용종, 관상동맥, OR/IF',key='surgery_query')
    left,right=st.columns(2)
    c3=left.selectbox('1~3종 분류',['전체','1종','2종','3종','비해당'],key='surgery_class3')
    c5=right.selectbox('1~5종 분류',['전체','1종','2종','3종','4종','5종','비해당'],key='surgery_class5')
    rows=search(data['rows'],query,c3,c5)
    context=(query,c3,c5)
    if st.session_state.get('surgery_context')!=context:
        st.session_state['surgery_page']=1
        st.session_state['surgery_context']=context
    st.caption(f"검색 결과 {len(rows):,}개 · 전체 {len(data['rows']):,}개")
    if not rows:
        st.info('일치하는 수술명이 없습니다. 핵심 단어나 다른 표기로 검색해 주세요. 검색되지 않았다는 이유로 보장 대상이 아니라고 판단할 수는 없습니다.')
    else:
        page=st.number_input('결과 페이지',min_value=1,max_value=max(1,(len(rows)+49)//50),step=1,key='surgery_page')
        st.dataframe([{'수술명':r['name'],'1~3종':r['class3'],'1~5종':r['class5']} for r in rows[(page-1)*50:page*50]],hide_index=True,width='stretch',column_config={'수술명':st.column_config.TextColumn(width='large')})
        st.caption('동일하거나 비슷한 이름이라도 부위·관혈/내시경·악성 여부 등의 조건까지 대조하세요.')
    st.caption(f"출처: {data['source_name']} · 원문 표시 업데이트 {data['source_updated_on']} · 수집 확인 {data['retrieved_on']}")
    st.link_button('출처 원문 확인',data['source_url'])
