"""Premium branded calculation snapshots for customer delivery."""
from io import BytesIO
from html import escape
from decimal import Decimal
import re

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from modules.shared.pdf_brand import draw_brand
from modules.shared.report_fonts import customer_pdf_fonts, pdf_text
from modules.shared.runtime_cache import session_export


def value_text(value):
    if value is None:
        return "미적용"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, (int, float, Decimal)):
        return format(value, ",")
    if isinstance(value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return format(Decimal(value), ",")
    return str(value)


def _customer_value(value: object) -> str:
    """Remove redundant won repetition when a manwon display already exists."""
    text = value_text(value).strip()
    match = re.fullmatch(r"(.+?만원)\s*\((-?[\d,]+)원\)", text)
    return match.group(1) if match else text


@session_export("calculator-pdf-v6")
def build_result_pdf(
    name,
    inputs,
    result,
    stamp,
    *,
    include_results=True,
    include_inputs=True,
    include_basis=True,
    enlarge_results=False,
):
    if not any((include_results, include_inputs, include_basis)):
        raise ValueError("PDF에 포함할 항목을 하나 이상 선택해주세요.")

    body_font, heading_font = customer_pdf_fonts()
    navy = colors.HexColor("#142d44")
    muted = colors.HexColor("#5c7186")
    line = colors.HexColor("#c9d6e3")
    inner_line = colors.HexColor("#e4ebf2")
    result_line = colors.HexColor("#9fbde5")
    result_bg = colors.HexColor("#f1f6fc")

    body = ParagraphStyle(
        "CalcBody",
        fontName=body_font,
        fontSize=9.4,
        leading=15.2,
        textColor=navy,
        wordWrap="CJK",
    )
    label_style = ParagraphStyle(
        "CalcLabel", parent=body, fontName=heading_font, fontSize=9.2, leading=14.5
    )
    value_style = ParagraphStyle(
        "CalcValue", parent=body, fontName=heading_font, fontSize=10, leading=15.5, alignment=2
    )
    title_style = ParagraphStyle(
        "CalcTitle",
        parent=body,
        fontName=heading_font,
        fontSize=21,
        leading=28,
        textColor=navy,
        spaceAfter=3,
    )
    section_style = ParagraphStyle(
        "CalcSection",
        parent=body,
        fontName=heading_font,
        fontSize=12.3,
        leading=18,
        textColor=navy,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    )
    note_style = ParagraphStyle(
        "CalcNote", parent=body, fontSize=8.8, leading=14.2, textColor=muted
    )

    def p(value, style=body):
        return Paragraph(
            escape(pdf_text(value_text(value))).replace("\n", "<br/>"), style
        )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=27 * mm,
        bottomMargin=22 * mm,
        title=name + " 결과 보고서",
        author="화랑 WORKSPACE",
    )
    width = A4[0] - 40 * mm
    story = [p(name, title_style), Spacer(1, 8)]

    def section_heading(title: str) -> None:
        # Customer PDFs use calm semantic headings rather than report step numbers.
        story.append(p(title, section_style))

    def _table_block(rows, *, highlight=False, primary=False):
        if not rows:
            return
        if primary:
            primary_label = ParagraphStyle(
                "PrimaryLabel",
                parent=label_style,
                fontSize=10.5 if enlarge_results else 9.5,
                leading=16,
                textColor=muted,
            )
            primary_value = ParagraphStyle(
                "PrimaryValue",
                parent=value_style,
                fontSize=21 if enlarge_results else 16,
                leading=29 if enlarge_results else 22,
                textColor=colors.HexColor("#163e71"),
            )
            data = [[p(rows[0][0], primary_label), p(_customer_value(rows[0][1]), primary_value)]]
            table = Table(data, colWidths=[width * 0.43, width * 0.57], hAlign="LEFT", splitByRow=1)
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), result_bg),
                ("BOX", (0, 0), (-1, -1), 0.9, result_line),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 18 if enlarge_results else 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18 if enlarge_results else 14),
            ]))
            story.append(table)
            return

        data = [[p(label, label_style), p(_customer_value(value), value_style)] for label, value in rows]
        table = Table(
            data,
            colWidths=[width * 0.43, width * 0.57],
            hAlign="LEFT",
            splitByRow=1,
            splitInRow=1,
        )
        bg = colors.HexColor("#f7faff") if highlight else colors.white
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            # A subtle outer border makes each table read as one complete block.
            ("BOX", (0, 0), (-1, -1), 0.7, result_line if highlight else line),
            ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
            ("INNERHORIZONTAL", (0, 0), (-1, -1), 0.35, inner_line),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)

    def table(rows, *, highlight=False, primary=False):
        pending = []
        for label, value in rows:
            text = pdf_text(_customer_value(value))
            if len(text) > 600 or len(pdf_text(label)) > 180:
                _table_block(pending, highlight=highlight)
                pending = []
                story.append(
                    p(
                        label,
                        ParagraphStyle(
                            "LongLabel",
                            parent=label_style,
                            fontSize=9.7,
                            leading=15,
                            spaceBefore=9,
                            spaceAfter=4,
                            keepWithNext=True,
                        ),
                    )
                )
                story.append(p(_customer_value(value), note_style))
                story.append(Spacer(1, 6))
            else:
                pending.append((label, value))
        if primary and pending:
            _table_block([pending[0]], highlight=True, primary=True)
            pending = pending[1:]
        _table_block(pending, highlight=highlight)

    # Reading order: customer conditions -> result -> basis.
    if include_inputs:
        section_heading("계산에 사용한 입력")
        table(inputs)

    if include_results:
        section_heading("계산 결과")
        from modules.calculators.input_design import _primary_metric_index
        from modules.calculators.visuals import primary_result_labels

        displayed = list(result.display().items())
        if displayed:
            first = _primary_metric_index(displayed, primary_result_labels(name))
            primary_row = [displayed[first]]
            secondary_rows = [item for i, item in enumerate(displayed) if i != first]
            table(primary_row, highlight=True, primary=True)
            if secondary_rows:
                story.append(Spacer(1, 7))
                table(secondary_rows, highlight=True)

    if include_basis:
        section_heading("산출 근거 및 적용 조건")
        from modules.calculators.rule_metadata import rule_for

        record = rule_for(name)
        applies_to = record.get("applies_to") if record else ""
        if applies_to:
            story.append(p(applies_to, note_style))
            story.append(Spacer(1, 5))
        story.append(p(result.formula, body))
        story.append(Spacer(1, 8))
        shown_notes = []
        seen_notes = {str(applies_to).strip()} if applies_to else set()
        if record:
            for note in record.get("limitations", ()):
                text = str(note).strip()
                if text and text not in seen_notes:
                    shown_notes.append(text)
                    seen_notes.add(text)
        for note in result.assumptions:
            text = str(note).strip()
            if text and text not in seen_notes:
                shown_notes.append(text)
                seen_notes.add(text)
        for note in shown_notes:
            story.append(p("- " + str(note), note_style))
            story.append(Spacer(1, 4))

    def page(canvas, document):
        draw_brand(canvas, document.page)

    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def pdf_section_options(key):
    import streamlit as st

    st.caption("PDF에 포함할 내용")
    columns = st.columns([1, 1, 1.65], gap="small")
    options = {}
    for column, field, label in zip(
        columns,
        ("include_inputs", "include_results", "include_basis"),
        ("입력 내용", "계산 결과", "산출 근거 및 적용 조건"),
    ):
        with column:
            options[field] = st.checkbox(label, value=True, key=key + "_sections_v3_" + field)
    if not any(options.values()):
        st.info("PDF에 포함할 항목을 하나 이상 선택해주세요.")
    enlarged = st.checkbox(
        "계산 결과 크게 표시",
        value=False,
        disabled=not options["include_results"],
        key=key + "_enlarge_results_v2",
        help="체크하면 대표 계산 결과를 한 단계 더 크게 표시합니다.",
    )
    options["enlarge_results"] = enlarged and options["include_results"]
    return options
