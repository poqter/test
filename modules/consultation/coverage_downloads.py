"""Session-scoped PDF outputs, invalidated by source or staff changes."""

import base64
import html
import re
from string import Template

import streamlit as st
from streamlit.components.v1 import html as render_html
from modules.consultation.coverage_signature import build_signature
from modules.consultation.coverage_visual_brief import brief_pdf


def _pdf_download(title, customer_name, data):
    # The browser supplies the date at click time, even across midnight in an open tab.
    customer = re.sub(r'[\\/:*?"<>|]+', "_", str(customer_name or "").strip()) or "OOO"
    filename = customer + "_" + title.removeprefix("고객용 ")
    page = Template("""
<style>
body{margin:0;font-family:system-ui,sans-serif}
button{width:100%;min-height:40px;background:white;color:#17233c;border:1px solid #cdd3db;
border-radius:8px;font:inherit;cursor:pointer}button:hover,button:focus-visible{border-color:#506482}
</style>
<button type="button" data-name="$name">$title PDF 다운로드</button>
<script>
const button = document.querySelector("button");
const dateFormat = new Intl.DateTimeFormat("en-CA", {
    timeZone:"Asia/Seoul", year:"numeric", month:"2-digit", day:"2-digit"
});
let url;
button.onclick = () => {
    if (!url) {
        const bytes = Uint8Array.from(atob("$payload"), c => c.charCodeAt(0));
        url = URL.createObjectURL(new Blob([bytes], {type:"application/pdf"}));
    }
    const parts = Object.fromEntries(dateFormat.formatToParts(new Date()).map(p => [p.type,p.value]));
    const link = document.createElement("a");
    link.href = url;
    link.download = button.dataset.name + "_" + parts.year + parts.month + parts.day + ".pdf";
    document.body.append(link);
    link.click();
    link.remove();
};
</script>""")
    render_html(page.substitute(name=html.escape(filename, quote=True), title=html.escape(title),
                                payload=base64.b64encode(data).decode("ascii")), height=42)


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
