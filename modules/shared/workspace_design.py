"""Reversible web-only design layer; never used by PDF/Excel generators."""
from base64 import b64encode
from pathlib import Path
import streamlit as st

def stylesheet():
    root = Path(__file__).parent
    font = b64encode((root / 'fonts/LINESeedKR-Bd.woff2').read_bytes()).decode('ascii')
    face = "@font-face{font-family:'HW LINE Seed';src:url(data:font/woff2;base64," + font + ") format('woff2');font-weight:100 900;font-style:normal;font-display:swap;}"
    return face + root.joinpath('workspace_design.css').read_text(encoding='utf-8')

def apply_workspace_design():
    st.session_state["hw_workspace_design"] = True
    st.markdown('<style>' + stylesheet() + '</style><span class="hw-design-2026" aria-hidden="true"></span>', unsafe_allow_html=True)
