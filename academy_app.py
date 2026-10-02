"""Separate Streamlit Academy production entrypoint."""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from functools import lru_cache
import streamlit as st
import streamlit.components.v1 as components
from hwarang_academy.content import ROOT,SCENARIOS,MODES,BUILD_ID,validate_content
from hwarang_academy.service import AppState,handle,present

st.set_page_config(page_title='화랑 ACADEMY',page_icon='🎓',layout='wide',initial_sidebar_state='collapsed')

@lru_cache(maxsize=1)
def component():
    return components.declare_component('hwarang_academy_v5',path=str(ROOT/'frontend'))

def access_allowed()->bool:
    """Academy V5 temporary public access. Authentication is intentionally bypassed."""
    return True

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
    # V5 운영 단계에서는 Academy와 시뮬레이터 모두 별도 비밀번호 입력 없이 진입합니다.
    if not access_allowed():return
    validate_content()
    independent=st.query_params.get('view')=='simulator'
    sid=st.query_params.get('scenario','C07-S01');mode=st.query_params.get('mode','GUIDE')
    if sid not in SCENARIOS:sid='C07-S01'
    if mode not in MODES:mode='GUIDE'
    route_key=(independent,sid)
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
