from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from modules.shared.ui_components import inject_global_styles
st.set_page_config(layout='wide')
inject_global_styles()
from modules.shared.workspace_design import apply_workspace_design
apply_workspace_design()
st.session_state['shell_runs'] = st.session_state.get('shell_runs', 0) + 1
st.caption('전체 실행 횟수: ' + str(st.session_state['shell_runs']))
@st.fragment
def surface():
    if st.query_params.get('tool') == 'calculator':
        from modules.calculators.calculator_center import render_quick_calculator
        render_quick_calculator('총 납입보험료계산기')
    else:
        from modules.consultation.enrollment_comparison import run
        run()
surface()
