"""Daily report editor using the existing authorized Records API and session drafts."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from uuid import uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo
from pathlib import Path
import streamlit.components.v1 as components
import streamlit as st
from modules.activity import ux
from modules.shared.hwarang_auth import HwarangAuthError

COUNTS=['TA','AP','PC','CS','약속 확보','상담','제안','청약']
KST=ZoneInfo('Asia/Seoul')


def payload(d,uid,day,submitted):
    """Keep retired and unknown historical fields when editing an existing report."""
    data=deepcopy((d['old'] or {}).get('data',{}))
    data['counts']={**data.get('counts',{}),**{c:int(d['values'][c]) for c in COUNTS}}
    data.update({k:deepcopy(d['values'][k]) for k in ('note','plan','help','sources','coverage','contracts','results')})
    data['no_activity']=bool(submitted and not any(d['values'][c] for c in COUNTS))
    body={'period':'일일','day':str(day),'submitted':submitted,'data':data}
    if not d['old']:body['id']=str(uuid5(NAMESPACE_URL,uid+'일일'+str(day)))
    return body


def save(db,d,day,submitted):
    if d.get('saving'):return False
    d['saving']=True
    d['retry_submitted']=submitted
    try:
        body=payload(d,db.uid,day,submitted)
        db.save('sales_reports',body,d['old'])
        rows=db.period('sales_reports',day,day,owner='eq.'+db.uid,period='eq.일일')
        if not rows or any(rows[0].get(k)!=v for k,v in body.items()):
            raise HwarangAuthError('저장된 내용이 변경되었습니다. 최신 기록을 확인해 주세요.')
        d['old']=rows[0]
        d['baseline']=deepcopy(d['values'])
        d['saved_at']=datetime.now(KST).strftime('%H:%M')
        for key in ('save_error','confirm','conflict','retry_submitted'):d.pop(key,None)
        st.session_state['sales_dialog_notice']='기록을 제출했습니다.' if submitted else '임시 저장했습니다. 서버에 보관된 기록입니다.'
        return True
    except HwarangAuthError as exc:
        d['save_error']='저장을 확인하지 못했습니다. 입력 내용은 유지됩니다. '+str(exc)
        d['conflict']=True
        return False
    finally:
        d['saving']=False


def reference(db,day,events):
    from modules.activity.redesign import event_list
    label='오늘 일정' if day==datetime.now(KST).date() else f'{day.month}월 {day.day}일 일정'
    st.markdown('**'+label+f' · {len(events)}건**')
    st.caption('일정을 누르면 상세 내용을 확인할 수 있어요.')
    with st.container(height=min(440,130*len(events)) if events and not ux.compact() else 'content',key='daily_schedule_list'):
        event_list(db,events,'daily_reference_')


def render(db,today,fixed_day=None):
    from modules.activity.redesign import report_key
    from modules.activity.center import report_detail
    from modules.activity.contracts import contract_editor
    styles()
    period='일일';nav='sales_day_일일';active='sales_report_active_일일'
    mobile=ux.compact()
    with st.container(key='daily_record'):
        if fixed_day is None:
            st.session_state.setdefault(nav,today)
            def move(delta):st.session_state[nav]=min(today,st.session_state[nav]+timedelta(days=delta))
            def current():st.session_state[nav]=today
            with st.container(key='daily_navigation',horizontal=True,vertical_alignment='center'):
                st.button('‹',key='daily_previous',help='이전 날',on_click=move,args=(-1,))
                selected=st.date_input('기록 날짜',max_value=today,key=nav,label_visibility='collapsed')
                st.button('›',key='daily_next',help='다음 날',on_click=move,args=(1,),disabled=selected>=today)
                st.button('오늘',key='daily_today',on_click=current)
            previous=st.session_state.get(active)
            pending=previous and previous!=str(selected) and ux.dirty(report_key(db,previous,period))
            day=date.fromisoformat(previous) if pending else selected
            if not pending:st.session_state[active]=str(day)
        else:day=fixed_day;pending=False
        key=report_key(db,day,period)
        if fixed_day is None:st.session_state['sales_active_draft']=key
        rows=db.period('sales_reports',day,day,owner='eq.'+db.uid,period='eq.일일')
        old=rows[0] if rows else {}
        data=old.get('data',{})
        initial={**{c:int(data.get('counts',{}).get(c,0) or 0) for c in COUNTS},
                 **{k:data.get(k,'') for k in ('note','plan','help')},
                 **{k:data.get(k,{} if k=='sources' else []) for k in ('sources','coverage','contracts','results')}}
        d=ux.draft(key,initial,old)
        # Add the new independent counters to drafts already open during deployment.
        for c in COUNTS:
            d['values'].setdefault(c,initial[c]);d['baseline'].setdefault(c,initial[c])
        v=d['values'];old=d['old'] or {}
        st.html('<span class="daily-context" data-context="'+d['epoch']+'"></span>')
        with st.container(key='daily_layout_bridge'):
            components.html(Path(__file__).with_name('daily_bridge.html').read_text(),height=0)
        for panel in (d['epoch']+'help_panel',key+'source_panel'):
            if panel in st.session_state:st.session_state[panel]=st.session_state[panel]

        if pending:
            st.warning(f'{day:%m월 %d일} 기록에 저장하지 않은 내용이 있습니다.')
            if old.get('submitted'):st.caption('저장 후 이동하면 제출된 기록에 수정 내용이 반영됩니다.')
            a,b,c=st.columns(3)
            if a.button('저장 후 이동',key='daily_save_move'):
                if save(db,d,day,bool(old.get('submitted'))):st.session_state[active]=str(selected)
                ux.refresh()
            if b.button('저장하지 않고 이동',key='discard_date_일일'):
                ux.clear_draft(key);st.session_state[active]=str(selected);ux.refresh()
            def stay():st.session_state[nav]=day
            c.button('계속 작성',key='keep_date_일일',on_click=stay)
        if d.get('save_error'):
            st.error(d['save_error'])
            if st.button('다시 저장',key=key+'retry'):
                save(db,d,day,d.get('retry_submitted',bool(old.get('submitted'))));ux.refresh()
            ux.conflict_recovery(d,key)
        ux.feedback()
        state='수정사항 미저장' if old.get('submitted') and ux.dirty(key) else '제출 완료' if old.get('submitted') else '작성 중' if ux.dirty(key) else '임시 저장' if old else '작성 전'
        ux.summary([f'{day:%Y.%m.%d} '+ '월화수목금토일'[day.weekday()]+'요일',state])
        events=db.period('sales_events',day,day,owner='eq.'+db.uid,order='day.asc,start_time.asc.nullsfirst')
        reference_label='오늘 일정' if day==today else f'{day.month}월 {day.day}일 일정'
        tab=st.segmented_control('일일 기록 화면',['기록 작성',reference_label],default='기록 작성',required=True,key=key+'view',label_visibility='collapsed') if mobile else '기록 작성'
        left,right=st.columns([1.55,1],gap='medium') if not mobile else (st.container(),None)
        if tab=='기록 작성':
            with left:
                with st.container(border=True,key='daily_inputs'):
                    st.markdown('### 활동 종류')
                    st.caption('각 항목의 건수를 입력하세요.')
                    width=2 if mobile else 4
                    for offset in range(0,len(COUNTS),width):
                        cols=st.columns(width)
                        for col,name in zip(cols,COUNTS[offset:offset+width]):
                            ux.field(d,name,col.number_input,name,min_value=0,step=1,format='%d')
                    ux.field(d,'note',st.text_area,'주요 성과 · 진행사항',height=110,placeholder='예: 상담 진행 내용, 고객 반응, 다음에 확인할 사항')
                    with st.expander('지원 요청 · 선택',key=d['epoch']+'help_panel',on_change='rerun'):
                        ux.field(d,'help',st.text_input,'지원받을 내용',placeholder='필요한 지원이 있을 때 입력하세요')
                    if v['help']:st.caption('지원 요청 · 입력됨')
                source_panel=st.expander('완료 일정 · 청약에서 집계 초안 확인',key=key+'source_panel',on_change='rerun')
                if source_panel.open:
                    with source_panel:
                        contracts=db.period('sales_contracts',day,day,owner='eq.'+db.uid)
                        linked={r['event'] for r in contracts}
                        completed=[r for r in events if r['status']=='완료']
                        current={r['id']:r['kind'] for r in completed if r['kind'] in COUNTS and not(r['kind']=='청약' and r['id'] in linked)}
                        current.update({r['id']:'청약' for r in contracts})
                        proposed=ux.refreshed_counts(v,v['sources'],current,COUNTS)
                        st.dataframe([{'항목':c,'현재 입력':v[c],'반영 후':proposed[c]} for c in COUNTS],hide_index=True,width='stretch')
                        st.caption('AP·PC는 각각 같은 활동 종류로 가져옵니다. 상담·제안으로 바꾸지 않으며, 이미 가져온 일정은 중복 합산하지 않습니다.')
                        def apply():
                            ux.set_values(d,{**proposed,'sources':current,'contracts':contracts,'results':[{'결과':e['result'],'지원 요청':e['help']} for e in completed if e['result'] or e['help']]})
                        st.button('이 집계 초안 반영',key=key+'import',on_click=apply)
                contract_editor(db,day)
                if old:
                    history=st.expander('기존 제출 내용 · 수정 이력 · 피드백',key=key+'history_panel',on_change='rerun')
                    if history.open:
                        with history:report_detail(db,old)
        if right is not None:
            with right:
                with st.container(border=True,key='daily_reference_card'):reference(db,day,events)
        elif tab!='기록 작성':reference(db,day,events)
        with st.container(key='daily_footer'):
            if saved_at:=d.get('saved_at'):st.caption('마지막 저장 '+saved_at)
            elif old.get('changed_at'):
                try:st.caption('마지막 저장 '+datetime.fromisoformat(old['changed_at'].replace('Z','+00:00')).astimezone(KST).strftime('%m.%d %H:%M'))
                except ValueError:pass
            a,b=st.columns(2)
            draft_slot=a.empty();submit_slot=b.empty()
            is_clean=not ux.dirty(key)
            save_draft=draft_slot.button('임시 저장',key=key+'draft',width='stretch',disabled=bool(old.get('submitted')) or bool(d.get('saving')))
            if submit_slot.button('수정 내용 제출' if old.get('submitted') else '제출하기',key=key+'submit',type='primary',width='stretch',disabled=bool(d.get('saving')) or bool(old.get('submitted') and is_clean)):
                d['confirm']=True
            submit=False
            if d.get('confirm'):
                empty=not any(v[c] for c in COUNTS)
                st.info('8개 활동 항목이 모두 0건입니다. 활동 없는 날로 제출할까요?' if empty else '입력한 내용으로 기록을 제출할까요?')
                x,y=st.columns(2)
                confirm_slot=x.empty()
                submit=confirm_slot.button('활동 없는 날로 제출' if empty else '제출 확인',key=key+'confirm',type='primary')
                if y.button('계속 작성',key=key+'cancel_submit'):d.pop('confirm',None);ux.refresh()
            if save_draft or submit:
                (confirm_slot if submit else draft_slot).button('저장 중…',disabled=True,key=key+'busy')
                if save(db,d,day,bool(submit)) and fixed_day is not None:ux.back()
                ux.refresh()
        return key


def styles():
    st.html('''<style>
    .st-key-daily_record{gap:12px!important;padding-bottom:8px}
    .st-key-daily_layout_bridge,.st-key-daily_record [data-testid="stElementContainer"]:has(>.stHtml>.daily-context){display:none!important}
    .st-key-daily_navigation{gap:8px!important}
    .st-key-daily_navigation [data-testid="stDateInput"]{max-width:240px}
    .st-key-daily_inputs{padding:18px!important;border-radius:14px!important;background:#fff}
    .st-key-daily_reference_card{background:#fff}
    .st-key-daily_inputs h3{font-size:20px!important;padding-top:0!important;padding-bottom:0!important}
    .st-key-daily_inputs [data-testid="stNumberInput"]{border:1px solid #dce3ed;border-radius:10px;padding:10px;background:#fff}
    .st-key-daily_inputs [data-testid="stNumberInput"] input{font-size:22px!important;text-align:center;border:0!important}
    .st-key-daily_inputs [data-testid="stNumberInput"] button{min-width:28px!important}
    .st-key-daily_inputs :is(input,textarea)::placeholder{color:#98a3b2!important;font-weight:400!important;opacity:1}
    .st-key-daily_record>[data-testid="stLayoutWrapper"]:has(>.st-key-daily_footer){position:sticky;bottom:var(--daily-keyboard-inset,0px);z-index:5}
    .st-key-daily_footer{background:#fff;border-top:1px solid #dce3ed;padding:10px 12px max(10px,env(safe-area-inset-bottom));box-shadow:0 -4px 12px #172e4d08;gap:6px!important}
    .st-key-daily_footer button{min-height:44px}
    .st-key-daily_footer button[kind="primary"]{background:#146f76!important;border-color:#146f76!important}
    .st-key-daily_record [data-testid="stButtonGroup"] button[role="radio"]{border:0!important;border-radius:0!important;background:transparent!important;border-bottom:2px solid transparent!important}
    .st-key-daily_record [data-testid="stButtonGroup"] button[aria-checked="true"]{border-bottom-color:#2d6ad5!important;color:#2d6ad5!important}
    @media(max-width:700px){
      .st-key-daily_record{gap:8px!important}
      .st-key-daily_navigation [data-testid="stDateInput"]{max-width:160px}
      .st-key-daily_inputs{padding:12px!important}
      .st-key-daily_footer [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:10px!important}
      .st-key-daily_footer [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:0!important;width:calc(50% - 5px)!important;flex:1!important}
      .st-key-daily_inputs [data-testid="stNumberInput"]{padding:7px!important}
      .st-key-daily_inputs [data-testid="stNumberInput"] label{margin-bottom:2px!important}
      .st-key-daily_inputs [data-testid="stNumberInput"] input{font-size:20px!important}
      .st-key-daily_inputs [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:10px!important}
      .st-key-daily_inputs [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:0!important;width:calc(50% - 5px)!important;flex:1!important}
      .st-key-daily_record :is(input,textarea){font-size:16px!important;scroll-margin-block:90px}
    }
    </style>''')
