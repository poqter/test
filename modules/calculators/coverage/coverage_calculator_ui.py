"""Coverage planning input and two audience views."""
import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from modules.calculators.input_design import number_input
from modules.calculators.coverage.coverage_models import NAMES, FIELDS, calculate
from modules.calculators.finance.finance_calculator_ui import csv_safe

def run(name, fields=None, calculator=None, caption=None):
    fields = FIELDS if fields is None else fields
    calculator = calculate if calculator is None else calculator
    st.caption(caption or '보장 필요액 시나리오 · 원본 입력·결과 대조 반영')
    from modules.calculators.input_design import input_panels as work_panels
    _ui_0, _ui_1 = work_panels("coverage_calculator_ui")
    with _ui_0:
        st.caption("01 · 조건 입력")
        with st.container(key='coverage_'+name):
            entries = fields[name]
            values = [None] * len(entries)
            confirmations = [i for i, (label, default, unit, options) in enumerate(entries)
                             if unit == '선택' and ('미확인' in options or '확인' in label or '요건 충족' in label or label == '신고의무 자격')]

            def render_field(i):
                label, default, unit, maximum = entries[i]
                key = f'cov_{name}_{i}'
                if unit == '선택':
                    value = st.selectbox(label, maximum, index=maximum.index(default), key=key)
                elif unit == '날짜':
                    from datetime import date
                    value = st.date_input(label, value=date.fromisoformat(default), min_value=date(1900,1,1), max_value=date(2100,12,31), key=key)
                elif unit == '문자':
                    # This calculator's signed adjustments are parsed in won by its engine.
                    signed_money = maximum == 30 and any(w in label for w in ('조정액', '순손익', '세무상 소득', '세액 합계', '수입금액', '보험료'))
                    value = st.text_input(label + (' (원)' if signed_money else ''), value=default, max_chars=maximum, key=key,
                                          help='원 단위 정수로 입력합니다. 빈칸과 음수의 허용 여부는 항목 안내를 따릅니다.' if signed_money else None)
                elif unit in ('%', '명(연평균)'):
                    value = number_input(f'{label} ({unit})', min_value=0.0, max_value=float(maximum), value=float(default), step=0.01 if unit=='명(연평균)' else 0.1, key=key)
                else:
                    value = number_input(f'{label} ({unit})', min_value=0, max_value=maximum, value=default, step=10000 if unit=='원' else 1, key=key)
                values[i] = value

            if confirmations:
                with st.container(border=True, key='hw_confirm_'+name):
                    st.markdown('**계산 전 확인**')
                    st.caption('적용 요건을 확인한 경우에만 해당 항목을 선택하세요. 선택에 따라 적용되는 계산 조건이 달라집니다.')
                    for i in confirmations:
                        render_field(i)
            remaining = [i for i in range(len(entries)) if i not in confirmations]
            if name == '상속세계산기':
                sections = [(title, [i for i in remaining if start <= i < end]) for title, start, end in
                            [('재산 · 채무 · 사전증여',0,9),('가족 관계 · 배우자 공제',9,19),
                             ('금융재산 · 기타 공제',19,30),('납부재원 · 추가 과세 조건',30,len(entries))]]
            elif len(remaining) <= 12:
                sections = [('계산 조건', remaining)]
            else:
                groups = {title: [] for title in ('대상 · 기본 정보', '소득 · 납입 · 지출', '자산 · 부채 · 평가금액',
                                                   '공제 · 세금 · 적용 기준', '기간 · 일정', '비율 · 가정')}
                for i in remaining:
                    label, default, unit, maximum = entries[i]
                    if unit == '%':
                        title = '비율 · 가정'
                    elif any(word in label for word in ('공제', '세액', '과세', '세율', '비과세', '원천징수', '할증', '감면')):
                        title = '공제 · 세금 · 적용 기준'
                    elif unit == '날짜' or unit in ('년', '개월', '세', '일'):
                        title = '기간 · 일정'
                    elif any(word in label for word in ('소득', '급여', '납입', '보험료', '생활비', '지출', '손익', '매출', '비용')):
                        title = '소득 · 납입 · 지출'
                    elif unit == '원' or any(word in label for word in ('자산', '부채', '조정액', '잔액')):
                        title = '자산 · 부채 · 평가금액'
                    else:
                        title = '대상 · 기본 정보'
                    groups[title].append(i)
                sections = [(title, indices) for title, indices in groups.items() if indices]
            for section_index, (title, indices) in enumerate(sections):
                if not indices:
                    continue
                with st.expander(title, expanded=section_index == 0):
                    for i in indices:
                        render_field(i)
            submitted = st.button('계산하기', type='primary', width='stretch')
        result_key='coverage_result_'+name
        if submitted:
            try:st.session_state[result_key]=(tuple(values),calculator(name,values),datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M'))
            except ValueError as exc:
                st.session_state.pop(result_key,None);st.error(str(exc))
                if confirmations: st.caption('적용 요건 선택은 입력 영역 맨 위의 ‘계산 전 확인’에서 확인할 수 있습니다.')
        stored=st.session_state.get(result_key)
        if not stored:return
        if stored[0] != tuple(values):
            st.info("입력 조건이 변경되었습니다. 다시 계산해주세요.")
            return
        args,result,stamp=stored
    with _ui_1:
        st.caption("02 · 계산 결과")
        customer,advisor=(st.container(), st.expander('산출 내역 자세히 보기'))
        display=result.display()
        from modules.calculators.calculator_exports import build_exports
        text,csv_bytes=build_exports(name,fields[name],args,result,stamp)
        st.caption('아래 결과와 다운로드는 '+stamp+'에 계산한 입력값 기준입니다. 입력을 바꾸면 계산하기를 다시 눌러주세요.')
        with customer:
            st.subheader(name)
            from modules.calculators.input_design import render_metrics
            render_metrics(display, 'cov_'+name)
            from modules.calculators.result_pdf import build_result_pdf, pdf_section_options
            pdf_options = pdf_section_options('cov_pdf_'+name)
            if any(pdf_options.values()):
                pdf = build_result_pdf(name, [(f'{f[0]} ({f[2]})', v) for f,v in zip(fields[name],args)], result, stamp, **pdf_options)
                st.download_button('결과 PDF 저장',pdf,file_name=name+'_결과보고서.pdf',mime='application/pdf',key=name+'_customer', type='primary', icon=':material/download:', width='stretch')
        with advisor:
            for note in result.assumptions: st.caption(note)
            st.write(result.formula)
            st.caption('계산 시각: '+stamp)
            inputs=[{'입력 항목':f'{f[0]} ({f[2]})','값':str(v)} for f,v in zip(fields[name],args)]
            st.dataframe(inputs,hide_index=True,width='stretch')
            st.dataframe([{k:float(v) if hasattr(v,'quantize') else v for k,v in row.items()} for row in result.rows],hide_index=True,width='stretch')
            st.download_button('상세 계산 CSV 저장',csv_bytes,file_name=name+'_상세.csv',mime='text/csv',key=name+'_advisor')

    from modules.calculators.input_design import jump_to_result
    jump_to_result(submitted, 'coverage_calculator_ui')
