from modules.activity.contracts import contract_editor, performance, conversions
import re
from calendar import monthrange
from pathlib import Path
import streamlit.components.v1 as components
from datetime import date, datetime, time, timedelta
from uuid import uuid4, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo

import streamlit as st
from modules.shared.hwarang_auth import HwarangAuthService, HwarangAuthError, SupabaseConfig

KST=ZoneInfo("Asia/Seoul")
SALES_TYPES={"TA":"고객 연락","AP":"초회 상담","PC":"프레젠테이션 / 클로징","CS":"기존 고객 관리"}
KINDS=["미분류",*SALES_TYPES,"청약","교육","회의","휴무","기타"]
REPORT_KIND={"AP":"상담","PC":"제안"}
COUNTS=["TA","CS","전화","메시지","약속 확보","상담","제안","청약"]
DAY=timedelta(days=1)

class Records:
    def __init__(self):
        self.auth=HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))
        identity=st.session_state["hwarang_auth"]
        self.token=identity["access_token"]
        self.uid=identity["profile"]["id"]
        rows=self.request("POST","rpc/sales_members",body={})
        self.members={row["member"]:row for row in rows}
        if self.uid not in self.members:
            raise HwarangAuthError("영업활동 관리 이용 권한을 확인해 주세요.")
        self.me=self.members[self.uid]

    def request(self,method,table,params=None,body=None,prefer=None):
        return self.auth._request(method,"/rest/v1/"+table,access_token=self.token,params=params,json=body,prefer=prefer)

    def period(self,table,start,end,**params):
        return self.request("GET",table,{"and":f"(day.gte.{start},day.lte.{end})","order":"day.asc",**params})

    def save(self,table,body,old=None):
        if old:
            changed=self.request("PATCH",table,{"id":"eq."+old["id"],"revision":"eq."+str(old["revision"])},body,"return=representation")
            if not changed:raise HwarangAuthError("다른 화면에서 먼저 수정했습니다. 최신 기록을 확인한 뒤 다시 저장해 주세요.")
        else:
            self.request("POST",table,body=body,prefer="return=minimal")

def saved():
    st.session_state["sales_notice"]="저장했습니다."
    st.rerun()

def bounds(day,view):
    if view=="주간":
        start=day-DAY*day.weekday()
        return start,start+6*DAY
    if view=="월간":return day.replace(day=1),day.replace(day=monthrange(day.year,day.month)[1])
    return day,day

