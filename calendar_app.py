"""Independent calendar deployment; retain the proven login and activity runtime.

Deploy only the deploy/calendar branch. Do not point this app at main.
The shared source is intentionally retained for authentication compatibility.
"""
from pathlib import Path
import runpy
import streamlit as st

# Every entry (including a fresh installed-app session) stays in the calendar.
# The existing auth gate continues to enforce workspace.sales_activity and RLS.
st.session_state['_calendar_deployment'] = True
runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
