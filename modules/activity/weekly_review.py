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
    from modules.activity.period_summary import daily_rows,totals,table
    ui.styles()
    day,period,start,end,members,query,units=ui.controls(db,today,weekly=True)
    from modules.activity.live_sync import attach
    attach(db,start,end)
    if hasattr(db,'activity_bundle'):db.activity_bundle(start,end)
    reports=db.period('sales_reports',start,end)
    daily=daily_rows(reports,start,end,members)
    checks=db.request('GET','sales_report_checks',{'reviewer':'eq.'+db.uid})
    grouped={u:[r for r in daily if r['owner']==u] for u in members}
    def state(u):
        states=[review_state(r,checks,db.uid) for r in grouped[u]]
        return '미제출' if not states else '재검토 필요' if '재검토 필요' in states else '확인 완료' if all(s=='확인 완료' for s in states) else '검토 대기'
    states={u:state(u) for u in members}
    labels=['전체','재검토 필요','검토 대기','미제출','확인 완료','지원 요청']
    def support(u):return any((r.get('data') or {}).get('help') for r in grouped[u])
    mode=st.segmented_control('검토 상태',labels,default='전체',required=True,key='review_filter_v2',format_func=lambda s:s+' '+str(len(members) if s=='전체' else sum(support(u) if s=='지원 요청' else states[u]==s for u in members)))
    order={'재검토 필요':0,'검토 대기':1,'미제출':2,'확인 완료':3}
    visible=sorted((u for u in members if query in members[u]['label'].casefold() and (mode=='전체' or mode==states[u] or mode=='지원 요청' and support(u))),key=lambda u:(order[states[u]],members[u]['label'],u))
    if not visible:st.info('조건에 맞는 구성원이 없습니다.');return
    selected=st.session_state.get('manager_selected')
    if selected not in visible:selected=visible[0];st.session_state['manager_selected']=selected
    mobile=ux.compact()
    left,right=st.columns([1,2.3]) if not mobile else (st.container(),st.container())
    def select(u):st.session_state.update(manager_selected=u,review_mobile_detail=True)
    with left:
        if not mobile or not st.session_state.get('review_mobile_detail'):
            for u in visible:st.button(members[u]['label']+' · '+states[u]+(' · 지원 요청' if support(u) else ''),key='review_pick_'+u,on_click=select,args=(u,),type='primary' if u==selected else 'secondary',width='stretch')
    if mobile and not st.session_state.get('review_mobile_detail'):return
    with right,st.container(key='review_detail'):
        if mobile and st.button('‹ 직원 목록',key='review_back'):
            st.session_state['review_mobile_detail']=False;ux.refresh()
        ui.navigation(visible,selected,'review_nav_')
        st.subheader(members[selected]['label'])
        rows=grouped[selected]
        st.caption(states[selected]+' · '+units.get(members[selected]['unit'],'소속 미지정'))
        ui.counts(totals(rows))
        table(rows,start,end,{selected:members[selected]},today)
        if states[selected]=='재검토 필요':st.info('확인 이후 수정된 일일 기록이 있습니다.')
        for row in rows:
            data=row.get('data') or {}
            if data.get('note') or data.get('help'):
                st.markdown('**'+row['day']+'**')
                if data.get('note'):st.write(data['note'])
                if data.get('help'):st.write('지원 요청 · '+data['help'])
        if rows:
            draft=f'period_feedback_{db.uid}_{selected}_{start}_{end}'
            widget='widget_'+draft
            if widget not in st.session_state:st.session_state[widget]=st.session_state.get(draft,'')
            st.text_area('피드백 · 선택',key=widget,height=90,on_change=lambda:st.session_state.update({draft:st.session_state[widget]}))
            pending=[u for u in visible if u!=selected and states[u] in ('검토 대기','재검토 필요')]
            with st.container(key='review_actions',horizontal=True):
                skip=st.button('다음 직원',key='review_skip',disabled=visible.index(selected)==len(visible)-1)
                save=st.button('피드백 저장' if states[selected]=='확인 완료' else '확인 완료 · 다음 직원' if pending else '확인 완료',key='review_commit',type='primary')
            if skip:st.session_state['manager_selected']=visible[visible.index(selected)+1];ux.refresh()
            if save:
                try:
                    message=st.session_state.get(draft,'').strip()
                    if states[selected]=='확인 완료' and not message:st.warning('피드백을 입력해 주세요.');return
                    token=draft+'_send';saved=st.session_state.get(token)
                    if not saved or saved['message']!=message:
                        saved={'id':str(uuid4()),'message':message};st.session_state[token]=saved
                    db.request('POST','rpc/sales_check_daily_period',body={'p_owner':selected,'p_first':str(start),'p_last':str(end),'p_versions':{r['id']:r['revision'] for r in rows},'p_message':message,'p_request':saved['id']})
                    st.session_state.pop(draft,None);st.session_state.pop(widget,None);st.session_state.pop(token,None)
                    if pending:st.session_state['manager_selected']=pending[0]
                    ux.refresh()
                except HwarangAuthError as exc:st.error('저장하지 못했습니다. 입력 내용은 유지됩니다. '+str(exc))
        else:st.info('제출된 일일 기록이 없습니다. 일정은 아래에서 확인할 수 있습니다.')
        with st.expander('일일 기록·일정·피드백',key='review_daily_'+selected,on_change='rerun') as panel:
            if panel.open:
                ui.daily_reference(db,selected,start,end,today,'review_daily_'+selected,records=reports)
                for row in rows:
                    for comment in db.request('GET','sales_reviews',{'report':'eq.'+row['id'],'deleted_at':'is.null','order':'created_at.desc'}):st.write(comment['message'])
        with st.expander('청약·계약 실적',key='review_contract_'+selected,on_change='rerun') as panel:
            if panel.open:
                contracts=db.period('sales_contracts',start,end,owner='eq.'+selected)
                if contracts:st.dataframe([{'접수일':r['day'],'보험사':r['insurer'],'구분':r['category'],'보험료(원)':r['amount'],'상태':r['status']} for r in contracts],hide_index=True,width='stretch')
                else:st.caption('청약 0건')
        legacy=[r for r in reports if r['owner']==selected and r['period']=='주간' and r.get('submitted')]
        if legacy:
            with st.expander('이전 주간 제출 기록 · 보관',key='review_legacy',on_change='rerun') as panel:
                if panel.open:
                    from modules.activity.center import report_detail
                    for row in legacy:report_detail(db,row)
