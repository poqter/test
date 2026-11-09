"""Activity workspace views. All reads/writes use the caller's existing Records/RLS."""
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from uuid import uuid4, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo
KST=ZoneInfo("Asia/Seoul")
import re
import streamlit as st
from modules.activity import ux
from modules.activity.contracts import contract_editor, performance, conversions
from modules.shared.hwarang_auth import HwarangAuthError

DAY=timedelta(days=1)
from modules.activity.daily import COUNTS
KINDS=["미분류","TA","AP","PC","CS","청약","교육","회의","휴무","기타"]
TYPES={code:code for code in ("TA","AP","PC","CS")}

def notify():
    st.session_state["sales_dialog_notice"]="저장했습니다."

def write_event(db,old,body,follow=None):
    follow_id=str(uuid5(NAMESPACE_URL,old["id"]+str(follow))) if follow else None
    try:
        ok=db.request("POST","rpc/sales_edit_event",body={"p_id":old["id"],"p_revision":old["revision"],"p_data":body,"p_follow":str(follow) if follow else None,"p_follow_id":follow_id})
        if ok:return
    except HwarangAuthError:
        pass
    # An exact state match resolves a lost successful response, not a conflicting edit.
    current=db.request("GET","sales_events",{"id":"eq."+old["id"],"limit":"1"})
    if current and all(current[0].get(k)==v for k,v in body.items() if not k.startswith('follow_')):
        if not follow:return
        linked=db.request("GET","sales_events",{"id":"eq."+follow_id,"limit":"1"})
        if linked and linked[0].get("previous_event")==old["id"] and all(linked[0].get(k.removeprefix('follow_'))==v for k,v in body.items() if k.startswith('follow_')):return
    raise HwarangAuthError("다른 화면의 변경 또는 통신 오류가 있습니다. 작성 내용은 유지됩니다. 최신 기록을 확인한 뒤 다시 시도해 주세요.")

def event_body(values):
    start=values["start"] if values["mode"]=="시간 지정" else None
    end=values["end"] if start else None
    return dict(day=str(values["day"]),start_time=str(start) if start else None,end_time=str(end) if end else None,
                time_pending=values["mode"]=="시간 미정",title=values["title"].strip(),kind=values["kind"],place=values["place"],
                note=values["note"],help=values["help"] if values["support"] else "",help_recipient=values.get("help_recipient") if values["support"] else None,common=values["common"],
                companion=values["companion"],status=values["status"],result=values["result"])

def follow_time_body(v):
    from modules.activity.calendar_service import parse_clock
    start=parse_clock(str(v['follow_start'])) if v.get('follow_start') else None
    end=parse_clock(str(v['follow_end'])) if v.get('follow_end') else None
    if end and (not start or end<=start):raise ValueError('새 일정 종료 시간은 시작 시간보다 늦어야 합니다.')
    return dict(follow_start_time=start,follow_end_time=end,follow_time_pending=not bool(start))

def event_errors(v):
    errors={}
    if v.get("support") and v.get("help", "").strip() and not v.get("help_recipient"):errors["help_recipient"]="지원 요청 대상을 선택해 주세요."
    if not v["title"].strip():errors["title"]="일정명을 입력해 주세요."
    if v["mode"]=="시간 지정":
        if not v["start"]:errors["start"]="시작 시간을 입력해 주세요."
        elif v["end"] and v["end"]<=v["start"]:errors["end"]="종료 시간은 시작 시간보다 늦어야 합니다."
    if v["follow"] and v["follow"]<v["day"]:errors["follow"]="후속 일정 날짜를 확인해 주세요."
    if v.get('follow'):
        try:follow_time_body(v)
        except ValueError as exc:errors['follow']=str(exc)
    return errors


