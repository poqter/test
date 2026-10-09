"""Allowlisted customer/staff projections and portable readers. No AI calls."""
from __future__ import annotations
import html,json
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import lru_cache
from .normalize import is_safe_url

METRIC_FIELDS=('code','label','value','unit','change','change_percent','observed_at','previous_observed_at','source_name','source_url','observation_kind','reference_definition','as_of_precision')

def display_date(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y.%m.%d %H:%M KST')
    except (ValueError,TypeError):return str(value or '기준일 미확인')

def metric_date(row):
    return str(row.get('observed_at') or '')[:10]+' 관측일' if row.get('as_of_precision')=='date' else display_date(row.get('observed_at'))

def metric_change(row):
    delta=row.get('change')
    if delta is None:return '이전 관측값 미확인'
    if row.get('code')=='US10Y':return f'{delta:+.2f} %p'
    if row.get('code')=='USDKRW':return f'{delta:+.2f} 원'
    return f"{row['change_percent']:+.2f}%" if row.get('change_percent') is not None else f'{delta:+.2f} pt'

def _project(content,external):
    issues=[]
    for row in content.get('issues',[]):
        if external and content.get('profile_code')=='INSURANCE' and (row.get('communication_state')!='customer_ready' or row.get('category') in {'영업·채널','보험사·시장'}):continue
        sources=[{k:r.get(k) for k in ('title','source_name','url','published_at')} for r in row.get('sources',[]) if is_safe_url(str(r.get('url') or '')) and r.get('published_at')][:4]
        if sources:issues.append({k:row.get(k) for k in ('event_key','title','summary','category','why_important','impact_summary','representative')}|{'sources':sources})
    metrics=content.get('market_metrics') or {};rows=metrics.get('items',[]) if isinstance(metrics,dict) else metrics
    metrics=[{k:r.get(k) for k in METRIC_FIELDS} for r in rows if r.get('value') is not None and is_safe_url(str(r.get('source_url') or '')) and (not external or r.get('external_allowed'))]
    research=content.get('research') or {}
    def views(rows):return [{k:v.get(k) for k in ('firm','url','stance','summary','conditions')} for v in rows if isinstance(v,dict) and is_safe_url(str(v.get('url') or ''))]
    safe={k:research.get(k) for k in ('status','report_count','institution_count','note')}
    safe['reports']=[{k:r.get(k) for k in ('firm','title','url','published_at')} for r in research.get('reports') or [] if is_safe_url(str(r.get('url') or ''))]
    safe['common']=[{k:r.get(k) for k in ('theme','timeframe','stance','firms')}|{'views':views(r.get('views') or [])} for r in research.get('common') or []]
    safe['differences']=[{k:r.get(k) for k in ('theme','timeframe')}|{'positive':views(r.get('positive') or []),'cautious':views(r.get('cautious') or [])} for r in research.get('differences') or []]
    safe['viewpoints']=[{k:r.get(k) for k in ('theme','timeframe')}|{'views':views(r.get('views') or [])} for r in research.get('viewpoints') or []]
    return {'schema':'hwarang-public-v2','profile_code':content.get('profile_code'),'profile_label':content.get('profile_label'),'as_of':content.get('as_of'),'issues':issues,'market_flow':[str(x) for x in content.get('market_flow',[])],'market_metrics':metrics,'research':safe}

def customer_body(content):return _project(content,True)
def staff_body(content):return _project(content,False)

READER_CSS='''
:root{--ink:#183346;--muted:#435a6d;--brand:#165e70;--line:#d8e3eb}*{box-sizing:border-box}body{font-family:system-ui,'Malgun Gothic',sans-serif;margin:0;background:#f1f5f8;color:var(--ink);font-size:17px;line-height:1.85;overflow-wrap:anywhere}.wrap{max-width:780px;margin:auto;padding:24px 20px 56px}header{padding:12px 2px 24px}.brand{font-size:12px;letter-spacing:1.5px;color:var(--muted)}h1{font-size:30px;line-height:1.35;margin:12px 0}h2{font-size:21px;line-height:1.5;margin:0 0 10px}h3{font-size:18px;line-height:1.5;margin:0 0 8px}.meta,.source{font-size:14px;color:var(--muted)}.controls{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}button,.button{border:1px solid #b8cbd8;border-radius:9px;background:white;color:var(--ink);padding:10px 14px;font:inherit;text-decoration:none;cursor:pointer}article,.panel{background:white;border:1px solid var(--line);border-radius:15px;padding:22px;margin-bottom:14px}.lead{border-top:4px solid var(--brand)}p{margin:8px 0 14px}.tag{font-size:13px;color:var(--brand);font-weight:650;display:block;margin-bottom:9px}a{color:#155e8b;text-underline-offset:3px}summary{cursor:pointer;color:var(--brand);font-weight:600;padding:8px 0}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric{padding:16px;background:white;border:1px solid var(--line);border-radius:12px}.value{font-size:24px;font-weight:750;margin:8px 0}.delta{font-size:16px;font-weight:650}.up{color:#b52638}.down{color:#145eb0}.flat{color:var(--muted)}.section-title{margin:28px 0 16px}.big{font-size:20px}.big h2{font-size:24px}@media(max-width:600px){.wrap{padding:18px 14px 40px}h1{font-size:27px}article,.panel{padding:18px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.value{font-size:22px}}@media(max-width:350px){.metrics{grid-template-columns:1fr}}@media print{body{background:white}.controls{display:none}.wrap{max-width:none;padding:0}article,.panel{break-inside:avoid}details{display:block}}
'''

def public_html(packet,*,canonical_url='',image_url='',pdf_url=''):
    e=lambda v:html.escape(str(v or ''),quote=True)
    body=packet.get('body') or {};sender=packet.get('sender') or {};edition=packet.get('edition') or {}
    identity=' '.join(str(sender.get(k) or '') for k in ('name','position')).strip()
    title=f"{identity} · {packet.get('briefing_date')} {body.get('profile_label') or '오늘의 브리핑'}"
    summary=(body.get('issues') or [{}])[0].get('summary') or '오늘의 뉴스와 시장 흐름을 확인하세요.'
    og=f'<title>{e(title)}</title><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(summary[:140])}"><meta property="og:type" content="article">'
    if canonical_url:og+=f'<meta property="og:url" content="{e(canonical_url)}">'
    if image_url:og+=f'<meta property="og:image" content="{e(image_url)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
    parts=[f'<div class="wrap"><header><span class="brand">화랑 WORKSPACE</span><h1>{e(body.get("profile_label") or "오늘의 브리핑")}</h1><p class="meta">{e(packet.get("briefing_date"))} · {e(identity)}<br>수집 기준 {e(display_date(body.get("as_of")))}</p>']
    if edition.get('corrected_at'):parts.append(f'<p class="meta">정정 {e(display_date(edition["corrected_at"]))} · {e(edition.get("number"))}판</p>')
    parts.append('<div class="controls"><button id="font" aria-pressed="false">큰 글자로 읽기</button>')
    if pdf_url:parts.append(f'<a class="button" href="{e(pdf_url)}">PDF 저장</a>')
    parts.append('</div></header>')
    if body.get('market_metrics'):
        parts.append('<h2 class="section-title">시장 지표</h2><div class="metrics">')
        for m in body['market_metrics']:
            state='up' if (m.get('change') or 0)>0 else 'down' if (m.get('change') or 0)<0 else 'flat'
            parts.append(f'<div class="metric"><b>{e(m["label"])}</b><div class="value">{float(m["value"]):,.2f} <small>{e(m["unit"])}</small></div><div class="delta {state}">{e(metric_change(m))}</div><p class="meta">{e(metric_date(m))}<br>{e(m.get("reference_definition") or m.get("observation_kind"))}<br><a href="{e(m["source_url"])}" target="_blank" rel="noopener noreferrer">{e(m["source_name"])}</a></p></div>')
        parts.append('</div>')
    if body.get('market_flow'):parts.append('<section class="panel" style="margin-top:18px"><h2>오늘의 시장 흐름</h2>'+''.join(f'<p>{e(x)}</p>' for x in body['market_flow'])+'</section>')
    parts.append(f'<h2 class="section-title">오늘의 소식 <span class="meta">{len(body.get("issues") or [])}개</span></h2>')
    for i,row in enumerate(body.get('issues') or [],1):
        parts.append(f'<article class="{"lead" if row.get("representative") else ""}"><span class="tag">{e(row.get("category"))}{" · 핵심 이슈" if row.get("representative") else ""}</span><h2>{i:02d} · {e(row["title"])}</h2><p>{e(row.get("summary"))}</p>')
        if row.get('why_important') or row.get('impact_summary'):parts.append(f'<details><summary>해설과 영향</summary><p>{e(row.get("why_important"))}</p><p>{e(row.get("impact_summary"))}</p></details>')
        for src in row['sources']:parts.append(f'<p class="source"><a href="{e(src["url"])}" target="_blank" rel="noopener noreferrer">{e(src["source_name"])} · 원문 읽기 ↗</a><br>{e(display_date(src["published_at"]))}</p>')
        parts.append('</article>')
    research=body.get('research') or {}
    if research.get('reports'):
        parts.append('<section class="panel"><h2>공개 리서치에서 확인한 견해</h2>')
        for group in research.get('viewpoints') or []:
            parts.append(f'<h3>{e(group.get("theme"))} · {e(group.get("timeframe"))}</h3>')
            for v in group.get('views') or []:parts.append(f'<p>{e(v.get("firm"))} · {e(v.get("summary"))}<br><span class="meta">{e(v.get("conditions"))}</span></p>')
        for src in research['reports']:parts.append(f'<p class="source"><a href="{e(src["url"])}" target="_blank" rel="noopener noreferrer">{e(src["firm"])} · {e(src["title"])}</a></p>')
        parts.append('</section>')
    parts.append('<p class="meta">각 기사의 원문과 실제 관측일을 함께 확인해 주세요.</p></div><script>document.getElementById("font").onclick=function(){let on=document.body.classList.toggle("big");this.setAttribute("aria-pressed",String(on));this.textContent=on?"기본 글자로 읽기":"큰 글자로 읽기";};</script>')
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">'+og+'<style>'+READER_CSS+'</style></head><body>'+''.join(parts)+'</body></html>'

def public_pdf(packet):return _cached_pdf(json.dumps(packet,ensure_ascii=False,sort_keys=True))

@lru_cache(maxsize=32)
def _cached_pdf(serialized):
    from io import BytesIO
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    packet=json.loads(serialized);body=packet.get('body') or {};sender=packet.get('sender') or {};edition=packet.get('edition') or {}
    font=Path(__file__).resolve().parents[2]/'assets/fonts/NanumGothic-Regular.ttf'
    if 'HwarangBriefing' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('HwarangBriefing',str(font)))
    ink=colors.HexColor('#183346');muted=colors.HexColor('#435a6d');brand=colors.HexColor('#165e70')
    base=ParagraphStyle('body',fontName='HwarangBriefing',fontSize=11.5,leading=19,textColor=ink,spaceAfter=8)
    heading=ParagraphStyle('heading',parent=base,fontSize=15,leading=23,spaceBefore=14,spaceAfter=8,keepWithNext=True)
    meta=ParagraphStyle('meta',parent=base,fontSize=9,leading=14,textColor=muted)
    metric_style=ParagraphStyle('metric',parent=meta,fontSize=10,leading=19)
    title=ParagraphStyle('title',parent=base,fontSize=24,leading=34,spaceAfter=10)
    e=lambda v:html.escape(str(v or ''),quote=True);identity=' '.join(str(sender.get(k) or '') for k in ('name','position')).strip()
    story=[Paragraph(e(body.get('profile_label') or '오늘의 브리핑'),title),Paragraph(e(packet.get('briefing_date'))+' · '+e(identity),base),Paragraph('수집 기준 '+e(display_date(body.get('as_of'))),meta)]
    if edition.get('corrected_at'):story.append(Paragraph('정정 '+e(display_date(edition['corrected_at']))+' · '+e(edition.get('number'))+'판',meta))
    items=body.get('market_metrics') or []
    if items:
        story.append(Paragraph('시장 지표',heading));cells=[]
        for m in items:cells.append(Paragraph(e(m['label'])+f'<br/><font size="16">{m["value"]:,.2f} {e(m["unit"])}</font><br/>'+e(metric_change(m))+'<br/>'+e(metric_date(m))+'<br/>'+e(m.get('reference_definition') or m.get('observation_kind'))+f'<br/><a href="{e(m["source_url"])}" color="#155e8b">{e(m["source_name"])}</a>',metric_style))
        rows=[cells[i:i+2]+([''] if len(cells[i:i+2])==1 else []) for i in range(0,len(cells),2)]
        table=Table(rows,colWidths=[253.5,253.5],hAlign='LEFT');table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f1f5f8')),('BOX',(0,0),(-1,-1),0.6,colors.HexColor('#d8e3eb')),('INNERGRID',(0,0),(-1,-1),0.5,colors.HexColor('#d8e3eb')),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
        story.extend([table,Spacer(1,12)])
    if body.get('market_flow'):
        story.append(Paragraph('오늘의 시장 흐름',heading))
        for text in body['market_flow']:story.append(Paragraph(e(text),base))
    for i,row in enumerate(body.get('issues') or [],1):
        article=[Paragraph('오늘의 소식',heading)] if i==1 else []
        if row.get('representative'):article.append(Paragraph('핵심 이슈 · '+e(row.get('category')),meta))
        article.append(Paragraph(f'{i:02d} · '+e(row['title']),heading));article.append(Paragraph(e(row.get('summary')),base))
        for key in ('why_important','impact_summary'):
            if row.get(key):article.append(Paragraph(e(row[key]),base))
        for src in row.get('sources') or []:article.append(Paragraph(f'<a href="{e(src["url"])}" color="#155e8b">{e(src["source_name"])} · 원문 읽기</a> · {e(display_date(src["published_at"]))}',meta))
        article.append(Spacer(1,5))
        card=Table([[article]],colWidths=[507],hAlign='LEFT')
        card.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        _,height=card.wrap(507,10000)
        story.append(card if height<730 else KeepTogether(article))
    research=body.get('research') or {}
    if research.get('reports'):
        story.append(Paragraph('공개 리서치에서 확인한 견해',heading))
        for group in research.get('viewpoints') or []:
            story.append(Paragraph(e(group.get('theme'))+' · '+e(group.get('timeframe')),heading))
            for v in group.get('views') or []:story.append(Paragraph(e(v.get('firm'))+' · '+e(v.get('summary'))+'<br/>'+e(v.get('conditions')),base))
        for r in research['reports']:story.append(Paragraph(f'<a href="{e(r["url"])}" color="#155e8b">{e(r["firm"])} · {e(r["title"])}</a>',meta))
    output=BytesIO()
    def decoration(canvas,doc):
        canvas.setTitle(str(body.get('profile_label') or '오늘의 브리핑'));canvas.setAuthor(identity);canvas.setStrokeColor(brand);canvas.setLineWidth(2);canvas.line(38,812,556,812)
        canvas.setFont('HwarangBriefing',8);canvas.setFillColor(muted);canvas.drawString(38,25,('화랑 WORKSPACE · '+identity)[:70]);canvas.drawRightString(556,25,str(doc.page))
    SimpleDocTemplate(output,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=46,bottomMargin=45).build(story,onFirstPage=decoration,onLaterPages=decoration)
    return output.getvalue()

