"""Central permission catalog for HWARANG feature-level authorization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class PermissionSpec:
    code: str
    app_code: str
    group_label: str
    display_name: str
    description: str
    sort_order: int
    default_granted: bool = True


PERMISSIONS: Final[tuple[PermissionSpec, ...]] = (
    PermissionSpec("workspace.briefing", "workspace", "브리핑", "브리핑 조회", "경제·보험·국내뉴스 브리핑 조회", 5, True),
    PermissionSpec("workspace.briefing_manage", "workspace", "브리핑", "브리핑 콘텐츠 관리", "브리핑 생성·검수·공개 관리", 6, False),
    PermissionSpec("workspace.consultation", "workspace", "상담", "상담 지원", "상담 질문지 제작 등 상담 준비 기능", 10, True),
    PermissionSpec("workspace.coverage_analysis", "workspace", "상담", "보장 분석", "보장분석 및 실손 세대 비교 기능", 20, True),
    PermissionSpec("workspace.remodeling", "workspace", "상담", "보험 리모델링", "보험 리모델링 기능", 30, False),
    PermissionSpec("workspace.comparison_tools", "workspace", "계산·비교", "비교 계산", "적금·단기납, 갱신·비갱신 비교 기능", 40, False),
    PermissionSpec("workspace.customer_materials", "workspace", "고객자료", "고객 전달자료", "고객용 비교표 및 보험금 청구 가이드", 50, True),
    PermissionSpec("workspace.official_resources", "workspace", "자료", "원수사·공식자료", "원수사 및 공식자료 포털", 60, True),
    PermissionSpec("workspace.performance_basic", "workspace", "실적", "개인 실적 도구", "컨벤션·썸머 등 개인 실적 도구", 70, True),
    PermissionSpec("workspace.performance_management", "workspace", "실적", "관리 실적·수수료", "매니저 업적 및 수수료 관리 도구", 80, False),

    PermissionSpec("calculator.insurance_basic", "calculator", "계산기", "보험 기본", "보험나이·상령일·총납입 등", 110, True),
    PermissionSpec("calculator.coverage_living", "calculator", "계산기", "보장·생활자금", "생활자금·치료비·보장 관련 계산", 120, True),
    PermissionSpec("calculator.pension_retirement", "calculator", "계산기", "연금·은퇴", "연금·퇴직·은퇴 관련 계산", 130, True),
    PermissionSpec("calculator.finance_investment", "calculator", "계산기", "재무·투자", "목표자금·복리·수익률 관련 계산", 140, True),
    PermissionSpec("calculator.personal_tax", "calculator", "계산기", "개인·부동산 세금", "소득세·양도세·부동산 세금 관련 계산", 150, True),
    PermissionSpec("calculator.inheritance_succession", "calculator", "계산기", "상속·증여·승계", "상속·증여·가업승계 관련 계산", 160, True),
    PermissionSpec("calculator.corporate_strategy", "calculator", "계산기", "법인·대표 전략", "대표자 의사결정 및 법인 전략 계산", 170, True),
    PermissionSpec("calculator.corporate_practice", "calculator", "계산기", "사업·법인 실무", "세무·노무·법인 실무 계산", 180, True),

    PermissionSpec("academy.simulator", "academy", "교육", "AI 상담 시뮬레이터", "AI 상담 시뮬레이터 이용", 210, True),
    PermissionSpec("academy.new_hire", "academy", "교육", "신입교육", "30·60·90일 신입교육 과정", 220, True),
    PermissionSpec("academy.consultation", "academy", "교육", "상담교육", "TA·1차·2차 상담교육", 230, True),
    PermissionSpec("academy.insurance_practice", "academy", "교육", "보험실무", "보장분석·계약·청구 실무교육", 240, True),
    PermissionSpec("academy.assessment", "academy", "교육", "시험·평가", "지식 및 상담 역량 평가", 250, True),
    PermissionSpec("academy.library", "academy", "교육", "교육자료실", "교육자료실 이용", 260, True),
    PermissionSpec("academy.my_learning", "academy", "교육", "나의학습", "개인 학습·평가·성장 기록", 270, True),
)

PERMISSION_BY_CODE: Final = {item.code: item for item in PERMISSIONS}

WORKSPACE_APP_PERMISSION: Final[dict[str, str]] = {
    "briefing": "workspace.briefing",
    "consultation_helper": "workspace.consultation",
    "deposit_vs_shortpay": "workspace.comparison_tools",
    "renewal_vs_nonrenewal": "workspace.comparison_tools",
    "inheritance_tax": "workspace.comparison_tools",
    "analyzer": "workspace.coverage_analysis",
    "remodeling": "workspace.remodeling",
    "silson_generation_comparison": "workspace.coverage_analysis",
    "comparison_builder": "workspace.customer_materials",
    "insurance_claim_guide": "workspace.customer_materials",
    "insurer_portal": "workspace.official_resources",
    "convention": "workspace.performance_basic",
    "summer": "workspace.performance_basic",
    "manager_results": "workspace.performance_management",
    "commission_calculator": "workspace.performance_management",
}

CALCULATOR_GROUP_PERMISSION: Final[dict[str, str]] = {
    "보험 기본": "calculator.insurance_basic",
    "보장·생활자금": "calculator.coverage_living",
    "연금·은퇴": "calculator.pension_retirement",
    "재무·투자": "calculator.finance_investment",
    "개인·부동산 세금": "calculator.personal_tax",
    "상속·증여·승계": "calculator.inheritance_succession",
    "법인·대표 전략": "calculator.corporate_strategy",
    "사업·법인 실무": "calculator.corporate_practice",
}

ACADEMY_MODULE_PERMISSION: Final[dict[str, str]] = {
    "simulator": "academy.simulator",
    "new_hire": "academy.new_hire",
    "consultation": "academy.consultation",
    "insurance_practice": "academy.insurance_practice",
    "assessment": "academy.assessment",
    "library": "academy.library",
    "my_learning": "academy.my_learning",
}


def default_granted_codes() -> set[str]:
    return {item.code for item in PERMISSIONS if item.default_granted}
