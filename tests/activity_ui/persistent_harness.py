"""PC and installed-app entry harness, synthetic data only."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import streamlit as st
from datetime import date
from activity_fixture import FakeRecords,UID
from modules.activity import center,mobile
st.set_page_config(layout='wide')
st.session_state.setdefault('hwarang_auth',{'profile':{'id':UID,'position_code':'team_leader','role':'user'}})
st.session_state.setdefault('sales_anchor',date(2026,11,6))
center.Records=FakeRecords
if st.query_params.get('surface')=='pc':center.run()
else:
 st.query_params['view']='mobile-calendar'
 from modules.shared.workspace_design import apply_workspace_design
 apply_workspace_design()
 mobile.run(lambda:st.session_state.update(logged_out=True))
