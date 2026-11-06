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
COUNTS=["TA","CS","전화","메시지","약속 확보","상담","제안","청약"]
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
    if current and all(current[0].get(k)==v for k,v in body.items()):
        if not follow:return
        linked=db.request("GET","sales_events",{"id":"eq."+follow_id,"limit":"1"})
        if linked and linked[0].get("previous_event")==old["id"]:return
    raise HwarangAuthError("다른 화면의 변경 또는 통신 오류가 있습니다. 작성 내용은 유지됩니다. 최신 기록을 확인한 뒤 다시 시도해 주세요.")

def event_body(values):
    start=values["start"] if values["mode"]=="시간 지정" else None
    end=values["end"] if start else None
    return dict(day=str(values["day"]),start_time=str(start) if start else None,end_time=str(end) if end else None,
                time_pending=values["mode"]=="시간 미정",title=values["title"].strip(),kind=values["kind"],place=values["place"],
                note=values["note"],help=values["help"] if values["support"] else "",common=values["common"],
                companion=values["companion"],status=values["status"],result=values["result"])

def event_errors(v):
    errors={}
    if not v["title"].strip():errors["title"]="고객 또는 일정명을 입력해 주세요."
    if v["mode"]=="시간 지정":
        if not v["start"]:errors["start"]="시작 시간을 입력해 주세요."
        elif v["end"] and v["end"]<=v["start"]:errors["end"]="종료 시간은 시작 시간보다 늦어야 합니다."
    if v["follow"] and v["follow"]<v["day"]:errors["follow"]="후속 일정 날짜를 확인해 주세요."
    return errors


def event_editor(db,day,event=None,parent=None,copy=None):
    old=event or copy or {}
    key=f'event:{db.uid}:{event["id"] if event else "copy:"+copy["id"] if copy else "follow:"+parent["id"] if parent else "new:"+str(day)}'
    initial=dict(day=date.fromisoformat(old.get("day",str(day))),title=old.get("title",parent["title"] if parent else ""),
        kind=old.get("kind",{"TA":"AP","AP":"PC"}.get(parent["kind"],"미분류") if parent else "미분류"),
        mode="시간 미정",start=time.fromisoformat(old["start_time"]) if old.get("start_time") else None,
        end=time.fromisoformat(old["end_time"]) if old.get("end_time") else None,place=old.get("place","") or "",note=old.get("note","") or "",
        help=old.get("help","") if event else "",support=bool(event and old.get("help")),companion=old.get("companion"),
        repeat=False,repeats=1,common=old.get("common",False) if event else False,status=old.get("status","예정") if event else "예정",
        result=old.get("result","") if event else "",follow=None)
    initial["mode"]="시간 지정" if old.get("start_time") else "시간 미정" if not old or old.get("time_pending") else "종일"
    d=ux.draft(key,initial,event)
    ux.conflict_recovery(d,key)
    v=d["values"]
    st.subheader("일정 수정" if event else "일정 복사" if copy else "후속 일정 등록" if parent else "일정 등록")
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
    ux.field(d,"title",st.text_input,"고객 또는 일정명",max_chars=200,placeholder="예: 소개 고객 첫 상담",after_change=infer_kind)
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
            choices=list(dict.fromkeys([None,*people,*([v["companion"]] if v["companion"] else [])]))
            ux.field(d,"companion",st.selectbox,"동행자",options=choices,format_func=lambda u:people.get(u,"기존 동행자") if u else "선택 안 함")
            ux.field(d,"support",st.toggle,"지원 요청")
            if v["support"]: ux.field(d,"help",st.text_input,"지원받을 내용")
            if not event:
                ux.field(d,"repeat",st.toggle,"매주 반복")
                if v["repeat"]: ux.field(d,"repeats",st.number_input,"총 등록 횟수 · 이번 일정 포함",min_value=1,max_value=52)
            if db.me["managed"]: ux.field(d,"common",st.checkbox,"지점 공통 일정")
    if populated:st.caption("추가 정보 · 입력됨")
    if event:
        with st.expander("처리 상태 · 활동 결과",expanded=d["baseline"]["status"]!="예정",key=d["epoch"]+"state",on_change="rerun"):
            ux.field(d,"status",st.selectbox,"처리 상태",options=["예정","완료","연기","취소"])
            ux.field(d,"result",st.text_area,"활동 결과",height=80)
            ux.field(d,"follow",st.date_input,"후속 일정 날짜 · 선택")
            if v["follow"] and v["follow"]<v["day"]:st.error("후속 일정 날짜는 현재 일정 날짜 이후로 선택해 주세요.")
    save_slot=st.empty()
    if save_slot.button("변경 저장" if event else "일정 등록",type="primary",key=key+"save",on_click=lambda:d.update(attempted=True)):
        errors=event_errors(v)
        if errors:
            ux.focus_field(d,next(iter(errors)))
            return key
        body=event_body(v)
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
        ux.saved_event(key,event["id"] if event else rows[0]["id"])
    if event:delete_control(db,event)
    return key

