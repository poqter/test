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
    update_keys={r.get('event_key') for r in content.get('important_updates',[])}
    for row in content.get('important_updates',[])+content.get('issues',[]):
        if external and content.get('profile_code')=='INSURANCE':
            state=row.get('communication_state')
            neutral=(state=='not_applicable' and row.get('customer_article_eligible') is True
                     and row.get('category') in {'제도·규제','상품·보험료','보험금·보상','세제·재무','소비자·사회이슈'})
            if (state!='customer_ready' and not neutral) or row.get('category') in {'영업·채널','보험사·시장'}:continue
        sources=[{k:r.get(k) for k in ('title','source_name','url','published_at')} for r in row.get('sources',[]) if is_safe_url(str(r.get('url') or '')) and r.get('published_at')][:4]
        if sources:issues.append({k:row.get(k) for k in ('event_key','title','summary','category','why_important','impact_summary','representative','headline_sufficient','event_date')}|{'sources':sources, 'reading_group':'more' if content.get('editorial_version',0) >= 2 and row.get('selection_tier') == 'light_digest' else 'main', 'important_update':row.get('event_key') in update_keys,
            'added_at':row.get('added_at') if row.get('event_key') in update_keys else None})
    raw_metrics=content.get('market_metrics') or {}
    raw_metrics=raw_metrics.get('items',[]) if isinstance(raw_metrics,dict) else raw_metrics
    metrics=[{k:r.get(k) for k in METRIC_FIELDS} for r in raw_metrics
             if r.get('value') is not None and is_safe_url(str(r.get('source_url') or ''))
             and (not external or r.get('external_allowed') is True)]
    research=content.get('research') or {}
    def views(rows):return [{k:v.get(k) for k in ('firm','url','stance','summary','conditions')} for v in rows if isinstance(v,dict) and is_safe_url(str(v.get('url') or ''))]
    safe={k:research.get(k) for k in ('status','report_count','institution_count','note')}
    safe['reports']=[{k:r.get(k) for k in ('firm','title','url','published_at')} for r in research.get('reports') or [] if is_safe_url(str(r.get('url') or ''))]
    safe['common']=[{k:r.get(k) for k in ('theme','timeframe','stance','firms')}|{'views':views(r.get('views') or [])} for r in research.get('common') or []]
    safe['differences']=[{k:r.get(k) for k in ('theme','timeframe')}|{'positive':views(r.get('positive') or []),'cautious':views(r.get('cautious') or [])} for r in research.get('differences') or []]
    safe['viewpoints']=[{k:r.get(k) for k in ('theme','timeframe')}|{'views':views(r.get('views') or [])} for r in research.get('viewpoints') or []]
    extras={}
    for key in ('weather','calendar'):
        extras[key]=[{k:r.get(k) for k in ('title','summary','scheduled_at')}|{'sources':[
            {k:src.get(k) for k in ('url','source_name','published_at')} for src in r.get('sources',[])
            if is_safe_url(str(src.get('url') or '')) and src.get('published_at')]}
            for r in content.get(key,[]) if isinstance(r,dict)][:3 if key=='calendar' else 1]
    return {'schema':'hwarang-public-v2' ,'profile_code':content.get('profile_code'),'profile_label':content.get('profile_label'),'as_of':content.get('as_of'),'issues':issues,'market_flow':[str(x) for x in content.get('market_flow',[])],'market_metrics':metrics,'research':safe,**extras}

def customer_body(content):return _project(content,True)
def staff_body(content):
    body = _project(content, False)
    body['source_links'] = []  # Raw, unanalyzed legacy links never become verified reading.
    return body

