"""Mobile workspace navigation over the existing activity records and RLS."""
from datetime import date, datetime
import streamlit as st
from modules.activity import center, redesign, ux
from modules.shared.hwarang_auth import HwarangAuthError

MENUS=('캘린더','활동 기록')


def menus(db):
    return [*MENUS,*(['구성원 현황'] if db.me['managed'] else [])]


def commit_page(target, backwards=False):
    current=st.session_state.get('mobile_page','캘린더')
    history=st.session_state.setdefault('mobile_back_stack',[])
    if target!=current:
        from modules.activity import read_state
        read_state.invalidate()
        if backwards:
            if history and history[-1]==target:history.pop()
        else:
            history.append(current)
            del history[:-30]
        st.session_state['mobile_page']=target
        if target=='캘린더':st.session_state['sales_view']='월간'
    st.session_state.pop('sales_active_draft',None)


def choose(target, backwards=False):
    if target==st.session_state.get('mobile_page','캘린더'):return
    active=st.session_state.get('sales_active_draft')
    if active and ux.dirty(active):
        st.session_state['mobile_pending']=target
        st.session_state['mobile_pending_back']=backwards
    else:
        commit_page(target,backwards)


def previous_page():
    history=st.session_state.get('mobile_back_stack',[])
    choose(history[-1] if history else '캘린더',backwards=True)


def menu_items(db,logout,prefix):
    st.markdown('**'+db.me['label']+'**')
    profile=st.session_state.get('login_profile') or {}
    affiliation=profile.get('organization_unit_name') or profile.get('organization_name')
    position=profile.get('position_name')
    if affiliation or position:st.caption(' · '.join(x for x in (affiliation,position) if x))
    for name in menus(db):
        st.button(name,key=prefix+'_nav_'+name,width='stretch',on_click=choose,args=(st.session_state.get('mobile_report_page','활동 기록') if name=='활동 기록' else name,),
                  type='primary' if ('활동 기록' if st.session_state.get('mobile_page')=='주간 기록' else st.session_state.get('mobile_page','캘린더'))==name else 'secondary')
    from modules.activity.view_scope import render_settings
    render_settings(prefix)
    st.divider()
    st.html('<button type="button" class="calendar-install" style="width:100%;min-height:44px;border:1px solid #d8e1e8;border-radius:8px;background:white;color:#18334c;font:inherit;cursor:pointer">홈 화면에 설치</button>')
    from modules.activity.launch import render_workspace_return
    render_workspace_return(prefix + '_workspace_return')
    st.button('로그아웃',key=prefix+'_logout',on_click=logout,width='stretch')


def pending_navigation():
    target=st.session_state.get('mobile_pending')
    if not target:return
    st.warning('저장하지 않은 기록이 있습니다. 이동 방법을 선택해 주세요.')
    a,b,c=st.columns(3)
    if a.button('계속 작성',key='mobile_continue'):
        st.session_state.pop('mobile_pending',None);st.session_state.pop('mobile_pending_back',None);st.rerun()
    retain=b.button('내용 유지하고 이동',key='mobile_retain')
    discard=c.button('내용 버리고 이동',key='mobile_discard')
    if retain or discard:
        if discard:ux.clear_draft(st.session_state.get('sales_active_draft'))
        commit_page(target,st.session_state.pop('mobile_pending_back',False))
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


@st.dialog('알림·피드백', width='large', dismissible=True, on_dismiss='rerun')
def alerts_dialog(db):
    alerts(db)
    if st.button('닫기', key='mobile_alerts_close', use_container_width=True):
        st.rerun()


@st.fragment
def alert_button(db):
    # Keep the trigger in the header's normal layout; only this fragment reruns
    # when opening notifications, rather than rebuilding the entire page.
    unread=db.request('GET','sales_notices',{'seen':'eq.false','select':'id','limit':'50'})
    label='알림'+(' '+str(len(unread))+('+' if len(unread)==50 else '') if unread else '')
    with st.container(key='mobile_alert_trigger'):
        if st.button(label,icon=':material/notifications:',key='mobile_alerts',width='stretch'):
            alerts_dialog(db)


