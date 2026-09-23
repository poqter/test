"""Shared home search and readable insurer workspace, backed by one catalog."""
import html
import streamlit as st
from .portal_repository import load_catalog,filter_insurers,safe_url
from .workspace_tools import field,session_notice
from .ui_components import page_header


def _clear_home_search():st.session_state['home_insurer_search']=''


def render_home_quick_search():
    data,issues=load_catalog()
    left,right=st.columns([10,1])
    query=left.text_input('보험사 검색',placeholder='보험사·별칭·대표번호 검색',key='home_insurer_search',label_visibility='collapsed').strip()
    if query:right.button('×',key='clear_home_insurer_search',on_click=_clear_home_search,help='검색어 지우기')
    if issues:st.caption('일부 포털 항목을 확인해야 합니다. 포털의 기준일 화면을 참고하세요.')
    if not query:return
    rows=filter_insurers(data['insurers'],query)
    st.markdown('''<style>.ip-home-result{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#fff;border:1px solid #d9dce3;border-radius:14px;padding:14px 16px;margin:8px 0;flex-wrap:wrap}.ip-home-result a{color:#17233c!important;font-size:1.05rem;font-weight:700;text-decoration:none}.ip-home-result span{font-size:1rem;color:#465266}.ip-home-result small{display:block;font-size:.9rem;color:#666}</style>''',unsafe_allow_html=True)
    if not rows:st.info('일치하는 보험사가 없습니다. 이름·별칭·번호로 다시 검색해 주세요.')
    for row in rows[:6]:
        name=html.escape(row['name']);url=html.escape(safe_url(row['url']),quote=True)
        phone=html.escape(row['phone'] or '기본 포털')
        status='번호 확인 '+row['phone_verified_at'] if row.get('phone_verified_at') else '번호 재확인 필요' if row['phone'] else '접속 미검증'
        if row.get('notice'):status+=' · 전산 주소 재확인 필요'
        st.markdown(f'<div class="ip-home-result"><a href="{url}" target="_blank" rel="noopener noreferrer">{name} ↗</a><span>{phone}<small>{html.escape(status)}</small></span></div>',unsafe_allow_html=True)
    if len(rows)>6:st.caption(f'검색 결과 {len(rows)}개 중 6개 표시 · 전체 결과는 원수사·공식자료 포털에서 확인하세요.')


def remember_detail(slug):
    recent=st.session_state.get('f_recent_details',[])
    st.session_state['f_recent_details']=[slug,*[v for v in recent if v!=slug]][:5]


@st.dialog('연락처·접속 상세',width='large')
def contact_dialog(row):
    st.subheader(row['name'])
    st.write('대표·상담 번호: '+(row['phone'] or '등록 없음'))
    if row['phone']:st.code(row['phone'],language=None)
    st.caption('번호를 복사해 사용하세요. 보상센터 직통번호나 통화 연결 성공을 확인한 것은 아닙니다.')
    st.write('번호 확인일: '+(row.get('phone_verified_at') or '재확인 필요'))
    if row.get('phone_source_url'):st.link_button('번호 확인 출처',row['phone_source_url'])
    st.write(row.get('note',''))
    st.caption('영업전산 로그인·보안 프로그램 호환성은 별도 확인이 필요합니다.')
    st.link_button('원수사 업무 전산 열기',row['url'],use_container_width=True)
    st.code(row['url'],language=None)


def insurer_cards(rows,contacts=False):
    if not rows:st.info('검색·분류·즐겨찾기 조건에 맞는 항목이 없습니다.')
    for index,row in enumerate(rows):
        with st.container(border=True):
            st.subheader(row['name'])
            st.caption(row['group']+' · '+('번호 확인 '+row['phone_verified_at'] if row.get('phone_verified_at') else '번호 재확인 필요' if row['phone'] else '대표번호 미등록'))
            if row['phone']:st.write('대표·상담 '+row['phone'])
            if row.get('notice'):st.warning(row['note'])
            elif row.get('edge_only'):st.caption(row['note'])
            buttons=st.columns(2)
            buttons[0].link_button('전산 열기 ↗',row['url'],use_container_width=True)
            if buttons[1].button('연락처·접속 상세',key='f_detail_open_'+row['slug'],use_container_width=True):
                remember_detail(row['slug']);contact_dialog(row)
            field('checkbox','즐겨찾기','f_favorite_'+row['slug'],False)


def run():
    data,issues=load_catalog()
    page_header('업무 지원','원수사·공식자료 포털','보험사 검색부터 연락처·서식·공식 자료까지 필요한 업무로 바로 이동합니다.', 'IP')
    session_notice('f_')
    st.caption(f"포털 개편 7단계 · 편집일 {data['edited_at']} · 전산 27개와 기본 포털을 이관한 목록입니다.")
    for issue in issues:st.warning(issue)
    mode=st.radio('업무 자료 선택',['전산 접속','연락처·보상','공식기관·공공자료','서식','즐겨찾기','기준일'],horizontal=True,key='f_mode')
    if mode in ('공식기관·공공자료','서식','기준일'):
        from .official_resources import render_resources
        render_resources(data,mode,issues)
        return
    query=field('text_input','보험사·별칭·대표번호 검색','f_search','',max_chars=100)
    group=field('selectbox','보험사 구분','f_group','전체',options=['전체','기본 포털','생명보험','손해보험'])
    rows=filter_insurers(data['insurers'],query,group)
    if mode=='즐겨찾기':rows=[r for r in rows if st.session_state.get('f_favorite_'+r['slug'],False)]
    st.caption(f'검색 결과 {len(rows)}개 · 즐겨찾기는 현재 세션에서만 유지됩니다.')
    recent=st.session_state.get('f_recent_details',[])
    names={r['slug']:r['name'] for r in data['insurers']}
    if recent:st.caption('최근 상세 확인: '+' · '.join(names[s] for s in recent if s in names))
    insurer_cards(rows,contacts=mode=='연락처·보상')
    if mode=='연락처·보상':
        from .official_resources import resource_cards
        st.subheader('청구·보상 공식 안내')
        resource_cards([r for r in data['resources'] if r['group']=='청구·보상'])
    st.caption('링크 열기와 실제 로그인 성공은 다릅니다. 계정·비밀번호는 이 도구에 입력하거나 저장하지 않습니다.')
