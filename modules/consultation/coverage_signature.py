"""Customer-facing KB report. Raw contract indices are the identity throughout."""

from io import BytesIO
from pathlib import Path
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
from modules.shared.report_fonts import coverage_fonts
from modules.consultation.analyzer_pdf import amount, norm

NAVY = "#17233C"
GOLD = "#B89555"
IVORY = "#F3EBDD"
LINE = "#E3E6EA"


def ribbon(canvas, x, y, width, height):
    """Layer sweeping brand ribbons inside a bounded illustration area."""
    canvas.saveState()
    canvas.translate(x, y)
    canvas.scale(width, height)
    for offset, shade in [(0.34, "#344360"), (0.21, "#526079"), (0.12, GOLD), (0.10, "#283650")]:
        path = canvas.beginPath()
        path.moveTo(0, 0)
        path.curveTo(0.38, offset, 0.58, 0.0, 1, 0.65 + offset)
        path.lineTo(1, 0)
        path.close()
        canvas.setFillColor(colors.HexColor(shade))
        canvas.drawPath(path, fill=1, stroke=0)
    canvas.restoreState()


INSURERS = (
    ('한화생명', 'hanwha_life'),
    ('미래에셋생명', 'miraeasset_life'),
    ('신한라이프', 'shinhan_life'),
    ('흥국생명', 'heungkuk_life'),
    ('교보생명', 'kyobo_life'),
    ('메트라이프', 'metlife'),
    ('DB생명', 'db_life'),
    ('농협생명', 'nh_life'),
    ('라이나생명', 'lina_life'),
    ('KB라이프생명', 'kb_life'),
    ('삼성생명', 'samsung_life'),
    ('IBK연금보험', 'ibk_pension'),
    ('동양생명', 'tongyang_life'),
    ('ABL생명', 'abl_life'),
    ('KDB생명', 'kdb_life'),
    ('BNP파리바 카디프생명', 'bnp_cardif_life'),
    ('KB손해보험', 'kb_insurance'),
    ('한화손해보험', 'hanwha_general'),
    ('롯데손해보험', 'lotte_insurance'),
    ('라이나손해보험', 'lina_general'),
    ('삼성화재', 'samsung_fire'),
    ('하나손해보험', 'hana_insurance'),
    ('예별손해보험', 'yebyeol'),
    ('흥국화재', 'heungkuk_fire'),
    ('DB손해보험', 'db_insurance'),
    ('메리츠화재', 'meritz_fire'),
    ('현대해상', 'hyundai_marine'),
    ('AIG손해보험', 'aig_insurance'),
)


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


CONTRACT_LOGOS = {
    **dict(INSURERS),
    "DB손보": "db_insurance", "KB손보": "kb_insurance", "KB라이프생명보험": "kb_life",
    "하나손보": "hana_insurance", "신한라이프생명": "shinhan_life", "한화손보": "hanwha_general",
    "NH농협생명": "nh_life", "롯데손보": "lotte_insurance", "메트라이프생명": "metlife",
    "AIG손보": "aig_insurance", "라이나(에이스)손보": "lina_general",
    "AXA손보": "axa", "AXA손해보험": "axa", "AIA생명": "aia", "새마을금고중앙회": "mgcc",
    "푸본현대생명": "fubon", "NH농협손보": "nh_nonlife", "NH농협손해보험": "nh_nonlife",
    "우정사업본부": "epost", "예별손보(구MG손보)": "yebyeol", "처브라이프생명": "chubb_life",
}


def insurer(index, company):
    key = CONTRACT_LOGOS.get(company)
    logo = Path(__file__).resolve().parents[2] / "assets" / "insurer_logos" / f"{key}.png"
    symbol = ""
    if key and logo.is_file():
        symbol = f'<img src="{logo}" width="10" height="10" valign="middle"/>&#160;'
    return f"{index:02}&#160;&#160;{symbol}{escape(company)}"


