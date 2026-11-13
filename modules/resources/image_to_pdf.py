"""Client-side PDF editor hosted inside the existing authorized WORKSPACE route."""
from pathlib import Path
import hashlib
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component(
    "hwarang_pdf_tools", path=str(Path(__file__).with_name("pdf_tools"))
)


def run() -> None:
    # The dispatcher applies organization and customer-materials access first.
    from modules.shell.navigation import allowed_ids
    if not st.session_state.get("password_correct") or "image_to_pdf" not in allowed_ids(st.session_state.get("login_user")):
        st.error("고객 전달자료 이용 권한을 확인해 주세요.")
        return
    st.title("PDF·이미지 도구")
    st.caption("파일 추가 → 페이지 편집 → 저장 전 확인 → 다운로드")
    # Recreate the isolated in-memory workspace on account/session changes.
    scope = repr((st.session_state.get("hw_platform_session_id"), st.session_state.get("login_profile")))
    key = "pdf_tools_" + hashlib.sha256(scope.encode()).hexdigest()[:20]
    _component(key=key, default=None)