def event_editor(db,day,event=None,parent=None,copy=None):
    old=event or copy or {}
    key=f'event:{db.uid}:{event["id"] if event else "copy:"+copy["id"] if copy else "follow:"+parent["id"] if parent else "new:"+str(day)}'
    initial=dict(day=date.fromisoformat(old.get("day",str(day))),title=old.get("title",parent["title"] if parent else ""),
        kind=old.get("kind",{"TA":"AP","AP":"PC"}.get(parent["kind"],"미분류") if parent else "미분류"),
        mode="시간 미정",start=time.fromisoformat(old["start_time"]) if old.get("start_time") else None,
        end=time.fromisoformat(old["end_time"]) if old.get("end_time") else None,place=old.get("place","") or "",note=old.get("note","") or "",
        help=old.get("help","") if event else "",help_recipient=old.get("help_recipient") if event else None,support=bool(event and old.get("help")),companion=old.get("companion"),
        repeat=False,repeats=1,common=old.get("common",False) if event else False,status=old.get("status","예정") if event else "예정",
        result=old.get("result","") if event else "",follow=None,
        follow_start=(old.get('start_time') or '')[:5],follow_end=(old.get('end_time') or '')[:5])
    initial["mode"]="시간 지정" if old.get("start_time") else "시간 미정" if not old or old.get("time_pending") else "종일"
    d=ux.draft(key,initial,event)
    for name in ('follow_start','follow_end'):
        d['values'].setdefault(name,initial[name])
    ux.conflict_recovery(d,key)
    v=d["values"]
    if copy:st.caption("날짜와 시간을 확인한 뒤 새 일정으로 저장해 주세요.")
    # Reuse loaded/saved personal events: no network round trip when opening a form.
    if "recent" not in d:
        d["recent"]=deepcopy(st.session_state.get("sales_recent_"+db.uid,[]))
    def infer_kind():
        if not event and not parent and not copy and not d.get("manual_kind"):
            matches=set(re.findall(r"(?<![A-Za-z0-9])(AP|PC|TA|CS)(?![A-Za-z0-9])",v["title"].upper()))
            ux.set_values(d,{"kind":matches.pop() if len(matches)==1 else "미분류"})
    def select_kind():
        d["manual_kind"]=True
        if v["kind"]=="휴무":
            updates={"mode":"종일"}
            if not v["title"].strip():updates["title"]="휴무"
            ux.set_values(d,updates)
    errors=event_errors(v) if d.get("attempted") else {}
    ux.field(d,"title",st.text_input,"일정명",max_chars=200,placeholder="예: 소개 고객 첫 상담",after_change=infer_kind)
    if "title" in errors:st.error(errors["title"])
    a,b=st.columns(2)
    ux.field(d,"day",a.date_input,"날짜")
    options=list(dict.fromkeys([*KINDS,v["kind"]]))
    ux.field(d,"kind",b.selectbox,"활동 종류",options=options,format_func=lambda k:TYPES.get(k,k),after_change=select_kind)
    ux.field(d,"mode",st.segmented_control,"시간",options=["시간 지정","종일","시간 미정"],selection_mode="single",required=True)
    if v["mode"]=="시간 지정":
        a,b=st.columns(2)
        previous=d.get("last_start",v["start"])
        # on_change ran before this render; move end only when the start changed.
        if previous!=v["start"]:
            ux.set_values(d,{"end":ux.shifted_end(previous,v["start"],v["end"])})
        d["last_start"]=v["start"]
        ux.field(d,"start",a.time_input,"시작 시간")
        ux.field(d,"end",b.time_input,"종료 시간 · 선택")
        if v["end"] and (not v["start"] or v["end"]<=v["start"]): st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
        if "start" in errors:st.error(errors["start"])
        if not v["start"]: st.caption("시작 시간을 입력하거나 ‘시간 미정’을 선택해 주세요.")
    ux.field(d,"place",st.text_input,"장소 · 선택",placeholder="예: 지점 상담실, 고객 방문, 전화 상담")
    populated=any((v["note"],v["companion"],v["support"],v["repeat"],v["common"]))
    extra=st.expander("추가 정보 · 선택",key=d["epoch"]+"extra",on_change="rerun")
    if extra.open:
        with extra:
            ux.field(d,"note",st.text_area,"메모",height=90)
            people={r["member"]:r["label"] for r in db.request("POST","rpc/sales_branch_members",body={}) if r["member"]!=db.uid}
            recent_people=list(dict.fromkeys(r.get("companion") for r in d["recent"] if r.get("companion") in people))[:5]
            choices=list(dict.fromkeys([None,*recent_people,*people,*([v["companion"]] if v["companion"] else [])]))
            ux.field(d,"companion",st.selectbox,"동행자",options=choices,format_func=lambda u:(("최근 · " if u in recent_people else "")+people.get(u,"기존 동행자")) if u else "선택 안 함")
            ux.field(d,"support",st.toggle,"지원 요청")
            if v["support"]:
                from modules.activity.support_request import picker
                picker(db,d)
                ux.field(d,"help",st.text_input,"지원받을 내용")
                if errors.get("help_recipient"):st.error(errors["help_recipient"])
            if not event:
                ux.field(d,"repeat",st.toggle,"매주 반복")
                if v["repeat"]: ux.field(d,"repeats",st.number_input,"총 등록 횟수 · 이번 일정 포함",min_value=1,max_value=52)
            if db.me["managed"]: ux.field(d,"common",st.checkbox,"지점 공통 일정")
    if populated:st.caption("추가 정보 · 입력됨")
    if event:
        with st.container(key="sales_status_emphasis"), st.expander("처리 상태 · 활동 결과",expanded=d["baseline"]["status"]!="예정",key=d["epoch"]+"state",on_change="rerun"):
            ux.field(d,"status",st.selectbox,"처리 상태",options=["예정","완료","연기","취소"])
            ux.field(d,"result",st.text_area,"활동 결과",height=80)
            ux.field(d,"follow",st.date_input,"후속 일정 날짜 · 선택")
            if v['follow']:
                ux.field(d,'follow_start',st.text_input,'새 일정 시작 시간')
                ux.field(d,'follow_end',st.text_input,'새 일정 종료 시간 · 선택')
            if v["follow"] and v["follow"]<v["day"]:st.error("후속 일정 날짜는 현재 일정 날짜 이후로 선택해 주세요.")
    with st.container(key="sales_event_save"):
        save_slot=st.empty()
    if save_slot.button("변경 저장" if event else "일정 등록",type="primary",key=key+"save",on_click=lambda:d.update(attempted=True)):
        errors=event_errors(v)
        if errors:
            ux.focus_field(d,next(iter(errors)))
            return key
        body=event_body(v)
        if event and v.get('follow'):
            body.update(follow_time_body(v))
        repeat=v["repeats"] if v["repeat"] and not event else 1
        if body["start_time"] and body["status"]=="예정":
            candidates=db.period("sales_events",v["day"],v["day"]+7*(repeat-1)*DAY,owner="eq."+db.uid,status="eq.예정")
            days={str(v["day"]+7*i*DAY) for i in range(repeat)}
            overlap=[r for r in candidates if r["id"]!=(event or {}).get("id") and r["day"] in days and r.get("start_time") and
                (r["start_time"]==body["start_time"] or r["start_time"]<(body["end_time"] or body["start_time"]) and (r.get("end_time") or r["start_time"])>body["start_time"])]
            if body['companion']:
                # Branch summary exposes only the already-authorized time/kind fields.
                stop=v['day']+7*(repeat-1)*DAY
                cursor=v['day']
                while cursor<=stop:
                    edge=min(stop,cursor+62*DAY)
                    summaries=db.request('POST','rpc/sales_calendar_days',body={'first_day':str(cursor),'last_day':str(edge)})
                    overlap.extend(r for r in summaries if r['id']!=(event or {}).get('id') and r['day'] in days and r['status']=='예정' and body['companion'] in (r['owner'],r.get('companion')) and r.get('start_time')==body['start_time'])
                    cursor=edge+DAY
            signature=(str(v["day"]),body["start_time"],body["end_time"],body['companion'],repeat,tuple(r["id"] for r in overlap))
            if overlap and d.get("overlap")!=signature:
                d["overlap"]=signature;st.warning("본인 또는 동행자의 기존 일정과 시간이 겹칩니다. 그대로 등록하려면 저장 버튼을 한 번 더 눌러 주세요.");return key
        save_slot.button("저장 중…",disabled=True,key=key+"busy")
        st.session_state["sales_write_in_progress"]=True
        if event:
            snapshot=d["old"]
            try:write_event(db,snapshot,body,v["follow"])
            except HwarangAuthError:
                d["conflict"]=True;raise
        else:
            seed=d.setdefault("seed",str(uuid4()))
            rows=[{**body,"unit":db.me["unit"],"previous_event":parent["id"] if parent else None,"series_id":seed if repeat>1 else None,"day":str(v["day"]+i*7*DAY),"id":str(uuid5(NAMESPACE_URL,seed+str(i)))} for i in range(repeat)]
            try:
                db.request("POST","sales_events",body=rows,prefer="resolution=ignore-duplicates")
                stored=db.request("GET","sales_events",{"id":"in.("+",".join(r["id"] for r in rows)+")"})
                indexed={r["id"]:r for r in stored}
                if any(r["id"] not in indexed or any(indexed[r["id"]].get(k)!=value for k,value in r.items()) for r in rows):
                    raise HwarangAuthError("같은 저장 요청의 기존 내용과 현재 입력이 다릅니다. 입력은 유지됩니다. 최신 일정을 확인해 주세요.")
            except HwarangAuthError:
                d["conflict"]=True;raise
        ux.remember_recent(db.uid,[{**body,"id":event["id"] if event else rows[0]["id"],"owner":db.uid}])
        st.session_state["sales_anchor"]=v["day"]
        ux.saved_event(key,event["id"] if event else rows[0]["id"])
    if event:delete_control(db,event)
    return key

