"""Generate and parse one result PDF for every calculator in the 88-item catalog."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.run_calculator_regression import CATALOG_NAMES, _discover, _special_cases, _validate_result
from modules.calculators.result_pdf import build_result_pdf


def _validate_pdf(payload: bytes) -> tuple[int, int]:
    if not isinstance(payload, (bytes, bytearray)) or not payload.startswith(b"%PDF"):
        raise AssertionError("PDF signature missing")
    reader = PdfReader(io.BytesIO(payload))
    if not reader.pages:
        raise AssertionError("PDF has no pages")
    return len(payload), len(reader.pages)


def run() -> dict[str, Any]:
    discovered = _discover()
    special = _special_cases()
    results: list[dict[str, Any]] = []
    for name in CATALOG_NAMES:
        source = ""
        try:
            if name in special:
                function, source = special[name]
                result = function()
                inputs = [("검증 시나리오", "기본·대표 조건")]
            else:
                calculate, values, source = discovered[name]
                result = calculate(name, values)
                inputs = [("검증 입력 수", len(values)), ("계산 모듈", source)]
            _validate_result(result)
            payload = build_result_pdf(name, inputs, result, "2026-09-30 23:50")
            byte_count, page_count = _validate_pdf(payload)
        except Exception as exc:
            results.append({
                "name": name,
                "status": "FAIL",
                "source": source,
                "bytes": 0,
                "pages": 0,
                "error": f"{type(exc).__name__}: {exc}",
            })
        else:
            results.append({
                "name": name,
                "status": "PASS",
                "source": source,
                "bytes": byte_count,
                "pages": page_count,
                "error": "",
            })
    passed = sum(item["status"] == "PASS" for item in results)
    return {"count": len(results), "passed": passed, "failed": len(results) - passed, "results": results}


if __name__ == "__main__":
    report = run()
    output = ROOT / "tests" / "all_calculator_pdf_regression_results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "passed", "failed")}, ensure_ascii=False, indent=2))
    for item in report["results"]:
        if item["status"] == "FAIL":
            print("FAIL", item["name"], item["source"], item["error"])
    raise SystemExit(0 if report["failed"] == 0 else 1)
