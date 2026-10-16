"""Metadata-guided calculator input and two-audience result views."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

import streamlit as st

from modules.calculators.coverage.coverage_models import FIELDS, NAMES, calculate
from modules.calculators.input_design import number_input, uses_decimal_manwon, uses_won_precision, read_money_state, set_money_state
from modules.calculators.input_policy import policy_for_field
from modules.calculators.structured_inputs import handled_indices, render as render_structured, state_keys as structured_state_keys
from modules.calculators.ux_profiles import (
    active_condition_summary,
    field_bucket,
    field_help,
    field_visible,
    ordered_indices,
    profile,
)


def _uses_won_precision(label: str) -> bool:
    """Match input_design.number_input's direct-won rule for per-unit values."""
    return uses_won_precision(label)


def _widget_value(name: str, index: int, entry: tuple, *, example: bool) -> object:
    _label, default, unit, _maximum = entry
    if example:
        if unit == "날짜":
            return date.fromisoformat(str(default))
        return default
    if unit == "선택":
        return default
    if unit == "날짜":
        return date.fromisoformat(str(default))
    if unit == "문자":
        return ""
    return 0.0 if unit in ("%", "명(연평균)") else 0


def _set_inputs(name: str, entries: list[tuple], *, example: bool) -> None:
    from modules.calculators.structured_inputs import reset_table
    for index, entry in enumerate(entries):
        label, default, unit, maximum = entry
        base = f"cov_{name}_{index}"
        if unit == "원":
            set_money_state(base, label, default if example else None,
                            policy=policy_for_field(name, index, label))
        else:
            # A cleared numeric value is missing, not an invented zero.
            value = _widget_value(name, index, entry, example=example)
            st.session_state[base] = value if example or unit in ("선택", "날짜", "문자") else None
    reset_table(name, example=example)
    st.session_state.pop("coverage_result_" + name, None)
    from modules.shared.runtime_cache import clear_scope
    clear_scope("export:")


def _state_snapshot(name: str, entries: list[tuple]) -> dict[str, object]:
    result = {}
    for index, (label, default, unit, _maximum) in enumerate(entries):
        base = f"cov_{name}_{index}"
        result[label] = (read_money_state(base, label, default, policy=policy_for_field(name, index, label))
                         if unit == "원" else st.session_state.get(base, default))
    return result


