
# Stable facade: UI only; engines/parsers/exports are independently testable.
from modules.performance.summer_core import (
    APP_VERSION,
    MONTHLY_TARGET,
    MONTHLY_HANWHA_MIN_PREMIUM,
    READY_BONUS_RATES,
    READY_BONUS_BY_COLLECTOR,
    SUMMER_GRADES,
    TABLE_SEQ,
    mark,
    won,
    signed_won,
    pct,
    normalize_columns,
    standardize_columns,
    parse_payment_period,
    normalize_collector_code,
    get_ready_bonus_rate,
    safe_table_name,
    safe_filename_part,
    unique_sheet_name,
    autosize_columns_full,
    is_hanwha_life_series,
    is_db_nonlife_series,
    is_kb_nonlife_series,
    is_hanwha_nonlife_series,
    is_heungkuk_nonlife_series,
    is_special_nonlife_series,
    is_nonlife_series,
    is_life_series,
    is_other_life_series,
    load_df,
    exclude_contracts,
    find_data_issues,
    build_review_display,
    build_excluded_with_reason,
    check_required_columns,
    compute_summer,
    check_monthly_requirements,
    get_summer_grade,
    get_next_grade_gap,
    check_final_summer_requirements,
    to_styled,
    style_detail_table,
    adjustment_summary,
    make_collector_summary,
    format_summary_for_display,
    filter_by_collector,
    filter_excluded_by_collector,
)

from modules.performance.summer_exports import (
    excel_safe_value,
    write_table,
    write_title,
    write_final_result_block,
    build_workbook,
)

import streamlit as st
from modules.shared.upload_ui import guarded_upload
import pandas as pd
import numpy as np
import os
import re
import hashlib
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.table import Table, TableStyleInfo
from modules.shared.ui_components import page_footer, page_header, section_intro


# ── 썸머 기준 ────────────────────────────────────────────────


# 회사 레디포썸머 명단: 수금자코드와 수금자명이 모두 일치할 때만 자동 적용합니다.


# ── 기본 유틸 ────────────────────────────────────────────────


# ── 보험사 분류 ───────────────────────────────────────────────


# ── 데이터 준비 ──────────────────────────────────────────────


# ── 썸머 계산 ────────────────────────────────────────────────


# ── 화면 표시 ────────────────────────────────────────────────


