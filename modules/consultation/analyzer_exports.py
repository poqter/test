"""Coverage analysis workbook generation; UI independent.

Extracted from the existing implementation; public facade names are preserved.
"""
from modules.shared.runtime_cache import session_export
import base64
import re
from copy import copy
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from modules.consultation.analyzer_model import (
    DEFAULT_COVERAGES,
    COLORS,
    LOGO_BASE64,
    MEDIUM_SIDE,
    THICK_SIDE,
    THIN_BORDER,
    _normalize_label,
    _to_number,
    _is_fully_paid,
    _format_won_text,
    parse_source_file,
)

def _set_outline(ws, min_row: int, max_row: int, min_col: int, max_col: int, side: Side) -> None:
    def replace_side(cell, **changes) -> None:
        border = cell.border
        cell.border = Border(
            left=changes.get("left", copy(border.left)),
            right=changes.get("right", copy(border.right)),
            top=changes.get("top", copy(border.top)),
            bottom=changes.get("bottom", copy(border.bottom)),
            diagonal=copy(border.diagonal),
            diagonal_direction=border.diagonal_direction,
            diagonalUp=border.diagonalUp,
            diagonalDown=border.diagonalDown,
            outline=border.outline,
            vertical=copy(border.vertical),
            horizontal=copy(border.horizontal),
        )

    for col in range(min_col, max_col + 1):
        top_cell = ws.cell(min_row, col)
        bottom_cell = ws.cell(max_row, col)
        replace_side(top_cell, top=side)
        replace_side(bottom_cell, bottom=side)
    for row in range(min_row, max_row + 1):
        left_cell = ws.cell(row, min_col)
        right_cell = ws.cell(row, max_col)
        replace_side(left_cell, left=side)
        replace_side(right_cell, right=side)

def _set_vertical_borders(
    ws,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    side: Side,
) -> None:
    """표 안의 모든 열 경계만 지정한 굵기로 통일합니다."""

    def replace_side(cell, **changes) -> None:
        border = cell.border
        cell.border = Border(
            left=changes.get("left", copy(border.left)),
            right=changes.get("right", copy(border.right)),
            top=copy(border.top),
            bottom=copy(border.bottom),
            diagonal=copy(border.diagonal),
            diagonal_direction=border.diagonal_direction,
            diagonalUp=border.diagonalUp,
            diagonalDown=border.diagonalDown,
            outline=border.outline,
            vertical=copy(border.vertical),
            horizontal=copy(border.horizontal),
        )

    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col):
            replace_side(ws.cell(row, col), right=side)
            replace_side(ws.cell(row, col + 1), left=side)

def _extract_logo() -> bytes:
    """외부 파일 없이 코드에 내장된 Hanwha Life Lab 로고를 반환합니다."""
    return base64.b64decode(LOGO_BASE64)

def _configure_print(
    ws,
    contract_count: int,
    coverage_count: int,
    last_row: int,
    last_col: int,
    page_count: int = 1,
) -> None:
    # 다운로드 직후 바로 인쇄할 수 있도록 A3 세로형에서
    # 너비와 높이를 모두 1페이지에 맞춥니다.
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.orientation = "portrait"
    ws.page_setup.pageOrder = "overThenDown"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_properties.pageSetUpPr.autoPageBreaks = False
    ws.page_setup.scale = None
    ws.print_area = f"A1:{get_column_letter(last_col)}{last_row}"
    # A~C열은 반복 인쇄하지 않습니다.
    ws.print_title_cols = None
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = True
    ws.oddFooter.center.text = "페이지 &P / &N"
    ws.oddFooter.center.size = 9
    # 좌우·위쪽은 인쇄 공간을 넓게 쓰고, 아래쪽은 표와 페이지 번호가
    # 겹치지 않도록 여유를 둡니다. 바닥글은 일반 프린터의 비인쇄 영역을
    # 고려해 용지 아래에서 0.20인치 위치에 배치합니다.
    ws.page_margins.left = 0.12
    ws.page_margins.right = 0.12
    ws.page_margins.top = 0.12
    ws.page_margins.bottom = 0.38
    ws.page_margins.header = 0
    ws.page_margins.footer = 0.20
    ws.sheet_view.zoomScale = 100

