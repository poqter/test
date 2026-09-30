"""Run deterministic default-scenario regression checks for all 80 calculators."""
from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CATALOG = json.loads((ROOT / "FINANCIAL_CALCULATORS_CATALOG.json").read_text(encoding="utf-8"))
CATALOG_NAMES = [item["name"] for group in CATALOG["groups"] for item in group["calculators"]]

# Pure calculation modules do not use Streamlit at runtime, but a few import a
# presentation helper transitively. A tiny import stub keeps this CLI test free
# from a Streamlit installation.
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.ModuleType("streamlit")


def _adjust_default(entry: tuple[Any, ...]) -> Any:
    label, default, unit, options = entry
    if unit == "선택":
        choices = tuple(options)
        if default in ("미확인", "확인중"):
            for choice in choices:
                if choice in ("확인", "예", "해당없음"):
                    return choice
        if any(word in str(label) for word in ("확인", "요건", "자격", "시가 우선")):
            for choice in choices:
                if choice in ("확인", "예", "요건 충족"):
                    return choice
    return default


def _module_candidates() -> list[str]:
    result = []
    for path in sorted((ROOT / "modules" / "calculators").rglob("*.py")):
        if path.name.startswith("__"):
            continue
        relative = path.relative_to(ROOT).with_suffix("")
        module = ".".join(relative.parts)
        if any(token in module for token in (
            "_ui", "calculator_center", "catalog_browser", "calculator_shell", "calculator_theme",
            "dedicated", "result_", "structured_inputs", "ux_profiles", "valuation_transfer",
        )):
            continue
        result.append(module)
    return result


_SCENARIO_OVERRIDES: dict[str, dict[int, Any]] = {
    # Keep mutually exclusive confirmation fields consistent with their default mode.
    "상속세계산기": {18: "아니요"},
    "양도소득세계산기": {13: "아니요"},
    "증여세계산기": {23: "아니요"},
    "차등배당계산기": {4: "예", 8: "아니요", 22: "배당가산 비대상 확인"},
    "해외금융계좌 신고계산기": {4: "거주자·내국법인, 면제 없음 확인", 6: "확인"},
}


def _discover() -> dict[str, tuple[Callable[..., Any], list[Any], str]]:
    found: dict[str, tuple[Callable[..., Any], list[Any], str]] = {}
    for module_name in _module_candidates():
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        fields = getattr(module, "FIELDS", None)
        calculate = getattr(module, "calculate", None)
        if not isinstance(fields, dict) or not callable(calculate):
            continue
        for name, entries in fields.items():
            if name not in CATALOG_NAMES or name in found:
                continue
            values = [_adjust_default(entry) for entry in entries]
            for index, value in _SCENARIO_OVERRIDES.get(name, {}).items():
                values[index] = value
            found[name] = (calculate, values, module_name)
    return found


def _special_cases() -> dict[str, tuple[Callable[[], Any], str]]:
    from modules.calculators.finance import finance_models as finance
    from modules.calculators.pension.pension_models import PensionPlan, calculate as pension_calculate
    from modules.calculators.pension import retirement_plan
    from modules.calculators.pension.retirement_remaining import FIELDS as RR_FIELDS, SAVE, saving, withdrawal

    return {
        "미래가치계산기": (lambda: finance.future_value(), "finance.future_value"),
        "복리계산기": (lambda: finance.compound(), "finance.compound"),
        "수익률계산기": (lambda: finance.tvm("rate", principal=10_000_000, payment=500_000, target=100_000_000, years=10, frequency=12), "finance.tvm(rate)"),
        "재무계산기": (lambda: finance.tvm("future", principal=10_000_000, payment=500_000, years=10, rate=5, frequency=12), "finance.tvm(future)"),
        "투자수익계산기": (lambda: finance.investment(), "finance.investment"),
        "현재가치계산기": (lambda: finance.present_value(), "finance.present_value"),
        "비상자금 진단계산기": (lambda: finance.emergency(3_000_000, 6, 20_000_000, 5_000_000, 0, 2_000_000), "finance.emergency"),
        "목표자금 계획계산기": (lambda: finance.goals([{"name": "자녀 교육비", "target": 100_000_000, "principal": 10_000_000, "years": 10, "rate": 4}], 500_000), "finance.goals"),
        "기회비용계산기": (lambda: finance.opportunity(300_000), "finance.opportunity"),
        "연금계산기": (lambda: pension_calculate(PensionPlan()), "pension.calculate"),
        "은퇴계산기": (lambda: retirement_plan.calculate(retirement_plan.MODES[0], [entry[1] for entry in retirement_plan.FIELDS[retirement_plan.MODES[0]]]), "retirement_plan.calculate"),
        "은퇴저축계산기": (lambda: saving(SAVE, [entry[1] for entry in RR_FIELDS[SAVE]]), "retirement_remaining.saving"),
        "연금 인출순서계산기": (lambda: withdrawal(3_000_000, 20, [("연금저축·IRP", 100_000_000, 5.5), ("일반 투자계좌", 100_000_000, 0), ("예적금", 100_000_000, 0)]), "retirement_remaining.withdrawal"),
    }


def _validate_result(result: Any) -> None:
    metrics = getattr(result, "metrics", None)
    if metrics is None and isinstance(result, tuple):
        metrics = result[0]
    if not isinstance(metrics, dict) or not metrics:
        raise AssertionError("결과 지표가 비어 있습니다.")
    display = getattr(result, "display", None)
    if callable(display):
        shown = display()
        if not isinstance(shown, dict) or not shown:
            raise AssertionError("표시용 결과가 비어 있습니다.")


def run() -> dict[str, Any]:
    discovered = _discover()
    special = _special_cases()
    results = []
    for name in CATALOG_NAMES:
        source = ""
        try:
            if name in special:
                fn, source = special[name]
                result = fn()
            else:
                calculate, values, source = discovered[name]
                result = calculate(name, values)
            _validate_result(result)
        except Exception as exc:
            results.append({"name": name, "status": "FAIL", "source": source, "error": f"{type(exc).__name__}: {exc}"})
        else:
            results.append({"name": name, "status": "PASS", "source": source, "error": ""})
    missing = [name for name in CATALOG_NAMES if name not in discovered and name not in special]
    passed = sum(item["status"] == "PASS" for item in results)
    return {
        "catalog_count": len(CATALOG_NAMES),
        "unique_count": len(set(CATALOG_NAMES)),
        "passed": passed,
        "failed": len(results) - passed,
        "missing_routes": missing,
        "group_counts": {group["group"]: len(group["calculators"]) for group in CATALOG["groups"]},
        "results": results,
    }


if __name__ == "__main__":
    report = run()
    output = ROOT / "tests" / "calculator_regression_results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("catalog_count", "unique_count", "passed", "failed", "missing_routes")}, ensure_ascii=False, indent=2))
    for item in report["results"]:
        if item["status"] != "PASS":
            print("FAIL", item["name"], item["source"], item["error"])
    raise SystemExit(0 if report["failed"] == 0 and not report["missing_routes"] else 1)
