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
    from modules.activity import manager_ui as ui
    from modules.activity.record_editor import weekly_source
    ui.styles()
    day,period,start,end,members,query,units=ui.controls(db,today,weekly=True)
    reports=db.period('sales_reports',start,end)
    weekly={r['owner']:r for r in reports if r['period']=='주간' and r['day']==str(start) and r['owner'] in members}
    checks=db.request('GET','sales_report_checks',{'reviewer':'eq.'+db.uid})
    states={u:review_state(weekly.get(u),checks,db.uid) for u in members}
    labels=['전체','재검토 필요','검토 대기','미제출','확인 완료','지원 요청']
    def support(u):return bool((weekly.get(u) or {}).get('submitted') and (weekly[u].get('data') or {}).get('help'))
    mode=st.segmented_control('검토 상태',labels,default='전체',required=True,key='review_filter_v2',format_func=lambda s:s+' '+str(len(members) if s=='전체' else sum(support(u) if s=='지원 요청' else states[u]==s for u in members)))
    order={'재검토 필요':0,'검토 대기':1,'미제출':2,'확인 완료':3}
    visible=sorted((u for u in members if query in members[u]['label'].casefold() and (mode=='전체' or mode==states[u] or mode=='지원 요청' and support(u))),key=lambda u:(order[states[u]],members[u]['label'],u))
    if not visible:st.info('조건에 맞는 구성원이 없습니다.');return
    selected=st.session_state.get('manager_selected')
    if selected not in visible:selected=visible[0];st.session_state['manager_selected']=selected
    mobile=ux.compact()
    left,right=st.columns([1,2.3]) if not mobile else (st.container(),st.container())
    def select(u):
        st.session_state['manager_selected']=u
        st.session_state['review_mobile_detail']=True
    with left:
        if not mobile or not st.session_state.get('review_mobile_detail'):
            for u in visible:
                st.button(members[u]['label']+' · '+states[u]+(' · 지원 요청' if support(u) else ''),key='review_pick_'+u,on_click=select,args=(u,),type='primary' if u==selected else 'secondary',width='stretch')
    if mobile and not st.session_state.get('review_mobile_detail'):return
    with right,st.container(key='review_detail'):
        if mobile and st.button('‹ 직원 목록',key='review_back'):
            st.session_state['review_mobile_detail']=False;st.rerun()
        ui.navigation(visible,selected,'review_nav_')
        st.subheader(members[selected]['label'])
        row=weekly.get(selected)
        st.caption(states[selected]+' · '+units.get(members[selected]['unit'],'소속 미지정'))
        if row and row.get('submitted'):
            data=row['data'];ui.counts(data.get('counts',{}))
            own=[c for c in checks if c['report']==row['id'] and c['reviewer']==db.uid]
            if states[selected]=='재검토 필요' and own:
                revision=max(c['report_revision'] for c in own)
                history=db.request('GET','sales_report_history',{'report':'eq.'+row['id'],'revision':'eq.'+str(revision),'limit':'1'})
                if history:
                    old=history[0]['data'];changed=[c for c in COUNTS if old.get('counts',{}).get(c,0)!=data.get('counts',{}).get(c,0)]
                    changed += [label for label,f in [('주요 성과','note'),('돌아보기','reflection'),('다음 주 계획','plan'),('지원 요청','help')] if old.get(f,'')!=data.get(f,'')]
                    st.info('마지막 확인 이후 변경 · '+(' · '.join(changed) if changed else '활동 수치·본문 변경 없음'))
            for label,field in [('주요 성과 · 진행사항','note'),('이번 주 돌아보기','reflection'),('다음 주 계획','plan'),('지원 요청','help')]:
                if data.get(field):st.markdown('**'+label+'**');st.write(data[field])
                else:st.caption(label+' · 없음')
            # Durable draft separate from widget lifecycle, keyed to the exact submission.
            draft=f'review_message_{db.uid}_{row["id"]}_{row["revision"]}'
            widget='widget_'+draft
            st.session_state[widget]=st.session_state.get(draft,'')
            st.text_area('피드백 · 선택',key=widget,height=90,on_change=lambda:st.session_state.update({draft:st.session_state[widget]}))
            pending=[u for u in visible if u!=selected and states[u] in ('검토 대기','재검토 필요')]
            with st.container(key='review_actions',horizontal=True):
                skip=st.button('다음 직원',key='review_skip',disabled=visible.index(selected)==len(visible)-1)
                save=st.button('피드백 저장' if states[selected]=='확인 완료' else '확인 완료 · 다음 직원' if pending else '확인 완료',key='review_commit',type='primary')
            if skip:
                st.session_state['manager_selected']=visible[visible.index(selected)+1];ux.refresh()
            if save:
                try:
                    message=st.session_state.get(draft,'').strip()
                    if message:
                        # Stable id makes retry after a lost response idempotent.
                        token=draft+'_send';saved=st.session_state.get(token)
                        if not saved or saved['message']!=message:
                            saved={'id':str(uuid4()),'message':message};st.session_state[token]=saved
                        db.request('POST','sales_reviews',body={'id':saved['id'],'report':row['id'],'revision':row['revision'],'message':message},prefer='resolution=ignore-duplicates')
                    if states[selected]!='확인 완료':
                        db.request('POST','rpc/sales_check_report',body={'p_report':row['id'],'p_revision':row['revision']})
                        if pending:st.session_state['manager_selected']=pending[0]
                        else:st.session_state['sales_dialog_notice']='현재 목록의 제출 기록을 모두 확인했습니다.'
                    elif not message:st.warning('피드백을 입력해 주세요.');return
                    st.session_state.pop(draft,None);st.session_state.pop(draft+'_send',None)
                    ux.refresh()
                except HwarangAuthError as exc:st.error('저장하지 못했습니다. 입력 내용은 유지됩니다. '+str(exc))
            with st.expander('이전 피드백',key='review_comments_'+row['id'],on_change='rerun') as panel:
                if panel.open:
                    for comment in db.request('GET','sales_reviews',{'report':'eq.'+row['id'],'order':'created_at.desc'}):st.write(comment['message'])
            with st.expander('일일 기록·일정 참고',key='review_daily_'+selected,on_change='rerun') as panel:
                if panel.open:ui.daily_reference(db,selected,start,end,today,'review_daily_'+selected,records=reports)
        else:
            st.caption('주간 미제출 · 아래 내용은 일일 기록·일정 참고 자료입니다.')
            daily=[r for r in reports if r['owner']==selected and r['period']=='일일' and r.get('submitted')]
            events=db.period('sales_events',start,end,owner='eq.'+selected)
            st.markdown('**제출된 일일 기록 합계**');ui.counts(weekly_source(daily))
            st.markdown('**완료 일정 기준 · 별도 참고**');ui.counts({c:sum(e['kind']==c and e['status']=='완료' for e in events) for c in COUNTS})
            ui.daily_reference(db,selected,start,end,today,'review_unsubmitted_'+selected,records=reports,events=events)
        with st.expander('청약·계약 실적',key='review_contract_'+selected,on_change='rerun') as panel:
            if panel.open:
                rows=db.period('sales_contracts',start,end,owner='eq.'+selected)
                if rows:st.dataframe([{'접수일':r['day'],'보험사':r['insurer'],'구분':r['category'],'보험료(원)':r['amount'],'상태':r['status']} for r in rows],hide_index=True,width='stretch')
                else:st.caption('청약 0건')
