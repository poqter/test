from io import BytesIO
import re
import unicodedata
from modules.consultation.coverage_visual_brief import (
    AXES,
    radar,
    coverage_fonts,
    amount,
    ribbon,
)
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from modules.consultation.coverage_signature import INSURERS
from pathlib import Path


def surgery_tier_rows(details):
    groups = {}
    for row in details:
        category = row.get("standard", "")
        if category not in ("질병종수술", "상해종수술"):
            continue
        name = unicodedata.normalize("NFKC", row["raw"])
        # A plan range such as 1~5종 does not identify the tier of this amount.
        name = re.sub(r"[1-9]\d*\s*종?\s*(?:[~∼～–—-]|부터|내지)\s*(?:제\s*)?[1-9]\d*\s*종", "", name)
        tiers = set(re.findall(r"(?<!\d)([1-5])\s*종(?!류)", name))
        if len(tiers) != 1 or not isinstance(row.get("value"), (float, int)):
            continue
        tier = int(tiers.pop())
        contracts = groups.setdefault(category, {}).setdefault(tier, {})
        contract = row["contract"]
        contracts[contract] = max(contracts.get(contract, 0), row["value"])
    return [(category[:2] + " · 종별 확인분", {tier: sum(values.values()) for tier, values in groups[category].items()})
            for category in ("질병종수술", "상해종수술") if category in groups]