def quick_result(db,row):
    key="result:"+row["id"]
    d=ux.draft(key,{"status":"완료","result":row.get("result", ""),"follow":max(date.fromisoformat(row["day"]),datetime.now(KST).date())+DAY},row)
    ux.conflict_recovery(d,key)
    ux.field(d,"status",st.segmented_control,"처리 결과",options=["완료","연기","취소"],required=True)
    ux.field(d,"result",st.text_area,"활동 결과 · 선택",height=80)
    if d["values"]["status"]=="연기": ux.field(d,"follow",st.date_input,"새 일정 날짜",min_value=date.fromisoformat(row["day"]))
    save_slot=st.empty()
    if save_slot.button("결과 저장",type="primary"):
        save_slot.button("저장 중…",disabled=True,key=key+"busy")
        st.session_state["sales_write_in_progress"]=True
        old=d["old"];v=d["values"];body={k:old.get(k) for k in ux.EVENT_FIELDS}
        body.update(status=v["status"],result=v["result"])
        follow=v["follow"] if v["status"]=="연기" else None
        try:write_event(db,old,body,follow)
        except HwarangAuthError:
            d["conflict"]=True;raise
        ux.saved_event(key,row["id"])
    return key

def event_detail(db,row):
    from modules.activity.center import review
    st.subheader(row["title"])
    ux.summary([row["day"],ux.schedule_time(row),TYPES.get(row["kind"],row["kind"]),row["status"]])
    people={r["member"]:r["label"] for r in db.request("POST","rpc/sales_branch_members",body={})} if row.get("companion") else {}
    ux.details([("장소",row.get("place") or "미입력"),("동행자",people.get(row.get("companion"))), ("메모",row.get("note")),("활동 결과",row.get("result")),("지원 요청",row.get("help"))])
    if row["owner"]==db.uid:
        a,b,c=st.columns(3)
        if a.button("일정 수정",width="stretch"): ux.navigate({"type":"edit","id":row["id"]},True)
        if b.button("완료 · 결과 처리",type="primary",width="stretch"): ux.navigate({"type":"result","id":row["id"]},True)
        if c.button("일정 복사",width="stretch"): ux.navigate({"type":"copy","id":row["id"]},True)
        delete_control(db,row)
        with st.expander("다음 활동 추가"):
            kind=st.radio("추가할 활동",["후속 일정","할 일"],horizontal=True,key="next_"+row["id"])
            if kind=="후속 일정":
                if st.button("후속 일정 작성"): ux.navigate({"type":"follow","id":row["id"]},True)
            else:
                with st.form("follow_task_"+row["id"]):
                    title=st.text_input("할 일",max_chars=200)
                    due=st.date_input("기한",max(date.fromisoformat(row["day"]),datetime.now(KST).date()))
                    if st.form_submit_button("할 일 추가"):
                        if not title.strip():st.error("할 일을 입력해 주세요.")
                        else:
                            seed="task_seed_"+row["id"]
                            db.request("POST","sales_followups",body={"id":st.session_state.setdefault(seed,str(uuid4())),"source":row["id"],"due":str(due),"title":title.strip()},prefer="resolution=ignore-duplicates")
                            st.session_state.pop(seed);notify();ux.refresh()
        contract_editor(db,date.fromisoformat(row["day"]),row["id"])
    feedback=st.expander("확인 · 피드백",key="event_feedback_"+row["id"],on_change="rerun")
    if feedback.open:
        with feedback:review(db,row,"event")

