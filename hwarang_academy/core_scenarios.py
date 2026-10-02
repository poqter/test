"""Future-facing 26 core-scenario taxonomy.

The legacy 97-type taxonomy remains the source training map.  This module only
prepares a stable grouping layer so the Academy can later expose a smaller set
of user-facing missions without deleting historical skill definitions.

C07-S01 is the current Golden Scenario and maps to DISCOVER_02.  The remaining
core scenarios are intentionally *not* made executable by this module.
"""
from __future__ import annotations

CORE_TAXONOMY_VERSION = "26-core-2026.10"

CORE_SCENARIOS = {
    "CONTACT_01": {"category":"CONTACT", "name":"신규·소개 고객 첫 연락", "legacy_types":["A01","A02"]},
    "CONTACT_02": {"category":"CONTACT", "name":"기존·이관 고객 재접촉", "legacy_types":["A03","A04"]},
    "CONTACT_03": {"category":"CONTACT", "name":"약속·거절·일정변경 대응", "legacy_types":["A05","A06","A07","A08","A09"]},
    "RAPPORT_01": {"category":"RAPPORT", "name":"첫 상담 시작과 목적 합의", "legacy_types":["B01","B02","B03","B04"]},
    "RAPPORT_02": {"category":"RAPPORT", "name":"경계·불신 고객 관계형성", "legacy_types":["B05","B06","B07","B08"]},
    "DISCOVER_01": {"category":"DISCOVER", "name":"가족·생활·재무상황 탐색", "legacy_types":["C01","C02","C04","C05","C06"]},
    "DISCOVER_02": {"category":"DISCOVER", "name":"보험료·기존계약 탐색", "legacy_types":["C03","C07","C08"]},
    "DISCOVER_03": {"category":"DISCOVER", "name":"가입경험·불만·우선순위 탐색", "legacy_types":["C09"]},
    "DISCOVER_04": {"category":"DISCOVER", "name":"건강·민감정보 탐색", "legacy_types":["C10","C11","C12"]},
    "ANALYZE_01": {"category":"ANALYZE", "name":"증권 전체 구조와 핵심보장 분석", "legacy_types":["D01","D09","D13","D14","D15"]},
    "ANALYZE_02": {"category":"ANALYZE", "name":"암·뇌·심장 핵심보장 설명", "legacy_types":["D02","D03","D04","D05"]},
    "ANALYZE_03": {"category":"ANALYZE", "name":"사망·수술·입원·간병 보장", "legacy_types":["D06","D07","D10","D16"]},
    "ANALYZE_04": {"category":"ANALYZE", "name":"실손보험 분석", "legacy_types":["D08"]},
    "ANALYZE_05": {"category":"ANALYZE", "name":"운전자·자녀·기타 생활보장", "legacy_types":["D11","D12"]},
    "PROPOSE_01": {"category":"PROPOSE", "name":"유지·보완형 제안", "legacy_types":["E01","E04","E06"]},
    "PROPOSE_02": {"category":"PROPOSE", "name":"보험료 절감·감액·해지 검토", "legacy_types":["E02","E03","E05","E07"]},
    "PROPOSE_03": {"category":"PROPOSE", "name":"복수안 비교와 우선순위 결정", "legacy_types":["E08","E09","E10"]},
    "HANDLE_01": {"category":"HANDLE", "name":"가격·필요성 반론", "legacy_types":["F01","F02","F03"]},
    "HANDLE_02": {"category":"HANDLE", "name":"신뢰·비교·가족 반론", "legacy_types":["F04","F05","F06","F07","F08","F09"]},
    "HANDLE_03": {"category":"HANDLE", "name":"클로징과 다음 행동 합의", "legacy_types":["F10","F11","F12","F13","F14"]},
    "SERVICE_01": {"category":"SERVICE", "name":"고지·계약변경·중요사항 확인", "legacy_types":["G01","G02","G03","G04"]},
    "SERVICE_02": {"category":"SERVICE", "name":"보험금 청구 상담", "legacy_types":["G05","G06","G07","G08","G09","G10"]},
    "SERVICE_03": {"category":"SERVICE", "name":"갱신·실효·해지·민원 관리", "legacy_types":["G11","G12","G13","G14","G15","G16"]},
    "ADVISORY_01": {"category":"ADVISORY", "name":"은퇴·연금 상담", "legacy_types":["H01","H02","H03"]},
    "ADVISORY_02": {"category":"ADVISORY", "name":"상속·증여 상담", "legacy_types":["H04","H05","H06"]},
    "ADVISORY_03": {"category":"ADVISORY", "name":"법인대표·가업승계·고액자산 상담", "legacy_types":["H07","H08","H09","H10","H11","H12"]},
}

LEGACY_TO_CORE = {
    legacy: core_id
    for core_id, spec in CORE_SCENARIOS.items()
    for legacy in spec["legacy_types"]
}

if len(CORE_SCENARIOS) != 26:
    raise RuntimeError("Core scenario taxonomy must contain exactly 26 missions.")
if len(LEGACY_TO_CORE) != 97:
    raise RuntimeError(f"All 97 legacy types must be mapped exactly once; got {len(LEGACY_TO_CORE)}.")

GOLDEN_SCENARIO = {
    "scenario_id": "C07-S01",
    "legacy_type_id": "C07",
    "core_scenario_id": LEGACY_TO_CORE["C07"],
    "status": "golden",
}


def core_for_legacy(type_id: str) -> str | None:
    return LEGACY_TO_CORE.get(type_id)


def public_structure() -> dict:
    """Metadata only. It does not publish unfinished core missions to the UI."""
    return {
        "version": CORE_TAXONOMY_VERSION,
        "core_count": len(CORE_SCENARIOS),
        "legacy_count": len(LEGACY_TO_CORE),
        "golden": dict(GOLDEN_SCENARIO),
    }