def run(logout):
    ux.styles()
    import streamlit.components.v1 as components
    from pathlib import Path
    components.html(Path(__file__).with_name('calendar_bridge.html').read_text(),height=0)
    st.html('''<style>
    [data-testid="stHeader"]{display:none}.block-container{padding-top:.4rem!important;padding-bottom:2rem!important;max-width:1200px}
    body:has(.st-key-mobile_header) [data-testid="stMain"] [data-testid="stMainBlockContainer"]{padding-top:0!important}
    body:has(.st-key-mobile_header) [data-testid="stElementContainer"]:has(iframe[title="modules.activity.device.workspace_device"]){display:none}
    body:has(.st-key-mobile_header) [data-testid="stMain"] [data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"]{gap:.4rem!important}
    body:has(.st-key-mobile_header) [data-testid="stElementContainer"]:has(> [data-testid="stEmpty"]){display:none!important}
    .st-key-mobile_content [data-testid="stVerticalBlock"]{gap:6px}
    .st-key-mobile_stage{position:relative;min-height:min(620px,78vh)}
    .st-key-mobile_stage .st-key-mobile_content{min-height:min(620px,78vh)}
    .st-key-mobile_header button{border:0!important;background:transparent!important;min-height:40px!important;padding:4px 10px!important}
    .st-key-mobile_header h3{margin:0;padding:0;font-size:1.15rem;white-space:nowrap}
    .st-key-mobile_header [data-testid="stHorizontalBlock"],.st-key-mobile_work_counts [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:6px!important}
    .st-key-mobile_header [data-testid="stColumn"],.st-key-mobile_work_counts [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important;width:0!important}
    .st-key-mobile_header [data-testid="stColumn"]:nth-child(2){flex:2 1 0!important}
    .st-key-mobile_work_counts button p,.st-key-mobile_header button p{font-size:12px!important}
    .st-key-mobile_alert_trigger{min-height:48px!important;min-width:92px!important}
    .st-key-mobile_alert_trigger button{min-height:48px!important;border:1px solid #d5dfed!important;border-radius:12px!important;background:#fff!important;padding:8px 12px!important}
    .st-key-mobile_header .st-key-mobile_alert_trigger button p{font-size:15px!important;font-weight:650!important;white-space:nowrap}
    .st-key-mobile_alert_trigger [data-testid="stIconMaterial"]{font-size:24px!important}
    @media(min-width:701px){.st-key-mobile_menu_toggle{display:none}}
    @media(max-width:700px){[data-testid="stSidebar"]{display:none!important}
    [data-testid="stPopoverBody"]:has(.mobile-drawer){position:fixed!important;inset:0 auto 0 0!important;width:min(84vw,320px)!important;max-height:100dvh!important;overflow:auto;border-radius:0!important;padding-top:env(safe-area-inset-top,12px)}
    .st-key-mobile_header{position:sticky;top:0;z-index:20;background:#f5f7fa;padding:0}
    .st-key-mobile_content input,.st-key-mobile_content textarea{font-size:16px!important}}
    </style>''')
    from contextlib import nullcontext
    standalone = bool(st.session_state.get('_calendar_deployment'))
    with st.container(key='mobile_stage') if standalone else nullcontext():
        shell_slot = None
        if standalone:
            from modules.activity.loading import calendar_shell
            shell_slot = st.empty()
            requested_page = st.session_state.get('mobile_page', '캘린더')
            if st.session_state.get('_calendar_shell_page') != requested_page:
                calendar_shell(requested_page, slot=shell_slot)
        try:
            db=center.Records();today=datetime.now(center.KST).date()
        finally:
            if shell_slot is not None: shell_slot.empty()
        if standalone: st.session_state['_calendar_shell_page'] = requested_page
        st.session_state['sales_dialog_rendered']=False
        # Preserve navigation widgets when another menu temporarily unmounts them.
        for key in ('sales_calendar_member','sales_calendar_team','sales_day_일일','sales_day_주간','sales_overview_day','sales_overview_period','sales_overview_unit','sales_member_search','sales_member_status','mobile_work_mode','mobile_work_tab'):
            if key in st.session_state:st.session_state[key]=st.session_state[key]
        st.session_state['mobile_back_stack']=[p for p in st.session_state.get('mobile_back_stack',[]) if p!='오늘의 업무']
        page=st.session_state.get('mobile_page','캘린더')
        allowed=[*menus(db),'주간 기록','알림·피드백']
        if page not in allowed:page='캘린더';st.session_state['mobile_page']=page
        if page in ('활동 기록','주간 기록'):st.session_state['mobile_report_page']=page
        with st.sidebar:menu_items(db,logout,'side')
        with st.container(key='mobile_header'):
            a,b,c=st.columns([1,3,1])
            with a.container(key='mobile_menu_toggle'):
                with st.popover('☰',key='mobile_drawer_'+page+str(bool(st.session_state.get('mobile_pending')))):
                    st.html('<span class="mobile-drawer"></span>');menu_items(db,logout,'drawer')
            b.subheader('화랑 캘린더')
            with c:alert_button(db)
        st.html('<span class="mobile-navigation-state" data-page="'+page+'" data-depth="'+str(len(st.session_state.get('mobile_back_stack',[])))+'"></span>')
        st.button('이전 메뉴',key='mobile_history_back',on_click=previous_page)
        st.html('<style>.st-key-mobile_history_back{display:none!important}.mobile-navigation-state{display:none}</style>')
        pending_navigation()
        with st.container(key='mobile_content'):
            if page=='캘린더':
                st.html("""<button class="mobile-new-event" aria-label="일정 등록" title="일정 등록">＋</button><style>.mobile-new-event{position:fixed;right:20px;bottom:calc(20px + env(safe-area-inset-bottom,0px));width:52px;height:52px;border:0;border-radius:50%;background:#155461;color:white;font-size:28px;z-index:40;box-shadow:0 3px 12px #1234;cursor:pointer}</style><script>document.querySelector('.mobile-new-event').onclick=()=>document.querySelectorAll('iframe').forEach(f=>f.contentWindow.postMessage({type:'hwarang.activity.new'},location.origin));</script>""",unsafe_allow_javascript=True)
                center.calendar(db,today)
            elif page=='구성원 현황':center.overview(db,today)
            elif page=='알림·피드백':alerts(db)
            else:
                tab_key='mobile_record_tab'
                st.session_state[tab_key]='주간 기록' if page=='주간 기록' else '일일 기록'
                def select_record():choose('주간 기록' if st.session_state[tab_key]=='주간 기록' else '활동 기록')
                st.segmented_control('기록 구분',['일일 기록','주간 기록'],key=tab_key,required=True,on_change=select_record,label_visibility='collapsed')
                center.reports(db,today,'주간' if page=='주간 기록' else '일일')
                personal_performance(db,today)
        if st.session_state.get('sales_route') and not st.session_state.get('sales_dialog_rendered'):redesign.dialog(db)


@st.fragment
def personal_performance(db,today):
    with st.expander('내 청약·계약 실적',key='mobile_performance',on_change='rerun') as panel:
        if panel.open:center.performance(db,today,{db.uid:db.me},center.bounds,selected_member=db.uid,key='mobile_perf')
