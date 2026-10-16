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


def render_body(body, *, large=False):
    import html
    e = lambda value: html.escape(str(value or ''), quote=True)
    render_style()
    issues = body.get('issues') or []
    representative = next((row for row in issues if row.get('representative')), None)
    ordered = ([representative] if representative else []) + [row for row in issues if row is not representative]
    flow = body.get('market_flow') or []
    digest = flow[:3]
    if digest:
        label = '오늘의 경제·금융 흐름' if flow else '오늘의 핵심'
        st.markdown('<section class="hw-digest'+(' big' if large else '')+'"><div class="tag">'+label+'</div>'+''.join('<p>'+e(text)+'</p>' for text in digest)+'</section>', unsafe_allow_html=True)
    last_section = None
    for index, row in enumerate(ordered, 1):
        if row.get("section_label") and row["section_label"] != last_section:
            last_section = row["section_label"]
            st.markdown('<h2 class="hw-briefing-section">'+e(last_section)+'</h2>', unsafe_allow_html=True)
        sources = [s for s in row.get('sources') or [] if is_safe_url(str(s.get('url') or ''))]
        primary = sources[0] if sources else None
        title = e(row.get('title') or '오늘의 소식')
        if primary:
            title = f'<a href="{e(primary["url"])}" target="_blank" rel="noopener noreferrer">{title}</a>'
        tag = ('중요 발표 추가 · ' if row.get('important_update') else '오늘의 주요 뉴스 · ' if row is representative else f'{index:02d} · ') + str(row.get('category') or '뉴스')
        source = ' · '.join([str(primary.get('source_name') or '원문'), stamp(primary.get('published_at'))]) if primary else ''
        classes = 'hw-news'+(' lead' if row is representative else '')+(' big' if large else '')
        explanation = ''
        st.markdown(f'<article class="{classes}"><div class="tag">{e(tag)}</div><h3>{title}</h3><p>{e(row.get("summary"))}</p>'+explanation+f'<div class="source">{e(source)}'+(f' · <a href="{e(primary["url"])}" target="_blank" rel="noopener noreferrer">원문 읽기 ↗</a>' if primary else '')+'</div></article>', unsafe_allow_html=True)
        if len(sources) > 1:
            with st.expander('추가 출처 보기'):
                for src in sources[1:]:
                    st.link_button(str(src.get('source_name') or '추가 원문'), src['url'])
    if not issues:
        st.info('이 판본에 저장된 요약 기사가 없습니다.')
    links = body.get('source_links') or []
    if links:
        with st.expander(f'더 읽을 기사 · 원문 {len(links)}개'):
            st.caption('수집된 원문 목록입니다. 요약·검증이 끝난 기사 수와 별도로 표시합니다.')
            for source in links:
                if is_safe_url(str(source.get('url') or '')):
                    st.link_button(str(source.get('title') or '원문'), source['url'], use_container_width=True)
                    st.caption(str(source.get('source_name') or '')+' · '+stamp(source.get('published_at')))
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
