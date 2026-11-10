"""Manager summaries built from the caller's authorized records, without extra writes."""
from collections import defaultdict
from datetime import timedelta
import streamlit as st
from modules.activity import ux

CODES=('TA','AP','PC','CS')

def required_days(start,end,today):
    return [start+timedelta(days=i) for i in range((end-start).days+1)
            if start+timedelta(days=i)<=today and (start==end or (start+timedelta(days=i)).weekday()<5)]

def summarize(members,events,reports,contracts,tasks,start,end,today,now):
    grouped={kind:defaultdict(list) for kind in ('events','reports','contracts','tasks')}
    for kind,rows in zip(grouped,(events,reports,contracts,tasks)):
        for row in rows:
            if row.get('owner') in members:grouped[kind][row['owner']].append(row)
    due={str(d) for d in required_days(start,end,today)}
    result=[]
    for uid,member in members.items():
        own=[e for e in grouped['events'][uid] if not e.get('deleted_at')]
        daily=[r for r in grouped['reports'][uid] if r['period']=='일일' and r['submitted']]
        submitted={r['day'] for r in daily}&due
        missing=[e for e in own if e['kind']!='휴무' and e['status']=='예정' and (e['day']<str(today) or e['day']==str(today) and (e.get('end_time') or e.get('start_time') or '23:59:59')<now.strftime('%H:%M:%S'))]
        support=[dict(type='event',id=e['id'],day=e['day'],text=e['help']) for e in own if e.get('help') and e['status'] not in ('취소','연기')]
        support += [dict(type='report',id=r['id'],day=r['day'],text=r['data']['help']) for r in grouped['reports'][uid] if r['submitted'] and r['data'].get('help')]
        overdue=[t for t in grouped['tasks'][uid] if not t.get('scheduled') and t['due']<str(today)]
        result.append(dict(uid=uid,name=member['label'],counts={k:sum(e['kind']==k and e['status']=='완료' for e in own) for k in CODES},
            submitted=len(submitted),required=len(due),unsubmitted=len(due-submitted),missing=len(missing),help=len(support),late=len(overdue),
            contracts=len(grouped['contracts'][uid]),support=support,tasks=overdue))
    return result

def registration_summary(db,today,members):
    """Retain the calendar's registration summary in its single management home."""
    from modules.activity.status_policy import unregistered_exclusions, summary_groups
    with st.expander('오늘의 일정 등록 현황',key='manager_registration',on_change='rerun') as panel:
        if not panel.open:return
        rows=db.request('POST','rpc/sales_calendar_days',body={'first_day':str(today),'last_day':str(today)})
        confirmations={r['owner'] for r in db.request('GET','sales_empty_days',{'day':'eq.'+str(today),'select':'owner'})}
        states={}
        for uid in members:
            own=[r for r in rows if not r['common'] and uid in (r['owner'],r.get('companion'))]
            active=[r for r in own if r['status'] not in ('취소','연기')]
            states[uid]=('일정 있음' if any(r['kind']!='휴무' or r['start_time'] for r in active) else '휴무' if active else '일정 없음' if uid in confirmations else '모두 취소' if own and all(r['status']=='취소' for r in own) else '미등록')
        excluded=unregistered_exclusions(db.auth,[uid for uid,state in states.items() if state=='미등록'])
        groups=summary_groups(states,{uid:m['label'] for uid,m in members.items()},excluded)
        st.caption('미등록 '+str(len(groups.get('미등록',[])))+'명 · 일정 없음 '+str(len(groups.get('일정 없음',[])))+'명')
        for state,names in groups.items():st.write(state+' '+str(len(names))+'명 · '+', '.join(sorted(names)))

