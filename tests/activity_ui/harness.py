"""Offline browser harness: synthetic identities only; never calls production."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import streamlit as st
from datetime import date
from activity_fixture import FakeRecords, UID, OTHER
from modules.activity import center
st.set_page_config(layout='wide')
st.session_state.setdefault('hwarang_auth',{'profile':{'id':UID,'position_code':'team_leader','role':'user'}})
st.session_state.setdefault('fixture_support_candidates',[{'member':OTHER,'label':'테스트 구성원','role_code':'team_leader'}])
st.session_state.setdefault('manager_pref_date',date(2026,11,6))
st.session_state.setdefault('sales_anchor',date(2026,11,6))
st.session_state.setdefault('sales_day_일일',date(2026,11,6))
st.session_state['full_runs']=st.session_state.get('full_runs',0)+1
st.caption('전체 실행 횟수 '+str(st.session_state['full_runs']))
center.Records=FakeRecords
import app as workspace
class SyntheticAuth:
 def refresh(self,state):return state
 def workspace_permission_role(self,profile):return 'user'
workspace.auth_service=lambda:SyntheticAuth()
workspace.dispatch=lambda *args,**kwargs:center.run()
workspace.render_task_content('sales_activity','user',['sales_activity'])
