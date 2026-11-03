from calendar import monthrange
from collections import Counter
from datetime import date, datetime, time, timedelta
from uuid import uuid4, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo

import streamlit as st
from modules.shared.hwarang_auth import HwarangAuthService, HwarangAuthError, SupabaseConfig

KST=ZoneInfo("Asia/Seoul")
KINDS=["전화","상담","제안","청약","고객관리","교육","회의","휴무","기타"]
COUNTS=["전화","메시지","약속 확보","상담","제안","청약"]
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

def event_editor(db,day,event=None):
    old=event or {}
    key="sales_edit_"+(old.get("id") or "new_"+str(day))+"_"+str(old.get("revision",0))
    with st.form(key):
        title=st.text_input("고객 또는 일정명",old.get("title",""),max_chars=200)
        kind=st.selectbox("활동 종류",KINDS,index=KINDS.index(old.get("kind","상담")))
        when=st.date_input("날짜",date.fromisoformat(old.get("day",str(day))))
        a,b=st.columns(2)
        start=a.time_input("시작 · 종일이면 비우기",value=time.fromisoformat(old["start_time"]) if old.get("start_time") else (None if event else time(9)))
        end=b.time_input("종료 · 선택",value=time.fromisoformat(old["end_time"]) if old.get("end_time") else None)
        with st.expander("장소 · 반복 · 지원 요청"):
            place=st.text_input("장소",old.get("place",""))
            note=st.text_area("메모",old.get("note",""))
            help_text=st.text_input("동행·검토 요청",old.get("help",""))
            repeat=1 if event else st.number_input("매주 반복 횟수",1,52,1)
            common=st.checkbox("지점 공통 일정",old.get("common",False)) if db.me["managed"] else False
        states=["예정","완료","연기","취소"]
        status=st.selectbox("처리 상태",states,index=states.index(old.get("status","예정"))) if event else "예정"
        result=st.text_input("활동 결과",old.get("result","")) if event else ""
        follow=st.date_input("후속 일정 날짜 · 선택",value=None) if event else None
        proceed=st.form_submit_button("일정 저장",type="primary")
    if proceed:
        if not title.strip() or end and (not start or end<=start):
            st.warning("일정명과 시작·종료 시간을 확인해 주세요.");return
        body=dict(day=str(when),start_time=str(start) if start else None,end_time=str(end) if end else None,
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
            rows=[{**body,"day":str(when+i*7*DAY),"id":str(uuid5(NAMESPACE_URL,seed+str(i)))} for i in range(repeat)]
            db.request("POST","sales_events",body=rows,prefer="resolution=ignore-duplicates")
            st.session_state.pop(key+"_seed")
        saved()

def review(db,row,target):
    reviews=db.request("GET","sales_reviews",{target:"eq."+row["id"],"order":"created_at.desc"})
    for item in reviews:
        st.caption(f'{item["created_at"][:10]} · {item["message"]}'+(" · 이전 버전" if item["revision"]!=row["revision"] else ""))
    if db.me["managed"] and db.members.get(row["owner"],{}).get("managed"):
        label="확인 완료" if target=="report" else "동행 수락"
        with st.form("review_"+row["id"]):
            message=st.text_input("피드백 또는 변경 요청")
            if st.form_submit_button(label+" · 의견 저장"):
                text=message.strip() or label
                db.request("POST","sales_reviews",body={"id":str(uuid5(NAMESPACE_URL,row["id"]+db.uid+str(row["revision"])+text)),target:row["id"],"revision":row["revision"],"message":text},prefer="resolution=ignore-duplicates")
                saved()

def calendar(db,today):
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
    team=db.me["managed"] and st.toggle("담당 조직 일정")
    mobile=st.context.headers.get("User-Agent","").lower()
    compact=any(word in mobile for word in ("android","iphone","mobile"))
    mode=st.radio("보기",["날짜별","주간","월간"],index=0 if compact or st.query_params.get("view")=="my-calendar" else 1,horizontal=True)
    day=st.date_input("기준 날짜",today,key="sales_calendar_date")
    start,end=bounds(day,mode)
    events=db.period("sales_events",start,end,order="day.asc,start_time.asc.nullsfirst")
    accepted=set()
    if db.me["managed"] and events:
        accepted={r["event"] for r in db.request("GET","sales_reviews",{"reviewer":"eq."+db.uid,"message":"eq.동행 수락","select":"event","event":"not.is.null"})}
    if not team:events=[x for x in events if x["owner"]==db.uid or x["common"] or x["id"] in accepted]
    if mode=="날짜별":
        monday=day-DAY*day.weekday()
        def set_day(value):
            st.session_state["sales_calendar_date"]=value
        with st.container(horizontal=True):
            for i,label in enumerate("월화수목금토일"):
                choice=monday+i*DAY
                st.button(f"{label} {choice.day}",key="sales_date_"+str(choice),on_click=set_day,args=(choice,),type="primary" if day==choice else "secondary")
    with st.expander("＋ 일정 등록"):event_editor(db,day)
    if mode!="날짜별":
        counts=Counter(x["day"] for x in events)
        grid=[]
        monday=start-DAY*start.weekday()
        while monday<=end:
            grid.append({label:(f"{d.day}일 · {counts[str(d)]}건" if start<=d<=end else "") for i,label in enumerate("월화수목금토일") for d in [monday+i*DAY]})
            monday+=7*DAY
        st.dataframe(grid,hide_index=True,width="stretch")
    if mode=="주간" and team:
        members=[]
        for uid,person in db.members.items():
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
    if not events:st.info("이 기간에 등록된 일정이 없습니다.")
    labels={}
    for row in events:
        owner=db.members.get(row["owner"],{}).get("label","지점 공통")
        stamp=(row["start_time"] or "종일")[:5]
        overdue=row["status"]=="예정" and (row["day"]<str(today) or row["day"]==str(today) and row["start_time"] and row["start_time"]<datetime.now(KST).strftime("%H:%M:%S"))
        status="결과 미입력" if overdue else row["status"]
        labels[row["id"]]=f'{row["day"][5:]} {stamp} · {owner} · {row["kind"]} · {status}'
        if row["id"] in accepted:labels[row["id"]]+=" · 동행"
        if row["help"]:labels[row["id"]]+=" · 지원 요청"
    if events:
        selected=st.radio("일정 선택",list(labels),format_func=labels.get,index=None)
        if selected:
            row=next(r for r in events if r["id"]==selected)
            with st.container(border=True):
                st.subheader(row["title"])
                for field in ("place","note","result","help"):
                    if row[field]:st.text(row[field])
                if row["owner"]==db.uid:
                    with st.expander("일정 수정 · 완료"):event_editor(db,day,row)
                review(db,row,"event")
    st.markdown("[화랑 내 일정 바로가기](https://hwarang-workspace.streamlit.app/?view=my-calendar)")
    st.caption("휴대폰에서 바로가기를 열고 브라우저 메뉴에서 ‘홈 화면에 추가’를 선택해 주세요.")

def reports(db,today,period):
    selected=st.date_input("기록 날짜",today,max_value=today,key="sales_day_"+period)
    day=selected if period=="일일" else bounds(selected,"주간")[0]
    rows=db.period("sales_reports",day,day,owner="eq."+db.uid,period="eq."+period)
    old=rows[0] if rows else {}
    data=old.get("data",{})
    key=f'{period}.{day}.{old.get("revision",0)}'
    totals=dict(data.get("counts",{}))
    sources=dict(data.get("sources",{}))
    coverage=data.get("coverage",[])
    if period=="일일":
        st.caption("전화는 발신 시도, 메시지는 당일 고객 수, 약속은 신규 확정, 상담·제안은 진행 횟수, 청약은 접수 건수입니다.")
        if st.button("완료 일정 불러오기"):
            events=db.period("sales_events",day,day,owner="eq."+db.uid,status="eq.완료")
            current=st.session_state.get(key+".sources",sources).copy()
            for row in events:
                if row["id"] not in current and row["kind"] in COUNTS:
                    field=key+row["kind"]
                    st.session_state[field]=st.session_state.get(field,totals.get(row["kind"],0))+1
                    current[row["id"]]=row["kind"]
            st.session_state[key+".sources"]=current
        sources=st.session_state.get(key+".sources",sources)
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
    period=st.radio("보고 구분",["일일","주간"],horizontal=True)
    start,end=bounds(day,"주간" if period=="주간" else "날짜별")
    submitted=db.period("sales_reports",start,start,period="eq."+period,submitted="eq.true")
    events=db.period("sales_events",start,end)
    index={r["owner"]:r for r in submitted}
    summary=[]
    for uid,member in db.members.items():
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
        mode=st.radio("메뉴",choices,horizontal=True,label_visibility="collapsed")
        today=datetime.now(KST).date()
        if mode=="캘린더":calendar(db,today)
        elif mode=="구성원 현황":overview(db,today)
        else:reports(db,today,mode[:2])
    except HwarangAuthError as exc:
        st.error("요청을 완료하지 못했습니다. 입력 내용을 확인하고 다시 시도해 주세요. "+str(exc))
