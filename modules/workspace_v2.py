"""Signature navigation and home. Only session-local preferences/history."""
import html
import streamlit as st
from .signature_theme import inject_signature_styles
from .insurer_portal import render_home_quick_search

CATEGORY_ORDER=("상담·보장·청구","계산·상품 비교","실적·수수료","교육·체크리스트","원수사·공식자료")
CATEGORY_META={name:(desc,"") for name,desc in zip(CATEGORY_ORDER,["고객 상황을 정리하고 설명자료를 준비합니다.","같은 기준과 가정으로 필요한 수치를 확인합니다.","계약자료를 확인하고 실적과 수당을 집계합니다.","용어와 상담 절차를 익히고 연습합니다.","보험사 전산과 공식 업무자료로 연결합니다."])}
inject_workspace_v2_styles=inject_signature_styles

def _category_apps(definitions, category):
    return [key for key,value in definitions.items() if value.get('group')==category]

@st.dialog('업데이트 안내',width='large')
def notice_dialog(notice):
    st.caption(notice['date']);st.subheader(notice['title'])
    for item in notice['items']: st.write('• '+item)
    st.caption('Planned & Built by 박병선 팀장')

@st.dialog('작업자료와 이용 안내')
def usage_dialog():
    st.write('자료는 서버 메모리에서 처리됩니다. 신규 도구는 DB·파일·공용 캐시에 고객정보를 저장하지 않습니다.')
    st.write('페이지 이동 중 유지되는 입력도 현재 접속 세션에 한정됩니다. 새로고침·연결 종료 후 복구를 보장하지 않습니다. 필요한 결과는 직접 내려받으세요.')
    st.write('로그아웃하면 작업 상태를 초기화합니다. 개인을 식별하는 정보는 필요한 범위로 제한하세요.')

def render_sidebar(allowed_ids,definitions,navigate,logout,notice):
    with st.sidebar:
        st.markdown('<div class="sig-brand"><span class="sig-mark">H</span><div><strong>HWARANG</strong><small>WORKSPACE · Signature</small></div></div>',unsafe_allow_html=True)
        if st.button('홈',key='v2_nav_home',use_container_width=True,type='primary' if st.session_state.get('active_app')=='home' else 'secondary'):navigate('home')
        query=st.text_input('기능 빠른 검색',placeholder='상령일, 문자, 실손…',key='sig_nav_search').strip().lower()
        for group in CATEGORY_ORDER:
            ids=[k for k in _category_apps(definitions,group) if k in allowed_ids and (not query or query in search_text(definitions[k]))]
            if not ids:continue
            with st.expander(group,expanded=bool(query) or st.session_state.get('active_app') in ids):
                for key in ids:
                    if st.button(definitions[key]['name'],key='v2_nav_'+key,type='primary' if st.session_state.get('active_app')==key else 'secondary',use_container_width=True):navigate(key)
        if query and not any(query in search_text(definitions[k]) for k in allowed_ids):st.caption('검색 결과가 없습니다.')
        st.divider()
        if st.button('이용 안내',key='sig_usage',use_container_width=True):usage_dialog()
        if st.button('최근 업데이트',key='sig_update',use_container_width=True):notice_dialog(notice)
        st.caption('접속 계정 · '+str(st.session_state.get('login_user','')))
        if st.button('로그아웃',key='v2_logout',use_container_width=True):logout()
        st.caption('Planned & Built by 박병선 팀장')

def search_text(app):return ' '.join([app['name'],app['description'],*app.get('keywords',[])]).lower()

def _tool_card(app_id,allowed_ids,definitions,icons,navigate,prefix='all'):
    app=definitions[app_id]
    with st.container(border=True,key=f'sig_card_{prefix}_{app_id}'):
        icon=icons.get(app_id,'<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h4"/></svg>')
        st.markdown(f'<div class="sig-icon">{icon}</div><div class="sig-card-title">{html.escape(app["name"])}</div><div class="sig-card-desc">{html.escape(app["description"])}</div>',unsafe_allow_html=True)
        if st.button('열기 →',key=f'v2_launch_{prefix}_{app_id}',disabled=app_id not in allowed_ids,use_container_width=True):navigate(app_id)

def render_grid(ids,allowed,definitions,icons,navigate,prefix):
    for i in range(0,len(ids),3):
        for col,app_id in zip(st.columns(3,gap='medium'),ids[i:i+3]):
            with col:_tool_card(app_id,allowed,definitions,icons,navigate,prefix)

def render_home(allowed_ids,definitions,icons,navigate,notice):
    st.markdown('<div class="sig-intro"><div class="sig-eyebrow">HWARANG WORKSPACE · SIGNATURE</div><h1>오늘의 상담을 더 명료하게.</h1><p>필요한 도구를 찾고, 다음 업무를 바로 시작하세요.</p></div>',unsafe_allow_html=True)
    if 'insurer_portal' in allowed_ids:
        with st.container(border=True):
            st.subheader('원수사 바로 검색')
            render_home_quick_search()
            st.caption('보험사명으로 검색하면 전산과 대표 연락처가 표시됩니다.')
    query=st.text_input('전체 기능 검색',key='v2_global_search',placeholder='보험나이, 상담 문자, 비교표, 청구서류…').strip().lower()
    with st.container(key='sig_home_grid'):
        if query:
            ids=[k for k in allowed_ids if query in search_text(definitions[k])]
            st.subheader(f'검색 결과 · {len(ids)}개')
            if not ids:st.info('관련 도구가 없습니다. 더 짧은 단어로 검색하세요.')
            render_grid(ids,allowed_ids,definitions,icons,navigate,'search')
        else:
            st.subheader('주요 업무')
            ids=[k for k in ('analyzer','remodeling','insurance_claim_guide','quick_calculators','consultation_helper','comparison_builder') if k in allowed_ids]
            render_grid(ids,allowed_ids,definitions,icons,navigate,'quick')
            recent=[k for k in st.session_state.get('sig_recent',[]) if k in allowed_ids][:4]
            if recent:
                st.subheader('최근 사용한 도구')
                for col,key in zip(st.columns(len(recent)),recent):
                    if col.button(definitions[key]['name'],key='sig_recent_'+key,use_container_width=True):navigate(key)
            st.subheader('전체 업무 도구')
            for group in CATEGORY_ORDER:
                ids=[k for k in _category_apps(definitions,group) if k in allowed_ids]
                if not ids:continue
                with st.expander(f'{group} · {len(ids)}',expanded=False):render_grid(ids,allowed_ids,definitions,icons,navigate,'all')
    st.divider()
    st.caption(notice['date']+' · '+notice['title'])
    if st.button('변경 내용 보기',key='sig_home_notice'):notice_dialog(notice)
    st.markdown('<div class="sig-footer">HWARANG WORKSPACE · Test Server<br>Planned &amp; Built by 박병선 팀장</div>',unsafe_allow_html=True)