def event_editor(db,day,event=None,parent=None):
    old=event or {}
    key="sales_edit_"+(old.get("id") or "new_"+str(day))+"_"+str(old.get("revision",0))
    existing=old.get("kind",{"TA":"AP","AP":"PC"}.get(parent["kind"],"미분류") if parent else "미분류")
    options=KINDS if existing in KINDS else [existing,*KINDS]
    def infer_kind():
        if not event and not parent and not st.session_state.get(key+"_manual"):
            matches=set(re.findall(r"(?<![A-Za-z0-9])(AP|PC|TA|CS)(?![A-Za-z0-9])",st.session_state[key+"_title"].upper()))
            st.session_state[key+"_kind"]=matches.pop() if len(matches)==1 else "미분류"
    def select_kind():
        st.session_state[key+"_manual"]=True
        if st.session_state[key+"_kind"]=="휴무":
            st.session_state[key+"_all"]=True
            if not st.session_state.get(key+"_title","").strip():
                st.session_state[key+"_title"]="휴무"
    with st.container():
        when=st.date_input("날짜",date.fromisoformat(old.get("day",str(day))),key=key+"_day")
        title=st.text_input("고객 또는 일정명",old.get("title",parent["title"] if parent else ""),key=key+"_title",on_change=infer_kind,max_chars=200,placeholder="예: 소개 고객 첫 상담")
        kind=st.selectbox("활동 종류",options,index=options.index(existing),key=key+"_kind",on_change=select_kind,
                          format_func=lambda k:f"{k} · {SALES_TYPES[k]}" if k in SALES_TYPES else k)
        all_day=st.checkbox("종일 일정",value=bool(event and not old.get("start_time") and not old.get("time_pending")),key=key+"_all")
        start=None
        if not all_day:
            start=st.time_input("시작 시간",value=st.session_state.get(key+"_last_start") or (time.fromisoformat(old["start_time"]) if old.get("start_time") else None),key=key+"_start")
            st.session_state[key+"_last_start"]=start

        with st.expander("선택 항목 · 종료 시간, 장소, 메모 등"):
            end=None
            if not all_day:
                end=st.time_input("종료 시간",value=st.session_state.get(key+"_last_end",time.fromisoformat(old["end_time"]) if old.get("end_time") else None),key=key+"_end")
                st.session_state[key+"_last_end"]=end
            place=st.text_input("장소",old.get("place",""))
            note=st.text_area("메모",old.get("note",""))
            people={r["member"]:r["label"] for r in db.request("POST","rpc/sales_branch_members",body={}) if r["member"]!=db.uid}
            choices=list(dict.fromkeys([None,*people,*([old["companion"]] if old.get("companion") else [])]))
            companion=st.selectbox("동행자",choices,index=choices.index(old.get("companion")),format_func=lambda u:people.get(u,"기존 동행자") if u else "선택 안 함")
            help_text=st.text_input("지원 요청",old.get("help",""))
            repeat=1 if event else st.number_input("매주 반복 횟수",1,52,1)
            common=st.checkbox("지점 공통 일정",old.get("common",False)) if db.me["managed"] else False
        states=["예정","완료","연기","취소"]
        status=st.selectbox("처리 상태",states,index=states.index(old.get("status","예정"))) if event else "예정"
        result=st.text_input("활동 결과",old.get("result","")) if event else ""
        follow=st.date_input("후속 일정 날짜 · 선택",value=None) if event else None
        proceed=st.button("일정 저장",type="primary",key=key+"_save")
    if proceed:
        if not title.strip() or end and (not start or end<=start):
            st.warning("일정명과 시작·종료 시간을 확인해 주세요.");return
        body=dict(companion=companion,time_pending=not all_day and start is None,day=str(when),start_time=str(start) if start else None,end_time=str(end) if end else None,
                  title=title.strip(),kind=kind,place=place,note=note,help=help_text,common=common,status=status,result=result,unit=db.me["unit"])
        if start and status=="예정":
            last=when+7*(repeat-1)*DAY
            candidates=db.period("sales_events",when,last,owner="eq."+db.uid,status="eq.예정")
            dates={str(when+7*i*DAY) for i in range(repeat)}
            overlaps=[r for r in candidates if r["id"]!=old.get("id") and r["day"] in dates and r["start_time"] and
                      (r["start_time"]==str(start) or r["start_time"]<str(end or start) and (r["end_time"] or r["start_time"])>str(start))]
            signature=(str(when),str(start),str(end),repeat,tuple(r["id"] for r in overlaps))
            if overlaps and st.session_state.get(key+"_overlap")!=signature:
                st.session_state[key+"_overlap"]=signature
                st.warning("기존 일정과 시간이 겹칩니다. 그대로 등록하려면 일정 저장을 한 번 더 눌러 주세요.")
                return
        if event:
            ok=db.request("POST","rpc/sales_edit_event",body={"p_id":event["id"],"p_revision":event["revision"],
                       "p_data":body,"p_follow":str(follow) if follow else None,
                       "p_follow_id":str(uuid5(NAMESPACE_URL,event["id"]+str(follow))) if follow else None})
            if not ok:raise HwarangAuthError("다른 화면의 변경 사항이 있습니다. 일정을 다시 열어 주세요.")
        else:
            # One atomic insert for the series; retry the same IDs after a lost response.
            seed=st.session_state.setdefault(key+"_seed",str(uuid4()))
            rows=[{**body,"previous_event":parent["id"] if parent else None,"day":str(when+i*7*DAY),"id":str(uuid5(NAMESPACE_URL,seed+str(i)))} for i in range(repeat)]
            db.request("POST","sales_events",body=rows,prefer="resolution=ignore-duplicates")
            st.session_state.pop(key+"_seed")
        saved()

