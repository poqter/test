"""Remodeling workbook generation and display formatting.

Extracted from the existing implementation; public facade names are preserved.
"""
from __future__ import annotations
from modules.shared.runtime_cache import session_export
from datetime import date
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from modules.consultation.remodeling_model import (
    NAVY,
    NAVY2,
    GOLD_LIGHT,
    BLUE_LIGHT,
    GREEN_LIGHT,
    SOFT,
    WHITE,
    INK,
    MUTED,
    GREEN,
    RED,
    THIN,
    ACTION_STYLE,
    NewPlan,
    ExistingContract,
    Person,
    won,
    change_amount,
    change_rate,
    combined,
)

def _border() -> Border:
    return Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def _merge(ws, address: str, value: object, *, fill: str | None = None, color: str = INK,
           size: float = 10, bold: bool = False, border: bool = True) -> None:
    ws.merge_cells(address)
    cell = ws[address.split(":")[0]]
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"
    cell.font = Font(name="맑은 고딕", size=size, bold=bold, color=color)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True, shrink_to_fit=True)
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    if border:
        for row in ws[address]:
            for item in row:
                item.border = _border()

def _excel_setup(ws, last_col: str, last_row: int) -> None:
    ws.sheet_view.showGridLines = False
    # 파일을 처음 열었을 때 비교표가 조금 더 크게 보이도록 설정합니다.
    # 화면 확대 비율은 인쇄 배율에는 영향을 주지 않습니다.
    ws.sheet_view.zoomScale = 110
    ws.sheet_view.zoomScaleNormal = 110
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=.25, right=.25, top=.30, bottom=.30, header=.1, footer=.1)
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = True
    ws.print_area = f"A1:{last_col}{last_row}"
    ws.oddHeader.right.text = "&K1769DC&BH  |  화랑 WORKSPACE"
    ws.oddHeader.right.size = 9
    ws.oddHeader.right.font = "Pretendard,Bold"

def _excel_top(ws, people: list[Person], title: str) -> None:
    totals = combined(people)
    _merge(ws, "A1:R2", title, color=NAVY, size=19, bold=True, border=False)
    subtitle = "보험료 부담과 필요한 보장을 함께 비교해 오래 유지하기 쉬운 구조로 재구성했습니다."
    _merge(ws, "A3:R3", subtitle, color=MUTED, size=10, bold=True, border=False)
    labels = (["월 보험료 변화", "변경 후 월 보험료", "납입 예정 총액 변화"] if len(people) == 1 else
              ["합산 월 보험료 변화", "변경 후 합산 월 보험료", "납입 예정 총액 변화"])
    for address, label in zip(("A5:F5", "G5:L5", "M5:R5"), labels):
        _merge(ws, address, label, fill=NAVY2, color=WHITE, size=9, bold=True)
    _merge(ws, "A6:D6", change_amount(totals["old_monthly"], totals["after_monthly"]), fill=GOLD_LIGHT, color=NAVY, size=11, bold=True)
    _merge(ws, "E6:F6", change_rate(totals["old_monthly"], totals["after_monthly"]), fill=GOLD_LIGHT, color=RED, size=11, bold=True)
    _merge(ws, "G6:L6", won(totals["after_monthly"]), fill=GOLD_LIGHT, color=NAVY, size=11, bold=True)
    _merge(ws, "M6:P6", change_amount(totals["old_total"], totals["after_total"]), fill=GOLD_LIGHT, color=NAVY, size=11, bold=True)
    _merge(ws, "Q6:R6", change_rate(totals["old_total"], totals["after_total"]), fill=GOLD_LIGHT, color=RED, size=11, bold=True)

