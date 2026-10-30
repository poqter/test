"""Current-insurance briefing derived from the existing analyzer, without new assumptions."""
from __future__ import annotations
from io import BytesIO
from html import escape
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import ParagraphStyle
from pypdf import PdfReader, PdfWriter
from modules.shared.report_fonts import korean_pdf_font, pdf_text
from modules.consultation.coverage_comparison_data import format_coverage, format_won
from modules.consultation.analyzer_model import _is_fully_paid

NAVY=colors.HexColor('#142A4B'); BLUE=colors.HexColor('#325FAD'); TEAL=colors.HexColor('#12847C')
TEXT=colors.HexColor('#233752'); MUTED=colors.HexColor('#64758C'); LINE=colors.HexColor('#DCE5F0')
BG=colors.HexColor('#F3F6FA'); LIGHT=colors.HexColor('#EAF2FC')

# Only exact, explicitly named coverage items may be aggregated. Narrower diagnoses
# and amounts with different units or conditions are never substituted.
EXACT = {
    '일반암': ('일반암','일반암진단비'),
    '유사암': ('유사암','유사암진단비'),
    '뇌혈관질환': ('뇌혈관','뇌혈관질환','뇌혈관질환진단비'),
    '허혈성심장질환': ('허혈성심장질환','허혈성심장질환진단비'),
    '질병사망': ('질병사망',),
    '재해·상해사망': ('재해(상해)사망',),
    '질병수술': ('질병수술',),
    '상해수술': ('상해수술',),
    '질병입원': ('질병입원','질병입원일당'),
    '상해입원': ('상해입원','상해입원일당'),
    '질병 실손 입원': ('질병입원(실손)',),
    '상해 실손 입원': ('상해입원(실손)',),
    '일상생활배상책임': ('일상생활배상책임',),
}