def review(db,row,target):
    reviews=db.request("GET","sales_reviews",{target:"eq."+row["id"],"order":"created_at.desc"})
    for item in reviews:
        st.caption(f'{item["created_at"][:10]} · {item["message"]}'+(" · 이전 버전" if item["revision"]!=row["revision"] else ""))
    if db.me["managed"] and db.members.get(row["owner"],{}).get("managed"):
        label="확인 완료" if target=="report" else "일정 확인"
        with st.form("review_"+row["id"]):
            message=st.text_input("피드백 또는 변경 요청")
            if st.form_submit_button(label+" · 의견 저장"):
                text=message.strip() or label
                db.request("POST","sales_reviews",body={"id":str(uuid5(NAMESPACE_URL,row["id"]+db.uid+str(row["revision"])+text)),target:row["id"],"revision":row["revision"],"message":text},prefer="resolution=ignore-duplicates")
                saved()

calendar_view=components.declare_component("sales_calendar_view",path=str(Path(__file__).with_name("calendar_view")))

@st.dialog("일정 등록",width="large")
def create_dialog(db,day):
    event_editor(db,day)

@st.dialog("일정 상세",width="large")
def detail_dialog(db,row):
    st.subheader(row["title"])
    st.caption(f'{row["day"]} · {(row["start_time"] or "종일")[:5]} · {row["kind"]} · {row["status"]}')
    for field in ("place","note","result","help"):
        if row[field]:st.text(row[field])
    if row["owner"]==db.uid:
        linked=row["kind"] in ("TA","AP") and st.toggle("다음 활동 연결")
        if linked:
            event_editor(db,date.fromisoformat(row["day"]),parent=row)
        else:
            with st.expander("일정 수정 · 완료"):event_editor(db,date.fromisoformat(row["day"]),row)
        with st.expander("후속 할 일 추가"):
            with st.form("follow_task_"+row["id"]):
                task_name=st.text_input("할 일",placeholder="예: 상담 후 재연락",max_chars=200)
                due=st.date_input("할 일 기한",max(date.fromisoformat(row["day"]),datetime.now(KST).date()))
                if st.form_submit_button("할 일 추가") and task_name.strip():
                    seed="task_seed_"+row["id"]
                    db.request("POST","sales_followups",body={"id":st.session_state.setdefault(seed,str(uuid4())),"source":row["id"],"due":str(due),"title":task_name.strip()},prefer="resolution=ignore-duplicates")
                    st.session_state.pop(seed)
                    saved()
        contract_editor(db,date.fromisoformat(row["day"]),row["id"])
    review(db,row,"event")