def _contract_column_width(contract_count: int) -> float:
    """보험 수가 적당할 때 A3 가로폭을 넉넉히 쓰되 지나치게 넓어지지 않게 합니다."""
    widths = {1: 25.0, 2: 25.0, 3: 27.0, 4: 24.0, 5: 20.5, 6: 18.0}
    return widths.get(contract_count, max(14.0, 108.0 / max(contract_count, 1)))

def _populate_analysis_sheet(
    workbook: Workbook,
    title: str,
    data: dict,
    selected: list[dict],
    contract_indices: list[int],
    contracts_per_page: int | None = None,
    page_count: int = 1,
) -> None:
    ws = workbook.create_sheet(title)
    ws.sheet_view.showGridLines = False
    ws.oddHeader.right.text = "&K1769DC&BH  |  화랑 WORKSPACE"
    ws.oddHeader.right.size = 9
    ws.oddHeader.right.font = "Pretendard,Bold"
    contracts = [data["contracts"][index] for index in contract_indices]
    contract_count = len(contracts)
    last_col = 3 + contract_count
    coverage_start = 11

    output_items = [
        {"label": "일반사망", "display": "일반 사망", "group": "사망", "values": [0] * contract_count},
        *[
            {
                **item,
                "values": [item["values"][index] for index in contract_indices],
            }
            for item in selected
        ],
        {"label": "기타", "display": "기타", "group": "기타", "values": [0] * contract_count},
    ]
    coverage_end = coverage_start + len(output_items) - 1

    normal_font = Font(name="나눔고딕", size=10, color=COLORS["black"])
    bold_font = Font(name="나눔고딕", size=10, bold=True, color=COLORS["black"])
    blue_font = Font(name="나눔고딕", size=11, bold=True, color=COLORS["blue"])
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.merge_cells("A1:C1")
    age_text = f" (보험연령:{data['age']}세)" if data["age"] else ""
    title_customer_name = re.sub(r"님$", "", str(data["customer_name"] or "OOO").strip()) or "OOO"
    ws["A1"] = f"{title_customer_name}님의 보장 분석{age_text}"
    ws["A1"].font = Font(name="나눔고딕", size=14, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="bottom")
    ws.row_dimensions[1].height = 82
    for col in range(1, last_col + 1):
        ws.cell(1, col).fill = PatternFill("solid", fgColor=COLORS["white"])
        ws.cell(1, col).border = Border()
        ws.cell(1, col).alignment = center

    logo = XLImage(BytesIO(_extract_logo()))
    logo.width = 350
    logo.height = 43
    ws.add_image(logo, "A1")

    ws.merge_cells("A2:A3")
    ws.merge_cells("B2:B3")
    ws.merge_cells("C2:C3")
    ws["A2"] = "합 계"
    ws["B2"] = "구분"
    ws["C2"] = "보장명"
    ws["A2"].font = Font(name="나눔고딕", size=11, bold=True, color=COLORS["red"])

    for row in range(2, 4):
        for col in range(1, last_col + 1):
            cell = ws.cell(row, col)
            cell.fill = PatternFill("solid", fgColor=COLORS["header"])
            cell.border = THIN_BORDER
            cell.alignment = center
            if cell.coordinate != "A2":
                cell.font = bold_font

    for index, contract in enumerate(contracts, start=4):
        ws.cell(2, index, contract["company"]).data_type = "s"
        ws.cell(3, index, contract["product"]).data_type = "s"
        ws.cell(2, index).font = Font(name="나눔고딕", size=10, bold=True, color=COLORS["black"])
        ws.cell(3, index).font = Font(name="나눔고딕", size=9, bold=True)
    ws.row_dimensions[2].height = 25
    ws.row_dimensions[3].height = 55

    meta_rows = [
        (4, "보장기간", "coverage_period"),
        (5, "납입횟수", "payment_count"),
        (6, "납입주기", "payment_cycle"),
        (7, "월보험료", "monthly"),
        (8, "납입완료", "paid"),
        (9, "납입예정", "remaining"),
        (10, "총보험료", "total"),
    ]
    for row, label, key in meta_rows:
        if row <= 6:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
            ws.cell(row, 1, label)
        else:
            last_contract_col = get_column_letter(last_col)
            ws.cell(row, 1, f"=SUM(D{row}:{last_contract_col}{row})")
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
            ws.cell(row, 2, label)

        fill_color = COLORS["header"] if row == 7 or row <= 6 else COLORS["premium"]
        for col in range(1, last_col + 1):
            cell = ws.cell(row, col)
            cell.fill = PatternFill("solid", fgColor=fill_color if col == 1 or col >= 4 else COLORS["header"])
            cell.border = THIN_BORDER
            cell.alignment = center
            cell.font = bold_font

        for index, contract in enumerate(contracts, start=4):
            cell = ws.cell(row, index)
            if row == 7 and _to_number(contract["monthly"]) == 0:
                cell.value = "확인 필요"
                cell.font = normal_font
            elif row == 7 and _is_fully_paid(contract["payment_count"]):
                cell.value = _format_won_text(contract["monthly"])
                cell.font = blue_font
            else:
                cell.value = contract[key]
                if isinstance(cell.value, str):
                    cell.data_type = "s"
            if row >= 7:
                cell.number_format = '#,##0"원"'
                if not (row == 7 and _to_number(contract["monthly"]) == 0):
                    cell.font = blue_font
        if row >= 7:
            ws.cell(row, 1).number_format = '#,##0"원"'
            ws.cell(row, 1).font = blue_font

    # 완납 계약은 보험회사명부터 총보험료까지 해당 보험 열 전체를 녹색으로 표시합니다.
    for index, contract in enumerate(contracts, start=4):
        if _is_fully_paid(contract["payment_count"]):
            completed_fill = PatternFill("solid", fgColor=COLORS["completed"])
            for row in range(2, 11):
                ws.cell(row, index).fill = completed_fill

    group_ranges: list[tuple[int, int]] = []
    group_start = coverage_start
    current_group = output_items[0]["group"]
    for offset, item in enumerate(output_items):
        row = coverage_start + offset
        group = item["group"]
        if group != current_group:
            group_ranges.append((group_start, row - 1))
            group_start = row
            current_group = group

        section_color = COLORS["white"]
        if group == "암\n보장":
            section_color = COLORS["cancer"]
        elif group == "뇌\n보장":
            section_color = COLORS["brain"]
        elif group == "심장\n보장":
            section_color = COLORS["heart"]

        last_contract_col = get_column_letter(last_col)
        ws.cell(row, 1, f"=SUM(D{row}:{last_contract_col}{row})")
        ws.cell(row, 2, group)
        ws.cell(row, 3, item["display"]).data_type = "s"
        for index, value in enumerate(item["values"], start=4):
            ws.cell(row, index, value)

        for col in range(1, last_col + 1):
            cell = ws.cell(row, col)
            cell.fill = PatternFill("solid", fgColor=COLORS["header"] if col == 2 else section_color)
            cell.border = THIN_BORDER
            cell.alignment = center
            cell.font = blue_font if col == 1 else bold_font
            if col == 1 or col >= 4:
                cell.number_format = '#,##0"만원";[Red]-#,##0"만원";;@'
        ws.row_dimensions[row].height = 25
    group_ranges.append((group_start, coverage_end))

    for start, end in group_ranges:
        if end > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=end, end_column=2)
        ws.cell(start, 2).alignment = center
        _set_outline(ws, start, end, 1, last_col, MEDIUM_SIDE)

    _set_outline(ws, 2, 3, 1, last_col, MEDIUM_SIDE)
    _set_outline(ws, 4, 6, 1, last_col, MEDIUM_SIDE)
    _set_outline(ws, 7, 10, 1, last_col, MEDIUM_SIDE)

    # C열(보장명)과 D열(첫 보험계약) 사이를 굵게 구분합니다.
    # 같은 보험사의 연속된 계약은 한 묶음으로 두고, 보험사가 바뀌는
    # 지점에만 굵은 세로 경계선을 표시합니다.
    company_group_start = 4
    for col in range(5, last_col + 1):
        previous_company = str(ws.cell(2, col - 1).value or "").strip()
        current_company = str(ws.cell(2, col).value or "").strip()
        if current_company != previous_company:
            _set_outline(
                ws,
                2,
                coverage_end,
                company_group_start,
                col - 1,
                MEDIUM_SIDE,
            )
            company_group_start = col
    _set_outline(
        ws,
        2,
        coverage_end,
        company_group_start,
        last_col,
        MEDIUM_SIDE,
    )

    # A열부터 마지막 보험계약 열까지 모든 내부 세로선을 굵게 표시합니다.
    # 가로선은 기존 굵기를 그대로 유지합니다.
    _set_vertical_borders(ws, 2, coverage_end, 1, last_col, MEDIUM_SIDE)

    # 모든 내부 경계선을 적용한 뒤 표 전체 외곽선을 마지막에 다시
    # 설정해 2행부터 시작하는 굵은 테두리가 중간에 끊기지 않게 합니다.
    _set_outline(ws, 2, coverage_end, 1, last_col, THICK_SIDE)

    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 11
    ws.column_dimensions["C"].width = 31
    contract_width = _contract_column_width(contract_count)
    for col in range(4, last_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = contract_width

    # 첫 행의 보험계약 영역은 하단 정렬과 굵은 글씨를 사용합니다.
    for col in range(4, last_col + 1):
        cell = ws.cell(1, col)
        alignment = copy(cell.alignment)
        alignment.vertical = "bottom"
        cell.alignment = alignment
        font = copy(cell.font)
        font.name = "나눔고딕"
        font.bold = True
        cell.font = font

    # 다운로드 엑셀의 모든 셀 글꼴을 나눔고딕으로 통일하되,
    # 크기·굵기·색상 등 기존 글꼴 속성은 그대로 유지합니다.
    for row in ws.iter_rows(min_row=1, max_row=coverage_end, min_col=1, max_col=last_col):
        for cell in row:
            font = copy(cell.font)
            font.name = "나눔고딕"
            cell.font = font

    _configure_print(ws, contract_count, len(selected), coverage_end, last_col, page_count)

def _populate_proposal_sheet(
    workbook: Workbook,
    data: dict,
    selected: list[dict],
) -> None:
    """보장 분석 합계와 사용자가 입력할 보장 제안 칸을 한 표에 구성합니다."""
    ws = workbook.create_sheet("보장 제안서")
    ws.sheet_view.showGridLines = False
    ws.oddHeader.right.text = "&K1769DC&BH  |  화랑 WORKSPACE"
    ws.oddHeader.right.size = 9
    ws.oddHeader.right.font = "Pretendard,Bold"

    proposal_start_col = 5  # E열
    proposal_end_col = 9  # I열
    coverage_start = 11
    output_items = [
        {"label": "일반사망", "display": "일반 사망", "group": "사망"},
        *selected,
        {"label": "기타", "display": "기타", "group": "기타"},
    ]
    coverage_end = coverage_start + len(output_items) - 1

    bold_font = Font(name="나눔고딕", size=10, bold=True, color=COLORS["black"])
    blue_font = Font(name="나눔고딕", size=11, bold=True, color=COLORS["blue"])
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.merge_cells("A1:D1")
    age_text = f" (보험연령:{data['age']}세)" if data["age"] else ""
    title_customer_name = re.sub(r"님$", "", str(data["customer_name"] or "OOO").strip()) or "OOO"
    ws["A1"] = f"{title_customer_name}님의 보장 제안서{age_text}"
    ws["A1"].font = Font(name="나눔고딕", size=14, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="bottom")
    ws.row_dimensions[1].height = 82
    for col in range(1, proposal_end_col + 1):
        ws.cell(1, col).fill = PatternFill("solid", fgColor=COLORS["white"])
        ws.cell(1, col).border = Border()
        ws.cell(1, col).alignment = center

    logo = XLImage(BytesIO(_extract_logo()))
    logo.width = 350
    logo.height = 43
    ws.add_image(logo, "A1")

    for col in range(1, 5):
        ws.merge_cells(start_row=2, start_column=col, end_row=3, end_column=col)
    ws["A2"] = "기존 보험 합계"
    ws["B2"] = "구분"
    ws["C2"] = "보장명"
    ws["D2"] = "보장 제안 합계"
    ws["A2"].font = Font(name="나눔고딕", size=11, bold=True, color=COLORS["red"])
    ws["D2"].font = Font(name="나눔고딕", size=11, bold=True, color=COLORS["red"])

    # E~I열은 제목을 포함해 사용자가 자유롭게 작성할 수 있도록 비워 둡니다.
    for row in range(2, 4):
        for col in range(1, proposal_end_col + 1):
            cell = ws.cell(row, col)
            cell.fill = PatternFill("solid", fgColor=COLORS["header"])
            cell.border = THIN_BORDER
            cell.alignment = center
            if col not in (1, 4):
                cell.font = bold_font
    ws.row_dimensions[2].height = 25
    ws.row_dimensions[3].height = 25

    # 보장 분석 시트와 동일하게 계약 기본정보 및 보험료 요약 행을 유지합니다.
    meta_rows = [
        (4, "보장기간"),
        (5, "납입횟수"),
        (6, "납입주기"),
        (7, "월보험료"),
        (8, "납입완료"),
        (9, "납입예정"),
        (10, "총보험료"),
    ]
    proposal_total_fill = PatternFill("solid", fgColor="FFFF00")
    for row, label in meta_rows:
        if row <= 6:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            ws.cell(row, 1, label)
        else:
            ws.cell(row, 1, f"='보장 분석'!A{row}")
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
            ws.cell(row, 2, label)
            ws.cell(row, 4, f"=SUM(E{row}:I{row})")

        fill_color = COLORS["header"] if row == 7 or row <= 6 else COLORS["premium"]
        for col in range(1, proposal_end_col + 1):
            cell = ws.cell(row, col)
            cell.fill = (
                proposal_total_fill
                if col == 4 and row >= 7
                else PatternFill("solid", fgColor=fill_color)
            )
            cell.border = THIN_BORDER
            cell.alignment = center
            cell.font = blue_font if row >= 7 and col in (1, 4) else bold_font
            if row >= 7 and (col == 1 or col >= 4):
                cell.number_format = '#,##0"원"'
        ws.row_dimensions[row].height = 25

    group_ranges: list[tuple[int, int]] = []
    group_start = coverage_start
    current_group = output_items[0]["group"]
    for offset, item in enumerate(output_items):
        row = coverage_start + offset
        group = item["group"]
        if group != current_group:
            group_ranges.append((group_start, row - 1))
            group_start = row
            current_group = group

        section_color = COLORS["white"]
        if group == "암\n보장":
            section_color = COLORS["cancer"]
        elif group == "뇌\n보장":
            section_color = COLORS["brain"]
        elif group == "심장\n보장":
            section_color = COLORS["heart"]

        analysis_row = coverage_start + offset
        ws.cell(row, 1, f"='보장 분석'!A{analysis_row}")
        ws.cell(row, 2, group)
        ws.cell(row, 3, item["display"]).data_type = "s"
        ws.cell(row, 4, f"=SUM(E{row}:I{row})")

        for col in range(1, proposal_end_col + 1):
            cell = ws.cell(row, col)
            if col == 4:
                cell.fill = proposal_total_fill
            else:
                cell.fill = PatternFill("solid", fgColor=COLORS["header"] if col == 2 else section_color)
            cell.border = THIN_BORDER
            cell.alignment = center
            cell.font = blue_font if col in (1, 4) else bold_font
            if col == 1 or col >= 4:
                cell.number_format = '#,##0"만원";[Red]-#,##0"만원";;@'
            if row >= coverage_start and proposal_start_col <= col <= proposal_end_col:
                font = copy(cell.font)
                font.color = COLORS["black"]
                cell.font = font
        ws.row_dimensions[row].height = 25
    group_ranges.append((group_start, coverage_end))

    for start, end in group_ranges:
        if end > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=end, end_column=2)
        ws.cell(start, 2).alignment = center
        _set_outline(ws, start, end, 1, proposal_end_col, MEDIUM_SIDE)

    _set_outline(ws, 2, 3, 1, proposal_end_col, MEDIUM_SIDE)
    _set_outline(ws, 4, 6, 1, proposal_end_col, MEDIUM_SIDE)
    _set_outline(ws, 7, 10, 1, proposal_end_col, MEDIUM_SIDE)
    _set_vertical_borders(ws, 2, coverage_end, 1, proposal_end_col, MEDIUM_SIDE)
    _set_outline(ws, 2, coverage_end, 1, proposal_end_col, THICK_SIDE)

    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 11
    ws.column_dimensions["C"].width = 31
    ws.column_dimensions["D"].width = 18
    for col in range(proposal_start_col, proposal_end_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18

    # 첫 행의 직접 입력 영역은 보장 분석 시트와 동일하게
    # 하단 정렬과 굵은 글씨를 사용합니다.
    for col in range(proposal_start_col, proposal_end_col + 1):
        cell = ws.cell(1, col)
        alignment = copy(cell.alignment)
        alignment.vertical = "bottom"
        cell.alignment = alignment
        font = copy(cell.font)
        font.name = "나눔고딕"
        font.bold = True
        cell.font = font

    # 다운로드 엑셀의 모든 셀 글꼴을 나눔고딕으로 통일하되,
    # 크기·굵기·색상 등 기존 글꼴 속성은 그대로 유지합니다.
    for row in ws.iter_rows(min_row=1, max_row=coverage_end, min_col=1, max_col=proposal_end_col):
        for cell in row:
            font = copy(cell.font)
            font.name = "나눔고딕"
            cell.font = font

    _configure_print(ws, 5, len(selected), coverage_end, proposal_end_col)

@session_export("analysis-excel-v3", name_arg=False)
def build_analysis_file(
    main_bytes: bytes,
    selected_labels: list[str] | None = None,
) -> tuple[bytes, str, str]:
    data = parse_source_file(main_bytes)
    available = {item["label"]: item for item in data["coverages"]}

    if selected_labels is None:
        selected_labels = DEFAULT_COVERAGES
    normalized_selection = {_normalize_label(label) for label in selected_labels}
    selected = [item for item in data["coverages"] if item["label"] in normalized_selection]
    if not selected:
        raise ValueError("출력할 보장항목을 한 개 이상 선택해 주세요.")

    workbook = Workbook()
    workbook.remove(workbook.active)
    all_contract_indices = list(range(len(data["contracts"])))
    _populate_analysis_sheet(
        workbook,
        "보장 분석",
        data,
        selected,
        all_contract_indices,
        contracts_per_page=len(data["contracts"]),
        page_count=1,
    )
    _populate_proposal_sheet(workbook, data, selected)
    workbook.calculation.calcMode = "auto"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True

    today = datetime.today().strftime("%Y%m%d")
    filename_name = re.sub(r"님$", "", str(data["customer_name"] or "OOO").strip())
    filename_name = re.sub(r'[\\/:*?"<>|]+', "_", filename_name).strip() or "OOO"
    filename = f"{filename_name}님_보장분석엑셀_{today}.xlsx"
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue(), filename, data["customer_name"]