def _excel_person_panel(ws, p: Person, left: int, right: int, top: int, max_plans: int) -> int:
    L, R = get_column_letter(left), get_column_letter(right)
    _merge(ws, f"{L}{top}:{R}{top+1}", f"{p.name or 'OOO'}님", fill=NAVY, color=WHITE, size=13, bold=True)
    mid = (left + right) // 2
    spans = [(left, left+1), (left+2, mid), (mid+1, mid+2), (mid+3, right)]
    rows = [
        ("기존 월 보험료", won(p.old_monthly), "리모델링 후", won(p.after_monthly)),
        ("기존 납입 예정 총액", won(p.old_total), "변경 납입 예정 총액", won(p.after_total)),
    ]
    for rr, values in enumerate(rows, top+2):
        for idx, ((a, b), value) in enumerate(zip(spans, values)):
            _merge(ws, f"{get_column_letter(a)}{rr}:{get_column_letter(b)}{rr}", value,
                   fill=BLUE_LIGHT if idx % 2 == 0 else WHITE, color=NAVY2 if idx == 3 else INK,
                   size=7.5 if idx % 2 == 0 else 9.5, bold=True)
    row = top + 5
    _merge(ws, f"{L}{row}:{R}{row}", "새롭게 가입하는 보험", fill=NAVY2, color=WHITE, bold=True)
    text_end = right - 2
    _merge(ws, f"{L}{row+1}:{get_column_letter(text_end)}{row+1}", "보험 또는 보장 구성", fill=NAVY2, color=WHITE, size=8, bold=True)
    _merge(ws, f"{get_column_letter(text_end+1)}{row+1}:{R}{row+1}", "월 보험료", fill=NAVY2, color=WHITE, size=8, bold=True)
    shown = p.plans[:max_plans]
    for idx in range(max_plans):
        plan = shown[idx] if idx < len(shown) else NewPlan()
        rr = row + 2 + idx
        _merge(ws, f"{L}{rr}:{get_column_letter(text_end)}{rr}", plan.name, fill=SOFT, size=8, bold=bool(plan.name))
        _merge(ws, f"{get_column_letter(text_end+1)}{rr}:{R}{rr}", won(plan.monthly) if plan.name else "", fill=WHITE, size=8, bold=bool(plan.name))
    total_row = row + 2 + max_plans
    _merge(ws, f"{L}{total_row}:{get_column_letter(text_end)}{total_row}", "신규 보험료 합계", fill=GREEN_LIGHT, color=NAVY, bold=True)
    _merge(ws, f"{get_column_letter(text_end+1)}{total_row}:{R}{total_row}", won(p.new_plan_monthly), fill=GREEN_LIGHT, color=GREEN, bold=True)
    coverage_row = total_row + 2
    _merge(ws, f"{L}{coverage_row}:{R}{coverage_row}", "새롭게 확보되는 핵심 보장", fill=NAVY, color=WHITE, bold=True)
    _merge(ws, f"{L}{coverage_row+1}:{R}{coverage_row+2}", p.coverage, fill=GREEN_LIGHT, color=NAVY, size=8.5, bold=True)
    return coverage_row + 2

def _excel_new_panel(ws, p: Person, left: int, right: int, top: int, max_plans: int) -> int:
    L, R = get_column_letter(left), get_column_letter(right)
    _merge(ws, f"{L}{top}:{R}{top}", "새롭게 가입하는 보험", fill=NAVY, color=WHITE, bold=True)
    text_end = right - 2
    _merge(ws, f"{L}{top+1}:{get_column_letter(text_end)}{top+1}", "보험 또는 보장 구성", fill=NAVY2, color=WHITE, size=8, bold=True)
    _merge(ws, f"{get_column_letter(text_end+1)}{top+1}:{R}{top+1}", "월 보험료", fill=NAVY2, color=WHITE, size=8, bold=True)
    for idx in range(max_plans):
        plan = p.plans[idx] if idx < len(p.plans) else NewPlan()
        rr = top + 2 + idx
        _merge(ws, f"{L}{rr}:{get_column_letter(text_end)}{rr}", plan.name, fill=SOFT, size=8, bold=bool(plan.name))
        _merge(ws, f"{get_column_letter(text_end+1)}{rr}:{R}{rr}", won(plan.monthly) if plan.name else "", fill=WHITE, size=8, bold=bool(plan.name))
    total_row = top + 2 + max_plans
    _merge(ws, f"{L}{total_row}:{get_column_letter(text_end)}{total_row}", "신규 보험료 합계", fill=GREEN_LIGHT, color=NAVY, bold=True)
    _merge(ws, f"{get_column_letter(text_end+1)}{total_row}:{R}{total_row}", won(p.new_plan_monthly), fill=GREEN_LIGHT, color=GREEN, bold=True)
    coverage_row = total_row + 2
    _merge(ws, f"{L}{coverage_row}:{R}{coverage_row}", "새롭게 확보되는 핵심 보장", fill=NAVY, color=WHITE, bold=True)
    _merge(ws, f"{L}{coverage_row+1}:{R}{coverage_row+2}", p.coverage, fill=GREEN_LIGHT, color=NAVY, size=8.5, bold=True)
    return coverage_row + 2