def render_customer_brief(p):
    raw = p.get("kb", {})
    m = raw.get("matrix", {})
    cs = raw.get("contracts", p["contracts"])
    aliases = dict(AXES)
    aliases.update({"암수술비":"암수술","상해수술비":"상해수술","상해입원의료비":"상해입원(실손)","상해통원의료비":"상해통원(실손)","질병통원의료비":"질병통원(실손)","가족/일상/자녀배상":"일상생활배상책임"})
    workbook = {r["label"]:r for r in p["coverages"]}

    def val(k):
        if k in m:
            return amount(m[k]["total"])
        key = aliases.get(k,k) if k not in workbook else k
        row = workbook.get(key)
        if row and row.get("brief_unknown"):
            return None
        if row and all(isinstance(n, (int, float)) for n in row["values"]):
            return sum(row["values"])
        return None

    out = BytesIO()
    c = Canvas(out, pagesize=A4)
    c.setTitle(p["customer_name"] + "님의 보장 브리핑")
    W, H = A4
    f, b = coverage_fonts()
    N = "#17233C"
    S = "#58697A"
    G = "#977436"
    T = "#F6F1E8"
    B = "#EBF0F5"
    L = "#DAE0E5"

    def tx(x, y, v, size=11, font=None, col=N, right=False):
        c.setFont(font or f, size)
        c.setFillColor(col)
        (c.drawRightString if right else c.drawString)(x, H - y, v)

    def box(x, y, w, h, col):
        c.setFillColor(col)
        c.rect(x, H - y - h, w, h, fill=1, stroke=0)

    def rule(y):
        box(36, y, W - 72, 0.6, L)

    def start(title):
        n = c.getPageNumber()
        tx(36, 38, "HWARANG", 12, b)
        ribbon(c, 110, H - 38, 42, 10)
        tx(W - 36, 38, f"고객용 보장 브리핑   /   {n:02}", 10, b, right=True)
        rule(49)
        tx(36, 101, title, 23, b)
        rule(790)
        tx(
            36,
            810,
            p["customer_name"] + ("   ·   조회 기준 " + p["source_date"] if p.get("source_date") else "   ·   컨설팅 보장분석"),
            9,
            f,
            S,
        )
        tx(W - 36, 810, "화랑 WORKSPACE", 9, b, S, True)

    def section(y, title, low=False):
        box(36, y, W - 72, 30, B if low else T)
        box(36, y, 3, 30, N if low else G)
        tx(48, y + 20, title, 13, b)

    def tiles(y, items, shade=T):
        w = (W - 72) / len(items)
        for i, (k, v) in enumerate(items):
            x = 36 + i * w
            box(x, y, w - 4, 64, shade)
            tx(x + 12, y + 20, k, 10, f, S)
            tx(x + 12, y + 47, v, 17, b)

    def rows(y, items, step=31):
        for k, v in items:
            if isinstance(v, dict):
                draw_tiers(y, k, v)
                y += step
                continue
            tx(46, y, k, 11)
            tx(W - 45, y, v, 12, b, right=True)
            rule(y + 10)
            y += step

    tier_rows = surgery_tier_rows(p.get("details", []))

    def draw_tiers(y, label, amounts):
        tx(46, y, label, 10, b)
        for tier in range(1, 6):
            right = 175 + (tier - 1) * 90
            tx(right, y - 11, f"{tier}종", 8, f, S, right=True)
            value = amounts.get(tier)
            tx(right, y + 2, fmt(value) if value is not None else "—", 10, b, right=True)
        rule(y + 10)

    def bars(y, items, peak):
        for k, v in items:
            tx(45, y, k, 11, b)
            box(180, y - 8, 235, 7, B)
            if v:
                box(180, y - 8, 235 * v / peak, 7, "#536B83")
            tx(W - 44, y, fmt(v), 12, b, right=True)
            y += 34

    def fmt(v):
        if v is None:
            return "확인 필요"
        if not v:
            return "0원"
        if v % 1:
            return f"{v:,.2f}".rstrip("0").rstrip(".") + "만원"
        e, r = divmod(int(v), 10000)
        return (
            (f"{e}억 " if e else "") + (f"{r:,}만원" if r else "원")
            if r
            else f"{e}억원"
        )

    def pair(k):
        return (k, fmt(val(k)))

    start(p["customer_name"] + "님의 보장 현황")
    if not cs:
        tx(36, 150, "조회된 유지 계약 0건", 16, b)
        c.showPage()
        c.save()
        return out.getvalue()
    missing = sum(c0["premium_missing"] for c0 in cs)
    monthly = sum(
        c0["monthly"]
        for c0 in cs
        if c0.get("cycle", "월납") == "월납" and not c0["premium_missing"]
    )
    tx(
        36,
        133,
        (f"계약 {len(cs)}건   ·   월 보험료 미제공" if missing == len(cs) else f"계약 {len(cs)}건   ·   확인된 월 보험료 {monthly:,}원")
        + (f"   ·   월 보험료 {missing}건 미제공" if 0 < missing < len(cs) else ""),
        11,
        f,
        S,
    )
    entries = [
        (
            label,
            val(label) if label in m else val(key),
            (amount(raw.get("references", {}).get(label, "-")) if raw else (workbook.get(key, {}).get("reference") or 0)),
        )
        for label, key in AXES
    ]
    entries = [r for r in entries if r[1] is not None]
    if sum(r[2] > 0 for r in entries) >= 3:
        care_parts = [(key, val(key)) for key in ("간병인지원입원일-질병","질병간호간병통합입원일당")]
        care_parts = [v for _,v in care_parts if v is not None]
        shown_axis = {}
        if len(care_parts)==2 and any(care_parts) and sum(care_parts)==val("간병인/간호간병질병일당"):
            shown_axis["간병인/간호간병질병일당"] = ("간병인 / 통합 · 질병", " / ".join(fmt(v) for v in care_parts))
        renderPDF.draw(radar(entries, b, shown_axis), c, (W - 510) / 2, H - 635)
    else:
        rows(185, [(k, fmt(v)) for k, v, r in entries])
    c.showPage()
    start("암 진단과 치료")
    section(125, "내 암 진단비")
    tiles(161, [pair("일반암"), pair("유사암"), pair("고액암")])
    target = "고액(표적)항암치료비"
    section(245, "내 암 치료 담보")
    rows(300, [("암수술비 가입금액 합계", fmt(val("암수술비"))), (("고액 항암치료 담보 합계" if raw else "표적항암약물허가치료비"), fmt(val(target)))], 28)
    parts = [
        ("표적항암약물·특정표적방사선", "표적항암약물"),
        ("항암양성자방사선", "항암양성자"),
        ("항암중입자방사선", "항암중입자"),
    ]
    shown = []
    for label, word in parts:
        vs = [q["value"] for q in p["details"] if word in q["raw"]]
        if vs:
            shown.append((label, fmt(sum(vs))))
    matched = [q for q in p["details"] if any(word in q["raw"] for _,word in parts)]
    source_total = val(target)
    separate = shown and (not raw or any("고액항암치료비" not in q["standard"].replace(" ","") for q in matched) or source_total != sum(q["value"] for q in matched))
    if separate:
        tx(46, 359, "계약에서 확인된 치료 담보", 10, b)
    rows(380 if separate else 360, shown, 21)
    y = 384 + 21 * len(shown) + (20 if separate else 0)
    section(y, "대표 고액 항암제 투약 비용 사례", True)

    def drug(x, y, w, name, cost, source, url):
        box(x, y, w, 55, B)
        tx(x + 8, y + 13, name, 9, b)
        tx(x + 8, y + 32, cost, 12, b)
        tx(x + 8, y + 46, source, 8, f, S)
        c.linkURL(url, (x, H - y - 55, x + w, H - y))

    gov = "https://www.mohw.go.kr/upload/140/202203/1648726114403_20220331202834.pdf"
    tx(39, y + 46, "1회 · 반복 투여", 9, b, S)
    drug(
        36, y + 52, 193, "킴리아 · CAR-T", "1회 약 4억원", "보건복지부 2022년 사례", gov
    )
    drug(
        234,
        y + 52,
        325,
        "플루빅토 · 전립선암 방사성리간드",
        "1회 약 3,810만원  →  6회 약 2억 2,900만원",
        "분당서울대병원 비급여 약제비 · 동일 단가 6회 가정",
        "https://snubh.org/medical/out/clinic05_2.do?CG_CD=03&cPage=29",
    )
    tx(39, y + 123, "연간 투약", 9, b, S)
    for j, (nm, cost, year, url) in enumerate(
        [
            (
                "엔허투",
                "8,300",
                "2024",
                "https://go.seoul.co.kr/news/prnewsView.php?id=335588",
            ),
            ("로즐리트렉", "8,500", "2022", gov),
            ("비트락비", "8,800", "2022", gov),
        ]
    ):
        drug(
            36 + 175 * j,
            y + 129,
            171,
            nm,
            "연간 약 " + cost + "만원",
            "보건복지부 " + year + "년 사례",
            url,
        )
    c.showPage()
    start("뇌·심장 진단과 치료")
    y = 130
    section(y, "내 뇌·심장 진단비")
    items = [
        (k, val(k))
        for k in ["뇌혈관질환", "뇌졸중", "허혈성심장질환", "급성심근경색증"]
    ]
    bars(y + 59, items, max([1] + [v for _, v in items if v is not None]))
    related = []
    for rider in p["details"]:
        name = rider["raw"]
        if (any(term in name for term in ("순환계", "뇌혈관", "허혈성심장", "혈전", "관상동맥"))
                and any(term in name for term in ("치료", "수술", "시술", "삽입", "제거", "용해"))):
            related.append((name, fmt(rider["value"])))
    for label, key in (("질병수술비", "질병수술비"), ("질병 종수술비 · 종별 최대 합계", "질병종수술")):
        value = val(key)
        if value:
            related.append((label, fmt(value)))
    cursor = 323
    section(cursor, "치료 시 함께 확인할 담보")
    cursor += 47
    if not related:
        tx(46, cursor, "원본에서 확인된 관련 담보 없음", 10, f, S)
    for name, value in related:
        lines = [""]
        for char in name:
            if c.stringWidth(lines[-1] + char, f, 10) > 389:
                lines.append("")
            lines[-1] += char
        if cursor + 14 * len(lines) > 775:
            c.showPage()
            start("뇌·심장 진단과 치료 (계속)")
            section(132, "치료 시 함께 확인할 담보 (계속)")
            cursor = 181
        for j, line in enumerate(lines):
            tx(46, cursor + 14*j, line, 10)
        tx(W-45, cursor, value, 12, b, right=True)
        cursor += 14 * len(lines)
        rule(cursor-3)
        cursor += 12
    case_y = cursor + 23
    if case_y + 244 > 777:
        c.showPage()
        start("뇌·심장 진단과 치료 (계속)")
        case_y = 130
    section(case_y, "대표 뇌·심장 치료비 사례", True)
    cases = [
        ("뇌동맥류 · 2026년 병원급 기본 행위료", [("동맥류 색전술 (보조물 미사용)", "약 174만원"), ("비파열 단순 클립결찰술", "약 349만원")],
         "행위료만 산정 · 코일 등 재료비, 입원·검사비, 가산 제외", "https://www.law.go.kr/LSW/flDownload.do?flSeq=158265607"),
        ("관상동맥 · 2025년 건당 평균 진료비", [("스텐트 삽입 중재술", "약 1,404만원"), ("관상동맥우회수술", "약 4,329만원")],
         "국민건강보험공단 주요수술 통계연보 · 급여 진료비, 비급여 제외", "https://byeongwonbiyong.com/surgery/pci-stent/"),
    ]
    for index, (title, costs, source, url) in enumerate(cases):
        top = case_y + 53 + index * 106
        tx(40, top, title, 11, b)
        tiles(top + 8, costs, B)
        tx(40, top + 85, source, 9, f, S)
        c.linkURL(url, (36, H-top-90, 510, H-top-72))
    c.showPage()
    groups = []

    def add(title, items):
        if items:
            groups.append((title, items))

    def active(keys):
        return [(k, fmt(val(k))) for k in keys if val(k) not in (None, 0)]

    add("사망 보장", active(("상해사망", "질병사망")))

    def cover_rows(names):
        return [
            (r["display"], fmt(val(r["label"])))
            for r in p["coverages"]
            if "".join(r["group"].split()) in names
            and (val(r["label"]) is None or val(r["label"]) > 0)
        ]

    add("후유장해", cover_rows(("후유장해",)))
    add(
        "실손의료비 가입 한도",
        active(
            (
                "상해입원의료비",
                "질병입원의료비",
                "상해통원의료비",
                "질병통원의료비",
                "3대비급여실손",
            )
        ),
    )
    add("수술 보장", cover_rows(("수술",)) + tier_rows)
    daily = cover_rows(("입원", "간호간병", "치매·장기요양", "통원·응급"))
    if daily and val("질병입원일당") == 0:
        daily.insert(0, ("질병 입원일당", "0원"))
    add("입원과 돌봄", daily)
    add("운전자·생활 보장", cover_rows(("생활보장", "배상책임", "운전자")))
    standard = (
        len(cover_rows(("후유장해",))) <= 4
        and all(
            active(keys)
            for keys in (
                ("상해사망", "질병사망"),
                ("질병입원의료비", "상해입원의료비"),
                ("질병수술비", "상해수술비"),
            )
        )
        and len(cover_rows(("생활보장", "배상책임", "운전자"))) >= 3
        and not cover_rows(("간호간병", "치매·장기요양", "통원·응급"))
        and all(
            r[0].replace(" ", "") in ("암입원", "암입원일당")
            for r in cover_rows(("입원",))
        )
        and all(
            r[0].replace(" ", "")
            in (
                "질병수술",
                "상해수술",
                "암수술",
                "상해종수술(1~5종)",
                "질병종수술(1~5종)",
            )
            for r in cover_rows(("수술",))
        )
    )
    if standard:
        start("사망·장해와 실손의료비")
        section(135, "사망 원인별 가입금액")
        items = [(k, val(k)) for k in ("상해사망", "질병사망")]
        bars(215, items, max([1] + [v for _, v in items if v is not None]))
        tx(36, 327, "후유장해", 14, b)
        dis = [
            (r["display"], fmt(val(r["label"])))
            for r in p["coverages"]
            if "후유장해" in r["label"] and val(r["label"])
        ]
        rows(355, dis or [pair("상해80%미만후유장해"), pair("질병80%미만후유장해")], 28)
        section(480, "실손의료비 가입 한도", True)
        tiles(532, [pair("상해입원의료비"), pair("질병입원의료비")], B)
        rows(
            644,
            [pair(k) for k in ("상해통원의료비", "질병통원의료비", "3대비급여실손")],
        )
        c.showPage()
        start("수술·입원·돌봄과 생활 보장")
        section(133, "수술과 입원")
        rows(
            196,
            [
                (
                    "상해수술비  /  질병수술비",
                    fmt(val("상해수술비")) + "  /  " + fmt(val("질병수술비")),
                ),
                (
                    "종수술비 · 계약별 최대 합계 (상해 / 질병)",
                    fmt(val("상해종수술")) + "  /  " + fmt(val("질병종수술")),
                ),
                pair("암수술비"),
            ],
            36,
        )
        rows(306, tier_rows, 30)
        offset = 30 if len(tier_rows) == 2 else 0
        tx(36, 339 + offset, "하루 기준으로 보는 입원과 돌봄", 14, b)
        tiles(
            361 + offset,
            [
                pair("질병입원일당"),
                ("암 입원일당", fmt(val("암입원"))),
                ("질병 간병일당 · KB 집계", fmt(val("간병인/간호간병질병일당"))),
            ],
        )
        section(486, "생활 보장", True)
        life = [
            (r["display"], fmt(val(r["label"])))
            for r in p["coverages"]
            if "".join(r["group"].split()) in ("생활보장", "배상책임", "운전자")
            and val(r["label"])
        ]
        if not life:
            life = [pair("가족/일상/자녀배상"), pair("골절진단비")]
        for j in range(0, len(life), 7):
            if j:
                c.showPage()
                start("생활 보장")
                section(130, "가입금액", True)
            rows(548 if not j else 192, life[j : j + 7], 30)
        c.showPage()
    else:
        # Keep related topics together in typical portfolios. Pack short portfolios onto one page.
        count = sum(len(items) for _, items in groups)
        cursor = 800
        for title, items in groups:
            if cursor > 685 or (title == "수술 보장" and count > 15):
                if cursor != 800:
                    c.showPage()
                start("생활 속 주요 보장")
                cursor = 132
            while items:
                if cursor > 685:
                    c.showPage()
                    start("생활 속 주요 보장")
                    cursor = 132
                section(
                    cursor, title, title in ("실손의료비 가입 한도", "운전자·생활 보장")
                )
                cursor += 57
                take = min(len(items), max(1, int((758 - cursor) // 30) + 1))
                rows(cursor, items[:take], 30)
                cursor += take * 30 + 20
                items = items[take:]
                if items:
                    c.showPage()
                    start("생활 속 주요 보장")
                    cursor = 132
                    title = title.removesuffix(" (계속)") + " (계속)"
        if groups:
            c.showPage()

    def detail():
        start("계약별 암 담보")
        tx(36, 131, "회사 담보명", 10, f, S)
        tx(W - 36, 131, "가입금액", 10, f, S, True)
        rule(142)

    def header(y, contract):
        company = contract["company"]
        key = dict(INSURERS).get(
            {"KB손보": "KB손해보험", "KB라이프생명보험": "KB라이프생명"}.get(
                company, company
            )
        )
        lines = [""]
        for ch in contract["product"]:
            if c.stringWidth(lines[-1] + ch, b, 9.8) > 490:
                lines.append("")
            lines[-1] += ch
        h = 48 + 13 * (len(lines) - 1)
        box(36, y, W - 72, h, B)
        logo = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "insurer_logos"
            / f"{key}.png"
        )
        if key and logo.is_file():
            c.drawImage(str(logo), 45, H - y - 19, 10, 10, mask="auto")
        tx(60, y + 17, company, 10, b)
        for j, line in enumerate(lines):
            tx(45, y + 36 + j * 13, line, 9.8, b)
        return y + h

    def cancer_rider(row):
        import re
        name = re.sub(r"암\s*(?:을\s*)?제외", "", row["raw"])
        return "암" in name or "암" in row["standard"]
    if any(cancer_rider(r) for r in p["details"]):
        detail()
    y = 153
    for i, contract in enumerate(cs):
        rr = [
            r
            for r in p["details"]
            if r["contract"] == i and cancer_rider(r)
        ]
        if not rr:
            continue
        if y > 680:
            c.showPage()
            detail()
            y = 153
        y = header(y, contract)
        for r in rr:
            name = r["raw"]
            lines = [""]
            for ch in name:
                if c.stringWidth(lines[-1] + ch, f, 10) > 415:
                    lines.append("")
                lines[-1] += ch
            h = 16 + len(lines) * 13
            if y + h > 769:
                c.showPage()
                detail()
                y = header(153, contract)
            for j, line in enumerate(lines):
                tx(44, y + 18 + j * 13, line, 10)
            tx(W - 43, y + 18, fmt(r["value"]), 10, b, right=True)
            y += h
            rule(y)
        y += 13
    c.save()
    return out.getvalue()
