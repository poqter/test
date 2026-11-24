"""Session-scoped PDF outputs, invalidated by source or staff changes."""

import streamlit as st
from modules.consultation.coverage_signature import build_signature
from modules.consultation.coverage_visual_brief import brief_pdf


def render_reports(parsed, signature):
    profile = st.session_state.get("login_profile") or {}
    token = (signature, profile.get("display_name"), profile.get("position_name"))
    if st.session_state.get("analyzer_reports_token") != token:
        st.session_state["analyzer_reports_token"] = token
        st.session_state["analyzer_report_files"] = {}
    files = st.session_state["analyzer_report_files"]
    builders = {"고객용 보장 브리핑": lambda: brief_pdf(parsed)}
    if "kb" in parsed:
        builders = {
            "화랑 보장분석": lambda: build_signature(parsed["kb"], profile),
            **builders,
        }
    for title, build in builders.items():
        try:
            if title not in files:
                files[title] = build()
            st.download_button(
                title + " PDF 다운로드",
                data=files[title],
                file_name=parsed["customer_name"] + "_" + title + ".pdf",
                mime="application/pdf",
                on_click="ignore",
                use_container_width=True,
            )
        except Exception as exc:
            from modules.shared.error_reporting import record_error, user_message

            st.error(
                title
                + " PDF를 생성하지 못했습니다. "
                + user_message(record_error(exc, "analyzer.report"))
            )