def calendar(db,today):
    # The component value is available at the start of the widget rerun.
    # Resolve navigation before querying the period, avoiding a second full run.
    nav=st.session_state.get("sales_interactive_calendar")
    if isinstance(nav,dict) and nav.get("action") in ("date","mode") and nav.get("nonce")!=st.session_state.get("sales_calendar_action"):
        st.session_state["sales_calendar_action"]=nav.get("nonce")
        try:
            target=date.fromisoformat(nav.get("value") if nav["action"]=="date" else nav.get("anchor"))
        except (TypeError,ValueError):
            target=None
        if target:st.session_state["sales_anchor"]=target
        if nav["action"]=="mode" and nav.get("value") in ("날짜별","주간","월간"):
            st.session_state["sales_view"]=nav["value"]
    notices=db.request("GET","sales_notices",{"seen":"eq.false","order":"created_at.desc","limit":"20","select":"id,message,sales_events(day,kind)"})
    if notices:
        with st.expander(f"일정 알림 {len(notices)}건",expanded=True):
            for notice in notices:
                event=notice.get("sales_events") or {}
                st.write(f'{event.get("day","")} · {event.get("kind","")} · {notice["message"]}')
            if st.button("표시된 알림 확인"):
                ids=",".join(n["id"] for n in notices)
                db.request("PATCH","sales_notices",{"id":"in.("+ids+")"},{"seen":True})
                st.rerun()
    position=st.session_state["hwarang_auth"]["profile"].get("position_code")
    team=st.toggle("지점 일정",value=position=="branch_manager")
    branch={r["member"]:r for r in db.request("POST","rpc/sales_branch_members",body={})}
    mobile=st.context.headers.get("User-Agent","").lower()
    compact=any(word in mobile for word in ("android","iphone","mobile"))
    mode=st.session_state.get("sales_view","월간")
    day=st.session_state.get("sales_anchor",today)
    start,end=bounds(day,mode)
    fetch_start,fetch_end=bounds(day,"주간") if mode=="날짜별" else (start,end)
    if mode=="날짜별":
        fetch_start-=7*DAY
        fetch_end+=7*DAY
    events=db.period("sales_events",fetch_start,fetch_end,order="day.asc,start_time.asc.nullsfirst")
    details={r["id"]:r for r in events}
    def calendar_rows(a,b):
        return db.request("POST","rpc/sales_calendar_days",body={"first_day":str(a),"last_day":str(b)})
    summary=calendar_rows(fetch_start,fetch_end)
    events=[details.get(r["id"],r) for r in summary if team or r["owner"]==db.uid or r["companion"]==db.uid or r["common"]]
    events.sort(key=lambda r:(r["day"],r["start_time"] or ""))
    todays=summary if fetch_start<=today<=fetch_end else calendar_rows(today,today)
    todays=[r for r in todays if r["day"]==str(today) and not r["common"]]
    confirmations={r["owner"] for r in db.request("GET","sales_empty_days",{"day":"eq."+str(today),"select":"owner"})}
    def day_state(uid):
        personal=[r for r in todays if uid in (r["owner"],r["companion"])]
        active=[r for r in personal if r["status"] not in ("취소","연기")]
        if any(r["kind"]!="휴무" or r["start_time"] for r in active):return "일정 있음"
        if active:return "휴무"
        if uid in confirmations:return "일정 없음"
        if personal and all(r["status"]=="취소" for r in personal):return "모두 취소"
        return "미등록"
    if db.me["managed"]:
        groups={}
        for uid in branch.keys() & db.members.keys():
            groups.setdefault(day_state(uid),[]).append(branch[uid]["label"])
        with st.expander(("오늘의 팀" if position=="team_leader" else "오늘의 지점")+" · 미등록 "+str(len(groups.get("미등록",[])))+"명 · 일정 없음 "+str(len(groups.get("일정 없음",[])))+"명"):
            for state,names in groups.items():st.write(state+" "+str(len(names))+"명 · "+", ".join(sorted(names)))
    if day_state(db.uid) in ("미등록","일정 없음","모두 취소"):
        checked=db.uid in confirmations
        if st.button("오늘 일정 없음 · 되돌리기" if checked else "오늘 일정 없음"):
            if checked:db.request("DELETE","sales_empty_days",{"owner":"eq."+db.uid,"day":"eq."+str(today)})
            else:db.request("POST","sales_empty_days",body={"day":str(today)},prefer="resolution=ignore-duplicates")
            st.rerun()
    if mode=="주간" and team:
        members=[]
        for uid,person in branch.items():
            line={"구성원":person["label"]}
            for i,label in enumerate("월화수목금토일"):
                target=str(start+i*DAY)
                line[label]=" · ".join((r["start_time"] or "종일")[:5]+" "+r["kind"] for r in events if r["owner"]==uid and r["day"]==target)
            members.append(line)
        st.dataframe(members,hide_index=True,width="stretch")
    if start<=today<=end:
        now=datetime.now(KST)
        soon=[]
        for item in events:
            if item["day"]==str(today) and item["status"]=="예정" and item["start_time"]:
                at=datetime.combine(today,time.fromisoformat(item["start_time"]),KST)
                if 0<=(at-now).total_seconds()<=1800:
                    soon.append(item["start_time"][:5]+" "+item["kind"])
        if soon:st.info("30분 이내 시작 · "+" / ".join(soon))
    cards=[]
    for row in events:
        owner=branch.get(row["owner"],{}).get("label","지점 공통")
        stamp=(row["start_time"] or ("시간 미정" if row.get("time_pending") else "종일"))[:5]
        status=row["status"]
        if status=="예정" and (row["day"]<str(today) or row["day"]==str(today) and row["start_time"] and row["start_time"]<datetime.now(KST).strftime("%H:%M:%S")):
            status="결과 미입력"
        label=f'{stamp} · {row["kind"]} · {owner} · {status}'
        if row.get("companion"):label+=" · 동행 "+branch.get(row["companion"],{}).get("label","")
        if row.get("help"):label+=" · 지원 요청"
        cards.append(dict(id=row["id"],day=row["day"],kind=row["kind"],member=row["owner"],allDay=not row["start_time"],short=(row.get('title') or row['kind'])+(f' · {owner}' if team else ''),label=label,done=status=="완료"))
    action=calendar_view(mobileSession=dict(url=db.auth.config.url,key=db.auth.config.publishable_key,token=db.token,uid=db.uid,unit=db.me["unit"],branch=position=="branch_manager"),mode=mode,day=str(day),today=str(today),events=cards,roster={uid:p["label"] for uid,p in branch.items()} if team else {},rangeStart=str(fetch_start),rangeEnd=str(fetch_end),key="sales_interactive_calendar",default=None)
    if isinstance(action,dict) and action.get("nonce")!=st.session_state.get("sales_calendar_action"):
        st.session_state["sales_calendar_action"]=action.get("nonce")
        command,value=action.get("action"),action.get("value")
        if command=="mode" and value in ("날짜별","주간","월간"):
            st.session_state["sales_view"]=value
            st.rerun()
        if command in ("new","date"):
            try:target=date.fromisoformat(value)
            except (TypeError,ValueError):return
            if command=="new":create_dialog(db,target)
            else:
                st.session_state["sales_anchor"]=target
                st.rerun()
        if command in ("event","new") and action.get("anchor"):
            try:st.session_state["sales_anchor"]=date.fromisoformat(action["anchor"])
            except (TypeError,ValueError):pass
        if command=="event":
            found=next((r for r in events if r["id"]==value),None)
            if found and found["id"] in details:detail_dialog(db,found)
            elif found:st.info(next(c["label"] for c in cards if c["id"]==value))
    st.caption("모바일 앱 열기로 캘린더에 접속한 뒤 홈 화면에 추가할 수 있습니다.")
    with st.expander("내 후속 할 일"):
        tasks=db.request("GET","sales_followups",{"owner":"eq."+db.uid,"scheduled":"is.null","order":"due.asc"})
        if not tasks:st.caption("예정된 후속 할 일이 없습니다.")
        for task in tasks:
            st.write(task["due"],task["title"])
            with st.form("schedule_task_"+task["id"]):
                target=st.date_input("일정 날짜",max(today,date.fromisoformat(task["due"])))
                kind=st.selectbox("활동 종류",KINDS)
                if st.form_submit_button("내 일정으로 전환"):
                    db.request("POST","rpc/schedule_sales_followup",body={"task":task["id"],"schedule_day":str(target),"activity":kind})
                    saved()


