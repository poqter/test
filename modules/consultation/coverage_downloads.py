"""Session-scoped PDF outputs, invalidated by source or staff changes."""

from datetime import timedelta
import re

import streamlit as st
from modules.shared.local_time import now_kst
from modules.consultation.coverage_signature import build_signature
from modules.consultation.coverage_visual_brief import brief_pdf


def _pdf_download(title, customer_name, data):
    customer = re.sub(r'[\\/:*?"<>|]+', "_", str(customer_name or "").strip()) or "OOO"
    filename = f"{customer}_{title.removeprefix('고객용 ')}_{now_kst():%Y%m%d}.pdf"
    st.download_button(title + " PDF 다운로드", data=data, file_name=filename,
                       mime="application/pdf", on_click="ignore", use_container_width=True)


def render_reports(parsed, signature, selected_labels):
    now = now_kst()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    @st.fragment(run_every=midnight - now)
    def dated_downloads():
        if now_kst().date() != now.date():
            st.rerun()
        _render_reports(parsed, signature, selected_labels)

    dated_downloads()


def _render_reports(parsed, signature, selected_labels):
    profile = st.session_state.get("login_profile") or {}
    token = (signature, profile.get("display_name"), profile.get("position_name"))
    if st.session_state.get("analyzer_reports_token") != token:
        st.session_state["analyzer_reports_token"] = token
        st.session_state["analyzer_report_files"] = {}
    files = st.session_state["analyzer_report_files"]
    builders = {"고객용 보장 브리핑": lambda: brief_pdf(parsed)}
    if "kb" in parsed:
        builders = {
            "화랑 보장분석": lambda: build_signature(parsed, profile, selected_labels),
            **builders,
        }
    for title, build in builders.items():
        try:
            if title not in files:
                files[title] = build()
            _pdf_download(title, parsed["customer_name"], files[title])
        except Exception as exc:
            from modules.shared.error_reporting import record_error, user_message

            st.error(
                title
                + " PDF를 생성하지 못했습니다. "
                + user_message(record_error(exc, "analyzer.report"))
            )