def run(name, fields=None, calculator=None, caption=None):
    fields = FIELDS if fields is None else fields
    calculator = calculate if calculator is None else calculator
    entries = fields[name]
    meta = profile(name)
    st.caption(caption or "입력 조건에 따른 계산 시나리오")
    st.markdown(
        f"**먼저 입력할 내용** · {meta['core']}  \n"
        f"<span style='color:#61758b;font-size:13px'>{meta['improvements']}</span>",
        unsafe_allow_html=True,
    )
    controls = st.columns([1, 1, 4], gap="small")
    controls[0].button("예시 입력", key=f"ux_example_{name}", on_click=_set_inputs, args=(name, entries), kwargs={"example": True}, use_container_width=True)
    controls[1].button("초기화", key=f"ux_clear_{name}", on_click=_set_inputs, args=(name, entries), kwargs={"example": False}, use_container_width=True)
    controls[2].caption("화면의 기본 금액은 기능 확인용 예시입니다. 실제 상담 조건으로 바꾼 뒤 계산하세요.")

    from modules.calculators.input_design import input_panels as work_panels
    input_panel, result_panel = work_panels("coverage_calculator_ui")
    with input_panel:
        st.caption("✍️ 01 · 조건 입력")
        with st.container(key="coverage_" + name):
            values = [entry[1] for entry in entries]
            snapshot = _state_snapshot(name, entries)
            consumed = handled_indices(name)
            table_errors = []
            rendered = set()

            def render_field(index: int) -> None:
                label, default, unit, maximum = entries[index]
                rendered.add(index)
                key = f"cov_{name}_{index}"
                help_text = field_help(label, unit)
                if unit == "선택":
                    current = snapshot.get(label, default)
                    selected_index = maximum.index(current) if current in maximum else maximum.index(default)
                    value = st.selectbox(label, maximum, index=selected_index, key=key, help=help_text)
                elif unit == "날짜":
                    value = st.date_input(
                        label,
                        value=date.fromisoformat(str(default)),
                        min_value=date(1900, 1, 1),
                        max_value=date(2100, 12, 31),
                        key=key,
                        help=help_text,
                    )
                elif unit == "문자":
                    signed_money = maximum == 30 and any(word in label for word in ("조정액", "순손익", "세무상 소득", "세액 합계", "수입금액", "보험료"))
                    value = st.text_input(
                        label + (" (원)" if signed_money else ""),
                        value=default,
                        max_chars=maximum,
                        key=key,
                        help=help_text or ("원 단위 정수로 입력합니다. 빈칸과 음수 허용 여부는 항목 안내를 따릅니다." if signed_money else None),
                    )
                elif unit in ("%", "명(연평균)"):
                    value = number_input(
                        f"{label} ({unit})",
                        min_value=0.0,
                        max_value=float(maximum),
                        value=float(default),
                        step=0.01 if unit == "명(연평균)" else 0.1,
                        key=key,
                        help=help_text,
                    )
                else:
                    value = number_input(
                        f"{label} ({unit})",
                        min_value=0,
                        max_value=maximum,
                        value=default,
                        step=10_000 if unit == "원" else 1,
                        money_policy=policy_for_field(name, index, label) if unit == "원" else None,
                        key=key,
                        help=help_text,
                    )
                values[index] = value
                snapshot[label] = value

            buckets: dict[str, list[int]] = {"core": [], "additional": [], "assumption": [], "confirmation": []}
            for index in ordered_indices(name, entries):
                if index in consumed:
                    continue
                label, _default, unit, _maximum = entries[index]
                if field_visible(name, label, snapshot):
                    buckets[field_bucket(name, label, unit)].append(index)

            if buckets["core"]:
                stable_key = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
                with st.container(key="hw_required_group_" + stable_key):
                    st.markdown("**핵심 입력**")
                    st.markdown('<div class="hw-input-group-note">계산 목적과 주요 금액·대상·기간을 먼저 확인하세요.</div>', unsafe_allow_html=True)
                    for index in buckets["core"]:
                        render_field(index)

            # Repeated rows belong after the calculator's purpose and core amounts.
            # This preserves the reviewed flow: purpose → core values → detailed rows.
            if consumed:
                render_structured(name, entries, values)
                table_errors = list(st.session_state.get("hw.table_errors." + name, []))

            labels = {
                "additional": ("추가 조건", "해당하는 공제·예외·과거 자료만 입력합니다."),
                "assumption": ("가정 조정", "수익률·물가·세율 등 결과에 적용되는 가정입니다."),
                "confirmation": ("확인자료·적용 요건", "신고서·법정 요건 등 실제로 확인한 값만 선택합니다."),
            }
            for bucket in ("additional", "assumption", "confirmation"):
                indices = buckets[bucket]
                if not indices:
                    continue
                title, guide = labels[bucket]
                expanded = bucket == "additional" and meta.get("priority") == "높음" and len(indices) <= 6
                with st.expander(title, expanded=expanded):
                    st.caption(guide)
                    for index in indices:
                        render_field(index)

            summary = active_condition_summary(name, snapshot)
            if summary:
                st.markdown('<div class="hw-active-condition"><b>현재 적용 조건</b><br>' + " · ".join(summary) + "</div>", unsafe_allow_html=True)
            missing_indices = [i for i in rendered if values[i] is None]
            missing = [entries[i][0] for i in missing_indices]
            if missing_indices:
                from modules.shared.input_states import apply_input_states
                from modules.calculators.input_design import money_widget_key
                missing_keys = []
                invalid_keys = []
                for i in missing_indices:
                    label, _default, unit, _maximum = entries[i]
                    base = f"cov_{name}_{i}"
                    widget_key = money_widget_key(base) if unit == "원" else base
                    raw = st.session_state.get(widget_key)
                    if raw not in (None, ""):
                        invalid_keys.append(widget_key)
                    else:
                        missing_keys.append(widget_key)
                apply_input_states(missing=missing_keys, invalid=invalid_keys)
                st.info("입력 필요: " + ", ".join(missing))
            submitted = st.button("계산하기", key="calculate_" + name, type="primary", width="stretch", disabled=bool(missing or table_errors))

        result_key = "coverage_result_" + name
        if submitted:
            try:
                st.session_state[result_key] = (
                    tuple(values),
                    calculator(name, values),
                    datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M"),
                )
            except ValueError as exc:
                st.session_state.pop(result_key, None)
                st.error(str(exc))
        if missing or table_errors:
            st.session_state.pop(result_key, None)
            return
        stored = st.session_state.get(result_key)
        if not stored:
            return
        if stored[0] != tuple(values):
            st.info("입력 조건이 변경되었습니다. 다시 계산해주세요.")
            return
        args, result, stamp = stored

    with result_panel:
        st.caption("✨ 02 · 계산 결과")
        customer, advisor = (st.container(), st.expander("산출 내역 자세히 보기"))
        display = result.display()
        from modules.calculators.calculator_exports import build_exports
        _text, csv_bytes = build_exports(name, fields[name], args, result, stamp)
        st.caption("아래 결과와 다운로드는 " + stamp + "에 계산한 입력값 기준입니다. 입력을 바꾸면 계산하기를 다시 눌러주세요.")
        with customer:
            st.subheader(name)
            from modules.calculators.input_design import render_metrics
            from modules.calculators.visuals import primary_result_labels
            render_metrics(display, "cov_" + name, primary_result_labels(name))
            from modules.calculators.result_pdf import build_result_pdf, pdf_section_options
            pdf_options = pdf_section_options("cov_pdf_" + name)
            if any(pdf_options.values()):
                pdf = build_result_pdf(name, [(f"{f[0]} ({f[2]})", value) for f, value in zip(fields[name], args)], result, stamp, **pdf_options)
                st.download_button("결과 PDF 저장", pdf, file_name=name + "_결과보고서.pdf", mime="application/pdf", key=name + "_customer", type="primary", icon=":material/download:", width="stretch")
        with advisor:
            for note in result.assumptions:
                st.caption(note)
            st.write(result.formula)
            st.caption("계산 시각: " + stamp)
            inputs = [{"입력 항목": f"{field[0]} ({field[2]})", "값": str(value)} for field, value in zip(fields[name], args)]
            st.dataframe(inputs, hide_index=True, width="stretch")
            st.dataframe([{key: float(value) if hasattr(value, "quantize") else value for key, value in row.items()} for row in result.rows], hide_index=True, width="stretch")
            st.download_button("상세 계산 CSV 저장", csv_bytes, file_name=name + "_상세.csv", mime="text/csv", key=name + "_advisor")

    from modules.calculators.input_design import jump_to_result
    jump_to_result(submitted, "coverage_calculator_ui")