def event_list(db,events,prefix):
    if not events: st.caption("등록된 일정이 없습니다.")
    for row in events:
        with st.container(border=True):
            st.caption(f'{ux.schedule_time(row)} · {TYPES.get(row["kind"],row["kind"])} · {row["status"]}')
            if st.button(row["title"],key=prefix+row["id"],width="stretch"):
                ux.navigate({"type":"event","id":row["id"]},bool(st.session_state.get("sales_route")))
            if row.get("place"):st.caption(row["place"])
            if row["owner"]==db.uid and row["status"]=="예정":
                if st.button("완료 · 연기 · 취소",key=prefix+"result"+row["id"]): ux.navigate({"type":"result","id":row["id"]},bool(st.session_state.get("sales_route")))

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
    columns=st.columns(2)
    for i,c in enumerate(COUNTS): columns[i%2].write(f'{ux.LABELS.get(c,c)} **{values.get(c,0):,}**')

def reports(db,today,period,fixed_day=None):
    from modules.activity.center import bounds, report_detail
    if fixed_day is None:
        selected=st.date_input("기록 날짜" if period=="일일" else "조회 주간",today,max_value=today,key="sales_day_"+period)
        day=selected if period=="일일" else bounds(selected,"주간")[0]
        previous=st.session_state.get("sales_report_active_"+period)
        if previous and previous!=str(day) and ux.dirty(report_key(db,previous,period)):
            st.warning("이전 날짜에 저장하지 않은 내용이 있습니다. 내용을 유지한 채 날짜를 변경할까요?")
            a,b,c=st.columns(3)
            if c.button("내용 버리고 날짜 변경",key="discard_date_"+period):
                ux.clear_draft(report_key(db,previous,period))
                st.session_state["sales_report_active_"+period]=str(day);ux.refresh()
            if a.button("날짜 변경",key="change_date_"+period):
                st.session_state["sales_report_active_"+period]=str(day);ux.refresh()
            def stay(): st.session_state["sales_day_"+period]=date.fromisoformat(previous)
            b.button("계속 작성",key="keep_date_"+period,on_click=stay)
            day=date.fromisoformat(previous)
        else: st.session_state["sales_report_active_"+period]=str(day)
    else: day=fixed_day
    key=report_key(db,day,period)
    if fixed_day is None: st.session_state["sales_active_draft"]=key
    rows=db.period("sales_reports",day,day,owner="eq."+db.uid,period="eq."+period)
    old=rows[0] if rows else {}
    data=old.get("data",{})
    events=db.period("sales_events",day,day,owner="eq."+db.uid,order="day.asc,start_time.asc.nullsfirst") if period=="일일" else []
    daily=db.period("sales_reports",day,day+6*DAY,owner="eq."+db.uid,period="eq.일일") if period=="주간" else []
    counts={c:int(data.get("counts",{}).get(c,0)) for c in COUNTS}
    if period=="주간" and not old: counts=ux.report_totals(daily,COUNTS)
    initial={**counts,"note":data.get("note",""),"plan":data.get("plan",""),"help":data.get("help",""),
             "sources":data.get("sources",{}),"coverage":data.get("coverage",[r["day"] for r in daily if r["submitted"]]),
             "contracts":data.get("contracts",[]),"results":data.get("results",[])}
    d=ux.draft(key,initial,old)
    ux.conflict_recovery(d,key)
    v=d["values"]
    if message:=d.pop("save_error",None):st.error(message)
    # New weekly drafts reflect saved daily records without overwriting legacy weekly snapshots.
    if period=="주간" and not old:
        v.update(ux.report_totals(daily,COUNTS));v["coverage"]=[r["day"] for r in daily if r["submitted"]]
        d["baseline"].update({c:v[c] for c in COUNTS});d["baseline"]["coverage"]=v["coverage"][:]
    st.subheader(str(day)+(f" – {day+6*DAY}" if period=="주간" else " · "+"월화수목금토일"[day.weekday()]))
    ux.feedback()
    ux.summary(["수정 중" if old.get("submitted") and ux.dirty(key) else "제출 완료" if old.get("submitted") else "임시 저장" if old else "작성 중",db.me["label"]])
    mobile=ux.compact()
    if mobile:
        with st.popover("오늘 일정 참고" if period=="일일" else "활동 합계 · 제출 현황",width="stretch"):
            st.html('<span class="sales-reference"></span>')
            report_reference(db,day,period,events,daily)
        left=st.container();right=None
    else: left,right=st.columns([1.55,1],gap="large")
    with left:
        with st.container(border=True):
            st.subheader("오늘의 활동 기록" if period=="일일" else "이번 주 돌아보기")
            if period=="일일":
                st.caption("실제 진행한 활동을 입력하세요. 일정 완료와 실적은 별도로 관리합니다.")
                source_panel=st.expander("완료 일정 · 청약에서 집계 초안 확인",key=key+"source_panel",on_change="rerun")
                if source_panel.open:
                    with source_panel:
                        contracts=db.period("sales_contracts",day,day,owner="eq."+db.uid)
                        linked={r["event"] for r in contracts}
                        completed=[r for r in events if r["status"]=="완료"]
                        current={r["id"]:{"AP":"상담","PC":"제안"}.get(r["kind"],r["kind"]) for r in completed if {"AP":"상담","PC":"제안"}.get(r["kind"],r["kind"]) in COUNTS and not(r["kind"]=="청약" and r["id"] in linked)}
                        current.update({r["id"]:"청약" for r in contracts})
                        proposed=ux.refreshed_counts(v,v["sources"],current,COUNTS)
                        st.dataframe([{"항목":ux.LABELS.get(c,c),"현재 입력":v[c],"반영 후":proposed[c]} for c in COUNTS],hide_index=True,width="stretch")
                        st.caption("반영 후 값을 확인해 주세요. 이미 반영한 원천은 중복 합산하지 않습니다.")
                        if st.button("이 집계 초안 반영",key=key+"import"):
                            ux.set_values(d,{**proposed,"sources":current,"contracts":contracts,"results":[{"결과":e["result"],"지원 요청":e["help"]} for e in completed if e["result"] or e["help"]]})
                for label,metrics in [("연락 활동",COUNTS[:4]),("상담 · 계약 활동",COUNTS[4:])]:
                    st.markdown("**"+label+"**")
                    cols=st.columns(2 if mobile else 4)
                    for i,c in enumerate(metrics): ux.field(d,c,cols[i%len(cols)].number_input,ux.LABELS.get(c,c),min_value=0,step=1)
                st.caption("전화: 발신 시도 · 메시지: 고객 수 · 약속: 신규 확정 · 상담·제안: 진행 횟수 · 청약: 접수 건수")
            else:
                st.caption("일일 기록을 참고해 주요 성과와 다음 주 계획을 정리하세요.")
                if old:
                    with st.expander("저장된 주간 실적 · 기존 기록 유지"):
                        count_grid({c:v[c] for c in COUNTS})
                        st.caption("제출된 일일 기록으로 재집계하면 이 주간 기록의 실적이 변경됩니다.")
                        if st.button("최신 일일 합계 확인",key=key+"check_week"): d["week_check"]=True
                        if d.get("week_check"):
                            proposed=ux.report_totals(daily,COUNTS)
                            count_grid(proposed)
                            if st.button("확인한 합계 반영",key=key+"apply_week"):
                                v.update(proposed);v["coverage"]=[r["day"] for r in daily if r["submitted"]];d.pop("week_check",None);ux.refresh()
            ux.field(d,"note",st.text_area,"주요 성과 · 진행사항",height=120,placeholder="주요 활동과 진행 내용을 적어 주세요.")
            if period=="주간":ux.field(d,"plan",st.text_area,"다음 주 계획",height=110,placeholder="다음 주 진행할 활동과 계획을 적어 주세요.")
            with st.expander("지원 요청 · 선택",key=d["epoch"]+"help_panel",on_change="rerun"):
                ux.field(d,"help",st.text_input,"지원받을 내용")
            if v["help"]:st.caption("지원 요청 · 입력됨")
            st.caption("조회 권한이 있는 관리자에게 제출 기록이 공유됩니다.")
            a,b=st.columns(2)
            draft_slot=a.empty()
            save_draft=draft_slot.button("임시 저장",disabled=bool(old.get("submitted")),key=key+"draft",width="stretch")
            if b.button("수정 제출" if old.get("submitted") else "기록 제출",type="primary",key=key+"submit",width="stretch"):
                d["confirm"]=True
            submit=False
            if d.get("confirm"):
                st.info("입력한 내용으로 기록을 제출할까요?")
                a,b=st.columns(2)
                submit_slot=a.empty()
                submit=submit_slot.button("제출 확인",type="primary",key=key+"confirm")
                if b.button("계속 작성",key=key+"cancel_submit"):d.pop("confirm",None);ux.refresh()
            if save_draft or submit:
                # Preserve unknown legacy data keys as well as all known input fields.
                payload=deepcopy((d["old"] or {}).get("data",{}))
                payload.update(counts={c:v[c] for c in COUNTS},**{k:v[k] for k in ("note","plan","help","sources","coverage","contracts","results")})
                body={"period":period,"day":str(day),"submitted":bool(submit),"data":payload}
                if not d["old"]:body["id"]=str(uuid5(NAMESPACE_URL,db.uid+period+str(day)))
                (submit_slot if submit else draft_slot).button("저장 중…",disabled=True,key=key+"busy")
                try:db.save("sales_reports",body,d["old"])
                except HwarangAuthError as exc:
                    d["conflict"]=True;d["save_error"]="저장하지 못했습니다. 입력 내용은 유지됩니다. "+str(exc);ux.refresh()
                ux.clear_draft(key)
                st.session_state["sales_dialog_notice"]="기록을 제출했습니다." if submit else "임시 저장했습니다. 서버에 보관된 기록입니다."
                if fixed_day is not None:ux.back()
                ux.refresh()
        if period=="일일":contract_editor(db,day)
        if old:
            history_panel=st.expander("기존 제출 내용 · 수정 이력 · 피드백",key=key+"history_panel",on_change="rerun")
            if history_panel.open:
                with history_panel:
                    report_detail(db,old)
    if right is not None:
        with right:
            with st.container(border=True):report_reference(db,day,period,events,daily)
    return key