def quick_result(db,row):
    key="result:"+row["id"]
    d=ux.draft(key,{"status":"완료","result":row.get("result", ""),"follow":max(date.fromisoformat(row["day"]),datetime.now(KST).date())+DAY,"follow_start":(row.get('start_time') or '')[:5],"follow_end":(row.get('end_time') or '')[:5]},row)
    for name,source in (('follow_start','start_time'),('follow_end','end_time')):
        d['values'].setdefault(name,(row.get(source) or '')[:5])
    ux.conflict_recovery(d,key)
    ux.field(d,"status",st.segmented_control,"처리 결과",options=["완료","연기","취소"],required=True)
    ux.field(d,"result",st.text_area,"활동 결과 · 선택",height=80)
    if d["values"]["status"]=="연기":
        ux.field(d,"follow",st.date_input,"새 일정 날짜",min_value=date.fromisoformat(row["day"]))
        ux.field(d,"follow_start",st.text_input,"새 일정 시작 시간")
        ux.field(d,"follow_end",st.text_input,"새 일정 종료 시간 · 선택")
    save_slot=st.empty()
    if save_slot.button("결과 저장",type="primary"):
        save_slot.button("저장 중…",disabled=True,key=key+"busy")
        st.session_state["sales_write_in_progress"]=True
        old=d["old"];v=d["values"];body={k:old.get(k) for k in ux.EVENT_FIELDS}
        body.update(status=v["status"],result=v["result"])
        follow=v["follow"] if v["status"]=="연기" else None
        if follow:
            try:body.update(follow_time_body(v))
            except ValueError as exc:
                st.session_state['sales_write_in_progress']=False
                st.error(str(exc))
                return key
        try:write_event(db,old,body,follow)
        except HwarangAuthError:
            d["conflict"]=True;raise
        ux.saved_event(key,row["id"])
    return key

