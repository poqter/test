"""Metadata-driven calculator input presentation.

The profiles are generated from the 80-calculator usability review. Calculation
engines and positional input contracts stay unchanged; this module only decides
presentation order, grouping, short guidance, and conditionally visible fields.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Mapping

from modules.shared.paths import PROJECT_ROOT


@lru_cache(maxsize=1)
def profiles() -> dict[str, dict[str, str]]:
    path = PROJECT_ROOT / "data" / "calculator_ux_profiles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def profile(name: str) -> dict[str, str]:
    return profiles().get(name, {"priority": "유지", "core": "핵심 조건", "improvements": "현재의 간결한 입력 구조를 유지합니다.", "section": ""})


def _norm(value: Any) -> str:
    text = str(value or "").lower()
    replacements = {
        "상속일": "상속개시일", "증여 관계": "받는 사람 관계", "재산 종류": "재산",
        "취득·양도": "취득 양도", "월세 수입": "월세", "개업일": "사업개시일",
        "매출": "수입금액", "직원 수": "근로자 수", "생활비": "생활비",
        "보유자금": "자산", "기존 보장": "기존 보장액", "보험료": "보험료",
        "연금액": "연금", "주식수": "발행주식수", "실효세율": "세율",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def _core_terms(name: str) -> list[str]:
    text = profile(name).get("core", "")
    # Preserve compound phrases first, then allow their meaningful words to match.
    terms = [part.strip() for part in re.split(r"[,;/]|\s+또는\s+|\s+및\s+", text) if part.strip()]
    return terms


def core_rank(name: str, label: str) -> tuple[int, int]:
    """Return (match group, profile order). Lower values appear first."""
    normalized_label = _norm(label)
    best: tuple[int, int] | None = None
    for order, term in enumerate(_core_terms(name)):
        normalized_term = _norm(term)
        if normalized_term and (normalized_term in normalized_label or normalized_label in normalized_term):
            candidate = (0, order)
        else:
            words = [w for w in re.split(r"[·\s/]+", term) if len(_norm(w)) >= 2]
            hits = sum(1 for word in words if _norm(word) in normalized_label)
            candidate = (1, order) if hits >= max(1, len(words) // 2) else None
        if candidate is not None and (best is None or candidate < best):
            best = candidate
    return best if best is not None else (9, 999)


ASSUMPTION_WORDS = (
    "수익률", "물가", "할인율", "증가율", "운용률", "적용률", "보정", "프리미엄",
    "가정", "복리", "납입 시점", "인출 시점", "예상 실효세율", "본인부담 비율",
)
CONFIRMATION_WORDS = (
    "확인", "요건", "자격", "미확인", "적격", "법정", "신고의무", "부과 대상",
    "적용 대상", "해당 여부", "중과 적용 판단", "신고 상태",
)
ADDITIONAL_WORDS = (
    "과거", "이전", "추가", "기타", "예외", "특례", "합산", "조정", "세대생략",
    "공제", "기납부", "이월", "할증", "손실", "원천징수", "필요경비", "비과세",
)


def field_bucket(name: str, label: str, unit: str) -> str:
    if core_rank(name, label)[0] < 9:
        return "core"
    if any(word in label for word in ASSUMPTION_WORDS) or unit == "%":
        return "assumption"
    if any(word in label for word in CONFIRMATION_WORDS):
        return "confirmation"
    if any(word in label for word in ADDITIONAL_WORDS):
        return "additional"
    return "additional"


def ordered_indices(name: str, entries: list[tuple]) -> list[int]:
    bucket_order = {"core": 0, "additional": 1, "assumption": 2, "confirmation": 3}
    return sorted(
        range(len(entries)),
        key=lambda i: (
            bucket_order[field_bucket(name, str(entries[i][0]), str(entries[i][2]))],
            core_rank(name, str(entries[i][0]))[1],
            i,
        ),
    )


def field_help(label: str, unit: str) -> str | None:
    if "미확인" in label or "확인액" in label or any(word in label for word in ("확정", "실제 세액", "기납부")):
        return "신고서·원천징수영수증·결산자료 등에서 확인한 값을 입력하세요. 확인하지 못한 값과 0원은 구분합니다."
    if unit == "%" and any(word in label for word in ("수익률", "물가", "증가율", "할인율", "세율")):
        return "결과에 적용되는 가정입니다. 실제 계약·시장·세법 적용값과 다를 수 있습니다."
    return None


def _value(state: Mapping[str, Any], label: str, default: Any = None) -> Any:
    return state.get(label, default)


def field_visible(name: str, label: str, state: Mapping[str, Any]) -> bool:
    """Return whether a dependent field should be shown for the selected branch."""
    if name == "차등배당계산기":
        stage = str(_value(state, "계산 단계", ""))
        method = str(_value(state, "정산 소득세액 계산 방식", ""))
        grossup = str(_value(state, "종합과세 계산 방식", ""))
        if label.startswith("정산용") or label.startswith("최초 신고 증여세액") or label.startswith("정산 소득세액"):
            return stage.startswith("정산")
        if label.startswith("초과배당 발생연도"):
            return stage.startswith("정산") and method.startswith("종합과세")
        if label.startswith("초과배당에 적용되는 분리과세"):
            return stage.startswith("정산") and method.startswith("적격 분리과세")
        if label.startswith("이 거래로 증가하는"):
            return "확인된 추가" in grossup
    elif name == "특정법인 증여의제계산기":
        system = str(_value(state, "적용 제도", ""))
        is_45_5 = "45조의5" in system
        if label.startswith("45조의5"):
            return is_45_5
        if label != "적용 제도" and not label.startswith("45조의5"):
            return not is_45_5
    elif name == "법인보험 만기계산기":
        action = str(_value(state, "처리 유형", ""))
        cause = str(_value(state, "계약 이전 원인", ""))
        transfer = "계약자 변경" in action
        transfer_labels = {
            "계약 이전 원인", "대표가 법인에 실제 지급하는 대가", "해당 이전의 법인 손금 인정 보수액 (확인액)",
            "이번 보험 외 동일 퇴직의 과세 퇴직급여", "개인 소득세법상 전체 임원퇴직소득 한도 (2011년 이전 인정분 포함)",
            "세법상 합산 근속연수 (1년 미만 올림)", "보험 이전 제외 연간 과세 총급여", "공통 근로소득공제 외 소득공제",
            "보험 평가액·퇴직 사실·보수 손금·개인 한도 확인",
        }
        if label in transfer_labels and not transfer:
            return False
        if transfer and label == "실제 원천징수된 국세·지방세 합계":
            return False
        if label == "대표가 법인에 실제 지급하는 대가":
            return "유상 양도" in cause
        if label in {"이번 보험 외 동일 퇴직의 과세 퇴직급여", "개인 소득세법상 전체 임원퇴직소득 한도 (2011년 이전 인정분 포함)", "세법상 합산 근속연수 (1년 미만 올림)"}:
            return "퇴직" in cause
        if label in {"보험 이전 제외 연간 과세 총급여", "공통 근로소득공제 외 소득공제"}:
            return "근로소득" in cause
    elif name == "업무용승용차 비용계산기":
        mode = str(_value(state, "보유 형태", "구입"))
        log = str(_value(state, "운행기록부 작성", "아니요"))
        repair_known = str(_value(state, "리스 수선비 구분 가능", "아니요"))
        if label in {"구입 차량 세무상 취득가액", "당기 이전 누적 상각액 (구입)"}:
            return mode == "구입"
        if label in {"당기 리스·렌트료", "리스료에 포함된 보험료·자동차세", "리스 수선비 구분 가능", "리스료에 포함된 실제 수선비"}:
            if mode == "구입":
                return False
            if label in {"리스료에 포함된 보험료·자동차세", "리스 수선비 구분 가능", "리스료에 포함된 실제 수선비"} and mode != "리스":
                return False
            if label == "리스료에 포함된 실제 수선비":
                return repair_known == "예"
        if label == "기록부상 업무사용 비율":
            return log == "예"
    elif name == "DC부담금 한도계산기":
        employee_mode = str(_value(state, "직원 계산 방식", ""))
        executive = str(_value(state, "임원 상태", ""))
        if label == "직원 실제 납입액":
            return "실제 납입액" in employee_mode
        if label == "임원 당기 실제 부담금":
            return executive != "임원 없음"
        if label in {"퇴직 임원 과거 누적 부담금", "퇴직 임원 법인세법상 한도 확인액", "퇴직 임원 한도·누적액 확인"}:
            return executive == "임원 당기 퇴직"
    elif name == "직무발명보상금계산기":
        income_type = str(_value(state, "소득 구분", ""))
        retired = "퇴직 후" in income_type
        retired_fields = {
            "퇴직 후 보상금에 대응하는 확인된 실제 필요경비", "같은 해 먼저 적용한 기타소득 직무발명 비과세액",
            "퇴직 후 기타소득 과세 방식", "근로소득 외 기존 종합소득금액", "다른 선택적 분리과세 기타소득금액 (한도 판정용)",
        }
        employee_fields = {"이번 보상금 제외 연간 과세 총급여", "같은 해 먼저 적용한 근로소득 직무발명 비과세액", "공통 소득공제 (근로소득공제 제외)"}
        if label in retired_fields:
            return retired
        if label in employee_fields:
            return not retired
    elif name == "법인 4대보험계산기":
        mode = str(_value(state, "입력 방식", ""))
        if label in {"월 보수 총액 (비과세 제외)", "직원 수"}:
            return "총급여" in mode
        if label.startswith("직원별 월 보수"):
            return "직원별" in mode
    elif name == "임대소득세계산기":
        house_count = _value(state, "간주임대료 주택 수 (소형주택 제외)", 0)
        if label in {"간주임대료 대상 주택의 보증금 합계", "보증금 유지 일수 (연중 동일 금액)", "보증금 운용 관련 확인된 금융수익"}:
            try:
                return float(house_count or 0) > 0
            except (TypeError, ValueError):
                return False
    elif name == "해외금융계좌 신고계산기":
        status = str(_value(state, "신고 상태", ""))
        if label.startswith("미신고·과소신고 금액") or label == "과태료 계산 사유":
            return status != "기한 내 정상신고"
    return True


def active_condition_summary(name: str, state: Mapping[str, Any]) -> list[str]:
    summary: list[str] = []
    for label, value in state.items():
        text = str(value)
        if any(word in label for word in ("방식", "유형", "구분", "상태", "단계", "종류")) and text:
            summary.append(f"{label}: {text}")
        elif text in {"예", "확인", "해당", "적용"}:
            summary.append(label)
    return summary[:6]
