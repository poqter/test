"""Unified estate input, snapshot and customer reports."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import streamlit as st
from modules.calculators.tax.estate_calculator import NAME,FIELDS,calculate
from modules.calculators.input_design import number_input
from modules.calculators.tax.estate_reports import money,metrics,headline,summary_rows,pdf_report,excel_report
from modules.shared.runtime_cache import cached, digest_bytes

GROUPS=[
 ('expenses','채무·장례비 등이 있습니다',[4,5,6,7]),
 ('financial','금융재산이 포함되어 있습니다',[20,21]),
 ('gifts','사전증여가 있습니다',[8,9,19,26,28]),
 ('personal','추가 인적공제를 확인합니다',[11,12,13]),
 ('deductions','주택·기타 공제를 적용합니다',[22,23,27,29]),
 ('special','특수한 상속 조건이 있습니다',[2,3,24,25,32,33,34]),
 ('business','가업·비상장주식이 관련됩니다',[35,36,37,38]),
]

def run():
    st.subheader('상속세·납부재원 계산기')
    st.caption('기본 조건 → 해당하는 추가 조건 → 납부재원 → 계산 결과')
    # Keep hidden optional input drafts across widget cleanup; inactive groups contribute defaults only.
    for key in list(st.session_state):
        if key.startswith('cov_'+NAME+'_') or key.startswith('estate_group_') or key in ('estate_cash_manwon_int','estate_insurance_manwon_int','estate_other_manwon_int','estate_note','estate_alias','estate_alignment','estate_funding_known'):
            st.session_state[key]=st.session_state[key]
    entries=FIELDS[NAME]
    values=[x[1] for x in entries]
    if st.session_state.get('estate_transfer_open'):
        st.session_state['estate_group_business']=True
        st.session_state.pop('estate_transfer_open')
    def field(i):
        label,default,unit,options=entries[i];key=f'cov_{NAME}_{i}'
        if unit=='선택':v=st.selectbox(label,options,index=options.index(default),key=key)
        elif unit=='날짜':v=st.date_input(label,value=date.fromisoformat(default),min_value=date(2026,1,1),max_value=date(2026,12,31),key=key)
        else:v=number_input(f'{label} ({unit})',min_value=0,max_value=options,value=default,step=10000 if unit=='원' else 1,key=key)
        values[i]=v
        return v
    st.markdown('**① 기본 재산·가족 구성**')
    cols=st.columns(2)
    with cols[0]:field(0);field(1)
    with cols[1]:field(14);field(10)
    # Gross belongs to basic; deemed/excluded are additional fields (indices 2,3).
    if values[14]=='예':
        c1,c2=st.columns(2)
        with c1:field(15)
        with c2:
            if values[15]!='배우자 단독':field(16)
            else:values[16]=0;values[10]=0
        field(17)
        if values[17]>=500000000:field(18)
    else:
        values[15]='직계비속';values[16]=values[10];values[17]=0;values[18]='아니요';values[19]=0
    st.markdown('**② 해당 사항 선택**')
    st.caption('선택한 항목만 계산에 반영합니다. 해제한 항목의 작성값은 보관됩니다.')
    for slug,label,indices in GROUPS:
        active=st.checkbox(label,key='estate_group_'+slug)
        if active:
            with st.expander('입력 · '+label,expanded=True):
                for i in indices:
                    if i==19 and values[14]!='예':continue
                    field(i)
                filled=[f'{entries[i][0]}: {money(values[i]) if entries[i][2]=="원" else values[i]}' for i in indices if values[i] not in (0,'아니요')]
            if filled:st.caption(' / '.join(filled))
    st.markdown('**③ 납부재원**')
    known=st.checkbox('납부재원을 입력하겠습니다',key='estate_funding_known')
    funding=None
    if known:
        c=st.columns(3);amounts=[]
        for col,key,label in zip(c,['cash','insurance','other'],['즉시 사용 가능한 현금·예금','납부에 사용할 사망보험금','기타 사용 가능한 자금']):
            with col:amounts.append(number_input(label+' (원)',min_value=0,max_value=10**12,value=0,step=10000,key='estate_'+key))
        funding=tuple(amounts)
        st.caption('사망보험금을 납부재원에 입력해도 과세재산에는 자동 합산하지 않습니다. 과세 대상 보험금은 위 추가 조건의 추정·간주재산에 포함해 주세요.')
    values[31]=sum(funding) if funding is not None else 0
    st.markdown('**이번 계산에 적용되는 조건**')
    field(30)
    conditions=[('상속개시일',str(values[0])),('총재산',money(values[1]+values[2]+values[35])),('배우자',values[14]),('자녀',str(values[10])+'명'),('공제 방식','기초·인적공제' if values[14]=='예' and values[15]=='배우자 단독' else '일괄·인적공제 비교'),('장례비 반영액',money(min(max(values[6],5000000),10000000)+min(values[7],5000000))),('신고세액공제',values[30])]
    st.caption(' · '.join(f'{a}: {b}' for a,b in conditions))
    signature=(tuple(values),funding)
    if st.button('계산하기',type='primary',key='estate_calculate'):
        try:
            result=calculate(NAME,values)
            st.session_state['estate_snapshot']=(signature,result,conditions,datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M'))
        except ValueError as exc:st.session_state.pop('estate_snapshot',None);st.error(str(exc))
    stored=st.session_state.get('estate_snapshot')
    if not stored:return
    if stored[0]!=signature:st.info('입력 조건이 변경되었습니다. 다시 계산하면 결과와 다운로드가 표시됩니다.');return
    _,result,conditions,stamp=stored
    st.divider();st.subheader('✨ 상속세·납부재원 결과')
    from modules.calculators.input_design import render_metrics
    from modules.calculators.visuals import primary_result_labels
    render_metrics(dict(metrics(result,funding)), 'estate', primary_result_labels("상속세계산기"))
    st.info(headline(result,funding))
    if funding is not None:st.table([{'납부재원':a,'금액':money(b)} for a,b in zip(['현금·예금','사망보험금','기타 자금','합계'],(*funding,sum(funding)))])
    st.markdown('**세액 계산 요약**');st.table([{'계산 단계':a,'금액':b} for a,b in summary_rows(result)])
    inputs=[(label+' ('+unit+')' if unit not in ('날짜','선택') else label,value) for (label,_,unit,_),value in zip(entries,values)]
    with st.expander('공제·계산 내역 자세히 보기'):
        st.table([{'항목':r['항목'],'금액':money(r['금액'])} for r in result.rows]);st.table([{'입력 항목':a,'값':str(b)} for a,b in inputs])
        for line in result.assumptions:st.caption(line)
    st.markdown('**고객에게 전할 설명 · 선택**')
    st.caption('설명은 계산을 다시 해도 유지됩니다. 금액과 조건을 바꿨다면 문구도 함께 확인해 주세요.')
    alias=st.text_input('고객 구분명 · 선택',key='estate_alias',max_chars=60)
    if st.button('현재 결과로 설명 작성',key='estate_explain'):
        if st.session_state.get('estate_note','').strip():st.session_state['estate_replace_note']=True
        else:st.session_state['estate_note']=headline(result,funding)
    if st.session_state.get('estate_replace_note'):
        st.info('작성 중인 설명을 현재 결과의 문구로 바꿀까요?')
        c1,c2=st.columns(2)
        if c1.button('설명 바꾸기',key='estate_confirm_note'):st.session_state['estate_note']=headline(result,funding);st.session_state['estate_replace_note']=False
        if c2.button('기존 설명 유지',key='estate_cancel_note'):st.session_state['estate_replace_note']=False
    align=st.radio('설명 정렬',['왼쪽','가운데','오른쪽'],horizontal=True,key='estate_alignment')
    css={'왼쪽':'left','가운데':'center','오른쪽':'right'}[align]
    st.markdown(f'<style>.st-key-estate_note textarea {{text-align:{css};}}</style>',unsafe_allow_html=True)
    note=st.text_area('고객에게 전할 설명',key='estate_note',height=150,max_chars=10000)
    from pypdf import PdfReader
    pdf=pdf_report(result,conditions,funding,stamp,alias,note,align)
    pages=cached("meta:estate:pdf_pages",digest_bytes(pdf),lambda:len(PdfReader(BytesIO(pdf)).pages))
    if pages>1:st.warning(f'현재 PDF는 {pages}장입니다. 설명을 줄이면 분량을 줄일 수 있으며, 그대로 다운로드할 수도 있습니다.')
    c1,c2=st.columns(2)
    c1.download_button('고객용 PDF 다운로드',pdf,'상속세_납부재원_요약.pdf','application/pdf',key='estate_pdf')
    c2.download_button('상세 엑셀 다운로드',excel_report(result,inputs,conditions,funding,stamp,note),'상속세_상세보고서.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='estate_excel')
