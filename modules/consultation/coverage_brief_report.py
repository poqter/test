"""Client briefing PDFs using local, embedded fonts and verified display values."""
from io import BytesIO
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Flowable
from modules.shared.report_fonts import korean_pdf_font, pdf_text
from modules.consultation.coverage_comparison_data import format_won, format_coverage, METRICS

NAVY=colors.HexColor('#162C4D'); BLUE=colors.HexColor('#315FC0'); PALE=colors.HexColor('#EFF4FB')

def P(s, style):return Paragraph(escape(pdf_text(s)).replace('\n','<br/>'),style)

class Bars(Flowable):
    def __init__(self, items, fmt, font, recommended=""):
        super().__init__(); self.items=items; self.fmt=fmt; self.font=font
        self.recommended=recommended; self.width=520; self.height=26*len(items)+8
    def draw(self):
        c=self.canv; valid=[v for _,v in self.items if isinstance(v,(int,float)) and v>=0]
        scale=max(valid or [1]) or 1
        for i,(name,val) in enumerate(self.items):
            y=self.height-22-i*26
            c.setFont(self.font,8.5);c.setFillColor(NAVY);c.drawString(0,y,pdf_text(name)[:19])
            c.setFillColor(PALE);c.roundRect(135,y,225,8,4,stroke=0,fill=1)
            if isinstance(val,(int,float)) and val>0:
                c.setFillColor(colors.HexColor('#07817C') if name==self.recommended else BLUE);c.roundRect(135,y,225*val/scale,8,4,stroke=0,fill=1)
            c.setFillColor(NAVY);c.drawRightString(515,y,pdf_text(self.fmt(val)))


def create_pdf(title, subtitle, sections):
    font=korean_pdf_font(); out=BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=35,leftMargin=35,topMargin=42,bottomMargin=42)
    body=ParagraphStyle('body',fontName=font,fontSize=9.3,leading=15,textColor=NAVY,wordWrap='CJK')
    title_style=ParagraphStyle('title',parent=body,fontSize=20,leading=26,spaceAfter=9)
    small=ParagraphStyle('small',parent=body,fontSize=8,leading=12,textColor=colors.HexColor('#65768A'))
    head=ParagraphStyle('head',parent=body,fontSize=12,leading=18,spaceBefore=7,spaceAfter=5,keepWithNext=True)
    cell=ParagraphStyle('cell',parent=body,fontSize=8.3,leading=12)
    white=ParagraphStyle('white',parent=cell,textColor=colors.white)
    story=[P('HWARANG WORKSPACE  /  고객 상담 자료',small),Spacer(1,8),P(title,title_style),P(subtitle,small),Spacer(1,14)]
    for heading, kind, content in sections:
        story.append(P(heading,head))
        if kind=='text':
            story.append(P(content,body));story.append(Spacer(1,8))
        elif kind=='bars':
            story.append(Bars(content['items'], content['format'], font, content.get('recommended','')));story.append(Spacer(1,8))
        elif kind=='table':
            cols=content['headers']; values=content['rows']; width=content.get('widths')
            table=Table([[P(x,white) for x in cols]]+[[P(str(x),cell) for x in row] for row in values],colWidths=width,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#DCE4ED'))]))
            story.append(table);story.append(Spacer(1,8))
    story.extend([Spacer(1,12),P('첨부 자료와 입력 내용을 바탕으로 정리했습니다. 실제 지급은 각 계약의 보장 범위와 약관, 심사 및 지급 조건에 따릅니다. 기재되지 않은 내용은 확인이 필요합니다.',small)])
    def page(c,d):
        c.setFillColor(NAVY);c.rect(0,A4[1]-7,A4[0],7,stroke=0,fill=1)
        c.setFont(font,8);c.setFillColor(colors.HexColor('#718195'));c.drawRightString(A4[0]-35,22,str(d.page))
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return out.getvalue()

def briefing_pdf(parsed):
    contracts=parsed['contracts']; coverages=parsed['coverages']
    policies=[[str(c.get('company') or '확인 필요'),str(c.get('product') or '확인 필요'),str(c.get('coverage_period') or '확인 필요'),format_won(c.get('monthly'))] for c in contracts]
    coverage=[]
    for row in coverages:
        vals=row.get('values',[])
        # The established analyzer parser maps blanks to 0; do not infer absence.
        present=[v for v in vals if isinstance(v,(int,float)) and v>0]
        if present:
            coverage.append([str(row.get('display') or row.get('label')), ' / '.join(format_coverage(v) for v in present[:5]), '세부 조건 확인'])
    sections=[('월 보험료','bars',{'items':[(str(c.get('company') or '확인 필요'),c.get('monthly') if c.get('monthly') else None) for c in contracts], 'format':format_won}), ('가입 보험','table',{'headers':['보험사','상품','보장기간','월 보험료'],'rows':policies,'widths':[80,180,100,160]}),
      ('주요 보장 내용','table',{'headers':['보장','계약별 기재 금액','안내'],'rows':coverage[:32] or [['기재된 보장 없음','확인 필요','원본 확인']], 'widths':[160,230,130]}),
      ('상담 시 확인','text','특약에 따라 보장 범위, 지급 횟수와 조건이 다릅니다. 공란이나 0원은 자료만으로 미가입이라고 단정하지 않습니다.')]
    return create_pdf('현재 보험 보장 브리핑',f"{parsed.get('customer_name','고객')}님 | 첨부한 보장분석 엑셀 기준",sections)

def comparison_pdf(current,plans,recommended,reason,caution):
    sections=[('추천 제안','text',f'{recommended or "추천안 미선택"}\n{reason or "추천 이유를 입력해 주세요."}')]
    for start in range(0,len(plans),4):
        batch=plans[start:start+4]
        suffix=f' ({start+1}~{start+len(batch)})' if len(plans)>4 else ''
        for title,key,fmt in [('월 보험료 비교','premium',format_won),('뇌혈관질환 진단금','뇌혈관질환',format_coverage),('허혈성심장질환 진단금','허혈성심장질환',format_coverage)]:
            sections.append((title+suffix,'bars',{'items':[(current['name'],current.get(key))]+[(p['name'],p.get(key)) for p in batch],'format':fmt,'recommended':recommended}))
        headers=['항목','현재 보장']+[p['name'] for p in batch]
        rows=[['월 보험료',format_won(current.get('premium'))]+[format_won(p.get('premium')) for p in batch]]
        for metric in METRICS:
            rows.append([metric,format_coverage(current.get(metric))]+[format_coverage(p.get(metric)) for p in batch])
        sections.append(('현재 보험과 제안 비교'+suffix,'table',{'headers':headers,'rows':rows,'widths':[100]+[420/(len(headers)-1)]*(len(headers)-1)}))
    sections.extend([('치료·수술·간병 및 기타 보장','table',{'headers':['구분','확인한 보장 내용'],'rows':[['현재',current.get('notes') or '확인 필요']]+[[p['name'],p.get('notes') or '확인 필요'] for p in plans],'widths':[120,400]}),
       ('변경 전 함께 확인','text',caution or '기존 계약의 해지환급금, 납입기간, 새 계약 인수와 면책·감액, 줄어드는 보장을 확인해 주세요.')])
    return create_pdf('보험 보장비교 제안 보고서','현재 유지 보험과 제안한 보험을 비교합니다.',sections)
