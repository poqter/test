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
    st.session_state["pdf_tools_component_key"] = key
    _component(key=key, default=None)
    pending = st.session_state.get("pdf_tools_pending_navigation")
    if pending:
        @st.dialog("PDF 작업을 종료하고 이동할까요?", on_dismiss=lambda: st.session_state.pop("pdf_tools_pending_navigation", None))
        def confirm_leave():
            st.write("현재 파일과 편집 내용은 브라우저에서 사라집니다. 필요한 결과를 먼저 다운로드해 주세요.")
            left, right = st.columns(2)
            if left.button("계속 편집", use_container_width=True):
                st.session_state.pop("pdf_tools_pending_navigation", None)
                st.rerun()
            if right.button("작업 종료 후 이동", use_container_width=True):
                from modules.shell.navigation import navigate
                target = st.session_state.pop("pdf_tools_pending_navigation")
                st.session_state["pdf_tools_leave_confirmed"] = True
                navigate(target["page"], target.get("mode"))
        confirm_leave()