def event_detail(db,row):
    from modules.activity.center import review
    title_slot,result_slot=st.columns([3,1])
    title_slot.subheader(row["title"])
    if row['owner']==db.uid:
        with result_slot.popover('완료 · 결과 처리',width='stretch',key='result_popover_'+row['id'],on_change='rerun') as result_popover:
            if result_popover.open:quick_result(db,row)
    ux.summary([row["day"],ux.schedule_time(row),TYPES.get(row["kind"],row["kind"]),row["status"]])
    people={r["member"]:r["label"] for r in db.request("POST","rpc/sales_branch_members",body={})} if row.get("companion") else {}
    ux.details([("장소",row.get("place") or "미입력"),("동행자",people.get(row.get("companion"))), ("메모",row.get("note")),("활동 결과",row.get("result")),("지원 요청",row.get("help"))])
    if row["owner"]==db.uid:
        a,c=st.columns(2)
        if a.button("일정 수정",width="stretch"): ux.navigate({"type":"edit","id":row["id"]},True)
        if c.button("일정 복사",width="stretch"): ux.navigate({"type":"copy","id":row["id"]},True)
        delete_control(db,row)
        if st.button("후속 일정 작성"):ux.navigate({"type":"follow","id":row["id"]},True)
        contract_editor(db,date.fromisoformat(row["day"]),row["id"])
    feedback=st.expander("확인 · 피드백",key="event_feedback_"+row["id"],on_change="rerun")
    if feedback.open:
        with feedback:review(db,row,"event")
    result_key='result:'+row['id']
    return result_key if result_key in st.session_state.get('sales_drafts',{}) else None

