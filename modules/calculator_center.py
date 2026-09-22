"""Thirteen calculation modes, explicit computation and reviewed exports."""
from datetime import date
from decimal import Decimal
import streamlit as st
from .calculator_catalog import MODES
from .calculator_core import calculate
from .calculator_exports import formatted_results, export_bytes
from .consultation_documents import fingerprint
from .session_store import save_result, input_revision
from .ui_components import page_header
from .workspace_tools import field, session_notice


@st.dialog('계산 가정과 입력 단위', width='large')
def assumptions_dialog(formula, assumptions):
    st.subheader('계산 근거')
    st.write(formula)
    st.subheader('가정과 미반영 조건')
    st.write(assumptions)
    st.caption('금액 입력은 만원, 결과는 원 단위로 표시합니다. 수익률·물가율은 사용자 시나리오입니다.')


def run():
    page_header('재무·보험 계산', '재무·보험 계산기 센터', '목적 선택 → 조건 입력 → 계산·검토 → 자료 내려받기', 'QC')
    session_notice('a_')
    group = st.selectbox('계산 목적', ['전체', '보험 기본', '생활과 보장', '미래 준비'], key='a_group')
    choices = [name for name,spec in MODES.items() if group == '전체' or spec[1] == group]
    if st.session_state.get('a_mode') not in choices:
        st.session_state['a_mode'] = choices[0]
    mode = st.radio('계산 선택', choices, key='a_mode', horizontal=True)
    kind, _, fields, formula, assumptions = MODES[mode]
    st.subheader(mode)
    st.caption('금액은 만원으로 입력하고 결과는 원 단위로 표시합니다. 0.01만원 = 100원. 소수 둘째 자리까지 입력하세요.')
    values, inputs = {}, []
    if kind in ('age','change'):
        birth = field('date_input', '생년월일', 'a_birth', date(1990,1,1), min_value=date(1900,1,1), max_value=date(2100,12,31))
        reference = field('date_input', '신규 가입 가정 기준일', 'a_reference', date.today(), min_value=date(1900,1,1), max_value=date(2100,12,31))
        values = {'birth':birth,'reference':reference}
        inputs = [('생년월일',birth.isoformat()),('기준일',reference.isoformat())]
    else:
        for key,label,typ,default,low,high in fields:
            if typ == 'money':
                value = field('number_input',label+' (만원)', f'a_{kind}_{key}', float(default), min_value=float(low), max_value=float(high), step=0.01, format='%.2f')
                # Quantize to the advertised input precision so hidden float digits never affect a result.
                raw = Decimal(str(value)).quantize(Decimal('.01'))
                values[key] = raw*10000
                inputs.append((label,f'{raw:,.2f}만원'))
            elif typ == 'rate':
                value = field('number_input',label, f'a_{kind}_{key}', float(default), min_value=float(low), max_value=float(high), step=.1, format='%.2f')
                raw = Decimal(str(value)).quantize(Decimal('.01'))
                values[key] = raw/100
                inputs.append((label,f'{raw}%'))
            else:
                value = field('number_input',label, f'a_{kind}_{key}', default, min_value=low,max_value=high,step=1)
                values[key]=value
                inputs.append((label,str(value)))
    st.caption(assumptions)
    if st.button('산식·가정 자세히 보기',key='a_help'):
        assumptions_dialog(formula,assumptions)
    token = fingerprint([mode,values,input_revision('quick_calculators')])
    if st.button('계산하기',key='a_calculate',type='primary',use_container_width=True):
        st.session_state.pop('a_review_token',None)
        st.session_state.pop('a_calculation',None)
        try:
            if kind in ('age','change'):
                from .quick_calculators import age_result
                age, insurance, change = age_result(values['birth'],values['reference'])
                output = {'만 나이':f'{age}세','신규 가입 보험나이':f'{insurance}세','다음 상령일':change.isoformat(),'다음 변경일까지':f"{(change-values['reference']).days}일"}
            else:
                output = calculate(kind,values)
        except ValueError as exc:
            st.warning(str(exc))
        else:
            result = {'title':mode,'values':output,'inputs':inputs,'formula':formula,'assumptions':assumptions,'prepared_on':date.today().isoformat(),'token':token}
            st.session_state['a_calculation']=result
            save_result('quick_calculators',result,rule_version='stage4.1')
    result = st.session_state.get('a_calculation')
    if not result:
        st.info('조건을 입력하고 계산하기를 눌러 주세요.')
        return
    if result['token'] != token:
        st.warning('계산 조건이 변경되었습니다. 다시 계산하면 현재 조건의 결과와 다운로드가 표시됩니다.')
        return
    st.subheader('계산 결과')
    for label,value in formatted_results(result['values']):
        with st.container(border=True):
            st.caption(label)
            st.subheader(value)
    with st.expander('이번 계산에 사용한 조건과 산식'):
        for label,value in result['inputs']: st.text(f'{label}: {value}')
        st.write(formula)
        st.write(assumptions)
    if st.button('조건·결과 확인 완료',key='a_approve'):
        st.session_state['a_review_token']=token
    if st.session_state.get('a_review_token') != token:
        st.caption('입력 조건과 결과를 확인하면 TXT·Excel·PDF 다운로드가 표시됩니다.')
        return
    for ext,label,mime in [('txt','TXT','text/plain'),('xlsx','Excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),('pdf','PDF','application/pdf')]:
        try:
            data = export_bytes(result,ext)
        except Exception:
            st.warning(f'{label} 출력을 만들지 못했습니다. 다른 형식을 이용하거나 설치 상태를 확인해 주세요.')
        else:
            st.download_button(label+' 내려받기',data,f'hwarang_calculator_{kind}.{ext}',mime,key='a_export_'+ext,use_container_width=True)
