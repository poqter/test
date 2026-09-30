"""Integrated insurance basics and living-fund calculators.

These calculators are first-class entries in the 88-item Hwarang catalog. The
calculation engines receive won and decimal rates; this module only manages the
shared Streamlit input, result, and export experience.
"""
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
from modules.shared.workspace_tools import field


QUICK_CALCULATORS: dict[str, str] = {
    "보험나이계산기": "보험나이",
    "다음 상령일계산기": "다음 상령일",
    "총 납입보험료계산기": "총 납입보험료",
    "납입면제 효과계산기": "납입면제 효과",
    "가족 생활자금계산기": "가족 생활자금",
    "교육자금계산기": "교육자금",
    "물가 반영 필요자금계산기": "물가 반영 필요자금",
    "부채 정리자금계산기": "부채 정리자금",
}
QUICK_CALCULATOR_NAMES = tuple(QUICK_CALCULATORS)

# 만원 단위 입력 중 실제 보험료처럼 1만원 미만 단위가 자주 필요한 항목만
# 0.01만원(100원) 단위까지 허용합니다. 정수값은 10.00이 아니라 10으로 표시합니다.
_DECIMAL_MONEY_FIELDS = frozenset({
    ("total", "premium"),
    ("waiver", "premium"),
})
_FLEXIBLE_NUMBER_FORMAT = "%.12g"


@st.dialog("계산 가정과 입력 단위", width="large")
def assumptions_dialog(formula: str, assumptions: str) -> None:
    st.subheader("계산 근거")
    st.write(formula)
    st.subheader("가정과 미반영 조건")
    st.write(assumptions)
    st.caption("금액 입력은 만원, 결과는 원 단위로 표시합니다. 수익률·물가율은 사용자 시나리오입니다.")


def run() -> None:
    """Render the complete 88-calculator center."""
    from modules.calculators.jarvia_calculator_center import run as run_integrated

    run_integrated()


def _scope(kind: str) -> str:
    return f"quick_calculator.{kind}"


def _mode_core_text(kind: str, fields: list[tuple]) -> str:
    if kind in ("age", "change"):
        return "생년월일, 기준일"
    labels = [label for _key, label, field_type, _default, _low, _high in fields if field_type != "rate"]
    return ", ".join(labels if len(labels) <= 4 else labels[:4]) + ("" if len(labels) <= 4 else " 등")


def _set_widget_value(page: str, key: str, value: object) -> None:
    """Update the durable value and the current field widget in one callback."""
    st.session_state[key] = value
    st.session_state["_ws_" + key] = value
    commit_input(page, key, value)


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
    page = _scope(kind)
    if kind in ("age", "change"):
        birth = date(1990, 1, 1) if example else date.today()
        _set_widget_value(page, f"a_{kind}_birth", birth)
        _set_widget_value(page, f"a_{kind}_reference", date.today())
    else:
        for key, _label, field_type, default, _low, _high in fields:
            decimal_value = field_type == "rate" or (
                field_type == "money" and _money_allows_decimals(kind, key)
            )
            if example:
                value = float(default) if decimal_value else int(default)
            else:
                value = 0.0 if decimal_value else 0
            _set_widget_value(page, f"a_{kind}_{key}", value)
    st.session_state.pop(f"a_calculation_{kind}", None)


def _format_compact_decimal(value: Decimal, *, grouped: bool = False) -> str:
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