def build_signature(parsed, profile, selected_labels=None):
    from modules.consultation.analyzer_exports import selected_coverage_rows

    from modules.consultation.analyzer_state import sort_contracts
    from modules.consultation.analyzer_limits import DEFAULT_LIMITS
    parsed = sort_contracts(parsed)
    limits = parsed.get("comparison_limits", DEFAULT_LIMITS)
    raw = parsed["kb"]
    comparison = [row for row in selected_coverage_rows(parsed, selected_labels)
                  if row["label"] != "일반사망"]
    contracts = raw["contracts"]
    body_font, font = coverage_fonts()
    out = BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=21,
        rightMargin=21,
        topMargin=49,
        bottomMargin=37,
        title="화랑 보장분석",
    )
    story = []

    def para(text, size=9, color=NAVY, face=None, leading=None):
        style = ParagraphStyle(
            "cell",
            fontName=face or body_font,
            fontSize=size,
            leading=leading or size * 1.45,
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
        title = para(text, 19, face=font)
        title.outline = (f"section{len(story)}", text)
        story.extend([title, Spacer(1, 12)])

    def table(headers, rows, widths, size=10, repeat_title=None, column_rules=False):
        data = [
            [
                para(s, size, "#FFFFFF", font) if not isinstance(s, Paragraph) else s
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
        if column_rules:
            for column in range(1, len(headers)):
                thickness = 0.9 if column == 2 else 0.55
                style.append(("LINEBEFORE", (column, 0), (column, -1), thickness, colors.HexColor("#A7B2C2")))
        if repeat_title:
            for row in data:
                row[-1].style.alignment = 2
            company, product, terms = repeat_title
            full = [""] * (len(headers) - 1)
            field_width = (doc.width - 22) / 3
            fields = Table(
                [[para(f"{label}　{value}", 10) for label, value in terms]],
                colWidths=[field_width] * 3,
                style=[("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ("TOPPADDING", (0, 0), (-1, -1), 0),
                       ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                       ("LEFTPADDING", (0, 0), (-1, -1), 3),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 9)],
            )
            data[:0] = [
                [[para(company, 9, "#475368", body_font), Spacer(1, 3), para(product, 14, NAVY, font)]] + full,
                [fields] + full,
                [Spacer(1, 14)] + full,
            ]
            repeat = 4
            style.extend([
                ("SPAN", (0, 0), (-1, 0)), ("SPAN", (0, 1), (-1, 1)),
                ("BACKGROUND", (0, 0), (-1, 1), "#F6F3EC"),
                ("SPAN", (0, 2), (-1, 2)), ("BACKGROUND", (0, 3), (-1, 3), NAVY),
                ("LINEBEFORE", (0, 0), (0, 1), 1.25, GOLD),
            ])
        grid = Table(data, colWidths=[w * (doc.width - 12) / sum(widths) for w in widths], repeatRows=repeat, hAlign="LEFT")
        grid.setStyle(
            TableStyle(
                style
                + [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    (
                        "ROWBACKGROUNDS",
                        (0, repeat),
                        (-1, -1),
                        [colors.white] if repeat_title else [colors.white, colors.HexColor("#F7F6F2")],
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

    assets = Path(__file__).resolve().parents[2] / "assets"

    def watermark(canvas, right):
        canvas.saveState()
        canvas.setFillAlpha(0.62)
        mark = "화랑 WORKSPACE"
        mark_x = right - canvas.stringWidth(mark, font, 8)
        canvas.drawImage(str(assets.parent / "static" / "workspace-icon-180.png"),
                         mark_x - 15, 13, 11, 11, mask="auto")
        canvas.setFillColor(colors.HexColor("#556176"))
        canvas.setFont(font, 8)
        canvas.drawString(mark_x, 15, mark)
        canvas.restoreState()

    def cover(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#F9F6EF"))
        width, height = document.pagesize
        bleed = 3
        canvas.rect(-bleed, 240, width + 2 * bleed, height - 240 + bleed, fill=1, stroke=0)
        for index, shade in enumerate(("#DAE2E6", "#C6D2DA", GOLD, "#EAE4D8")):
            path = canvas.beginPath()
            path.moveTo(-bleed, 240)
            path.curveTo(214, 290, 405, 255, width + bleed, 445 - index * 17)
            path.lineTo(width + bleed, 240)
            path.close()
            canvas.setFillColor(colors.HexColor(shade))
            canvas.drawPath(path, fill=1, stroke=0)
        canvas.drawImage(str(assets / "hanwha_life_lab.png"), 39, 770, 139, 39,
                         preserveAspectRatio=True, mask="auto")
        canvas.setFillColor(colors.HexColor("#576577"))
        canvas.setFont(font, 23)
        canvas.drawString(40, 550, raw["customer_name"] + " 님의")
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.setFont(font, 52)
        canvas.drawString(40, 475, "보장분석")
        canvas.setFillColor(colors.HexColor(NAVY))
        for x, label, value in [(40, "조회 기준일", raw["source_date"]), (212, "가입 계약", f"{len(contracts)}건")]:
            canvas.setFillColor(colors.HexColor("#F5F5F2"))
            canvas.roundRect(x, 184, 158, 44, 4, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor(NAVY))
            canvas.setFont(body_font, 9)
            canvas.drawString(x + 12, 213, label)
            canvas.setFont(font, 14)
            canvas.drawString(x + 12, 191, value)
        staff = " ".join(
            str(profile.get(k) or "") for k in ("display_name", "position_name")
        ).strip()
        watermark(canvas, 555)
        canvas.setFont(font, 11)
        if staff:
            canvas.drawRightString(552, 191, "담당자   " + staff)
        canvas.setStrokeColor(colors.HexColor(LINE))
        canvas.line(40, 171, 555, 171)
        canvas.setFont(font, 10)
        canvas.drawString(40, 152, "취급 보험사")
        for index, (name, key) in enumerate(sorted(INSURERS, key=lambda item: len(item[0].replace(" ", "")))):
            row, col = divmod(index, 6)
            x, y = 40 + col * 87, 129 - row * 23
            if key and (assets / "insurer_logos" / (key + ".png")).is_file():
                canvas.drawImage(str(assets / "insurer_logos" / (key + ".png")), x, y - 2, 12, 12,
                                 preserveAspectRatio=True, mask="auto")
            else:
                canvas.setFillColor(colors.HexColor(IVORY))
                canvas.roundRect(x, y - 2, 12, 12, 2, fill=1, stroke=0)
                canvas.setFillColor(colors.HexColor(NAVY))
                canvas.setFont(font, 7)
                canvas.drawCentredString(x + 6, y + 1, "예")
            canvas.setFont(body_font, 7.5)
            canvas.drawString(x + 15, y, name)
        canvas.restoreState()

    def footer(canvas, document):
        canvas.setFont(font, 9)
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.drawString(29, 811, "HWARANG")
        ribbon(canvas, 88, 811, 38, 9)
        canvas.drawRightString(565, 811, "화랑 보장분석   /   " + raw["source_date"])
        watermark(canvas, 535)
        canvas.drawRightString(565, 15, str(document.page))

    story.append(PageBreak())
    heading(raw["customer_name"] + " 님의 계약 현황")
    payment_rows = parsed["contracts"]
    known = [r for r in payment_rows if not r["payment_unknown"]]
    monthly = [c["monthly"] for c in contracts if not c["premium_missing"] and c["cycle"] == "월납"]
    life = sum(any(word in c["company"] for word in ("생명", "라이프", "연금보험")) for c in contracts)
    nonlife = sum(any(word in c["company"] for word in ("손해", "손보", "화재", "해상", "보증보험")) for c in contracts)
    counts = f"생보 {life}건 · 손보 {nonlife}건"
    other = len(contracts) - life - nonlife
    if other:
        counts += f" · 기타 {other}건"

    def subtotal(values):
        if not values:
            return "산출 불가"
        return f"{sum(values):,}원"

    metrics = [("계약 건수", counts), ("확인된 월 보험료", subtotal(monthly)),
               ("납입완료 추정", subtotal([r["paid"] for r in known])),
               ("납입예정 추정", subtotal([r["remaining"] for r in known]))]
    width = doc.width - 12
    summary = Table([[para(k,8.4,"#526076",body_font) for k,v in metrics],[para(v,12,NAVY,font) for k,v in metrics]],colWidths=[width*f for f in (.22,.25,.25,.28)],hAlign="LEFT",style=[("BACKGROUND",(0,0),(-1,-1),"#F5F5F2"),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,0),6),("BOTTOMPADDING",(0,0),(-1,0),0),("BOTTOMPADDING",(0,1),(-1,1),6)])
    missing = sum(c["premium_missing"] for c in contracts)
    missing_note = f" · 월 보험료 {missing}건 미제공" if missing else ""
    story.extend([summary, Spacer(1, 10), para(f"유지 계약 {len(contracts)}건{missing_note}   ·   납입 추정 기준 {parsed['calculation_month']}", 10), Spacer(1, 6)])
    for index, (c, payment) in enumerate(zip(contracts, payment_rows), 1):
        premium = "미제공" if c["premium_missing"] else f"{c['monthly']:,}원"
        start_year, start_month = map(int, c["start"][:7].split("-"))
        last_month = start_year * 12 + start_month - 1 + c["years"] * 12 - 1
        pay_end = f"{last_month // 12}.{last_month % 12 + 1:02}" if c["years"] > 0 and c["cycle"] == "월납" else "미제공"
        maturity = "종신" if c["end"].startswith("9999") else c["end"][:7].replace("-", ".") + " · " + c["maturity"]
        def estimated(key):
            return "산출 불가" if payment["payment_unknown"] else f"{payment[key]:,}원"
        holder = (c.get("holder") or "").strip() or "미제공"
        insured = (c.get("insured") or "").strip() or "미제공"
        info = [
            ("계약자", holder), ("주피보험자", insured),
            ("계약년월", c["start"][:7].replace("-", ".")), ("납입만기(예정)", pay_end), ("보장만기", maturity),
            ("납입주기", c["cycle"]), ("납입횟수(추정)", payment["payment_count"]),
            ("총보험료(추정)", estimated("total")), ("납입완료(추정)", estimated("paid")), ("납입예정(추정)", estimated("remaining")),
        ]
        premium_label = para(premium, 11, "#36597A", font)
        premium_label.style.alignment = 2
        title = Table([[Paragraph(insurer(index,c["company"]),ParagraphStyle("insurer",fontName=font,fontSize=9.5,leading=12,textColor=colors.HexColor(NAVY))), para(c["product"], 10, NAVY, font, leading=12), premium_label]],
                      colWidths=[119, width-186, 67], style=[("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BACKGROUND",(0,0),(-1,-1),"#F0F3F5")])
        inline_style = ParagraphStyle("contract field", fontName=font, fontSize=9,
                                      leading=13, textColor=colors.HexColor(NAVY), wordWrap="CJK")
        def field(label, value):
            mark = ""
            if holder != insured and label in ("계약자", "주피보험자"):
                icon = assets / "contract_party_star.png"
                mark = f'&#160;<img src="{icon}" width="8" height="8" valign="middle"/>'
            return Paragraph(f'<font name="{body_font}" size="7.2" color="#48566B">{escape(label)}</font>'
                             f'&#160;&#160;{escape(str(value))}{mark}', inline_style)
        fields = [[field(k, v) for k, v in info[offset:offset+5]] for offset in (0, 5)]
        card = Table([[title, "", "", "", ""]] + fields,
                     colWidths=[width*f for f in (.145,.196,.21,.21,.239)], splitByRow=0, hAlign="LEFT",
                     style=[("SPAN",(0,0),(-1,0)),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                            ("LEFTPADDING",(0,0),(0,0),0),("RIGHTPADDING",(0,0),(0,0),0),
                            ("LEFTPADDING",(0,1),(-1,-1),3),("RIGHTPADDING",(0,1),(-1,-1),2),
                            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
                            ("LINEBELOW",(0,2),(-1,2),0.25,"#E4E8EB")])
        story.append(card)
        if index < len(contracts):
            story.append(Spacer(1, 23))
    from modules.consultation.coverage_overview import add_overview
    add_overview(story, comparison, limits, heading, para, doc.width - 12, doc.height - 12)
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
        story.append(Spacer(1, 23))
        premium = "미제공" if c["premium_missing"] else f"{c['monthly']:,}원"
        title = (f"{c['company']}  ·  계약 {i + 1:02}", c["product"],
                 (("가입일", c["start"]), ("만기", c["maturity"]), ("월 보험료", premium)))
        table(
            ["담보 분류", "회사 담보명", "가입금액"],
            [[para(r["standard"], 10, "#455268"), r["raw"], money(r["value"]) + "만원"] for r in c["rows"]],
            [120, 327, 84],
            10.5,
            title,
        )
    if raw["history"]:
        story.append(PageBreak())
        heading("실효·해지 계약 현황")
        table(
            ["상태", "보험사", "상품명", "가입일", "주기", "납입", "만기", "보험료"],
            raw["history"],
            [32, 52, 192, 68, 39, 38, 41, 69],
            10,
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
                        "link", fontName=font, fontSize=10, leading=13, wordWrap="CJK"
                    ),
                )
            )
        rows = []
        for item in comparison:
            values = item["values"]
            total = money(sum(values)) if all(isinstance(v, (int, float)) for v in values) else "확인 필요"
            cells = []
            for value in values[first:first + len(subset)]:
                if isinstance(value, str):
                    cells.append(value)
                else:
                    cells.append(money(value) if value else "–")
            rows.append([item["display"], total, *cells])
        story.append(PageBreak())
        heading("상품별 보장 비교")
        table(headers, rows, [114, 73] + [344 / len(subset)] * len(subset), 10, column_rules=True)
    doc.build(story, onFirstPage=cover, onLaterPages=footer)
    return out.getvalue()
