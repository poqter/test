"""Official resources with separate provenance, access and content checks."""
import streamlit as st
import pandas as pd
from .portal_repository import filter_resources
from .workspace_tools import field


def status_text(row):
    return '내용 확인 '+row['content_verified_at'] if row.get('content_verified_at') else '연결 주소 확인 '+row['link_verified_at'] if row.get('link_verified_at') else '내용 재확인 필요'


@st.dialog('자료 범위·확인 근거',width='large')
def resource_dialog(row):
    st.subheader(row['name']);st.write(row['description'])
    st.write('적용 범위: '+row['scope'])
    st.write('내용 확인일: '+(row.get('content_verified_at') or '미확인'))
    st.write('연결 주소 확인일: '+(row.get('link_verified_at') or '미확인'))
    st.write('조회 시도일: '+(row.get('access_checked_at') or '미확인'))
    st.write('조회 결과: '+row['access_status'])
    st.write(row['verification_note'])
    st.link_button('확인 근거 페이지',row['source_url'])
    st.link_button('자료 열기',row['url'])


def resource_cards(rows):
    if not rows:st.info('조건에 맞는 공식 자료가 없습니다.')
    for row in rows:
        with st.container(border=True):
            st.subheader(row['name']);st.write(row['description'])
            st.caption(row['scope']+' · '+status_text(row))
            left,right=st.columns(2)
            left.link_button('공식 자료 열기 ↗',row['url'],use_container_width=True)
            if right.button('적용 범위·확인 근거',key='f_resource_open_'+row['id'],use_container_width=True):resource_dialog(row)


def render_resources(data,mode,issues=()):
    if mode=='기준일':
        st.info('편집일·공식 연결 주소 확인·내용 확인·조회 시도는 서로 다릅니다. 조회 도구 오류를 사이트 장애로 판정하지 않습니다. 실제 로그인 성공은 검사하지 않았습니다.')
        rows=[{'자료':r['name'],'종류':r['group'],'내용 확인일':r.get('content_verified_at') or '미확인','연결 주소 확인일':r.get('link_verified_at') or '미확인','조회 시도일':r.get('access_checked_at') or '미확인','조회 결과':r['access_status'],'적용 범위':r['scope'],'공식 주소':r['url']} for r in data['resources']]
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        st.subheader('보험사 번호·전산 확인 상태')
        contacts=[{'보험사':r['name'],'번호':r['phone'],'번호 확인일':r.get('phone_verified_at') or '재확인 필요','출처':r.get('phone_source_url') or '기존 목록','전산 접속':r.get('portal_status','미검증')} for r in data['insurers']]
        st.dataframe(pd.DataFrame(contacts),hide_index=True,use_container_width=True)
        report='화랑 WORKSPACE · 포털 확인 상태\n편집일 '+data['edited_at']+'\n\n'+'\n'.join(str(r) for r in rows+contacts)
        st.download_button('확인 상태 TXT 내려받기',report.encode('utf-8-sig'),'hwarang_portal_status.txt',key='f_status_download')
        return
    query=field('text_input','기관·자료·용도 검색','f_resource_search','',max_chars=100)
    base=[r for r in data['resources'] if r['group']=='서식'] if mode=='서식' else [r for r in data['resources'] if r['group'] in ('공식기관','공공사이트')]
    if mode=='서식':
        st.info('보험사 제출서식은 해당 보험사의 최신 원본을 이용하세요. AIA 서식은 다른 보험사에 공통 적용하지 않습니다.')
        checklist='화랑 WORKSPACE 자체 작성 · 상담 준비용\n보험사 제출서식이 아닙니다.\n\n미확인: 상담 목적\n미확인: 기존 계약 조건\n미확인: 비교 단위\n미확인: 면책·감액·갱신 조건\n미확인: 추가 확인 사항\n'
        st.download_button('자체 상담 준비 체크리스트 TXT',checklist.encode('utf-8-sig'),'hwarang_consultation_checklist.txt',key='f_form_download')
    else:
        group=field('selectbox','자료 구분','f_resource_group','전체',options=['전체','공식기관','공공사이트'])
        base=filter_resources(base,group=group)
    rows=filter_resources(base,query)
    st.caption(f'자료 {len(rows)}개')
    resource_cards(rows)
