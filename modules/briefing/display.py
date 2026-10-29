"""Readable staff/customer cards from allowlisted saved projections."""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from .normalize import is_safe_url


def stamp(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y.%m.%d %H:%M')
    except (ValueError,TypeError):return str(value or '기준일 미확인')


def render_style():
    st.markdown("""<style>
    .st-key-hw_briefing_center{--hw-ink:#172b46;--hw-muted:#62728a;--hw-line:#dce4ee;--hw-soft:#edf3fb;--hw-surface:#fff;--hw-brand:#173d6a}
    .st-key-hw_briefing_header .hw-briefing-hero{border:0;margin:0;padding:16px 0;background:transparent}
    .st-key-hw_briefing_header .hw-weather{margin:0;padding:16px 20px}
    .st-key-hw_weather_toolbar{margin-top:4px}
    .hw-briefing-hero{padding:7px 0 18px;margin:0 0 10px;border-bottom:1px solid var(--hw-line,#dce4ee)}
    .hw-briefing-hero>span{font-size:12px;letter-spacing:1px;color:var(--hw-muted,#62728a)}
    .hw-briefing-hero h1{font-size:29px;font-weight:650;letter-spacing:-1px;margin:8px 0 0;color:var(--hw-ink,#172b46);line-height:1.35}
    .hw-edition{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:18px 0 12px;color:var(--hw-muted,#62728a);font-size:13px}
    .hw-edition strong{font-size:20px;color:var(--hw-ink,#172b46)}
    .hw-edition-state{font-size:12px;background:var(--hw-soft,#edf3fb);color:var(--hw-brand,#173d6a);padding:4px 10px;border-radius:30px}
    .hw-news,.hw-digest{max-width:860px;font-family:Pretendard,'Malgun Gothic',sans-serif;background:var(--hw-surface,#fff);border:1px solid var(--hw-line,#dce4ee);border-radius:12px;padding:23px 25px;margin:12px 0 16px;color:var(--hw-ink,#172b46)}
    .hw-digest{border-top:3px solid var(--hw-brand,#173d6a)}
    .hw-news.lead{border-top:3px solid var(--hw-brand,#173d6a)}
    .hw-news .tag,.hw-digest .tag{color:var(--hw-muted,#62728a);font-size:13px;font-weight:600;margin-bottom:9px}
    .hw-news h3{font-size:24px;line-height:1.5;letter-spacing:-.6px;margin:0 0 12px;color:var(--hw-ink,#172b46)}
    .hw-news p,.hw-digest p{font-size:17px!important;line-height:1.95;margin:8px 0 14px;color:var(--hw-ink,#172b46);overflow-wrap:anywhere}
    .hw-news .source{font-size:13px;line-height:1.7;color:var(--hw-muted,#62728a);overflow-wrap:anywhere}
    .hw-news a{color:var(--hw-brand,#173d6a);text-underline-offset:3px}.hw-news h3 a{color:inherit;text-decoration:none}
    .hw-news .hw-context{background:var(--hw-soft,#edf3fb);border-radius:8px;padding:14px 17px;margin:15px 0}
    .hw-news .hw-context h4{font-size:13px;color:var(--hw-brand,#173d6a);margin:0 0 6px}
    .hw-news .hw-context p{font-size:16px!important;line-height:1.9;margin-bottom:14px}
    .hw-briefing-section{max-width:860px;font-size:23px;font-weight:700;color:var(--hw-ink,#172b46);padding:16px 0;margin:30px 0 12px;border-top:2px solid var(--hw-line,#dce4ee)}
    .hw-news.big h3{font-size:25px}.hw-news.big p,.hw-digest.big p{font-size:20px!important;line-height:1.85}
    .st-key-hw_briefing_center button{min-height:42px}.st-key-hw_briefing_center [data-testid="stExpander"]{border-color:var(--hw-line)}
    .st-key-hw_briefing_center [data-testid="stRadio"]{margin:5px 0 15px}
    .st-key-hw_briefing_center [data-testid="stRadio"] label{padding:6px 10px;border-radius:8px}
    .st-key-hw_briefing_center [data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px}

    @media(max-width:640px){.hw-news,.hw-digest{padding:18px}.hw-briefing-hero h1{font-size:25px}.hw-news h3{font-size:20px}.st-key-hw_briefing_center [data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-hw_briefing_center [data-testid="stColumn"]{min-width:min(100%,240px)}}
    .st-key-hw_briefing_center{background:#fff;color:#172b46;color-scheme:light;padding:0 12px}
    .st-key-hw_briefing_center .hw-briefing-hero h1,.st-key-hw_briefing_center .hw-edition strong,.st-key-hw_briefing_center .hw-news h3,.st-key-hw_briefing_center .hw-news h3 a{color:#172b46!important;-webkit-text-fill-color:#172b46!important;opacity:1!important}
    .hw-news,.hw-news.lead{border:0;border-bottom:1px solid #e4eaf1;border-radius:0;background:#fff;padding:22px 0;margin:0;box-shadow:none}
    .hw-news h3{font-size:20px;font-weight:700}.hw-news p{font-size:16px!important;line-height:1.8;color:#45556a}.hw-digest{background:#f4f7fb;border:0;padding:18px 22px}.hw-digest p{font-size:15px!important;line-height:1.75;margin:5px 0}
    .st-key-hw_briefing_center [data-baseweb="tab-list"]{gap:24px;background:#fff;border-bottom:1px solid #dce4ee}
    .st-key-hw_briefing_center [data-baseweb="tab"]{background:transparent!important;border-radius:0!important;color:#647187!important;padding:12px 0;font-weight:500}
    .st-key-hw_briefing_center [aria-selected="true"]{color:#243f64!important;font-weight:700}
    .st-key-hw_briefing_center [data-baseweb="tab-highlight"]{background:#243f64}
    </style>""", unsafe_allow_html=True)
    from .presentation import CARD_CSS
    st.markdown("<style>"+CARD_CSS+"""
    .st-key-hw_briefing_center{max-width:860px;margin:auto;padding:0 4px;background:#fafbfd}
    .st-key-hw_briefing_center .hw-briefing-hero{background:#fff;padding:12px 8px 20px}
    .st-key-hw_briefing_center [data-baseweb="tab-list"]{gap:0;position:sticky;top:0;z-index:5;background:#fff}
    .st-key-hw_briefing_center [data-baseweb="tab"]{flex:1;min-height:48px;font-size:16px}
    .st-key-hw_briefing_center [data-baseweb="tab-highlight"]{background:#168b90}
    .st-key-hw_briefing_center button{min-height:44px}
    .hw-briefing-section{border:0;margin:20px 0 5px;padding:0;font-size:19px;font-weight:600}
    .hw-digest{background:#f0f5f9;border-radius:14px;margin:16px 0}
    .hw-digest .tag{color:#172b46;font-weight:600;font-size:17px}
    .st-key-hw_briefing_center .hw-edition{margin-top:14px}
    .st-key-hw_briefing_header .hw-weather-expanded{display:block;padding:16px 20px;background:linear-gradient(110deg,#f0f6ff,#e8f2ff);border:1px solid #dfebf8;border-radius:16px;color:#263c59;font-size:13px;line-height:1.5}
    .hw-weather-heading{display:flex;justify-content:space-between;gap:12px;color:#4d6380;margin-bottom:10px}.hw-weather-heading b{font-size:14px}
    .hw-weather-main{display:grid;grid-template-columns:64px minmax(110px,1fr) minmax(210px,1.6fr);gap:12px;align-items:center}
    .hw-weather-now{display:flex;flex-direction:column;gap:1px;white-space:nowrap}.hw-weather-current-label{font-size:12px;color:#5b6f88}.hw-weather-now strong{font-size:40px!important;line-height:1.1;letter-spacing:-1.5px;color:#183759;font-variant-numeric:tabular-nums}.hw-weather-range{margin-top:5px;font-size:12px}.hw-weather-range b:first-child{color:#3477ad}.hw-weather-range b:last-child{color:#a44e37}
    .hw-weather-expanded .hw-weather-large-icon svg{width:64px;height:64px}.hw-weather-expanded .hw-weather-symbol svg{width:38px;height:38px}
    .hw-weather-periods{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-left:1px solid #d4e1f0;padding-left:16px;gap:10px}.hw-weather-period{display:flex;align-items:center;flex-direction:column;gap:3px;text-align:center;min-width:0}.hw-weather-period>b{font-size:12px;font-weight:500;word-break:keep-all}.hw-weather-symbol{font-size:28px;line-height:1.2;color:#477fb6}.hw-weather-pop{font-size:12px;color:#345d88;white-space:nowrap}
    .hw-weather-advice{border-top:1px solid #d9e5f3;padding-top:9px;margin-top:12px;font-size:13px;color:#315475}.hw-weather-meta{margin-top:5px;font-size:10px;color:#596d84;line-height:1.5}.hw-weather-meta>span{display:block}
    @media(max-width:1100px){.st-key-hw_briefing_header [data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-hw_briefing_header [data-testid="stColumn"]{min-width:100%;width:100%}.st-key-hw_briefing_header .hw-briefing-hero{padding-bottom:8px}}
    @media(max-width:600px){.hw-weather-large-icon{display:none}.st-key-hw_briefing_header .hw-weather-expanded{padding:14px}.hw-weather-main{grid-template-columns:1fr;gap:14px}.hw-weather-now{display:grid;grid-template-columns:1fr 1fr;align-items:center;gap:2px 12px}.hw-weather-now strong{grid-column:1;grid-row:2 / 4}.hw-weather-now>span:nth-child(3){grid-column:2;grid-row:2}.hw-weather-range{grid-column:2;grid-row:3;margin:0}.hw-weather-periods{border-left:0;border-top:1px solid #d4e1f0;padding:12px 0 0;gap:8px}.hw-weather-meta{font-size:11px}}
    </style>""",unsafe_allow_html=True)


def render_body(body, *, large=False):
    import html
    e = lambda value: html.escape(str(value or ''), quote=True)
    render_style()
    issues = body.get('issues') or []
    representative = next((row for row in issues if row.get('representative')), None)
    ordered = ([representative] if representative else []) + [row for row in issues if row is not representative]
    if body.get('weather_forecast'):
        from .weather import weather_html
        st.markdown(weather_html(body['weather_forecast']),unsafe_allow_html=True)
    flow = body.get('market_flow') or []
    digest = flow
    if digest:
        label = '오늘의 경제·금융 흐름' if flow else '오늘의 핵심'
        st.markdown('<section class="hw-digest hw-market-flow'+(' big' if large else '')+'"><div class="tag">'+label+'</div>'+'<div class="hw-flow-copy">'+''.join('<p>'+e(text)+'</p>' for text in digest)+'</div></section>', unsafe_allow_html=True)
    from .public_body import metric_date, metric_change
    for m in body.get('market_metrics') or []:
        st.caption(f"{m['label']} · {m['value']} {m.get('unit','')} · {metric_change(m)} · {metric_date(m)} · {m.get('source_name','')}")
    more = [r for r in ordered if r.get('reading_group') == 'more']
    ordered = [r for r in ordered if r.get('reading_group') != 'more']
    last_group=None
    last_section = None
    for index, row in enumerate(ordered, 1):
        if row.get("section_label") and row["section_label"] != last_section:
            last_section = row["section_label"]
            st.markdown('<h2 class="hw-briefing-section">'+e(last_section)+'</h2>', unsafe_allow_html=True)
        group=row.get('reading_group') or 'main'
        if group != last_group:
            last_group=group
            st.markdown('<h2 class="hw-briefing-section">'+('더 읽을 기사' if group=='more' else '오늘의 주요 뉴스')+'</h2>',unsafe_allow_html=True)
        from .presentation import article_html
        st.markdown(article_html(row, lead=index==1, large=large), unsafe_allow_html=True)
    if more:
        with st.expander(f'더 읽을 기사 · {len(more)}건', expanded=False):
            for row in more:
                source = next((x for x in row.get('sources', []) if is_safe_url(str(x.get('url') or ''))), None)
                if source:
                    st.markdown('<a style="display:block;padding:12px 0;line-height:1.6" href="'+e(source['url'])+'" target="_blank" rel="noopener noreferrer">'+e(row.get('title'))+' ↗</a>', unsafe_allow_html=True)
    if not issues:
        st.info('이 판본에 저장된 요약 기사가 없습니다.')
    for kind,label in (('calendar','오늘 예정된 주요 발표 · KST'),):
        if body.get(kind):st.markdown('**'+label+'**')
        for item in body.get(kind) or []:
            st.write((stamp(item['scheduled_at'])+' · ' if item.get('scheduled_at') else '')+str(item.get('title') or ''))
            st.write(str(item.get('summary') or ''))
            for src in item.get('sources',[]):
                if is_safe_url(str(src.get('url') or '')):st.link_button(str(src.get('source_name') or '원문'),src['url'])
    if (body.get('research') or {}).get('reports'):
        render_research(body['research'])


def _views(rows):
    for r in rows:
        st.markdown('**'+str(r.get('firm') or '')+'**')
        st.write(str(r.get('summary') or ''))
        if r.get('conditions'):st.caption('조건·관찰 변수 · '+str(r['conditions']))


def render_research(research):
    st.subheader('증권사 리서치 종합')
    st.caption(f"자료 {research.get('report_count') or 0}개 · 기관 {research.get('institution_count') or 0}곳")
    if not research.get('reports'):
        st.info('이번 수집 기간에 확인할 수 있는 공개 리서치 자료가 없습니다. 휴일·자료 부족·출처 확인 실패일 수 있으며, 이전 자료를 오늘 자료로 표시하지 않습니다.')
    for common in research.get('common') or []:
        with st.container(border=True):
            st.markdown('**공통 견해 · '+str(common['theme'])+'**')
            st.caption(str(common['timeframe'])+' · '+' · '.join(common['firms']));_views(common['views'])
    for diff in research.get('differences') or []:
        with st.container(border=True):
            st.markdown('**의견 차이 · '+str(diff['theme'])+'**');st.caption(diff['timeframe'])
            a,b=st.columns(2)
            with a:st.markdown('**긍정적 관점**');_views(diff['positive'])
            with b:st.markdown('**신중한 관점**');_views(diff['cautious'])
    if research.get('reports') and not research.get('common'):st.caption('같은 주제와 기간에 대한 기관 간 공통 견해가 충분하지 않습니다.')
    with st.expander('기관별 견해와 원문 더 보기'):
        for theme in research.get('viewpoints') or []:
            st.markdown('**'+str(theme['theme'])+' · '+str(theme['timeframe'])+'**');_views(theme['views'])
        for report in research.get('reports') or []:
            st.caption(stamp(report.get('published_at')))
            if is_safe_url(str(report.get('url') or '')):st.link_button(str(report['firm'])+' · '+str(report['title']),report['url'])
    st.caption(str(research.get('note') or ''))


def render_public_entry(repo):
    token=str(st.query_params.get('briefing','') or '')
    if not token:return False
    packet=repo.public_share(token)
    if not packet:st.warning('이 공유 링크는 만료됐거나 공개가 중단됐습니다.');return True
    body=packet['body'];sender=packet.get('sender') or {}
    st.title(body.get('profile_label') or '오늘의 브리핑')
    st.caption(str(packet.get('briefing_date') or '')+' · '+str(sender.get('name') or '')+' '+str(sender.get('position') or ''))
    render_body(body)
    return True
