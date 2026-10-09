"""Explicit customer DTO. Internal advice is never serialized to a public page."""
from __future__ import annotations
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import lru_cache
from typing import Any
from .normalize import is_safe_url


def display_date(value):
    try: return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y.%m.%d %H:%M KST')
    except (ValueError,TypeError): return str(value or '기준일 미확인')


def metric_change(row):
    delta=row.get('change')
    if delta is None:return '이전 관측값 미확인'
    unit='%p' if row.get('code')=='US10Y' else '원' if row.get('code')=='USDKRW' else 'pt'
    text=f'{delta:+.2f} {unit}'
    if row.get('code')!='US10Y' and row.get('change_percent') is not None:text+=f" ({row['change_percent']:+.2f}%)"
    return text


def customer_body(content: dict[str, Any]) -> dict[str, Any]:
    issues=[]
    for row in content.get("issues", []):
        sources=[{k:r.get(k) for k in ("title","source_name","url","published_at")} for r in row.get("sources",[]) if is_safe_url(str(r.get("url") or ""))]
        if not sources: continue
        issues.append({k:row.get(k) for k in ("event_key","title","summary","category","why_important","impact_summary","representative")}|{"sources":sources})
    metrics=content.get("market_metrics") or {}
    safe_metrics=[{k:r.get(k) for k in ("code","label","value","unit","change","change_percent","observed_at","source_name","source_url","observation_kind")} for r in metrics.get("items",[]) if r.get("external_allowed")]
    research=content.get("research") or {}
    def view(v):
        return {k:v.get(k) for k in ("firm","url","stance","summary","conditions")}
    def views(rows):
        return [view(v) for v in rows if isinstance(v,dict) and is_safe_url(str(v.get("url") or ""))]
    safe_research={k:research.get(k) for k in ("status","report_count","institution_count","note")}
    safe_research["reports"]=[{k:r.get(k) for k in ("firm","title","url","published_at")} for r in research.get("reports") or [] if is_safe_url(str(r.get("url") or ""))]
    safe_research["common"]=[{k:r.get(k) for k in ("theme","timeframe","stance","firms")}|{"views":views(r.get("views") or [])} for r in research.get("common") or []]
    safe_research["differences"]=[{k:r.get(k) for k in ("theme","timeframe")}|{"positive":views(r.get("positive") or []),"cautious":views(r.get("cautious") or [])} for r in research.get("differences") or []]
    safe_research["viewpoints"]=[{k:r.get(k) for k in ("theme","timeframe")}|{"views":views(r.get("views") or [])} for r in research.get("viewpoints") or []]
    return {"schema":"hwarang-public-v2","profile_code":content.get("profile_code"),"profile_label":content.get("profile_label"),
            "as_of":content.get("as_of"),"issues":issues,"market_flow":[str(x) for x in content.get("market_flow",[])],
            "market_metrics":safe_metrics,"research":safe_research}