def member_detail(db,uid,day,period):
    from modules.activity.center import bounds, report_detail
    if uid not in db.members: st.error("조회 권한이 없는 구성원입니다.");return
    member=db.members[uid]
    st.subheader(member["label"])
    period=st.segmented_control("보기",["일일","주간"],default=period,key="member_period_"+uid,required=True)
    if st.session_state.get("sales_route",{}).get("type")=="member":
        st.session_state["sales_route"]["period"]=period
    start,end=bounds(day,"주간" if period=="주간" else "날짜별")
    events=db.period("sales_events",start,end,owner="eq."+uid,order="day.asc,start_time.asc.nullsfirst")
    records=db.period("sales_reports",start,end,owner="eq."+uid)
    submitted=[r for r in records if r["period"]=="일일" and r["submitted"]]
    ux.summary([f"{start} – {end}" if period=="주간" else str(day),f"일정 {len(events)}건",f'완료 {sum(e["status"]=="완료" for e in events)}건'])
    def one(target):
        a,b=st.columns([1.1,1]) if not ux.compact() else (st.container(),st.container())
        with a:
            st.markdown("**일정**")
            event_list(db,[e for e in events if e["day"]==str(target)],"member_"+str(target))
        with b:
            st.markdown("**일일 활동 기록**")
            row=next((r for r in records if r["day"]==str(target) and r["period"]=="일일"),None)
            if row:
                count_grid(row["data"].get("counts",{}))
                ux.details([("진행사항",row["data"].get("note")),("지원 요청",row["data"].get("help"))])
                report_detail(db,row,show_content=False)
            else:
                from modules.activity.center import KST
                st.caption("예정" if target>datetime.now(KST).date() else "제출된 기록이 없습니다.")
    if period=="일일":one(day)
    else:
        with st.expander("일일 기록 합계",key="member_week_totals_"+uid,on_change="rerun"):
            count_grid(ux.report_totals(submitted,COUNTS))
        from modules.activity.center import KST
        days=[start+i*DAY for i in range(7)]
        route=st.session_state.get("sales_route",{})
        selection_key="member_week_day_"+uid+str(start)
        remembered=route.get("selected_day")
        fallback=datetime.now(KST).date() if datetime.now(KST).date() in days else day
        if selection_key not in st.session_state:
            st.session_state[selection_key]=next((d for d in days if str(d)==remembered),fallback if fallback in days else start)
        target=st.segmented_control("날짜 선택",days,key=selection_key,required=True,
            format_func=lambda d: f'{"월화수목금토일"[d.weekday()]} {d:%m/%d} · {sum(e["day"]==str(d) for e in events)}건 · '+
                ("제출" if any(r["day"]==str(d) for r in submitted) else "임시 저장" if any(r["day"]==str(d) and r["period"]=="일일" for r in records) else "예정" if d>datetime.now(KST).date() else "미제출"),width="stretch")
        if route.get("type")=="member":route["selected_day"]=str(target)
        own=[e for e in events if e["day"]==str(target)]
        row=next((r for r in submitted if r["day"]==str(target)),None)
        state="제출 완료" if row else "예정" if target>datetime.now(KST).date() else "미제출"
        st.caption(f'{target:%m월 %d일} · 일정 {len(own)}건 · {state}')
        one(target)
        with st.expander("주간 제출 기록"):
            weekly=next((r for r in records if r["period"]=="주간" and r["day"]==str(start)),None)
            if weekly:report_detail(db,weekly)
            else:st.caption("제출된 주간 기록이 없습니다.")
    perf=st.expander("개인 청약·계약 실적",key="member_perf_open",on_change="rerun")
    if perf.open:
        with perf:performance(db,day,{uid:member},bounds,selected_member=uid,key="member_perf_"+uid)
    conv=st.expander("개인 상담 전환",key="member_conv_open",on_change="rerun")
    if conv.open:
        with conv:conversions(db,start,end,{uid:member})

