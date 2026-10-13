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
    .hw-briefing-hero{background:linear-gradient(125deg,#102b48,#214b72);border-radius:20px;padding:25px 28px;margin:0 0 20px;color:#fff}
    .hw-briefing-hero>span{font-size:11px;letter-spacing:2px;color:#b8d1e7}.hw-briefing-hero h1{color:#fff;font-size:30px;font-weight:750;margin:8px 0;line-height:1.25}.hw-briefing-hero p{font-size:15px!important;color:#dce8f4;margin:0}
    .hw-edition{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:24px 0 14px;color:#536579;font-size:13px}.hw-edition strong{font-size:21px;color:#172d45}.hw-edition-state{font-size:12px;background:#eaf0f7;color:#345579;padding:5px 10px;border-radius:30px}
    .hw-news{background:#fff;border:1px solid #dbe3ec;border-radius:16px;padding:22px 24px;margin:14px 0;color:#23384e;box-shadow:0 3px 14px rgba(20,40,70,.025)}.hw-news.lead{border-left:5px solid #284f77;background:#f8fbff}
    .hw-news .tag{color:#52708e;font-size:12px;font-weight:650;margin-bottom:10px}.hw-news h3{font-size:21px;line-height:1.48;margin:0 0 10px;color:#132c46}.hw-news.lead h3{font-size:24px}.hw-news p{font-size:17px!important;line-height:1.8;margin:0 0 14px;color:#34495f}.hw-news .source{font-size:12px;line-height:1.7;color:#64758a}.hw-news a{color:#235b8d;text-decoration:none}.hw-news h3 a{color:inherit}.hw-news a:hover{text-decoration:underline;text-underline-offset:3px}
    .hw-news .hw-context{border-top:1px solid #e4eaf0;padding-top:14px;margin-top:12px}.hw-news .hw-context h4{font-size:14px;color:#355774;margin:0 0 6px}.hw-news .hw-context p{font-size:16px!important;margin-bottom:12px}
    .hw-news.big h3{font-size:25px}.hw-news.big p{font-size:20px!important;line-height:1.85}
    .hw-market-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0 22px}.hw-market-metric{background:#fff;border:1px solid #dbe3ec;border-radius:14px;padding:17px}.hw-market-metric .name{font-size:13px;color:#52677d}.hw-market-metric .value{font-size:26px;font-weight:750;color:#172d45;margin:8px 0}.hw-market-metric .delta{font-size:14px;font-weight:650}.hw-market-metric .date{font-size:11px;color:#64758a;margin-top:8px}.hw-market-metric a{font-size:11px;color:#456988}.hw-market-metric .up{color:#ba3447}.hw-market-metric .down{color:#2864ad}.hw-market-metric .flat{color:#60738b}
    .st-key-hw_briefing_center button{min-height:42px}.st-key-hw_briefing_center [data-testid="stExpander"]{border-color:#dce4ee}.st-key-hw_briefing_center [data-testid="stRadio"]{margin:4px 0 10px}
    @media(max-width:640px){.hw-briefing-hero{padding:21px 20px}.hw-briefing-hero h1{font-size:27px}.hw-market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hw-news{padding:18px}.hw-news h3{font-size:20px}.hw-news.lead h3{font-size:22px}.hw-market-metric .value{font-size:22px}}
    @media(max-width:340px){.hw-market-grid{grid-template-columns:1fr}}
    </style>""", unsafe_allow_html=True)


def render_body(body, *, large=False):
    import html
    e = lambda value: html.escape(str(value or ''), quote=True)
    render_style()
    if body.get('profile_code') == 'MARKET':
        if body.get('market_flow'):
            with st.container(border=True):
                st.markdown('#### 오늘의 경제 흐름')
                for text in body['market_flow']:
                    st.write(text)
    issues = body.get('issues') or []
    representative = next((row for row in issues if row.get('representative')), None)
    ordered = ([representative] if representative else []) + [row for row in issues if row is not representative]
    for index, row in enumerate(ordered, 1):
        sources = [s for s in row.get('sources') or [] if is_safe_url(str(s.get('url') or ''))]
        primary = sources[0] if sources else None
        title = e(row.get('title') or '오늘의 소식')
        if primary:
            title = f'<a href="{e(primary["url"])}" target="_blank" rel="noopener noreferrer">{title}</a>'
        tag = ('중요 발표 추가 · ' if row.get('important_update') else '오늘의 주요 뉴스 · ' if row is representative else f'{index:02d} · ') + str(row.get('category') or '뉴스')
        source = ' · '.join([str(primary.get('source_name') or '원문'), stamp(primary.get('published_at'))]) if primary else ''
        classes = 'hw-news'+(' lead' if row is representative else '')+(' big' if large else '')
        explanation = ''
        if row.get('why_important'):
            explanation += f'<h4>배경</h4><p>{e(row["why_important"])}</p>'
        if row.get('impact_summary'):
            explanation += f'<h4>생활·금융에 미치는 영향</h4><p>{e(row["impact_summary"])}</p>'
        if explanation:
            explanation = '<div class="hw-context">'+explanation+'</div>'
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
    from .public_body import public_pdf
    st.download_button('PDF로 저장',public_pdf(packet),file_name='hwarang_briefing.pdf',mime='application/pdf')
    return True
