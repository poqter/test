"""Import every project Python module with a lightweight Streamlit stub."""
from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.streamlit_stub import install
install()



def run() -> dict:
    names = ["app", "calculator_app"]
    for path in sorted((ROOT / "modules").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        names.append(".".join(path.relative_to(ROOT).with_suffix("").parts))
    results = []
    for name in dict.fromkeys(names):
        try:
            importlib.import_module(name)
        except Exception as exc:
            results.append({"module": name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
        else:
            results.append({"module": name, "status": "PASS", "error": ""})
    passed = sum(item["status"] == "PASS" for item in results)
    return {"count": len(results), "passed": passed, "failed": len(results) - passed, "results": results}


if __name__ == "__main__":
    report = run()
    import os
    output = Path(os.environ.get("HW_TEST_OUTPUT_DIR", str(ROOT / "artifacts" / "validation"))) / "import_smoke_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "passed", "failed")}, ensure_ascii=False, indent=2))
    for item in report["results"]:
        if item["status"] == "FAIL":
            print("FAIL", item["module"], item["error"])
    raise SystemExit(0 if report["failed"] == 0 else 1)
