"""Shared task and home presentation; never changes business or permission rules."""
from pathlib import Path
import streamlit as st


def apply_clean_design():
    css = Path(__file__).with_suffix('.css').read_text(encoding='utf-8')
    st.markdown('<style>' + css + '</style><span class="hw-clean-design" aria-hidden="true"></span>', unsafe_allow_html=True)