READER_CSS='''
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
:root{color-scheme:light;--ink:#182c46;--muted:#607087;--brand:#172e4d;--line:#e4eaf1;--soft:#f1f5fa}*{box-sizing:border-box}body{font-family:Pretendard,'Malgun Gothic',sans-serif;margin:0;background:#eef2f6;color:var(--ink);font-size:16px;line-height:1.9;overflow-wrap:anywhere}.wrap{max-width:736px;margin:24px auto 48px;background:#fff;padding:0 36px 30px;border-radius:12px;overflow:hidden}header{margin:0 -36px 30px;padding:30px 36px 0;background:var(--brand);color:#f7f9fc}.brand{display:flex;align-items:center;gap:12px;font-size:13px;font-weight:600;letter-spacing:1.5px;color:#cdd8e7;margin-bottom:28px}.brand:before{content:'H';font-family:Georgia,serif;font-weight:400;font-size:30px;line-height:42px;text-align:center;width:44px;height:44px;border:1px solid #77869c;flex-shrink:0}h1{font-size:32px;line-height:1.35;letter-spacing:-1.2px;margin:0 0 14px;font-weight:700}h2{font-size:23px;line-height:1.45;letter-spacing:-.7px;margin:0 0 15px;font-weight:700}h3{font-size:14px;line-height:1.7;margin:0 0 7px;font-weight:600}.meta,.source{font-size:13px;color:var(--muted)}header .meta{color:#c5d2e4;font-size:14px;line-height:1.8}.controls{display:flex;gap:8px;flex-wrap:wrap;margin:24px -36px 0;padding:17px 36px;background:#fff;border-bottom:1px solid var(--line)}button,.button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);padding:9px 14px;font:inherit;font-size:13px;text-decoration:none;cursor:pointer}button[aria-pressed=true]{background:var(--soft);border-color:var(--muted)}article{background:#fff;border:0;border-radius:0;padding:0 0 28px;margin:0 0 28px;border-bottom:1px solid var(--line)}article.lead{border-top:0}.panel{background:var(--soft);border:0;border-radius:8px;padding:21px 23px;margin:0 0 32px}.panel h2{font-size:16px}.panel p{margin-bottom:8px}.explanation{border-left:3px solid #9aaec8;padding:2px 0 2px 17px;margin:20px 0}.explanation p{font-size:15px;color:var(--muted);line-height:1.8}p{margin:8px 0 19px}.tag{font-size:12px;color:var(--muted);font-weight:600;display:block;margin-bottom:10px}a{color:#365d85;text-underline-offset:4px}summary{cursor:pointer;color:var(--brand);font-weight:600;padding:8px 0}.source{font-size:12px;margin:10px 0;line-height:1.8}.source a{color:var(--muted)}.section-title{font-size:14px;color:var(--muted);font-weight:500;display:flex;align-items:center;gap:10px;margin:30px 0 20px}.section-title:after{content:'';height:1px;flex:1;background:var(--line)}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric{padding:16px;background:var(--soft);border-radius:8px}.value{font-size:24px;font-weight:700}.delta{font-size:16px}.up{color:#b52638}.down{color:#145eb0}.flat{color:var(--muted)}.big{font-size:19px}.big h2{font-size:26px}.big .panel h2{font-size:19px}.big .explanation p{font-size:18px}.reader-footer{background:var(--soft);margin:30px -36px -30px;padding:25px 36px;font-size:12px;color:var(--muted);line-height:1.8}.reader-footer strong{color:var(--ink);font-size:14px;font-weight:600}@media(max-width:600px){.wrap{margin:0;border-radius:0;padding:0 22px 24px}header{margin:0 -22px 26px;padding:24px 22px 0}.controls{margin:22px -22px 0;padding:15px 22px}h1{font-size:28px}h2{font-size:21px}.panel{padding:18px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.reader-footer{margin:26px -22px -24px;padding:23px 22px}}@media(max-width:350px){.metrics{grid-template-columns:1fr}}@media print{body{background:white}.wrap{max-width:none;margin:0;padding:0;border-radius:0}header{background:white;color:var(--ink);margin:0;padding:0 0 16px}header .meta,.brand{color:var(--muted)}.controls{display:none}article,.panel{break-inside:avoid}.reader-footer{margin:20px 0 0}details{display:block}}
.briefing-section{font-size:22px;font-weight:700;color:var(--ink);margin:42px 0 24px;padding:14px 0;border-top:2px solid var(--line)}article h2{font-size:25px}article>p{font-size:17px;line-height:1.95}.explanation{background:var(--soft);border-left:0;border-radius:8px;padding:17px 20px}.explanation p{color:#40546d;font-size:16px}.source{font-size:13px}.big article>p{font-size:20px}@media(max-width:600px){article h2{font-size:22px}.briefing-section{font-size:20px}}
'''

