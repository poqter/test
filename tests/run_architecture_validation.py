"""Static and import-level validation for the split WORKSPACE/CALCULATOR release."""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.streamlit_stub import install

st = install()

EXPECTED_GROUP_COUNTS = {
    "보험 기본": 6,
    "보장·생활자금": 9,
    "연금·은퇴": 14,
    "재무·투자": 10,
    "개인·부동산 세금": 9,
    "상속·증여·승계": 9,
    "법인·대표 전략": 14,
    "사업·법인 실무": 17,
}
EXPECTED_GROUP_ITEMS = {
    "보험 기본": ("보험나이계산기", "다음 상령일계산기", "총 납입보험료계산기", "납입면제 효과계산기", "적정보험료계산기", "정기·종신 비교계산기"),
    "보장·생활자금": ("가족 생활자금계산기", "교육자금계산기", "부채 정리자금계산기", "비상자금 진단계산기", "사망보장 필요액계산기", "중대질병 보장계산기", "간병·장기요양 필요액계산기", "자녀보험 필요액계산기", "의료비 부담계산기"),
    "연금·은퇴": ("연금계산기", "은퇴계산기", "퇴직금계산기", "연금저축·IRP 세액공제계산기", "국민연금 수령시기계산기", "주택연금계산기", "일시금·연금 세금비교계산기", "은퇴크레바스계산기", "3층연금 점검계산기", "연금 인출기간계산기", "사적연금 과세계산기", "IRP 적립계산기", "은퇴저축계산기", "연금 인출순서계산기"),
    "재무·투자": ("미래가치계산기", "복리계산기", "수익률계산기", "재무계산기", "투자수익계산기", "현재가치계산기", "목표자금 계획계산기", "기회비용계산기", "물가 반영 필요자금계산기", "ISA 절세계산기"),
    "개인·부동산 세금": ("양도소득세계산기", "근로소득세계산기", "종합소득세계산기", "임대소득세계산기", "금융소득종합과세계산기", "주택담보대출 이자공제계산기", "4대보험계산기", "취득세 중과계산기", "해외금융계좌 신고계산기"),
    "상속·증여·승계": ("상속세계산기", "증여세계산기", "비상장주식 평가계산기", "가업승계 세부담계산기", "명의신탁주식계산기", "차등배당계산기", "특정법인 증여의제계산기", "지분 매입자금계산기", "승계 재원계산기"),
    "법인·대표 전략": ("인정이자계산기", "급여vs배당 비교계산기", "개인사업자·법인 비교계산기", "임원퇴직금 한도계산기", "가지급금 정밀진단계산기", "이익소각계산기", "법인청산 세부담계산기", "지주회사 수입배당금계산기", "합병 세부담계산기", "키맨리스크계산기", "특허권 자본화계산기", "법인 부동산 보유·양도 비교계산기", "특수관계자 임대료계산기", "법인보험 만기계산기"),
    "사업·법인 실무": ("창업중소기업 세액감면계산기", "성실신고 대상판정계산기", "법인세계산기", "법인세 중간예납계산기", "부가세 예정신고 선택계산기", "업무용승용차 비용계산기", "접대비 한도계산기", "고용증대 세액공제계산기", "연구인력개발비 세액공제계산기", "직무발명보상금계산기", "이월결손금계산기", "주식매수선택권계산기", "사내근로복지기금계산기", "법인 4대보험계산기", "상여금·복리후생비 비교계산기", "DC부담금 한도계산기", "정책자금 자격진단계산기"),
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
    group_order = tuple(group["group"] for group in catalog["groups"])
    items = [item for group in catalog["groups"] for item in group["calculators"]]
    ids = [item.get("id") for item in items]
    check("catalog_count_88", len(names) == 88, f"count={len(names)}")
    check("catalog_names_unique", len(set(names)) == 88, f"unique={len(set(names))}")
    check("catalog_ids_unique", len(set(ids)) == 88, f"unique={len(set(ids))}")
    check("catalog_ids_stable_format", all(re.fullmatch(r"calc-\d{3}", str(item_id)) for item_id in ids))
    check("catalog_title", catalog.get("title") == "화랑 종합 계산기 센터")
    check("catalog_declared_count", catalog.get("count") == 88, f"declared={catalog.get('count')}")
    check("catalog_group_order", group_order == tuple(EXPECTED_GROUP_COUNTS), repr(group_order))
    check("catalog_group_counts", group_counts == EXPECTED_GROUP_COUNTS, json.dumps(group_counts, ensure_ascii=False))
    group_items = {group["group"]: tuple(item["name"] for item in group["calculators"]) for group in catalog["groups"]}
    check("catalog_group_membership", group_items == EXPECTED_GROUP_ITEMS)
    metadata_ok = all(
        bool(str(item.get("description", "")).strip())
        and isinstance(item.get("tags"), list)
        and bool(item.get("tags"))
        for item in items
    )
    check("catalog_descriptions_and_tags", metadata_ok)
    from modules.calculators.calculator_center import QUICK_CALCULATOR_NAMES
    check("quick_calculators_in_catalog", set(QUICK_CALCULATOR_NAMES).issubset(names), f"quick={len(QUICK_CALCULATOR_NAMES)}")

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

    schema_errors: list[str] = []
    from datetime import date
    for name, entries in discovered.items():
        labels: list[str] = []
        for index, entry in enumerate(entries):
            if len(entry) != 4:
                schema_errors.append(f"{name}[{index}]: field tuple")
                continue
            label, default, unit, maximum = entry
            labels.append(str(label))
            if unit == "선택" and default not in maximum:
                schema_errors.append(f"{name}[{index}]: selection default")
            elif unit == "날짜":
                try:
                    date.fromisoformat(str(default))
                except ValueError:
                    schema_errors.append(f"{name}[{index}]: date default")
            elif unit not in {"문자", "선택", "날짜"} and maximum is not None:
                try:
                    if float(default) > float(maximum):
                        schema_errors.append(f"{name}[{index}]: default above maximum")
                except (TypeError, ValueError):
                    schema_errors.append(f"{name}[{index}]: numeric schema")
        if len(labels) != len(set(labels)):
            schema_errors.append(f"{name}: duplicate labels")
    check("calculator_field_schema", not schema_errors, ", ".join(schema_errors[:10]))

    from modules.calculators.calculator_catalog import MODES as QUICK_MODES
    from modules.calculators.calculator_center import QUICK_CALCULATORS
    quick_schema_ok = all(
        mode in QUICK_MODES
        and all(len(entry) == 6 and entry[4] <= entry[3] <= entry[5] for entry in QUICK_MODES[mode][2])
        for mode in QUICK_CALCULATORS.values()
    )
    check("quick_calculator_field_schema", quick_schema_ok)

    from modules.shell.app_registry import APP_BY_ID
    from modules.shell.navigation import normalize_route

    calculator_spec = APP_BY_ID["quick_calculators"]
    check(
        "calculator_registry_external",
        calculator_spec.source_status == "standalone" and calculator_spec.external_app_key == "calculator_url",
        f"status={calculator_spec.source_status}, key={calculator_spec.external_app_key}",
    )
    check("calculator_registry_title_88", calculator_spec.label == "종합 계산기 센터 (88개)", calculator_spec.label)
    check("external_route_not_dispatched", normalize_route("quick_calculators", "Admin") == "home")

    check("calculator_entrypoint_exists", (ROOT / "calculator_app.py").is_file())
    calculator_source = (ROOT / "calculator_app.py").read_text(encoding="utf-8")
    check(
        "calculator_entrypoint_public",
        all(term not in calculator_source for term in ("passwords", "render_login", "login_user", "authenticate")),
    )
    check("calculator_entrypoint_title_88", "종합 계산기 센터 (88개)" in calculator_source)
    check("calculator_styles_injected_once", calculator_source.count("inject_global_styles()") == 1 and calculator_source.count("apply_calculator_theme()") == 1)
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
    deep_links_ok = True
    deep_link_failures: list[str] = []
    if calculator_render_ok:
        for item in items:
            st.session_state.clear()
            st.query_params.clear()
            st.query_params["calc"] = item["id"]
            calculator_module._apply_calculator_deep_link()
            if st.session_state.get("jc_open") != item["name"]:
                deep_links_ok = False
                deep_link_failures.append(item["name"])
        st.query_params.clear()
        st.session_state.clear()
    check("calculator_deep_links_88", deep_links_ok, ", ".join(deep_link_failures[:10]))

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
        _launch_widget(calculator_spec, "종합 계산기 센터 (88개)", key="architecture_calculator_link")
        link_events = [event for event in st._api.events if event["kind"] == "link_button"]
        link_ok = bool(link_events) and link_events[-1]["args"][1] == "https://example-calculator.streamlit.app" and link_events[-1]["kwargs"].get("disabled") is False
        check("workspace_uses_external_link_button", link_ok)
        check("calculator_link_has_no_hover_help", bool(link_events) and link_events[-1]["kwargs"].get("help") is None)

        from modules.calculators.input_design import _primary_metric_index
        check(
            "representative_result_prefers_money",
            _primary_metric_index([("먼저 인출할 계좌", "일반 투자계좌"), ("기간 필요액", "720,000,000원")]) == 1,
        )
        from modules.calculators.visuals import category_label, primary_result_labels
        check(
            "representative_result_audited_override",
            _primary_metric_index(
                [("필요 연 수익률", "6.2%"), ("예상 최종 자금", "100,000,000원")],
                primary_result_labels("수익률계산기"),
            ) == 0,
        )
        check(
            "representative_result_status_override",
            _primary_metric_index(
                [("신고 대상 판단", "신고 대상"), ("판단 잔액", "800,000,000원")],
                primary_result_labels("해외금융계좌 신고계산기"),
            ) == 0,
        )
        check("calculator_category_visuals", category_label("보험 기본") == "🧾 보험 기본")
        check("calculator_category_count_label", category_label("사업·법인 실무", 17) == "🏢 사업·법인 실무 · 17")
        from modules.calculators.catalog_browser import calculator_deep_link, save_query
        check("calculator_deep_link_uses_stable_id", calculator_deep_link("보험나이계산기", {"보험나이계산기": "calc-001"}) == "?calc=calc-001")
        st.session_state.clear()
        st.session_state.update(jc_search="보험나이", jc_catalog_group="법인·대표 전략")
        save_query()
        check("calculator_search_is_global", st.session_state.get("jc_catalog_group") == "전체")

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

    legacy_brand_hits = []
    for path, text in _production_texts():
        if path.name == "jarvia_calculator_center.py":
            text = text.replace("jarvia_calculator_center", "")
        for term in ("JARVIA", "자비아", "원본 화면 대조", "계산식 구현 초안"):
            if term in text:
                legacy_brand_hits.append(f"{path.relative_to(ROOT)}:{term}")
    check("legacy_reference_copy_removed", not legacy_brand_hits, ", ".join(legacy_brand_hits[:10]))
    hub_source = (ROOT / "modules" / "calculators" / "jarvia_calculator_center.py").read_text(encoding="utf-8")
    check("legacy_duplicate_calculator_engine_removed", "def compute(" not in hub_source and "FIELDS =" not in hub_source)
    finance_ui_source = (ROOT / "modules" / "calculators" / "finance" / "finance_calculator_ui.py").read_text(encoding="utf-8")
    check("return_calculator_defaults_to_rate", "default_label = '필요 수익률' if name == '수익률계산기'" in finance_ui_source)

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
    from modules.calculators.input_design import uses_decimal_manwon
    decimal_manwon_ok = (
        uses_decimal_manwon("종신보험 월 보험료 (원)")
        and uses_decimal_manwon("보장성 보험료 월납 (원)")
        and not uses_decimal_manwon("월 생활비 (원)")
    )
    check("monthly_premium_decimal_manwon_rules", decimal_manwon_ok)

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