def _render_input(entry: tuple, kind: str, page: str) -> tuple[object, str]:
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
                page=page,
                min_value=float(low),
                max_value=float(high),
                step=0.01,
                format=_FLEXIBLE_NUMBER_FORMAT,
                help=(
                    "기본 정수 금액은 소수점 없이 표시하고, 필요한 경우에만 "
                    "0.01만원(100원) 단위까지 입력할 수 있습니다."
                ),
            )
            raw = Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        else:
            value = field(
                "number_input",
                label + " (만원)",
                widget_key,
                int(default),
                page=page,
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
            page=page,
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
        page=page,
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


def _age_output(mode: str, birth: date, reference: date) -> dict[str, str]:
    from modules.calculators.quick_calculators import age_result

    age, insurance_age, change = age_result(birth, reference)
    days = (change - reference).days
    if mode == "다음 상령일":
        return {
            "다음 상령일": change.isoformat(),
            "다음 변경일까지": f"{days}일",
            "현재 만 나이": f"{age}세",
            "현재 보험나이": f"{insurance_age}세",
        }
    return {
        "신규 가입 보험나이": f"{insurance_age}세",
        "만 나이": f"{age}세",
        "다음 상령일": change.isoformat(),
        "다음 변경일까지": f"{days}일",
    }


def render_quick_calculator(calculator_name: str) -> None:
    """Render one of the eight integrated quick calculators."""
    mode = QUICK_CALCULATORS.get(calculator_name)
    if mode is None:
        st.error("지원하지 않는 간편 계산기입니다.")
        return

    kind, _group, fields, formula, assumptions = MODES[mode]
    page = _scope(kind)
    result_key = f"a_calculation_{kind}"

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

    input_panel, result_panel = input_panels("insurance_basics_" + kind)
    submitted = False
    calculation_succeeded = False
    with input_panel:
        st.caption("✍️ 01 · 조건 입력")
        with st.container(key="insurance_basics_" + kind):
            values: dict[str, object] = {}
            display_values: dict[str, str] = {}
            stable_key = sha256(calculator_name.encode("utf-8")).hexdigest()[:12]
            with st.container(key="hw_required_group_" + stable_key):
                st.markdown("**핵심 입력**")
                st.markdown(
                    '<div class="hw-input-group-note">계산 목적과 주요 금액·대상·기간을 먼저 확인하세요.</div>',
                    unsafe_allow_html=True,
                )
                if kind in ("age", "change"):
                    birth_key = f"a_{kind}_birth"
                    reference_key = f"a_{kind}_reference"
                    birth = field(
                        "date_input",
                        "생년월일",
                        birth_key,
                        date(1990, 1, 1),
                        page=page,
                        min_value=date(1900, 1, 1),
                        max_value=date(2100, 12, 31),
                    )
                    reference_label = "신규 가입 가정 기준일" if mode == "보험나이" else "기준일"
                    reference = field(
                        "date_input",
                        reference_label,
                        reference_key,
                        date.today(),
                        page=page,
                        min_value=date(1900, 1, 1),
                        max_value=date(2100, 12, 31),
                    )
                    values = {"birth": birth, "reference": reference}
                    display_values = {"생년월일": birth.isoformat(), "기준일": reference.isoformat()}
                else:
                    for entry in fields:
                        if entry[2] == "rate":
                            continue
                        value, display = _render_input(entry, kind, page)
                        values[entry[0]] = value
                        display_values[entry[1]] = display

            rate_fields = [entry for entry in fields if entry[2] == "rate"]
            if rate_fields:
                with st.expander("가정 조정", expanded=False):
                    st.caption("수익률·물가 등 결과에 적용되는 가정입니다.")
                    for entry in rate_fields:
                        value, display = _render_input(entry, kind, page)
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
            if st.button("산식·가정 자세히 보기", key=f"a_help_{kind}", use_container_width=True):
                assumptions_dialog(formula, assumptions)
            token = fingerprint([calculator_name, values, input_revision(page)])
            submitted = st.button(
                "계산하기",
                key=f"a_calculate_{kind}",
                type="primary",
                use_container_width=True,
            )
            if submitted:
                st.session_state.pop(result_key, None)
                try:
                    output = (
                        _age_output(mode, values["birth"], values["reference"])
                        if kind in ("age", "change")
                        else calculate(kind, values)
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
                    result = {
                        "title": calculator_name,
                        "values": output,
                        "inputs": inputs,
                        "formula": formula,
                        "assumptions": assumptions,
                        "prepared_on": date.today().isoformat(),
                        "prepared_at": stamp,
                        "token": token,
                    }
                    st.session_state[result_key] = result
                    save_result(page, result, rule_version="quick.88.1")
                    calculation_succeeded = True

        result = st.session_state.get(result_key)
        if not result:
            return
        if result["token"] != token:
            st.info("입력 조건이 변경되었습니다. 다시 계산해주세요.")
            return

    with result_panel:
        st.caption("✨ 02 · 계산 결과")
        stamp = result.get("prepared_at", result["prepared_on"])
        st.caption("아래 결과와 다운로드는 " + stamp + "에 계산한 입력값 기준입니다. 입력을 바꾸면 계산하기를 다시 눌러주세요.")
        st.subheader(calculator_name)
        from modules.calculators.input_design import render_metrics
        from modules.calculators.visuals import primary_result_labels

        render_metrics(
            dict(formatted_results(result["values"])),
            "insurance_basics_" + kind,
            primary_result_labels(calculator_name),
        )

        from modules.calculators.finance.finance_models import FinanceResult
        from modules.calculators.result_pdf import build_result_pdf, pdf_section_options

        pdf_options = pdf_section_options(f"insurance_basics_{kind}_pdf_scope")
        if any(pdf_options.values()):
            pdf_result = FinanceResult(
                metrics=result["values"],
                formula=result["formula"],
                assumptions=[result["assumptions"]],
            )
            try:
                pdf_data = build_result_pdf(
                    calculator_name,
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
                    f"hwarang_{kind}_result.pdf",
                    "application/pdf",
                    key=f"a_export_pdf_{kind}",
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
                    f"hwarang_{kind}_detail.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"a_export_xlsx_{kind}",
                    icon=":material/download:",
                    use_container_width=True,
                )

    from modules.calculators.input_design import jump_to_result

    jump_to_result(submitted and calculation_succeeded, "insurance_basics_" + kind)
