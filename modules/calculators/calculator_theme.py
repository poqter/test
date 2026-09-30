"""Standalone CALCULATOR shell styles shared by catalog and detail screens."""
from __future__ import annotations

import streamlit as st

CSS = r'''
body:has(.hw-calculator-standalone) .stApp,
body:has(.hw-calculator-standalone) [data-testid="stAppViewContainer"],
body:has(.hw-calculator-standalone) [data-testid="stMain"]{background:#f5f7fa!important;color:#203a58!important}
body:has(.hw-calculator-standalone) [data-testid="stHeader"]{background:#f5f7faee!important}
body:has(.hw-calculator-standalone) [data-testid="stMainBlockContainer"]{max-width:1260px!important;padding:3.2rem 2rem 4rem!important;margin-inline:auto!important}
body:has(.hw-calculator-standalone) [data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #dde5ee!important}
body:has(.hw-calculator-standalone) .st-key-hw_calc_shell{background:#fff;border:1px solid #dce5ef;border-radius:20px;padding:26px!important;box-shadow:0 7px 24px #203c5b08}
body:has(.hw-calculator-standalone) .hw-calc-shell-kicker{font-size:12px;letter-spacing:.11em;color:#6b8298;margin-bottom:5px}
body:has(.hw-calculator-standalone) .hw-calc-sidebar-note{font-size:12px;line-height:1.55;color:#6a7d91;padding:10px 4px 2px}
body:has(.hw-calculator-standalone) [data-testid="stSidebar"] .sig-brand{margin-bottom:14px}
body:has(.hw-calculator-standalone) [data-testid="stSidebar"] [data-testid="stLinkButton"] a{justify-content:flex-start!important}
body:has(.hw-calculator-standalone) [class*="st-key-hw_required_group_"]{background:#fff9db!important;border:1px solid #f2d670!important;border-radius:14px;padding:14px!important;margin:6px 0 12px}
body:has(.hw-calculator-standalone) [class*="st-key-hw_required_group_"] [data-testid="stWidgetLabel"] p:after{content:" · 입력 필요";color:#a65f00;font-size:12px;font-weight:700}
body:has(.hw-calculator-standalone) .hw-input-group-note{font-size:13px;color:#61758b;margin:-2px 0 10px}
body:has(.hw-calculator-standalone) .hw-active-condition{background:#eef4ff;border:1px solid #cbdcff;border-radius:10px;padding:10px 12px;color:#355c87;font-size:13px;line-height:1.55;margin:8px 0 12px}
@media(max-width:768px){
body:has(.hw-calculator-standalone) [data-testid="stMainBlockContainer"]{padding:4rem 10px 2rem!important}
body:has(.hw-calculator-standalone) .st-key-hw_calc_shell{padding:15px!important;border-radius:15px}}
'''


def apply() -> None:
    st.markdown('<style>' + CSS + '</style>', unsafe_allow_html=True)
