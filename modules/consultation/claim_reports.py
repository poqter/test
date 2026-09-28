"""Customer-facing output for the reviewed claim model, independent of the UI."""
from datetime import date
from html import escape
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from modules.shared.pdf_brand import draw_brand


def build_customer_pdf(claims, documents, *, name='', note='', accident='', coverages=()):
    from .insurance_claim_guide import _register_korean_font
    font = _register_korean_font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=22*mm, bottomMargin=18*mm,
                            title='보험금 청구 안내', author='화랑 WORKSPACE')
    body = ParagraphStyle('body', fontName=font, fontSize=9, leading=13, wordWrap='CJK')
    title = ParagraphStyle('title', parent=body, fontSize=18, leading=24, spaceAfter=12)
    heading = ParagraphStyle('heading', parent=body, fontSize=11, leading=16, spaceBefore=10, spaceAfter=7)
    def p(text, style=body):
        return Paragraph(escape(str(text)).replace('\n','<br/>'), style)
    def table(headers, rows, widths):
        data = [[p(x) for x in headers]] + [[p(x) for x in row] for row in rows]
        t = Table(data, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF2F6')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#D4DEE7')),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        return t
    story = [p('보험금 청구 안내',title),p((name+'님 · ' if name else '')+date.today().isoformat()),
             p('청구 내용: '+' · '.join(claims)),Spacer(1,10)]
    selected = [d for d in documents if d['include']]
    if selected:
        story.append(table(['발급·준비','서류','확인할 내용'],
            [('병원' if d['group']=='병원 발급' else '별도 준비',d['name'],d['required_info']) for d in selected],
            [24*mm,53*mm,103*mm]))
    else:
        story.append(p('안내할 서류가 선택되지 않았습니다.'))
    for label, text in [('추가 안내',note),('사고경위',accident)]:
        if text.strip(): story.extend([p(label,heading),p(text)])
    story.extend([Spacer(1,10),p('보험회사·가입 담보에 따라 서류가 추가되거나 달라질 수 있습니다. 발급비용이 큰 서류는 발급 전에 보험회사에 확인해 주세요.')])
    chosen = [c for c in coverages if c.get('포함')]
    if chosen:
        story.extend([PageBreak(),p('함께 확인할 가입 담보',title),
            p('가입금액은 예상 지급액이 아닙니다. 실제 지급 여부와 금액은 약관 및 심사 결과에 따라 달라집니다.'),Spacer(1,10),
            table(['보험회사·상품','담보','가입금액','확인할 내용'],
                [(r.get('보험회사','')+'\n'+r.get('상품명',''), r.get('관련 담보',''),r.get('가입금액',''),r.get('확인사항','')) for r in chosen],
                [48*mm,57*mm,24*mm,51*mm])])
    doc.build(story,onFirstPage=lambda c,d:draw_brand(c,d.page),onLaterPages=lambda c,d:draw_brand(c,d.page))
    return buffer.getvalue()
