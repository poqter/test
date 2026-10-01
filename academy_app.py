"""Separate Streamlit Academy entrypoint; existing WORKSPACE/Calculator untouched."""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from functools import lru_cache
import hmac,time
import streamlit as st
import streamlit.components.v1 as components
from hwarang_academy.content import ROOT,SCENARIOS,MODES,BUILD_ID,validate_content
from hwarang_academy.service import AppState,handle,present

st.set_page_config(page_title='화랑 ACADEMY',page_icon='🎓',layout='wide',initial_sidebar_state='collapsed')

@lru_cache(maxsize=1)
def component():
    return components.declare_component('hwarang_academy_v12',path=str(ROOT/'frontend'))

def access_allowed()->bool:
    """Independent session login. Never borrow WORKSPACE session/token privileges."""
    try:config=dict(st.secrets.get('academy',{}))
    except (FileNotFoundError,KeyError):config={}
    if config.get('access_mode')=='public_demo':return True
    if st.session_state.get('_academy_authorized'):return True
    try:
        passwords=dict(st.secrets.get('passwords',{}))
        single=config.get('password')
        values=[single] if single else list(passwords.values())
        values=[p for p in values if isinstance(p,str) and p]
    except (FileNotFoundError,KeyError,TypeError):values=[]
    st.markdown('## 화랑 ACADEMY')
    if not values:
        st.info('Academy Secrets에 전용 비밀번호 또는 기존 [passwords] 설정을 등록해 주세요.')
        st.code('[academy]\npassword = "직접 정한 비밀번호"',language='toml')
        st.caption('공개 시험만 필요할 때는 [academy] access_mode = "public_demo"를 명시적으로 설정합니다.')
        return False
    now=time.monotonic();locked=st.session_state.get('_academy_retry_after',0)>now
    with st.form('academy_login',clear_on_submit=True):
        pwd=st.text_input('아카데미 비밀번호',type='password')
        submitted=st.form_submit_button('시작하기',disabled=locked)
    if locked:st.warning('잠시 후 다시 시도해 주세요.')
    if submitted:
        if any(hmac.compare_digest(pwd.encode(),p.encode()) for p in values):
            st.session_state['_academy_authorized']=True;st.session_state['_academy_attempts']=0;st.rerun()
        else:
            tries=st.session_state.get('_academy_attempts',0)+1;st.session_state['_academy_attempts']=tries
            if tries>=5:st.session_state['_academy_retry_after']=now+30
            st.error('비밀번호가 일치하지 않습니다.')
    return False

def base_url()->str:
    try:raw=str(st.secrets.get('academy',{}).get('public_url',''))
    except (FileNotFoundError,KeyError):raw=''
    if not raw:
        try:raw=st.context.url
        except AttributeError:raw=''
    if raw:
        p=urlsplit(raw)
        if p.scheme in ('http','https') and p.netloc:return urlunsplit((p.scheme,p.netloc,p.path,'',''))
    return ''

def main():
    if not access_allowed():return
    validate_content()
    independent=st.query_params.get('view')=='simulator'
    sid=st.query_params.get('scenario','C07-S01');mode=st.query_params.get('mode','GUIDE')
    if sid not in SCENARIOS:sid='C07-S01'
    if mode not in MODES:mode='GUIDE'
    route_key=(independent,sid,mode)
    if st.session_state.get('_academy_route')!=route_key:
        st.session_state['_academy_route']=route_key
        st.session_state['_academy_model']=AppState(independent=independent,selection=sid,mode=mode)
    app=st.session_state['_academy_model']
    bg='#0a233e' if independent else '#f4f7fb'
    st.markdown(f'''<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"]{{display:none!important}}
    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer{{display:none!important}}
    .stApp,[data-testid="stAppViewContainer"], [data-testid="stMain"]{{background:{bg}!important}}
    [data-testid="stMainBlockContainer"]{{max-width:1600px!important;padding:0!important}}
    iframe[title*="hwarang_academy"]{{border:0!important;display:block;width:100%}}
    </style>''',unsafe_allow_html=True)
    payload=present(app);payload['base_url']=base_url()
    event=component()(model=payload,key='academy_engine_component',default=None)
    if isinstance(event,dict) and event.get('event_id')!=app.ack:
        # The controller verifies mode, scenario, payload sizes and once-only commits.
        try:handle(app,event)
        except (ValueError,TypeError):
            app.error='요청을 확인해 주세요.'
            # Consume a malformed component event rather than rerunning forever.
            app.ack=event.get('event_id')
        st.rerun()
if __name__=='__main__':main()
