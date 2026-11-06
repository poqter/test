"""Mobile workspace navigation over the existing activity records and RLS."""
from datetime import date, datetime
import streamlit as st
from modules.activity import center, redesign, ux
from modules.shared.hwarang_auth import HwarangAuthError

MENUS=('캘린더','오늘의 업무','활동 기록','후속 할 일')


def menus(db):
    return [*MENUS,*(['구성원 현황'] if db.me['managed'] else [])]


def choose(target):
    active=st.session_state.get('sales_active_draft')
    if active and ux.dirty(active):
        st.session_state['mobile_pending']=target
    else:
        st.session_state['mobile_page']=target
        st.session_state.pop('sales_active_draft',None)


def menu_items(db,logout,prefix):
    st.markdown('**'+db.me['label']+'**')
    profile=st.session_state.get('login_profile') or {}
    affiliation=profile.get('organization_unit_name') or profile.get('organization_name')
    position=profile.get('position_name')
    if affiliation or position:st.caption(' · '.join(x for x in (affiliation,position) if x))
    for name in menus(db):
        st.button(name,key=prefix+'_nav_'+name,width='stretch',on_click=choose,args=(st.session_state.get('mobile_report_page','활동 기록') if name=='활동 기록' else name,),
                  type='primary' if ('활동 기록' if st.session_state.get('mobile_page')=='주간 기록' else st.session_state.get('mobile_page','캘린더'))==name else 'secondary')
    st.divider()
    st.link_button('WORKSPACE 열기','https://hwarang-workspace.streamlit.app/',width='stretch')
    st.button('로그아웃',key=prefix+'_logout',on_click=logout,width='stretch')


def pending_navigation():
    target=st.session_state.get('mobile_pending')
    if not target:return
    st.warning('저장하지 않은 기록이 있습니다. 이동 방법을 선택해 주세요.')
    a,b,c=st.columns(3)
    if a.button('계속 작성',key='mobile_continue'):
        st.session_state.pop('mobile_pending',None);st.rerun()
    retain=b.button('내용 유지하고 이동',key='mobile_retain')
    discard=c.button('내용 버리고 이동',key='mobile_discard')
    if retain or discard:
        if discard:ux.clear_draft(st.session_state.get('sales_active_draft'))
        st.session_state['mobile_page']=target
        st.session_state.pop('mobile_pending',None)
        st.session_state.pop('sales_active_draft',None)
        st.rerun()


def overdue(row,today):
    if row['status']!='예정':return False
    if row['day']<str(today):return True
    stamp=row.get('end_time') or row.get('start_time')
    return row['day']==str(today) and bool(stamp and stamp<datetime.now(center.KST).strftime('%H:%M:%S'))


def work_data(db,today):
    events=db.request('GET','sales_events',{'owner':'eq.'+db.uid,'day':'lte.'+str(today),'status':'eq.예정','order':'day.desc'})
    todays=db.period('sales_events',today,today,owner='eq.'+db.uid,order='start_time.asc.nullsfirst')
    tasks=db.request('GET','sales_followups',{'owner':'eq.'+db.uid,'scheduled':'is.null','order':'due.asc'})
    return todays,[r for r in events if overdue(r,today)],tasks


@st.fragment(run_every='30s')
def summary(db,today):
    db._reads.clear()
    events,missing,tasks=work_data(db,today)
    with st.container(key='mobile_work_counts'):
        a,b,c=st.columns(3)
    for slot,label,count,section in [(a,'오늘 일정',len(events),'오늘 일정'),(b,'결과 미입력',len(missing),'결과 미입력'),(c,'할 일',len(tasks),'후속 할 일')]:
        def select(section=section):
            st.session_state['mobile_work_section']=section
            if section!='후속 할 일':st.session_state['mobile_work_tab']=section
            choose('후속 할 일' if section=='후속 할 일' else '오늘의 업무')
            st.rerun()
        slot.button(f'{label} {count}',key='mobile_count_'+section,on_click=select,width='stretch')


