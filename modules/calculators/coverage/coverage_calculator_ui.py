"""Coverage planning input and two audience views."""
import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from modules.calculators.coverage.coverage_models import NAMES, FIELDS, calculate
from modules.calculators.finance.finance_calculator_ui import csv_safe

def run(name, fields=None, calculator=None, caption=None):
    fields = FIELDS if fields is None else fields
    calculator = calculate if calculator is None else calculator
    st.caption(caption or '보장 필요액 시나리오 · 원본 입력·결과 대조 반영')
    from modules.shared.page_layouts import work_panels
    _ui_0, _ui_1 = work_panels("coverage_calculator_ui")
    with _ui_0:
        st.caption("01 · 조건 입력")
        with st.form('coverage_'+name):
            values=[]
            entries = fields[name]
            if name == '상속세계산기':
                sections = [("재산 · 채무 · 사전증여", 0, 9), ("가족 관계 · 배우자 공제", 9, 19),
                            ("금융재산 · 기타 공제", 19, 30), ("납부재원 · 추가 과세 조건", 30, len(entries))]
            elif len(entries) > 12:
                sections = [(f"입력 조건 {j//8+1} · {entries[j][0]}", j, min(j+8,len(entries))) for j in range(0,len(entries),8)]
            else:
                sections = [("기본 입력", 0, len(entries))]
            for section_index, (title, start, end) in enumerate(sections):
                if start >= len(entries): continue
                changed = sum(str(st.session_state.get(f'cov_{name}_{i}', entries[i][1])) != str(entries[i][1]) for i in range(start,min(end,len(entries))))
                label_text = title + (f" · 기본값과 다른 항목 {changed}개" if changed else " · 기본값")
                with st.expander(label_text, expanded=section_index == 0 or len(sections)==1):
                    for i in range(start,min(end,len(entries))):
                        label,default,unit,maximum = entries[i]
                        if unit=='선택':
                            value=st.selectbox(label,maximum,index=maximum.index(default),key=f'cov_{name}_{i}')
                        elif unit=='날짜':
                            from datetime import date
                            value=st.date_input(label,value=date.fromisoformat(default),min_value=date(1900,1,1),max_value=date(2100,12,31),key=f'cov_{name}_{i}')
                        elif unit=='문자':
                            value=st.text_input(label,value=default,max_chars=maximum,key=f'cov_{name}_{i}')
                        elif unit in ('%','명(연평균)'):
                            value=st.number_input(f'{label} ({unit})',min_value=0.0,max_value=float(maximum),value=float(default),step=0.01 if unit=='명(연평균)' else 0.1,key=f'cov_{name}_{i}')
                        else:
                            value=st.number_input(f'{label} ({unit})',min_value=0,max_value=maximum,value=default,step=10000 if unit=='원' else 1,key=f'cov_{name}_{i}')
                        values.append(value)
            submitted=st.form_submit_button('계산하기')
        result_key='coverage_result_'+name
        if submitted:
            try:st.session_state[result_key]=(tuple(values),calculator(name,values),datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M'))
            except ValueError as exc:
                st.session_state.pop(result_key,None);st.error(str(exc))
        stored=st.session_state.get(result_key)
        if not stored:return
        args,result,stamp=stored
    with _ui_1:
        st.caption("02 · 고객용 결과 · 상세 계산")
        customer,advisor=st.tabs(['고객용 결과','설계사용 상세 계산'])
        display=result.display()
        from modules.calculators.calculator_exports import build_exports
        text,csv_bytes=build_exports(name,fields[name],args,result,stamp)
        st.caption('아래 결과와 다운로드는 '+stamp+'에 계산한 입력값 기준입니다. 입력을 바꾸면 계산하기를 다시 눌러주세요.')
        with customer:
            st.subheader(name)
            for k,v in display.items():st.metric(k,v)
            for note in result.assumptions:st.caption(note)
            st.download_button('고객용 결과 저장',text,file_name=name+'_고객용.txt',mime='text/plain',key=name+'_customer')
        with advisor:
            st.write(result.formula)
            st.caption('계산 시각: '+stamp)
            inputs=[{'입력 항목':f'{f[0]} ({f[2]})','값':str(v)} for f,v in zip(fields[name],args)]
            st.dataframe(inputs,hide_index=True,width='stretch')
            st.dataframe([{k:float(v) if hasattr(v,'quantize') else v for k,v in row.items()} for row in result.rows],hide_index=True,width='stretch')
            st.download_button('상세 계산 CSV 저장',csv_bytes,file_name=name+'_상세.csv',mime='text/csv',key=name+'_advisor')
