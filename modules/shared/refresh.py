"""Refresh the current tool without remounting the workspace shell."""
import streamlit as st
from streamlit.errors import StreamlitAPIException


def refresh_current():
    try:
        st.rerun(scope="fragment")
    except StreamlitAPIException:
        # Initial app runs and legacy entrypoints have no active fragment.
        st.rerun()
