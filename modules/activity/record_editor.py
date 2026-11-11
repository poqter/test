"""Daily/weekly editing with versioned saves and explicit submission snapshots."""
from copy import deepcopy
from html import escape
from datetime import date, datetime, timedelta
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from modules.activity import ux
from modules.activity.daily import COUNTS, KST
from modules.shared.hwarang_auth import HwarangAuthError

DAY=timedelta(days=1)
TEXT_FIELDS=('note','reflection','plan','help')
META_FIELDS=('sources','coverage','contracts','results','manual_fields','source_versions','no_activity','help_recipient')


def values_from(data):
    return {**{c:int(data.get('counts',{}).get(c,0) or 0) for c in COUNTS},
        **{k:data.get(k,'') for k in TEXT_FIELDS},
        'sources':deepcopy(data.get('sources',{})), 'coverage':deepcopy(data.get('coverage',[])),
        'contracts':deepcopy(data.get('contracts',[])), 'results':deepcopy(data.get('results',[])),
        'manual_fields':list(data.get('manual_fields',[])), 'source_versions':deepcopy(data.get('source_versions',{})),
        'no_activity':bool(data.get('no_activity',False)), 'help_recipient':data.get('help_recipient')}


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


def confirmed_save(db, request, old):
    """Resolve a lost response only when the expected server snapshot is present."""
    rows = db.request('GET', 'sales_reports', {
        'owner': 'eq.' + db.uid, 'day': 'eq.' + request['p_day'],
        'period': 'eq.' + request['p_period'], 'limit': '1',
    })
    if not rows:
        return None
    report = rows[0]
    base_revision = request['p_base_revision']
    if old.get('id') and report.get('id') != old['id']:
        return None
    if old.get('submitted') and not request['p_submit']:
        if not report.get('submitted') or report.get('revision') != base_revision:
            return None
        drafts = db.request('GET', 'sales_report_drafts', {'report': 'eq.' + report['id'], 'limit': '1'})
        draft = drafts[0] if drafts else {}
        if (draft.get('revision'), draft.get('base_revision'), draft.get('data')) == (
            request['p_draft_revision'] + 1, base_revision, request['p_data']
        ):
            return {'report': report, 'draft': draft}
    elif (report.get('revision'), report.get('submitted'), report.get('data')) == (
        base_revision + 1, request['p_submit'], request['p_data']
    ):
        return {'report': report, 'draft': None}
    return None


def persist(db,d,day,period,submit=False,slot=None):
    if d.get('saving'):return False
    if submit and period=='일일' and not any(d['values'][c] for c in COUNTS) and not d['values']['no_activity']:
        d['save_error']='활동 건수를 입력하거나 ‘활동 없는 날’을 선택해 주세요.'
        if slot is not None:slot.error(d['save_error'])
        return False
    if submit and d['values'].get('help','').strip() and not d['values'].get('help_recipient'):
        st.warning('지원 요청 대상을 선택해 주세요.');return False
    d['saving']=True
    if slot is not None:slot.caption('제출 중…' if submit else '저장 중…')
    try:
        # Use the latest authenticated token, even after a long editing session.
        if hasattr(db,'token'):db.token=st.session_state.get('hwarang_auth',{}).get('access_token',db.token)
        request = {
            'p_day':str(day),'p_period':period,'p_data':pack(d),
            'p_base_revision':(d.get('old') or {}).get('revision',0),
            'p_draft_revision':(d.get('server_draft') or {}).get('revision',0),'p_submit':submit,
        }
        try:
            result = db.request('POST', 'rpc/sales_save_report', body=request)
            if not isinstance(result, dict) or not isinstance(result.get('report'), dict):
                raise HwarangAuthError('서버 저장 결과를 확인하지 못했습니다.', code='save_unconfirmed')
        except HwarangAuthError as exc:
            uncertain = exc.code in ('transport_error', 'save_unconfirmed') or (exc.status or 0) >= 500
            same_retry = exc.code == '40001' and d.get('unconfirmed_request') == request
            if not (uncertain or same_retry):
                raise
            try:
                result = confirmed_save(db, request, d.get('old') or {})
            except HwarangAuthError:
                result = None
            if result is None:
                raise HwarangAuthError('서버에서 처리 여부를 확인하지 못했습니다.', code='save_unconfirmed') from exc
        d['old']=result['report'];d['server_draft']=result.get('draft')
        d['baseline']=deepcopy(d['values']);d['saved_at']=datetime.now(KST).strftime('%H:%M:%S')
        d.pop('save_error',None);d.pop('conflict',None);d.pop('retry_submit',None);d.pop('unconfirmed_request',None)
        if submit:d['notice']='제출했습니다.'
        if slot is not None:slot.caption('제출 완료' if submit else '임시 저장됨 · '+d['saved_at'])
        return True
    except HwarangAuthError as exc:
        prefix = '처리 결과 미확인' if exc.code == 'save_unconfirmed' else '저장 실패'
        d['save_error']=prefix+' · 입력 내용은 유지됩니다. '+str(exc);d['conflict']=True
        d['retry_submit'] = submit
        if exc.code == 'save_unconfirmed':
            d['unconfirmed_request'] = request
        else:
            d.pop('unconfirmed_request', None)
        if slot is not None:slot.error(d['save_error'])
        return False
    finally:d['saving']=False


