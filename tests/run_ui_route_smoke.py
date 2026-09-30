"""Exercise the first render path for every standalone calculator route."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.streamlit_stub import install

st = install()

from modules.calculators.calculator_center import run

CATALOG = json.loads((ROOT / "FINANCIAL_CALCULATORS_CATALOG.json").read_text(encoding="utf-8"))
NAMES = [item["name"] for group in CATALOG["groups"] for item in group["calculators"]]


def smoke() -> dict:
    results = []
    for name in NAMES:
        st.session_state.clear()
        st.session_state["jc_open"] = name
        st.session_state["jc_selected"] = name
        try:
            run()
        except Exception as exc:
            results.append({"name": name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
        else:
            results.append({"name": name, "status": "PASS", "error": ""})
    passed = sum(row["status"] == "PASS" for row in results)
    return {"count": len(NAMES), "passed": passed, "failed": len(NAMES) - passed, "results": results}


if __name__ == "__main__":
    report = smoke()
    path = ROOT / "tests" / "ui_route_smoke_results.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("count", "passed", "failed")}, ensure_ascii=False, indent=2))
    for row in report["results"]:
        if row["status"] == "FAIL":
            print("FAIL", row["name"], row["error"])
    raise SystemExit(0 if report["failed"] == 0 else 1)