def _excel_bottom(ws, people: list[Person], top: int) -> int:
    t = combined(people)
    spans = [("A", "C"), ("D", "H"), ("I", "M"), ("N", "R")]
    headers = ["한눈에 보는 비교" if len(people) == 1 else "2인 합산 비교", "기존", "리모델링 후", "변화"]
    for span, value in zip(spans, headers):
        _merge(ws, f"{span[0]}{top}:{span[1]}{top}", value, fill=NAVY, color=WHITE, bold=True)
    records = [
        ("월 보험료", t["old_monthly"], t["after_monthly"]),
        ("연간 보험료", t["old_monthly"]*12, t["after_monthly"]*12),
        ("납입 예정 총액", t["old_total"], t["after_total"]),
    ]
    for rr, (label, old, new) in enumerate(records, top+1):
        _merge(ws, f"A{rr}:C{rr}", label, fill=BLUE_LIGHT, bold=True)
        _merge(ws, f"D{rr}:H{rr}", won(old), fill=WHITE)
        _merge(ws, f"I{rr}:M{rr}", won(new), fill=WHITE)
        _merge(ws, f"N{rr}:P{rr}", change_amount(old, new), fill=GOLD_LIGHT, color=GREEN if old > new else INK, bold=True)
        _merge(ws, f"Q{rr}:R{rr}", change_rate(old, new), fill=GOLD_LIGHT, color=RED, bold=True)
    return top + 3

def _excel_detail(wb: Workbook, people: list[Person]) -> None:
    ws = wb.create_sheet("기존 계약 변경")
    ws.sheet_view.showGridLines = False
    for col, width in zip("ABCDEF", [16, 24, 18, 44, 16, 16]):
        ws.column_dimensions[col].width = width
    _merge(ws, "A1:F2", "기존 계약별 처리 계획", color=NAVY, size=18, bold=True, border=False)
    row = 4
    for p in people:
        _merge(ws, f"A{row}:F{row}", f"{p.name or 'OOO'}님", fill=NAVY, color=WHITE, bold=True)
        row += 1
        for col, text in enumerate(["보험회사", "상품명", "처리 방향", "구체적인 변경 내용"], 1):
            end = col if col < 4 else 6
            _merge(ws, f"{get_column_letter(col)}{row}:{get_column_letter(end)}{row}", text, fill=NAVY2, color=WHITE, bold=True)
            if col == 4:
                break
        row += 1
        records = p.contracts or [ExistingContract(detail="입력된 기존 계약 변경 내용이 없습니다.")]
        for c in records:
            action_fill, action_color = ACTION_STYLE.get(c.action, (WHITE, INK))
            _merge(ws, f"A{row}:A{row}", c.company, fill=WHITE)
            _merge(ws, f"B{row}:B{row}", c.product, fill=WHITE)
            _merge(ws, f"C{row}:C{row}", c.action if c.company or c.product else "", fill=action_fill, color=action_color, bold=True)
            _merge(ws, f"D{row}:F{row}", c.detail, fill=WHITE)
            ws.row_dimensions[row].height = 30
            row += 1
        row += 1
    _merge(ws, f"A{row}:F{row}", "※ 감액·해지는 신규 계약의 승인과 보장 개시를 확인한 후 진행합니다.", fill=GOLD_LIGHT, color=MUTED, size=9)
    _excel_setup(ws, "F", row)

