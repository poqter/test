"""Paired columns with a repeated legend for the coverage status section."""
from collections import Counter
from reportlab.platypus import PageBreak, Table, TableStyle, Spacer

STATUSES = [
    ("○", "기준 충족", "#35658A"), ("△", "기준 미만", "#946717"),
    ("×", "가입금액 0원", "#AA4545"), ("?", "확인 필요", "#505B68"),
    ("—", "기준 미설정", "#737B85"),
]

def add_overview(story, comparison, limits, heading, para, width):
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
        rows.append([para(name,9), money(limit) if limit else "—",
                     money(amount) if amount is not None else "확인 필요", para(mark,13,color)])
    for offset in range(0,len(rows),38):
        story.append(PageBreak())
        heading("전체 보장 현황")
        legend = [para(mark+" "+name+" "+str(counts[i])+"개",9,color) for i,(mark,name,color) in enumerate(STATUSES)]
        story.extend([Table([legend],colWidths=[width/5]*5),Spacer(1,8),para("단위  만원",9),Spacer(1,4)])
        chunk = rows[offset:offset+38]
        mid = (len(chunk)+1)//2
        header = [para(t,8,"#FFFFFF") for t in ("보장 항목","기준금액","가입금액","결과")]
        def side(data):
            body = [[r[0],para(r[1],9),para(r[2],9),r[3]] for r in data]
            return Table([header]+body,colWidths=[width*x for x in (.218,.093,.111,.064)],style=TableStyle([
                ("BACKGROUND",(0,0),(-1,0),"#17233C"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("LINEBELOW",(0,1),(-1,-1),.35,"#E3E6EA"),
                ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),2),
                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story.append(Table([[side(chunk[:mid]),"",side(chunk[mid:])]],colWidths=[width*.486,width*.028,width*.486],
                           style=[("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