READER_CSS += 'header{background:#fff;color:#17273d;padding-bottom:0}.brand,header .meta{color:#64738a}.brand:before{display:none}h1,h2,article h2{color:#17273d!important;-webkit-text-fill-color:#17273d!important}h1{font-size:27px}article h2{font-size:20px}article>p{font-size:16px;line-height:1.8;color:#45556a}.reader-tabs{display:flex;gap:25px;border-bottom:1px solid #dce4ee;margin-bottom:22px}.reader-tabs button{border:0;border-bottom:3px solid transparent;border-radius:0;padding:10px 0 14px;background:transparent;color:#64738a;font-size:16px}.reader-tabs button[aria-selected=true]{border-bottom-color:#263f62;color:#263f62;font-weight:700}.edition-delay{font-size:14px;background:#f4f7fb;padding:12px 16px;color:#45556a}.panel{background:#f4f7fb;padding:17px 21px;margin-bottom:24px}.panel ul{margin:0;padding-left:20px;font-size:15px}.explanation{display:none}[hidden]{display:none!important}@media(max-width:400px){.reader-tabs{gap:18px}.reader-tabs button{font-size:14px}}@media print{[role=tabpanel][hidden]{display:block!important}.reader-tabs{display:none}}\n'

READER_CSS += '.more-reading{border:1px solid var(--line);border-radius:8px;padding:8px 16px;margin:20px 0}.more-title{display:block;padding:12px 0;line-height:1.6;text-decoration:none;border-top:1px solid var(--line)}.reader-tabs button[aria-selected=true]{border-bottom-color:#0b9ea8}.reader-tabs{gap:18px}.reader-tabs button{flex:1}.panel{background:#fafbfd}.big .more-title{font-size:20px}'

from .presentation import CARD_CSS, article_html
READER_CSS += CARD_CSS + """
.wrap.reader-modern{max-width:840px;background:#fafbfd;padding:0 24px 24px;overflow:visible}
.reader-modern header{background:#fff;margin:0 -24px 20px;padding:26px 24px 0;border-radius:14px 14px 0 0}
.reader-modern .brand{margin-bottom:15px;font-size:11px;letter-spacing:2px}.reader-modern h1{font-size:27px;font-weight:650}
.reader-modern .controls{margin:0;padding:0;border:0;justify-content:flex-end;background:transparent}
.reader-modern .controls button{border:0;background:transparent;font-size:14px}
.reader-modern .reader-tabs{position:sticky;top:0;z-index:5;background:#fff;margin:0 -4px 16px;gap:0}
.reader-modern .reader-tabs button{flex:1;min-height:48px;font-size:15px;border-radius:0}
.reader-modern .reader-tabs button[aria-selected=true]{color:#126d73;border-bottom-color:#168b90}
.reader-modern .section-title{font-size:18px;font-weight:600;color:#172b46;margin:20px 0 12px}.reader-modern .section-title:after{display:none}
.reader-modern .panel{background:#eff5fa;border-radius:14px;padding:20px}.reader-modern .panel li{padding-bottom:8px}
.reader-modern .reader-footer{margin:24px -24px -24px;background:#f1f5f8;padding:20px 24px}
.reader-modern .more-reading{background:#fff;border-radius:12px}.reader-modern summary{min-height:44px}
@media(max-width:600px){.wrap.reader-modern{padding:0 16px 20px}.reader-modern header{margin:0 -16px 14px;padding:22px 16px 0}.reader-modern .reader-footer{margin:20px -16px -20px;padding:20px 16px}}
"""

