"""Offline actual Streamlit renderer; never contacts auth/AI/database services."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import streamlit as st
from modules.shared.ui_components import inject_global_styles
from modules.shared.permissions import CALCULATOR_GROUP_PERMISSION
from modules.shell.app_registry import APP_BY_ID
from modules.shell.workspace_v2 import render_home,render_sidebar
from modules.shell.navigation import navigate
st.set_page_config(layout='wide',initial_sidebar_state='expanded')
inject_global_styles()
surface=st.query_params.get('surface','workspace')
profile={'display_name':'검수 사용자','organization_name':'검수 조직','position_name':'팀장'}
st.session_state['login_profile']=profile
if surface=='calculator':
 from modules.calculators.calculator_shell import render_sidebar as calc_shell
 from modules.calculators.calculator_theme import apply
 from modules.calculators.calculator_center import run
 st.session_state['hw_feature_permissions']=st.session_state.get('test_permissions',set(CALCULATOR_GROUP_PERMISSION.values()))
 st.session_state['_hwarang_calculator_identity']={'profile':profile}
 apply();st.markdown('<div class="hw-calculator-standalone"></div>',unsafe_allow_html=True)
 calc_shell()
 with st.container(key='hw_calc_shell'):run()
else:
 allowed=st.session_state.get('test_allowed',[a.id for a in APP_BY_ID.values() if a.enabled])
 st.session_state['active_app']=st.session_state.get('active_app','home')
 st.session_state['ws_allowed_ids']=allowed
 notice={'title':'검수','date':'2026-10-15','items':[]}
 with patch('modules.shell.workspace_v2.render_home_quick_search',lambda:st.caption('검수 환경: 외부 원수사 검색 연결 생략')),patch('modules.briefing.briefing_center.render_home_summary',lambda nav:st.button('브리핑 센터 열기',key='qa_brief',on_click=navigate,args=('briefing',))):
  render_sidebar(allowed,navigate,lambda:None,notice)
  if st.session_state['active_app']=='home':render_home(allowed,navigate,notice)
  else:st.title('이동 완료: '+st.session_state['active_app'])
