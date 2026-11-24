"""Graphical briefing shared by the KB and consulting workbook entry points."""

from io import BytesIO
from math import cos, pi, sin
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Line, Polygon, String, Circle, Rect
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Paragraph,
    Table,
    TableStyle,
    SimpleDocTemplate,
    PageBreak,
    Spacer,
)

from modules.shared.report_fonts import coverage_fonts
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
    ("상해수술비", "상해수술"),
    ("질병종수술", "질병종수술"),
    ("상해종수술", "상해종수술"),
    ("질병입원일당", "질병입원"),
    ("간병인/간호간병질병일당", "간병인지원입원일-질병"),
]


def radar(entries, font, amounts=None, surgery_caption=()):
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
        "상해종수술": "종수술비 · 상해",
        "질병종수술": "종수술비 · 질병",
        "질병입원일당": "입원일당 · 질병",
    }
    for i, (label, value, _) in enumerate(entries):
        x, y = at(i, r + 38)
        x = cx + (x - cx) * 1.02
        original_label = label
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
        label, shown = (amounts or {}).get(original_label, (label, shown))
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
        if original_label == "수술비":
            for index, line in enumerate(surgery_caption):
                drawing.add(String(x, y - 9 - index * 11, line, fontName=font,
                                   fontSize=8.5, textAnchor="middle",
                                   fillColor=colors.HexColor("#526375")))
            continue
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
    from modules.consultation.coverage_customer_brief import render_customer_brief
    return render_customer_brief(parsed)
