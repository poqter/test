import csv
import io
from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from modules.calculators.pension.pension_models import PensionPlan, calculate
from modules.calculators.finance.finance_calculator_ui import csv_safe

def run():
    st.caption('은퇴·연금 자금계획 · 현금흐름 및 추가 납입 세액공제 시뮬레이션')
    args={}
    labels={}
    from modules.shared.page_layouts import work_panels
    _ui_0, _ui_1 = work_panels("pension_calculator_ui")
    with _ui_0:
        st.caption("01 · 조건 입력")
        with st.form('pension_plan'):
            for key,label,default,maximum in [('age','현재 나이',45,120),('retire','은퇴 나이',60,120),('end','자금 사용 종료 나이',90,120),('expense','목표 월 생활비 (원)',3000000,10**12),('assets','현재 연금자산 (원)',80000000,10**12),('saving','월 저축액 (오늘 가치·원)',500000,10**12),('saving_years','저축 기간 (년)',15,120),('pension','예상 월 국민연금 (오늘 가치·원)',1100000,10**12),('normal_age','국민연금 정상 개시 나이',65,65),('pension_start','실제 수령 개시 나이',65,120)]:
                labels[key]=label;args[key]=st.number_input(label,min_value=0,max_value=maximum,value=default,key='pp_'+key)
            args['expense_future']=st.checkbox('목표 생활비를 은퇴시점의 명목금액으로 입력')
            args['adjust']=st.checkbox('국민연금 조기·연기 수령률 적용',value=True)
            direct=st.checkbox('예상 적립액 직접 사용 (오늘 가치)')
            direct_value=st.number_input('은퇴시점 예상자산 직접 입력 (오늘 가치·원)',min_value=0,value=200000000,key='pp_direct')
            args['direct']=direct_value if direct else None
            for key,label,value in [('before_rate','은퇴 전 연 수익률 (%)',5.0),('after_rate','은퇴 후 연 수익률 (%)',3.5),('inflation','연 물가상승률 (%)',2.5),('pension_growth','국민연금 수령 후 연 증가율 (%)',2.5)]:
                labels[key]=label;args[key]=st.number_input(label,min_value=-99.0,max_value=100.0,value=value,key='pp_'+key)
            args['extra']=st.number_input('추가 월 저축액 (오늘 가치·원)',min_value=0,value=300000,key='pp_extra')
            args['extra_years']=st.number_input('추가 저축 기간 (년)',min_value=0,max_value=120,value=15,key='pp_extra_years')
            args['delay']=st.number_input('시작을 미룰 기간 (년)',min_value=0,max_value=120,value=5,key='pp_delay')
            include_credit=st.checkbox('추가 납입액의 연금저축·IRP 세액공제도 계산')
            tax_inputs={}
            for key,label,default in [('income','연간 총급여 (근로소득만 있는 경우)',60000000),('existing_pension','기존 연금저축 연 납입액',0),('existing_irp','기존 IRP 연 납입액',0),('extra_pension_annual','추가 납입액 중 연금저축 연 배분액',3600000)]:
                labels[key]=label;tax_inputs[key]=st.number_input(label,min_value=0,value=default,key='pp_tax_'+key)
            submitted=st.form_submit_button('계산하기')
        if submitted:
            try:
                result=calculate(PensionPlan(**args));saved_inputs=dict(args)
                if include_credit:
                    from modules.calculators.pension.pension_credit import attach
                    if not args['extra_years']:raise ValueError('세액공제 시뮬레이션은 추가 납입기간이 1년 이상이어야 합니다.')
                    result=attach(result,{**tax_inputs,'extra_monthly':args['extra']});saved_inputs.update(tax_inputs)
                saved_inputs['세액공제 계산 포함']=include_credit
                st.session_state['pp_result']=(saved_inputs,result,datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M'))
            except ValueError as exc:st.session_state.pop('pp_result',None);st.error(str(exc))
        stored=st.session_state.get('pp_result')
        if not stored:return
        saved,r=stored[:2]
        stamp=stored[2] if len(stored)>2 else '이전 계산'
        labels.update(expense_future='생활비 은퇴시점 가치 여부',adjust='조기·연기 조정 적용',direct='예상자산 직접 입력',extra='추가 월 저축액',extra_years='추가 저축기간',delay='시작 지연기간')
        from modules.calculators.calculator_exports import build_exports
        export_fields=[(labels.get(k,k),v,'입력',None) for k,v in saved.items()]
        text,csv_data=build_exports('연금계산기',export_fields,list(saved.values()),r,stamp)
    with _ui_1:
        st.caption("02 · 고객용 결과 · 상세 계산")
        st.caption('계산 시각: '+stamp+' · 입력 변경 후 계산하기를 눌러 결과를 갱신하세요.')
        customer,advisor=st.tabs(['고객용 결과','설계사용 상세 계산'])
        with customer:
            for k,v in r.display().items():st.metric(k,v)
            st.line_chart([{'나이':float(x['나이']),'현재 계획 잔액':float(x['현재 계획 잔액']),'추가 납입 후 잔액':float(x['추가 납입 후 잔액'])} for x in r.rows],x='나이',y=['현재 계획 잔액','추가 납입 후 잔액'])
            for note in r.assumptions:st.caption(note)
            st.download_button('고객용 결과 저장',text,file_name='연금계산_고객용.txt')
        with advisor:
            st.write(r.formula)
            st.caption('국민연금 개시연령·조기/연기 비율: 국민연금공단 안내 대조 2026-09-26.')
            st.markdown('[국민연금공단 제도 안내](https://www.nps.or.kr/pnsinfo/ntpsklg/getOHAF0100M0.do)')
            labels.update(expense_future='생활비 은퇴시점 가치 여부',adjust='조기·연기 조정 적용',direct='예상자산 직접 입력',extra='추가 월 저축액',extra_years='추가 저축기간',delay='시작 지연기간')
            rows=[{'항목':labels.get(k,k),'입력':str(v)} for k,v in saved.items()]
            st.dataframe(rows,hide_index=True)
            st.dataframe([{k:float(v) for k,v in row.items()} for row in r.rows],hide_index=True)
            st.download_button('상세 계산 CSV 저장',csv_data,file_name='연금계산_상세.csv',mime='text/csv')
