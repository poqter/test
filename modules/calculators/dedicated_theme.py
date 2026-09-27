"""Login-inspired navy glass surround; readable light calculation paper."""
import streamlit as st
CSS = '''
body:has(.hw-calculator-only) .stApp,
body:has(.hw-calculator-only) [data-testid="stAppViewContainer"],
body:has(.hw-calculator-only) [data-testid="stMain"]{
background:radial-gradient(circle at 18% 78%,#244f79 0,#112b49 33%,#071a30 77%)!important;background-attachment:fixed!important}
body:has(.hw-calculator-only) [data-testid="stMainBlockContainer"]{max-width:1200px!important;padding:36px 24px!important;margin-inline:auto!important}
body:has(.hw-calculator-only) .st-key-hw_task_page{
padding:14px!important;border:1px solid rgba(168,220,233,.36)!important;border-top-color:rgba(220,249,255,.65)!important;border-radius:28px!important;
background:linear-gradient(125deg,rgba(93,148,187,.3),rgba(18,48,75,.6) 52%,rgba(7,26,47,.8))!important;
box-shadow:0 28px 70px rgba(0,9,22,.42),inset 0 1px 0 rgba(220,249,255,.25)!important;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
body:has(.hw-calculator-only) .st-key-hw_calc_paper{background:#f5f7fa!important;color:#243247!important;border:1px solid #d8e4ef!important;border-radius:18px!important;padding:28px!important;box-shadow:0 5px 22px #061b3026}
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid #cfdae7!important;border-radius:14px!important}
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-baseweb="input"],
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-baseweb="textarea"],
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-baseweb="select"]>div{
background:#fff!important;border:2px solid #91a6bc!important;border-radius:9px!important;box-shadow:inset 0 1px 2px #122f4510!important}
body:has(.hw-calculator-only) .st-key-hw_calc_paper input,
body:has(.hw-calculator-only) .st-key-hw_calc_paper textarea{color:#18334f!important;-webkit-text-fill-color:#18334f!important;caret-color:#245fc5!important;background:#fff!important}
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-baseweb="input"]:focus-within,
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-baseweb="textarea"]:focus-within,
body:has(.hw-calculator-only) .st-key-hw_calc_paper [data-baseweb="select"]:focus-within>div{border-color:#2875cc!important;box-shadow:0 0 0 3px #2875cc26!important}
@media(max-width:640px){body:has(.hw-calculator-only) [data-testid="stMainBlockContainer"]{padding:14px 8px!important}body:has(.hw-calculator-only) .st-key-hw_task_page{padding:7px!important;border-radius:20px!important}body:has(.hw-calculator-only) .st-key-hw_calc_paper{padding:16px 12px!important;border-radius:13px!important}}
'''
def apply():
    st.markdown('<style>'+CSS+'</style>',unsafe_allow_html=True)