def render(db,today):
    from modules.activity.center import bounds,KST
    from modules.activity.redesign import admin_settings
    from modules.activity.contracts import performance,conversions
    from datetime import datetime
    styles()
    ux.feedback()
    with st.container(horizontal=True,vertical_alignment='center'):
        st.subheader('구성원 현황')
        if st.button('새로고침',key='manager_refresh',help='최신 변경 내용을 조회합니다.'):
            from modules.activity import read_state
            db._reads.clear();read_state.invalidate()

    screen=st.segmented_control('관리 화면',['활동 현황','주간 기록 검토'],default='활동 현황',required=True,key='manager_screen',label_visibility='collapsed')
    if screen=='주간 기록 검토':
        from modules.activity.weekly_review import render as weekly_review
        weekly_review(db,today)
        return
    from modules.activity import manager_ui as ui
    ui.styles()
    day,period,start,end,members,query,units=ui.controls(db,today)
    admin=st.session_state['hwarang_auth']['profile'].get('role')=='super_admin'
    events=db.period('sales_events',start,end)
    reports=db.period('sales_reports',start,end)
    contracts=db.period('sales_contracts',start,end)
    tasks=[]
    summary=summarize(members,events,reports,contracts,tasks,start,end,today,datetime.now(KST))
    filters=[('지원 요청','help'),('결과 미입력','missing'),('일일 기록 미제출','unsubmitted')]
    labels=['전체',*(label for label,_ in filters)]
    if st.session_state.get('sales_member_status') not in labels:st.session_state['sales_member_status']='전체'
    counts={'전체':len(summary),**{label:sum(r[field]>0 for r in summary) for label,field in filters}}
    if period=='일일':
        from modules.activity.status_policy import unregistered_exclusions
        confirmations={r['owner'] for r in db.request('GET','sales_empty_days',{'day':'eq.'+str(day),'select':'owner'})}
        registered={e['owner'] for e in events if e['status'] not in ('취소','연기')}
        excluded=unregistered_exclusions(db.auth,[u for u in members if u not in registered and u not in confirmations])
        for r in summary:r['unregistered']=int(r['uid'] not in registered and r['uid'] not in confirmations and r['uid'] not in excluded)
        filters.append(('일정 미등록','unregistered'));labels.append('일정 미등록')
        counts['일정 미등록']=sum(r['unregistered'] for r in summary)
    status=st.segmented_control('표시',labels,label_visibility='collapsed',default='전체',required=True,key='manager_status_v2',format_func=lambda label:label+' '+str(counts[label])+'명')
    st.caption('활동은 완료 일정 기준 · 청약은 접수일 기준')
    field=dict(filters).get(status)
    visible=[r for r in summary if query in r['name'].casefold() and (not field or r[field]>0)]
    st.caption(f'검색 결과 {len(visible)}명 / 조회 범위 {len(summary)}명')
    if not visible:
        st.info('조건에 맞는 구성원이 없습니다.')
        def reset():
            st.session_state['manager_pref_search']=''
            st.session_state['manager_status_v2']='전체'
        st.button('필터 초기화',on_click=reset)
    if not visible:return
    ids=[r['uid'] for r in visible]
    st.session_state['manager_visible_members']=ids
    selected=st.session_state.get('manager_selected')
    if selected not in ids:selected=ids[0];st.session_state['manager_selected']=selected
    def select(uid):st.session_state['manager_selected']=uid
    signature=tuple(ids)
    if st.session_state.get('manager_list_signature')!=signature:
        st.session_state['manager_list_signature']=signature
        st.session_state['manager_list_page']=1
    pages=(len(visible)+24)//25
    if pages>1:
        page=st.selectbox('목록 페이지',range(1,pages+1),key='manager_list_page',format_func=lambda n:f'{n} / {pages} 페이지')
        visible=visible[(page-1)*25:page*25]
    mobile=ux.compact()
    left,right=st.columns([1.5,1]) if not mobile else (st.container(),None)
    with left,st.container(key='manager_table'):
        if not ux.compact():
            cols=st.columns([2,1.4,0.6,0.6,0.6,0.6,0.8,2.2])
            for col,label in zip(cols,['직원','기록 제출',*CODES,'청약','확인할 사항']):col.markdown('**'+label+'**')
        for r in visible:
            flags=' · '.join(f'{label} {r[field]}' for label,field in filters[:3] if r[field]) or '없음'
            submission=('제출' if r['submitted'] else '미제출') if start==end and r['required'] else f"{r['submitted']}/{r['required']}일 제출" if r['required'] else '예정'
            with st.container(key='manager_row_'+r['uid']):
                if ux.compact():
                    if st.button(r['name']+' ›',key='member_open_'+r['uid'],width='stretch'):
                        select(r['uid']);ux.navigate({'type':'member','uid':r['uid'],'day':str(day),'period':period,'range_start':str(start),'range_end':str(end)})
                    st.caption(submission+' · '+' · '.join(f'{k} {r["counts"][k]}' for k in CODES)+f' · 청약 {r["contracts"]}건')
                    st.caption(flags)
                else:
                    cols=st.columns([2,1.4,0.6,0.6,0.6,0.6,0.8,2.2],vertical_alignment='center')
                    cols[0].button(r['name'],key='member_open_'+r['uid'],width='stretch',on_click=select,args=(r['uid'],),type='primary' if r['uid']==selected else 'secondary')
                    cols[1].write(submission)
                    for col,k in zip(cols[2:6],CODES):col.write(str(r['counts'][k]))
                    cols[6].write(f'{r["contracts"]}건');cols[7].caption(flags)
    if right is not None:
        with right,st.container(key='manager_detail'):
            ui.navigation(ids,selected,'manager_nav_')
            st.subheader(members[selected]['label'])
            ui.daily_reference(db,selected,start,end,today,'manager_daily_'+selected,records=reports,events=[e for e in events if e['owner']==selected])
    with st.expander('추가 통계',key='manager_extra',on_change='rerun') as extra:
        if extra.open:
            performance(db,day,members,bounds,selected_member=False,key='overview_perf',period_range=(start,end))
            with st.expander('상담 전환',key='overview_conv_open',on_change='rerun') as panel:
                if panel.open:conversions(db,start,end,members)
    if admin and not members:admin_settings(db,start,end)


