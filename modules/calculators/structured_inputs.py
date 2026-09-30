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
    try:
        return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0


def _parse_loss_ledger(text: str) -> pd.DataFrame:
    rows = []
    for item in str(text or "").split(";"):
        parts = [part.strip() for part in item.split(",")]
        if len(parts) == 2 and parts[0]:
            try:
                rows.append({"발생연도": int(parts[0]), "미사용 잔액(원)": int(parts[1].replace(",", ""))})
            except ValueError:
                continue
    return pd.DataFrame(rows or [{"발생연도": 2025, "미사용 잔액(원)": 500_000_000}])


def _parse_wages(text: str) -> pd.DataFrame:
    rows = []
    for index, item in enumerate(str(text or "").split(";"), 1):
        item = item.strip().replace(",", "")
        if not item:
            continue
        try:
            rows.append({"직원": index, "월 보수(원)": int(item)})
        except ValueError:
            continue
    return pd.DataFrame(rows or [{"직원": 1, "월 보수(원)": 5_000_000}])


def render(name: str, entries: list[tuple], values: list[Any]) -> set[int]:
    """Render a specialized table and populate original positional values."""
    consumed = handled_indices(name)
    if not consumed:
        return consumed
    reset_mode = st.session_state.pop("ux_table_reset_mode_" + name, None)

    if name == "이월결손금계산기":
        st.markdown("**연도별 미사용 결손금**")
        st.caption("문자열 대신 발생연도와 신고·경정으로 인정된 미사용 잔액을 행별로 입력합니다.")
        default = (
            pd.DataFrame([{"발생연도": 2025, "미사용 잔액(원)": 0}])
            if reset_mode == "clear"
            else _parse_loss_ledger(entries[0][1])
        )
        edited = st.data_editor(
            default,
            key="ux_table_carryforward",
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "발생연도": st.column_config.NumberColumn(min_value=2009, max_value=2025, step=1, format="%d"),
                "미사용 잔액(원)": st.column_config.NumberColumn(min_value=0, max_value=10**12, step=10_000, format="%d원"),
            },
        )
        rows = []
        for _, row in edited.dropna(how="all").iterrows():
            year, amount = row.get("발생연도"), row.get("미사용 잔액(원)")
            if pd.notna(year) and pd.notna(amount):
                rows.append(f"{int(year)},{_won(amount)}")
        values[0] = ";".join(rows)

    elif name == "법인 4대보험계산기":
        mode = str(st.session_state.get(f"cov_{name}_1", entries[1][1]))
        if "직원별" in mode:
            st.markdown("**직원별 월 보수**")
            st.caption("직원별 보수를 행으로 입력하면 기존 계산 엔진에 안전하게 전달됩니다.")
            default = (
                pd.DataFrame([{"직원": 1, "월 보수(원)": 0}])
                if reset_mode == "clear"
                else _parse_wages(entries[4][1])
            )
            edited = st.data_editor(
                default,
                key="ux_table_corporate_social",
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                column_config={
                    "직원": st.column_config.NumberColumn(disabled=True, format="%d"),
                    "월 보수(원)": st.column_config.NumberColumn(min_value=0, max_value=10**12, step=10_000, format="%d원"),
                },
            )
            wages = [_won(value) for value in edited.get("월 보수(원)", []) if pd.notna(value)]
            values[4] = ";".join(str(value) for value in wages)
        else:
            values[4] = entries[4][1]

    elif name == "비상장주식 평가계산기":
        st.markdown("**3개년 순손익·조정액·평가용 주식수**")
        st.caption("연도별 값을 한 표에서 입력합니다. 주식 수가 같으면 각 행에 같은 값을 사용할 수 있습니다.")
        default = pd.DataFrame([
            {
                "기준": f"{year}년 전",
                "당기순손익(원)": 0 if reset_mode == "clear" else _won(entries[10 + index][1]),
                "평가 조정액(원)": 0 if reset_mode == "clear" else _won(entries[13 + index][1]),
                "평가용 주식수": 1 if reset_mode == "clear" else int(entries[16 + index][1]),
            }
            for index, year in enumerate((1, 2, 3))
        ])
        edited = st.data_editor(
            default,
            key="ux_table_unlisted",
            num_rows="fixed",
            hide_index=True,
            width="stretch",
            column_config={
                "기준": st.column_config.TextColumn(disabled=True),
                "당기순손익(원)": st.column_config.NumberColumn(min_value=-10**12, max_value=10**12, step=10_000, format="%d원"),
                "평가 조정액(원)": st.column_config.NumberColumn(min_value=-10**12, max_value=10**12, step=10_000, format="%d원"),
                "평가용 주식수": st.column_config.NumberColumn(min_value=1, max_value=10**10, step=1, format="%d"),
            },
        )
        for index in range(3):
            values[10 + index] = str(_won(edited.iloc[index]["당기순손익(원)"]))
            values[13 + index] = str(_won(edited.iloc[index]["평가 조정액(원)"]))
            values[16 + index] = int(edited.iloc[index]["평가용 주식수"])
    return consumed