def overview(db,today):
    ux.feedback()
    from modules.activity.center import bounds, KST
    a,b,c=st.columns([1,1,1.3])
    day=a.date_input("조회 기준일",today,key="sales_overview_day")
    period=b.segmented_control("기록 구분",["일일","주간"],default="일일",required=True,key="sales_overview_period")
    start,end=bounds(day,"주간" if period=="주간" else "날짜별")
    members=db.members.copy()
    admin=st.session_state["hwarang_auth"]["profile"].get("role")=="super_admin"
    if admin:
        units={r["id"]:r["name"] for r in db.request("GET","organization_units",{"select":"id,name"})}
        choices=list(dict.fromkeys([db.me["unit"],"all",*(r["unit"] for r in members.values())]))
        unit=c.selectbox("조회 범위",choices,format_func=lambda u:"전체 조직" if u=="all" else units.get(u,"소속 미지정"),key="sales_overview_unit")
        if unit!="all":members={uid:m for uid,m in members.items() if m["unit"]==unit}
    reports=db.period("sales_reports",start,start,period="eq."+period,submitted="eq.true")
    index={r["owner"]:r for r in reports if r["owner"] in members}
    events=[r for r in db.period("sales_events",start,end) if r["owner"] in members]
    now=datetime.now(KST)
    summary=[]
    for uid,m in members.items():
        own=[e for e in events if e["owner"]==uid];row=index.get(uid)
        overdue=sum(e["status"]=="예정" and (e["day"]<str(today) or e["day"]==str(today) and (e.get("end_time") or e.get("start_time") or "23:59:59")<now.strftime("%H:%M:%S")) for e in own)
        summary.append(dict(uid=uid,name=m["label"],submitted=bool(row),missing=overdue,events=len(own),done=sum(e["status"]=="완료" for e in own),help=sum(bool(e.get("help")) for e in own)+int(bool(row and row["data"].get("help"))),cancelled=sum(e["status"] in ("취소","연기") for e in own)))
    left,right=st.columns([2.2,1],gap="large")
    with left:
        with st.container(border=True):
            st.subheader("구성원 현황")
            query=st.text_input("직원 이름 검색",placeholder="이름을 입력하세요",key="sales_member_search").strip().casefold()
            status=st.segmented_control("표시",["전체","미제출","결과 미입력","지원 요청"],default="전체",required=True,key="sales_member_status")
            visible=[r for r in summary if query in r["name"].casefold() and (status=="전체" or status=="미제출" and not r["submitted"] and day<=today or status=="결과 미입력" and r["missing"] or status=="지원 요청" and r["help"])]
            st.caption(f"검색 결과 {len(visible)}명 / 조회 범위 {len(summary)}명")
            if not visible:st.info("조건에 맞는 구성원이 없습니다.")
            for r in visible:
                with st.container(border=True):
                    a,b=st.columns([1.3,2])
                    if a.button(r["name"]+" ›",key="member_open_"+r["uid"],width="stretch"):
                        ux.navigate({"type":"member","uid":r["uid"],"day":str(day),"period":period})
                    b.caption(("제출 완료" if r["submitted"] else "예정" if day>today else "미제출")+f' · 일정 {r["events"]} · 완료 {r["done"]}')
                    flags=[f'결과 미입력 {r["missing"]}' if r["missing"] else "",f'지원 요청 {r["help"]}' if r["help"] else "",f'취소·연기 {r["cancelled"]}' if r["cancelled"] else ""]
                    if any(flags):st.caption(" · ".join(x for x in flags if x))
    with right:
        with st.container(border=True):
            st.subheader("조직 요약")
            st.caption("선택한 조직·기간 전체 기준")
            ux.summary([f"구성원 {len(summary)}명",f"제출 {len(index)}명",f"일정 {len(events)}건",f'완료 {sum(r["done"] for r in summary)}건'])
            with st.expander("청약·계약 실적",expanded=True):performance(db,day,members,bounds,selected_member=False,key="overview_perf",period_range=(start,end))
            conv=st.expander("상담 전환",key="overview_conv_open",on_change="rerun")
            if conv.open:
                with conv:conversions(db,start,end,members)
    if admin:admin_settings(db,start,end)

