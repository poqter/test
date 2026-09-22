"""Common page frame and compatibility adapters for legacy drafts."""
from __future__ import annotations

import streamlit as st

from .app_registry import APP_BY_ID
from .session_store import (
    get_result,
    input_revision,
    reset_all_work,
    reset_page,
    restore_legacy_draft,
    save_legacy_draft,
)


STEPS = {
    "analyzer": ("원본 업로드", "인식·보장 확인", "고객용 결과"),
    "remodeling": ("기존·변경안 입력", "보험료·계약 변화", "비교안 다운로드"),
    "deposit_vs_shortpay": ("비교 조건 입력", "10년 가정 확인", "예상 결과 비교"),
    "renewal_vs_nonrenewal": ("현재·제안 조건", "갱신 가정", "총액·상세 비교"),
    "inheritance_tax": ("재산·공제 입력", "세액 확인", "납부재원 점검"),
    "insurance_claim_guide": ("청구 유형", "서류·담보 확인", "안내문 작성"),
    "silson_generation_comparison": ("현재·비교 조건", "의료비 예시", "보험료·보장 비교"),
    "convention": ("계약자료 등록", "확인·제외 내역", "달성·환산 결과"),
    "summer": ("계약자료 등록", "월별 필수조건", "보너스·결과"),
    "manager_results": ("실적자료 등록", "집계 대상 확인", "수금자별 결과"),
    "commission_calculator": ("예시표·계약 등록", "매칭·지급률 확인", "예상 수당"),
}


def save_page_draft(page: str) -> None:
    save_legacy_draft(page)


def restore_page_draft(page: str) -> None:
    restore_legacy_draft(page)


@st.dialog("이 도구만 초기화")
def reset_page_dialog(page: str) -> None:
    st.write("현재 도구에서 연결된 입력·계산 결과·업로드 참조를 비우고 홈으로 이동합니다. 다른 도구와 로그인 상태는 유지됩니다.")
    st.caption("다시 열면 새 작업으로 시작합니다. 필요한 결과는 먼저 내려받으세요.")
    st.button("이 도구만 초기화", type="primary", key="wb_reset_confirm", on_click=_reset_page_and_home, args=(page,))


@st.dialog("전체 작업 초기화")
def reset_all_dialog() -> None:
    st.write("모든 도구의 입력·계산 결과·업로드 참조를 초기화합니다. 로그인 상태는 유지됩니다.")
    st.button("전체 작업 초기화", type="primary", key="wb_reset_all_confirm", on_click=_reset_all_and_home)


def _reset_page_and_home(page: str) -> None:
    reset_page(page)
    st.session_state["active_app"] = "home"


def _reset_all_and_home() -> None:
    reset_all_work()
    st.session_state["active_app"] = "home"


def render_workbench(page: str, allowed: list[str], navigate) -> None:
    back, related, reset = st.columns([1, 2, 1])
    if back.button("← 홈으로", key="wb_home"):
        navigate("home")
    choices = [app_id for app_id in allowed if app_id != page]
    with related:
        selected = st.selectbox("다른 도구로 이동", choices, index=None, format_func=lambda app_id: APP_BY_ID[app_id].label, placeholder="도구 선택", key="wb_jump")
        if selected and st.button("선택한 도구 열기", key="wb_jump_go"):
            navigate(selected)
    if reset.button("이 도구만 초기화", key="wb_reset"):
        reset_page_dialog(page)
    with st.expander("작업 상태와 초기화 범위", expanded=False):
        result = get_result(page)
        st.caption(f"작성 내용 변경 횟수 · {input_revision(page)}")
        if result:
            state = "다시 계산 필요" if result.get("stale") else "최근 계산 결과와 현재 입력이 일치합니다."
            st.caption(state)
        else:
            st.caption("일부 기존 입력은 페이지 안에서만 유지됩니다. 파일 선택은 다시 열 때 복원되지 않을 수 있습니다.")
        if st.button("전체 작업 초기화 열기", key="wb_reset_all"):
            reset_all_dialog()
    if page in STEPS:
        st.markdown(
            '<div class="sig-steps">' + "".join(f'<span class="sig-step">{index} · {step}</span>' for index, step in enumerate(STEPS[page], 1)) + "</div>",
            unsafe_allow_html=True,
        )


def dataset_overview(raw, candidates, excluded, review, label):
    """Show reconciliation without changing any business calculation filter."""
    st.subheader("업로드 자료 확인")
    for column, title, value in zip(
        st.columns(4),
        ("원본 계약", "검토 후보", "기준상 제외", "후보 중 확인 필요"),
        (len(raw), len(candidates), len(excluded), len(review)),
    ):
        column.metric(title, f"{value:,}건")
    st.caption("원본 = 검토 후보 + 기준상 제외. 확인 필요 건은 검토 후보에 포함되며, 수정 후 최종 집계가 달라질 수 있습니다.")
    if len(raw) != len(candidates) + len(excluded):
        st.warning("원본과 분류 건수가 일치하지 않습니다. 아래 내역을 확인하세요.")
    with st.expander("입력 자료 열·일부 행 확인"):
        st.write(" · ".join(str(column) for column in raw.columns if not str(column).startswith("_")))
        st.dataframe(raw.head(10), hide_index=True, use_container_width=True)
