
# Stable facade: UI only; engines/parsers/exports are independently testable.
from modules.consultation.analyzer_model import (
    APP_VERSION,
    DEFAULT_COVERAGES,
    DISPLAY_NAMES,
    GROUP_RULES,
    COLORS,
    LOGO_BASE64,
    THIN_SIDE,
    MEDIUM_SIDE,
    THICK_SIDE,
    THIN_BORDER,
    _normalize_label,
    _to_number,
    _is_fully_paid,
    _format_won_text,
    _group_for,
    _extract_customer_name,
    _extract_age,
    parse_source_file,
)

from modules.consultation.analyzer_exports import (
    _set_outline,
    _set_vertical_borders,
    _extract_logo,
    _configure_print,
    _contract_column_width,
    _populate_analysis_sheet,
    _populate_proposal_sheet,
    build_analysis_file,
)

import hashlib
import base64
import re
from copy import copy
from datetime import datetime
from io import BytesIO

import openpyxl
import streamlit as st
from modules.shared.upload_ui import guarded_upload
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from modules.shared.ui_components import page_footer, page_header, tool_guide


def make_input_signature(main_bytes: bytes, mode: str, selected_labels: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(main_bytes)
    digest.update(mode.encode("utf-8"))
    digest.update("|".join(selected_labels).encode("utf-8"))
    return digest.hexdigest()


def _render_personal_selector(
    available_labels: list[str],
    default_labels: list[str],
    file_key: str,
) -> list[str]:
    """모든 보장항목을 구분별 카드에 펼쳐 보여주는 개인모드 선택기입니다."""
    prefix = f"analyzer_v2_cov_{file_key}_"
    default_set = set(default_labels)

    for label in available_labels:
        state_key = f"{prefix}{label}"
        if state_key not in st.session_state:
            st.session_state[state_key] = label in default_set

    col_all, col_default, col_clear = st.columns(3)
    if col_all.button("전체 선택", use_container_width=True, key=f"{prefix}all"):
        for label in available_labels:
            st.session_state[f"{prefix}{label}"] = True
    if col_default.button("기본 보장 선택", use_container_width=True, key=f"{prefix}default"):
        for label in available_labels:
            st.session_state[f"{prefix}{label}"] = label in default_set
    if col_clear.button("전체 해제", use_container_width=True, key=f"{prefix}clear"):
        for label in available_labels:
            st.session_state[f"{prefix}{label}"] = False

    grouped: dict[str, list[str]] = {}
    for label in available_labels:
        group = _group_for(label).replace("\n", " ")
        grouped.setdefault(group, []).append(label)

    card_columns = st.columns(3)
    for group_index, (group, labels) in enumerate(grouped.items()):
        selected_count = sum(bool(st.session_state[f"{prefix}{label}"]) for label in labels)
        with card_columns[group_index % 3]:
            with st.container(border=True):
                st.markdown(f"**{group}** · {selected_count}/{len(labels)}")
                for label in labels:
                    st.checkbox(
                        DISPLAY_NAMES.get(label, label),
                        key=f"{prefix}{label}",
                    )

    selected = [label for label in available_labels if st.session_state[f"{prefix}{label}"]]
    st.caption(f"전체 {len(available_labels)}개 중 {len(selected)}개 선택")
    return selected


def _inject_analyzer_page_styles() -> None:
    """Local presentation only; does not alter parsing or workbook output."""
    st.markdown("""
    <style>
    .st-key-analyzer_page_inputs, .st-key-analyzer_page_results {
        background: #fff; border: 1px solid #dfe6ef; border-radius: 16px;
        padding: 24px; margin-bottom: 20px; box-shadow: 0 3px 12px #21344b04;
    }
    .st-key-analyzer_page_inputs h3, .st-key-analyzer_page_results h3 {
        font-size: 1.16rem !important; letter-spacing: -.025em;
        margin-bottom: 16px;
    }
    .st-key-analyzer_page_inputs [data-testid="stFileUploader"] {
        background: #f5f8fd; border: 1px dashed #aebfd5;
        border-radius: 12px; padding: 12px;
    }
    .st-key-analyzer_page_inputs [role="radiogroup"] {gap: 12px; flex-wrap: wrap;}
    .st-key-analyzer_page_inputs [role="radiogroup"] label {
        border: 1px solid #d4deec; border-radius: 10px; padding: 12px 18px;
        background: #fff; transition: background .18s, border-color .18s;
    }
    .st-key-analyzer_page_inputs [role="radiogroup"] label:has(input:checked) {
        background: #eff5ff; border-color: #3673cc;
    }
    .st-key-analyzer_page_results [data-testid="stMetric"] {padding: 12px 0;}
    .st-key-analyzer_page_inputs button:hover,
    .st-key-analyzer_page_results button:hover {transform: none !important;}
    @media(max-width: 760px) {
        .st-key-analyzer_page_inputs, .st-key-analyzer_page_results {padding: 16px;}
        .st-key-analyzer_page_inputs [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
        .st-key-analyzer_page_inputs [data-testid="stColumn"] {
            width: 100% !important; flex: 1 1 100% !important; min-width: 0 !important;
        }
    }
    @media(prefers-reduced-motion: reduce) {
        .st-key-analyzer_page_inputs *, .st-key-analyzer_page_results * {transition: none !important;}
    }
    </style>
    """, unsafe_allow_html=True)


def run() -> None:
    page_header(
        "고객 상담",
        "보장 분석 도우미",
        "전체 보장분석 원본을 고객 상담용 엑셀로 자동 정리합니다.",
        "▤",
    )

    _inject_analyzer_page_styles()
    with st.container(key="analyzer_page_inputs"):
        st.markdown("### 01 · 자료와 분석 설정")
        upload_column, mode_column = st.columns([1.05, 1], gap="large")
        with upload_column:
            st.markdown("**전체 보장분석 원본**")
            uploaded_main = guarded_upload(
                "전체 보장내용이 포함된 컨설팅보장분석.xlsx 파일을 업로드하세요",
                type=["xlsx"],
                key="analyzer_v2_main_file",
            )

        parsed = None
        parse_error = None
        main_bytes = uploaded_main.getvalue() if uploaded_main else b""
        if uploaded_main:
            try:
                parsed = parse_source_file(main_bytes)
            except Exception as exc:
                parse_error = exc
                from modules.shared.error_reporting import record_error, user_message
                st.error(user_message(record_error(exc, "analyzer.parse")))

        with mode_column:
            st.markdown("**분석 방식**")
            mode = st.radio(
                "분석 방식을 선택하세요",
                ["간편모드", "개인모드"],
                horizontal=True,
                key="analyzer_v2_mode",
                format_func=lambda value: {"간편모드":"자동 정리", "개인모드":"항목 직접 선택"}[value],
            )

            st.caption("자동 정리는 파일을 올리면 결과를 만듭니다. 항목 직접 선택은 출력할 보장을 고른 뒤 실행합니다.")

        selected_labels: list[str] = []
        if parsed:
            with st.expander('인식된 계약과 고객정보 확인', expanded=False):
                st.write(f"고객: {parsed['customer_name']} · 보험나이: {parsed['age']} · 계약 {len(parsed['contracts'])}개")
                st.dataframe([{'보험사': c['company'], '상품': c['product'], '월보험료': c['monthly'], '보장기간': c['coverage_period']} for c in parsed['contracts']], hide_index=True, use_container_width=True)
                if any(not c['company'] or not c['product'] or c['monthly'] == 0 for c in parsed['contracts']):
                    st.info('회사·상품명이 비어 있거나 보험료가 0인 계약이 있습니다. 완납 여부와 원본을 확인하세요.')
            available_labels = [item["label"] for item in parsed["coverages"]]
            default_labels = [label for label in available_labels if label in set(DEFAULT_COVERAGES)]

            if mode == "간편모드":
                selected_labels = default_labels
                st.info(f"기본 보장 {len(selected_labels)}개가 자동으로 적용됩니다.")
                with st.expander("자동 정리에 포함되는 보장 보기"):
                    st.write([DISPLAY_NAMES.get(label, label) for label in selected_labels])
            else:
                st.markdown("#### 출력할 보장항목")
                st.caption("구분별 카드에서 필요한 보장항목을 바로 체크하거나 해제하세요.")
                selected_labels = _render_personal_selector(
                    available_labels,
                    default_labels,
                    hashlib.sha256(main_bytes).hexdigest()[:10],
                )
        elif not uploaded_main:
            st.caption("원본 파일을 업로드하면 선택 가능한 전체 보장항목이 표시됩니다.")

        ready = bool(parsed) and bool(selected_labels) and parse_error is None
        signature = make_input_signature(main_bytes, mode, selected_labels) if ready else None

        should_generate = False
        if mode == "간편모드" and ready:
            current_result = st.session_state.get("analyzer_v2_result")
            current_error = st.session_state.get("analyzer_v2_error")
            should_generate = not (
                (current_result and current_result.get("signature") == signature)
                or (current_error and current_error.get("signature") == signature)
            )
        elif mode == "개인모드":
            st.markdown("**선택한 항목으로 분석**")
            should_generate = st.button(
                "보장 분석 시작",
                type="primary",
                disabled=not ready,
                use_container_width=True,
                key="analyzer_v2_run",
            )

    with st.container(key="analyzer_page_results"):
        st.markdown("### 02 · 분석 결과 및 다운로드")
        if should_generate:
            st.session_state.pop("analyzer_v2_result", None)
            st.session_state.pop("analyzer_v2_error", None)
            try:
                with st.spinner("고객 상담용 보장분석 엑셀을 만들고 있습니다..."):
                    result_bytes, filename, customer_name = build_analysis_file(
                        main_bytes,
                        selected_labels,
                    )
                st.session_state["analyzer_v2_result"] = {
                    "signature": signature,
                    "bytes": result_bytes,
                    "filename": filename,
                    "customer_name": customer_name,
                    "mode": mode,
                    "coverage_count": len(selected_labels),
                }
            except Exception as exc:
                from modules.shared.error_reporting import record_error, user_message
                reference = record_error(exc, "analyzer.export")
                st.session_state["analyzer_v2_error"] = {
                    "signature": signature,
                    "message": user_message(reference),
                    "reference": reference,
                }

        error = st.session_state.get("analyzer_v2_error")
        if error and error.get("signature") == signature:
            st.error(error["message"])
            if st.button("분석 다시 시도", key="analyzer_retry"):
                st.session_state.pop("analyzer_v2_error", None)
                st.rerun()

        result = st.session_state.get("analyzer_v2_result")
        if result and result.get("signature") == signature:
            st.success("보장 분석이 완료되었습니다.")
            col1, col2, col3 = st.columns(3)
            col1.metric("고객명", result["customer_name"])
            col2.metric("분석 모드", result["mode"])
            col3.metric("보장항목", f"{result['coverage_count']}개")
            st.download_button(
                "결과 엑셀 다운로드",
                data=result["bytes"],
                file_name=result["filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                key="analyzer_v2_download",
            )

        elif not error or error.get("signature") != signature:
            st.info("원본 파일을 업로드하면 결과를 확인할 수 있습니다." if not uploaded_main else "출력할 보장항목을 확인하고 보장 분석을 시작하세요.")

    tool_guide(
        "사용 방법 및 출력 기준",
        "전체 보장분석 엑셀을 고객 상담용 보장표로 자동 정리합니다.",
        [
            ("원본 업로드", "전체 보장내용이 포함된 컨설팅보장분석.xlsx 파일을 등록합니다."),
            ("분석 방식 선택", "간편모드는 기본 보장을 적용하고, 개인모드는 출력 항목을 직접 선택합니다."),
            ("결과 확인", "생성된 상담용 보장표를 확인하고 엑셀로 내려받습니다."),
        ],
        criteria="- A3 세로형, 너비 1페이지·높이 자동 맞춤으로 생성됩니다.\n- 페이지 하단에 현재 페이지와 전체 페이지 번호가 표시됩니다.",
        caution="필요한 경우 엑셀 인쇄 화면에서 방향·배율·페이지 나누기를 조정할 수 있습니다.",
    )


    page_footer("보장 분석 도우미", APP_VERSION)


if __name__ == "__main__":
    run()
