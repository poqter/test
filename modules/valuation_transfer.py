"""Explicit handoff of the calculated tax value, never the scenario premium."""
from decimal import Decimal, ROUND_DOWN
import streamlit as st
TARGETS=('가업승계 세부담계산기','증여세계산기','상속세계산기')

def apply_pending():
    pending=st.session_state.pop('jc_valuation_transfer',None)
    if not pending:return
    target,amount=pending
    st.session_state['jc_group']='전체'
    st.session_state['jc_search']=''
    st.session_state['jc_selected']=target
    if target==TARGETS[0]:
        st.session_state[f'cov_{target}_0']=amount
    elif target==TARGETS[2]:
        st.session_state[f'cov_{target}_35']=amount
    else:
        st.session_state['gift_mode']='증여세 상세 계산'
        st.session_state[f'cov_{target}_6']=amount
    st.session_state.pop('coverage_result_'+target,None)
    st.session_state['jc_transfer_notice']=f'{target}에 평가액 {amount:,}원을 입력했습니다. 다른 재산·공제·적격요건을 확인한 뒤 계산하세요.'

def render():
    stored=st.session_state.get('coverage_result_비상장주식 평가계산기')
    if not stored:return
    args,result,_=stored
    per_share=result.metrics['1주당 보충적 평가액']
    with st.expander('평가액으로 증여·상속·가업승계 계산 이어가기'):
        st.caption('계산된 세법상 1주 평가액을 사용합니다. 업종 보정·경영권 프리미엄 참고값은 전달하지 않습니다. 대상 계산기의 해당 주식 평가액을 바꾸며, 다른 재산·공제는 이동한 화면에서 다시 확인하세요.')
        shares=st.number_input('이번에 이전할 주식 수',min_value=1,max_value=int(args[1]),value=1,key='jc_transfer_shares')
        amount=int((per_share*Decimal(shares)).quantize(Decimal('1'),rounding=ROUND_DOWN))
        st.write(f'이전 주식 평가액: {amount:,}원 (원 미만 절사)')
        target=st.selectbox('이어서 계산할 항목',TARGETS,key='jc_transfer_target')
        if st.button('평가액 입력하고 이동',key='jc_transfer_apply'):
            if amount>10**12:
                st.error('연결 대상 계산기의 입력 한도 1조원을 초과합니다.')
            else:
                st.session_state['jc_valuation_transfer']=(target,amount)
                st.rerun()
