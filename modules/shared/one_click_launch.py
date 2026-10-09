from pathlib import Path
import re
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component("hwarang_one_click_launch", path=str(Path(__file__).with_name("launch_frontend")))


def launch_button(label, *, key, issue_url, disabled=False, primary=False):
    response_key = "hw.launch_response." + key
    response = st.session_state.get(response_key)
    request = _component(label=label, disabled=disabled, primary=primary,
                         response=response, key=key, default=None)
    nonce = str((request or {}).get("nonce") or "") if isinstance(request, dict) else ""
    if disabled or not re.fullmatch(r"[a-f0-9-]{36}", nonce) or (response or {}).get("nonce") == nonce:
        return
    # Nonce is UI idempotency only. issue_url rechecks server-side account access.
    url = issue_url()
    st.session_state[response_key] = {"nonce": nonce, "url": url,
        "error": "앱을 연결하지 못했습니다. 권한·연결 설정을 확인한 뒤 다시 눌러 주세요." if not url else ""}
    st.rerun()
