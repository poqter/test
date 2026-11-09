"""Shared manager controls; session preferences never expand database permissions."""
from datetime import timedelta
from html import escape
import streamlit as st
from modules.activity import ux
from modules.activity.record_editor import COUNTS, day_states


def controls(db,today,weekly=False):
    state=st.session_state
    for name,default in [('date',today),('period','주간'),('unit',None),('team',None),('search','')]:
        state.setdefault('manager_pref_'+name,default)
    def field(name,render,*args,**kwargs):
        key='manager_control_'+name
        state[key]=state['manager_pref_'+name]
        return render(*args,key=key,on_change=lambda:state.update({'manager_pref_'+name:state[key]}),**kwargs)
    members={u:m for u,m in db.members.items() if m.get('managed')} if weekly else db.members.copy()
    units={r['id']:r['name'] for r in db.request('GET','organization_units',{'select':'id,name'})}
    options=[None,*sorted({m['unit'] for m in members.values() if m.get('unit')})]
    if state['manager_pref_unit'] not in options:state['manager_pref_unit']=None
    cols=st.columns(2 if ux.compact() else 4)
    def shift(n):state['manager_pref_date']=min(today,state['manager_pref_date']+timedelta(days=n))
    with cols[0]:
        with st.container(horizontal=True,vertical_alignment='bottom'):
            step=7 if weekly or state['manager_pref_period']=='주간' else 1
            st.button('‹',key='manager_date_prev',on_click=shift,args=(-step,),help='이전 기간')
            day=field('date',st.date_input,'조회 기준일',max_value=today)
            st.button('›',key='manager_date_next',on_click=shift,args=(step,),disabled=day>=today,help='다음 기간')
    if weekly:
        period='주간';cols[1].caption('주간 기록 검토')
    else:period=field('period',cols[1].segmented_control,'기록 구분',['일일','주간'],required=True)
    unit=field('unit',cols[2%len(cols)].selectbox,'직할·지점',options,format_func=lambda u:units.get(u,'소속 미지정') if u else '전체 조회 가능 조직')
    if unit:members={u:m for u,m in members.items() if m['unit']==unit}
    assignments=db.request('GET','sales_team_assignments',{'select':'leader,member'})
    leaders=[None,*sorted({r['leader'] for r in assignments if r['leader'] in members})]
    if state['manager_pref_team'] not in leaders:state['manager_pref_team']=None
    leader=field('team',cols[3%len(cols)].selectbox,'담당 팀',leaders,format_func=lambda u:db.members[u]['label'] if u else '전체 팀')
    if leader:
        ids={leader}|{r['member'] for r in assignments if r['leader']==leader}
        members={u:m for u,m in members.items() if u in ids}
    query=field('search',st.text_input,'직원 이름 검색',placeholder='이름 검색').strip().casefold()
    start=day-timedelta(days=day.weekday()) if period=='주간' else day
    end=start+timedelta(days=6) if period=='주간' else day
    st.caption(f'{start:%Y.%m.%d} – {end:%m.%d}')
    return day,period,start,end,members,query,units


def counts(values):
    st.html('<div class="manager-counts">'+''.join('<div><span>'+escape(c)+'</span><strong>'+str(int(values.get(c,0)))+'</strong></div>' for c in COUNTS)+'</div>')


def navigation(visible,selected,key):
    index=visible.index(selected)
    def select(uid):st.session_state['manager_selected']=uid
    with st.container(horizontal=True,vertical_alignment='center'):
        st.button('‹ 이전',key=key+'prev',disabled=index==0,on_click=select,args=(visible[max(0,index-1)],))
        st.caption(f'{index+1} / {len(visible)}명')
        st.button('다음 ›',key=key+'next',disabled=index==len(visible)-1,on_click=select,args=(visible[min(len(visible)-1,index+1)],))


def daily_reference(db,uid,start,end,today,key,records=None,events=None):
    from modules.activity.redesign import event_list
    records=records if records is not None else db.period('sales_reports',start,end,owner='eq.'+uid)
    events=events if events is not None else db.period('sales_events',start,end,owner='eq.'+uid,order='day.asc,start_time.asc.nullsfirst')
    daily=[r for r in records if r['owner']==uid and r['period']=='일일']
    states=[item for item in day_states(start,today,daily,events) if item[0]<=end]
    options=[d for d,_,_ in states]
    statuses={d:s for d,s,_ in states}
    target=st.segmented_control('날짜별 일정·기록',options,default=today if today in options else options[0],required=True,key=key+'day',format_func=lambda d:f'{d:%m.%d} {statuses[d]}')
    st.markdown('**일정**')
    event_list(db,[e for e in events if e['day']==str(target)],key+'event',show_result_actions=False)
    st.markdown('**제출된 일일 기록**')
    row=next((r for r in daily if r['day']==str(target) and r.get('submitted')),None)
    if row:
        counts(row['data'].get('counts',{}))
        st.write(row['data'].get('note') or '작성 내용 없음')
        st.caption('지원 요청 · '+(row['data'].get('help') or '없음'))
    else:st.caption('예정' if target>today else '제출된 기록이 없습니다.')


def styles():
    st.html('''<style>
.manager-counts{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin:8px 0 16px}
.manager-counts>div{border:1px solid #dce4ee;background:#f7f9fc;border-radius:9px;text-align:center;padding:8px 4px}
.manager-counts span{font-size:12px;color:#53657d}.manager-counts strong{display:block;font-size:22px;color:#172b49}
.st-key-manager_table{border:1px solid #dce4ee;border-radius:12px;padding:12px}
.st-key-manager_detail,.st-key-review_detail{border:1px solid #dce4ee;border-radius:12px;padding:16px;background:white}
@media(max-width:700px){.manager-counts{grid-template-columns:repeat(3,minmax(0,1fr))}
.st-key-review_actions{position:sticky;bottom:0;background:white;z-index:5;padding:10px 0}}
</style>''')