def event_list(db,events,prefix,*,show_result_actions=True):
    if not events: st.caption("등록된 일정이 없습니다.")
    for row in events:
        with st.container(border=True):
            st.caption(f'{ux.schedule_time(row)} · {TYPES.get(row["kind"],row["kind"])} · {row["status"]}')
            if st.button(row["title"],key=prefix+row["id"],width="stretch"):
                ux.navigate({"type":"event","id":row["id"]},bool(st.session_state.get("sales_route")))
            if row.get("place"):st.caption(row["place"])
            if show_result_actions and row["owner"]==db.uid and row["status"]=="예정":
                if st.button("✓ 완료",key=prefix+"result"+row["id"]):
                    from modules.activity.calendar_service import command
                    command(db,'status',{'id':row['id'],'revision':row['revision'],'status':'완료'})
                    notify();ux.refresh()

def report_key(db,day,period): return f'report:{db.uid}:{period}:{day}'

def report_reference(db,day,period,events,daily):
    if period=="일일":
        st.subheader("오늘의 일정")
        st.caption(f'완료 {sum(e["status"]=="완료" for e in events)} / 전체 {len(events)}건')
        event_list(db,events,"report_ref_")
    else:
        st.subheader("이번 주 활동 합계")
        submitted=[r for r in daily if r.get("submitted")]
        st.caption(f"제출된 {len(submitted)}일 기준 · 일일 기록 저장 후 갱신")
        count_grid(ux.report_totals(submitted,COUNTS))
        st.divider();st.subheader("날짜별 기록 상태")
        index={r["day"]:r for r in daily}
        from modules.activity.center import KST
        today=datetime.now(KST).date()
        for i in range(7):
            target=day+i*DAY;row=index.get(str(target));future=target>today
            a,b=st.columns([1,1.4])
            a.write(target.strftime("%m.%d")+" "+"월화수목금토일"[i])
            label="예정" if future else "제출 완료 · 보기" if row and row["submitted"] else "임시 저장 · 이어쓰기" if row else "미제출 · 작성하기"
            if b.button(label,key="week_day_"+str(target),disabled=future,width="stretch"):
                ux.navigate({"type":"daily","day":str(target)},bool(st.session_state.get("sales_route")))

def count_grid(values):
    from html import escape
    items=[*COUNTS,*[c for c in ("전화","메시지") if values.get(c)]]
    # A row-major CSS grid stays two columns on narrow screens as well.
    st.html('<div class="report-count-grid" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 16px">'+''.join(
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px;border:1px solid #dce3ed;border-radius:10px;background:#f8fafc;min-width:0"><span>'+escape(ux.LABELS.get(c,c))+'</span><strong>'+format(values.get(c,0),',')+'</strong></div>'
        for c in items)+'</div>')

def reports(db,today,period,fixed_day=None):
    from modules.activity.record_editor import render
    return render(db,today,period,fixed_day)