def reports(db,today,period):
    st.caption("완료 일정과 접수한 청약을 집계합니다. 캘린더 밖에서 진행한 활동만 더해 주세요." if period=="일일" else "제출된 일일 기록을 바탕으로 이번 주 성과와 다음 주 계획을 정리하세요.")
    selected=st.date_input("기록 날짜",today,max_value=today,key="sales_day_"+period)
    day=selected if period=="일일" else bounds(selected,"주간")[0]
    if period=="일일":contract_editor(db,day)
    rows=db.period("sales_reports",day,day,owner="eq."+db.uid,period="eq."+period)
    old=rows[0] if rows else {}
    data=old.get("data",{})
    key=f'{period}.{day}.{old.get("revision",0)}'
    totals=dict(data.get("counts",{}))
    sources=dict(data.get("sources",{}))
    coverage=data.get("coverage",[])
    if period=="일일":
        st.caption("전화는 발신 시도, 메시지는 당일 고객 수, 약속은 신규 확정, 상담·제안은 진행 횟수, 청약은 접수 건수입니다.")
        if not old.get("submitted") or st.button("최신 일정으로 수정 초안 만들기"):
            events=db.period("sales_events",day,day,owner="eq."+db.uid,status="eq.완료")
            contracts=db.period("sales_contracts",day,day,owner="eq."+db.uid)
            linked={r["event"] for r in contracts}
            current={}
            for row in events:
                metric=REPORT_KIND.get(row["kind"],row["kind"])
                if metric in COUNTS and not (metric=="청약" and row["id"] in linked):
                    current[row["id"]]=metric
            current.update({r["id"]:"청약" for r in contracts})
            previous=st.session_state.get(key+".sources",sources)
            for metric in COUNTS:
                field=key+metric
                base=st.session_state.get(field,totals.get(metric,0))
                st.session_state[field]=max(0,base-list(previous.values()).count(metric)+list(current.values()).count(metric))
            st.session_state[key+".sources"]=current
            st.session_state[key+".contracts"]=contracts
            st.session_state[key+".results"]=[{"결과":e["result"],"지원 요청":e["help"]} for e in events if e["result"] or e["help"]]
        sources=st.session_state.get(key+".sources",sources)
        if st.session_state.get(key+".results",data.get("results")):
            st.write(st.session_state.get(key+".results",data.get("results")))
    elif not old or st.button("제출된 일일 기록으로 다시 집계"):
        daily=db.period("sales_reports",day,day+6*DAY,owner="eq."+db.uid,period="eq.일일",submitted="eq.true")
        totals={c:sum(r["data"]["counts"].get(c,0) for r in daily) for c in COUNTS}
        coverage=[r["day"] for r in daily]
        st.session_state[key+".week"]=(totals,coverage)
    if period=="주간":
        totals,coverage=st.session_state.get(key+".week",(totals,coverage))
        st.caption(f"7일 중 {len(coverage)}일 제출 · "+", ".join(coverage))
        st.table([totals])
    with st.form("report."+key):
        if period=="일일":
            cols=st.columns(3)
            totals={c:cols[i%3].number_input(c,min_value=0,value=int(totals.get(c,0)),key=key+c) for i,c in enumerate(COUNTS)}
        note=st.text_area("주요 성과 · 진행사항",data.get("note",""))
        plan=st.text_area("다음 주 계획",data.get("plan","")) if period=="주간" else ""
        help_text=st.text_input("지원 요청",data.get("help",""))
        draft=st.form_submit_button("임시저장",disabled=bool(old.get("submitted")))
        submit=st.form_submit_button("수정 제출" if old.get("submitted") else "제출",type="primary")
    if submit or draft:
        payload={"counts":totals,"note":note,"plan":plan,"help":help_text,"sources":sources,"coverage":coverage}
        if period=="일일":payload.update(contracts=st.session_state.get(key+".contracts",data.get("contracts",[])),results=st.session_state.get(key+".results",data.get("results",[])))
        body={"period":period,"day":str(day),"submitted":submit,"data":payload}
        if not old:body["id"]=str(uuid5(NAMESPACE_URL,db.uid+period+str(day)))
        db.save("sales_reports",body,old)
        saved()
    if old:
        modified=bool(db.request("GET","sales_report_history",{"report":"eq."+old["id"],"select":"revision","limit":"1"})) if old["submitted"] else False
        state="수정됨" if modified else ("제출됨" if old["submitted"] else "임시저장")
        st.caption(state+" · "+datetime.fromisoformat(old["changed_at"]).astimezone(KST).strftime("%m/%d %H:%M"))
        if old["submitted"]:report_detail(db,old)

