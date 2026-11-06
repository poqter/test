from modules.activity.contracts import contract_editor, performance, conversions
import re
import json
from copy import deepcopy
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

mobile_calendar = components.declare_component("mobile_calendar", path=str(Path(__file__).parent / "calendar_view/pwa/calendar"))

class Records:
    def __init__(self):
        self._reads={}
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
        readonly = method == "GET" or (method == "POST" and table in {"rpc/sales_members", "rpc/sales_branch_members", "rpc/sales_calendar_days"})
        if not readonly:self._reads.clear()
        def fetch(query):
            key=json.dumps([method,table,query,body,prefer],sort_keys=True)
            if readonly and key in self._reads:return deepcopy(self._reads[key])
            value=self.auth._request(method,"/rest/v1/"+table,access_token=self.token,params=query,json=body,prefer=prefer)
            if readonly:self._reads[key]=deepcopy(value)
            return value
        if not readonly or "limit" in (params or {}):
            return fetch(params)
        from modules.shared.collection_pages import collect_pages
        keys={"sales_empty_days":("owner","day"), "sales_report_history":("report","revision"), "sales_team_assignments":("member",), "rpc/sales_members":("member",), "rpc/sales_branch_members":("member",)}.get(table,("id",))
        return collect_pages(fetch, params, keys)


    def period(self,table,start,end,**params):
        return self.request("GET",table,{"and":f"(day.gte.{start},day.lte.{end})","order":"day.asc",**params})

    def save(self,table,body,old=None):
        try:
            if old:
                changed=self.request("PATCH",table,{"id":"eq."+old["id"],"revision":"eq."+str(old["revision"])},body,"return=representation")
                if not changed:raise HwarangAuthError("다른 화면에서 먼저 수정했습니다. 최신 기록을 확인한 뒤 다시 저장해 주세요.")
            else:
                self.request("POST",table,body=body,prefer="return=minimal")
        except HwarangAuthError:
            # A response may be lost after commit. Accept only the exact intended state.
            identity=(old or body).get("id")
            if identity:
                current=self.request("GET",table,{"id":"eq."+identity,"limit":"1"})
                if current and all(current[0].get(k)==v for k,v in body.items()):return
            raise


def saved():
    st.session_state["sales_dialog_notice"]="저장했습니다."
    from modules.activity import ux
    ux.refresh()

def bounds(day,view):
    if view=="주간":
        start=day-DAY*day.weekday()
        return start,start+6*DAY
    if view=="월간":return day.replace(day=1),day.replace(day=monthrange(day.year,day.month)[1])
    return day,day

def event_editor(db,day,event=None,parent=None):
    from modules.activity.redesign import event_editor as editor
    return editor(db,day,event,parent)

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

def create_dialog(db,day):
    st.session_state["sales_route"]={"type":"new","day":str(day)}
    st.session_state["sales_route_stack"]=[]
    st.session_state["sales_calendar_open"]=True

def detail_dialog(db,row):
    st.session_state["sales_route"]={"type":"event","id":row["id"]}
    st.session_state["sales_route_stack"]=[]
    st.session_state["sales_calendar_open"]=True