@st.fragment
def tasks_view(db,today):
    db._reads.clear();ux.feedback()
    st.subheader('후속 할 일')
    tasks=db.request('GET','sales_followups',{'owner':'eq.'+db.uid,'scheduled':'is.null','order':'due.asc'})
    if not tasks:st.info('남아 있는 후속 할 일이 없습니다. 일정 상세의 ‘다음 활동 추가’에서 할 일을 등록할 수 있습니다.')
    for task in tasks:
        with st.container(border=True):
            st.markdown('**'+task['title']+'**')
            st.caption(task['due']+(' · 기한 지남' if task['due']<str(today) else ' · 오늘' if task['due']==str(today) else ''))
            if st.button('연결된 일정 보기',key='task_source_'+task['id']):ux.navigate({'type':'event','id':task['source']})
            with st.expander('일정으로 전환',key='task_panel_'+task['id'],on_change='rerun'):
                with st.form('mobile_task_'+task['id']):
                    target=st.date_input('일정 날짜',max(today,date.fromisoformat(task['due'])))
                    kind=st.selectbox('활동 종류',center.KINDS)
                    if st.form_submit_button('일정으로 등록',type='primary'):
                        try:
                            event_id=db.request('POST','rpc/schedule_sales_followup',body={'task':task['id'],'schedule_day':str(target),'activity':kind})
                            st.session_state['sales_dialog_notice']='일정으로 전환했습니다.'
                            if isinstance(event_id,str):ux.navigate({'type':'event','id':event_id})
                            ux.refresh()
                        except HwarangAuthError as exc:st.error(str(exc))


@st.fragment
def today_view(db,today):
    db._reads.clear()
    st.subheader('오늘의 업무')
    if db.me['managed']:
        mode=st.segmented_control('업무 범위',['내 업무','관리 현황'],default='내 업무',required=True,key='mobile_work_mode')
        if mode=='관리 현황':
            st.caption('기존 조회 권한 범위의 구성원입니다.')
            redesign.overview(db,today)
            return
    events,missing,tasks=work_data(db,today)
    sections=['오늘 일정','결과 미입력']
    selected=st.session_state.get('mobile_work_section','오늘 일정')
    selected=selected if selected in sections else sections[0]
    which=st.segmented_control('확인할 업무',sections,default=selected,required=True,key='mobile_work_tab')
    redesign.event_list(db,events if which=='오늘 일정' else missing,'mobile_work_')
    if st.button('오늘 일일 기록 작성',type='primary'):
        st.session_state['sales_day_일일']=today
        ux.navigate({'type':'daily','day':str(today)})
    due=[r for r in tasks if r['due']<=str(today)]
    if due:st.caption(f'오늘까지 처리할 후속 할 일 {len(due)}건 · 후속 할 일 메뉴에서 확인하세요.')


@st.fragment
def alerts(db):
    db._reads.clear();st.subheader('알림·피드백')
    rows=db.request('GET','sales_notices',{'order':'created_at.desc','limit':'50'})
    if not rows:st.info('일정 알림이 없습니다.')
    for row in rows:
        with st.container(border=True):
            st.write(('● ' if not row['seen'] else '')+row['message'])
            st.caption(datetime.fromisoformat(row['created_at'].replace('Z','+00:00')).astimezone(center.KST).strftime('%m.%d %H:%M'))
            if st.button('해당 일정 보기',key='mobile_notice_'+row['id']):
                db.request('PATCH','sales_notices',{'id':'eq.'+row['id']},{'seen':True})
                ux.navigate({'type':'event','id':row['event']})
    st.caption('최근 알림 최대 50개 · 일정 상세에서 의견을 확인할 수 있습니다.')
    with st.expander('기록에 남긴 최근 피드백',key='mobile_report_feedback',on_change='rerun') as panel:
        if panel.open:
            reviews=db.request('GET','sales_reviews',{'report':'not.is.null','order':'created_at.desc','limit':'30','select':'id,message,created_at,report,sales_reports(owner,day,period)'})
            for item in reviews:
                report=item.get('sales_reports') or {}
                if report.get('owner')!=db.uid:continue
                st.write(item['message'])
                st.caption(report.get('day','')+' · '+report.get('period',''))
                if st.button('기록 보기',key='mobile_review_'+item['id']):
                    period=report['period']
                    st.session_state['sales_day_'+period]=date.fromisoformat(report['day'])
                    choose('활동 기록' if period=='일일' else '주간 기록');st.rerun()


