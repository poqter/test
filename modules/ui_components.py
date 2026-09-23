"""Compatibility components backed by the single Signature theme."""
from __future__ import annotations

import html

import streamlit as st


def inject_global_styles() -> None:
    from .signature_theme import inject_signature_styles
    inject_signature_styles()


def page_header(category: str, title: str, description: str, icon: str) -> None:
    st.markdown(
        f'''<div class="hw-page-head"><div class="hw-page-icon" aria-hidden="true">{html.escape(icon)}</div>
        <div class="hw-page-copy"><div class="hw-breadcrumb">화랑 WORKSPACE / {html.escape(category)}</div>
        <div class="hw-page-title">{html.escape(title)}</div><div class="hw-page-desc">{html.escape(description)}</div></div></div>''',
        unsafe_allow_html=True,
    )

    from .legacy_workflow import render_workflow
    render_workflow(st.session_state.get("active_app", ""))


def tool_guide(title: str, introduction: str, steps: list[tuple[str, str]], criteria: str = "", caution: str = "") -> None:
    with st.expander(title, expanded=False):
        st.markdown(f'<div class="hw-guide-intro">{html.escape(introduction)}</div>', unsafe_allow_html=True)
        if steps:
            cards = "".join(
                f'<div class="hw-guide-step"><span class="hw-guide-number">{index:02d}</span>'
                f'<div class="hw-guide-copy"><b>{html.escape(step_title)}</b><span>{html.escape(step_description)}</span></div></div>'
                for index, (step_title, step_description) in enumerate(steps, 1)
            )
            st.markdown(f'<div class="hw-guide-label">사용 순서</div><div class="hw-guide-steps">{cards}</div>', unsafe_allow_html=True)
        if criteria:
            st.markdown('<div class="hw-guide-label">계산·판정 기준</div>', unsafe_allow_html=True)
            st.markdown(criteria)
        if caution:
            st.markdown('<div class="hw-guide-label">확인사항</div>', unsafe_allow_html=True)
            st.markdown(caution)


def page_footer(tool_name: str, version: str, updated: str = "2026.08.22") -> None:
    st.markdown(
        f'<div class="hw-page-footer"><span class="hw-page-footer-brand">화랑 WORKSPACE</span>'
        f'<span>{html.escape(tool_name)} v{html.escape(version.lstrip("v"))} · Updated {html.escape(updated)}</span></div>',
        unsafe_allow_html=True,
    )


def section_intro(label: str, title: str, description: str = "") -> None:
    desc = f'<div class="hw-section-desc">{html.escape(description)}</div>' if description else ""
    st.markdown(
        f'<div class="hw-section-head"><div class="hw-section-label">{html.escape(label)}</div>'
        f'<div class="hw-section-title">{html.escape(title)}</div>{desc}</div>',
        unsafe_allow_html=True,
    )