@st.fragment(run_every="30s")
def calendar(db,today):
    from modules.activity import ux
    ux.feedback()
    pending=st.session_state.get("sales_interactive_calendar")
    opening=isinstance(pending,dict) and pending.get("action") in ("new","event") and pending.get("nonce")!=st.session_state.get("sales_calendar_action")
    # Reuse only this already-visible calendar frame when opening a modal.
    # Normal navigation and the 30-second refresh always read current data.
    if not opening:db._reads.clear()
    # The component value is available at the start of the widget rerun.
    # Resolve navigation before querying the period, avoiding a second full run.
    nav=st.session_state.get("sales_interactive_calendar")
    if isinstance(nav,dict) and nav.get("action") in ("date","mode","weekends") and nav.get("nonce")!=st.session_state.get("sales_calendar_action"):
        st.session_state["sales_calendar_action"]=nav.get("nonce")
        if nav["action"]=="weekends":st.session_state["sales_hide_weekends"]=bool(nav.get("value"))
        try:
            target=date.fromisoformat(nav.get("value") if nav["action"]=="date" else nav.get("anchor"))
        except (TypeError,ValueError):
            target=None
        if target:st.session_state["sales_anchor"]=target
        if nav["action"]=="mode" and nav.get("value") in ("날짜별","주간","월간"):
            st.session_state["sales_view"]=nav["value"]
    mobile_shell=st.query_params.get("view")=="mobile-calendar"
    notices_slot = None if mobile_shell else st.container()
    position=st.session_state["hwarang_auth"]["profile"].get("position_code")
    filters=st.expander("직원·지점 일정 조회",key="mobile_calendar_filters") if mobile_shell else st.container()
    with filters:
        team=st.toggle("지점 일정",value=position=="branch_manager")
        branch={r["member"]:r for r in db.request("POST","rpc/sales_branch_members",body={})}
        selected_member=None
        if db.me["managed"]:
            a,b,c=st.columns([3,1,1])
            selected_member=a.selectbox("직원 이름 검색 · 선택",[None,*db.members],format_func=lambda u:db.members[u]["label"] if u else "전체 · 기존 조회 범위",key="sales_calendar_member")
            if selected_member:c.button("전체 보기",key="calendar_clear_member",on_click=lambda:st.session_state.update(sales_calendar_member=None))
            if selected_member and b.button("일정 · 활동 기록",key="calendar_member_detail"):
                st.session_state["sales_route"]={"type":"member","uid":selected_member,"day":str(st.session_state.get("sales_anchor",today)),"period":"주간" if st.session_state.get("sales_view")=="주간" else "일일"}
                st.session_state["sales_route_stack"]=[]
                st.session_state["sales_calendar_open"]=True
    mobile=st.context.headers.get("User-Agent","").lower()
    compact=any(word in mobile for word in ("android","iphone","mobile"))
    mode=st.session_state.get("sales_view","월간")
    day=st.session_state.get("sales_anchor",today)
    start,end=bounds(day,mode)
    fetch_start,fetch_end=bounds(day,"주간") if mode=="날짜별" else (start,end)
    if mode=="날짜별":
        fetch_start-=7*DAY
        fetch_end+=7*DAY
    detail_scope={"owner":"eq."+selected_member} if selected_member else {"unit":"eq."+db.me["unit"]}
    events=db.period("sales_events",fetch_start,fetch_end,order="day.asc,start_time.asc.nullsfirst",**detail_scope)
    details={r["id"]:r for r in events}
    def calendar_rows(a,b):
        return db.request("POST","rpc/sales_calendar_days",body={"first_day":str(a),"last_day":str(b)})
    summary=calendar_rows(fetch_start,fetch_end)
    events=[details.get(r["id"],r) for r in summary if team or r["owner"]==db.uid or r["companion"]==db.uid or r["common"]]
    if selected_member:
        # Detailed records are already restricted by the existing sales_scope RLS.
        events=[r for r in details.values() if r["owner"]==selected_member]
    events.sort(key=lambda r:(r["day"],r["start_time"] or ""))
    status_slot = None if mobile_shell else st.container()
    if mode=="주간" and team and not selected_member:
        members=[]
        for uid,person in branch.items():
            line={"구성원":person["label"]}
            for i,label in enumerate("월화수목금" if st.session_state.get("sales_hide_weekends",True) else "월화수목금토일"):
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
    action=calendar_view(hideMobileApp=st.query_params.get("view")=="mobile-calendar",hideWeekends=st.session_state.get("sales_hide_weekends",True),mobileSession=dict(url=db.auth.config.url,key=db.auth.config.publishable_key,token=db.token,uid=db.uid,unit=db.me["unit"],branch=position=="branch_manager"),mode=mode,day=str(day),today=str(today),events=cards,roster={uid:p["label"] for uid,p in branch.items() if not selected_member or uid==selected_member} if team else {},rangeStart=str(fetch_start),rangeEnd=str(fetch_end),key="sales_interactive_calendar",default=None)
    if isinstance(action,dict) and action.get("nonce")!=st.session_state.get("sales_calendar_action"):
        st.session_state["sales_calendar_action"]=action.get("nonce")
        command,value=action.get("action"),action.get("value")
        if command=="mode" and value in ("날짜별","주간","월간"):
            st.session_state["sales_view"]=value
            ux.refresh()
        if command in ("new","date"):
            try:target=date.fromisoformat(value)
            except (TypeError,ValueError):return
            if command=="new":create_dialog(db,target)
            else:
                st.session_state["sales_anchor"]=target
                ux.refresh()
        if command in ("event","new") and action.get("anchor"):
            try:st.session_state["sales_anchor"]=date.fromisoformat(action["anchor"])
            except (TypeError,ValueError):pass
        if command=="event":
            found=next((r for r in events if r["id"]==value),None)
            if found and found["id"] in details:detail_dialog(db,found)
            elif found:st.info(next(c["label"] for c in cards if c["id"]==value))
    with notices_slot if notices_slot is not None else st.container():
        notices=db.request("GET","sales_notices",{"seen":"eq.false","order":"created_at.desc","limit":"20","select":"id,message,sales_events(day,kind)"})
        if notices:
            with st.expander("일정 알림",expanded=True,key="sales_notice_panel",on_change="rerun"):
                st.caption(f"새 알림 {len(notices)}건")
                for notice in notices:
                    event=notice.get("sales_events") or {}
                    st.write(f'{event.get("day","")} · {event.get("kind","")} · {notice["message"]}')
                if st.button("표시된 알림 확인"):
                    ids=",".join(n["id"] for n in notices)
                    db.request("PATCH","sales_notices",{"id":"in.("+ids+")"},{"seen":True})
                    ux.refresh()
    with status_slot if status_slot is not None else st.container():
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
            from modules.activity.status_policy import unregistered_exclusions, summary_groups
            states={uid:day_state(uid) for uid in branch.keys() & db.members.keys()}
            excluded=unregistered_exclusions(db.auth, [uid for uid,state in states.items() if state=="미등록"])
            groups=summary_groups(states, {uid:branch[uid]["label"] for uid in states}, excluded)
            with st.expander("오늘의 팀" if position=="team_leader" else "오늘의 지점",key="sales_team_panel",on_change="rerun"):
                st.caption("미등록 "+str(len(groups.get("미등록",[])))+"명 · 일정 없음 "+str(len(groups.get("일정 없음",[])))+"명")
                for state,names in groups.items():st.write(state+" "+str(len(names))+"명 · "+", ".join(sorted(names)))
        if day_state(db.uid) in ("미등록","일정 없음","모두 취소"):
            checked=db.uid in confirmations
            if st.button("오늘 일정 없음 · 되돌리기" if checked else "오늘 일정 없음"):
                if checked:db.request("DELETE","sales_empty_days",{"owner":"eq."+db.uid,"day":"eq."+str(today)})
                else:db.request("POST","sales_empty_days",body={"day":str(today)},prefer="resolution=ignore-duplicates")
                ux.refresh()
    if st.query_params.get("view")!="mobile-calendar":st.caption("모바일 앱 열기로 캘린더에 접속한 뒤 홈 화면에 추가할 수 있습니다.")
    if st.query_params.get("view")!="mobile-calendar":
        tasks_panel=st.expander("내 후속 할 일",key="sales_tasks_panel",on_change="rerun")
        if tasks_panel.open:
            with tasks_panel:
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
    # A dialog opened inside this fragment must be re-registered when its
    # calendar refreshes; otherwise Streamlit removes its widget callbacks.
    if st.session_state.pop("sales_calendar_open",False) or st.session_state.get("sales_route"):
        from modules.activity.redesign import dialog
        st.session_state["sales_dialog_rendered"]=True
        dialog(db)



