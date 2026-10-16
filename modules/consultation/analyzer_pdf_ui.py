"""Optional review for KB PDF only. Existing XLSX UI is unaffected."""
import copy
import json
import math
import re


def apply_review(data, name, age, edited):
    result=copy.deepcopy(data)
    if not name.strip() or len(name.strip()) > 80 or name.strip()[0] in '=+-@':
        raise ValueError('고객명을 확인해 주세요.')
    result['customer_name']=name.strip()
    result['age']=str(int(age))
    if len(edited)!=len(result['coverages']):
        raise ValueError('검토표의 행 수가 변경되었습니다.')
    for row,item in zip(edited,result['coverages']):
        for index in range(len(result['contracts'])):
            text=str(row[f'{index+1}번']).strip().replace(',','')
            if text=='확인 필요':
                item['values'][index]=text
                continue
            if not re.fullmatch(r'\d+(?:\.\d{1,6})?',text):
                raise ValueError('보장금액은 0 이상의 숫자 또는 확인 필요로 입력하세요. 단위는 만원입니다.')
            number=float(text)
            if not math.isfinite(number) or number>1_000_000_000:
                raise ValueError('보장금액 범위를 확인하세요.')
            item['values'][index]=int(number) if number.is_integer() else number
    result['reviewed']=True
    return result


def render_pdf_review(data, token, basic_only=True):
    import streamlit as st
    token += "_39" if basic_only else "_all"
    if basic_only:
        from modules.consultation.analyzer_model import DEFAULT_COVERAGES
        data=copy.deepcopy(data)
        data['coverages']=[r for r in data['coverages'] if r['label'] in DEFAULT_COVERAGES]
    active={r['label'] for r in data['coverages']}
    relevant=[r for r in data['details'] if active.intersection(r['targets']) and r['reason']!='직접 분류']
    st.info(f"KB PDF 검토 · 조회일 {data['source_date']} · 납입 추정 기준월 {data['calculation_month']} · 계약 {len(data['contracts'])}건")
    st.caption('보장정보는 PDF 조회일 기준입니다. 납입금액은 현재 보험료가 유지된다는 가정의 추정값이며 실제 수납내역이 아닙니다.')
    name=st.text_input('고객명 확인',data['customer_name'],key='kb_name_'+token)
    age=st.number_input('PDF 기준 보험연령',min_value=0,max_value=120,value=int(data['age']),key='kb_age_'+token)
    st.dataframe([{'번호':i+1,'보험사':c['company'],'상품':c['product'],'가입일':c['start'],
                   '월보험료': '미제공' if c['premium_missing'] else f"{c['monthly']:,}원",'납입횟수(추정)':c['payment_count']}
                  for i,c in enumerate(data['contracts'])],hide_index=True,use_container_width=True)
    unmapped=[r for r in data['details'] if not r['targets']]
    st.caption(f"현재 검토 항목 {len(data['coverages'])}개 · 해당 항목의 계산·조건 확인 대상 {len(relevant)}건. 원본에 없는 항목의 0은 엑셀에서 빈칸으로 표시됩니다.")
    with st.expander('상세담보·분류 근거 및 제외 항목 확인',expanded=False):
        records=[{'계약':r['contract']+1,'PDF쪽':r['page'],'원문담보':r['raw'],'분류명':r['standard'],
                  '금액(만원)':r['value'],'출력항목':', '.join(r['targets']) or '자동 반영 제외','확인사항':r['reason']}
                 for r in data['details']]
        st.dataframe(records,hide_index=True,use_container_width=True)
        st.download_button('PDF 검토내역 저장',json.dumps(records,ensure_ascii=False,indent=2).encode('utf-8'),
                           file_name='KB_PDF_review.json',mime='application/json',key='kb_detail_'+token)
    rows=[{'보장항목':item['display'],**{f'{i+1}번':str(v) for i,v in enumerate(item['values'])}}
          for item in data['coverages']]
    with st.expander('보장금액 확인 및 수정 (만원)',expanded=False):
        st.caption('계약 번호별 금액입니다. 확인 필요는 원문을 확인한 뒤 숫자로 바꿀 수 있습니다. 남겨두면 엑셀에도 확인 필요로 표시됩니다. 종수술 합계는 1회 지급액이 아닙니다.')
        edited=st.data_editor(rows,disabled=['보장항목'],hide_index=True,use_container_width=True,
                              num_rows='fixed',key='kb_editor_'+token)
    try:
        reviewed=apply_review(data,name,age,edited)
    except ValueError as exc:
        st.error(str(exc))
        return data,False
    return reviewed,True
