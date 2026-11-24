"""Customer-facing KB report. Raw contract indices are the identity throughout."""

from io import BytesIO
from math import ceil
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    PageBreak,
    Spacer,
)
from modules.shared.report_fonts import korean_pdf_font
from modules.consultation.analyzer_pdf import amount, norm

NAVY = "#17233C"
GOLD = "#B89555"
IVORY = "#F3EBDD"
LINE = "#E3E6EA"


def money(value):
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def components(contract, name, source):
    keys = (
        ("도수", "주사", "MRI")
        if "비급여실손" in name
        else ("간병인", "간병통합서비스")
    )
    buckets = [[], [], []] if len(keys) == 3 else [[], []]
    for row in contract["rows"]:
        standard = norm(row["standard"])
        if len(keys) == 2 and ("상해" if "상해" in name else "질병") not in standard:
            continue
        if len(keys) == 3 and (row["kind"] != "실손" or "비급여" not in standard):
            continue
        for index, key in enumerate(keys):
            if key in standard:
                buckets[index].append(row["value"])
                break
    if not all(buckets):
        return None
    parts = [sum(bucket) for bucket in buckets]
    return parts if abs(sum(parts) - amount(source)) < 0.00001 else None


def build_signature(raw, profile):
    contracts = raw["contracts"]
    font = korean_pdf_font()
    out = BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=29,
        rightMargin=29,
        topMargin=49,
        bottomMargin=37,
        title="화랑 보장분석",
    )
    story = []

    def para(text, size=9, color=NAVY):
        style = ParagraphStyle(
            "cell",
            fontName=font,
            fontSize=size,
            leading=size * 1.45,
            textColor=colors.HexColor(color),
            wordWrap="CJK",
        )
        import unicodedata

        return Paragraph(
            escape(unicodedata.normalize("NFKC", str(text))).replace("\n", "<br/>"),
            style,
        )

    def record_section(flowable):
        entry = getattr(flowable, "outline", None)
        if entry:
            key, title = entry
            doc.canv.bookmarkPage(key)
            doc.canv.addOutlineEntry(title, key)

    doc.afterFlowable = record_section

    def heading(text):
        title = para(text, 21)
        title.outline = (f"section{len(story)}", text)
        story.extend([title, Spacer(1, 12)])

    def table(headers, rows, widths, size=9, repeat_title=None):
        data = [
            [
                para(s, size, "#FFFFFF") if not isinstance(s, Paragraph) else s
                for s in headers
            ]
        ]
        data.extend(
            [
                [v if isinstance(v, Paragraph) else para(v, size) for v in row]
                for row in rows
            ]
        )
        repeat = 1
        style = [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
        if repeat_title:
            data.insert(
                0, [para(repeat_title, 13, "#FFFFFF")] + [""] * (len(headers) - 1)
            )
            repeat = 2
            style.extend(
                [("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 1), NAVY)]
            )
        grid = Table(data, colWidths=widths, repeatRows=repeat, hAlign="LEFT")
        grid.setStyle(
            TableStyle(
                style
                + [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    (
                        "ROWBACKGROUNDS",
                        (0, repeat),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F7F6F2")],
                    ),
                    ("LINEBELOW", (0, repeat), (-1, -1), 0.35, colors.HexColor(LINE)),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5 if size < 8 else 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 if size < 8 else 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(grid)

    def cover(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.rect(0, 240, 596, 610, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor("#39465B"))
        for i in range(16):
            x = 320 + i * 5
            path = canvas.beginPath()
            path.moveTo(x, 842)
            path.lineTo(x, 450 + i * 3)
            path.lineTo(x + 150, 550 + i * 3)
            path.lineTo(x + 150, 842)
            canvas.drawPath(path)
        canvas.setFillColor(colors.white)
        canvas.setFont(font, 18)
        canvas.drawString(40, 786, "HWARANG")
        canvas.setFillColor(colors.HexColor(GOLD))
        canvas.setFont(font, 24)
        canvas.drawString(40, 585, raw["customer_name"] + " 님의")
        canvas.setFillColor(colors.white)
        canvas.setFont(font, 50)
        canvas.drawString(40, 508, "보장분석")
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.setFont(font, 15)
        canvas.drawString(
            40,
            164,
            f"조회 기준일   {raw['source_date']}      가입 계약   {len(contracts)}건",
        )
        staff = " ".join(
            str(profile.get(k) or "") for k in ("display_name", "position_name")
        ).strip()
        canvas.setFont(font, 11)
        canvas.drawString(40, 60, "화랑 WORKSPACE")
        if staff:
            canvas.drawRightString(552, 60, "담당자   " + staff)
        canvas.restoreState()

    def footer(canvas, document):
        canvas.setFont(font, 9)
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.drawString(29, 811, "HWARANG")
        canvas.drawRightString(565, 811, "화랑 보장분석   /   " + raw["source_date"])
        canvas.drawRightString(565, 20, str(document.page))

    story.append(PageBreak())
    heading(raw["customer_name"] + " 님의 계약 현황")
    premium = sum(c["monthly"] for c in contracts if not c["premium_missing"])
    missing = sum(c["premium_missing"] for c in contracts)
    story.extend(
        [
            para(
                f"가입 계약 {len(contracts)}건　 ·　 확인된 월 보험료 {premium:,}원"
                + (f"　 ·　 {missing}건 미제공" if missing else ""),
                13,
            ),
            Spacer(1, 16),
        ]
    )
    if contracts:
        badge = ParagraphStyle(
            "company",
            fontName=font,
            fontSize=9,
            leading=13,
            backColor=colors.HexColor(IVORY),
            borderPadding=2,
        )
        table(
            ["보험사", "가입 상품", "가입일", "만기", "월 보험료"],
            [
                [
                    Paragraph(escape(c["company"]), badge),
                    c["product"],
                    c["start"],
                    c["maturity"],
                    "미제공" if c["premium_missing"] else f"{c['monthly']:,}원",
                ]
                for c in contracts
            ],
            [62, 254, 78, 57, 80],
        )
    groups = ceil(len(contracts) / 5)
    for group in range(groups):
        first = group * len(contracts) // groups
        subset = contracts[first : (group + 1) * len(contracts) // groups]
        headers = ["보장 항목 (만원)", "전체"]
        for i, c in enumerate(subset, first):
            text = (
                escape(c["company"] + " · " + c["product"])
                + "<br/>"
                + escape(c["start"])
            )
            headers.append(
                Paragraph(
                    f'<link href="#contract{i}" color="white">{text}</link>',
                    ParagraphStyle(
                        "link", fontName=font, fontSize=8, leading=10, wordWrap="CJK"
                    ),
                )
            )
        rows = []
        for label, item in raw["matrix"].items():
            vals = [item["contracts"].get(i, "") for i in range(len(contracts))]
            special = "비급여실손" in label or "간호간병" in label
            parts = [
                components(c, label, v) if special and v and v != "-" else None
                for c, v in zip(contracts, vals)
            ]

            def display(v, part):
                if part:
                    return " / ".join(money(n) for n in part)
                return (
                    money(amount(v)) if v and v != "-" else ("–" if v else "확인 필요")
                )

            total = item["total"]
            total_parts = None
            known = [v for v in parts if v]
            if known and all(v == "-" or part for v, part in zip(vals, parts)):
                candidate = list(map(sum, zip(*known)))
                if sum(candidate) == amount(total):
                    total_parts = candidate
            title = label
            if known:
                title += "\n" + (
                    "도수 등 / 주사 / MRI"
                    if "비급여" in label
                    else "간병인 / 통합서비스"
                )
            rows.append(
                [title, display(total, total_parts) if total != "-" else "0"]
                + [
                    display(vals[i], parts[i])
                    for i in range(first, first + len(subset))
                ]
            )
        story.append(PageBreak())
        heading("상품별 보장 비교")
        table(headers, rows, [114, 73] + [344 / len(subset)] * len(subset), 7.7)
    for i, c in enumerate(contracts):
        story.append(PageBreak())
        story.append(
            Paragraph(
                f'<a name="contract{i}"/>계약별 상세 내역',
                ParagraphStyle("detail", fontName=font, fontSize=19, leading=27),
            )
        )
        story[-1].outline = (
            f"detail{i}",
            f"{c['company']} · {c['product']} · {c['start']}",
        )
        title = f"{c['company']}  ·  계약 {i + 1:02}   {c['product']}\n가입 {c['start']}     만기 {c['maturity']}     월 보험료 "
        title += "미제공" if c["premium_missing"] else f"{c['monthly']:,}원"
        table(
            ["회사 담보명", "담보 분류", "가입금액"],
            [[r["raw"], r["standard"], money(r["value"]) + "만원"] for r in c["rows"]],
            [310, 145, 76],
            9,
            title,
        )
    if raw["history"]:
        story.append(PageBreak())
        heading("실효·해지 계약 현황")
        table(
            ["상태", "보험사", "상품명", "가입일", "주기", "납입", "만기", "보험료"],
            raw["history"],
            [32, 52, 192, 68, 39, 38, 41, 69],
            8,
        )
    doc.build(story, onFirstPage=cover, onLaterPages=footer)
    return out.getvalue()
