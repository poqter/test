"""Daily/weekly editing with versioned saves and explicit submission snapshots."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from modules.activity import ux
from modules.activity.daily import COUNTS, KST
from modules.shared.hwarang_auth import HwarangAuthError

DAY=timedelta(days=1)
TEXT_FIELDS=('note','reflection','plan','help')
META_FIELDS=('sources','coverage','contracts','results','manual_fields','source_versions','no_activity')


def values_from(data):
    return {**{c:int(data.get('counts',{}).get(c,0) or 0) for c in COUNTS},
        **{k:data.get(k,'') for k in TEXT_FIELDS},
        'sources':deepcopy(data.get('sources',{})), 'coverage':deepcopy(data.get('coverage',[])),
        'contracts':deepcopy(data.get('contracts',[])), 'results':deepcopy(data.get('results',[])),
        'manual_fields':list(data.get('manual_fields',[])), 'source_versions':deepcopy(data.get('source_versions',{})),
        'no_activity':bool(data.get('no_activity',False))}


def pack(d):
    data=deepcopy((d.get('old') or {}).get('data',{}));v=d['values']
    data['counts']={**data.get('counts',{}),**{c:int(v[c]) for c in COUNTS}}
    data.update({k:deepcopy(v[k]) for k in (*TEXT_FIELDS,*META_FIELDS)})
    if any(v[c] for c in COUNTS):data['no_activity']=False
    return data


def weekly_source(rows):
    rows=sorted((r for r in rows if r.get('submitted')),key=lambda r:r['day'])
    return {**ux.report_totals(rows,COUNTS),
        'note':'\n\n'.join(r['day'][5:]+' · '+r['data']['note'].strip() for r in rows if r['data'].get('note','').strip()),
        'coverage':[r['day'] for r in rows],
        'source_versions':{r['id']:r['revision'] for r in rows}}


def merge_source(values, source):
    """Import does not overwrite manually edited counters or prose."""
    protected=set(values.get('manual_fields',[]))
    return {k:deepcopy(v) for k,v in source.items() if k not in protected}


def day_states(start,today,reports,events):
    index={r['day']:r for r in reports};result=[]
    for i in range(7):
        day=start+i*DAY;row=index.get(str(day))
        own=[e for e in events if e['day']==str(day) and e.get('status') not in ('취소','연기') and not e.get('common')]
        off=bool(own) and all(e['kind']=='휴무' and not e.get('start_time') for e in own)
        status='예정' if day>today else '제출' if row and row.get('submitted') else '임시 저장' if row else '대상 아님' if day.weekday()>=5 or off else '미작성'
        result.append((day,status,row))
    return result


def persist(db,d,day,period,submit=False,slot=None):
    if d.get('saving'):return False
    if submit and period=='일일' and not any(d['values'][c] for c in COUNTS) and not d['values']['no_activity']:
        d['save_error']='활동 건수를 입력하거나 ‘활동 없는 날’을 선택해 주세요.'
        if slot is not None:slot.error(d['save_error'])
        return False
    d['saving']=True
    if slot is not None:slot.caption('제출 중…' if submit else '저장 중…')
    try:
        # Use the latest authenticated token, even after a long editing session.
        if hasattr(db,'token'):db.token=st.session_state.get('hwarang_auth',{}).get('access_token',db.token)
        result=db.request('POST','rpc/sales_save_report',body={
            'p_day':str(day),'p_period':period,'p_data':pack(d),
            'p_base_revision':(d.get('old') or {}).get('revision',0),
            'p_draft_revision':(d.get('server_draft') or {}).get('revision',0),'p_submit':submit})
        if not isinstance(result,dict) or not isinstance(result.get('report'),dict):
            raise HwarangAuthError('서버 저장 결과를 확인하지 못했습니다.')
        d['old']=result['report'];d['server_draft']=result.get('draft')
        d['baseline']=deepcopy(d['values']);d['saved_at']=datetime.now(KST).strftime('%H:%M:%S')
        d.pop('save_error',None);d.pop('conflict',None)
        if submit:d['notice']='제출했습니다.'
        if slot is not None:slot.caption('제출 완료' if submit else '임시 저장됨 · '+d['saved_at'])
        return True
    except HwarangAuthError as exc:
        d['save_error']='저장 실패 · 입력 내용은 유지됩니다. '+str(exc);d['conflict']=True
        if slot is not None:slot.error(d['save_error'])
        return False
    finally:d['saving']=False


@st.dialog('청약·계약 입력 및 수정',width='large',dismissible=True,on_dismiss='rerun')
def contract_dialog(db,day):
    from modules.activity.contracts import contract_editor
    contract_editor(db,day,expanded=True)
    if st.button('닫기',key='record_contract_close'):st.rerun()


def render(db,today,period,fixed_day=None):
    from modules.activity.redesign import report_key,event_list
    from modules.activity.daily import styles as daily_styles
    daily_styles();styles()
    suffix='_dialog' if fixed_day is not None else ''
    nav='sales_day_'+period;active='sales_report_active_'+period
    with st.container(key='daily_record'+suffix):
        if fixed_day is None:
            st.session_state.setdefault(nav,today)
            def move(delta):st.session_state[nav]=min(today,st.session_state[nav]+delta*DAY)
            def current():st.session_state[nav]=today
            with st.container(key='daily_navigation',horizontal=True,vertical_alignment='center'):
                st.button('‹',key='record_prev_'+period,on_click=move,args=(-7 if period=='주간' else -1,),help='이전 주' if period=='주간' else '이전 날')
                selected=st.date_input('조회 주간' if period=='주간' else '기록 날짜',max_value=today,key=nav,label_visibility='collapsed')
                st.button('›',key='record_next_'+period,on_click=move,args=(7 if period=='주간' else 1,),disabled=selected>=today)
                st.button('이번 주' if period=='주간' else '오늘',key='record_today_'+period,on_click=current)
            day=selected-selected.weekday()*DAY if period=='주간' else selected
            previous=st.session_state.get(active)
            if previous and previous!=str(day) and ux.dirty(report_key(db,previous,period)):
                prior_key=report_key(db,previous,period);prior=st.session_state['sales_drafts'][prior_key]
                if not persist(db,prior,date.fromisoformat(previous),period):
                    st.error(prior['save_error']);day=date.fromisoformat(previous)
                    st.info('저장이 완료될 때까지 이전 기록을 유지합니다.')
            st.session_state[active]=str(day)
        else:day=fixed_day
        key=report_key(db,day,period)
        if fixed_day is None:st.session_state['sales_active_draft']=key
        rows=db.period('sales_reports',day,day,owner='eq.'+db.uid,period='eq.'+period)
        old=rows[0] if rows else {}
        bucket=st.session_state.setdefault('sales_drafts',{})
        if key not in bucket:
            drafts=db.request('GET','sales_report_drafts',{'report':'eq.'+old['id'],'limit':'1'}) if old.get('submitted') else []
            draft=drafts[0] if drafts else None
            initial=values_from(draft['data'] if draft else old.get('data',{}))
            d=ux.draft(key,initial,old);d['server_draft']=draft
            if draft and draft['base_revision']!=old['revision']:
                d['save_error']='제출된 기록이 변경됐습니다. 수정 초안과 최신 제출 내용을 비교해 주세요.';d['conflict']=True
        d=bucket[key]
        for name,value in values_from({}).items():
            d['values'].setdefault(name,value);d['baseline'].setdefault(name,deepcopy(value))
        v=d['values'];old=d.get('old') or {}
        st.html('<span class="daily-context" data-context="'+d['epoch']+'"></span>')
        with st.container(key='daily_layout_bridge'+suffix):components.html(Path(__file__).with_name('daily_bridge.html').read_text(),height=0)
        changed=v!=values_from(old.get('data',{}))
        state='제출 완료 · 수정 초안' if old.get('submitted') and (changed or d.get('server_draft')) else '제출 완료' if old.get('submitted') else '임시 저장' if old else '작성 전'
        st.caption(f'{day:%Y.%m.%d}'+(f' – {day+6*DAY:%m.%d}' if period=='주간' else ' '+ '월화수목금토일'[day.weekday()])+' · '+state)
        status_slot=st.empty()
        if d.get('save_error'):
            status_slot.error(d['save_error'])
            if st.button('다시 저장',key=key+'retry'):persist(db,d,day,period,slot=status_slot)
            with st.expander('최신 저장 내용 확인',key=key+'conflict_view'):
                st.write(rows[0].get('data',{}) if rows else {})
                if st.button('현재 입력을 버리고 서버 저장본 불러오기',key=key+'reload'):
                    ux.clear_draft(key);ux.refresh()
        else:status_slot.caption('임시 저장됨 · '+d['saved_at'] if d.get('saved_at') else '입력 항목을 벗어나면 자동 임시 저장됩니다.')
        if notice:=d.pop('notice',None):st.success(notice)
        def edit(name):
            def changed_field():
                v['manual_fields']=list(set(v['manual_fields'])|{name})
                persist(db,d,day,period,slot=status_slot)
            return changed_field
        end=day+6*DAY if period=='주간' else day
        events=db.period('sales_events',day,end,owner='eq.'+db.uid,order='day.asc,start_time.asc.nullsfirst')
        daily=db.period('sales_reports',day,end,owner='eq.'+db.uid,period='eq.일일') if period=='주간' else []
        contracts=db.period('sales_contracts',day,end,owner='eq.'+db.uid)
        source=weekly_source(daily) if period=='주간' else None
        mobile=ux.compact()
        left,right=st.columns([1.85,1],gap='medium') if not mobile else (st.container(),None)
        def import_values(source):
            ux.set_values(d,merge_source(v,source));persist(db,d,day,period,slot=status_slot)
        if period=='주간':
            states=day_states(day,today,daily,events)
            st.caption('일일 기록 · '+' · '.join(f'{label} {sum(s==label for _,s,_ in states)}일' for label in ('제출','임시 저장','미작성')))
            if v['source_versions'] and v['source_versions']!=source['source_versions']:st.info('일일 기록이 변경되었습니다. 직접 수정한 항목을 유지하며 초안을 갱신할 수 있습니다.')
            st.button('일일 기록에서 초안 가져오기',key=key+'import',on_click=import_values,args=(source,),disabled=not source['coverage'])
        with left:
            with st.container(border=True,key='daily_inputs'+suffix):
                st.markdown('### 활동 건수')
                width=2 if mobile else 3
                for offset in range(0,len(COUNTS),width):
                    for col,name in zip(st.columns(width),COUNTS[offset:offset+width]):
                        ux.field(d,name,col.number_input,name,min_value=0,max_value=99999999,step=1,format='%d',after_change=edit(name))
                if period=='일일':ux.field(d,'no_activity',st.checkbox,'활동 없는 날',after_change=edit('no_activity'))
                ux.field(d,'note',st.text_area,'주요 성과 · 진행사항',height=120,after_change=edit('note'))
                if period=='주간':
                    ux.field(d,'reflection',st.text_area,'이번 주 돌아보기',height=100,after_change=edit('reflection'))
                    ux.field(d,'plan',st.text_area,'다음 주 계획',height=100,after_change=edit('plan'))
                with st.expander('지원 요청 · 선택',key=key+'help_panel',on_change='rerun'):
                    if period=='주간':
                        requests={r['id']:r['day'][5:]+' · '+r['data']['help'] for r in daily if r.get('submitted') and r['data'].get('help')}
                        picked=st.multiselect('아직 필요한 요청',list(requests),format_func=requests.get,key=key+'help_pick')
                        def apply_help():
                            ux.set_values(d,{'help':'\n'.join(requests[x] for x in picked)})
                            edit('help')()
                        st.button('선택한 요청 가져오기',key=key+'help_apply',on_click=apply_help,disabled=not picked)
                    ux.field(d,'help',st.text_area,'지원받을 내용',height=80,after_change=edit('help'))
        def references():
            if period=='일일':
                st.markdown('**'+('오늘 일정' if day==today else '선택한 날짜의 일정')+f' · {len(events)}건**')
                event_list(db,events,'daily_reference_')
                linked={r.get('event') for r in contracts}
                completed=[r for r in events if r['status']=='완료']
                sources={r['id']:r['kind'] for r in completed if r['kind'] in COUNTS and not(r['kind']=='청약' and r['id'] in linked)}
                sources.update({r['id']:'청약' for r in contracts})
                proposed=ux.refreshed_counts(v,v['sources'],sources,COUNTS)
                st.markdown('**완료 일정·청약 기준 집계**')
                st.dataframe([{'항목':c,'입력':v[c],'자동 집계':list(sources.values()).count(c),'직접 수정':c in v['manual_fields']} for c in COUNTS],hide_index=True,width='stretch')
                st.caption('직접 수정한 항목은 유지합니다. 가져온 원천은 중복 합산하지 않습니다.')
                st.button('집계값 가져오기',key=key+'import',on_click=import_values,args=({**proposed,'sources':sources},))
            else:
                st.markdown('**일일 기록 반영 현황**')
                for target,status,row in states:
                    a,b=st.columns([1,1.4]);a.caption(target.strftime('%m.%d')+' · '+'월화수목금토일'[target.weekday()])
                    if b.button(status+' · '+('보기' if row else '작성'),key=key+'day'+str(target),disabled=target>today,width='stretch'):
                        ux.navigate({'type':'daily','day':str(target)})
                st.caption('합산은 제출된 일일 기록 기준입니다. 주말·종일 휴무는 미작성에서 제외합니다.')
                st.dataframe([{'항목':c,'주간 입력':v[c],'일일 합계':source[c]} for c in COUNTS],hide_index=True,width='stretch')
            with st.expander('청약·계약 실적',key=key+'contract_summary'):
                if contracts:st.dataframe([{'접수일':r['day'],'보험사':r['insurer'],'구분':r['category'],'보험료(원)':r['amount'],'상태':r['status']} for r in contracts],hide_index=True,width='stretch')
                else:st.caption('선택 기간에 등록된 실적이 없습니다.')
            if fixed_day is None and st.button('청약·계약 입력 및 수정',key=key+'contracts'):contract_dialog(db,day)
        if right is not None:
            with right:
                with st.container(border=True,key='daily_reference_card'+suffix):references()
        else:
            with st.expander('일정·집계·참고 자료',key=key+'references',on_change='rerun') as panel:
                if panel.open:references()
        with st.container(key='daily_footer'+suffix,horizontal=True,vertical_alignment='center'):
            st.caption('수정 초안은 다시 제출하기 전까지 기존 제출 내용에 반영되지 않습니다.' if old.get('submitted') else '입력 후 자동 임시 저장 · 제출은 직접 선택')
            if st.button('임시 저장',key=key+'draft',disabled=bool(d.get('saving'))):persist(db,d,day,period,slot=status_slot)
            if st.button('수정 내용 제출' if old.get('submitted') else '제출하기',key=key+'submit',type='primary',disabled=bool(d.get('saving')) or bool(old.get('submitted') and not changed and not d.get('server_draft'))):
                if persist(db,d,day,period,True,status_slot):
                    if fixed_day is not None:ux.back()
                    else:ux.refresh()
        if old:
            with st.expander('제출 이력·피드백',key=key+'history',on_change='rerun') as panel:
                if panel.open:
                    from modules.activity.center import report_detail
                    report_detail(db,d.get('old') or old)
        return key


def styles():
    st.html('''<style>
[class*="st-key-daily_navigation"]{justify-content:flex-start!important;flex-wrap:nowrap!important}
[class*="st-key-daily_navigation"]>[data-testid="stElementContainer"]{flex:0 0 auto!important;width:auto!important}
[class*="st-key-daily_navigation"] [data-testid="stDateInput"]{width:200px!important}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"]{padding:5px 8px!important}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"] input{font-size:18px!important}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"] label{margin-bottom:0!important}
[class*="st-key-daily_footer"]{justify-content:flex-end!important;align-items:center!important;flex-wrap:wrap!important}
[class*="st-key-daily_footer"]>[data-testid="stElementContainer"]{flex:0 0 auto!important;width:auto!important}
[class*="st-key-daily_footer"] [data-testid="stCaptionContainer"]{margin-right:auto}
[class*="st-key-daily_reference_card"]{padding:14px!important}
@media(max-width:700px){[class*="st-key-daily_navigation"] [data-testid="stDateInput"]{width:150px!important}[class*="st-key-daily_footer"] button{min-width:110px}}
</style>''')
