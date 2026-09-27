"""Input branches and results for nine financial calculators."""
import csv
import io
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import streamlit as st
from . import finance_models as engine

NAMES = ('미래가치계산기','복리계산기','수익률계산기','재무계산기','투자수익계산기',
         '현재가치계산기','비상자금 진단계산기','목표자금 계획계산기','기회비용계산기')
MODES = {'미래 금액':'future','정기 납입액':'payment','필요 수익률':'rate','필요 시작 자금':'principal','필요 투자 기간':'period'}
INPUT_LABELS={'mode':'계산 방식','principal':'시작 자금 (원)','payment':'정기 납입액 (원)','monthly':'월 금액 (원)','target':'목표 금액 (원)','years':'기간 (년)','rate':'연 수익률 (%)','frequency':'연 납입·복리 횟수','compounding':'연 복리 횟수','beginning':'기초 납입 여부','amount':'계산 대상 금액 (원)','annual_payment':'연 추가 납입액 (원)','expense':'월 필수지출 (원)','months':'목표 개월','cash':'현금 (원)','deposits':'단기 예적금 (원)','other':'기타 유동자산 (원)','debt':'단기부채 (원)','budget':'월 저축 가능액 (원)','name':'목표 이름'}

def input_rows(args):
    rows=[]
    for key,value in args.items():
        if key=='items':
            for i,goal in enumerate(value,1):
                for k,v in goal.items():rows.append((f'목표 {i} · '+INPUT_LABELS.get(k,k),str(v)))
        else:
            if key=='mode':value={v:k for k,v in MODES.items()}.get(value,value)
            rows.append((INPUT_LABELS.get(key,key),str(value)))
    return rows

def csv_safe(value):
    value=str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value

FREQUENCIES = {'매월':12,'분기마다':4,'반기마다':2,'매년':1}


def _money(label,default=0,key=None):
    return st.number_input(label+' (원)',min_value=0,max_value=10**12,value=int(default),step=10000,key=key)


def _rate(label='연 명목수익률 (%)',default=4.0,key=None):
    return st.number_input(label,min_value=-99.99,max_value=100.0,value=float(default),step=.1,key=key)


def _years(default=10,key=None):
    return st.number_input('기간 (년)',min_value=1,max_value=120,value=int(default),step=1,key=key)


