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
body:has(.hw-calculator-standalone) [data-testid="stSidebar"] button{min-height:42px!important;height:auto!important}
body:has(.hw-calculator-standalone) [data-testid="stSidebar"] button p{white-space:normal!important;word-break:keep-all!important;overflow-wrap:anywhere!important;text-align:left!important;line-height:1.35!important}
body:has(.hw-calculator-standalone) button:focus-visible,
body:has(.hw-calculator-standalone) a:focus-visible,
body:has(.hw-calculator-standalone) input:focus-visible,
body:has(.hw-calculator-standalone) select:focus-visible{outline:3px solid rgba(45,106,213,.28)!important;outline-offset:2px!important}
body:has(.hw-calculator-standalone) [class*="st-key-hw_required_group_"]{background:#fff9db!important;border:1px solid #f2d670!important;border-radius:14px;padding:14px!important;margin:6px 0 12px}
body:has(.hw-calculator-standalone) [class*="st-key-hw_required_group_"] [data-testid="stWidgetLabel"] p:after{content:" · 입력 필요";color:#a65f00;font-size:12px;font-weight:700}
body:has(.hw-calculator-standalone) .hw-input-group-note{font-size:13px;color:#61758b;margin:-2px 0 10px}
body:has(.hw-calculator-standalone) .hw-active-condition{background:#eef4ff;border:1px solid #cbdcff;border-radius:10px;padding:10px 12px;color:#355c87;font-size:13px;line-height:1.55;margin:8px 0 12px}
body:has(.hw-calculator-standalone) .hw-primary-result-kicker{display:inline-flex;align-items:center;gap:6px;margin:0 0 7px;padding:5px 9px;border-radius:999px;background:#fff4cf;color:#805b00;font-size:12px;font-weight:750;letter-spacing:-.01em}
body:has(.hw-calculator-standalone) [class*="_hero_result"]{margin:4px 0 13px!important}
body:has(.hw-calculator-standalone) [class*="_hero_result"] [data-testid="stMetric"]{background:linear-gradient(135deg,#eaf3ff 0%,#f8fbff 62%,#fff7df 100%)!important;border:1px solid #9fbde5!important;border-left:5px solid #2d6ad5!important;border-radius:17px!important;padding:20px 22px!important;box-shadow:0 8px 22px #23496f12!important}
body:has(.hw-calculator-standalone) [class*="_hero_result"] [data-testid="stMetricLabel"] p{font-size:14px!important;font-weight:700!important;color:#426588!important}
body:has(.hw-calculator-standalone) [class*="_hero_result"] [data-testid="stMetricValue"],
body:has(.hw-calculator-standalone) [class*="_hero_result"] [data-testid="stMetricValue"] *{font-size:clamp(31px,3.2vw,43px)!important;line-height:1.2!important;font-weight:800!important;color:#143f72!important;white-space:normal!important;overflow-wrap:anywhere}
body:has(.hw-calculator-standalone) [class*="_support_result"] [data-testid="stMetric"]{background:#f8fafc!important;border:1px solid #dce5ef!important;border-radius:12px!important;padding:11px 14px!important}
body:has(.hw-calculator-standalone) [class*="_support_result"] [data-testid="stMetricValue"],
body:has(.hw-calculator-standalone) [class*="_support_result"] [data-testid="stMetricValue"] *{font-size:21px!important;line-height:1.35!important;font-weight:700!important;color:#294b6e!important;white-space:normal!important;overflow-wrap:anywhere}
@media(max-width:768px){
body:has(.hw-calculator-standalone) [data-testid="stMainBlockContainer"]{padding:4rem 10px 2rem!important}
body:has(.hw-calculator-standalone) .st-key-hw_calc_shell{padding:15px!important;border-radius:15px}
body:has(.hw-calculator-standalone) [data-testid="stSidebar"] button{min-height:44px!important}}
@media(prefers-reduced-motion:reduce){
body:has(.hw-calculator-standalone) *,body:has(.hw-calculator-standalone) *::before,body:has(.hw-calculator-standalone) *::after{scroll-behavior:auto!important;animation-duration:.01ms!important;transition-duration:.01ms!important}}
'''


def apply() -> None:
    st.markdown('<style>' + CSS + '</style>', unsafe_allow_html=True)
