"""Static and import-level validation for the split WORKSPACE/CALCULATOR release."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.streamlit_stub import install

st = install()

EXPECTED_GROUP_COUNTS = {
    "개인 · 세금": 11,
    "개인 · 연금·은퇴": 14,
    "개인 · 보장·설계": 7,
    "개인 · 재무계산": 9,
    "법인 · 대표 의사결정": 17,
    "법인 · 세무 실무": 22,
}
DELETED_TOKEN_PATHS = (
    "modules/calculators/dedicated_tab.py",
    "modules/calculators/tab_access.py",
    "modules/calculators/dedicated_theme.py",
    "modules/calculators/components/launcher.js",
    "modules/calculators/components/receiver.js",
)
BANNED_TOKEN_TERMS = (
    "dedicated_tab",
    "tab_access",
    "issue_grant",
    "claim_grant",
    "verify_lease",
    "hw_calc_grant",
    "hw_calc_lease",
    "receiver.js",
    "launcher.js",
)
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}


def _catalog() -> tuple[dict[str, Any], list[str]]:
    data = json.loads((ROOT / "FINANCIAL_CALCULATORS_CATALOG.json").read_text(encoding="utf-8"))
    names = [item["name"] for group in data["groups"] for item in group["calculators"]]
    return data, names


def _production_texts() -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for root in (ROOT / "modules",):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".js"} and "__pycache__" not in path.parts:
                rows.append((path, path.read_text(encoding="utf-8")))
    for path in (ROOT / "app.py", ROOT / "calculator_app.py"):
        rows.append((path, path.read_text(encoding="utf-8")))
    return rows


def _discover_fields(catalog_names: set[str]) -> dict[str, list[tuple]]:
    found: dict[str, list[tuple]] = {}
    for path in sorted((ROOT / "modules" / "calculators").rglob("*.py")):
        if path.name.startswith("__") or "__pycache__" in path.parts:
            continue
        module_name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if any(token in module_name for token in (
            "_ui", "calculator_center", "catalog_browser", "calculator_shell", "calculator_theme",
            "result_", "structured_inputs", "ux_profiles", "valuation_transfer",
        )):
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        fields = getattr(module, "FIELDS", None)
        if not isinstance(fields, dict):
            continue
        for name, entries in fields.items():
            if name in catalog_names and name not in found and isinstance(entries, list):
                found[name] = entries
    return found


def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    catalog, names = _catalog()
    group_counts = {group["group"]: len(group["calculators"]) for group in catalog["groups"]}
    check("catalog_count_80", len(names) == 80, f"count={len(names)}")
    check("catalog_names_unique", len(set(names)) == 80, f"unique={len(set(names))}")
    check("catalog_group_counts", group_counts == EXPECTED_GROUP_COUNTS, json.dumps(group_counts, ensure_ascii=False))

    from modules.calculators.ux_profiles import ordered_indices, profiles

    profile_map = profiles()
    check("ux_profiles_exact_catalog", set(profile_map) == set(names), f"profiles={len(profile_map)}")
    valid_priorities = {"높음", "중간", "유지"}
    profile_fields_ok = all(
        row.get("priority") in valid_priorities
        and bool(str(row.get("core", "")).strip())
        and bool(str(row.get("improvements", "")).strip())
        and bool(str(row.get("section", "")).strip())
        for row in profile_map.values()
    )
    check("ux_profiles_complete", profile_fields_ok)

    discovered = _discover_fields(set(names))
    permutations_ok = True
    bad_permutations: list[str] = []
    for name, entries in discovered.items():
        ordered = ordered_indices(name, entries)
        if sorted(ordered) != list(range(len(entries))):
            permutations_ok = False
            bad_permutations.append(name)
    check("metadata_order_permutations", permutations_ok, ", ".join(bad_permutations))

    from modules.shell.app_registry import APP_BY_ID
    from modules.shell.navigation import normalize_route

    calculator_spec = APP_BY_ID["quick_calculators"]
    check(
        "calculator_registry_external",
        calculator_spec.source_status == "standalone" and calculator_spec.external_app_key == "calculator_url",
        f"status={calculator_spec.source_status}, key={calculator_spec.external_app_key}",
    )
    check("external_route_not_dispatched", normalize_route("quick_calculators", "Admin") == "home")

    check("calculator_entrypoint_exists", (ROOT / "calculator_app.py").is_file())
    calculator_source = (ROOT / "calculator_app.py").read_text(encoding="utf-8")
    check(
        "calculator_entrypoint_public",
        all(term not in calculator_source for term in ("passwords", "render_login", "login_user", "authenticate")),
    )
    calculator_render_ok = True
    calculator_render_detail = ""
    try:
        calculator_module = importlib.import_module("calculator_app")
        calculator_module.main()
    except Exception as exc:
        calculator_render_ok = False
        calculator_render_detail = f"{type(exc).__name__}: {exc}"
    finally:
        st.session_state.clear()
    check("calculator_entrypoint_first_render", calculator_render_ok, calculator_render_detail)

    from modules.shared.external_apps import calculator_url, external_app_url

    original_secrets = dict(st.secrets)
    original_env = os.environ.get("HW_CALCULATOR_URL")
    try:
        st.secrets.clear()
        st.secrets["external_apps"] = {"calculator_url": "https://example-calculator.streamlit.app/"}
        check("external_url_from_secrets", calculator_url() == "https://example-calculator.streamlit.app")
        st.secrets["external_apps"] = {"calculator_url": "javascript:alert(1)"}
        check("external_url_scheme_validation", calculator_url() == "")
        st.secrets.clear()
        os.environ["HW_CALCULATOR_URL"] = "https://env-calculator.streamlit.app/"
        check("external_url_environment_fallback", external_app_url("calculator_url") == "https://env-calculator.streamlit.app")

        st.secrets.clear()
        st.secrets["external_apps"] = {"calculator_url": "https://example-calculator.streamlit.app"}
        from modules.shell.workspace_v2 import _launch_widget
        st._api.events.clear()
        _launch_widget(calculator_spec, "종합계산기(80개)", key="architecture_calculator_link")
        link_events = [event for event in st._api.events if event["kind"] == "link_button"]
        link_ok = bool(link_events) and link_events[-1]["args"][1] == "https://example-calculator.streamlit.app" and link_events[-1]["kwargs"].get("disabled") is False
        check("workspace_uses_external_link_button", link_ok)
        check("calculator_link_has_no_hover_help", bool(link_events) and link_events[-1]["kwargs"].get("help") is None)

        from modules.calculators.input_design import _primary_metric_index
        check(
            "representative_result_prefers_money",
            _primary_metric_index([("먼저 인출할 계좌", "일반 투자계좌"), ("기간 필요액", "720,000,000원")]) == 1,
        )
        from modules.calculators.visuals import category_label
        check("calculator_category_visuals", category_label("개인 · 세금") == "🧾 세금")

        st.session_state.clear()
        st.session_state.update(password_correct=True, login_user="Admin", active_app="home")
        workspace_render_ok = True
        workspace_render_detail = ""
        try:
            workspace_module = importlib.import_module("app")
            workspace_module.main()
        except Exception as exc:
            workspace_render_ok = False
            workspace_render_detail = f"{type(exc).__name__}: {exc}"
        check("workspace_home_first_render", workspace_render_ok, workspace_render_detail)
    finally:
        st.secrets.clear()
        st.secrets.update(original_secrets)
        if original_env is None:
            os.environ.pop("HW_CALCULATOR_URL", None)
        else:
            os.environ["HW_CALCULATOR_URL"] = original_env

    deleted_ok = all(not (ROOT / relative).exists() for relative in DELETED_TOKEN_PATHS)
    check("legacy_token_files_removed", deleted_ok)
    token_hits = []
    for path, text in _production_texts():
        for term in BANNED_TOKEN_TERMS:
            if term in text:
                token_hits.append(f"{path.relative_to(ROOT)}:{term}")
    check("legacy_token_references_removed", not token_hits, ", ".join(token_hits[:10]))

    font_files = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file() and path.suffix.lower() in FONT_SUFFIXES]
    check("font_binaries_absent", not font_files, ", ".join(font_files))
    check("real_streamlit_secrets_absent", not (ROOT / ".streamlit" / "secrets.toml").exists())
    check("secrets_example_present", (ROOT / ".streamlit" / "secrets.example.toml").exists())

    hardcoded_urls = []
    for path, text in _production_texts():
        relative = str(path.relative_to(ROOT))
        if relative == "modules/shared/external_apps.py":
            continue
        if "streamlit.app" in text:
            hardcoded_urls.append(relative)
    check("no_hardcoded_deployed_url", not hardcoded_urls, ", ".join(hardcoded_urls))

    from modules.calculators.coverage.coverage_calculator_ui import _uses_won_precision

    precision_ok = (
        _uses_won_precision("1주당 평가액")
        and _uses_won_precision("액면가")
        and _uses_won_precision("행사가액")
        and not _uses_won_precision("총재산 평가액")
    )
    check("direct_won_precision_rules", precision_ok)

    from modules.calculators.structured_inputs import handled_indices

    repeat_inputs_ok = (
        handled_indices("이월결손금계산기") == {0}
        and handled_indices("법인 4대보험계산기") == {4}
        and handled_indices("비상장주식 평가계산기") == set(range(10, 19))
    )
    check("repeat_input_mappings", repeat_inputs_ok)

    passed = sum(item["status"] == "PASS" for item in checks)
    return {"count": len(checks), "passed": passed, "failed": len(checks) - passed, "checks": checks}


if __name__ == "__main__":
    report = run()
    output = ROOT / "tests" / "architecture_validation_results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "passed", "failed")}, ensure_ascii=False, indent=2))
    for item in report["checks"]:
        if item["status"] == "FAIL":
            print("FAIL", item["name"], item["detail"])
    raise SystemExit(0 if report["failed"] == 0 else 1)
