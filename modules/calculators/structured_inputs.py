"""Table-style inputs for calculators that previously used repeated text fields."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd
import streamlit as st


def state_keys(name: str) -> tuple[str, ...]:
    if name == "이월결손금계산기":
        return ("ux_table_carryforward",)
    if name == "법인 4대보험계산기":
        return ("ux_table_corporate_social",)
    if name == "비상장주식 평가계산기":
        return ("ux_table_unlisted",)
    return ()


def handled_indices(name: str) -> set[int]:
    return {
        "이월결손금계산기": {0},
        "법인 4대보험계산기": {4},
        "비상장주식 평가계산기": set(range(10, 19)),
    }.get(name, set())


def _won(value: Any) -> int:
    from modules.shared.numeric import integer_won
    return integer_won(value, maximum=10**12)


def _parse_loss_ledger(text: str) -> pd.DataFrame:
    from modules.shared.numeric import integer_won
    rows = []
    for index, item in enumerate(str(text or "").split(";"), 1):
        if not item.strip():
            continue
        parts = item.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"결손금 {index}행: 발생연도와 잔액을 확인해 주세요.")
        year = integer_won(parts[0], label="발생연도", allow_negative=False)
        if not 2009 <= year <= 2025:
            raise ValueError(f"결손금 {index}행: 발생연도는 2009~2025년이어야 합니다.")
        amount = integer_won(parts[1], label="미사용 잔액", allow_negative=False, maximum=10**12)
        rows.append({"발생연도": year, "미사용 잔액(원)": amount})
    return pd.DataFrame(rows, columns=["발생연도", "미사용 잔액(원)"]).astype({"발생연도": "Int64", "미사용 잔액(원)": "Int64"})


def _parse_wages(text: str) -> pd.DataFrame:
    from modules.shared.numeric import integer_won
    rows = []
    for item in str(text or "").split(";"):
        if not item.strip():
            continue
        amount = integer_won(item, label="월 보수", allow_negative=False, maximum=10**12)
        rows.append({"직원": len(rows) + 1, "월 보수(원)": amount})
    return pd.DataFrame(rows, columns=["직원", "월 보수(원)"]).astype({"직원": "Int64", "월 보수(원)": "Int64"})


def reset_table(name: str, *, example: bool) -> None:
    for key in state_keys(name):
        st.session_state.pop(key, None)
    st.session_state.pop("hw.table_base." + name, None)
    st.session_state.pop("hw.table_snapshot." + name, None)
    st.session_state["ux_table_reset_mode_" + name] = "example" if example else "clear"
    st.session_state["hw.table_errors." + name] = []


def _table_base(name, factory):
    key = "hw.table_base." + name
    if key not in st.session_state:
        st.session_state[key] = factory()
    return st.session_state[key]


def _validate_rows(name: str, edited: pd.DataFrame, required: tuple[str, ...], *, signed=()) -> tuple[list[dict], list[str]]:
    from modules.shared.numeric import integer_won
    records, errors = [], []
    for row_index, (_, row) in enumerate(edited.iterrows(), 1):
        # A truly empty row is not an instruction to insert a default example.
        supplied = [row.get(k) for k in required]
        if all(pd.isna(v) or (isinstance(v, str) and not v.strip()) for v in supplied):
            continue
        converted = {}
        for key in required:
            try:
                converted[key] = integer_won(row.get(key), label=key, allow_negative=key in signed, maximum=10**12)
            except ValueError as exc:
                errors.append(f"{row_index}행 · {exc}")
        if len(converted) == len(required):
            records.append(converted)
    if len(records) > 1000:
        errors.append("표는 최대 1,000행까지 처리합니다.")
    st.session_state["hw.table_snapshot." + name] = edited.copy(deep=True)
    return records, errors


def render(name: str, entries: list[tuple], values: list[Any]) -> set[int]:
    """Retain original positional API; invalid rows block calculation, not vanish."""
    consumed = handled_indices(name)
    if not consumed:
        return consumed
    mode = st.session_state.pop("ux_table_reset_mode_" + name, None)
    example = mode == "example"
    if mode:
        st.session_state.pop("hw.table_base." + name, None)
    errors = []
    if name == "이월결손금계산기":
        st.markdown("**연도별 미사용 결손금**")
        st.caption("해당하는 결손금만 행별로 입력하세요. 빈 표는 결손금 없음이며, 예시는 ‘예시 입력’으로만 불러옵니다.")
        default = _table_base(name, lambda: _parse_loss_ledger(entries[0][1] if example else ""))
        edited = st.data_editor(default, key="ux_table_carryforward", num_rows="dynamic", hide_index=True,
            width="stretch", column_config={
                "발생연도": st.column_config.NumberColumn(min_value=2009, max_value=2025, step=1, format="%d"),
                "미사용 잔액(원)": st.column_config.NumberColumn(min_value=0, max_value=10**12, step=1, format="%d원")})
        rows, errors = _validate_rows(name, edited, ("발생연도", "미사용 잔액(원)"))
        years = [r["발생연도"] for r in rows]
        if len(set(years)) != len(years):
            errors.append("같은 발생연도는 한 행으로 합산해 입력하세요.")
        if any(not 2009 <= year <= 2025 for year in years):
            errors.append("발생연도는 2009~2025년이어야 합니다.")
        values[0] = ";".join(f"{row['발생연도']},{row['미사용 잔액(원)']}" for row in rows) if not errors else None
    elif name == "법인 4대보험계산기":
        method = str(st.session_state.get(f"cov_{name}_1", entries[1][1]))
        if "직원별" in method:
            st.markdown("**직원별 월 보수**")
            default = _table_base(name, lambda: _parse_wages(entries[4][1] if example else ""))
            edited = st.data_editor(default, key="ux_table_corporate_social", num_rows="dynamic", hide_index=True,
                width="stretch", column_config={
                    "직원": st.column_config.NumberColumn(disabled=True, format="%d"),
                    "월 보수(원)": st.column_config.NumberColumn(min_value=0, max_value=10**12, step=1, format="%d원")})
            rows, errors = _validate_rows(name, edited, ("월 보수(원)",))
            if not rows:
                errors.append("직원별 입력은 최소 한 명의 월 보수가 필요합니다.")
            values[4] = ";".join(str(r["월 보수(원)"]) for r in rows) if not errors else None
        else:
            # Never let hidden example wages contribute to a totals-mode result.
            values[4] = ""
    elif name == "비상장주식 평가계산기":
        st.markdown("**3개년 순손익·조정액·평가용 주식수**")
        st.caption("손익·조정액은 원 단위, 주식수는 정수로 입력합니다. 미확인과 실제 0은 구분합니다.")
        default = _table_base(name, lambda: pd.DataFrame([
            {"기준": f"{index+1}년 전",
             "당기순손익(원)": _won(entries[10+index][1]) if example else None,
             "평가 조정액(원)": _won(entries[13+index][1]) if example else None,
             "평가용 주식수": int(entries[16+index][1]) if example else None}
            for index in range(3)]).astype({"당기순손익(원)": "Int64", "평가 조정액(원)": "Int64", "평가용 주식수": "Int64"}))
        edited = st.data_editor(default, key="ux_table_unlisted", num_rows="fixed", hide_index=True,
            width="stretch", column_config={
                "기준": st.column_config.TextColumn(disabled=True),
                "당기순손익(원)": st.column_config.NumberColumn(min_value=-10**12, max_value=10**12, step=1, format="%d원"),
                "평가 조정액(원)": st.column_config.NumberColumn(min_value=-10**12, max_value=10**12, step=1, format="%d원"),
                "평가용 주식수": st.column_config.NumberColumn(min_value=1, max_value=10**10, step=1, format="%d")})
        rows, errors = _validate_rows(name, edited, ("당기순손익(원)", "평가 조정액(원)", "평가용 주식수"), signed=("당기순손익(원)", "평가 조정액(원)"))
        if len(rows) != 3:
            errors.append("3개년 손익·조정액·주식수를 모두 입력하세요. 해당 금액이 없으면 0을 입력합니다.")
        if any(r["평가용 주식수"] < 1 or r["평가용 주식수"] > 10**10 for r in rows):
            errors.append("평가용 주식수는 1~100억 사이 정수여야 합니다.")
        if not errors:
            for i, row in enumerate(rows):
                values[10+i], values[13+i], values[16+i] = str(row["당기순손익(원)"]), str(row["평가 조정액(원)"]), row["평가용 주식수"]
        else:
            for i in consumed:
                values[i] = None
    st.session_state["hw.table_errors." + name] = errors
    for error in errors[:6]:
        st.error(error)
    return consumed
