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
    category = {
        '상담·제안서': '고객 상담', '보험자료 분석': '고객 상담',
        '고객 전달자료': '고객 상담', '재무·보험 계산': '보험 비교 · 계산',
        '종합계산기(80개)': '보험 비교 · 계산', '교육·체크리스트': '자료 · 교육',
        '원수사·공식정보': '자료 · 교육', '실적·수수료': '실적 관리',
    }.get(category, category)
    icons = {'RM':'🔄','QC':'🧮','CH':'💬','CB':'📊','CM':'📄','CG':'📋','DS':'💰','RN':'🛡️','IT':'🏛️','CV':'🏆','SU':'☀️','MR':'📈','CC':'🧾','IP':'🌐','ED':'📚','▤':'🛡️'}
    icon = icons.get(icon, icon)
    st.markdown(
        f'''<div class="hw-page-head"><div class="hw-page-icon" aria-hidden="true">{html.escape(icon)}</div>
        <div class="hw-page-copy"><div class="hw-breadcrumb">화랑 WORKSPACE / {html.escape(category)}</div>
        <div class="hw-page-title">{html.escape(title)}</div><div class="hw-page-desc">{html.escape(description)}</div></div></div>''',
        unsafe_allow_html=True,
    )

    # Workflow help is available from the compact page toolbar.


def workflow_steps(labels: list[str], key: str) -> str:
    """Consistent, session-preserving step selector for document workflows."""
    pending = st.session_state.pop(key + '_pending', None)
    current = pending or st.session_state.get(key, labels[0])
    st.session_state[key] = current if current in labels else labels[0]
    with st.container(key='hw_steps_' + key):
        return st.radio('작성 순서', labels, horizontal=True, key=key)


def workflow_button(label: str, step: str, key: str, *, primary=False):
    if st.button(label, key=key + '_go_' + step,
                 type='primary' if primary else 'secondary', use_container_width=True):
        st.session_state[key + '_pending'] = step
        st.rerun()


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
