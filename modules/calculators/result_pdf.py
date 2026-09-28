from modules.shared.pdf_brand import draw_brand
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


def build_result_pdf(name, inputs, result, stamp, *, include_results=True, include_inputs=True, include_basis=True, enlarge_results=False):
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
        large = highlight and enlarge_results
        label_style = ParagraphStyle('ResultLabel', parent=body, fontSize=13 if large else 9, leading=20 if large else 14)
        data=[[p(a,label_style),p(b,ParagraphStyle('Value',parent=body,fontSize=20 if large else (12 if highlight else 9),leading=29 if large else (18 if highlight else 14)))] for a,b in rows]
        if not data:return
        t=Table(data,colWidths=[width*.43,width*.57],hAlign='LEFT',repeatRows=0)
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#edf4f9') if highlight else colors.white),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.HexColor('#edf4f9'),colors.HexColor('#f4f8fb')] if highlight else [colors.white,colors.HexColor('#f7f9fc')]),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dce5ef')),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),24 if large else 10),('BOTTOMPADDING',(0,0),(-1,-1),24 if large else 10)]))
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
        draw_brand(canvas, doc.page)
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return buf.getvalue()


def pdf_section_options(key):
    import streamlit as st
    st.caption('PDF에 포함할 내용')
    columns = st.columns([1, 1, 1.65], gap='small')
    options = {}
    for column, field, label in zip(columns,
            ('include_results', 'include_inputs', 'include_basis'),
            ('핵심 결과', '입력 내용', '산출 근거 및 적용 조건')):
        with column:
            options[field] = st.checkbox(label, value=True, key=key+'_sections_v2_'+field)
    if not any(options.values()):
        st.info('PDF에 포함할 항목을 하나 이상 선택해주세요.')
    enlarged = st.checkbox('핵심 결과 크게 표시', value=False, disabled=not options['include_results'], key=key+'_enlarge_results', help='체크하면 핵심 결과의 글자와 행 간격을 확대합니다. 입력 내용과 산출 근거는 기존 크기를 유지합니다.')
    options['enlarge_results'] = enlarged and options['include_results']
    return options
