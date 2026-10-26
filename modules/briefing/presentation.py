"""Shared, escaped reading components. Presentation only: no publication decisions."""
import html
from .normalize import is_safe_url

READER_VERSION = '20261026-cards'
e = lambda value: html.escape(str(value or ''), quote=True)

CARD_CSS = '''
.hw-news,.hw-news.lead{box-sizing:border-box;background:#fff;border:1px solid #e2e8ef;border-radius:14px;padding:20px 22px;margin:12px 0;color:#172b46;box-shadow:0 2px 7px #172b4603;overflow-wrap:anywhere}
.hw-news.lead{border-top:2px solid #168b90}
.hw-news .tag{display:inline-block;background:#e8f6f5;color:#126d73;border-radius:20px;padding:3px 11px;font-size:12px;font-weight:600;margin:0 0 10px;line-height:1.7}
.hw-news h3,.hw-news h2{font-family:inherit;font-size:20px;font-weight:600;letter-spacing:-.45px;line-height:1.5;margin:0 0 9px;color:#172b46}
.hw-news h3 a,.hw-news h2 a{color:inherit;text-decoration:none;display:block;white-space:normal;overflow-wrap:anywhere}
.hw-news h3 a:hover,.hw-news h2 a:hover{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px}
.hw-news p{font-size:16px!important;line-height:1.75;margin:0 0 12px;color:#46566b}
.hw-news .source{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:#617188;line-height:1.7;margin:0}
.hw-news .source a{color:#21445e;text-decoration:none;min-height:44px;display:inline-flex;align-items:center;white-space:nowrap}
.hw-news .event-date{font-size:12px;color:#617188;margin-bottom:7px}.hw-news details{font-size:13px;margin-top:5px}.hw-news details a{display:block;padding:10px 0}
.hw-news.big h3,.big .hw-news h2{font-size:24px}.hw-news.big p,.big .hw-news p{font-size:20px!important;line-height:1.8}
.hw-news a:focus-visible,.hw-more a:focus-visible,.reader-tabs button:focus-visible{outline:2px solid #168b90;outline-offset:3px;border-radius:4px}
.hw-more{border:1px solid #e2e8ef;border-radius:12px;background:#fff;padding:0 16px;margin-top:16px}.hw-more summary{min-height:48px;display:list-item;padding:12px 0;color:#172b46;font-size:15px;cursor:pointer}.hw-more a{display:block;padding:13px 0;border-top:1px solid #eef1f5;line-height:1.6;color:#21445e;text-decoration:none;overflow-wrap:anywhere}
.hw-weather{display:grid;grid-template-columns:76px minmax(0,1fr);gap:14px;align-items:center;background:linear-gradient(120deg,#edf7ff,#e4f2fc);border-radius:14px;padding:18px 20px;margin:14px 0 20px;color:#172b46;font-size:14px;overflow-wrap:anywhere}
.hw-weather svg{width:76px;height:76px}.hw-weather .weather-head{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:12px;color:#465b73}.hw-weather strong{display:block;font-size:20px;font-weight:600;margin:5px 0}.hw-weather .temps{font-size:15px;margin:4px 0}.hw-weather .low{color:#1765b6;font-weight:650}.hw-weather .high{color:#be5322;font-weight:650}.hw-weather .weather-note{font-size:12px;line-height:1.6;color:#51677f;margin-top:8px}.hw-weather a{color:inherit}.hw-weather.unavailable{grid-template-columns:1fr;background:#f3f6fa}
@media(max-width:600px){.hw-news{padding:17px 18px;margin:10px 0}.hw-news h3,.hw-news h2{font-size:19px}.hw-weather{padding:15px;grid-template-columns:58px minmax(0,1fr);gap:10px}.hw-weather svg{width:58px;height:58px}.hw-news .source{font-size:12px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
'''


def article_html(row, *, lead=False, large=False, heading='h3'):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    def stamp(value):
        try:return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d %H:%M")
        except (ValueError,TypeError):return str(value or "기준일 미확인")
    sources=[s for s in row.get('sources',[]) if is_safe_url(str(s.get('url') or ''))]
    first=sources[0] if sources else None
    title=e(row.get('title') or '오늘의 소식')
    if first:title=f'<a href="{e(first["url"])}" target="_blank" rel="noopener noreferrer">{title}</a>'
    cls='hw-news'+(' lead' if lead else '')+(' big' if large else '')
    tag=('중요 발표 · ' if row.get('important_update') else '')+str(row.get('category') or '뉴스')
    parts=[f'<article class="{cls}"><span class="tag">{e(tag)}</span><{heading}>{title}</{heading}>']
    if not row.get('headline_sufficient'):parts.append('<p>'+e(row.get('summary'))+'</p>')
    if row.get('event_date'):parts.append('<div class="event-date">사건·발표일 '+e(row['event_date'])+'</div>')
    if row.get('important_update'):parts.append('<div class="event-date">추가 '+e(stamp(row.get('added_at')))+'</div>')
    if first:
        parts.append('<div class="source"><span>'+e(first.get('source_name'))+' · '+e(stamp(first.get('published_at')))+'</span><a href="'+e(first['url'])+'" target="_blank" rel="noopener noreferrer">원문 ↗</a></div>')
    if len(sources)>1:
        parts.append('<details><summary>추가 출처 '+str(len(sources)-1)+'건</summary>')
        for s in sources[1:]:parts.append('<a href="'+e(s['url'])+'" target="_blank" rel="noopener noreferrer">'+e(s.get('source_name'))+' · '+e(stamp(s.get('published_at')))+'</a>')
        parts.append('</details>')
    return ''.join(parts)+'</article>'
