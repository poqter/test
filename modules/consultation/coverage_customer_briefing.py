"""Add a customer briefing to the existing analyzer without changing its XLSX export."""
import streamlit as st
from modules.consultation.coverage_brief_report import briefing_pdf
from modules.consultation.coverage_comparison_data import format_coverage, format_won

def render_briefing(parsed):
    st.markdown('### 03 · 고객용 현재 보험 브리핑')
    st.caption('첨부한 보장분석 엑셀에 기재된 내용을 고객 설명용으로 정리합니다. 비어 있는 항목은 미가입으로 판단하지 않습니다.')
    if not parsed:
        return
    cols=st.columns(2)
    cols[0].metric('확인된 보험',f"{len(parsed['contracts'])}건")
    # The original parser maps missing premiums to zero. Do not assert a total if any contract shows zero.
    premiums=[p.get('monthly') for p in parsed['contracts']]
    total=sum(premiums) if premiums and all(isinstance(n,(int,float)) and n>0 for n in premiums) else None
    cols[1].metric('월 보험료',format_won(total))
    if total is None:st.caption('보험료가 0원이거나 기재가 없는 계약은 완납 여부를 확인해 주세요.')
    with st.expander('고객에게 보여줄 주요 보장 미리보기'):
        for c in parsed['coverages']:
            values=[v for v in c.get('values',[]) if isinstance(v,(int,float)) and v>0]
            if values:
                st.write(f"{c.get('display') or c['label']} : " + ' / '.join(format_coverage(v) for v in values))
        st.caption('보장 금액은 원본의 계약별 기재 금액입니다. 지급조건을 확인하세요.')
    try:
        data=briefing_pdf(parsed)
        st.download_button('고객용 브리핑 PDF 다운로드', data=data, file_name='보험_보장_브리핑.pdf', mime='application/pdf',use_container_width=True,key='analyzer_customer_brief_pdf')
    except Exception:
        st.warning('브리핑 PDF를 만들지 못했습니다. 엑셀 원본의 내용을 확인한 후 다시 시도해 주세요.')
