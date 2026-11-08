"""Production host layout, synthetic records and deliberately slow context."""
from pathlib import Path
import sys,time
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[1])]
from datetime import date
import streamlit as st
from activity_fixture import FakeRecords,UID
from modules.activity import center
from modules.activity.workspace_calendar import render
from modules.shell.page_slot import page_slot
st.set_page_config(layout='wide')
st.session_state.setdefault('hwarang_auth',{'access_token':'fake','profile':{'id':UID,'position_code':'team_leader','role':'user'}})
st.session_state.setdefault('sales_anchor',date(2026,11,6))
def go(route):st.session_state['active_app']=route
with st.sidebar:
 st.button('홈',key='v2_nav_home',on_click=go,args=('home',))
 st.button('영업활동 관리',key='hw_sidebar_sales',on_click=go,args=('sales_activity',))
class SlowRecords(FakeRecords):
 def __init__(self):
  time.sleep(3)
  if st.query_params.get('fail') and not st.session_state.get('failed_once'):
   from modules.shared.hwarang_auth import HwarangAuthError
   st.session_state['failed_once']=True
   raise HwarangAuthError('연결 확인 실패')
  super().__init__()
center.Records=SlowRecords
active=st.session_state.get('active_app','home')
slot=st.container(key="sales_calendar_host")
st.session_state['sales_workspace_host_enabled']=True
st.session_state.pop('sales_host_args',None)
st.session_state.pop('sales_host_error',None)
try:
 with st.container(key='hw_workspace_body'):
  with page_slot(active):
   if active=='home':
    st.title('홈 본문')
    st.button('영업활동 관리 열기',key='brand_tile_sales',on_click=go,args=('sales_activity',))
   else:center.run()
finally:
 with slot:
  args=st.session_state.get('sales_host_args')
  render(active=='sales_activity' and st.session_state.get('sales_menu','캘린더')=='캘린더',args)
