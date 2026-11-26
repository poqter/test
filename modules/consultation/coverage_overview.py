"""Paired columns with a repeated legend for the coverage status section."""
from collections import Counter
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from modules.shared.report_fonts import coverage_fonts
from reportlab.platypus import PageBreak, Table, TableStyle, Spacer

STATUSES = [
    ("○", "기준 충족", "#35658A"), ("△", "기준 미만", "#946717"),
    ("×", "가입금액 0원", "#AA4545"), ("?", "확인 필요", "#505B68"),
    ("—", "기준 미설정", "#737B85"),
]

def add_overview(story, comparison, limits, heading, para, width, frame_height):
    from modules.consultation.coverage_signature import money
    rows = []
    counts = Counter()
    for item in comparison:
        values = item["values"]
        amount = sum(values) if values and all(isinstance(v,(float,int)) for v in values) else None
        limit = limits.get(item["label"])
        status = 3 if amount is None else 4 if not limit else 2 if amount == 0 else 0 if amount >= limit else 1
        mark, _, color = STATUSES[status]
        counts[status] += 1
        name = item["display"]
        if item["label"] in ("질병입원","상해입원","암입원") or "간병" in item["label"] and "입원" in item["label"]:
            name += " (1일)"
        number = para(money(limit) if limit else "—", 10)
        actual = para(money(amount) if amount is not None else "확인 필요", 10)
        symbol = para(mark, 11, color)
        number.style.alignment = actual.style.alignment = TA_RIGHT
        symbol.style.alignment = TA_CENTER
        rows.append([para(name, 10), number, actual, symbol])

    bold = coverage_fonts()[1]
    header = [para(t, 10, "#FFFFFF", bold) for t in ("보장 항목", "기준금액", "가입금액", "결과")]
    header[1].style.alignment = header[2].style.alignment = TA_RIGHT
    header[3].style.alignment = TA_CENTER
    widths = [width * part for part in (.218, .093, .111, .064)]
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#17233C"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), .35, "#E3E6EA"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    def side(items):
        return Table([header, *items], colWidths=widths, style=style)

    legend = [para(f"{mark} {name} {counts[i]}개", 9, color)
              for i, (mark, name, color) in enumerate(STATUSES)]
    offset = 0
    while offset < len(rows):
        story.append(PageBreak())
        start = len(story)
        heading("전체 보장 현황")
        story.extend([Table([legend], colWidths=[width/5]*5), Spacer(1, 8),
                      para("단위  만원", 9), Spacer(1, 4)])
        room = frame_height - sum(f.wrap(width, frame_height)[1] for f in story[start:])

        # Keep source order and fill this page first. Try balanced columns first
        # only among splits that show the same number of items on this page.
        for count in range(min(48, len(rows)-offset), 0, -1):
            chunk = rows[offset:offset+count]
            splits = sorted(range(max(1, count-24), min(24, count)+1),
                            key=lambda n: abs(n-(count+1)//2))
            for n in splits:
                left = side(chunk[:n])
                right = side(chunk[n:]) if n < count else ""
                pair = Table([[left, "", right]], colWidths=[sum(widths), width*.028, sum(widths)],
                             style=[("VALIGN",(0,0),(-1,-1),"TOP"),
                                    ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                                    ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)])
                if pair.wrap(width, room)[1] <= room:
                    break
            else:
                continue
            story.append(pair)
            offset += count
            break
        else:
            raise ValueError("보장 항목 한 행이 인쇄 영역을 초과합니다.")
