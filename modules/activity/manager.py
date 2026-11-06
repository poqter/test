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
        missing=[e for e in own if e['status']=='예정' and (e['day']<str(today) or e['day']==str(today) and (e.get('end_time') or e.get('start_time') or '23:59:59')<now.strftime('%H:%M:%S'))]
        support=[dict(type='event',id=e['id'],day=e['day'],text=e['help']) for e in own if e.get('help') and e['status'] not in ('취소','연기')]
        support += [dict(type='report',id=r['id'],day=r['day'],text=r['data']['help']) for r in grouped['reports'][uid] if r['submitted'] and r['data'].get('help')]
        overdue=[t for t in grouped['tasks'][uid] if not t.get('scheduled') and t['due']<str(today)]
        result.append(dict(uid=uid,name=member['label'],counts={k:sum(e['kind']==k and e['status']=='완료' for e in own) for k in CODES},
            submitted=len(submitted),required=len(due),unsubmitted=len(due-submitted),missing=len(missing),help=len(support),late=len(overdue),
            contracts=len(grouped['contracts'][uid]),support=support,tasks=overdue))
    return result

def render(db,today):
    from modules.activity.center import bounds,KST
    from modules.activity.redesign import admin_settings
    from modules.activity.contracts import performance,conversions
    from datetime import datetime
    styles()
    ux.feedback()
    st.subheader('구성원 현황')
    a,b,c=st.columns([1,1,1.3])
    day=a.date_input('조회 기준일',today,key='sales_overview_day')
    period=b.segmented_control('기록 구분',['일일','주간'],default='주간',required=True,key='sales_overview_period')
    start,end=bounds(day,'주간' if period=='주간' else '날짜별')
    members=db.members.copy()
    admin=st.session_state['hwarang_auth']['profile'].get('role')=='super_admin'
    if admin:
        units={r['id']:r['name'] for r in db.request('GET','organization_units',{'select':'id,name'})}
        choices=list(dict.fromkeys([db.me['unit'],'all',*(m['unit'] for m in members.values())]))
        unit=c.selectbox('조회 범위',choices,format_func=lambda u:'전체 조직' if u=='all' else units.get(u,'소속 미지정'),key='sales_overview_unit')
        if unit!='all':members={u:m for u,m in members.items() if m['unit']==unit}
    assignments=db.request('GET','sales_team_assignments',{'select':'leader,member'})
    leaders={r['leader'] for r in assignments if r['leader'] in members}
    if leaders:
        leader=st.selectbox('팀 조회',[None,*sorted(leaders)],format_func=lambda u:db.members[u]['label']+' 담당 팀' if u else '전체 팀',key='manager_team')
        if leader:
            ids={r['member'] for r in assignments if r['leader']==leader}|{leader}
            members={u:m for u,m in members.items() if u in ids}
    events=db.period('sales_events',start,end)
    reports=db.period('sales_reports',start,end)
    contracts=db.period('sales_contracts',start,end)
    tasks=db.request('GET','sales_followups',{'and':f'(due.gte.{start},due.lte.{end})','scheduled':'is.null','order':'due.asc'})
    summary=summarize(members,events,reports,contracts,tasks,start,end,today,datetime.now(KST))
    filters=[('지원 요청','help'),('결과 미입력','missing'),('지연된 후속 활동','late'),('일일 기록 미제출','unsubmitted')]
    labels=['전체',*(label for label,_ in filters)]
    if st.session_state.get('sales_member_status') not in labels:st.session_state['sales_member_status']='전체'
    def choose(label):st.session_state['sales_member_status']=label
    with st.container(key='manager_summary'):
        columns=st.columns(2 if ux.compact() else 4)
        for i,(label,field) in enumerate(filters):
            count=sum(r[field] for r in summary) if field!='unsubmitted' else sum(r[field]>0 for r in summary)
            columns[i%len(columns)].button(f'{label} {count}'+('명' if field=='unsubmitted' else '건'),key='manager_'+field,on_click=choose,args=(label,),width='stretch')
    st.caption(f'{start} – {end} · 활동은 완료 일정 기준 · 청약은 접수일 기준 · 미제출은 조회 기간 중 오늘까지의 '+('평일' if period=='주간' else '조회일')+' 기준입니다.')
    with st.expander('오늘 먼저 확인할 사항',expanded=any(r['help'] or r['late'] for r in summary)):
        attention=[(r,s) for r in summary for s in r['support']]+[(r,dict(type='task',id=t['id'],day=t['due'],text=t['title'])) for r in summary for t in r['tasks']]
        if not attention:st.caption('선택 기간에 등록된 지원 요청·지연된 후속 활동이 없습니다.')
        for r,item in attention[:5]:
            a,b=st.columns([5,1])
            a.write(f"**{r['name']}** · {item['day']} · {item['text']}")
            if b.button('확인',key='attention_'+r['uid']+item['type']+item['id']):
                if item['type']=='event':ux.navigate({'type':'event','id':item['id']})
                else:ux.navigate({'type':'member','uid':r['uid'],'day':item['day'],'period':'일일'})
        if len(attention)>5:st.caption(f'외 {len(attention)-5}건 · 아래 직원 목록에서 확인하세요.')
        st.caption('지원 요청은 기록된 요청 기준이며 처리 완료 여부를 뜻하지 않습니다.')
    st.markdown('### 직원별 활동 요약')
    query=st.text_input('직원 이름 검색',placeholder='이름을 입력하세요',key='sales_member_search').strip().casefold()
    status=st.segmented_control('표시',labels,required=True,key='sales_member_status')
    field=dict(filters).get(status)
    visible=[r for r in summary if query in r['name'].casefold() and (not field or r[field]>0)]
    st.caption(f'검색 결과 {len(visible)}명 / 조회 범위 {len(summary)}명')
    if not visible:st.info('조건에 맞는 구성원이 없습니다.')
    signature=tuple(r['uid'] for r in visible)
    if st.session_state.get('manager_list_signature')!=signature:
        st.session_state['manager_list_signature']=signature
        st.session_state['manager_list_page']=1
    pages=(len(visible)+24)//25
    if pages>1:
        page=st.selectbox('목록 페이지',range(1,pages+1),key='manager_list_page',format_func=lambda n:f'{n} / {pages} 페이지')
        st.caption(f'{(page-1)*25+1}–{min(page*25,len(visible))}번째 직원 · 상단 요약은 조회 범위 전체 기준입니다.')
        visible=visible[(page-1)*25:page*25]
    with st.container(key='manager_table'):
        if not ux.compact():
            cols=st.columns([2,1.4,0.6,0.6,0.6,0.6,0.8,2.2])
            for col,label in zip(cols,['직원','기록 제출',*CODES,'청약','확인할 사항']):col.markdown('**'+label+'**')
        for r in visible:
            flags=' · '.join(f'{label} {r[field]}' for label,field in filters[:3] if r[field]) or '없음'
            submission=f"{r['submitted']}/{r['required']}일 제출" if r['required'] else '예정'
            with st.container(key='manager_row_'+r['uid']):
                if ux.compact():
                    if st.button(r['name']+' ›',key='member_open_'+r['uid'],width='stretch'):ux.navigate({'type':'member','uid':r['uid'],'day':str(day),'period':period})
                    st.caption(submission+' · '+' · '.join(f'{k} {r["counts"][k]}' for k in CODES)+f' · 청약 {r["contracts"]}건')
                    st.caption(flags)
                else:
                    cols=st.columns([2,1.4,0.6,0.6,0.6,0.6,0.8,2.2],vertical_alignment='center')
                    if cols[0].button(r['name']+' ›',key='member_open_'+r['uid'],width='stretch'):ux.navigate({'type':'member','uid':r['uid'],'day':str(day),'period':period})
                    cols[1].write(submission)
                    for col,k in zip(cols[2:6],CODES):col.write(str(r['counts'][k]))
                    cols[6].write(f'{r["contracts"]}건');cols[7].caption(flags)
    with st.expander('청약·계약 실적',key='manager_perf',on_change='rerun') as panel:
        if panel.open:performance(db,day,members,bounds,selected_member=False,key='overview_perf',period_range=(start,end))
    with st.expander('상담 전환',key='overview_conv_open',on_change='rerun') as panel:
        if panel.open:conversions(db,start,end,members)
    if admin:admin_settings(db,start,end)