def member_detail(db,uid,day,period):
    from modules.activity.center import bounds, report_detail
    from modules.activity.manager import required_days, styles
    if uid not in db.members: st.error("조회 권한이 없는 구성원입니다.");return
    styles()
    member=db.members[uid]
    today=datetime.now(KST).date()
    route=st.session_state.get("sales_route",{})
    anchor_key="member_anchor_"+uid
    if anchor_key not in st.session_state or route.get("type")=="member" and not route.get("anchor_initialized"):
        st.session_state[anchor_key]=day
        if route.get("type")=="member":route["anchor_initialized"]=True
    peers=[u for u in st.session_state.get('manager_visible_members',[]) if u in db.members]
    if ux.compact() and uid in peers:
        index=peers.index(uid)
        with st.container(horizontal=True):
            previous=st.button('‹ 이전 직원',disabled=index==0,key='member_peer_prev')
            st.caption(f'{index+1} / {len(peers)}명')
            following=st.button('다음 직원 ›',disabled=index==len(peers)-1,key='member_peer_next')
        if previous or following:
            target_uid=peers[index+(-1 if previous else 1)]
            st.session_state['manager_selected']=target_uid
            ux.navigate({'type':'member','uid':target_uid,'day':str(day),'period':period})
    st.subheader(member["label"])
    period=st.segmented_control("보기",["일일","주간"],default=period,key="member_period_"+uid,required=True,label_visibility="collapsed")
    def shift(amount):
        st.session_state[anchor_key]+=DAY*amount
        route.pop("selected_day",None)
    def current():
        st.session_state[anchor_key]=today
        route.pop("selected_day",None)
    with st.container(key="member_navigation",horizontal=True,vertical_alignment="bottom"):
        st.button("‹",help="이전 주" if period=="주간" else "이전 날",key="member_previous",on_click=shift,args=(-7 if period=="주간" else -1,))
        day=st.date_input("조회 기준일",key=anchor_key,label_visibility="collapsed")
        st.button("›",help="다음 주" if period=="주간" else "다음 날",key="member_next",on_click=shift,args=(7 if period=="주간" else 1,))
        st.button("이번 주" if period=="주간" else "오늘",key="member_current",on_click=current)
    if route.get("type")=="member":route.update(period=period,day=str(day))
    start,end=bounds(day,"주간" if period=="주간" else "날짜별")
    events=db.period("sales_events",start,end,owner="eq."+uid,order="day.asc,start_time.asc.nullsfirst")
    records=db.period("sales_reports",start,end,owner="eq."+uid)
    submitted=[r for r in records if r["period"]=="일일" and r["submitted"]]
    due={str(d) for d in required_days(start,end,today)}
    done=len({r["day"] for r in submitted}&due)
    ux.summary([f'일정 {len(events)}건 · 완료 {sum(e["status"]=="완료" for e in events)}건',f"일일 기록 {done}/{len(due)}일 제출" if due else "기록 제출 예정"])
    if period=="주간":st.caption(f"{start:%m/%d} – {end:%m/%d} · 제출 집계: 오늘까지 평일")
    support=[(e["day"],e["help"],e["id"]) for e in events if e.get("help") and e["status"] not in ("취소","연기")]
    support += [(r["day"],r["data"]["help"],None) for r in records if r["submitted"] and r["data"].get("help")]
    if support:
        with st.expander(f"지원 요청 {len(support)}건"):
            for i,(request_day,message,event_id) in enumerate(support):
                st.write(f"**{request_day}** · {message}")
                if event_id and st.button("일정 확인",key=f"member_support_{uid}_{i}"):ux.navigate({"type":"event","id":event_id})
    def one(target):
        mobile=ux.compact()
        tab=None
        a,b=st.columns([1.1,1]) if not mobile else (st.container(),st.container())
        if tab is None or tab=="일정":
            with a:
                st.markdown("**일정**")
                event_list(db,[e for e in events if e["day"]==str(target)],"member_"+str(target),show_result_actions=False)
        if tab is None or tab=="활동 기록":
            with b:
                st.markdown("**일일 활동 기록**")
                row=next((r for r in records if r["day"]==str(target) and r["period"]=="일일"),None)
                if row and (row["submitted"] or uid==db.uid):
                    count_grid(row["data"].get("counts",{}))
                    ux.details([("진행사항",row["data"].get("note")),("지원 요청",row["data"].get("help"))])
                    if row["submitted"]:report_detail(db,row,show_content=False)
                    else:st.caption("임시 저장된 기록입니다.")
                else:st.caption("예정" if target>today else "제출된 기록이 없습니다.")
                if uid==db.uid and target<=today and not (row and row["submitted"]):
                    if st.button("일일 기록 작성",key="member_write_daily"):ux.navigate({"type":"daily","day":str(target)})
    if period=="일일":one(day)
    else:
        weekend=st.toggle("주말 포함",value=False,key="member_weekends_"+uid,help="주말 표시를 바꿔도 주간 합계는 유지됩니다.")
        days=[start+i*DAY for i in range(7 if weekend else 5)]
        selection_key="member_week_day_"+uid+str(start)
        remembered=route.get("selected_day")
        fallback=today if today in days else day if day in days else days[0]
        if st.session_state.get(selection_key) not in days:
            st.session_state[selection_key]=next((d for d in days if str(d)==remembered),fallback)
        with st.container(key="member_date_strip"):
            target=st.segmented_control("날짜 선택",days,key=selection_key,required=True,label_visibility="collapsed",
                format_func=lambda d:f'{"월화수목금토일"[d.weekday()]} {d:%m/%d}  \n{sum(e["day"]==str(d) for e in events)}건 · '+
                    ("제출" if any(r["day"]==str(d) for r in submitted) else "임시 저장" if any(r["day"]==str(d) and r["period"]=="일일" for r in records) else "예정" if d>today else "미제출"),width="stretch")
        if route.get("type")=="member":route["selected_day"]=str(target)
        row=next((r for r in records if r["period"]=="일일" and r["day"]==str(target)),None)
        state="제출 완료" if row and row["submitted"] else "임시 저장" if row else "예정" if target>today else "미제출"
        st.caption(f'{target:%m월 %d일} · {state}')
        one(target)
        with st.expander("일일 기록 합계",key="member_week_totals_"+uid,on_change="rerun"):
            count_grid(ux.report_totals(submitted,COUNTS))
        with st.expander("주간 제출 기록"):
            weekly=next((r for r in records if r["period"]=="주간" and r["day"]==str(start) and r["submitted"]),None)
            if weekly:report_detail(db,weekly)
            else:st.caption("제출된 주간 기록이 없습니다.")
    perf=st.expander("개인 청약·계약 실적",key="member_perf_open",on_change="rerun")
    if perf.open:
        with perf:performance(db,day,{uid:member},bounds,selected_member=uid,key="member_perf_"+uid)
    conv=st.expander("개인 상담 전환",key="member_conv_open",on_change="rerun")
    if conv.open:
        with conv:conversions(db,start,end,{uid:member})