def public_html(packet: dict[str, Any]) -> str:
    e=lambda x:html.escape(str(x or ""),quote=True)
    sender=packet.get("sender") or {}; body=packet.get("body") or {}
    identity=" ".join(str(sender.get(k) or "") for k in ("name","position")).strip()
    title=f"{identity}의 {body.get('profile_label') or '오늘 브리핑'}"
    description=(body.get("issues") or [{}])[0].get("summary") or "오늘의 뉴스와 시장 흐름을 확인하세요."
    parts=[f"<header><small>화랑 WORKSPACE</small><h1>{e(title)}</h1><p>{e(packet.get('briefing_date'))} · {e(identity)}</p></header>"]
    if body.get("market_metrics"):
        parts.append('<section><h2>시장 지표</h2><div class="metrics">')
        for m in body["market_metrics"]:
            parts.append(f"<article><b>{e(m['label'])}</b><h3>{e(m['value'])} {e(m['unit'])}</h3><p>{e(metric_change(m))}<br>{e(display_date(m['observed_at']))} · {e(m['observation_kind'])}</p><a href='{e(m['source_url'])}' target='_blank' rel='noopener noreferrer'>{e(m['source_name'])}</a></article>")
        parts.append('</div></section>')
    if body.get("market_flow"):
        parts.append('<section><h2>오늘의 시장 흐름</h2>'+''.join(f'<p>{e(x)}</p>' for x in body['market_flow'])+'</section>')
    for issue in body.get("issues",[]):
        parts.append(f"<article><small>{e(issue.get('category'))}</small><h2>{e(issue.get('title'))}</h2><p>{e(issue.get('summary'))}</p>")
        if issue.get("impact_summary") or issue.get("why_important"):
            parts.append(f"<details><summary>의미와 영향 더 보기</summary><p>{e(issue.get('why_important'))}</p><p>{e(issue.get('impact_summary'))}</p></details>")
        parts.append(''.join(f"<p class='source'><a href='{e(r['url'])}' target='_blank' rel='noopener noreferrer'>{e(r['source_name'])} · {e(r['title'])}</a><br>{e(display_date(r['published_at']))}</p>" for r in issue.get('sources',[]))+'</article>')
    research=body.get('research') or {}
    if body.get('profile_code')=='MARKET':
        parts.append(f"<section id='research'><h2>증권사 리서치 종합</h2><p>자료 {e(research.get('report_count',0))}개 · 기관 {e(research.get('institution_count',0))}곳</p>")
        for common in research.get('common') or []:
            parts.append(f"<article><h3>공통 견해 · {e(common['theme'])}</h3><p>{e(common['timeframe'])} · {e(' · '.join(common['firms']))}</p>"+''.join(f"<p>{e(v['firm'])} · {e(v['summary'])}<br>{e(v['conditions'])}</p>" for v in common['views'])+'</article>')
        for diff in research.get('differences') or []:
            parts.append(f"<article><h3>의견 차이 · {e(diff['theme'])}</h3><p>{e(diff['timeframe'])}</p><div class='comparison'>")
            for label,key in [('긍정적 관점','positive'),('신중한 관점','cautious')]:
                parts.append(f"<div><b>{label}</b>"+''.join(f"<p>{e(v['firm'])} · {e(v['summary'])}<br>{e(v['conditions'])}</p>" for v in diff[key])+'</div>')
            parts.append('</div></article>')
        if not research.get('common'): parts.append('<p>확인한 자료에서 기관 간 공통 견해가 충분하지 않습니다.</p>')
        parts.append('<details><summary>기관별 견해와 원문</summary>'+''.join(f"<h3>{e(t['theme'])} · {e(t['timeframe'])}</h3>"+''.join(f"<p>{e(v['firm'])} · {e(v['summary'])}<br>{e(v['conditions'])}</p>" for v in t['views']) for t in research.get('viewpoints') or [])+''.join(f"<p><a href='{e(r['url'])}'>{e(r['firm'])} · {e(r['title'])}</a><br>{e(display_date(r['published_at']))}</p>" for r in research.get('reports') or [])+'</details></section>')
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+f'<title>{e(title)}</title><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description[:150])}"><meta property="og:type" content="article">'+'''<style>body{font-family:system-ui,'Malgun Gothic',sans-serif;max-width:940px;margin:0 auto;padding:24px;background:#f4f7fb;color:#183750;font-size:17px;line-height:1.8}header,article,section{background:white;border:1px solid #dbe4ee;border-radius:16px;padding:22px;margin-bottom:18px}section article{padding:16px}h1{font-size:30px}h2{font-size:22px}h3{font-size:19px}a{color:#155f9d;overflow-wrap:anywhere}small,.source{font-size:14px;color:#64768b}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:20px}summary{cursor:pointer;font-weight:600}@media(max-width:640px){body{padding:12px}h1{font-size:25px}.metrics{grid-template-columns:1fr 1fr}.comparison{grid-template-columns:1fr}}@media print{body{background:white}article{break-inside:avoid}details{display:block}}</style></head><body>'''+''.join(parts)+'</body></html>'


def public_pdf(packet: dict[str, Any]) -> bytes:
    return _cached_pdf(json.dumps(packet,ensure_ascii=False,sort_keys=True))


