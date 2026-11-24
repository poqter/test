"""Session-scoped PDF outputs, invalidated by source or staff changes."""

import base64
import html
import re
from string import Template

import streamlit as st
from modules.shared.local_time import now_kst
from modules.consultation.coverage_signature import build_signature
from modules.consultation.coverage_visual_brief import brief_pdf


def _pdf_download(title, customer_name, data):
    # The browser supplies the date at click time, even across midnight in an open tab.
    customer = re.sub(r'[\\/:*?"<>|]+', "_", str(customer_name or "").strip()) or "OOO"
    filename = customer + "_" + title.removeprefix("고객용 ")
    element_id = "hw-coverage-download-" + ("brief" if title.startswith("고객용") else "analysis")
    page = Template("""
<style>
.hw-coverage-download{display:block;text-align:center;padding:8px;color:#17233c!important;
border:1px solid #cdd3db;border-radius:8px;text-decoration:none!important;background:white}
.hw-coverage-download:hover,.hw-coverage-download:focus-visible{border-color:#506482}
</style>
<a class="hw-coverage-download" id="$id" data-name="$name" download="$initial"
href="data:application/pdf;base64,$payload">$title PDF 다운로드</a>
<script>
(() => {
    const link = document.getElementById("$id");
    const dateFormat = new Intl.DateTimeFormat("en-CA", {
        timeZone:"Asia/Seoul", year:"numeric", month:"2-digit", day:"2-digit"
    });
    link.onclick = () => {
        const parts = Object.fromEntries(dateFormat.formatToParts(new Date()).map(p => [p.type,p.value]));
        link.download = link.dataset.name + "_" + parts.year + parts.month + parts.day + ".pdf";
    };
})();
</script>""")
    initial = f"{filename}_{now_kst():%Y%m%d}.pdf"
    st.html(page.substitute(id=element_id, name=html.escape(filename, quote=True),
                            initial=html.escape(initial, quote=True), title=html.escape(title),
                            payload=base64.b64encode(data).decode("ascii")), unsafe_allow_javascript=True)


def render_reports(parsed, signature, selected_labels):
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