def public_html(packet,*,canonical_url='',image_url='',pdf_url=''):
    e=lambda v:html.escape(str(v or ''),quote=True)
    body=packet.get('body') or {};sender=packet.get('sender') or {}
    identity=' '.join(str(sender.get(k) or '') for k in ('name','position')).strip()
    title=f"{identity} · {packet.get('briefing_date')} 오늘의 브리핑"
    og=f'<title>{e(title)}</title><meta property="og:title" content="{e(title)}"><meta property="og:type" content="article">'
    if canonical_url:og+=f'<meta property="og:url" content="{e(canonical_url)}">'
    if image_url:og+=f'<meta property="og:image" content="{e(image_url)}">'
    sections=body.get('sections') or [{'profile_code':body.get('profile_code') or 'NEWS','profile_label':body.get('profile_label') or '브리핑','briefing_date':packet.get('briefing_date')}]
    parts=[f'<div class="wrap reader-modern"><header><span class="brand">HWARANG WORKSPACE</span><h1>오늘의 브리핑</h1><p class="meta">{e(identity)} · {e(packet.get('requested_date') or packet.get('briefing_date'))}</p><div class="controls"><button id="font" aria-pressed="false">큰 글자로 읽기</button></div></header>']
    edition=packet.get('edition') or {}
    if edition.get('corrected_at'):
        parts.append('<p class="meta">정정 '+e(display_date(edition['corrected_at']))+' · '+e(edition.get('number'))+'판</p>')
    parts.append('<nav class="reader-tabs" role="tablist" aria-label="공유받은 브리핑 영역">')
    for i,section in enumerate(sections):
        parts.append(f'<button role="tab" id="tab-{i}" aria-controls="section-{i}" aria-selected="{str(i==0).lower()}" data-section="{i}">{e(section["profile_label"])}</button>')
    parts.append('</nav>')
    for i,section in enumerate(sections):
        code=section['profile_code'];day=section.get('briefing_date')
        rows=[r for r in body.get('issues') or [] if (r.get('section_code') or body.get('profile_code'))==code]
        parts.append(f'<section role="tabpanel" id="section-{i}" aria-labelledby="tab-{i}"'+(' hidden' if i else '')+'>')
        if day:
            parts.append(f'<p class="meta" data-edition-date="{e(day)}">{e(day)} 브리핑</p>')
            parts.append(f'<p class="edition-delay" data-stale-date="{e(day)}" hidden>오늘 브리핑은 아직 준비되지 않았습니다. 공유된 최근 자료({e(day)})를 보여드립니다.</p>')
        if code=='NEWS' and body.get('weather_forecast'):
            from .weather import weather_html
            parts.append(weather_html(body['weather_forecast']))
        if not rows:parts.append('<p class="panel">아직 공개된 브리핑이 없습니다.</p>')
        if code=='MARKET' and body.get('market_flow'):
            parts.append('<section class="panel"><h2>오늘의 경제·금융 흐름</h2><ul>'+''.join('<li>'+e(t)+'</li>' for t in body['market_flow'])+'</ul></section>')
        if code=='MARKET':
            for m in body.get('market_metrics') or []:
                parts.append('<p class="source">'+e(m.get('label'))+' · '+e(m.get('value'))+' '+e(m.get('unit'))+' · '+e(metric_change(m))+' · '+e(metric_date(m))+' · <a href="'+e(m.get('source_url'))+'">'+e(m.get('source_name'))+'</a></p>')
        reading_group = None
        counters = {'main':0, 'more':0}
        more=[r for r in rows if r.get('reading_group')=='more']
        rows=[r for r in rows if r.get('reading_group')!='more']
        for row in rows:
            group=row.get('reading_group') or 'main'
            if group!=reading_group:
                reading_group=group
                parts.append('<h2 class="section-title">'+('더 읽을 기사' if group=='more' else '오늘의 주요 뉴스')+'</h2>')
            counters[group]+=1
            parts.append(article_html(row,lead=counters[group]==1,heading='h2'))
        if more:
            parts.append('<details class="more-reading"><summary>더 읽을 기사 · '+str(len(more))+'건</summary>')
            for row in more:
                src=next((s for s in row.get('sources',[]) if is_safe_url(str(s.get('url') or ''))),None)
                if src:parts.append('<a class="more-title" href="'+e(src['url'])+'" target="_blank" rel="noopener noreferrer">'+e(row.get('title'))+' ↗</a>')
            parts.append('</details>')
        for kind,label in (('calendar','오늘 예정된 주요 발표 · KST'),):
            if (kind=='calendar' and code!='MARKET') or (kind=='weather' and code!='NEWS'):continue
            extras=body.get(kind) or []
            if extras:parts.append('<section class="panel"><h2>'+label+'</h2>')
            for item in extras:
                parts.append('<p>'+e(display_date(item['scheduled_at']) if item.get('scheduled_at') else '')+' '+e(item.get('title'))+' · '+e(item.get('summary'))+'</p>')
                for src in item.get('sources',[]):parts.append('<a class="source" href="'+e(src['url'])+'">'+e(src.get('source_name'))+'</a>')
            if extras:parts.append('</section>')
        research=body.get('research') or {}
        if code=='MARKET' and research.get('reports'):
            parts.append('<details><summary>공개 리서치 더 보기</summary>')
            for group in research.get('viewpoints') or []:
                parts.append('<h3>'+e(group.get('theme'))+'</h3>')
                for v in group.get('views') or []:parts.append('<p>'+e(v.get('firm'))+' · '+e(v.get('summary'))+'</p>')
            for src in research['reports']:
                if is_safe_url(str(src.get('url') or '')):parts.append(f'<p class="source"><a href="{e(src["url"])}" target="_blank" rel="noopener noreferrer">{e(src.get("firm"))} · {e(src.get("title"))}</a></p>')
            parts.append('</details>')
        parts.append('</section>')
    parts.append(f'<footer class="reader-footer"><strong>{e(identity)}</strong><br>화랑 WORKSPACE · 출처와 원문을 함께 확인해 주세요.</footer></div>')
    script='''<script>
    document.getElementById('font').onclick=function(){const on=document.body.classList.toggle('big');this.setAttribute('aria-pressed',String(on));this.textContent=on?'기본 글자로 읽기':'큰 글자로 읽기';};
    const positions={};let active='0';document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',()=>{positions[active]=window.scrollY;active=b.dataset.section;document.querySelectorAll('[data-section]').forEach(t=>t.setAttribute('aria-selected',String(t===b)));document.querySelectorAll('[role=tabpanel]').forEach(p=>p.hidden=p.id!==b.getAttribute('aria-controls'));window.scrollTo(0,positions[active]||0);}));
    document.querySelectorAll('[role=tab]').forEach((b,i)=>b.addEventListener('keydown',ev=>{const tabs=[...document.querySelectorAll('[role=tab]')];let n;if(ev.key==='ArrowRight')n=(i+1)%tabs.length;if(ev.key==='ArrowLeft')n=(i+tabs.length-1)%tabs.length;if(ev.key==='Home')n=0;if(ev.key==='End')n=tabs.length-1;if(n!==undefined){ev.preventDefault();tabs[n].click();tabs[n].focus();}}));
    const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    document.querySelectorAll('[data-weather-date]').forEach(p=>{if(p.dataset.weatherDate!==today){const h=p.querySelector('.weather-head span');if(h)h.textContent='공유일의 날씨';}});
    document.querySelectorAll('[data-stale-date]').forEach(p=>p.hidden=p.dataset.staleDate>=today);
    </script>'''
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">'+og+'<style>'+READER_CSS+'</style></head><body>'+''.join(parts)+script+'</body></html>'

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
        story.append(Paragraph('오늘의 경제·금융 흐름',heading))
        for text in body['market_flow']:story.append(Paragraph(e(text),base))
    last_section = None
    for i,row in enumerate(body.get('issues') or [],1):
        if row.get('section_label') and row['section_label'] != last_section:
            last_section = row['section_label']
            section_day = next((s.get('briefing_date') for s in body.get('sections', []) if s.get('profile_label') == last_section), None)
            story.append(Paragraph(e(last_section)+((' · '+e(section_day)) if section_day else ''), heading))
        article=[Paragraph('오늘의 소식',heading)] if i==1 else []
        if row.get('important_update'):article.append(Paragraph('중요 발표 추가 · '+e(display_date(row.get('added_at'))),meta))
        if row.get('representative'):article.append(Paragraph('핵심 이슈 · '+e(row.get('category')),meta))
        article.append(Paragraph(f'{i:02d} · '+e(row['title']),heading));article.append(Paragraph(e(row.get('summary')),base))
        for src in row.get('sources') or []:article.append(Paragraph(f'<a href="{e(src["url"])}" color="#155e8b">{e(src["source_name"])} · 원문 읽기</a> · {e(display_date(src["published_at"]))}',meta))
        article.append(Spacer(1,5))
        card=Table([[article]],colWidths=[507],hAlign='LEFT')
        card.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        _,height=card.wrap(507,10000)
        story.append(card) if height < 650 else story.extend(article)
    research=body.get('research') or {}
    if research.get('reports'):
        story.append(Paragraph('공개 리서치에서 확인한 견해',heading))
        for group in research.get('viewpoints') or []:
            story.append(Paragraph(e(group.get('theme'))+' · '+e(group.get('timeframe')),heading))
            for v in group.get('views') or []:story.append(Paragraph(e(v.get('firm'))+' · '+e(v.get('summary'))+'<br/>'+e(v.get('conditions')),base))
        for r in research['reports']:story.append(Paragraph(f'<a href="{e(r["url"])}" color="#155e8b">{e(r["firm"])} · {e(r["title"])}</a>',meta))
    if body.get('schema') == 'hwarang-staff-export-v1':
        story.append(Paragraph('상담 준비 · 직원 내부용 / 고객 공유 금지', heading))
        for row in body.get('consultations') or []:
            story.append(Paragraph(e(row['title']), heading))
            story.append(Paragraph('상담 상태: '+e(row['state']), meta))
            for field in row['fields']:
                story.append(Paragraph(e(field['label'])+' · '+e(field['text']), base))
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
