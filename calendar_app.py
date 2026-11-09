"""Independent calendar deployment; retain the proven login and activity runtime.

Deploy main / calendar_app.py as a separate Streamlit app.
The shared source is intentionally retained for authentication compatibility.
"""
from pathlib import Path
import streamlit as st

# Every entry (including a fresh installed-app session) stays in the calendar.
# The existing auth gate continues to enforce workspace.sales_activity and RLS.
st.session_state['_calendar_deployment'] = True
# Execute in an isolated namespace. runpy.run_path temporarily replaces shared
# sys.modules entries, which is unsafe across concurrent Streamlit sessions.
entry = Path(__file__).with_name('app.py')
namespace = {"__name__": "__main__", "__file__": str(entry), "__package__": None}
exec(compile(entry.read_bytes(), str(entry), "exec"), namespace)