def preview_png(packet):
    from io import BytesIO
    from pathlib import Path
    from PIL import Image,ImageDraw,ImageFont
    font=Path(__file__).resolve().parents[2]/'assets/fonts/NanumGothic-Regular.ttf';image=Image.new('RGB',(1200,630),'#f0f5f8');draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((44,42,1156,588),radius=30,fill='white',outline='#d8e3eb',width=2);draw.rounded_rectangle((84,80,91,548),radius=3,fill='#165e70')
    def put(text,at,size,color='#183346',max_width=980):
        face=ImageFont.truetype(str(font),size)
        while draw.textlength(text,font=face)>max_width and size>20:size-=1;face=ImageFont.truetype(str(font),size)
        draw.text(at,text,font=face,fill=color)
    body=packet.get('body') or {};sender=packet.get('sender') or {}
    put(str(packet.get('briefing_date') or ''),(128,110),30,'#435a6d');put(str(body.get('profile_label') or '오늘의 브리핑'),(128,202),58)
    put('오늘의 소식을 편하게 읽어보세요',(128,310),34,'#435a6d');put(' '.join(str(sender.get(k) or '') for k in ('name','position')).strip(),(128,442),34)
    put('화랑 WORKSPACE',(880,518),20,'#435a6d',220);out=BytesIO();image.save(out,format='PNG');return out.getvalue()
