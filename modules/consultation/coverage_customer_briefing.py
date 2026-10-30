"""Customer briefing added alongside the existing XLSX export."""
import hashlib
import json
import streamlit as st
from modules.consultation.coverage_current_briefing import current_brief_pdf, _metric, _premium
from modules.consultation.coverage_comparison_data import format_won


def render_briefing(parsed):
    if not parsed:
        return
    st.markdown('### 03 · 고객용 보장 브리핑')
    st.caption('기존 보장분석 엑셀을 바탕으로 고객에게 현재 보험을 설명하는 자료입니다.')
    cols=st.columns(2)
    cols[0].metric('가입 보험',f"{len(parsed['contracts'])}건")
    cols[1].metric('월 보험료',format_won(_premium(parsed)))
    cards=st.columns(3)
    for col,label in zip(cards,('일반암','뇌혈관질환','허혈성심장질환')):
        col.metric(label,_metric(parsed,label))
    st.caption('보장분석표에 기재된 금액의 합계입니다. 빈 칸은 미가입으로 단정하지 않으며, 지급 조건은 원본 확인이 필요합니다.')
    kind=st.radio('브리핑 형식',('한 장 요약','자세한 브리핑'),horizontal=True,key='analyzer_brief_format')
    st.caption('한 장 요약은 상담용 핵심 정리입니다. 자세한 브리핑은 요약 뒤에 보험별·보장별 내역을 더합니다.')
    sig=hashlib.sha256(json.dumps(parsed,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()[:16]
    checked=st.checkbox('고객명, 계약과 보장금액을 원본과 대조했습니다.',key='analyzer_brief_review_'+sig)
    if not checked:
        st.info('원본과 대조한 뒤 고객용 브리핑을 내려받을 수 있습니다.')
        return
    try:
        profile=st.session_state.get('login_profile') or {}
        data=current_brief_pdf(parsed,profile=profile,detailed=kind=='자세한 브리핑')
        st.download_button('고객용 브리핑 PDF 다운로드',data=data,file_name='현재_보험_보장_브리핑.pdf',mime='application/pdf',use_container_width=True,key='analyzer_customer_brief_pdf')
    except Exception as exc:
        from modules.shared.error_reporting import record_error, user_message
        reference=record_error(exc,'analyzer.customer_briefing')
        st.warning('브리핑 PDF를 만들지 못했습니다. '+user_message(reference))
