"""Synthetic fixtures only; no customer or staff records."""
from __future__ import annotations

import io

from openpyxl import Workbook


def synthetic_contract_rows() -> list[dict[str, object]]:
    return [
        {"synthetic_id": "SYN-001", "premium": 100_000, "months": 120},
        {"synthetic_id": "SYN-002", "premium": 50_000, "months": 60},
    ]


def synthetic_xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "가상자료"
    sheet.append(["가상ID", "보험료", "개월"])
    for row in synthetic_contract_rows():
        sheet.append([row["synthetic_id"], row["premium"], row["months"]])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
