"""Mobile workspace navigation over the existing activity records and RLS."""
from datetime import date, datetime
from uuid import uuid4
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
    from modules.activity.kakao_settings import render_admin_entry, render_entry
    render_entry(prefix)
    auth_profile = st.session_state.get('hwarang_auth', {}).get('profile', {})
    render_admin_entry(auth_profile.get('role') == 'super_admin', prefix)
    st.divider()
    st.html('<button type="button" class="calendar-install" style="width:100%;min-height:44px;border:1px solid #d8e1e8;border-radius:8px;background:white;color:#18334c;font:inherit;cursor:pointer">홈 화면에 설치</button>')
    from modules.activity.launch import render_workspace_return
    render_workspace_return(prefix + '_workspace_return')
    st.button('로그아웃',key=prefix+'_logout',on_click=logout,width='stretch')


def cancel_pending_navigation():
    st.session_state.pop('mobile_pending',None)
    st.session_state.pop('mobile_pending_back',None)


@st.dialog('저장하지 않은 변경',width='small',dismissible=True,on_dismiss=cancel_pending_navigation)
def navigation_dialog():
    target=st.session_state.get('mobile_pending')
    if not target:return
    st.write('아직 저장되지 않은 내용이 있습니다. 이동 방법을 선택해 주세요.')
    if st.button('계속 작성',key='mobile_continue',type='primary',width='stretch'):
        cancel_pending_navigation();st.rerun()
    retain=st.button('내용 유지하고 이동',key='mobile_retain',width='stretch')
    discard=st.button('내용 버리고 이동',key='mobile_discard',width='stretch')
    if retain or discard:
        if discard:ux.clear_draft(st.session_state.get('sales_active_draft'))
        commit_page(target,st.session_state.get('mobile_pending_back',False))
        cancel_pending_navigation()
        st.rerun()


def pending_navigation():
    if st.session_state.get('mobile_pending'):navigation_dialog()


def accept_widget_date(params, state):
    """Apply only navigation hints, after the normal calendar login gate."""
    raw_day = params.get('widget_day')
    if raw_day is None:
        return
    scope = params.get('widget_scope', 'mine')
    for key in ('widget_day', 'widget_scope'):
        if key in params:
            del params[key]
    try:
        day = date.fromisoformat(raw_day)
    except (TypeError, ValueError):
        return
    if day.isoformat() != raw_day or not 1900 <= day.year <= 2100 or scope not in ('mine', 'branch'):
        return
    state.update(mobile_page='캘린더', sales_anchor=day, sales_view='날짜별',
                 sales_calendar_team=scope=='branch', sales_widget_day=raw_day)
    state.pop('sales_calendar_member', None)
    state.pop('sales_persistent_boot', None)
    state['calendar_scope_generation'] = 'widget_' + uuid4().hex


def run(logout):
    accept_widget_date(st.query_params, st.session_state)
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
    /* Calendar owns the scroll inside its viewport; other pages keep normal page scrolling. */
    [data-testid="stMain"]:has(.st-key-mobile_content iframe[title="modules.activity.center.sales_calendar_view"]){overflow-y:hidden!important}
    [data-testid="stMainBlockContainer"]:has(.st-key-mobile_content iframe[title="modules.activity.center.sales_calendar_view"]){padding-bottom:0!important}
    .st-key-mobile_stage:has(.st-key-mobile_content iframe[title="modules.activity.center.sales_calendar_view"]),.st-key-mobile_content:has(iframe[title="modules.activity.center.sales_calendar_view"]){min-height:0!important}
    .st-key-mobile_stage{position:relative;min-height:min(620px,78vh)}
    .st-key-mobile_stage .st-key-mobile_content{min-height:min(620px,78vh)}
    .st-key-mobile_header button{border:0!important;background:transparent!important;min-height:40px!important;padding:4px 10px!important}
    .st-key-mobile_header h3{margin:0;padding:0;font-size:1.15rem;white-space:nowrap}
    .st-key-mobile_header [data-testid="stHorizontalBlock"],.st-key-mobile_work_counts [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:6px!important}
    .st-key-mobile_header [data-testid="stColumn"],.st-key-mobile_work_counts [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important;width:0!important}
    .st-key-mobile_header [data-testid="stColumn"]:nth-child(2){flex:2 1 0!important}
    .st-key-mobile_work_counts button p,.st-key-mobile_header button p{font-size:12px!important}
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
        st.session_state['mobile_back_stack']=[p for p in st.session_state.get('mobile_back_stack',[]) if p not in ('오늘의 업무','알림·피드백','후속 할 일')]
        page=st.session_state.get('mobile_page','캘린더')
        allowed=[*menus(db),'주간 기록']
        if page not in allowed:page='캘린더';st.session_state['mobile_page']=page
        if page in ('활동 기록','주간 기록'):st.session_state['mobile_report_page']=page
        with st.sidebar:menu_items(db,logout,'side')
        with st.container(key='mobile_header'):
            a,b=st.columns([1,4])
            with a.container(key='mobile_menu_toggle'):
                with st.popover('☰',key='mobile_drawer_'+page+str(bool(st.session_state.get('mobile_pending')))):
                    st.html('<span class="mobile-drawer"></span>');menu_items(db,logout,'drawer')
            b.subheader('화랑 캘린더')
        st.html('<span class="mobile-navigation-state" data-page="'+page+'" data-depth="'+str(len(st.session_state.get('mobile_back_stack',[])))+'"></span>')
        st.button('이전 메뉴',key='mobile_history_back',on_click=previous_page)
        st.html('<style>.st-key-mobile_history_back{display:none!important}.mobile-navigation-state{display:none}</style>')
        pending_navigation()
        with st.container(key='mobile_content'):
            if page=='캘린더':
                st.html("""<button class="mobile-new-event" aria-label="일정 등록" title="일정 등록">＋</button><style>.mobile-new-event{position:fixed;right:20px;bottom:calc(20px + env(safe-area-inset-bottom,0px));width:52px;height:52px;border:0;border-radius:50%;background:#155461;color:white;font-size:28px;z-index:40;box-shadow:0 3px 12px #1234;cursor:pointer}</style><script>document.querySelector('.mobile-new-event').onclick=()=>document.querySelectorAll('iframe').forEach(f=>f.contentWindow.postMessage({type:'hwarang.activity.new'},location.origin));</script>""",unsafe_allow_javascript=True)
                center.calendar(db,today)
            elif page=='구성원 현황':center.overview(db,today)
            else:
                tab_key='mobile_record_tab'
                st.session_state[tab_key]='주간 요약' if page=='주간 기록' else '일일 기록'
                def select_record():choose('주간 기록' if st.session_state[tab_key]=='주간 요약' else '활동 기록')
                st.segmented_control('기록 구분',['일일 기록','주간 요약'],key=tab_key,required=True,on_change=select_record,label_visibility='collapsed')
                center.reports(db,today,'주간' if page=='주간 기록' else '일일')
                personal_performance(db,today)
        if st.session_state.get('sales_route') and not st.session_state.get('sales_dialog_rendered'):redesign.dialog(db)


@st.fragment
def personal_performance(db,today):
    with st.expander('내 청약·계약 실적',key='mobile_performance',on_change='rerun') as panel:
        if panel.open:center.performance(db,today,{db.uid:db.me},center.bounds,selected_member=db.uid,key='mobile_perf')
