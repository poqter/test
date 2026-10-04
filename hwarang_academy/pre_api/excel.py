"""Approved-format coverage-analysis Excel generator.

The writer loads a sanitized template derived from the user-provided real
'보장 분석' workbook style. It writes synthetic Case data only; the workbook does
not expose Ground Truth, recommendation scores, or evaluator answers.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from .constants import EXCEL_TEMPLATE_VERSION, MAX_CONTRACTS_V1
from .coverage import EXCEL_COVERAGE_ROWS, excel_contract_matrix

_TEMPLATE = Path(__file__).resolve().parents[1] / "data" / "templates" / "coverage_analysis_v3_template.xlsx"
_CONTRACT_COLUMNS = ("D", "E", "F", "G", "H", "I", "J")


def _safe_number(value: Any) -> int | None:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return None
    return number if number != 0 else None


def workbook_payload(customer_state: dict[str, Any], insurance_state: dict[str, Any]) -> dict[str, Any]:
    """Return a spreadsheet-neutral payload; used for validation without editing XLSX files."""
    contracts = list(insurance_state.get("contracts", []))[:MAX_CONTRACTS_V1]
    matrix = excel_contract_matrix({"contracts": contracts})
    rows: list[dict[str, Any]] = []
    for row_no, (label, code) in enumerate(EXCEL_COVERAGE_ROWS, start=11):
        values = matrix.get(code, [None] * len(contracts)) if code else [None] * len(contracts)
        total = sum(int(v or 0) for v in values)
        rows.append({"row": row_no, "label": label, "coverage_code": code, "total_manwon": total or None, "values": values})
    return {
        "template_version": EXCEL_TEMPLATE_VERSION,
        "customer_name": customer_state.get("alias") or customer_state.get("public_state", {}).get("customer_alias") or "가상고객",
        "insurance_age": int(customer_state.get("age") or customer_state.get("ground_truth", {}).get("identity", {}).get("age", 30)),
        "contracts": contracts,
        "coverage_rows": rows,
        "total_monthly_premium_won": sum(int(c.get("premium_won") or 0) for c in contracts),
        "total_paid_amount_won": sum(int(c.get("paid_amount_won") or 0) for c in contracts),
        "total_future_amount_won": sum(int(c.get("future_amount_won") or 0) for c in contracts),
        "total_contract_amount_won": sum(int(c.get("total_amount_won") or 0) for c in contracts),
    }


def build_coverage_analysis_xlsx(customer_state: dict[str, Any], insurance_state: dict[str, Any]) -> bytes:
    """Generate the approved-layout workbook bytes.

    openpyxl is imported lazily because the application already ships it for
    Excel output. This function is not needed to run the rule-based simulator.
    """
    from openpyxl import load_workbook  # runtime dependency already present in HWARANG

    if not _TEMPLATE.exists():
        raise FileNotFoundError(f"coverage analysis template missing: {_TEMPLATE}")
    payload = workbook_payload(customer_state, insurance_state)
    wb = load_workbook(_TEMPLATE)
    ws = wb["보장 분석"]

    ws["A1"] = f"{payload['customer_name']}님의 보장 분석 (보험연령:{payload['insurance_age']}세)"

    contracts = payload["contracts"]
    for idx, col in enumerate(_CONTRACT_COLUMNS):
        if idx < len(contracts):
            c = contracts[idx]
            ws[f"{col}2"] = c.get("insurer")
            ws[f"{col}3"] = c.get("product_name")
            ws[f"{col}4"] = f"{c.get('start_date')}~{c.get('coverage_end')}"
            ws[f"{col}5"] = f"{int(c.get('paid_months') or 0)}/{int(c.get('total_payment_months') or 0)}회"
            ws[f"{col}6"] = f"{c.get('payment_cycle') or '월납'} / {c.get('payment_end') or '-'}"
            ws[f"{col}7"] = _safe_number(c.get("premium_won"))
            ws[f"{col}8"] = _safe_number(c.get("paid_amount_won"))
            ws[f"{col}9"] = _safe_number(c.get("future_amount_won"))
            ws[f"{col}10"] = _safe_number(c.get("total_amount_won"))
        else:
            for row in range(2, 50):
                ws[f"{col}{row}"] = None

    # Row totals and coverage values. 0 is always written as blank.
    for row in range(7, 11):
        values = [ws[f"{col}{row}"].value for col in _CONTRACT_COLUMNS]
        total = sum(int(v or 0) for v in values if isinstance(v, (int, float)))
        ws[f"A{row}"] = total or None

    for row_data in payload["coverage_rows"]:
        row = int(row_data["row"])
        ws[f"A{row}"] = row_data["total_manwon"]
        values = list(row_data["values"])
        for idx, col in enumerate(_CONTRACT_COLUMNS):
            ws[f"{col}{row}"] = _safe_number(values[idx]) if idx < len(values) else None

    # Preserve the approved template's blank-zero appearance explicitly.
    blank_zero_format = '#,##0;[Red]-#,##0;;'
    for row in range(7, 50):
        ws[f"A{row}"].number_format = blank_zero_format
        for col in _CONTRACT_COLUMNS:
            ws[f"{col}{row}"].number_format = blank_zero_format

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def suggested_filename(customer_state: dict[str, Any]) -> str:
    alias = str(customer_state.get("alias") or "가상고객").replace("/", "-")
    return f"{alias}_보장분석_시뮬레이션.xlsx"