def run(logout):
    ux.styles()
    st.html('''<style>
    [data-testid="stHeader"]{display:none}.block-container{padding-top:1rem!important;padding-bottom:2rem!important;max-width:1200px}
    .st-key-mobile_header h3{margin:0;padding:0;font-size:1.15rem;white-space:nowrap}
    .st-key-mobile_header [data-testid="stHorizontalBlock"],.st-key-mobile_work_counts [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:6px!important}
    .st-key-mobile_header [data-testid="stColumn"],.st-key-mobile_work_counts [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important;width:0!important}
    .st-key-mobile_header [data-testid="stColumn"]:nth-child(2){flex:2 1 0!important}
    .st-key-mobile_work_counts button p,.st-key-mobile_header button p{font-size:12px!important}
    @media(min-width:701px){.st-key-mobile_menu_toggle{display:none}}
    @media(max-width:700px){[data-testid="stSidebar"]{display:none!important}
    [data-testid="stPopoverBody"]:has(.mobile-drawer){position:fixed!important;inset:0 auto 0 0!important;width:min(84vw,320px)!important;max-height:100dvh!important;overflow:auto;border-radius:0!important;padding-top:env(safe-area-inset-top,12px)}
    .st-key-mobile_header{position:sticky;top:0;z-index:20;background:#f5f7fa;padding:4px 0}
    .st-key-mobile_content input,.st-key-mobile_content textarea{font-size:16px!important}}
    </style>''')
    db=center.Records();today=datetime.now(center.KST).date()
    st.session_state['sales_dialog_rendered']=False
    # Preserve navigation widgets when another menu temporarily unmounts them.
    for key in ('sales_calendar_member','sales_day_일일','sales_day_주간','sales_overview_day','sales_overview_period','sales_overview_unit','sales_member_search','sales_member_status','mobile_work_mode','mobile_work_tab'):
        if key in st.session_state:st.session_state[key]=st.session_state[key]
    page=st.session_state.get('mobile_page','캘린더')
    allowed=[*menus(db),'주간 기록','알림·피드백']
    if page not in allowed:page='캘린더';st.session_state['mobile_page']=page
    if page in ('활동 기록','주간 기록'):st.session_state['mobile_report_page']=page
    with st.sidebar:menu_items(db,logout,'side')
    with st.container(key='mobile_header'):
        a,b,c=st.columns([1,3,1])
        with a.container(key='mobile_menu_toggle'):
            with st.popover('☰ 메뉴',key='mobile_drawer_'+page+str(bool(st.session_state.get('mobile_pending')))):
                st.html('<span class="mobile-drawer"></span>');menu_items(db,logout,'drawer')
        b.subheader('화랑 캘린더')
        unread=db.request('GET','sales_notices',{'seen':'eq.false','select':'id','limit':'50'})
        c.button('🔔 '+(str(len(unread))+'+' if len(unread)==50 else str(len(unread))) if unread else '🔔 알림',on_click=choose,args=('알림·피드백',),key='mobile_alerts')
    pending_navigation()
    with st.container(key='mobile_content'):
        if page=='캘린더':
            summary(db,today)
            center.calendar(db,today)
        elif page=='오늘의 업무':today_view(db,today)
        elif page=='후속 할 일':tasks_view(db,today)
        elif page=='구성원 현황':center.overview(db,today)
        elif page=='알림·피드백':alerts(db)
        else:
            a,b=st.columns(2)
            a.button('일일 기록',on_click=choose,args=('활동 기록',),key='mobile_daily',type='primary' if page=='활동 기록' else 'secondary')
            b.button('주간 기록',on_click=choose,args=('주간 기록',),key='mobile_weekly',type='primary' if page=='주간 기록' else 'secondary')
            center.reports(db,today,'주간' if page=='주간 기록' else '일일')
            with st.expander('내 청약·계약 실적',key='mobile_performance',on_change='rerun') as panel:
                if panel.open:center.performance(db,today,{db.uid:db.me},center.bounds,selected_member=db.uid,key='mobile_perf')
    if st.session_state.get('sales_route') and not st.session_state.get('sales_dialog_rendered'):redesign.dialog(db)
