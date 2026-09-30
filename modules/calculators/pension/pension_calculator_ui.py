"""Retirement and pension calculator UI with core-first input grouping."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from modules.calculators.input_design import number_input
from modules.calculators.pension.pension_models import PensionPlan, calculate


def _required_number(label: str, *, key: str, value, max_value, min_value=0):
    return number_input(
        label,
        min_value=min_value,
        max_value=max_value,
        value=value,
        key=key,
    )


def run():
    st.caption("은퇴·연금 자금계획 · 현금흐름 및 추가 납입 세액공제 시뮬레이션")
    st.markdown(
        '<div class="hw-input-group-note">목표와 핵심 금액을 먼저 입력하고, 국민연금·수익률 가정·추가 저축 조건은 필요한 경우에만 조정하세요.</div>',
        unsafe_allow_html=True,
    )

    args: dict = {}
    labels: dict = {}
    tax_inputs: dict = {}

    from modules.calculators.input_design import input_panels as work_panels

    input_panel, result_panel = work_panels("pension_calculator_ui")
    with input_panel:
        st.caption("01 · 조건 입력")
        with st.container(key="pension_plan"):
            st.markdown("#### 핵심 입력")
            with st.container(key="hw_required_group_pp_core"):
                core_specs = [
                    ("age", "현재 나이", 45, 120),
                    ("retire", "은퇴 나이", 60, 120),
                    ("end", "자금 사용 종료 나이", 90, 120),
                    ("expense", "목표 월 생활비 (원)", 3_000_000, 10**12),
                ]
                for key, label, default, maximum in core_specs:
                    labels[key] = label
                    args[key] = _required_number(
                        label,
                        min_value=0,
                        max_value=maximum,
                        value=default,
                        key="pp_" + key,
                    )

                asset_mode = st.radio(
                    "은퇴시점 예상자산 계산 방식",
                    ("현재 자산·월 저축액으로 계산", "예상 적립액 직접 입력"),
                    horizontal=True,
                    key="pp_asset_mode",
                )
                if asset_mode == "예상 적립액 직접 입력":
                    labels["direct"] = "은퇴시점 예상자산 직접 입력 (오늘 가치·원)"
                    args["direct"] = _required_number(
                        labels["direct"],
                        min_value=0,
                        max_value=10**12,
                        value=200_000_000,
                        key="pp_direct",
                    )
                    # These values are ignored by the engine when ``direct`` is set.
                    args["assets"] = 80_000_000
                    args["saving"] = 500_000
                    args["saving_years"] = 15
                else:
                    args["direct"] = None
                    accumulation_specs = [
                        ("assets", "현재 연금자산 (원)", 80_000_000, 10**12),
                        ("saving", "월 저축액 (오늘 가치·원)", 500_000, 10**12),
                        ("saving_years", "저축 기간 (년)", 15, 120),
                    ]
                    for key, label, default, maximum in accumulation_specs:
                        labels[key] = label
                        args[key] = _required_number(
                            label,
                            min_value=0,
                            max_value=maximum,
                            value=default,
                            key="pp_" + key,
                        )

            with st.expander("국민연금 입력", expanded=False):
                pension_specs = [
                    ("pension", "예상 월 국민연금 (오늘 가치·원)", 1_100_000, 10**12),
                    ("normal_age", "국민연금 정상 개시 나이", 65, 65),
                    ("pension_start", "실제 수령 개시 나이", 65, 120),
                ]
                for key, label, default, maximum in pension_specs:
                    labels[key] = label
                    args[key] = number_input(
                        label,
                        min_value=0,
                        max_value=maximum,
                        value=default,
                        key="pp_" + key,
                    )
                args["adjust"] = st.checkbox(
                    "국민연금 조기·연기 수령률 적용",
                    value=True,
                    key="pp_adjust",
                )
                labels["adjust"] = "조기·연기 조정 적용"

            with st.expander("수익률·물가 가정 조정", expanded=False):
                args["expense_future"] = st.checkbox(
                    "목표 생활비를 은퇴시점의 명목금액으로 입력",
                    key="pp_expense_future",
                )
                labels["expense_future"] = "생활비 은퇴시점 가치 여부"
                for key, label, default in [
                    ("before_rate", "은퇴 전 연 수익률 (%)", 5.0),
                    ("after_rate", "은퇴 후 연 수익률 (%)", 3.5),
                    ("inflation", "연 물가상승률 (%)", 2.5),
                    ("pension_growth", "국민연금 수령 후 연 증가율 (%)", 2.5),
                ]:
                    labels[key] = label
                    args[key] = number_input(
                        label,
                        min_value=-99.0,
                        max_value=100.0,
                        value=default,
                        key="pp_" + key,
                        help="결과에 적용되는 가정입니다. 실제 수익률·물가·연금 변동과 다를 수 있습니다.",
                    )

            include_extra = st.checkbox(
                "추가 저축 시나리오 비교",
                value=True,
                key="pp_include_extra",
            )
            labels["추가 저축 시나리오 포함"] = "추가 저축 시나리오 포함"
            with st.expander("추가 저축·세액공제", expanded=include_extra):
                labels.update(
                    extra="추가 월 저축액 (오늘 가치·원)",
                    extra_years="추가 저축기간 (년)",
                    delay="시작 지연기간 (년)",
                )
                args["extra"] = number_input(
                    labels["extra"],
                    min_value=0,
                    max_value=10**12,
                    value=300_000,
                    key="pp_extra",
                    disabled=not include_extra,
                ) if include_extra else 0
                args["extra_years"] = number_input(
                    labels["extra_years"],
                    min_value=0,
                    max_value=120,
                    value=15,
                    key="pp_extra_years",
                    disabled=not include_extra,
                ) if include_extra else 0
                args["delay"] = number_input(
                    labels["delay"],
                    min_value=0,
                    max_value=120,
                    value=5,
                    key="pp_delay",
                    disabled=not include_extra,
                ) if include_extra else 5

                include_credit = st.checkbox(
                    "추가 납입액의 연금저축·IRP 세액공제도 계산",
                    value=False,
                    key="pp_include_credit",
                    disabled=not include_extra,
                ) if include_extra else False
                if include_credit:
                    st.caption("세액공제 입력은 추가 저축 시나리오에만 적용됩니다.")
                    for key, label, default in [
                        ("income", "연간 총급여 (근로소득만 있는 경우)", 60_000_000),
                        ("existing_pension", "기존 연금저축 연 납입액", 0),
                        ("existing_irp", "기존 IRP 연 납입액", 0),
                        ("extra_pension_annual", "추가 납입액 중 연금저축 연 배분액", 3_600_000),
                    ]:
                        labels[key] = label + " (원)"
                        tax_inputs[key] = number_input(
                            label + " (원)",
                            min_value=0,
                            max_value=10**12,
                            value=default,
                            key="pp_tax_" + key,
                        )

            submitted = st.button("계산하기", type="primary", width="stretch")

        if submitted:
            try:
                result = calculate(PensionPlan(**args))
                saved_inputs = dict(args)
                saved_inputs["추가 저축 시나리오 포함"] = include_extra
                if include_credit:
                    from modules.calculators.pension.pension_credit import attach

                    if not args["extra_years"]:
                        raise ValueError("세액공제 시뮬레이션은 추가 납입기간이 1년 이상이어야 합니다.")
                    result = attach(result, {**tax_inputs, "extra_monthly": args["extra"]})
                    saved_inputs.update(tax_inputs)
                saved_inputs["세액공제 계산 포함"] = include_credit
                st.session_state["pp_result"] = (
                    saved_inputs,
                    result,
                    datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M"),
                )
            except ValueError as exc:
                st.session_state.pop("pp_result", None)
                st.error(str(exc))

        stored = st.session_state.get("pp_result")
        if not stored:
            return

        current_inputs = dict(args)
        current_inputs["추가 저축 시나리오 포함"] = include_extra
        if include_credit:
            current_inputs.update(tax_inputs)
        current_inputs["세액공제 계산 포함"] = include_credit
        if stored[0] != current_inputs:
            st.info("입력 조건이 변경되었습니다. 다시 계산해주세요.")
            return

        saved, result = stored[:2]
        stamp = stored[2] if len(stored) > 2 else "이전 계산"
        labels.update(
            income="연간 총급여 (원)",
            existing_pension="기존 연금저축 연 납입액 (원)",
            existing_irp="기존 IRP 연 납입액 (원)",
            extra_pension_annual="추가 납입액 중 연금저축 연 배분액 (원)",
            **{
                "세액공제 계산 포함": "세액공제 계산 포함",
                "추가 저축 시나리오 포함": "추가 저축 시나리오 포함",
            },
        )
        from modules.calculators.calculator_exports import build_exports

        export_fields = [(labels.get(key, key), value, "입력", None) for key, value in saved.items()]
        _text, csv_data = build_exports("연금계산기", export_fields, list(saved.values()), result, stamp)

    with result_panel:
        st.caption("02 · 계산 결과")
        st.caption("계산 시각: " + stamp + " · 입력 변경 후 계산하기를 눌러 결과를 갱신하세요.")
        customer, advisor = st.container(), st.expander("산출 내역 자세히 보기")
        with customer:
            from modules.calculators.input_design import render_metrics

            render_metrics(result.display(), "pp")
            from modules.calculators.result_pdf import build_result_pdf, pdf_section_options

            pdf_options = pdf_section_options("pp_pdf_scope")
            if any(pdf_options.values()):
                pdf = build_result_pdf(
                    "연금계산기",
                    [(labels.get(key, key), value) for key, value in saved.items()],
                    result,
                    stamp,
                    **pdf_options,
                )
                st.download_button(
                    "결과 PDF 저장",
                    pdf,
                    file_name="연금계산_결과보고서.pdf",
                    mime="application/pdf",
                    type="primary",
                    icon=":material/download:",
                    width="stretch",
                )
            st.line_chart(
                [
                    {
                        "나이": float(row["나이"]),
                        "현재 계획 잔액": float(row["현재 계획 잔액"]),
                        "추가 납입 후 잔액": float(row["추가 납입 후 잔액"]),
                    }
                    for row in result.rows
                ],
                x="나이",
                y=["현재 계획 잔액", "추가 납입 후 잔액"],
            )
        with advisor:
            for note in result.assumptions:
                st.caption(note)
            st.write(result.formula)
            st.caption("국민연금 개시연령·조기/연기 비율: 국민연금공단 안내 대조 2026-09-26.")
            st.markdown("[국민연금공단 제도 안내](https://www.nps.or.kr/pnsinfo/ntpsklg/getOHAF0100M0.do)")
            rows = [{"항목": labels.get(key, key), "입력": str(value)} for key, value in saved.items()]
            st.dataframe(rows, hide_index=True)
            st.dataframe([{key: float(value) for key, value in row.items()} for row in result.rows], hide_index=True)
            st.download_button(
                "상세 계산 CSV 저장",
                csv_data,
                file_name="연금계산_상세.csv",
                mime="text/csv",
            )

    from modules.calculators.input_design import jump_to_result

    jump_to_result(submitted, "pension_calculator_ui")
