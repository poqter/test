"""Explicit, revision-bound review in the caller's authorized scope."""
from datetime import timedelta
from uuid import uuid4
import streamlit as st
from modules.activity import ux
from modules.activity.record_editor import COUNTS, day_states
from modules.shared.hwarang_auth import HwarangAuthError


def review_state(row,checks,reviewer):
    if not row or not row.get('submitted'):return '미제출'
    own=[c for c in checks if c['report']==row['id'] and c['reviewer']==reviewer]
    if any(c['report_revision']==row['revision'] for c in own):return '확인 완료'
    return '재검토 필요' if own else '검토 대기'


def render(db,today):
    st.session_state.setdefault('review_week',today)
    def move(n):st.session_state['review_week']=min(today,st.session_state['review_week']+timedelta(days=n))
    with st.container(horizontal=True,vertical_alignment='bottom'):
        st.button('‹',key='review_prev',on_click=move,args=(-7,))
        day=st.date_input('조회 주간',key='review_week',max_value=today)
        st.button('›',key='review_next',on_click=move,args=(7,),disabled=day>=today)
    start=day-timedelta(days=day.weekday());end=start+timedelta(days=6)
    members={u:m for u,m in db.members.items() if m.get('managed')}
    units={r['id']:r['name'] for r in db.request('GET','organization_units',{'select':'id,name'})}
    a,b=st.columns(2)
    unit=a.selectbox('직할·지점',[None,*sorted({m['unit'] for m in members.values() if m.get('unit')})],format_func=lambda u:units.get(u,'소속 미지정') if u else '전체 조회 가능 조직',key='review_unit')
    if unit:members={u:m for u,m in members.items() if m['unit']==unit}
    assignments=db.request('GET','sales_team_assignments',{'select':'leader,member'})
    leaders=sorted({r['leader'] for r in assignments if r['leader'] in members})
    leader=b.selectbox('담당 팀장',[None,*leaders],format_func=lambda u:db.members[u]['label'] if u else '전체 팀',key='review_team')
    if leader:
        ids={leader}|{r['member'] for r in assignments if r['leader']==leader}
        members={u:m for u,m in members.items() if u in ids}
    reports=db.period('sales_reports',start,end)
    weekly={r['owner']:r for r in reports if r['period']=='주간' and r['day']==str(start)}
    checks=db.request('GET','sales_report_checks',{'reviewer':'eq.'+db.uid})
    states={u:review_state(weekly.get(u),checks,db.uid) for u in members}
    st.caption(f'{start:%Y.%m.%d} – {end:%m.%d} · 제출 {sum(s!="미제출" for s in states.values())}/{len(members)}명 · 검토 대기 {sum(s in ("검토 대기","재검토 필요") for s in states.values())}명 · 확인 완료 {sum(s=="확인 완료" for s in states.values())}명')
    a,b=st.columns([1,2])
    query=a.text_input('구성원 검색',key='review_search').strip().casefold()
    mode=b.segmented_control('상태',['전체','미제출','검토 대기','확인 완료','지원 요청'],default='전체',required=True,key='review_filter')
    def matches(u):
        row=weekly.get(u) or {}
        return (not query or query in members[u]['label'].casefold()) and (mode=='전체' or mode==states[u] or mode=='검토 대기' and states[u]=='재검토 필요' or mode=='지원 요청' and row.get('submitted') and bool(row.get('data',{}).get('help')))
    visible=sorted((u for u in members if matches(u)),key=lambda u:(states[u]=='확인 완료',members[u]['label'],u))
    if not visible:st.info('조건에 맞는 구성원이 없습니다.');return
    selected=st.session_state.get('review_member')
    if selected not in visible:selected=visible[0];st.session_state['review_member']=selected
    def select(u):st.session_state['review_member']=u
    left,right=st.columns([1,2.2]) if not ux.compact() else (st.container(),st.container())
    with left:
        for u in visible:st.button(members[u]['label']+' · '+states[u],key='review_pick_'+u,on_click=select,args=(u,),type='primary' if u==selected else 'secondary',width='stretch')
    with right:
        st.markdown('### '+members[selected]['label'])
        row=weekly.get(selected)
        st.caption(states[selected]+' · '+units.get(members[selected]['unit'],'소속 미지정'))
        if row and row.get('submitted'):
            data=row['data']
            st.dataframe([{'항목':c,'제출 건수':data.get('counts',{}).get(c,0)} for c in COUNTS],hide_index=True,width='stretch')
            for label,field in [('주요 성과 · 진행사항','note'),('이번 주 돌아보기','reflection'),('다음 주 계획','plan'),('지원 요청','help')]:
                st.markdown('**'+label+'**');st.write(data.get(field) or '작성 내용 없음')
            st.caption('제출 버전 '+str(row['revision'])+' · 내용을 열어보는 것만으로 확인 처리되지 않습니다.')
            a,b=st.columns(2)
            done=a.button('확인 완료',key='review_done_'+row['id'],disabled=states[selected]=='확인 완료',width='stretch')
            advance=b.button('확인 후 다음',key='review_advance_'+row['id'],width='stretch')
            if done or advance:
                try:
                    db.request('POST','rpc/sales_check_report',body={'p_report':row['id'],'p_revision':row['revision']})
                    if advance:
                        pending=[u for u in visible if u!=selected and states[u] in ('검토 대기','재검토 필요')]
                        if pending:st.session_state['review_member']=pending[0]
                        else:st.session_state['sales_dialog_notice']='현재 목록의 제출 기록을 모두 확인했습니다.'
                    ux.refresh()
                except HwarangAuthError as exc:st.error(str(exc))
            with st.expander('피드백 · 선택',key='weekly_feedback_'+row['id'],on_change='rerun') as panel:
                if panel.open:
                    comments=db.request('GET','sales_reviews',{'report':'eq.'+row['id'],'order':'created_at.desc'})
                    for comment in comments:st.caption(comment['message']+(' · 이전 제출 버전' if comment['revision']!=row['revision'] else ''))
                    with st.form('weekly_comment_'+row['id']+'_'+str(row['revision'])):
                        message=st.text_area('피드백 내용')
                        if st.form_submit_button('피드백 저장'):
                            if not message.strip():st.warning('피드백을 입력해 주세요.')
                            else:
                                try:
                                    db.request('POST','sales_reviews',body={'id':str(uuid4()),'report':row['id'],'revision':row['revision'],'message':message.strip()})
                                    ux.refresh()
                                except HwarangAuthError as exc:st.error(str(exc))
        else:st.info('이번 주 기록을 아직 제출하지 않았습니다.')
        with st.expander('일일 기록·일정 확인',key='review_daily_'+selected,on_change='rerun') as panel:
            if panel.open:
                daily=[r for r in reports if r['owner']==selected and r['period']=='일일']
                events=db.period('sales_events',start,end,owner='eq.'+selected)
                for target,status,record in day_states(start,today,daily,events):
                    if st.button(target.strftime('%m.%d')+' · '+status,key='review_day_'+selected+str(target),disabled=target>today):ux.navigate({'type':'member','uid':selected,'day':str(target),'period':'일일'})
        with st.expander('청약·계약 실적',key='review_contract_'+selected,on_change='rerun') as panel:
            if panel.open:
                rows=db.period('sales_contracts',start,end,owner='eq.'+selected)
                if rows:st.dataframe([{'접수일':r['day'],'보험사':r['insurer'],'구분':r['category'],'보험료(원)':r['amount'],'상태':r['status']} for r in rows],hide_index=True,width='stretch')
                else:st.caption('선택 기간에 등록된 실적이 없습니다.')
