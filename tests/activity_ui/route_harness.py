from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import streamlit as st
from modules.activity.entry_route import select_entry
path=select_entry()
st.write("CALENDAR" if path=="calendar" else "WORKSPACE")
st.write("view="+st.query_params.get("view",""))