def run(name):
    prefix='finance_'+name
    is_tvm=name in ('수익률계산기','재무계산기','투자수익계산기')
    mode='future'
    if is_tvm:
        mode=MODES[st.selectbox('계산할 항목',list(MODES),key=prefix+'_mode')]
    elif name=='현재가치계산기':
        mode=st.radio('현재가치 계산 방식',['미래 일시금','매년 정기 입금'],horizontal=True,key=prefix+'_mode')
    st.caption('금액은 원 단위입니다. 입력값을 변경한 뒤 계산하기를 누르면 결과가 갱신됩니다.')
    with st.form(prefix+'_form_'+mode):
        args={}
        if name=='미래가치계산기':
            args=dict(principal=_money('처음 투자할 금액',10000000),annual_payment=_money('매년 추가할 금액',200000),
                years=_years(20),rate=_rate(default=6),beginning=st.radio('추가 납입 시점',['연초','연말'],horizontal=True)=='연초')
            calculate=engine.future_value
        elif name=='복리계산기':
            freqs={**FREQUENCIES,'매일':365}
            args=dict(principal=_money('초기 투자금액',10000000),years=_years(),rate=_rate('연 명목이자율 (%)',5),
                frequency=freqs[st.selectbox('복리 계산 주기',list(freqs))])
            calculate=engine.compound
        elif is_tvm:
            general=name=='재무계산기'
            args={'mode':mode}
            if mode!='principal':args['principal']=_money('처음 투자할 금액',10000000 if general else 20000000)
            if mode!='payment':args['payment']=_money('매번 납입할 금액' if general else '매월 추가할 금액',100000 if general else 200000)
            if mode!='future':args['target']=_money('목표 금액',30000000 if general else 100000000)
            if mode!='period':args['years']=_years(10 if general else 15)
            if mode!='rate':args['rate']=_rate(default=5 if general else 6)
            selected_frequency=FREQUENCIES[st.selectbox('납입·복리 주기' if general else '복리 주기',list(FREQUENCIES))]
            args['frequency']=selected_frequency if general else 12
            args['compounding']=selected_frequency
            args['beginning']=general and st.radio('납입 시점',['기간 말','기간 시작'],horizontal=True)=='기간 시작'
            if general:
                calculate=engine.tvm
            else:
                args['monthly']=args.pop('payment',200000)
                args['frequency']=args.pop('compounding')
                args.pop('beginning')
                calculate=engine.investment
        elif name=='현재가치계산기':
            annuity=mode=='매년 정기 입금'
            args=dict(mode='annuity' if annuity else 'lump',amount=_money('매년 입금액' if annuity else '미래 일시금',300000 if annuity else 10000000),
                years=_years(),rate=_rate('연 할인율 (%)',6))
            if annuity:args['beginning']=st.radio('입금 시점',['기간 시작','기간 말'],horizontal=True)=='기간 시작'
            calculate=engine.present_value
        elif name=='비상자금 진단계산기':
            args=dict(expense=_money('월 필수 생활비',3000000),months=st.number_input('목표 보유 기간 (개월)',min_value=1,max_value=1200,value=6),
                cash=_money('현금·수시입출금',20000000),deposits=_money('단기 예적금'),other=_money('기타 즉시 현금화 자산'),debt=_money('1년 내 상환할 단기부채'))
            calculate=engine.emergency
        elif name=='목표자금 계획계산기':
            items=[]
            for i,default_name in enumerate(('자녀 교육비','주택 자금','노후 자금')):
                with st.expander(f'목표 {i+1}',expanded=i==0):
                    label=st.text_input('목표 이름',value=default_name,key=prefix+f'_name_{i}')
                    target=_money('목표 금액',100000000 if i==0 else 0,key=prefix+f'_target_{i}')
                    principal=_money('현재 모은 금액',key=prefix+f'_principal_{i}')
                    years=_years(10+i*5,key=prefix+f'_years_{i}')
                    rate=_rate('연 유효수익률 (%)',key=prefix+f'_rate_{i}')
                    items.append(dict(name=label,target=target,principal=principal,years=years,rate=rate))
            args=dict(items=items,budget=_money('매달 저축 가능액'))
            calculate=engine.goals
        else:
            args=dict(monthly=_money('매달 나가는 금액',300000),years=_years(20),rate=_rate())
            calculate=engine.opportunity
        submit=st.form_submit_button('계산하기',type='primary')
    result_key=prefix+'_result'
    if submit:
        st.session_state.pop(result_key,None)
        try:result=calculate(**args)
        except (ValueError,ArithmeticError) as exc:st.warning(str(exc))
        else:st.session_state[result_key]=(args,result,datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'))
    saved=st.session_state.get(result_key)
    if not saved or saved[0]!=args:return
    _,result,calculated_on=saved
    render_result(name,result,calculated_on,args,prefix)


def _rows_for_display(result):
    return [{k:(f'{v.quantize(Decimal(1),rounding=result.rounding):,}' if isinstance(v,Decimal) else v) for k,v in row.items()} for row in result.rows]


def render_result(name,result,calculated_on,args,prefix):
    customer,advisor=st.tabs(['고객용 결과','설계사용 상세 계산'])
    display=result.display()
    with customer:
        st.subheader(name)
        for label,value in display.items():st.metric(label,value)
        if result.rows and '총 자금' in result.rows[0]:
            st.line_chart([{'경과 연수':r['경과 연수'],'총 자금':float(r['총 자금']),'납입 원금':float(r['납입 원금'])} for r in result.rows],x='경과 연수',y=['총 자금','납입 원금'])
        st.caption('입력한 수익률과 조건에 따른 예상치입니다.')
        summary=name+'\n계산일: '+calculated_on+'\n'+'\n'.join(f'{k}: {v}' for k,v in display.items())+'\n\n계산에 사용한 입력\n'+'\n'.join(f'{k}: {v}' for k,v in input_rows(args))+'\n\n산식: '+result.formula+'\n\n'+'\n'.join(result.assumptions)
        st.download_button('고객용 결과 저장',summary.encode('utf-8-sig'),name+'_고객용.txt','text/plain',key=prefix+'_customer_export')
    with advisor:
        st.caption('계산일: '+calculated_on)
        st.write(result.formula)
        for assumption in result.assumptions:st.write('• '+assumption)
        if result.rows:st.dataframe(_rows_for_display(result),hide_index=True,width='stretch')
        with st.expander('적용한 입력 조건'):
            for label,value in input_rows(args):st.text(f'{label}: {value}')
        text=io.StringIO(newline='');writer=csv.writer(text)
        writer.writerow(['계산기',name]);writer.writerow(['계산일',calculated_on]);writer.writerow(['산식',result.formula])
        for k,v in display.items():writer.writerow([csv_safe(k),csv_safe(v)])
        for assumption in result.assumptions:writer.writerow(['가정',csv_safe(assumption)])
        writer.writerow([])
        for k,v in input_rows(args):writer.writerow([k,csv_safe(v)])
        if result.rows:
            rows=_rows_for_display(result);writer.writerow([]);writer.writerow(rows[0].keys())
            for row in rows:writer.writerow([csv_safe(v) for v in row.values()])
        st.download_button('상세 계산 CSV 저장',text.getvalue().encode('utf-8-sig'),name+'_상세계산.csv','text/csv',key=prefix+'_advisor_export')