def _norm(x): return re.sub(r'\s+', '', str(x or ''))
def _positive(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and v>0

def _row_values(parsed, label):
    wanted=set(EXACT.get(label,(label,)))
    matches=[r for r in parsed.get('coverages',[]) if _norm(r.get('label')) in wanted]
    if len(matches)!=1: return None
    vals=matches[0].get('values',[])
    return [v for v in vals if _positive(v)]

def _metric(parsed, label):
    values=_row_values(parsed,label)
    if not values:return '확인 필요'
    # Indemnity coverages are not additive. Keep each contract in the detail.
    if '실손' in label:return '계약별 확인'
    return format_coverage(sum(values))

def _premium(parsed):
    items=parsed.get('contracts',[]); vals=[]
    for c in items:
        n=c.get('monthly')
        # Original premium can remain populated after payment completion; the
        # worksheet does not establish the current charge for that contract.
        if _is_fully_paid(c.get('payment_count')): return None
        if _positive(n): vals.append(n)
        else:return None
    return sum(vals) if vals else None

def _clip(c, text, width, font, size):
    text=pdf_text(str(text));
    if c.stringWidth(text,font,size)<=width:return text
    while text and c.stringWidth(text+'…',font,size)>width:text=text[:-1]
    return text+'…'

def _line(c,text,x,y,font,size,color=TEXT,width=None):
    c.setFont(font,size); c.setFillColor(color)
    c.drawString(x,y,_clip(c,text,width,font,size) if width else pdf_text(str(text)))

def _round(c,x,y,w,h,fill,r=9,stroke=None):
    c.setFillColor(fill);c.setStrokeColor(stroke or fill);c.roundRect(x,y,w,h,r,stroke=bool(stroke),fill=1)

def _staff(profile):
    p=profile or {}
    return '  '.join(str(p.get(k) or '').strip() for k in ('organization_name','position_name','display_name') if p.get(k))

def _page_one(parsed, profile):
    out=BytesIO(); c=canvas.Canvas(out,pagesize=A4); w,h=A4; f=korean_pdf_font(); x=35; inner=w-70
    c.setTitle('현재 보험 보장 브리핑');c.setFillColor(colors.white);c.rect(0,0,w,h,fill=1,stroke=0)
    _round(c,x,h-123,inner,91,NAVY,11)
    _line(c,'HWARANG WORKSPACE  /  고객 보장 브리핑',x+16,h-53,f,8,colors.HexColor('#B8D1F3'))
    _line(c,f"{parsed.get('customer_name') or '고객'} 님의 현재 보장",x+16,h-79,f,19,colors.white,inner-32)
    _line(c,'가입하신 보험을 함께 살펴보는 한 장 요약',x+16,h-101,f,9,colors.HexColor('#D4E4F7'))
    y=h-182; gap=8; cw=(inner-gap*2)/3
    for i,(label,val) in enumerate([('가입 보험',f"{len(parsed.get('contracts',[]))}건"),('월 보험료',format_won(_premium(parsed))),('자료 기준','보장분석 엑셀')]):
        xx=x+i*(cw+gap);_round(c,xx,y,cw,48,BG,8);_line(c,label,xx+11,y+30,f,8,MUTED);_line(c,val,xx+11,y+12,f,13,NAVY,cw-22)
    _line(c,'01  핵심 진단비',x,h-210,f,12,NAVY)
    _line(c,'기재 금액 합계 / 막대는 세 항목 중 최대 금액 대비',x+125,h-210,f,8,MUTED)
    top=h-286; cardw=(inner-16)/3
    keys=[('일반암','암 진단'),('뇌혈관질환','뇌 진단'),('허혈성심장질환','심장 진단')]
    amounts=[sum(_row_values(parsed,label) or []) for label,_ in keys]
    scale=max(amounts or [0])
    for i,(label,sub) in enumerate(keys):
        xx=x+i*(cardw+8);_round(c,xx,top,cardw,62,LIGHT,8)
        _line(c,sub,xx+10,top+46,f,8,BLUE);_line(c,label,xx+10,top+31,f,9,TEXT,cardw-20);_line(c,_metric(parsed,label),xx+10,top+15,f,12,NAVY,cardw-20)
        _round(c,xx+10,top+5,cardw-20,3,colors.HexColor('#CEDCEF'),1)
        if scale and amounts[i]:_round(c,xx+10,top+5,(cardw-20)*amounts[i]/scale,3,BLUE,1)
    _line(c,'02  영역별 보장 살펴보기',x,h-311,f,12,NAVY)
    _line(c,'기재 금액을 보여주며 보장 여부를 단정하지 않습니다',x+171,h-311,f,8,MUTED)
    rows=[('암','유사암',_metric(parsed,'유사암')),('뇌','뇌혈관질환',_metric(parsed,'뇌혈관질환')),('심장','허혈성심장질환',_metric(parsed,'허혈성심장질환')),('사망','질병사망',_metric(parsed,'질병사망')),('수술','질병수술',_metric(parsed,'질병수술')),('입원','질병입원',_metric(parsed,'질병입원')),('실손','질병 실손 입원',_metric(parsed,'질병 실손 입원')),('배상','일상생활배상책임',_metric(parsed,'일상생활배상책임'))]
    for i,(area,label,value) in enumerate(rows):
        yy=h-340-i*28; c.setStrokeColor(LINE);c.line(x,yy-9,w-x,yy-9)
        _round(c,x,yy-3,40,18,LIGHT,7);_line(c,area,x+8,yy+2,f,8,BLUE,30)
        _line(c,label,x+54,yy+2,f,9,TEXT,175)
        c.setFont(f,9);c.setFillColor(TEAL if value not in ('확인 필요','계약별 확인') else MUTED);c.drawRightString(w-x-5,yy+2,pdf_text(value))
    bottom=h-602
    _round(c,x,bottom,inner,48,BG,8)
    missing=[name for name,_ in keys if _metric(parsed,name)=='확인 필요']
    note=('금액 확인 필요: '+', '.join(missing)) if missing else '주요 진단비의 보장 범위와 지급 조건을 함께 확인해 주세요.'
    _line(c,'함께 확인할 내용',x+11,bottom+29,f,9,NAVY)
    _line(c,note,x+11,bottom+12,f,8,MUTED,inner-22)
    _line(c,'03  가입 보험',x,214,f,11,NAVY)
    contracts=parsed.get('contracts',[])
    for i,p in enumerate(contracts[:3]):
        if i==2 and len(contracts)>3:
            _line(c,f'외 {len(contracts)-2}건  /  자세한 브리핑에서 확인',x+4,165,f,8,MUTED,inner)
            break
        title=f"{p.get('company') or '보험사 미기재'}  /  {p.get('product') or '상품명 미기재'}"
        _line(c,f'{i+1:02d}  {title}',x+4,196-i*15,f,8,TEXT,inner)
    _line(c,'기재된 금액의 단순 합계이며 지급조건이 다르면 실제 지급액은 달라질 수 있습니다.',x,100,f,8,MUTED,inner)
    _line(c,'실손은 합산하지 않습니다. 공란과 0원은 미가입을 의미하지 않습니다.',x,86,f,8,MUTED,inner)
    _line(c,'실제 보장과 지급은 각 계약의 약관 및 심사에 따릅니다.',x,72,f,8,MUTED,inner)
    _line(c,_staff(profile) or '화랑 WORKSPACE',x,48,f,8,BLUE,inner-60)
    c.setFont(f,8);c.setFillColor(MUTED);c.drawRightString(w-x,48,'1')
    c.showPage();c.save();return out.getvalue()

def _paragraph(v,style):return Paragraph(escape(pdf_text(str(v or '확인 필요'))).replace('\n','<br/>'),style)

def _detail(parsed):
    out=BytesIO(); f=korean_pdf_font(); body=ParagraphStyle('body',fontName=f,fontSize=8.7,leading=14,wordWrap='CJK',textColor=TEXT)
    head=ParagraphStyle('head',parent=body,fontSize=13,leading=19,spaceBefore=13,spaceAfter=7,textColor=NAVY,keepWithNext=True)
    title=ParagraphStyle('title',parent=head,fontSize=18,leading=25,spaceAfter=8)
    small=ParagraphStyle('small',parent=body,fontSize=8,leading=12,textColor=MUTED)
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=35,rightMargin=35,topMargin=37,bottomMargin=42)
    story=[_paragraph('현재 보험 자세히 보기',title),_paragraph('계약별 내용과 보장분석표에 기재된 금액을 정리했습니다.',small),Spacer(1,8)]
    headers=['번호','보험사 / 상품명','보장기간','납입횟수','월 보험료']
    rows=[[_paragraph(x,body) for x in headers]]
    contracts=parsed.get('contracts',[])
    for i,p in enumerate(contracts):
        premium=('납입완료 / 확인 필요' if _is_fully_paid(p.get('payment_count')) else format_won(p.get('monthly') if _positive(p.get('monthly')) else None))
        rows.append([_paragraph(str(i+1),body),_paragraph(f"{p.get('company') or '보험사 미기재'}\n{p.get('product') or '상품명 미기재'}",body),_paragraph(p.get('coverage_period'),body),_paragraph(p.get('payment_count'),body),_paragraph(premium,body)])
    table=Table(rows,colWidths=[32,195,80,90,128],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,BG]),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,LINE)]));story.append(table)
    story.append(_paragraph('보장의 역할을 이해해요',head))
    explanations=[('진단비','해당 질환을 진단받았을 때 약관의 지급 조건에 따라 지급하는 보장입니다.'),('치료·수술·입원','실제 치료나 수술, 입원 등 정해진 조건과 지급 횟수를 확인합니다.'),('실손의료비','의료비 부담에 대한 보장입니다. 여러 계약이 있어도 금액을 단순히 더하지 않습니다.')]
    explanation_table=Table([[_paragraph(a,body),_paragraph(b,body)] for a,b in explanations],colWidths=[120,405],hAlign='LEFT')
    explanation_table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BG),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-2),.4,LINE)]));story.append(explanation_table)
    story.append(_paragraph('보장별 기재 내역',head));story.append(_paragraph('번호는 위의 보험 계약과 같습니다. 금액은 각 계약의 보장금액이며, 지급 범위와 횟수는 원본 약관에서 확인합니다.',small));story.append(Spacer(1,8))
    rows=[[_paragraph('보장항목',body),_paragraph('보험별 기재 금액',body)]]
    for r in parsed.get('coverages',[]):
        vals=[f"{i+1}번  {format_coverage(v)}" for i,v in enumerate(r.get('values',[])) if _positive(v)]
        if vals:rows.append([_paragraph(r.get('display') or r.get('label'),body),_paragraph('  /  '.join(vals),body)])
    if len(rows)==1:rows.append([_paragraph('보장 내역',body),_paragraph('기재 금액 확인 필요',body)])
    table=Table(rows,colWidths=[200,325],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,BG]),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,LINE)]));story.append(table)
    story.extend([Spacer(1,12),_paragraph('보험료나 보장 내역이 비어 있는 계약은 원본 확인이 필요합니다. 실손은 계약별로 표시하며 합산하지 않습니다.',small)])
    def footer(c,d):
        c.setFont(f,8);c.setFillColor(MUTED);c.drawRightString(A4[0]-35,22,str(d.page+1))
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return out.getvalue()

def current_brief_pdf(parsed, profile=None, detailed=False):
    first=_page_one(parsed,profile)
    if not detailed:return first
    writer=PdfWriter()
    for raw in (first,_detail(parsed)):
        for page in PdfReader(BytesIO(raw)).pages:writer.add_page(page)
    out=BytesIO();writer.write(out);return out.getvalue()