def styles():
    st.html('''<style>
    .st-key-manager_summary button{min-height:76px!important;background:#f4f7fb;border:1px solid #e3e9f1;border-radius:14px;font-weight:650}
    .st-key-manager_summary button:hover{border-color:#417ab1;background:#eef5fc}
    .st-key-manager_table{border:1px solid #e3e9f1;border-radius:14px;padding:12px 16px;gap:8px}
    [class*="st-key-manager_row_"]{border-top:1px solid #eef1f5;padding-top:8px}
    [class*="st-key-manager_row_"] button{border:0;background:transparent;text-align:left;color:#234b72}
    .st-key-member_navigation{gap:8px!important}
    .st-key-member_navigation [data-testid="stDateInput"]{max-width:240px}
    .st-key-member_date_strip [data-testid="stButtonGroup"]{overflow-x:auto;padding-bottom:4px}
    .st-key-member_date_strip [data-testid="stButtonGroup"]>div{flex-wrap:nowrap!important;min-width:max-content}
    .st-key-member_date_strip button{min-height:64px!important;min-width:125px;flex:1;white-space:normal}
    .st-key-member_date_strip button p{white-space:pre-line;text-align:center}
    .st-key-member_date_strip button[aria-checked="true"]{background:#e7f3ef!important;border-color:#397e68!important;color:#245f4d!important}
    @media(max-width:700px){
      .st-key-manager_table{padding:10px 12px}
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