@lru_cache(maxsize=32)
def _cached_pdf(serialized: str) -> bytes:
    packet=json.loads(serialized)
    from io import BytesIO
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib import colors
    font=Path(__file__).resolve().parents[2]/'assets/fonts/NanumGothic-Regular.ttf'
    if not font.is_file(): raise ValueError('한글 PDF 폰트가 없습니다.')
    if 'HwarangBriefing' not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont('HwarangBriefing',str(font)))
    style=ParagraphStyle('Briefing',fontName='HwarangBriefing',fontSize=11,leading=18,spaceAfter=8)
    heading=ParagraphStyle('BriefingHeading',parent=style,fontSize=16,leading=23,spaceBefore=12,keepWithNext=True)
    e=lambda v:html.escape(str(v or ''))
    story=[]; body=packet.get('body') or {};sender=packet.get('sender') or {}
    story.append(Paragraph(e(body.get('profile_label')),heading));story.append(Paragraph(e(packet.get('briefing_date'))+' · '+e(sender.get('name'))+' '+e(sender.get('position')),style))
    for m in body.get('market_metrics') or []:
        story.append(Paragraph(e(m['label'])+' '+e(m['value'])+' '+e(m['unit'])+' · '+e(metric_change(m))+'<br/>'+e(display_date(m['observed_at']))+' · '+e(m['observation_kind'])+f'''<br/><a href="{e(m['source_url'])}">{e(m['source_name'])}</a>''',style))
    for flow in body.get('market_flow') or []:story.append(Paragraph(e(flow),style))
    for row in body.get('issues') or []:
        story.append(Paragraph(e(row['title']),heading))
        for key in ('summary','why_important','impact_summary'):
            if row.get(key):story.append(Paragraph(e(row[key]),style))
        for src in row.get('sources') or []:
            story.append(Paragraph(f'<a href="{e(src["url"])}" color="#155f9d">{e(src["source_name"])} · {e(src["title"])} · {e(display_date(src["published_at"]))}</a>',style))
    research=body.get('research') or {}
    if body.get('profile_code')=='MARKET':
        story.append(Paragraph('증권사 리서치 종합',heading))
        story.append(Paragraph(f"자료 {research.get('report_count') or 0}개 · 기관 {research.get('institution_count') or 0}곳",style))
        for common in research.get('common') or []:
            story.append(Paragraph('공통 견해 · '+e(common['theme'])+' · '+e(common['timeframe']),heading))
            story.append(Paragraph(e(' · '.join(common['firms'])),style))
        for diff in research.get('differences') or []:
            story.append(Paragraph('의견 차이 · '+e(diff['theme'])+' · '+e(diff['timeframe']),heading))
            for label,key in [('긍정적 관점','positive'),('신중한 관점','cautious')]:
                for v in diff[key]:story.append(Paragraph(label+' · '+e(v['firm'])+' · '+e(v['summary'])+'<br/>'+e(v['conditions']),style))
        for theme in research.get('viewpoints') or []:
            story.append(Paragraph(e(theme['theme'])+' · '+e(theme['timeframe']),heading))
            for v in theme['views']:story.append(Paragraph(e(v['firm'])+' · '+e(v['summary'])+'<br/>'+e(v['conditions']),style))
        for r in research.get('reports') or []:story.append(Paragraph(f'<a href="{e(r["url"])}">{e(r["firm"])} · {e(r["title"])} · {e(display_date(r["published_at"]))}</a>',style))
    output=BytesIO()
    def footer(canvas,doc):
        canvas.setTitle(str(body.get('profile_label') or '화랑 브리핑'));canvas.setAuthor(str(sender.get('name') or '')+' '+str(sender.get('position') or ''))
        canvas.setFont('HwarangBriefing',8);canvas.setFillColor(colors.HexColor('#64768b'));canvas.drawString(38,25,('화랑 WORKSPACE · '+str(sender.get('name') or '')+' '+str(sender.get('position') or ''))[:55]);canvas.drawRightString(556,25,str(doc.page))
    SimpleDocTemplate(output,rightMargin=38,leftMargin=38,topMargin=36,bottomMargin=45).build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
