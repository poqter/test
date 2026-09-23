"""UI-only guidance for preserved business tools. No business calculations."""
import streamlit as st
from .app_registry import APP_BY_ID

# Describes the existing implementation, not newly verified law or product terms.
WORKFLOWS = {
 'analyzer': ('원본 자료 → 보장 항목 검토 → 분석·제안서 출력', '전체 보장내용이 포함된 컨설팅보장분석.xlsx를 준비하세요.', ['계약별 보장과 금액을 원본과 대조', '출력할 항목과 순서 확인', '분석·제안서의 인쇄 영역 확인'], '인식된 값은 원본 증권과 대조하세요. 분석 결과가 보장 확정을 의미하지 않습니다.', ['remodeling','comparison_builder']),
 'remodeling': ('기존 계약 정리 → 신규안 입력 → 변경안 출력', '유지·감액·해지할 계약과 신규안의 월 보험료·납입기간을 준비하세요.', ['유지·변경·해지 구분 확인', '신규안 보험료와 납입기간 확인', '보장 공백과 인수 조건 확인'], '유지보험료와 신규보험료를 구분해 비교합니다. 해지·가입 결정 전 개별 조건을 확인하세요.', ['analyzer','comparison_builder']),
 'deposit_vs_shortpay': ('조건 입력 → 같은 기간 비교 → 결과 검토', '월 납입액, 적금 금리와 단기납 환급 조건을 준비하세요.', ['금리와 환급률의 기준 확인', '세전·세후 및 비교 기간 확인', '중도해지 조건 별도 확인'], '기존 10년 비교 산식을 유지합니다. 예시 결과를 확정 수익이나 동일한 상품 특성으로 해석하지 마세요.', ['quick_calculators','comparison_builder']),
 'renewal_vs_nonrenewal': ('보험료 입력 → 갱신 가정 설정 → 기간별 비교', '현재 보험료, 갱신 주기와 비교할 기간을 준비하세요.', ['갱신 가정과 직접입력 값 확인', '동일 보장·납입기간 여부 확인', '마지막 구간의 비교 기간 확인'], '갱신 보험료는 입력한 가정에 따른 시나리오이며 실제 갱신 금액의 예측 보장이 아닙니다.', ['quick_calculators','comparison_builder']),
 'inheritance_tax': ('재산·조건 입력 → 예상 세액 확인 → 재원 검토', '재산과 채무·공제 등 화면에서 요구하는 조건을 준비하세요.', ['입력 금액 단위 확인', '화면의 공제·가정 확인', '미반영 재산·조건 별도 확인'], '기존 계산 규칙을 유지한 검토용 추정치입니다. 이번 UX 개편은 최신 세법 검증이나 신고세액 확정이 아닙니다.', ['quick_calculators','insurer_portal']),
 'insurance_claim_guide': ('청구 항목 선택 → 서류·담보 검토 → 안내서 출력', '청구할 항목을 선택하고 필요한 경우 보장분석 PDF를 준비하세요.', ['자동 추출 담보를 원본과 대조', '고객에게 해당하는 서류만 선택', '보험사별 추가서류와 접수 조건 확인'], '서류 안내와 담보 매칭은 보험금 지급 확정이 아닙니다. 공식 서식은 원수사 포털에서 확인하세요.', ['insurer_portal','customer_materials']),
 'silson_generation_comparison': ('가입 조건 입력 → 예시 비교 → 차이 설명', '현재 실손의 세대·보험료와 비교할 진료비 예시를 준비하세요.', ['현재 가입 세대·특약 확인', '급여·비급여와 예시 단위 확인', '약관·시행 기준 별도 대조'], '현재 코드의 세대별 가정을 유지합니다. 제도 최신성 검증이 완료된 자료로 표시하지 않으며 가입 약관과 대조해야 합니다.', ['insurance_claim_guide','comparison_builder']),
 'convention': ('계약 업로드 → 보류·제외 검토 → 환산 결과', '해당 기간의 컨벤션 계산용 계약 Excel을 준비하세요.', ['확인 필요 계약 수정', '제외된 계약 사유 확인', '목표 기준과 환산 합계 확인'], '컨벤션의 기존 환산·인정 규칙을 사용합니다. 다른 실적 도구의 기준과 혼합하지 마세요.', ['summer','manager_results']),
 'summer': ('계약 업로드 → 월별 인정 검토 → 등급 확인', '7·8월 계약과 계속보험료·납입기간·쉐어 조건을 준비하세요.', ['7월·8월 조건 각각 확인', '계속보험료 공란·0원과 보류 확인', '쉐어 조정·치아보험·보너스 확인'], '기존 월별 충족 조건과 보너스·등급 규칙을 유지합니다. 제외·보류 계약을 먼저 검토하세요.', ['convention','manager_results']),
 'manager_results': ('계약 업로드 → 수금자 선택 → 환산·합계 검토', '계약 목록 Excel과 집계할 수금자를 준비하세요.', ['선택한 수금자 범위 확인', '계약 상태·제외 사유 확인', '개별 환산과 지점 합계 대조'], '매니저 업적 환산의 기존 규칙을 사용합니다. 다른 시책 결과와 동일하다고 가정하지 마세요.', ['convention','summer']),
 'commission_calculator': ('요율표 준비 → 계약 매칭 → 지급률·결과 검토', '생보·손보 수수료 예시표와 필요한 경우 보유계약 파일을 준비하세요.', ['요율표 기준월과 계약 기준 확인', '미매칭·수동 매칭·제외 계약 확인', '지급률과 최종 금액 확인'], '표의 조건과 수동 선택에 따른 추정 결과입니다. 요율표를 교체한 뒤에는 매칭과 지급률을 다시 확인하세요.', ['manager_results','convention']),
}


@st.dialog('업무 준비·검토 안내', width='large')
def help_dialog(page):
    flow, preparation, checks, caution, related = WORKFLOWS[page]
    st.subheader(APP_BY_ID[page].label)
    st.write(preparation)
    st.write(caution)
    st.caption('계산 기준: 기존 업무 코드 유지 · 안내 개편: 8단계 · 제도·약관 최신성 확인일이 아닙니다.')


def render_workflow(page):
    if page not in WORKFLOWS:
        return
    flow, preparation, checks, caution, related = WORKFLOWS[page]
    with st.container(border=True):
        st.caption('업무 화면 개편 10단계')
        st.markdown('**'+flow+'**')
        st.write(preparation)
        if st.button('준비사항·계산 기준 보기', key='ux8_help_'+page):
            help_dialog(page)
        with st.expander('결과를 사용하기 전 확인할 항목'):
            st.caption('검토 안내입니다. 체크 여부를 저장하거나 검토 완료를 자동 판정하지 않습니다.')
            for check in checks:
                st.markdown('- '+check)
            st.info(caution)
        from .navigation import allowed_ids, navigate
        allowed = allowed_ids(st.session_state.get('login_user'))
        targets = [p for p in related if p in allowed]
        if targets:
            with st.expander('관련 도구로 이동'):
                st.caption('다른 도구로 이동합니다. 업로드 파일과 계산 결과는 자동 전달하지 않습니다.')
                for target in targets:
                    if st.button(APP_BY_ID[target].label, key='ux8_go_'+page+'_'+target, use_container_width=True):
                        navigate(target)