def render_adjustment_summary(dfin: pd.DataFrame, title="쉐어 조정 요약"):
    summary = adjustment_summary(dfin)
    st.markdown(f"#### {title}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("원본 계속보험료 합계", won(summary["원본"]))
    c2.metric("50% 조정 보험료 합계", won(summary["조정"]), signed_won(summary["차액"]))
    c3.metric("증가액 / 감소액", f"+{summary['증가']:,.0f} / {summary['감소']:,.0f} 원")
    c4.metric("쉐어 적용 계약", f"{summary['쉐어건수']:,}건")


def money_box(title, value, color="#ff9800"):
    return f"""
    <div style='border: 2px solid {color}; border-radius: 10px; padding: 18px; background-color: #fff8e1; margin-bottom: 12px;'>
        <h4 style='color:{color}; margin:0 0 8px 0;'>{title}</h4>
        <p style='font-size:20px; font-weight:bold; margin:0;'>{value:,.0f} 원</p>
    </div>
    """


def bonus_box(base_amount, bonus_rate, bonus_amount, final_amount):
    return f"""
    <div style='border: 2px solid #6f42c1; border-radius: 10px; padding: 18px; background-color: #f3ecff; margin-bottom: 12px;'>
        <h4 style='color:#6f42c1; margin:0 0 10px 0;'>🎁 레디포썸머 보너스 반영</h4>
        <p style='margin:4px 0;'><strong>기본 썸머 환산업적:</strong> {base_amount:,.0f} 원</p>
        <p style='margin:4px 0;'><strong>보너스율:</strong> {bonus_rate:.0f} %</p>
        <p style='margin:4px 0;'><strong>보너스 가산금액:</strong> {bonus_amount:,.0f} 원</p>
        <p style='font-size:20px; font-weight:bold; margin:10px 0 0 0; color:#6f42c1;'>
            보너스 반영 최종 환산업적: {final_amount:,.0f} 원
        </p>
    </div>
    """


def grade_box(final_grade, amount_grade, base_amount, bonus_rate, bonus_amount, final_amount, monthly_ok):
    if final_grade == "필수조건 미충족":
        color = "#b80000"
        bg = "#fdecea"
    elif final_grade == "미달성":
        color = "#b80000"
        bg = "#fdecea"
    elif final_grade in ["일반", "더블"]:
        color = "#0c6b2c"
        bg = "#e6f4ea"
    elif final_grade in ["트리플", "크라운"]:
        color = "#7a4b00"
        bg = "#fff4d6"
    else:
        color = "#4b0082"
        bg = "#f0e6ff"

    monthly_text = "월별 필수조건 충족" if monthly_ok else "월별 필수조건 미충족"

    return f"""
    <div style='border: 2px solid {color}; border-radius: 12px; padding: 20px; background-color: {bg}; margin-bottom: 16px;'>
        <h3 style='color:{color}; margin:0 0 10px 0;'>최종 인정 등급: {final_grade}</h3>
        <p style='margin:4px 0;'><strong>기본 썸머 환산업적:</strong> {base_amount:,.0f} 원</p>
        <p style='margin:4px 0;'><strong>레디포썸머 보너스율:</strong> {bonus_rate:.0f} %</p>
        <p style='margin:4px 0;'><strong>레디포썸머 보너스금액:</strong> {bonus_amount:,.0f} 원</p>
        <p style='font-size:20px; font-weight:bold; margin:8px 0;'>보너스 반영 최종 환산업적: {final_amount:,.0f} 원</p>
        <p style='font-weight:bold; margin:4px 0;'>금액 기준 등급: {amount_grade}</p>
        <p style='font-weight:bold; margin:4px 0;'>월별 필수조건: {monthly_text}</p>
    </div>
    """


def gap_box(title, amount):
    if amount > 0:
        color = "#e6f4ea"
        txt = "#0c6b2c"
        sym = f"+{amount:,.0f} 원 초과"
    elif amount < 0:
        color = "#fdecea"
        txt = "#b80000"
        sym = f"{amount:,.0f} 원 부족"
    else:
        color = "#f3f3f3"
        txt = "#000000"
        sym = "기준 달성"

    return f"""
    <div style='border: 1px solid {txt}; border-radius: 8px; background-color: {color}; padding: 12px; margin: 10px 0;'>
        <strong style='color:{txt};'>{title}: {sym}</strong>
    </div>
    """


def req_box(title, ok):
    color = "#e6f4ea" if ok else "#fdecea"
    txt = "#0c6b2c" if ok else "#b80000"
    mark_txt = "✅ 충족" if ok else "❌ 미충족"

    return f"""
    <div style='border: 1px solid {txt}; border-radius: 8px; background-color: {color}; padding: 12px; margin: 10px 0;'>
        <strong style='color:{txt};'>{title}: {mark_txt}</strong>
    </div>
    """


# ── 선택 수금자 필터 ─────────────────────────────────────────


# ── 엑셀 출력 ────────────────────────────────────────────────


# ── 탭 렌더링 함수 ───────────────────────────────────────────
def render_result_tabs(summary_df, july_df, august_df, other_month_df):
    tab1, tab2, tab3, tab4 = st.tabs(["🧮 수금자별 요약", "7월 상세", "8월 상세", "7월/8월 외"])

    with tab1:
        st.dataframe(format_summary_for_display(summary_df), use_container_width=True)

    with tab2:
        if july_df.empty:
            st.info("7월 계약이 없습니다.")
        else:
            st.dataframe(style_detail_table(july_df), use_container_width=True)

    with tab3:
        if august_df.empty:
            st.info("8월 계약이 없습니다.")
        else:
            st.dataframe(style_detail_table(august_df), use_container_width=True)

    with tab4:
        if other_month_df.empty:
            st.info("7월/8월 외 계약이 없습니다.")
        else:
            st.dataframe(style_detail_table(other_month_df), use_container_width=True)


# ── 메인 실행 ────────────────────────────────────────────────
def run():
    page_header("실적 관리", "썸머 계산기", "계약일 기준으로 7월과 8월을 분리해 썸머 업적과 최종 등급을 계산합니다.", "SU")

    with st.expander("사용 방법 및 실적 환산 기준", expanded=False):
        st.markdown("#### 사용 순서")
        st.markdown(
            """
            **🖥️ 한화라이프랩 전산**  
            **- 📂 계약관리**  
            **- 📑 보유계약 장기**  
            **- ⏱️ 기간 설정**  
            **- 💾 엑셀 다운로드 후 파일 첨부**
            """
        )

        st.divider()

        st.markdown("#### 월별 필수조건")
        st.markdown(
            f"""
            - 7월: 전체 환산업적 **{MONTHLY_TARGET:,.0f}원 이상**
            - 7월: 한화생명 환산업적 합계 **{MONTHLY_HANWHA_MIN_PREMIUM:,.0f}원 이상**
            - 7월: 한화생명 인정 건수 **1건 이상**
            - 8월: 전체 환산업적 **{MONTHLY_TARGET:,.0f}원 이상**
            - 8월: 한화생명 환산업적 합계 **{MONTHLY_HANWHA_MIN_PREMIUM:,.0f}원 이상**
            - 8월: 한화생명 인정 건수 **1건 이상**
            """
        )

        st.markdown("#### 레디포썸머 보너스")
        st.markdown(
            """
            - 수금자코드와 수금자명이 회사 명단과 일치하면 보너스율 자동 선택
            - 자동 선택된 보너스율은 직접 변경 가능
            - 선택 가능: 0%, 15%, 20%, 25%, 30%
            - 등급 판정은 보너스 반영 후 금액 기준
            - 월별 필수조건은 보너스 전 기준으로 판단
            """
        )

        st.markdown("#### 최종 합산 등급")
        st.markdown(
            """
            - 일반: 300만원 이상
            - 더블: 500만원 이상
            - 트리플: 800만원 이상
            - 크라운: 1,000만원 이상
            - HWARANG: 1,500만원 초과
            """
        )

        st.markdown("#### 환산율")
        st.markdown(
            """
            **손해보험**
            - 10년납 초과: 흥국/한화/KB/DB 250%
            - 10년납 초과: 이외 손해/화재 100%
            - 10년납 이하: 흥국/한화/KB/DB 100%
            - 10년납 이하: 이외 손해/화재 50%

            **생명보험**
            - 10년납 초과: 한화생명 150%
            - 10년납 초과: 이외 생명보험 100%
            - 10년납 이하: 한화생명 100%
            - 10년납 이하: 이외 생명보험 50%

            **예외 및 쉐어 기준**
            - 상품명 또는 상품군에 `치아`가 포함되면 보험사와 관계없이 10년납 초과 구간 적용
            - 원본 계속보험료는 해당 FP의 원래 쉐어율이 이미 반영된 귀속금액으로 간주
            - 공동계약은 귀속 계속보험료와 쉐어율로 전체 보험료를 역산
            - 공동계약은 원래 쉐어율과 관계없이 50% 보험료·0.5건으로 통일
            - 쉐어율 공란은 100% 단독계약으로 적용
            - 조정 실적보험료의 원 미만 금액은 반올림하지 않고 버림
            """
        )

        st.markdown(
            """
            **🚫 제외 기준**  
            - 일시납  
            - 연금성 / 저축성  
            - 본인계약  
            - 계약상태가 정상이 아닌 모든 계약
            """
        )

    with st.container(key="hw_surface_summer_0"):
        st.caption("01 · 계약자료 업로드")
        section_intro("입력", "계약자료 불러오기", "7월과 8월 계약이 포함된 보유계약 엑셀 파일을 등록해 주세요.")
        uploaded_file = guarded_upload(
            "📂 썸머 계산용 Excel 파일 업로드 (.xlsx)",
            type=["xlsx"],
            key="summer_one_file",
        )

        if uploaded_file is None:
            st.caption("파일을 등록하면 자료 확인과 집계 단계가 표시됩니다.")
            return

        base_filename = os.path.splitext(uploaded_file.name)[0]

    with st.container(key="hw_surface_summer_1"):
        st.caption("02 · 인정 조건 · 계약 검토")
        file_bytes = uploaded_file.getvalue()

        try:
            raw = load_df(BytesIO(file_bytes)).copy()
        except Exception as e:
            st.error("자료 처리에 실패했습니다. 파일 형식과 입력 내용을 확인한 뒤 다시 시도해 주세요. [PROCESS_FAILED]")
            return

        missing = check_required_columns(raw)

        if missing:
            st.error(
                "❌ 업로드된 파일에 다음 항목이 필요합니다:\n\n"
                + ", ".join(sorted(missing))
            )
            return

        raw["_원본행번호"] = raw.index + 2
        candidate_df, excluded_df = exclude_contracts(raw)
        blocking_issues, condition_issues, _ = find_data_issues(candidate_df)
        initial_review_mask = blocking_issues.ne("") | condition_issues.ne("")
        initial_review = candidate_df[initial_review_mask].copy()
        from modules.shared.workbench import dataset_overview
        dataset_overview(raw, candidate_df, excluded_df, initial_review, '썸머')

        if not initial_review.empty:
            initial_review["확인사항"] = blocking_issues.loc[initial_review.index]
            condition_only = condition_issues.loc[initial_review.index]
            initial_review["확인사항"] = initial_review.apply(
                lambda row: " / ".join(
                    part for part in [row["확인사항"], condition_only.loc[row.name]] if part
                ),
                axis=1,
            )
            editor_columns = [
                "_원본행번호", "수금자명", "계약일자", "보험사", "상품명",
                "납입기간", "계속보험료", "쉐어율", "납입방법", "상품군1", "상품군2",
                "계약상태", "본인계약", "확인사항",
            ]

            st.warning(
                f"입력값을 확인해야 하는 계약이 {len(initial_review):,}건 있습니다. "
                "표에서 직접 수정한 뒤 적용할 수 있습니다."
            )
            with st.expander("📝 확인 필요 계약 수정", expanded=True):
                with st.form("summer_review_editor_form"):
                    edited_review = st.data_editor(
                        initial_review[editor_columns].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True,
                        disabled=["_원본행번호", "상품명", "확인사항"],
                        key=f"summer_review_{hashlib.sha256(file_bytes).hexdigest()[:16]}",
                    )
                    corrections_submitted = st.form_submit_button(
                        "수정값 적용", type="primary", use_container_width=True
                    )

            editable_columns = [
                "수금자명", "계약일자", "보험사", "납입기간", "계속보험료",
                "쉐어율", "납입방법", "상품군1", "상품군2", "계약상태", "본인계약",
            ]
            for _, edited_row in edited_review.iterrows():
                row_mask = candidate_df["_원본행번호"] == edited_row["_원본행번호"]
                for column in editable_columns:
                    candidate_df.loc[row_mask, column] = edited_row[column]

            if corrections_submitted:
                st.success("입력한 수정값을 다시 검증하여 반영했습니다.")

        candidate_df, newly_excluded_df = exclude_contracts(candidate_df)
        if not newly_excluded_df.empty:
            excluded_df = pd.concat([excluded_df, newly_excluded_df]).sort_index()

        blocking_issues, condition_issues, share_numeric = find_data_issues(candidate_df)
        blocked_df = candidate_df[blocking_issues.ne("")].copy()
        if not blocked_df.empty:
            blocked_df["확인사항"] = blocking_issues.loc[blocked_df.index]
            blocked_df["반영상태"] = "계산 보류"

        condition_mask = blocking_issues.eq("") & condition_issues.ne("")
        condition_df = candidate_df[condition_mask].copy()
        if not condition_df.empty:
            condition_df["확인사항"] = condition_issues.loc[condition_df.index]
            condition_df["반영상태"] = "금액 반영 · 인정 건수 보류"

        review_df = pd.concat([blocked_df, condition_df]).sort_index()
        review_disp_all = build_review_display(review_df)
        df_valid = candidate_df[blocking_issues.eq("")].copy()
        df_valid.loc[:, "쉐어율"] = share_numeric.loc[df_valid.index]
        excluded_disp = build_excluded_with_reason(excluded_df)

        upload_key = hashlib.sha256(file_bytes).hexdigest()[:16]

        # 쉐어율 공란은 별도 확인 화면 없이 100% 단독계약으로 적용합니다.
        df_valid["_공란적용쉐어율"] = 100.0

        # 상품명 또는 상품군2에 '치아'가 있으면 기본 체크하고, 해제 시 즉시 일반 납기 기준으로 계산합니다.
        product_name = df_valid["상품명"].fillna("").astype(str)
        product_group = df_valid["상품군2"].fillna("").astype(str)
        dental_mask = product_name.str.contains("치아", na=False) | product_group.str.contains("치아", na=False)
        df_valid["_치아보험예외적용"] = False
        dental_df = df_valid[dental_mask].copy()
        st.markdown(f"#### 치아보험 확인 대상 {len(dental_df):,}건")
        if dental_df.empty:
            st.info("상품명 또는 상품군에 '치아'가 포함된 계약이 없습니다.")
        else:
            st.caption("체크된 계약은 실제 납입기간과 관계없이 10년납 초과 환산율을 적용합니다.")
            dental_editor = dental_df[
                ["_원본행번호", "수금자명", "보험사", "상품명", "상품군2", "납입기간"]
            ].copy()
            dental_editor["치아보험 예외 적용"] = True
            dental_editor = st.data_editor(
                dental_editor.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
                disabled=["_원본행번호", "수금자명", "보험사", "상품명", "상품군2", "납입기간"],
                column_config={
                    "치아보험 예외 적용": st.column_config.CheckboxColumn(
                        "치아보험 예외 적용", default=True
                    )
                },
                key=f"summer_dental_check_{upload_key}",
            )
            for _, edited_row in dental_editor.iterrows():
                row_mask = df_valid["_원본행번호"] == edited_row["_원본행번호"]
                df_valid.loc[row_mask, "_치아보험예외적용"] = bool(edited_row["치아보험 예외 적용"])

        if not blocked_df.empty:
            st.warning(
                f"중요 항목을 확인할 수 없는 계약 {len(blocked_df):,}건은 계산에서 제외했습니다."
            )
        if not condition_df.empty:
            st.info(
                f"조건을 확인해야 하는 계약 {len(condition_df):,}건이 있습니다."
            )
        if not review_disp_all.empty:
            with st.expander("⚠️ 아직 확인이 필요한 계약", expanded=False):
                st.dataframe(review_disp_all, use_container_width=True, hide_index=True)

        if df_valid.empty:
            st.warning("계산에 포함할 수 있는 정상 계약이 없습니다. 확인 필요 계약을 수정해 주세요.")
            return

        df = compute_summer(df_valid)

        july_df = df[df["계약월"] == 7].copy()
        august_df = df[df["계약월"] == 8].copy()
        other_month_df = df[~df["계약월"].isin([7, 8])].copy()

        if july_df.empty:
            st.warning("⚠️ 계약일 기준 7월 계약이 없습니다.")

        if august_df.empty:
            st.warning("⚠️ 계약일 기준 8월 계약이 없습니다.")

        if not other_month_df.empty:
            st.info(
                f"ℹ️ 7월/8월 외 계약 {len(other_month_df)}건이 있습니다. "
                "이 계약들은 썸머 최종 조건 계산에서는 제외하고, 엑셀에는 별도 시트로 저장합니다."
            )

        # 전체 기준 결과: 보너스율 0% 기준
        total_result = check_final_summer_requirements(
            july_df,
            august_df,
            ready_bonus_rate=0,
        )
        total_summary = make_collector_summary(july_df, august_df)

        # 1. 제외 계약 보기 - 기본 펼침
        if excluded_disp is not None and not excluded_disp.empty:
            st.warning(
                f"⚠️ 제외된 계약 {len(excluded_disp)}건이 있습니다. "
                "제외 조건: 일시납 / 연금성·저축성 / 본인계약 / 정상 외 계약상태"
            )

            with st.expander("🚫 제외된 계약 보기", expanded=True):
                st.dataframe(excluded_disp, use_container_width=True)
        else:
            with st.expander("🚫 제외된 계약 보기", expanded=True):
                st.info("제외된 계약이 없습니다.")

    # 2. 전체 환산 결과
    with st.container(key="hw_surface_summer_2"):
        st.caption("03 · 월별 실적 · 등급 · 엑셀")
        section_intro("전체 결과", "썸머 환산 결과", "반영 계약과 제외 계약을 포함한 전체 계산 결과입니다.")
        render_adjustment_summary(df, "전체 쉐어 조정 요약")
        render_result_tabs(
            summary_df=total_summary,
            july_df=july_df,
            august_df=august_df,
            other_month_df=other_month_df,
        )

        # 3. 수금자별 결과 확인
        section_intro("상세 결과", "수금자별 결과 확인", "수금자를 선택해 월별 실적과 보너스 적용 결과를 확인해 주세요.")

        collectors = ["전체"] + sorted(df["수금자명"].astype(str).dropna().unique().tolist())

        selected_collector = st.selectbox(
            "👤 확인할 수금자를 선택하세요.",
            collectors,
            index=0,
            key="summer_selected_collector",
        )

        auto_bonus_rate, auto_bonus_source = get_ready_bonus_rate(df, selected_collector)
        bonus_identity_key = f"{selected_collector}|{auto_bonus_rate}|{upload_key}"
        if st.session_state.get("summer_bonus_identity_key") != bonus_identity_key:
            st.session_state["summer_ready_bonus_rate"] = auto_bonus_rate
            st.session_state["summer_bonus_identity_key"] = bonus_identity_key

        ready_bonus_rate = st.selectbox(
            "🎁 레디포썸머 보너스율을 선택하세요.",
            READY_BONUS_RATES,
            format_func=lambda x: f"{x}%",
            key="summer_ready_bonus_rate",
        )
        bonus_selection_source = (
            auto_bonus_source if ready_bonus_rate == auto_bonus_rate else "사용자 수동 변경"
        )
        st.caption(
            f"{bonus_selection_source}: {ready_bonus_rate}% "
            f"(자동 기준 {auto_bonus_rate}%)"
        )

        selected_df = filter_by_collector(df, selected_collector)
        selected_july_df = filter_by_collector(july_df, selected_collector)
        selected_august_df = filter_by_collector(august_df, selected_collector)
        selected_other_month_df = filter_by_collector(other_month_df, selected_collector)

        selected_summary = make_collector_summary(selected_july_df, selected_august_df)

        selected_result = check_final_summer_requirements(
            selected_july_df,
            selected_august_df,
            ready_bonus_rate=ready_bonus_rate,
        )

        selected_excluded_disp = filter_excluded_by_collector(excluded_disp, selected_collector)
        selected_review_disp = filter_excluded_by_collector(review_disp_all, selected_collector)

        st.markdown(f"### 📌 선택 기준: {selected_collector}")
        st.caption(f"레디포썸머 보너스율: {ready_bonus_rate}% · {bonus_selection_source}")

        st.info(
            "업로드 파일의 계속보험료는 해당 FP의 원래 쉐어율이 반영된 귀속금액입니다. "
            "공동계약은 전체 보험료를 역산한 뒤 내부 인정 기준에 따라 "
            "50% 보험료·0.5건으로 재산정합니다."
        )

        render_adjustment_summary(selected_df, f"{selected_collector} 쉐어 조정 요약")

        render_result_tabs(
            summary_df=selected_summary,
            july_df=selected_july_df,
            august_df=selected_august_df,
            other_month_df=selected_other_month_df,
        )

        # 4. 선택값 기준 월별 필수조건 체크
        st.subheader("✅ 월별 필수조건 체크")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 7월")
            st.markdown(
                money_box("7월 환산업적", selected_result["7월"]["환산금액"]),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box(
                    f"7월 한화생명 환산업적 합계 {MONTHLY_HANWHA_MIN_PREMIUM:,.0f}원 이상",
                    selected_result["7월"]["한화생명5만"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box(
                    f"7월 한화생명 인정 건수 1건 이상 "
                    f"(현재 {selected_result['7월']['한화생명인정건수']:g}건)",
                    selected_result["7월"]["한화생명1건"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box(
                    f"7월 환산업적 {MONTHLY_TARGET:,.0f}원 이상",
                    selected_result["7월"]["환산50만"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box("7월 필수조건 전체", selected_result["7월"]["월달성"]),
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown("### 8월")
            st.markdown(
                money_box("8월 환산업적", selected_result["8월"]["환산금액"]),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box(
                    f"8월 한화생명 환산업적 합계 {MONTHLY_HANWHA_MIN_PREMIUM:,.0f}원 이상",
                    selected_result["8월"]["한화생명5만"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box(
                    f"8월 한화생명 인정 건수 1건 이상 "
                    f"(현재 {selected_result['8월']['한화생명인정건수']:g}건)",
                    selected_result["8월"]["한화생명1건"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box(
                    f"8월 환산업적 {MONTHLY_TARGET:,.0f}원 이상",
                    selected_result["8월"]["환산50만"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                req_box("8월 필수조건 전체", selected_result["8월"]["월달성"]),
                unsafe_allow_html=True,
            )

        st.markdown(
            req_box("7월·8월 월별 필수조건 전체", selected_result["월별필수조건"]),
            unsafe_allow_html=True,
        )

        # 5. 레디포썸머 보너스 반영 결과
        st.subheader("🎁 레디포썸머 보너스 반영 결과")

        st.markdown(
            bonus_box(
                selected_result["기본합산환산금액"],
                selected_result["레디포썸머보너스율"],
                selected_result["레디포썸머보너스금액"],
                selected_result["합산환산금액"],
            ),
            unsafe_allow_html=True,
        )

        # 6. 선택값 기준 썸머 최종 결과
        section_intro("최종 결과", "썸머 최종 등급", "월별 필수조건과 보너스를 모두 반영한 최종 결과입니다.")

        st.markdown(
            grade_box(
                selected_result["최종인정등급"],
                selected_result["금액기준등급"],
                selected_result["기본합산환산금액"],
                selected_result["레디포썸머보너스율"],
                selected_result["레디포썸머보너스금액"],
                selected_result["합산환산금액"],
                selected_result["월별필수조건"],
            ),
            unsafe_allow_html=True,
        )

        if selected_result["다음등급"]:
            st.markdown(
                gap_box(
                    f"다음 등급 {selected_result['다음등급']}({selected_result['다음등급기준']:,.0f}원)까지",
                    -selected_result["다음등급부족금액"],
                ),
                unsafe_allow_html=True,
            )
        else:
            st.success("🎉 최고 등급 HWARANG 기준을 달성했습니다.")

        # 7. 엑셀 다운로드
        # 선택 기준에 따라 다운로드 데이터 분기
        # - 전체 선택: 전체 다운로드
        # - 수금자 선택: 해당 수금자만 다운로드
        # - 제외계약도 선택 기준에 맞게 필터링
        # - 선택한 보너스율이 엑셀 결과에 반영
        file_collector_name = safe_filename_part(selected_collector)
        download_filename = f"{base_filename}_썸머환산결과_{file_collector_name}.xlsx"

        wb = build_workbook(
            df_all=selected_df,
            july_df=selected_july_df,
            august_df=selected_august_df,
            other_month_df=selected_other_month_df,
            summary=selected_summary,
            result=selected_result,
            excluded_disp=selected_excluded_disp,
            review_disp=selected_review_disp,
            selected_collector=selected_collector,
        )

        excel_output = BytesIO()
        wb.save(excel_output)
        excel_output.seek(0)

        st.download_button(
            label=f"📥 {selected_collector} 썸머 환산 결과 엑셀 다운로드",
            data=excel_output,
            file_name=download_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    page_footer("썸머 계산기", APP_VERSION)
