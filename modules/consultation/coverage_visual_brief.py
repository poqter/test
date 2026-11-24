"""Graphical briefing shared by the KB and consulting workbook entry points."""

from io import BytesIO
from math import cos, pi, sin
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Line, Polygon, String
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Paragraph,
    Table,
    TableStyle,
    SimpleDocTemplate,
    PageBreak,
    Spacer,
)

from modules.shared.report_fonts import korean_pdf_font
from modules.consultation.analyzer_pdf import amount
from modules.consultation.coverage_signature import money

AXES = [
    ("상해사망", "재해(상해)사망"),
    ("질병사망", "질병사망"),
    ("일반암", "일반암"),
    ("고액(표적)항암치료비", "표적항암약물허가치료비"),
    ("뇌혈관질환", "뇌혈관"),
    ("허혈성심장질환", "허혈성심장질환"),
    ("질병입원의료비", "질병입원(실손)"),
    ("질병수술비", "질병수술"),
    ("질병종수술", "질병종수술"),
    ("질병입원일당", "질병입원"),
    ("간병인/간호간병질병일당", "간병인지원입원일-질병"),
]


def radar(entries, font):
    drawing = Drawing(500, 340)
    cx, cy, r = 250, 169, 112

    def at(index, radius):
        theta = 2 * pi * index / len(entries)
        return cx + radius * sin(theta), cy + radius * cos(theta)

    for scale in (0.3, 0.7, 1):
        points = [
            coordinate for i in range(len(entries)) for coordinate in at(i, r * scale)
        ]
        drawing.add(
            Polygon(
                points,
                strokeColor=colors.HexColor("#C7D7D2"),
                strokeWidth=0.7,
                fillColor=None,
            )
        )
    points = []
    for i, (label, value, reference) in enumerate(entries):
        x, y = at(i, r)
        drawing.add(
            Line(cx, cy, x, y, strokeColor=colors.HexColor("#D4DFDB"), strokeWidth=0.5)
        )
        points.extend(at(i, r * min(value / reference, 1)))
        x, y = at(i, r + 26)
        align = "start" if x > cx + 12 else "end" if x < cx - 12 else "middle"
        drawing.add(String(x, y, label, fontName=font, fontSize=8, textAnchor=align))
        drawing.add(
            String(
                x,
                y - 12,
                money(value) + "만원" if value else "0원",
                fontName=font,
                fontSize=9,
                textAnchor=align,
            )
        )
    drawing.add(
        Polygon(
            points,
            strokeColor=colors.HexColor("#25766A"),
            strokeWidth=1.2,
            fillColor=colors.HexColor("#B9D7CE"),
        )
    )
    return drawing


def brief_pdf(parsed):
    out = BytesIO()
    font = korean_pdf_font()
    doc = SimpleDocTemplate(
        out,
        leftMargin=36,
        rightMargin=36,
        topMargin=38,
        bottomMargin=34,
        title="고객용 보장 브리핑",
    )

    def text(s, size=10):
        return Paragraph(
            escape(str(s)),
            ParagraphStyle(
                "body",
                fontName=font,
                fontSize=size,
                leading=size * 1.5,
                wordWrap="CJK",
                textColor=colors.HexColor("#172F39"),
            ),
        )

    def block(label, items):
        rows = [[text(label, 14), ""]] + [[text(k), text(v)] for k, v in items]
        grid = Table(rows, colWidths=[345, 165], repeatRows=1, hAlign="LEFT")
        grid.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 0), (-1, 0)),
                    ("BACKGROUND", (0, 0), (-1, 0), "#DCEBE6"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.4, "#D6E0DA"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return grid

    kb = parsed.get("kb", {})
    matrix = kb.get("matrix", {})
    workbook = {r["label"]: r for r in parsed["coverages"]}
    story = [
        text("HWARANG   /   고객용 보장 브리핑", 10),
        Spacer(1, 16),
        text(parsed["customer_name"] + " 님의 보장 현황", 23),
    ]
    contracts = parsed["contracts"]
    known = sum(
        c["monthly"] for c in contracts if isinstance(c["monthly"], (float, int))
    )
    missing = sum(c.get("premium_missing", False) for c in contracts)
    story.append(
        text(
            f"계약 {len(contracts)}건　 ·　 확인된 월 보험료 {known:,}원"
            + (f"　 ·　 {missing}건 미제공" if missing else "")
        )
    )
    entries = []
    extra = []
    for label, key in AXES:
        if label in matrix:
            value = amount(matrix[label]["total"])
            ref = amount(kb.get("references", {}).get(label) or "-")
        elif key in workbook:
            row = workbook[key]
            if any(isinstance(v, str) for v in row["values"]):
                continue
            value = sum(row["values"])
            ref = row.get("reference") or 0
        else:
            continue
        if ref:
            entries.append((label, value, ref))
        elif value:
            extra.append((label, money(value) + "만원"))
    if len(entries) >= 3:
        story.append(radar(entries, font))
    else:
        extra.extend((label, money(v) + "만원") for label, v, _ in entries)
    for r in parsed.get("details", []):
        if "간병" in r["standard"] and "일당" in r["standard"]:
            extra.append(
                (
                    contracts[r["contract"]]["company"] + " · " + r["standard"],
                    "하루 " + money(r["value"]) + "만원",
                )
            )
    if extra:
        story.append(block("보장 금액", extra))
    sections = {}
    for label, r in workbook.items():
        values = r["values"]
        if not any(isinstance(v, (int, float)) and v > 0 for v in values):
            continue
        if parsed.get("details") and "암" in label:
            continue
        known_value = (
            "확인 필요"
            if any(isinstance(v, str) for v in values)
            else money(sum(values)) + "만원"
        )
        sections.setdefault(r["group"], []).append((r["display"], known_value))
    cancer = []
    for r in parsed.get("details", []):
        if "암" in r["raw"] or "암" in r["standard"]:
            cancer.append(
                (
                    contracts[r["contract"]]["company"] + " · " + r["raw"],
                    money(r["value"]) + "만원",
                )
            )
    if cancer:
        sections = {"내 암 보장": cancer, **sections}
    # Historical official cases. Keep costing periods visible and avoid implying a personal co-pay.
    if cancer or any(
        "암" in row["label"]
        and any(isinstance(v, (int, float)) and v > 0 for v in row["values"])
        for row in parsed["coverages"]
    ):
        sections["항암제 투약 비용 · 보건복지부 발표 사례"] = [
            ("키트루다 · 전이성 비소세포폐암 등 (2022년)", "연간 약 1억원"),
            ("킴리아 · 급성 림프성 백혈병 등 (2022년)", "1회 약 4억원"),
        ]
    for idx, (label, rows) in enumerate(sections.items()):
        story.append(PageBreak() if idx % 2 == 0 else Spacer(1, 18))
        story.append(block(label, rows))
    doc.build(story)
    return out.getvalue()
