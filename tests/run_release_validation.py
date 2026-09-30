"""Run the complete offline release-validation suite and write one summary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _run(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }




def _git_diff_check() -> dict[str, Any]:
    if not (ROOT / ".git").exists():
        return {
            "name": "git_diff_check",
            "status": "PASS",
            "returncode": 0,
            "stdout": "packaged release: .git directory not included",
            "stderr": "",
        }
    return _run("git_diff_check", ["git", "diff", "--check"])

def run() -> dict[str, Any]:
    checks = [
        _run(
            "python_compileall",
            [sys.executable, "-m", "compileall", "-q", "app.py", "calculator_app.py", "modules", "tests"],
        ),
        _run("project_import_smoke", [sys.executable, "tests/run_import_smoke.py"]),
        _run("calculator_engine_regression", [sys.executable, "tests/run_calculator_regression.py"]),
        _run("calculator_ui_route_smoke", [sys.executable, "tests/run_ui_route_smoke.py"]),
        _run("pdf_smoke", [sys.executable, "tests/run_pdf_smoke.py"]),
        _run("all_calculator_pdf_regression", [sys.executable, "tests/run_all_calculator_pdf_regression.py"]),
        _run("architecture_validation", [sys.executable, "tests/run_architecture_validation.py"]),
        _git_diff_check(),
    ]
    passed = sum(item["status"] == "PASS" for item in checks)
    return {"count": len(checks), "passed": passed, "failed": len(checks) - passed, "checks": checks}


if __name__ == "__main__":
    report = run()
    output = ROOT / "tests" / "release_validation_results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "passed", "failed")}, ensure_ascii=False, indent=2))
    for item in report["checks"]:
        print(item["status"], item["name"])
        if item["status"] == "FAIL":
            if item["stdout"]:
                print(item["stdout"])
            if item["stderr"]:
                print(item["stderr"])
    raise SystemExit(0 if report["failed"] == 0 else 1)
