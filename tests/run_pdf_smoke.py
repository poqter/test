"""Generate representative Korean PDFs after removing the bundled font file."""
from __future__ import annotations

import io
import json
import sys
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.streamlit_stub import install
install()


def _validate(name: str, payload: bytes) -> dict:
    if not isinstance(payload, (bytes, bytearray)) or not payload.startswith(b"%PDF"):
        raise AssertionError(f"{name}: PDF signature missing")
    reader = PdfReader(io.BytesIO(payload))
    if not reader.pages:
        raise AssertionError(f"{name}: no pages")
    return {"name": name, "bytes": len(payload), "pages": len(reader.pages), "status": "PASS"}


def run() -> dict:
    rows: list[dict] = []

    from modules.calculators.finance.finance_models import FinanceResult
    from modules.calculators.result_pdf import build_result_pdf
    result = FinanceResult(
        {"예상 결과": Decimal("12345678"), "비율": Decimal("12.3")},
        "예상 결과 = 입력금액 × 적용계수",
        ["상담용 가정입니다.", "세금과 수수료는 별도 확인합니다."],
        units={"비율": "%"},
    )
    rows.append(_validate("calculator_result_pdf", build_result_pdf(
        "연금계산기", [("월 저축액 (원)", 500_000)], result, "2026-09-30 23:00"
    )))

    from modules.shared.workspace_tools import pdf_bytes
    rows.append(_validate("workspace_table_pdf", pdf_bytes(
        "화랑 WORKSPACE 테스트", ["항목", "내용"], [["한글 출력", "정상"], ["금액", "1,000만원"]], "상담 참고용"
    )))

    from modules.consultation.question_pdf import build_question_pdf
    question_pdf, page_count = build_question_pdf(
        "고객 상담 질문지",
        [{"id": "Q01", "text": "현재 가장 우선하여 점검하고 싶은 보장은 무엇인가요?"}],
        customer="테스트 고객",
        consultation_date="2026-09-30",
    )
    question_row = _validate("question_pdf", question_pdf)
    question_row["reported_pages"] = page_count
    rows.append(question_row)

    from modules.consultation.consultation_documents import document_pdf
    rows.append(_validate("consultation_document_pdf", document_pdf(
        "상담 요약", "상담 목적\n보장 점검\n\n다음 행동\n가입 조건 확인", prepared_on="2026-09-30", customer_label="테스트"
    )))

    from modules.consultation.enrollment_comparison import build_pdf as build_enrollment_pdf, example_model
    rows.append(_validate("enrollment_comparison_pdf", build_enrollment_pdf(example_model())))

    from modules.consultation.insurance_claim_guide import DocumentRule, build_guide_pdf
    docs = [
        DocumentRule("진료비 영수증", "환자명·진료일·금액", "병원 발급"),
        DocumentRule("신분증 사본", "청구인 기준", "직접 준비"),
    ]
    rows.append(_validate("claim_guide_pdf", build_guide_pdf(["실손 통원"], docs)))

    from modules.calculators.comparison.silson_generation_comparison import build_pdf as build_silson_pdf
    silson_data = {
        "customer": "테스트 고객", "consultant": "박병선", "generation": "4세대",
        "current_rates": {"급여": 20.0, "중증 비급여": 30.0, "비중증 비급여": 30.0},
        "current_premium": 30_000, "fifth_premium": 24_000, "premium_diff": 6_000,
        "current_payout": 1_500_000, "fifth_payout": 1_400_000,
        "current_burden": 500_000, "fifth_burden": 600_000, "burden_diff": 100_000,
        "total_medical": 2_300_000, "excluded": 300_000,
        "premium_basis": "테스트 직접 입력", "current_premium_basis": "테스트 직접 입력",
    }
    rows.append(_validate("silson_comparison_pdf", build_silson_pdf(silson_data)))

    from modules.calculators.tax import estate_calculator, estate_reports
    estate_values = [field[1] for field in estate_calculator.FIELDS[estate_calculator.NAME]]
    estate_result = estate_calculator.calculate(estate_calculator.NAME, estate_values)
    rows.append(_validate("estate_summary_pdf", estate_reports.pdf_report(
        estate_result,
        [("상속개시일", str(estate_values[0])), ("배우자 생존", str(estate_values[14]))],
        (50_000_000, 100_000_000, 0),
        "2026-09-30",
        alias="테스트 고객",
        note="상속세와 실제 납부재원은 별도로 점검합니다.",
    )))

    passed = sum(row["status"] == "PASS" for row in rows)
    return {"count": len(rows), "passed": passed, "failed": len(rows) - passed, "results": rows}


if __name__ == "__main__":
    report = run()
    import os
    output = Path(os.environ.get("HW_TEST_OUTPUT_DIR", str(ROOT / "artifacts" / "validation"))) / "pdf_smoke_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("count", "passed", "failed")}, ensure_ascii=False, indent=2))
    for row in report["results"]:
        print(row)
    raise SystemExit(0 if report["failed"] == 0 else 1)