@st.dialog('청약·계약 입력 및 수정',width='large',dismissible=True,on_dismiss='rerun')
def contract_dialog(db,day):
    from modules.activity.contracts import contract_editor
    contract_editor(db,day,expanded=True)
    if st.button('닫기',key='record_contract_close'):st.rerun()


def render(db,today,period,fixed_day=None):
    if period=="주간":
        from modules.activity.period_summary import render as summary
        return summary(db,today)
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
        from modules.activity.live_sync import attach
        attach(db,day,day,db.uid)
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
        changed=not ux.same_draft_values(v,values_from(old.get('data',{})))
        state='제출 완료 · 수정 초안' if old.get('submitted') and (changed or d.get('server_draft')) else '제출 완료' if old.get('submitted') else '임시 저장' if old else '작성 전'
        date_label=f'{day:%Y.%m.%d}'+(f' – {day+6*DAY:%m.%d}' if period=='주간' else ' '+ '월화수목금토일'[day.weekday()]+'요일')
        st.html('<div class="record-meta"><span>'+date_label+'</span><span class="record-state'+(' is-submitted' if old.get('submitted') else '')+'">'+escape(state)+'</span></div>')
        status_slot=st.empty()
        if d.get('save_error'):
            status_slot.error(d['save_error'])
            retry_submit = d.get('retry_submit', False)
            if st.button('다시 제출' if retry_submit else '다시 저장', key=key+'retry'):
                if persist(db,d,day,period,submit=retry_submit,slot=status_slot) and retry_submit:
                    if fixed_day is not None:ux.back()
                    else:ux.refresh()
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
        def import_values(source):
            ux.set_values(d,merge_source(v,source));persist(db,d,day,period,slot=status_slot)
        if period=='주간':
            states=day_states(day,today,daily,events)
            st.caption('일일 기록 · '+' · '.join(f'{label} {sum(s==label for _,s,_ in states)}일' for label in ('제출','임시 저장','미작성')))
            if v['source_versions'] and v['source_versions']!=source['source_versions']:st.info('일일 기록이 변경되었습니다. 직접 수정한 항목을 유지하며 초안을 갱신할 수 있습니다.')
            st.button('일일 기록에서 초안 가져오기',key=key+'import',on_click=import_values,args=(source,),disabled=not source['coverage'])
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
                st.html('<div class="record-count-summary">'+''.join(f'<div class="record-count-item"><span>{c}</span><strong>{list(sources.values()).count(c)}<small>건</small></strong></div>' for c in COUNTS)+'</div>')
                st.caption('직접 수정한 값은 유지됩니다.')
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
        if mobile:
            with st.expander('일정·집계·참고 자료',expanded=False,key=key+'references',on_change='rerun') as panel:
                if panel.open:references()
        left,right=st.columns([1.85,1],gap='medium') if not mobile else (st.container(),None)
        with left:
            with st.container(border=True,key='daily_inputs'+suffix):
                st.html('<div class="record-section-heading" role="heading" aria-level="3">활동 건수</div>')
                width=2 if mobile else 3
                for offset in range(0,len(COUNTS),width):
                    for col,name in zip(st.columns(width),COUNTS[offset:offset+width]):
                        ux.field(d,name,col.number_input,name,min_value=0,max_value=99999999,step=1,format='%d',after_change=edit(name))
                if period=='일일':ux.field(d,'no_activity',st.checkbox,'활동 없는 날',after_change=edit('no_activity'))
                ux.field(d,'note',st.text_area,'주요 성과 · 진행사항',height=140,placeholder='오늘의 성과와 진행 내용을 남겨주세요.' if period=='일일' else '이번 주의 주요 성과를 정리해 주세요.',after_change=edit('note'))
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
                    from modules.activity.support_request import picker
                    picker(db,d,after_change=edit('help_recipient'))
                    ux.field(d,'help',st.text_area,'지원받을 내용',height=80,after_change=edit('help'))
        if right is not None:
            with right:
                with st.container(border=True,key='daily_reference_card'+suffix):references()
        with left:
            with st.container(key='daily_footer'+suffix,horizontal=True,vertical_alignment='center'):
                st.caption('수정 초안은 다시 제출하기 전까지 기존 제출 내용에 반영되지 않습니다.' if old.get('submitted') else '자동 저장 · 제출 전까지 수정 가능')
                if st.button('임시 저장',key=key+'draft',disabled=bool(d.get('saving'))):
                    if not persist(db,d,day,period,slot=status_slot) and 'retry_submit' in d:ux.refresh()
                if st.button('수정 내용 제출' if old.get('submitted') else '제출하기',key=key+'submit',type='primary',disabled=bool(d.get('saving')) or bool(old.get('submitted') and not changed and not d.get('server_draft'))):
                    if persist(db,d,day,period,True,status_slot):
                        if fixed_day is not None:ux.back()
                        else:ux.refresh()
                    elif 'retry_submit' in d:ux.refresh()
            if old:
                with st.expander('제출 이력·피드백',key=key+'history',on_change='rerun') as panel:
                    if panel.open:
                        from modules.activity.center import report_detail
                        report_detail(db,d.get('old') or old)
        return key


