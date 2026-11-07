from pathlib import Path
import sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import streamlit as st
from types import SimpleNamespace
from modules.shared.ui_components import inject_global_styles
from modules.shared.workspace_design import apply_workspace_design
from modules.shell.workspace_v2 import render_home,render_sidebar,APP_BY_ID
from modules.shell import home_briefing
from modules.shared.hwarang_auth import SupabaseConfig
st.set_page_config(layout='wide',initial_sidebar_state='expanded')
inject_global_styles();apply_workspace_design()
SupabaseConfig.from_mapping=lambda _:SimpleNamespace(url='test',secret_key='test')
def slow(*_):
 time.sleep(8)
 return '오늘 자료 공개','경제·금융 · 종합뉴스 · 보험업계'
home_briefing._load=slow
st.session_state['login_profile']={'display_name':'Test'}
def navigate(target,*args,**kwargs):st.session_state['active_app']=target
render_sidebar(list(APP_BY_ID),navigate,lambda:None,{})
if st.session_state.get('active_app','home')=='home':render_home(list(APP_BY_ID),navigate,{})
else:st.title('OPENED '+st.session_state['active_app'])
