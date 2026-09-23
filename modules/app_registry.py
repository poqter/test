"""Pure page metadata and role permissions for HWARANG WORKSPACE.

This module deliberately has no Streamlit or page-module imports.  Page modules
are stored as strings and imported only by :mod:`modules.navigation`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Final, Mapping


@dataclass(frozen=True, slots=True)
class AppSpec:
    id: str
    label: str
    group_id: str
    description: str
    keywords: tuple[str, ...]
    module_path: str
    entrypoint: str = "run"
    icon_key: str = "tool"
    order: int = 0
    enabled: bool = True
    source_status: str = "legacy"


@dataclass(frozen=True, slots=True)
class GroupSpec:
    id: str
    label: str
    description: str
    order: int


GROUPS: Final[tuple[GroupSpec, ...]] = (
    GroupSpec("consultation", "상담·제안서", "상담 흐름과 고객 설명을 준비합니다.", 10),
    GroupSpec("calculators", "재무·보험 계산", "조건과 가정을 확인하며 수치를 계산합니다.", 20),
    GroupSpec("analysis", "보험자료 분석", "보험 자료를 검토하고 분석 결과를 만듭니다.", 30),
    GroupSpec("materials", "고객 전달자료", "비교표와 청구 안내를 준비합니다.", 40),
    GroupSpec("education", "교육·체크리스트", "용어와 상담 절차를 익히고 연습합니다.", 50),
    GroupSpec("official", "원수사·공식정보", "보험사 전산과 공식 업무자료를 찾습니다.", 60),
    GroupSpec("performance", "실적·수수료", "계약 자료와 실적·수수료를 집계합니다.", 70),
)


APPS: Final[tuple[AppSpec, ...]] = (
    AppSpec("consultation_helper", "상담·제안서 스튜디오", "consultation", "상담 준비부터 요약·고객 전달문·제안서 PDF까지 정리합니다.", ("문자", "생애주기", "질문", "상담요약", "스크립트", "제안서", "PDF"), "modules.consultation_helper", icon_key="consultation", order=10, source_status="stage3"),
    AppSpec("quick_calculators", "재무·보험 계산기", "calculators", "보험·생활·미래 준비를 위한 13개 계산과 검토용 자료를 만듭니다.", ("보험나이", "상령일", "총납입", "비상자금", "납입면제", "교육자금", "은퇴", "저축", "물가", "부채"), "modules.quick_calculators", icon_key="calculator", order=20, source_status="stage4"),
    AppSpec("deposit_vs_shortpay", "적금 vs 단기납", "calculators", "10년 기준 적금과 단기납의 예상 결과를 비교합니다.", ("저축", "적금", "단기납", "환급"), "modules.deposit_vs_shortpay", icon_key="compare", order=30),
    AppSpec("renewal_vs_nonrenewal", "갱신 vs 비갱신", "calculators", "보험료 변동을 반영해 장기 총납입액을 비교합니다.", ("갱신보험료", "총납입", "갱신형", "비갱신형"), "modules.renewal_vs_nonrenewal", icon_key="compare", order=40),
    AppSpec("inheritance_tax", "상속세 계산기", "calculators", "예상 상속세와 부족한 현금성 납부재원을 계산합니다.", ("상속세", "상속", "재산", "납부재원"), "modules.inheritance_tax", icon_key="tax", order=50),
    AppSpec("analyzer", "보장 분석 도우미", "analysis", "보험사 보장분석 자료를 고객용 양식으로 변환합니다.", ("보장분석", "증권", "고객용", "엑셀"), "modules.analyzer", icon_key="analysis", order=60),
    AppSpec("remodeling", "보험 리모델링", "analysis", "변경안을 비교하고 고객용 엑셀 자료를 만듭니다.", ("보험료", "변경안", "리모델링"), "modules.remodeling", icon_key="remodeling", order=70),
    AppSpec("silson_generation_comparison", "실손보험 세대 비교", "analysis", "현재 가입 실손과 5세대 실손의 보험료와 입원 보장을 비교합니다.", ("실손", "실비", "세대", "입원"), "modules.silson_generation_comparison", icon_key="medical", order=80),
    AppSpec("comparison_builder", "고객용 비교표 제작기", "materials", "금액·기간·조건을 비교하고 순서를 정해 Excel·PDF로 전달합니다.", ("비교표", "워터마크", "설명문", "변경안"), "modules.comparison_builder", icon_key="materials", order=90, source_status="stage5"),
    AppSpec("customer_materials", "고객자료 제작기", "materials", "9개 안내 양식과 상담·계산 결과로 고객 전달자료를 만듭니다.", ("고객자료", "안내문", "한 장 요약", "전달자료", "계약 변경"), "modules.customer_materials", icon_key="materials", order=95, source_status="stage5"),
    AppSpec("insurance_claim_guide", "보험금 청구 가이드", "materials", "청구 항목별 필요서류를 확인하고 관련 담보를 찾습니다.", ("청구서류", "진단서", "보험금", "안내문"), "modules.insurance_claim_guide", icon_key="claim", order=100),
    AppSpec("education_center", "교육·체크리스트 센터", "education", "용어·상담 연습·오답 복습·체크리스트와 수동 연구노트를 제공합니다.", ("교육", "용어", "설명의무", "퀴즈", "신입", "FAQ", "연구노트", "오답"), "modules.education_center", icon_key="education", order=110, source_status="stage6"),
    AppSpec("insurer_portal", "원수사·공식자료 포털", "official", "보험사 전산·연락처·서식과 공식기관 자료를 찾습니다.", ("전산", "원수사", "보험사", "서식", "공공사이트", "콜센터", "포털"), "modules.insurer_portal", icon_key="official", order=120, source_status="stage7"),
    AppSpec("convention", "컨벤션 계산기", "performance", "계약 실적을 환산하고 컨벤션 달성 여부를 확인합니다.", ("실적", "달성", "컨벤션", "환산"), "modules.convention", icon_key="performance", order=130),
    AppSpec("summer", "썸머 계산기", "performance", "7·8월 업적을 반영해 썸머 업적을 계산합니다.", ("실적", "썸머", "업적", "여름"), "modules.summer", icon_key="performance", order=140),
    AppSpec("manager_results", "매니저 업적 환산", "performance", "지점 실적 환산금액을 집계합니다.", ("지점", "매니저", "조직", "환산"), "modules.manager_results", icon_key="performance", order=150),
    AppSpec("commission_calculator", "수수료 계산기", "performance", "예시표에서 상품별 수수료율을 찾아 예상 수당을 계산합니다.", ("수당", "수수료", "예시표", "수수료율"), "modules.commission_calculator", icon_key="performance", order=160),
)

APP_BY_ID: Final[Mapping[str, AppSpec]] = MappingProxyType({app.id: app for app in APPS})
APP_IDS: Final[tuple[str, ...]] = tuple(app.id for app in APPS)
ROLES: Final[tuple[str, ...]] = ("Admin", "Manager1", "Basic", "Crew", "Dream")

_ALL = frozenset(APP_IDS)
ROLE_PERMISSIONS: Final[Mapping[str, frozenset[str]]] = MappingProxyType({
    "Admin": _ALL,
    "Manager1": _ALL,
    "Basic": frozenset({"analyzer", "insurer_portal", "insurance_claim_guide", "silson_generation_comparison", "convention", "summer", "quick_calculators", "consultation_helper", "comparison_builder", "customer_materials", "education_center"}),
    "Crew": frozenset({"analyzer", "deposit_vs_shortpay", "renewal_vs_nonrenewal", "insurer_portal", "insurance_claim_guide", "silson_generation_comparison", "convention", "summer", "quick_calculators", "consultation_helper", "comparison_builder", "customer_materials", "education_center"}),
    "Dream": frozenset({"analyzer", "remodeling", "deposit_vs_shortpay", "renewal_vs_nonrenewal", "inheritance_tax", "insurer_portal", "insurance_claim_guide", "silson_generation_comparison", "convention", "summer", "quick_calculators", "consultation_helper", "comparison_builder", "customer_materials", "education_center"}),
})

# Search aliases are static public labels only. Customer input never enters this index.
SEARCH_ALIASES: Final[Mapping[str, tuple[str, str | None]]] = MappingProxyType({
    "소득상실": ("quick_calculators", "소득상실·비상자금"),
    "비상자금": ("quick_calculators", "소득상실·비상자금"),
    "상령일": ("quick_calculators", "보험나이·상령일"),
    "청구서류": ("insurance_claim_guide", None),
    "상담 문자": ("consultation_helper", "고객 유형별 문자"),
})


def public_definition_map() -> dict[str, dict[str, object]]:
    """Return a UI compatibility view containing static metadata only."""
    result: dict[str, dict[str, object]] = {}
    group_labels = {group.id: group.label for group in GROUPS}
    for app in APPS:
        item = asdict(app)
        item.update(name=app.label, group=group_labels[app.group_id], category=group_labels[app.group_id])
        result[app.id] = item
    return result


APP_DEFINITIONS: Final[dict[str, dict[str, object]]] = public_definition_map()
USER_PERMISSIONS: Final[dict[str, dict[str, bool]]] = {
    role: {app_id: app_id in allowed for app_id in APP_IDS}
    for role, allowed in ROLE_PERMISSIONS.items()
}
