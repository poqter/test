"""F35–40. Official links; verification status is explicit, never fabricated."""
import streamlit as st
import pandas as pd

RESOURCES = [
    ('공식기관','생명보험협회','https://www.klia.or.kr/','보험 공시·소비자 안내','2026-09-21'),
    ('공식기관','손해보험협회','https://www.knia.or.kr/','손해보험 정보·소비자 안내','재확인 필요'),
    ('공식기관','금융감독원','https://www.fss.or.kr/','금융소비자 정보·민원','재확인 필요'),
    ('공공사이트','국민건강보험','https://www.nhis.or.kr/nhis/index.do','건강보험 제도·민원','2026-09-21'),
    ('공공사이트','내보험찾아줌','https://cont.insure.or.kr/','생명보험협회에서 연결하는 보험조회 서비스','2026-09-21 · 협회 링크 확인'),
    ('공공사이트','보험다모아','https://www.e-insmarket.or.kr/','생명보험협회에서 연결하는 보험상품 비교','2026-09-21 · 협회 링크 확인'),
    ('서식','AIA 보험금 청구서·위임장·치아 진료확인서','https://www.aia.co.kr/ko/customer-support/customer-guide/forms/claims.html','해당 보험사 공식 최신 서식 다운로드','2026-09-21'),
    ('청구·보상','현대해상 청구·보상 안내','https://www.hi.co.kr/','공식 홈페이지의 보험금 청구·보상 메뉴','2026-09-21'),
    ('청구·보상','KB손해보험 청구 안내','https://www.kbinsure.co.kr/CG205010001.ec','접수 방법·청구 절차·구비서류','2026-09-21'),
]

@st.dialog('연락처와 업무 안내')
def contact_dialog(name, phone):
    st.subheader(name)
    st.write('대표 콜센터: '+(phone or '등록된 번호 없음'))
    st.code(phone or '공식 홈페이지에서 확인',language=None)
    st.write('대표센터에서 사고 유형에 맞는 보상 담당 부서 연결을 요청하세요. 지역별 보상센터 직통번호는 별도 등록하지 않았습니다.')
    st.caption('번호 출처: 기존 포털 목록. 현대해상은 2026-09-21 공식 홈페이지 재확인, 그 외 번호는 이번 개편에서 재확인하지 않았습니다.')

def render_resources(insurers, phones):
    mode=st.radio('업무 자료 선택',['전산 접속','연락처·보상','공식기관·공공자료','서식','기준일'],horizontal=True,key='f_mode')
    if mode=='전산 접속': return False
    if mode=='연락처·보상':
        query=st.text_input('보험사 이름 찾기',key='f_contact_search').strip().lower()
        matches=[i for i in insurers if query in i['name'].lower()]
        if not matches: st.info('일치하는 보험사가 없습니다.')
        for insurer in matches:
            name=insurer['name']; phone=phones.get(name,'')
            with st.container(border=True):
                st.write(f'**{name}** · {phone or "공식 안내 확인"}')
                if st.button('연락처 상세',key='f_phone_'+insurer['slug']): contact_dialog(name,phone)
                st.link_button('원수사 업무 전산',insurer['url'])
        st.subheader('청구·보상 공식 안내')
        chosen=[r for r in RESOURCES if r[0]=='청구·보상']
    elif mode=='서식':
        st.info('보험사 제출서식은 해당 보험사의 최신 원본을 사용합니다. 아래 서식은 AIA용이며 다른 보험사에 공통 적용하지 않습니다.')
        chosen=[r for r in RESOURCES if r[0]=='서식']
        checklist='상담자료 준비 체크리스트\n[ ] 상담 목적 정리\n[ ] 기존 계약 조건 확인\n[ ] 비교 단위 확인\n[ ] 면책·감액·갱신 조건 확인\n[ ] 추가 확인 사항 정리\n'
        st.download_button('공통 상담 준비 서식 (.txt)',checklist.encode('utf-8-sig'),'hwarang_consultation_checklist.txt',key='f_form_download')
    elif mode=='기준일':
        st.caption('확인일은 편집 시 검토한 날짜이며 자동 갱신되지 않습니다. 전산 접속·로그인 성공을 보증하는 날짜가 아닙니다.')
        st.dataframe(pd.DataFrame(RESOURCES,columns=['종류','자료','공식 주소','용도','확인 상태']),hide_index=True,use_container_width=True)
        st.info('기존 27개 보험사 영업전산 링크는 원본 목록을 유지했습니다. 로그인이 필요한 접속·보안프로그램은 테스트 서버 환경에서 별도 확인이 필요합니다.')
        return True
    else:
        query=st.text_input('기관·자료 검색',key='f_resource_search').strip()
        chosen=[r for r in RESOURCES if r[0] in ('공식기관','공공사이트') and (query in r[1] or query in r[3])]
    for kind,name,url,desc,checked in chosen:
        with st.container(border=True):
            st.link_button(name,url,use_container_width=True)
            st.write(desc)
            st.caption('확인 상태 · '+checked)
    return True