def report_detail(db,row):
    with st.expander("제출 내용 · 확인 및 피드백",expanded=True):
        st.table([row["data"]["counts"]])
        for field in ("note","plan","help"):
            if row["data"].get(field):st.text(row["data"][field])
        history=db.request("GET","sales_report_history",{"report":"eq."+row["id"],"order":"revision.desc"})
        for prior in history:
            st.caption("수정 전 · "+prior["changed_at"][:16])
            st.write(prior["data"]["counts"],prior["data"].get("note",""),prior["data"].get("plan",""),prior["data"].get("help",""))
        review(db,row,"report")

def overview(db,today):
    day=st.date_input("조회 기준일",today)
    period=st.segmented_control("보고 구분",["일일","주간"],default="일일") or "일일"
    start,end=bounds(day,"주간" if period=="주간" else "날짜별")
    members=db.members.copy()
    profile=st.session_state["hwarang_auth"]["profile"]
    if profile.get("role")=="super_admin":
        units={r["id"]:r["name"] for r in db.request("GET","organization_units",{"select":"id,name"})}
        choices=list(dict.fromkeys([db.me["unit"],"all",*(r["unit"] for r in members.values())]))
        unit=st.selectbox("조회 범위",choices,format_func=lambda u:"전체 조직" if u=="all" else units.get(u,"소속 미지정"))
        with st.expander("QA · 권한별 미리보기 및 담당 팀원 설정"):
            leaders=db.request("GET","profiles",{"position_code":"eq.team_leader","is_active":"eq.true","select":"id,display_name,organization_unit_id"})
            names={r["id"]:r["display_name"] for r in leaders}
            if names:
                leader=st.selectbox("대상 팀장",list(names),format_func=names.get)
                preview=st.toggle("팀장 권한으로 미리보기")
                if not preview:
                    candidates=[uid for uid,m in members.items() if uid!=leader and m["unit"]==members[leader]["unit"]]
                    if candidates:
                        member=st.selectbox("담당 팀원",candidates,format_func=lambda u:members[u]["label"])
                        if st.button("담당 팀원 연결"):
                            db.request("POST","sales_team_assignments",body={"leader":leader,"member":member},prefer="resolution=merge-duplicates")
                            saved()
                else:
                    st.info("팀장 권한으로 미리보기 중 · 읽기 전용")
                    snap=db.request("POST","rpc/sales_qa_snapshot",body={"subject":leader,"first_day":str(start),"last_day":str(end)})
                    labels={m["member"]:m["label"] for m in snap["members"]}
                    st.write("조회 가능 구성원",list(labels.values()))
                    for e in snap["events"]:st.write(e["day"],labels[e["owner"]],e["kind"],e["title"])
                    for r in snap["reports"]:
                        with st.expander(labels[r["owner"]]+" · "+r["period"]+" 기록 · "+r["day"]):st.write(r["data"])
                    return
        if unit!="all":members={uid:m for uid,m in members.items() if m["unit"]==unit}
    performance(db,day,members,bounds)
    conversions(db,start,end,members)
    submitted=[r for r in db.period("sales_reports",start,start,period="eq."+period,submitted="eq.true") if r["owner"] in members]
    events=db.period("sales_events",start,end)
    index={r["owner"]:r for r in submitted}
    summary=[]
    for uid,member in members.items():
        row=index.get(uid)
        own=[e for e in events if e["owner"]==uid]
        overdue=sum(e["status"]=="예정" and (e["day"]<str(today) or (e["day"]==str(today) and (e["end_time"] or e["start_time"] or "23:59:59")<datetime.now(KST).strftime("%H:%M:%S"))) for e in own)
        summary.append({"결과 미입력":overdue,"취소·연기":sum(e["status"] in ("취소","연기") for e in own),"구성원":member["label"],"보고":"제출" if row else "미제출","일정":len(own),"완료":sum(e["status"]=="완료" for e in own),"지원 요청":sum(bool(e["help"]) for e in own)+int(bool(row and row["data"].get("help"))),**(row["data"]["counts"] if row else {})})
    st.dataframe(summary,hide_index=True,width="stretch")
    if index:
        uid=st.selectbox("제출 기록 보기",list(index),format_func=lambda u:db.members[u]["label"])
        report_detail(db,index[uid])

def run():
    st.title("영업활동 관리")
    if notice:=st.session_state.pop("sales_notice",None):st.success(notice)
    try:
        db=Records()
        choices=["캘린더","일일 기록","주간 기록"]+(["구성원 현황"] if db.me["managed"] else [])
        tabs=st.tabs(choices,key="sales_menu",on_change="rerun")
        today=datetime.now(KST).date()
        for mode,tab in zip(choices,tabs):
            if tab.open:
                with tab:
                    if mode=="캘린더":calendar(db,today)
                    elif mode=="구성원 현황":overview(db,today)
                    else:reports(db,today,mode[:2])
    except HwarangAuthError as exc:
        st.error("요청을 완료하지 못했습니다. 입력 내용을 확인하고 다시 시도해 주세요. "+str(exc))
