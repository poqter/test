"""Shared renderer for staff and customers, from the same public DTO."""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from .normalize import is_safe_url


def stamp(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y.%m.%d %H:%M')
    except (ValueError,TypeError):return str(value or '기준일 미확인')


def render_body(body):
    st.markdown('<style>[data-testid="stMarkdownContainer"] p{font-size:17px;line-height:1.8}[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px} @media(max-width:640px){[data-testid="stMarkdownContainer"] p{font-size:17px}}</style>',unsafe_allow_html=True)
    if body.get('profile_code')=='MARKET':
        st.subheader('시장 지표')
        items=body.get('market_metrics') or []
        if not items:st.info('출처·기준일·표시 권한이 확인된 시장 지표를 기다리고 있습니다.')
        for i in range(0,len(items),3):
            for col,m in zip(st.columns(min(3,len(items)-i)),items[i:i+3]):
                with col,st.container(border=True):
                    from .public_body import metric_change
                    delta=metric_change(m)
                    st.metric(str(m['label']),f"{m['value']:,.2f} {m['unit']}",delta=delta,delta_color='off')
                    st.caption(stamp(m.get('observed_at'))+' · '+str(m.get('observation_kind') or ''))
                    if is_safe_url(str(m.get('source_url') or '')):st.link_button(str(m.get('source_name') or '출처'),m['source_url'])
        if body.get('market_flow'):
            st.subheader('오늘의 시장 흐름')
            for text in body['market_flow']:st.write(text)
    for row in body.get('issues') or []:
        with st.container(border=True):
            st.caption(str(row.get('category') or '')+(' · 대표 뉴스' if row.get('representative') else ''))
            st.subheader(str(row.get('title') or '오늘의 소식'))
            st.write(str(row.get('summary') or ''))
            for src in row.get('sources') or []:
                st.caption(str(src.get('source_name') or '출처')+' · '+stamp(src.get('published_at')))
                if is_safe_url(str(src.get('url') or '')):st.link_button('원문 · '+str(src.get('title') or src.get('source_name') or '기사'),src['url'])
            if row.get('why_important') or row.get('impact_summary'):
                with st.expander('의미와 영향 더 보기'):
                    if row.get('why_important'):st.write(row['why_important'])
                    if row.get('impact_summary'):st.write(row['impact_summary'])
    if not body.get('issues'):st.info('이 날짜에 확인된 뉴스가 없습니다. 부족한 내용을 임의로 채우지 않습니다.')
    if body.get('profile_code')=='MARKET':render_research(body.get('research') or {})


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