def overview(db,today):
    from modules.activity.manager import render
    return render(db,today)


def admin_settings(db,start,end):
    with st.expander("담당 구성원 설정 안내"):
        st.caption("관리자 센터 → 계정 기본정보에서 담당 부지점장·담당 팀장을 선택하세요. 동일 직할·지점 내에서 선택하며 미지정도 가능합니다.")

def calendar_scope(db):
    options=["내 일정","지점 일정"]+(["직원 선택"] if db.me["managed"] else [])
    current=st.session_state.get("sales_calendar_member")
    default="직원 선택" if current in db.members and db.me["managed"] else "지점 일정" if st.session_state.get("sales_calendar_team") else "내 일정"
    choice=st.radio("조회 대상",options,index=options.index(default),key="calendar_scope_choice",horizontal=True)
    member=None
    if choice=="직원 선택":
        ids=list(db.members)
        member=st.selectbox("직원 이름 검색 · 선택",ids,index=ids.index(current) if current in ids else 0,format_func=lambda u:db.members[u]["label"],key="calendar_scope_member")
    if st.button("적용",type="primary",key="calendar_scope_apply"):
        st.session_state["sales_calendar_team"]=choice=="지점 일정"
        st.session_state["sales_calendar_member"]=member
        ux.back(preserve=False)