def styles():
    st.html('''<style>
    .st-key-manager_summary button{min-height:76px!important;background:#f4f7fb;border:1px solid #e3e9f1;border-radius:14px;font-weight:650}
    .st-key-manager_summary button:hover{border-color:#417ab1;background:#eef5fc}
    .st-key-manager_table{border:1px solid #e3e9f1;border-radius:14px;padding:12px 16px;gap:8px}
    [class*="st-key-manager_row_"]{border-top:1px solid #eef1f5;padding-top:8px}
    [class*="st-key-manager_row_"] button{border:0;background:transparent;text-align:left;color:#234b72}
    .st-key-member_navigation{gap:8px!important}
    .st-key-member_navigation [data-testid="stDateInput"]{max-width:240px}
    .st-key-member_date_strip [data-testid="stButtonGroup"]{padding-bottom:4px}
    .st-key-member_date_strip [data-testid="stButtonGroup"]>div{display:grid!important;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);width:100%}
    .st-key-member_date_strip button{min-height:64px!important;min-width:0;flex:1;white-space:normal}
    .st-key-member_date_strip button p{white-space:pre-line;text-align:center;line-height:1.4;margin:0}
    .st-key-member_date_strip button[aria-checked="true"]{background:#e7f3ef!important;border-color:#397e68!important;color:#245f4d!important}
    @media(max-width:700px){
      .st-key-manager_table{padding:10px 12px}
      .st-key-member_date_strip [data-testid="stButtonGroup"]>div{grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-auto-flow:row;gap:8px}
      .st-key-member_date_strip button{width:100%!important;height:72px!important;padding:8px!important;border-radius:8px!important}
      .st-key-manager_status_v2 [data-testid="stButtonGroup"]>div,.st-key-review_filter_v2 [data-testid="stButtonGroup"]>div{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-auto-flow:row;gap:8px}

      .st-key-member_navigation [data-testid="stDateInput"]{max-width:160px}
      [class*="st-key-member_content_"] button{border:0!important;border-radius:0!important;background:transparent!important;border-bottom:2px solid transparent!important}
      [class*="st-key-member_content_"] button[aria-checked="true"]{border-bottom-color:#2870aa!important;color:#225f91!important}
    }
    </style>''')
    st.html('''<script>
    if(!window.hwarangMemberDateStrip){
      const reveal=()=>{
        const strip=document.querySelector('.st-key-member_date_strip [data-testid="stButtonGroup"]');
        const selected=strip?.querySelector('[aria-checked="true"]');
        if(!selected)return;
        const box=strip.getBoundingClientRect(),item=selected.getBoundingClientRect();
        if(item.right>box.right)strip.scrollLeft+=item.right-box.right+2;
        else if(item.left<box.left)strip.scrollLeft-=box.left-item.left+2;
      };
      let queued=false;
      const observer=new MutationObserver(()=>{
        if(queued)return;queued=true;
        requestAnimationFrame(()=>{queued=false;reveal();});
      });
      observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['aria-checked']});
      window.hwarangMemberDateStrip=observer;reveal();
    }
    </script>''',unsafe_allow_javascript=True)