def styles():
    st.html('''<style>
.record-count-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:4px 0 8px}
.record-count-item{background:#f7f9fc;border:1px solid #dce4ee;border-radius:10px;padding:10px 6px;text-align:center;min-width:0}
.record-count-item span{display:block;font-size:13px;color:#52647c;white-space:nowrap}
.record-count-item strong{display:block;font-size:22px;line-height:1.5;color:#172b49}
.record-count-item small{font-size:12px;font-weight:400;margin-left:3px}

/* Keep headings in a real measured block, independent of markdown heading metrics. */
[class*="st-key-daily_record"]{gap:12px!important}
[class*="st-key-daily_record"] .record-meta{display:flex;align-items:center;flex-wrap:wrap;gap:10px;min-height:30px;color:#53657c;font-size:14px}
[class*="st-key-daily_record"] .record-state{background:#eaf0f8;color:#426080;border:1px solid #dce6f1;padding:3px 10px;border-radius:20px;font-size:12px}
[class*="st-key-daily_record"] .record-state.is-submitted{background:#e9f5f2;color:#216959;border-color:#cfe9e1}
[class*="st-key-daily_inputs"]{padding:20px!important;border:1px solid #dce4ee!important;border-radius:16px!important;background:#fff;gap:14px!important;box-shadow:0 3px 12px #18365004}
[class*="st-key-daily_inputs"] [data-testid="stElementContainer"]:has(.record-section-heading){height:auto!important;min-height:42px!important;flex-shrink:0!important}
[class*="st-key-daily_inputs"] .record-section-heading{box-sizing:border-box;display:flex;align-items:center;min-height:42px;padding:0 0 12px;margin:0;font-size:20px;line-height:30px;color:#172f4a;font-weight:700}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"]{padding:10px 12px!important;background:#f8fafd!important;border:1px solid #e0e7f0!important;border-radius:12px!important}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"] input{font-size:22px!important;line-height:1.5!important;color:#183c64!important;background:transparent!important}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"] label{margin-bottom:6px!important;color:#4a607b!important}
[class*="st-key-daily_inputs"] [data-testid="stNumberInput"] button{min-width:30px!important;background:transparent!important}
[class*="st-key-daily_inputs"] [data-testid="stTextArea"] textarea{background:#f9fbfd!important;border:1px solid #dce5ef!important;border-radius:10px!important;padding:12px!important;line-height:1.65!important}
[class*="st-key-daily_inputs"] [data-testid="stTextArea"] label{margin-bottom:8px!important}
[class*="st-key-daily_navigation"]{justify-content:flex-start!important;flex-wrap:nowrap!important;gap:8px!important}
[class*="st-key-daily_navigation"]>[data-testid="stElementContainer"]{flex:0 0 auto!important;width:auto!important}
[class*="st-key-daily_navigation"] [data-testid="stDateInput"]{width:190px!important}
[class*="st-key-daily_navigation"] button{min-height:42px!important;border-radius:10px!important}
[class*="st-key-daily_reference_card"]{padding:18px!important;border:1px solid #e0e7ef!important;border-radius:16px!important;gap:12px!important;background:#fff}
[class*="st-key-daily_reference_card"] [data-testid="stCaptionContainer"]{font-size:12px!important;color:#718096!important}
[class*="st-key-daily_footer"]{justify-content:flex-end!important;align-items:center!important;flex-wrap:wrap!important;padding:12px 14px!important;border:1px solid #dce5ef!important;border-radius:12px!important;background:#fff!important;box-shadow:none!important;gap:8px!important;margin-top:4px!important}
[class*="st-key-daily_footer"]>[data-testid="stElementContainer"]{flex:0 0 auto!important;width:auto!important}
[class*="st-key-daily_footer"] [data-testid="stCaptionContainer"]{font-size:12px!important;color:#718096!important}
[class*="st-key-daily_footer"] button{min-height:44px!important;min-width:94px!important;border-radius:10px!important}
.st-key-mobile_record_tab button{border:0!important;border-bottom:2px solid transparent!important;border-radius:0!important;background:transparent!important;padding:8px 18px!important}
.st-key-mobile_record_tab button[aria-checked="true"]{border-bottom-color:#2d6ad5!important;color:#2d6ad5!important;background:#edf3ff!important}
@media(max-width:700px){
 [class*="st-key-daily_inputs"]{padding:14px!important;gap:12px!important}
 [class*="st-key-daily_navigation"] [data-testid="stDateInput"]{width:150px!important}
 [class*="st-key-daily_inputs"] [data-testid="stNumberInput"]{padding:8px!important}
 [class*="st-key-daily_footer"]{position:static!important}
 [class*="st-key-daily_footer"] button{min-width:104px!important}
 [class*="st-key-daily_inputs"] .record-section-heading{font-size:18px;min-height:40px}
}
</style>''')
