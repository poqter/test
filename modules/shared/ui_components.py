"""Compatibility components backed by the single Signature theme."""
from __future__ import annotations

import html

import streamlit as st


def inject_global_styles() -> None:
    from modules.shared.signature_theme import inject_signature_styles
    inject_signature_styles()
    from modules.shared.task_theme import inject_task_styles
    inject_task_styles()


def page_header(category: str, title: str, description: str, icon: str) -> None:
    icons = {'RM':'🔄','QC':'🧮','CH':'💬','CB':'📊','CM':'📄','CG':'📋','DS':'💰','RN':'🛡️','IT':'🏛️','CV':'🏆','SU':'☀️','MR':'📈','CC':'🧾','IP':'🌐','ED':'📚','▤':'🛡️'}
    icon = icons.get(icon, icon)
    st.markdown(
        f'''<div class="hw-page-head"><div class="hw-page-icon" aria-hidden="true">{html.escape(icon)}</div>
        <div class="hw-page-copy"><div class="hw-breadcrumb">화랑 WORKSPACE / {html.escape(category)}</div>
        <div class="hw-page-title">{html.escape(title)}</div><div class="hw-page-desc">{html.escape(description)}</div></div></div>''',
        unsafe_allow_html=True,
    )

    # Workflow help is available from the compact page toolbar.


def tool_guide(title: str, introduction: str, steps: list[tuple[str, str]], criteria: str = "", caution: str = "") -> None:
    with st.popover("사용 방법 · 기준", icon=":material/help_outline:"):
        st.markdown("**"+title+"**")
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
    with st.expander('도구 정보'):
        st.caption(f'{tool_name} · v{version.lstrip("v")} · 업데이트 {updated}')


def section_intro(label: str, title: str, description: str = "") -> None:
    desc = f'<div class="hw-section-desc">{html.escape(description)}</div>' if description else ""
    st.markdown(
        f'<div class="hw-section-head"><div class="hw-section-label">{html.escape(label)}</div>'
        f'<div class="hw-section-title">{html.escape(title)}</div>{desc}</div>',
        unsafe_allow_html=True,
    )
