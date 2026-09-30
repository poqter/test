"""Insurance basics and living-fund calculators with the shared Calculator UX."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from modules.calculators.calculator_catalog import MODES
from modules.calculators.calculator_core import calculate
from modules.calculators.legacy_calculator_exports import export_bytes, formatted_results
from modules.consultation.consultation_documents import fingerprint
from modules.shared.session_store import commit_input, input_revision, save_result
from modules.shared.ui_components import page_header
from modules.shared.workspace_tools import field


_GROUP_VISUALS = {
    "전체": "🧮",
    "보험 기본": "🧾",
    "생활과 보장": "🛡️",
    "미래 준비": "🎯",
}

# 만원 단위 입력 중 실제 보험료처럼 1만원 미만 단위가 자주 필요한 항목만
# 0.01만원(100원) 단위까지 허용합니다. 정수값은 10.00이 아니라 10으로 표시합니다.
_DECIMAL_MONEY_FIELDS = frozenset({
    ("total", "premium"),
    ("waiver", "premium"),
})

# Streamlit number_input은 printf 형식을 지원합니다. %g 계열을 사용하면
# 10.00 → 10, 10.50 → 10.5, 10.25 → 10.25처럼 불필요한 0만 숨길 수 있습니다.
_FLEXIBLE_NUMBER_FORMAT = "%.12g"


@st.dialog("계산 가정과 입력 단위", width="large")
def assumptions_dialog(formula: str, assumptions: str) -> None:
    st.subheader("계산 근거")
    st.write(formula)
    st.subheader("가정과 미반영 조건")
    st.write(assumptions)
    st.caption("금액 입력은 만원, 결과는 원 단위로 표시합니다. 수익률·물가율은 사용자 시나리오입니다.")


def run() -> None:
    from modules.calculators.jarvia_calculator_center import run as run_new

    run_new(run_legacy=lambda: run_legacy(integrated=True))


def _format_group(group: str) -> str:
    return f"{_GROUP_VISUALS.get(group, '🧮')} {group}"


def _mode_core_text(kind: str, fields: list[tuple]) -> str:
    if kind in ("age", "change"):
        return "생년월일, 기준일"
    labels = [label for _key, label, field_type, _default, _low, _high in fields if field_type != "rate"]
    if len(labels) <= 4:
        return ", ".join(labels)
    return ", ".join(labels[:4]) + " 등"


def _set_widget_value(key: str, value: object) -> None:
    """Update the durable value and the current field widget in one callback."""
    st.session_state[key] = value
    st.session_state["_ws_" + key] = value
    commit_input("quick_calculators", key, value)


def _money_allows_decimals(kind: str, key: str) -> bool:
    return (kind, key) in _DECIMAL_MONEY_FIELDS


def _normalize_numeric_widget_state(widget_key: str, *, decimals: bool) -> None:
    """Keep existing sessions compatible when an input changes float/int type."""
    quantum = Decimal(".01") if decimals else Decimal("1")
    for state_key in (widget_key, "_ws_" + widget_key):
        if state_key not in st.session_state:
            continue
        try:
            number = Decimal(str(st.session_state[state_key])).quantize(quantum, rounding=ROUND_HALF_UP)
        except Exception:
            continue
        st.session_state[state_key] = float(number) if decimals else int(number)


def _set_mode_inputs(kind: str, fields: list[tuple], *, example: bool) -> None:
    if kind in ("age", "change"):
        birth = date(1990, 1, 1) if example else date.today()
        _set_widget_value("a_birth", birth)
        _set_widget_value("a_reference", date.today())
    else:
        for key, _label, field_type, default, _low, _high in fields:
            decimal_value = field_type == "rate" or (
                field_type == "money" and _money_allows_decimals(kind, key)
            )
            if example:
                value = float(default) if decimal_value else int(default)
            else:
                value = 0.0 if decimal_value else 0
            _set_widget_value(f"a_{kind}_{key}", value)
    st.session_state.pop("a_calculation", None)
    st.session_state.pop("a_review_token", None)


def _format_compact_decimal(value: Decimal, *, grouped: bool = False) -> str:
    """Hide only unnecessary trailing zeros while preserving up to 2 decimals."""
    rendered = f"{value:,.2f}" if grouped else f"{value:.2f}"
    return rendered.rstrip("0").rstrip(".")


def _format_manwon(value: Decimal) -> str:
    return f"{_format_compact_decimal(value, grouped=True)}만원"


def _render_amount_words(won: Decimal) -> None:
    from modules.calculators.input_design import amount_words

    st.markdown(
        '<div style="font-size:12px;color:#426e98;text-align:right;margin-top:-8px">'
        + escape(amount_words(won))
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_input(entry: tuple, kind: str) -> tuple[object, str]:
    key, label, field_type, default, low, high = entry
    widget_key = f"a_{kind}_{key}"
    if field_type == "money":
        allow_decimals = _money_allows_decimals(kind, key)
        _normalize_numeric_widget_state(widget_key, decimals=allow_decimals)
        if allow_decimals:
            value = field(
                "number_input",
                label + " (만원)",
                widget_key,
                float(default),
                min_value=float(low),
                max_value=float(high),
                step=0.01,
                format=_FLEXIBLE_NUMBER_FORMAT,
                help=(
                    "기본 정수 금액은 소수점 없이 표시하고, 필요한 경우에만 "
                    "0.01만원(100원) 단위까지 입력할 수 있습니다."
                ),
            )
            raw = Decimal(str(value)).quantize(Decimal(".01"))
        else:
            value = field(
                "number_input",
                label + " (만원)",
                widget_key,
                int(default),
                min_value=int(low),
                max_value=int(high),
                step=1,
                format="%d",
                help="만원 단위 정수로 입력합니다.",
            )
            raw = Decimal(int(value))
        won = raw * 10_000
        _render_amount_words(won)
        return won, f"{_format_manwon(raw)} ({int(won):,}원)"
    if field_type == "rate":
        value = field(
            "number_input",
            label,
            widget_key,
            float(default),
            min_value=float(low),
            max_value=float(high),
            step=0.1,
            format=_FLEXIBLE_NUMBER_FORMAT,
            help="정수 비율은 소수점 없이 표시하며, 필요한 경우 소수 비율을 입력할 수 있습니다.",
        )
        raw = Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        return raw / 100, f"{_format_compact_decimal(raw)}%"
    value = field(
        "number_input",
        label,
        widget_key,
        default,
        min_value=low,
        max_value=high,
        step=1,
    )
    return value, f"{int(value):,}"


def _condition_summary(inputs: list[tuple[str, str]]) -> str:
    shown = [f"{escape(label)} {escape(value)}" for label, value in inputs[:4]]
    if len(inputs) > 4:
        shown.append(f"외 {len(inputs) - 4}개")
    return " · ".join(shown)


def run_legacy(integrated: bool = False) -> None:
    if not integrated:
        page_header(
            "종합계산기(80개)",
            "종합계산기(80개)",
            "목적 선택 → 조건 입력 → 계산·검토 → 자료 내려받기",
            "QC",
        )
    else:
        st.subheader("🧮 보험 기본·생활자금 계산")
        st.caption("보험나이·보험료·생활자금·미래 준비를 빠르게 계산합니다.")

    merged = {"필요 보장액", "소득 공백·비상자금", "목표 달성 월 저축액", "미래 목표자금", "은퇴 생활자금"} if integrated else set()
    with st.container(border=True, key="insurance_basics_selector"):
        st.caption("계산 항목 선택")
        group_column, mode_column = st.columns([1, 2], gap="medium")
        group = group_column.selectbox(
            "계산 분류",
            ["전체", "보험 기본", "생활과 보장", "미래 준비"],
            key="a_group",
            format_func=_format_group,
        )
        choices = [
            name
            for name, spec in MODES.items()
            if name not in merged and (group == "전체" or spec[1] == group)
        ]
        if st.session_state.get("a_mode") not in choices:
            st.session_state["a_mode"] = choices[0]
        mode = mode_column.selectbox("계산 항목", choices, key="a_mode")

    kind, _group, fields, formula, assumptions = MODES[mode]
    st.markdown(
        f"**먼저 입력할 내용** · {_mode_core_text(kind, fields)}  \n"
        f"<span style='color:#61758b;font-size:13px'>{escape(assumptions)}</span>",
        unsafe_allow_html=True,
    )
    controls = st.columns([1, 1, 4], gap="small")
    controls[0].button(
        "예시 입력",
        key=f"a_example_{kind}",
        on_click=_set_mode_inputs,
        args=(kind, fields),
        kwargs={"example": True},
        use_container_width=True,
    )
    controls[1].button(
        "초기화",
        key=f"a_clear_{kind}",
        on_click=_set_mode_inputs,
        args=(kind, fields),
        kwargs={"example": False},
        use_container_width=True,
    )
    controls[2].caption("화면의 기본 금액은 기능 확인용 예시입니다. 실제 상담 조건으로 바꾼 뒤 계산하세요.")

    from modules.calculators.input_design import input_panels

    input_panel, result_panel = input_panels("insurance_basics")
    submitted = False
    calculation_succeeded = False
    with input_panel:
        st.caption("✍️ 01 · 조건 입력")
        with st.container(key="insurance_basics_" + kind):
            values: dict[str, object] = {}
            display_values: dict[str, str] = {}
            stable_key = sha256(mode.encode("utf-8")).hexdigest()[:12]
            with st.container(key="hw_required_group_" + stable_key):
                st.markdown("**핵심 입력**")
                st.markdown(
                    '<div class="hw-input-group-note">계산 목적과 주요 금액·대상·기간을 먼저 확인하세요.</div>',
                    unsafe_allow_html=True,
                )
                if kind in ("age", "change"):
                    birth = field(
                        "date_input",
                        "생년월일",
                        "a_birth",
                        date(1990, 1, 1),
                        min_value=date(1900, 1, 1),
                        max_value=date(2100, 12, 31),
                    )
                    reference = field(
                        "date_input",
                        "신규 가입 가정 기준일",
                        "a_reference",
                        date.today(),
                        min_value=date(1900, 1, 1),
                        max_value=date(2100, 12, 31),
                    )
                    values = {"birth": birth, "reference": reference}
                    display_values = {"생년월일": birth.isoformat(), "기준일": reference.isoformat()}
                else:
                    for entry in fields:
                        if entry[2] == "rate":
                            continue
                        value, display = _render_input(entry, kind)
                        values[entry[0]] = value
                        display_values[entry[1]] = display

            rate_fields = [entry for entry in fields if entry[2] == "rate"]
            if rate_fields:
                with st.expander("가정 조정", expanded=False):
                    st.caption("수익률·물가 등 결과에 적용되는 가정입니다.")
                    for entry in rate_fields:
                        value, display = _render_input(entry, kind)
                        values[entry[0]] = value
                        display_values[entry[1]] = display

            inputs = (
                [("생년월일", display_values["생년월일"]), ("기준일", display_values["기준일"])]
                if kind in ("age", "change")
                else [(entry[1], display_values[entry[1]]) for entry in fields]
            )
            st.markdown(
                '<div class="hw-active-condition"><b>현재 적용 조건</b><br>'
                + _condition_summary(inputs)
                + "</div>",
                unsafe_allow_html=True,
            )
            if st.button("산식·가정 자세히 보기", key="a_help", use_container_width=True):
                assumptions_dialog(formula, assumptions)
            token = fingerprint([mode, values, input_revision("quick_calculators")])
            submitted = st.button("계산하기", key="a_calculate", type="primary", use_container_width=True)
            if submitted:
                st.session_state.pop("a_review_token", None)
                st.session_state.pop("a_calculation", None)
                try:
                    if kind in ("age", "change"):
                        from modules.calculators.quick_calculators import age_result

                        age, insurance, change = age_result(values["birth"], values["reference"])
                        output = {
                            "만 나이": f"{age}세",
                            "신규 가입 보험나이": f"{insurance}세",
                            "다음 상령일": change.isoformat(),
                            "다음 변경일까지": f"{(change - values['reference']).days}일",
                        }
                    else:
                        output = calculate(kind, values)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
                    result = {
                        "title": mode,
                        "values": output,
                        "inputs": inputs,
                        "formula": formula,
                        "assumptions": assumptions,
                        "prepared_on": date.today().isoformat(),
                        "prepared_at": stamp,
                        "token": token,
                    }
                    st.session_state["a_calculation"] = result
                    save_result("quick_calculators", result, rule_version="stage4.2")
                    calculation_succeeded = True

        result = st.session_state.get("a_calculation")
        if not result:
            return
        if result["token"] != token:
            st.info("입력 조건이 변경되었습니다. 다시 계산해주세요.")
            return

    with result_panel:
        st.caption("✨ 02 · 계산 결과")
        stamp = result.get("prepared_at", result["prepared_on"])
        st.caption("아래 결과와 다운로드는 " + stamp + "에 계산한 입력값 기준입니다. 입력을 바꾸면 계산하기를 다시 눌러주세요.")
        st.subheader(mode)
        from modules.calculators.input_design import render_metrics

        render_metrics(dict(formatted_results(result["values"])), "insurance_basics")

        # 다른 계산기와 동일하게 PDF에 포함할 내용을 먼저 선택합니다.
        # 보험 기본·생활자금 계산은 기존 dict 결과를 공통 PDF 모델로 변환해
        # 핵심 결과·입력 내용·산출 근거를 선택적으로 출력합니다.
        from modules.calculators.finance.finance_models import FinanceResult
        from modules.calculators.result_pdf import build_result_pdf, pdf_section_options

        pdf_options = pdf_section_options("insurance_basics_pdf_scope")
        if any(pdf_options.values()):
            pdf_result = FinanceResult(
                metrics=result["values"],
                formula=result["formula"],
                assumptions=[result["assumptions"]],
            )
            try:
                pdf_data = build_result_pdf(
                    mode,
                    result["inputs"],
                    pdf_result,
                    stamp,
                    **pdf_options,
                )
            except Exception:
                st.warning("PDF 출력을 만들지 못했습니다. 설치 상태를 확인해 주세요.")
            else:
                st.download_button(
                    "결과 PDF 저장",
                    pdf_data,
                    f"hwarang_calculator_{kind}.pdf",
                    "application/pdf",
                    key="a_export_pdf",
                    type="primary",
                    icon=":material/download:",
                    use_container_width=True,
                )

        with st.expander("산출 내역 자세히 보기"):
            st.markdown("**입력 조건**")
            st.dataframe(
                [{"입력 항목": label, "값": value} for label, value in result["inputs"]],
                hide_index=True,
                use_container_width=True,
            )
            st.markdown("**계산식**")
            st.write(result["formula"])
            st.markdown("**가정과 미반영 조건**")
            st.caption(result["assumptions"])
            st.caption("계산 시각: " + stamp)
            try:
                excel_data = export_bytes(result, "xlsx")
            except Exception:
                st.warning("Excel 출력을 만들지 못했습니다. 설치 상태를 확인해 주세요.")
            else:
                st.download_button(
                    "상세 계산 Excel 저장",
                    excel_data,
                    f"hwarang_calculator_{kind}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="a_export_xlsx",
                    icon=":material/download:",
                    use_container_width=True,
                )

    from modules.calculators.input_design import jump_to_result

    jump_to_result(submitted and calculation_succeeded, "insurance_basics")