@st.fragment
def reports(db,today,period):
    db._reads.clear()
    from modules.activity.redesign import reports as render
    return render(db,today,period)

def report_detail(db,row,show_content=True):
    with st.expander("제출 내용 · 확인 및 피드백",expanded=True):
        if show_content:
            from modules.activity.redesign import count_grid
            from modules.activity.ux import details
            count_grid(row["data"].get("counts",{}))
            details([(label,row["data"].get(field)) for field,label in [("note","진행사항"),("plan","다음 주 계획"),("help","지원 요청")]])
        history=db.request("GET","sales_report_history",{"report":"eq."+row["id"],"order":"revision.desc"})
        for prior in history:
            st.caption("수정 전 · "+prior["changed_at"][:16])
            st.write(prior["data"]["counts"],prior["data"].get("note",""),prior["data"].get("plan",""),prior["data"].get("help",""))
        review(db,row,"report")

@st.fragment
def overview(db,today):
    db._reads.clear()
    from modules.activity.redesign import overview as render
    return render(db,today)

def run():
    from modules.activity import ux, redesign
    st.session_state["sales_dialog_rendered"]=False
    ux.styles()
    st.title("영업활동 관리")
    if notice:=st.session_state.pop("sales_notice",None):st.success(notice)
    try:
        db=Records()
        choices=["캘린더","일일 기록","주간 기록"]+(["구성원 현황"] if db.me["managed"] else [])
        # Preserve unsubmitted input across tabs and ask before changing the work context.
        desired=st.session_state.get("sales_menu",choices[0])
        prior=st.session_state.get("sales_previous_menu",desired)
        active=st.session_state.get("sales_active_draft")
        if desired!=prior and active and ux.dirty(active):
            st.session_state["sales_pending_menu"]=desired
            st.session_state["sales_menu"]=prior
        if pending:=st.session_state.get("sales_pending_menu"):
            st.warning("저장하지 않은 기록이 있습니다. 내용을 유지하고 다른 메뉴로 이동할까요?")
            a,b,c=st.columns(3)
            if c.button("내용 버리고 이동"):
                ux.clear_draft(active)
                st.session_state["sales_menu"]=pending
                st.session_state["sales_previous_menu"]=pending
                st.session_state.pop("sales_pending_menu",None)
                st.session_state.pop("sales_active_draft",None)
                st.rerun()
            if a.button("내용 유지하고 이동"):
                st.session_state["sales_menu"]=pending
                st.session_state["sales_previous_menu"]=pending
                st.session_state.pop("sales_pending_menu",None)
                st.session_state.pop("sales_active_draft",None)
                st.rerun()
            if b.button("계속 작성"):
                st.session_state.pop("sales_pending_menu",None);st.rerun()
        with st.container(key="sales_workspace"):
            tabs=st.tabs(choices,key="sales_menu",on_change="rerun")
            st.session_state["sales_previous_menu"]=st.session_state.get("sales_menu",choices[0])
            today=datetime.now(KST).date()
            for mode,tab in zip(choices,tabs):
                if tab.open:
                    with tab:
                        if mode=="캘린더":calendar(db,today)
                        elif mode=="구성원 현황":overview(db,today)
                        else:reports(db,today,mode[:2])
        if st.session_state.get("sales_route") and not st.session_state.get("sales_dialog_rendered"):redesign.dialog(db)
    except HwarangAuthError as exc:
        st.error("요청을 완료하지 못했습니다. 입력 내용은 유지됩니다. "+str(exc))
