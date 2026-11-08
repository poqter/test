"""Exercise real home -> calendar rendering with delayed/failed access checks."""
from pathlib import Path
import sys,time
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[1])]
import streamlit as st
from activity_fixture import FakeRecords,UID
from modules.activity import center
from modules.shell.page_slot import page_slot
from modules.shared.workspace_design import apply_workspace_design
from modules.shared.hwarang_auth import HwarangAuthError
st.set_page_config(layout='wide')
apply_workspace_design()
st.session_state.setdefault('hwarang_auth',{'profile':{'id':UID,'position_code':'team_leader','role':'user'}})
def go(route):st.session_state['active_app']=route
with st.sidebar:
 st.button('홈',on_click=go,args=('home',))
 st.button('영업활동 관리',on_click=go,args=('sales_activity',))
class SlowRecords(FakeRecords):
 def __init__(self):
  time.sleep(4)
  if st.query_params.get('fail') and not st.session_state.get('attempted'):
   st.session_state['attempted']=True
   raise HwarangAuthError('연결 확인 실패')
  super().__init__()
center.Records=SlowRecords
with page_slot(st.session_state.get('active_app','home')):
 if st.session_state.get('active_app','home')=='home':
  st.title('안녕하세요, 테스트님')
  for i in range(8):st.info('홈 본문 '+str(i))
 else:center.run()
