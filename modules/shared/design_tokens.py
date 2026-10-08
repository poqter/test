"""Approved control tokens; scoped consumers prevent cross-page CSS overrides."""
CONTROL_CSS = """
:root{--hw-control-border:#8da3ba;--hw-control-hover:#6f8eac;--hw-control-focus:#2867c5;--hw-control-bg:#ffffff;--hw-control-radius:10px}
body:has(.hw-calculator-standalone) .st-key-hwcalc_search [data-testid="stTextInputRootElement"]{
 background:var(--hw-control-bg)!important;border:2px solid var(--hw-control-border)!important;
 border-radius:var(--hw-control-radius)!important;box-shadow:0 1px 3px #19395914!important}
body:has(.hw-calculator-standalone) .st-key-hwcalc_search [data-testid="stTextInputRootElement"]:hover{border-color:var(--hw-control-hover)!important}
body:has(.hw-calculator-standalone) .st-key-hwcalc_search [data-testid="stTextInputRootElement"]:focus-within{border-color:var(--hw-control-focus)!important;box-shadow:0 0 0 3px #2867c521!important}
body:has(.hw-calculator-standalone) .st-key-hwcalc_search [data-testid="stTextInputRootElement"] [data-baseweb]{border:0!important;box-shadow:none!important;background:transparent!important}
.hw-scope-label{font-size:12px;color:#526a80;line-height:1.6;padding:8px 12px;border:1px solid #d6e1ec;border-radius:9px;background:#f7fafc;margin:6px 0 12px}
.hw-field-missing{color:#985a00;font-size:12px;font-weight:650}
@media(prefers-reduced-motion:reduce){.st-key-hwcalc_search *{transition:none!important}}
"""