def admin_settings(db,start,end):
    with st.expander("관리 설정 · 담당 팀원 및 권한 미리보기"):
        members=db.members
        leaders=db.request("GET","profiles",{"position_code":"eq.team_leader","is_active":"eq.true","select":"id,display_name,organization_unit_id"})
        names={r["id"]:r["display_name"] for r in leaders if r["id"] in members}
        if not names:st.caption("설정할 팀장이 없습니다.");return
        leader=st.selectbox("대상 팀장",list(names),format_func=names.get)
        preview=st.toggle("팀장 권한으로 미리보기")
        if not preview:
            candidates=[uid for uid,m in members.items() if uid!=leader and m["unit"]==members[leader]["unit"]]
            if candidates:
                member=st.selectbox("담당 팀원",candidates,format_func=lambda u:members[u]["label"])
                if st.button("담당 팀원 연결"):
                    db.request("POST","sales_team_assignments",body={"leader":leader,"member":member},prefer="resolution=merge-duplicates");notify();ux.refresh()
        else:
            st.info("팀장 권한으로 미리보기 중 · 읽기 전용")
            snap=db.request("POST","rpc/sales_qa_snapshot",body={"subject":leader,"first_day":str(start),"last_day":str(end)})
            labels={m["member"]:m["label"] for m in snap["members"]}
            st.write("조회 가능 구성원",list(labels.values()))
            for e in snap["events"]:st.write(e["day"],labels[e["owner"]],e["kind"],e["title"])
            for r in snap["reports"]:
                with st.expander(labels[r["owner"]]+" · "+r["period"]+" 기록 · "+r["day"]):st.write(r["data"])

