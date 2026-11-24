"""Graphical briefing shared by the KB and consulting workbook entry points."""

from io import BytesIO
from math import cos, pi, sin
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Line, Polygon, String, Circle
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
from modules.consultation.coverage_signature import GOLD, IVORY, LINE, NAVY, money, ribbon

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
    drawing = Drawing(510, 476)
    cx, cy, r = 255, 237, 151

    def at(index, radius):
        theta = 2 * pi * index / len(entries)
        return cx + radius * sin(theta), cy + radius * cos(theta)

    outline = colors.HexColor(NAVY)
    points = [
        at(i, r * max(0, min(value / reference, 1))) if reference else None
        for i, (_, value, reference) in enumerate(entries)
    ]
    vertices = [point for point in points if point is not None]
    flat = [coordinate for point in vertices for coordinate in point]
    drawing.add(Polygon(flat, fillColor=colors.HexColor(IVORY), strokeColor=None))
    for scale in (0.3, 0.7, 1):
        ring = [n for i in range(len(entries)) for n in at(i, r * scale)]
        drawing.add(
            Polygon(
                ring,
                fillColor=None,
                strokeColor=colors.HexColor("#CFC9BB"),
                strokeWidth=0.65,
            )
        )
    for i in range(len(entries)):
        drawing.add(
            Line(cx, cy, *at(i, r), strokeColor=colors.HexColor(LINE), strokeWidth=0.55)
        )
    drawing.add(
        Polygon(
            flat, fillColor=None, strokeColor=outline, strokeWidth=1.5, strokeLineJoin=1
        )
    )
    for x, y in set(vertices):
        drawing.add(
            Circle(
                x,
                y,
                2.4,
                fillColor=colors.HexColor(GOLD),
                strokeColor=outline,
                strokeWidth=0.7,
            )
        )
    aliases = {
        "간병인/간호간병질병일당": "간병일당 · 질병",
        "질병입원의료비": "실손 · 질병입원",
        "질병종수술": "종수술비 · 질병",
        "질병입원일당": "입원일당 · 질병",
    }
    for i, (label, value, _) in enumerate(entries):
        x, y = at(i, r + 38)
        x = cx + (x - cx) * 1.02
        label = aliases.get(label, label)
        if value >= 10000:
            billions, remainder = divmod(value, 10000)
            shown = (
                money(billions)
                + "억"
                + (" " + money(remainder) + "만원" if remainder else "원")
            )
        else:
            shown = money(value) + "만원" if value else "0원"
        drawing.add(
            String(
                x,
                y + 4,
                label,
                fontName=font,
                fontSize=9.5,
                textAnchor="middle",
                fillColor=outline,
            )
        )
        drawing.add(
            String(
                x,
                y - 12,
                shown,
                fontName=font,
                fontSize=12,
                textAnchor="middle",
                fillColor=outline,
            )
        )
    return drawing


def brief_pdf(parsed):
    out = BytesIO()
    font = korean_pdf_font()
    doc = SimpleDocTemplate(
        out,
        leftMargin=29,
        rightMargin=29,
        topMargin=73,
        bottomMargin=34,
        title="고객용 보장 브리핑",
    )

    def text(s, size=10, color=NAVY):
        return Paragraph(
            escape(str(s)),
            ParagraphStyle(
                "body",
                fontName=font,
                fontSize=size,
                leading=size * 1.5,
                wordWrap="CJK",
                textColor=colors.HexColor(color),
            ),
        )

    def block(label, items, lower=False):
        tint = "#E8EDF2" if lower else IVORY
        accent = NAVY if lower else GOLD
        rows = [[text(label, 13), "", ""]]
        for index in range(0, len(items), 2):
            cells = []
            for name, value in items[index:index + 2]:
                cells.append([text(name, 9), text(value, 13)])
            rows.append([cells[0], "", cells[1] if len(cells) > 1 else ""])
        grid = Table(rows, colWidths=[249, 12, 249], repeatRows=1, hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), tint),
            ("LINEBEFORE", (0, 0), (0, 0), 3, accent),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 1), (0, -1), 0.5, LINE),
            ("LINEBELOW", (2, 1), (2, -1), 0.5, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return grid

    kb = parsed.get("kb", {})
    matrix = kb.get("matrix", {})
    workbook = {r["label"]: r for r in parsed["coverages"]}
    story = [
        text("전체 보장", 12, "#85652D"),
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
        entries.append((label, value, ref))
    if sum(ref > 0 for _, _, ref in entries) >= 3:
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
        story.append(block(label, rows, lower=bool(idx % 2)))

    def frame(canvas, document):
        canvas.saveState()
        w, h = document.pagesize
        canvas.setFillColor(colors.HexColor("#FBFAF7"))
        canvas.rect(0, 0, w, h, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.setFont(font, 12)
        canvas.drawString(35, h - 36, "HWARANG")
        ribbon(canvas, 108, h - 36, 45, 12)
        canvas.setFont(font, 10)
        canvas.drawRightString(w - 35, h - 36, f"보장 브리핑   /   {document.page:02}")
        canvas.setStrokeColor(colors.HexColor(NAVY))
        canvas.line(35, h - 49, w - 35, h - 49)
        canvas.setStrokeColor(colors.HexColor(GOLD))
        canvas.line(35, 32, w - 35, 32)
        canvas.setFont(font, 8)
        canvas.drawString(
            35,
            17,
            parsed["customer_name"]
            + "  ·  "
            + str(parsed.get("source_date") or "컨설팅 보장분석"),
        )
        canvas.drawRightString(w - 35, 17, "고객용 보장 브리핑")
        canvas.restoreState()

    doc.build(story, onFirstPage=frame, onLaterPages=frame)
    return out.getvalue()
