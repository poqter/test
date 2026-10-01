"""Shared visual language for required, invalid and read-only Streamlit inputs.

Only the input control is highlighted. Completed valid inputs return to the
ordinary workspace surface automatically because their key is no longer
included in the current state set.
"""
from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


BASE_CSS = r'''
:root{
  --hw-input-required-bg:#fff8ce;
  --hw-input-required-line:#d5b42b;
  --hw-input-invalid-bg:#fff1ee;
  --hw-input-invalid-line:#c95a4f;
  --hw-input-readonly-bg:#f1f4f7;
  --hw-input-readonly-line:#c9d3dd;
}
/* Required groups are structural only. State color belongs to the control. */
[class*="st-key-hw_required_group_"]{
  background:transparent!important;
  border:0!important;
  border-radius:0!important;
  padding:0!important;
  margin:6px 0 12px!important;
}
'''


def inject_input_state_styles() -> None:
    st.html("<style>" + BASE_CSS + "</style>")


def _safe_key(key: object) -> str:
    # Current project widget keys contain letters, digits, Hangul, underscores
    # and hyphens. Strip anything that could terminate a CSS selector.
    return "".join(ch for ch in str(key) if ch.isalnum() or ch in "_-" or "가" <= ch <= "힣")


def _selectors(keys: Iterable[object]) -> str:
    result: list[str] = []
    for raw in keys:
        key = _safe_key(raw)
        if not key:
            continue
        root = f".st-key-{key}"
        result.extend([
            root + ' [data-testid="stTextInputRootElement"]',
            root + ' [data-testid="stNumberInputContainer"]',
            root + ' [data-testid="stTextArea"] textarea',
            root + ' [data-baseweb="select"]>div',
            root + ' [data-testid="stSelectbox"] [role="group"]:has(>[role="combobox"])',
            root + ' [data-testid="stDateInput"] [data-baseweb="input"]',
            root + ' [data-testid="stDataEditor"]',
            root + ' [data-testid="stFileUploaderDropzone"]',
        ])
    return ",".join(result)


def apply_input_states(
    *,
    missing: Iterable[object] = (),
    invalid: Iterable[object] = (),
    readonly: Iterable[object] = (),
) -> None:
    """Paint only controls whose current state needs attention.

    Call this after rendering the widgets. On the next rerun, a key that is no
    longer missing/invalid is omitted and therefore immediately returns to the
    normal white workspace style.
    """
    rules: list[str] = []
    for keys, bg, line, shadow in (
        (missing, "var(--hw-input-required-bg)", "var(--hw-input-required-line)", "rgba(213,180,43,.10)"),
        (invalid, "var(--hw-input-invalid-bg)", "var(--hw-input-invalid-line)", "rgba(201,90,79,.10)"),
        (readonly, "var(--hw-input-readonly-bg)", "var(--hw-input-readonly-line)", "rgba(65,85,105,.06)"),
    ):
        selector = _selectors(keys)
        if selector:
            rules.append(
                selector + "{border:2px solid " + line + "!important;background:" + bg
                + "!important;box-shadow:0 0 0 2px " + shadow + "!important;}"
            )
    if rules:
        st.markdown("<style>" + "".join(rules) + "</style>", unsafe_allow_html=True)