@st.dialog("영업활동",width="large",dismissible=False)
def dialog(db):
    from modules.activity import read_state
    read_state.remember(db)
    ux.dialog_styles()
    st.html('<span class="sales-dialog-marker"></span>')
    kind=st.session_state.get("sales_route",{}).get("type")
    title={"new":"일정 등록","edit":"일정 수정","event":"일정 상세","copy":"일정 복사","follow":"다음 활동 추가","result":"완료 · 결과 처리","member":"직원 활동 기록","daily":"일일 기록","trash":"삭제한 일정","scope":"조회 대상"}.get(kind,"영업활동")
    with st.container(key="sales_dialog_header",horizontal=True,vertical_alignment="center"):
        st.markdown("**"+title+"**")
        close_top=st.button("✕",help="팝업 닫기",key="sales_close_top",type="tertiary")
    with st.container(key="sales_dialog_body"):
        close_feedback=st.container()
        ux.feedback()
        if message:=st.session_state.pop("sales_dialog_error",None):st.error(message)
        route_key=st.session_state.get("sales_route",{})
        read_state.refresh(db,("dialog",route_key.get("type"),route_key.get("id"),route_key.get("day"),route_key.get("uid")))
        route=st.session_state.get("sales_route",{})
        key=None
        try:
            kind=route.get("type")
            if kind=="scope":calendar_scope(db)
            elif kind=="new":key=event_editor(db,date.fromisoformat(route["day"]))
            elif kind=="member":member_detail(db,route["uid"],date.fromisoformat(route["day"]),route["period"])
            elif kind=="trash":trash(db)
            elif kind=="daily":key=reports(db,date.fromisoformat(route["day"]),"일일",date.fromisoformat(route["day"]))
            else:
                editing=kind in ("edit","copy","follow","result")
                cached=route.get("editing_snapshot") if editing else None
                rows=[cached] if cached else db.request("GET","sales_events",{"id":"eq."+route.get("id",""),"limit":"1"})
                if rows and editing:route["editing_snapshot"]=deepcopy(rows[0])
                if not rows:st.info("일정을 조회할 수 없습니다.")
                else:
                    row=rows[0]
                    if kind=="event":key=event_detail(db,row)
                    elif row["owner"]!=db.uid:st.error("본인의 일정만 변경할 수 있습니다.")
                    elif kind=="result":key=quick_result(db,row)
                    elif kind=="edit":key=event_editor(db,date.fromisoformat(row["day"]),event=row)
                    elif kind=="copy":key=event_editor(db,date.fromisoformat(row["day"]),copy={**ux.copy_event(row),"id":row["id"]})
                    elif kind=="follow":key=event_editor(db,date.fromisoformat(row["day"]),parent=row)
        except HwarangAuthError as exc:
            st.session_state["sales_dialog_error"]="요청을 완료하지 못했습니다. 입력 내용은 유지됩니다. "+str(exc)
            # Only retry rendering after a failed write, never retry a failed read.
            if st.session_state.pop("sales_write_in_progress",False):ux.refresh()
            st.error(st.session_state.pop("sales_dialog_error"))
            key=next((k for k in st.session_state.get("sales_drafts",{}) if ux.dirty(k)),None)
    with st.container(key="sales_dialog_footer"):
        ux.close_control(key,requested=close_top,top_container=close_feedback)


def delete_control(db,row):
    if row['owner']!=db.uid:return
    ux.delete_styles()
    key='delete_'+row['id']
    if st.button('일정 삭제',key=key+'_open',type='secondary'):
        st.session_state[key+'_visible']=not st.session_state.get(key+'_visible',False)
    if st.session_state.get(key+'_visible'):
        st.write(row['day']+' · '+row['title'])
        future=False
        if row.get('series_id'):
            future=st.radio('삭제 범위',['이번 일정만','이후 반복 일정까지'],key=key+'_scope')=='이후 반복 일정까지'
        st.caption('일정은 즉시 삭제되며 복구할 수 없습니다. 연결된 계약·후속 활동은 보존됩니다.')
        if st.button('일정 삭제 확인',key=key+'_submit'):
            db.request('POST','rpc/sales_delete_event',body={'p_id':row['id'],'p_revision':row['revision'],'p_future':future})
            st.session_state.pop('sales_route',None)
            st.session_state['sales_route_stack']=[]
            for k in list(st.session_state.get('sales_drafts',{})):
                if k in ('event:'+db.uid+':'+row['id'],'result:'+row['id']):ux.clear_draft(k)
            st.session_state['sales_dialog_notice']='삭제했습니다.'
            st.session_state['sales_calendar_refresh']=str(uuid4())
            ux.refresh()


def trash(db):
    st.info('삭제한 일정 보관·복구 기능은 종료되었습니다.')