@st.dialog("영업활동",width="large",dismissible=False)
def dialog(db):
    st.html('<span class="sales-dialog-marker"></span>')
    with st.container(key="sales_close_corner",horizontal=True,horizontal_alignment="right"):
        close_top=st.button("✕",help="팝업 닫기",key="sales_close_top",type="tertiary")
    close_feedback=st.container()
    ux.feedback()
    if message:=st.session_state.pop("sales_dialog_error",None):st.error(message)
    db._reads.clear() # Dialog fragments must not retain a stale Records read snapshot.
    route=st.session_state.get("sales_route",{})
    key=None
    try:
        kind=route.get("type")
        if kind=="new":key=event_editor(db,date.fromisoformat(route["day"]))
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
                if kind=="event":event_detail(db,row)
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
    ux.close_control(key,requested=close_top,top_container=close_feedback)


def delete_control(db,row):
    if row['owner']!=db.uid:return
    key='delete_'+row['id']
    if st.button('일정 삭제',key=key+'_open',type='secondary'):
        st.session_state[key+'_visible']=not st.session_state.get(key+'_visible',False)
    if st.session_state.get(key+'_visible'):
        st.write(row['day']+' · '+row['title'])
        future=False
        if row.get('series_id'):
            future=st.radio('삭제 범위',['이번 일정만','이후 반복 일정까지'],key=key+'_scope')=='이후 반복 일정까지'
        st.caption('달력과 활동 집계에서 제외됩니다. 계약·후속 활동은 보존되며, 삭제한 일정 메뉴에서 30일 동안 복구할 수 있습니다.')
        if st.button('일정 삭제 확인',key=key+'_submit'):
            db.request('POST','rpc/sales_archive_event',body={'p_id':row['id'],'p_revision':row['revision'],'p_future':future,'p_restore':False})
            st.session_state['sales_route']={'type':'trash'}
            st.session_state['sales_route_stack']=[]
            for k in list(st.session_state.get('sales_drafts',{})):
                if k in ('event:'+db.uid+':'+row['id'],'result:'+row['id']):ux.clear_draft(k)
            st.session_state['sales_dialog_notice']='삭제했습니다. 30일 동안 복구할 수 있습니다.'
            st.session_state['sales_calendar_refresh']=str(uuid4())
            ux.refresh()


def trash(db):
    st.subheader('삭제한 일정')
    st.caption('본인의 일정만 표시됩니다. 삭제 후 30일 동안 개별 복구할 수 있습니다. 연결된 계약·후속 기록은 삭제하지 않습니다.')
    cutoff=(datetime.now(KST)-timedelta(days=30)).isoformat()
    rows=db.request('GET','sales_events',{'owner':'eq.'+db.uid,'deleted_at':'gte.'+cutoff,'order':'deleted_at.desc,day.asc'})
    if not rows:st.info('복구할 일정이 없습니다.')
    for row in rows:
        with st.container(border=True):
            st.write(row['day']+' · '+row['title'])
            if st.button('복구',key='restore_'+row['id']):
                db.request('POST','rpc/sales_archive_event',body={'p_id':row['id'],'p_revision':row['revision'],'p_future':False,'p_restore':True})
                st.session_state['sales_dialog_notice']='일정을 복구했습니다.'
                st.session_state['sales_calendar_refresh']=str(uuid4());ux.refresh()
