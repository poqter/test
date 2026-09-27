"""Branded, paginated calculation snapshots. No calculation or rounding changes."""
from io import BytesIO
from pathlib import Path
from html import escape
from decimal import Decimal
import re
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def value_text(value):
    if value is None: return '미적용'
    if isinstance(value, bool): return '예' if value else '아니오'
    if isinstance(value, (int, float, Decimal)): return format(value, ',')
    if isinstance(value, str) and re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        return format(Decimal(value), ',')
    return str(value)


def build_result_pdf(name, inputs, result, stamp, *, include_results=True, include_inputs=True, include_basis=True):
    if not any((include_results, include_inputs, include_basis)):
        raise ValueError("PDF에 포함할 항목을 하나 이상 선택해주세요.")
    font = 'HwarangReport'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(__file__).resolve().parents[2] / 'assets/fonts/PretendardVariable.ttf')))
    navy, teal = colors.HexColor('#112b49'), colors.HexColor('#158391')
    body = ParagraphStyle('Body',fontName=font,fontSize=9,leading=14,textColor=navy,wordWrap='CJK')
    heading = ParagraphStyle('Heading',parent=body,fontSize=13,leading=19,spaceBefore=17,spaceAfter=9,keepWithNext=True)
    def p(value, style=body):
        return Paragraph(escape(value_text(value)).replace('\n','<br/>'),style)
    try:
        from datetime import datetime
        stamp = datetime.fromisoformat(str(stamp)).strftime('%Y-%m-%d %H:%M')
    except ValueError:
        pass
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=20*mm,leftMargin=20*mm,topMargin=27*mm,bottomMargin=22*mm,title=name+' 결과 보고서',author='화랑 WORKSPACE')
    width=A4[0]-40*mm
    story=[p('CALCULATION REPORT',ParagraphStyle('Kicker',parent=body,textColor=teal,fontSize=9)),Spacer(1,7),p(name,ParagraphStyle('Title',parent=body,fontSize=23,leading=31)),Spacer(1,8),p('계산 시각  '+str(stamp)),Spacer(1,14)]
    def table(rows, highlight=False):
        data=[[p(a),p(b,ParagraphStyle('Value',parent=body,fontSize=12 if highlight else 9,leading=18 if highlight else 14))] for a,b in rows]
        if not data:return
        t=Table(data,colWidths=[width*.43,width*.57],hAlign='LEFT',repeatRows=0)
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#edf4f9') if highlight else colors.white),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.HexColor('#edf4f9'),colors.HexColor('#f4f8fb')] if highlight else [colors.white,colors.HexColor('#f7f9fc')]),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dce5ef')),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        story.append(t)
    section = 0
    def section_heading(title):
        nonlocal section
        section += 1
        story.append(p(f'{section:02d}  {title}',heading))
    if include_results:
        section_heading('핵심 결과');table(list(result.display().items()),True)
    if include_inputs:
        section_heading('계산에 사용한 입력');table(inputs)
    if include_basis:
        section_heading('산출 근거 및 적용 조건')
        story.append(p(result.formula));story.append(Spacer(1,9))
        for note in result.assumptions:
            story.append(p('• '+str(note)));story.append(Spacer(1,5))
    def page(canvas, doc):
        canvas.saveState();w,h=A4
        canvas.setFillColor(navy);canvas.rect(0,h-13*mm,w,13*mm,fill=1,stroke=0)
        canvas.setFillColor(colors.white);canvas.setFont(font,9);canvas.drawString(20*mm,h-8.5*mm,'H  |  화랑 WORKSPACE')
        canvas.setStrokeColor(colors.HexColor('#dce5ef'));canvas.line(20*mm,17*mm,w-20*mm,17*mm)
        canvas.setFont(font,8);canvas.setFillColor(colors.HexColor('#62758a'));canvas.drawString(20*mm,11*mm,'화랑 WORKSPACE');canvas.drawRightString(w-20*mm,11*mm,str(doc.page))
        canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return buf.getvalue()


def pdf_section_options(key):
    import streamlit as st
    st.caption('PDF에 포함할 내용')
    options = {
        'include_results': st.checkbox('핵심 결과', value=True, key=key+'_results'),
        'include_inputs': st.checkbox('입력 내용', value=False, key=key+'_inputs'),
        'include_basis': st.checkbox('산출 근거 및 적용 조건', value=False, key=key+'_basis'),
    }
    if not any(options.values()):
        st.info('PDF에 포함할 항목을 하나 이상 선택해주세요.')
    return options
