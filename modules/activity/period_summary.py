"""Daily submissions are the sole activity source; period views never write copies."""
from datetime import timedelta
from calendar import monthrange
import streamlit as st
from modules.activity import ux
from modules.activity.daily import COUNTS


def period_bounds(day, mode):
    if mode in ('월간', '이번 달'):
        return day.replace(day=1), day.replace(day=monthrange(day.year, day.month)[1])
    if mode in ('주간', '이번 주'):
        first = day - timedelta(days=day.weekday())
        return first, first + timedelta(days=6)
    return day, day


def daily_rows(rows, start, end, owners=None):
    # Ignore legacy weekly copies, drafts, and duplicate older revisions.
    found = {}
    for row in rows:
        if row.get('period') != '일일' or not row.get('submitted'): continue
        if not str(start) <= row['day'] <= str(end): continue
        if owners is not None and row['owner'] not in owners: continue
        key = row['owner'], row['day']
        if key not in found or row.get('revision', 0) > found[key].get('revision', 0): found[key] = row
    return sorted(found.values(), key=lambda r: (r['day'], r['owner']))


def totals(rows):
    return ux.report_totals(rows, COUNTS)


def date_table(rows, start, end, members, today):
    submitted = daily_rows(rows, start, end, members)
    result = []
    for i in range((end-start).days+1):
        day = start + timedelta(days=i)
        own = [r for r in submitted if r['day'] == str(day)]
        result.append({'날짜': f'{day:%m/%d} {"월화수목금토일"[day.weekday()]}', **totals(own),
                       '제출': f'{len(own)}/{len(members)}명' if day <= today else '예정'})
    return result


def table(rows, start, end, members, today):
    data = date_table(rows, start, end, members, today)
    data.append({'날짜': '기간 합계', **totals(daily_rows(rows,start,end,members)), '제출': ''})
    st.dataframe(data, hide_index=True, width='stretch', height=min(600, 38*(len(data)+1)),
                 column_config={'날짜':st.column_config.TextColumn(pinned=True)})


def render(db, today):
    from modules.activity import manager_ui as ui
    from modules.activity.center import report_detail
    ui.styles()
    st.session_state.pop('sales_active_draft', None)
    st.session_state.setdefault('sales_day_주간', today)
    def move(delta):
        st.session_state['sales_day_주간'] = min(today, st.session_state['sales_day_주간']+timedelta(days=delta))
    with st.container(horizontal=True,vertical_alignment='center'):
        st.button('‹',key='summary_prev',on_click=move,args=(-7,))
        anchor=st.date_input('조회 주간',key='sales_day_주간',max_value=today,label_visibility='collapsed')
        st.button('›',key='summary_next',on_click=move,args=(7,),disabled=anchor>=today)
        st.button('이번 주',key='summary_today',on_click=lambda:st.session_state.update({'sales_day_주간':today}))
    start,end=period_bounds(anchor,'주간')
    from modules.activity.live_sync import attach
    attach(db,start,end,db.uid)
    if hasattr(db,'activity_bundle'):db.activity_bundle(start,end,db.uid)
    rows=db.period('sales_reports',start,end,owner='eq.'+db.uid)
    daily=daily_rows(rows,start,end,{db.uid})
    st.caption(f'{start:%Y.%m.%d} – {end:%m.%d} · 제출된 일일 기록 자동 합산')
    from modules.activity.manager import required_days
    due={str(d) for d in required_days(start,end,today)}
    submitted={r['day'] for r in daily}
    missing=len(due-submitted)
    st.caption(f'오늘까지 일일 기록 {len(due & submitted)}/{len(due)}일 제출 · '+(f'미제출 {missing}일' if missing else '대상 일일 기록 제출 완료'))
    ui.counts(totals(daily))
    table(rows,start,end,{db.uid:db.me},today)
    for row in daily:
        with st.expander(row['day']+' · 일일 기록',key='summary_day_'+row['id'],on_change='rerun') as panel:
            if panel.open:report_detail(db,row)
    if not daily:st.info('일일 기록을 제출하면 이곳에 자동으로 반영됩니다.')
    def write_daily():
        if st.query_params.get('view')=='mobile-calendar':
            from modules.activity.mobile import choose
            choose('활동 기록')
        else:st.session_state['sales_menu']='일일 기록'
    if st.button('일일 기록 작성',key='summary_write'):
        write_daily()
        # This view runs inside the reports fragment; the parent owns its menu.
        st.rerun()
    legacy=[r for r in rows if r.get('period')=='주간']
    if legacy:
        with st.expander('이전 주간 제출 기록 · 보관',key='summary_legacy',on_change='rerun') as panel:
            if panel.open:
                for row in legacy:report_detail(db,row)