@session_export("remodeling-excel-v3", name_arg=False)
def _create_excel_bytes(people: list[Person], title: str, consultation_date: date, consultant: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "리모델링 비교안"
    widths = [8,8,8,8,8,8,10,10,4,4,10,10,8,8,8,8,8,8]
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    _excel_top(ws, people, title)
    if len(people) == 1:
        p = people[0]
        _excel_new_panel(ws, p, 11, 18, 8, 5)
        _merge(ws, "A8:H8", "보험료 비교", fill=NAVY, color=WHITE, bold=True)
        left_rows = [("기존 월 보험료", p.old_monthly), ("유지 보험료", p.retained_monthly), ("신규 보험료", p.new_plan_monthly), ("리모델링 후", p.after_monthly)]
        for rr, (label, value) in enumerate(left_rows, 9):
            _merge(ws, f"A{rr}:D{rr}", label, fill=BLUE_LIGHT, bold=True)
            _merge(ws, f"E{rr}:H{rr}", won(value), fill=GOLD_LIGHT if rr == 12 else WHITE, color=NAVY2, bold=True)
        _merge(ws, "A14:H14", "납입 예정 총액", fill=NAVY, color=WHITE, bold=True)
        for rr, (label, value) in enumerate([("기존", p.old_total), ("리모델링 후", p.after_total), ("변화", abs(p.total_change))], 15):
            _merge(ws, f"A{rr}:D{rr}", label, fill=BLUE_LIGHT, bold=True)
            _merge(ws, f"E{rr}:H{rr}", won(value), fill=GOLD_LIGHT if rr == 17 else WHITE, color=GREEN if rr == 17 and p.total_change < 0 else INK, bold=True)
        bottom = _excel_bottom(ws, people, 21)
        last = 27
    else:
        _excel_person_panel(ws, people[0], 1, 8, 8, 4)
        _excel_person_panel(ws, people[1], 11, 18, 8, 4)
        bottom = _excel_bottom(ws, people, 25)
        last = 31
    note = "※ 신규 보험의 납입 예정 총액은 입력한 현재 월 보험료와 납입기간을 기준으로 계산했습니다."
    _merge(ws, f"A{last-1}:R{last-1}", note, color=MUTED, size=8, border=False)
    _merge(ws, f"A{last}:R{last}", f"상담일 {consultation_date:%Y.%m.%d} · 담당자 {consultant or '-'}", color=MUTED, size=8, border=False)
    _excel_setup(ws, "R", last)
    _excel_detail(wb, people)
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()

def create_excel(people: list[Person], title: str, consultation_date: date, consultant: str) -> BytesIO:
    return BytesIO(_create_excel_bytes(people, title, consultation_date, consultant))

def _editor_excel(people, title, consultation_date, consultant, include_detail):
    """Presentation changes only, based on the original workbook generator."""
    wb = load_workbook(create_excel(people, title, consultation_date, consultant))
    ws = wb["리모델링 비교안"]
    ws["A3"] = "기존 계약과 변경안을 같은 기준으로 비교한 상담 자료입니다."
    totals = combined(people)
    # Keep before/after values visible; highlight reductions only.
    for label_cell, amount_cell, rate_cell, old_key, new_key in [
        ("A5", "A6", "E6", "old_monthly", "after_monthly"),
        ("M5", "M6", "Q6", "old_total", "after_total")]:
        if totals[old_key] <= totals[new_key]:
            ws[label_cell] = "변경 후 월 보험료" if old_key == "old_monthly" else "변경 후 납입 예정 총액"
            ws[amount_cell] = won(totals[new_key])
            ws[rate_cell] = ""
    if len(people) == 1:
        p = people[0]
        ws["A17"] = "감소액" if p.total_change < 0 else ""
        ws["E17"] = won(-p.total_change) if p.total_change < 0 else ""
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str):
                if cell.value.endswith("원 증가"):
                    cell.value = "—"
                if cell.value == "새롭게 확보되는 핵심 보장":
                    cell.value = "신규 가입안의 핵심 보장"
    # Display existing payment terms without changing any amount calculation.
    for person_index, person in enumerate(people):
        start_col = 11 if len(people) == 1 or person_index == 1 else 1
        start_row = 10 if len(people) == 1 else 15
        limit = 5 if len(people) == 1 else 4
        for i, plan in enumerate(person.plans[:limit]):
            cell = ws.cell(start_row + i, start_col)
            cell.value = f"{plan.name} · {plan.months}개월납"
    if not include_detail:
        del wb["기존 계약 변경"]
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output, wb
