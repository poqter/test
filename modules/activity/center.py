from modules.activity import read_state
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

WORKSPACE_HOST_PROTOCOL = 1
KST=ZoneInfo("Asia/Seoul")
SALES_TYPES={"TA":"고객 연락","AP":"초회 상담","PC":"프레젠테이션 / 클로징","CS":"기존 고객 관리"}
KINDS=["미분류",*SALES_TYPES,"청약","교육","회의","휴무","기타"]
REPORT_KIND={"AP":"상담","PC":"제안"}
from modules.activity.daily import COUNTS
DAY=timedelta(days=1)

mobile_calendar = components.declare_component("mobile_calendar", path=str(Path(__file__).parent / "calendar_view/pwa/calendar"))

class Records:
    def __init__(self):
        resumed=read_state.consume()
        self._reads=resumed if resumed is not None else {}
        self._resumed=resumed is not None
        self.auth=HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))
        identity=st.session_state["hwarang_auth"]
        from modules.activity.view_scope import current
        self.view_scope=current()
        self.auth.http.headers["X-Hwarang-View-Scope"]=self.view_scope
        calendar_entry = (st.session_state.get('mobile_page', '캘린더') == '캘린더'
            if st.query_params.get('view') == 'mobile-calendar'
            else st.session_state.get('sales_menu', '캘린더') == '캘린더')
        if calendar_entry:
            self.auth.http.headers['X-Hwarang-Calendar-Entry'] = '1'
        self.token=identity["access_token"]
        self.uid=identity["profile"]["id"]
        context=self.request("POST","rpc/sales_calendar_context",body={})
        entry=context.get('entry')
        if isinstance(entry, dict):
            day=entry['day']
            def seed(method, table, params, value, body=None):
                key=json.dumps([method,table,params,body,None],sort_keys=True)
                self._reads[key]=value
            seed('POST','rpc/sales_calendar_days',None,entry['summary'],{'first_day':day,'last_day':day})
            seed('GET','sales_empty_days',{'day':'eq.'+day,'select':'owner'},entry['empty_days'])
            seed('GET','sales_notices',{'seen':'eq.false','order':'created_at.desc','limit':'20','select':'id,message,sales_events(day,kind)'},entry['notices'][:20])
            seed('GET','sales_notices',{'seen':'eq.false','select':'id','limit':'50'},[{'id':n['id']} for n in entry['notices']])
        rows=context["members"]
        self.branch={r["member"]:r for r in context["branch"]}
        self.fast_calendar=True
        self.members={row["member"]:row for row in rows}
        if self.uid not in self.members:
            raise HwarangAuthError("영업활동 관리 이용 권한을 확인해 주세요.")
        self.me=self.members[self.uid]

    def request(self,method,table,params=None,body=None,prefer=None):
        if method == "GET" and table == "sales_events":
            params={"deleted_at":"is.null",**(params or {})}
        readonly = method == "GET" or (method == "POST" and table in {"rpc/sales_members", "rpc/sales_branch_members", "rpc/sales_calendar_days", "rpc/sales_calendar_days_v2", "rpc/sales_calendar_stamp", "rpc/sales_calendar_context", "rpc/sales_calendar_payload"})
        if not readonly:
            self._reads.clear()
            read_state.invalidate()
        def fetch(query):
            key=json.dumps([method,table,query,body,prefer],sort_keys=True)
            if readonly and key in self._reads:return deepcopy(self._reads[key])
            value=self.auth._request(method,"/rest/v1/"+table,access_token=self.token,params=query,json=body,prefer=prefer)
            if readonly:self._reads[key]=deepcopy(value)
            return value
        if readonly:
            cached_key=json.dumps([method,table,params,body,prefer],sort_keys=True)
            if cached_key in self._reads:return deepcopy(self._reads[cached_key])
        if table in {"rpc/sales_calendar_stamp","rpc/sales_calendar_context","rpc/sales_calendar_payload"} or not readonly or "limit" in (params or {}):
            return fetch(params)
        from modules.shared.collection_pages import collect_pages
        keys={"sales_empty_days":("owner","day"), "sales_report_history":("report","revision"), "sales_team_assignments":("member",), "sales_deputy_assignments":("member",), "sales_report_checks":("report","reviewer"), "rpc/sales_members":("member",), "rpc/sales_branch_members":("member",)}.get(table,("id",))
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

@st.fragment
def calendar(db,today):
    """Stable component mount: browser owns navigation, forms and dialog lifecycle."""
    from modules.activity import calendar_service
    import logging
    if hasattr(db,"token"):db.token=st.session_state.get("hwarang_auth",{}).get("access_token",db.token)
    state=st.session_state
    owner=state.get("sales_persistent_owner")
    if owner!=db.uid:
        state["sales_persistent_owner"]=db.uid
        for key in ("sales_persistent_boot","sales_persistent_reply","sales_persistent_nonce"):
            state.pop(key,None)
    component_key="sales_interactive_calendar" + ("_"+str(state["calendar_scope_generation"]) if state.get("calendar_scope_generation") else "")
    pending=state.get(component_key)
    if isinstance(pending,dict) and pending.get("action")=="reauth" and pending.get("nonce")!=state.get("sales_reauth_nonce"):
        state["sales_reauth_nonce"]=pending["nonce"]
        st.rerun()
    reply=state.get("sales_persistent_reply")
    if isinstance(pending,dict) and pending.get("action")=="rpc" and pending.get("nonce")!=state.get("sales_persistent_nonce"):
        nonce=pending.get("nonce")
        try:
            request=pending["value"]
            result=calendar_service.command(db,request["op"],request.get("args",{}))
            reply={"nonce":nonce,"ok":True,"result":result}
        except (HwarangAuthError,ValueError,KeyError,TypeError) as exc:
            reply={"nonce":nonce,"ok":False,"error":str(exc)}
        except Exception:
            logging.getLogger(__name__).exception("Persistent calendar request failed")
            reply={"nonce":nonce,"ok":False,"error":"요청을 완료하지 못했습니다. 입력은 유지됩니다. 다시 시도해 주세요."}
        state["sales_persistent_reply"]=reply
        state["sales_persistent_nonce"]=nonce
    boot_fresh = "sales_persistent_boot" not in state or state["sales_persistent_boot"].get("access") != json.dumps(db.members,sort_keys=True)
    if boot_fresh:
        position=state["hwarang_auth"]["profile"].get("position_code")
        team=state.get("sales_calendar_team",position=="branch_manager" or getattr(db,"view_scope","daily").startswith("{"))
        member=state.get("sales_calendar_member") if db.me["managed"] else None
        if member not in db.members:member=None
        state["sales_persistent_boot"]=calendar_service.bootstrap(db,today,state.get("sales_anchor",today),state.get("sales_view","월간"),team,member)
    # No conditional Streamlit elements before this mount: its position and key are fixed.
    args=dict(boot=state["sales_persistent_boot"],bootFresh=boot_fresh,reply=reply,
        shellFirst=bool(state.get("_calendar_deployment")),
        hideMobileApp=st.query_params.get("view")=="mobile-calendar",
        changeNonce=state.pop("sales_calendar_refresh",None),
        mobileSession=dict(url=db.auth.config.url,key=db.auth.config.publishable_key,token=db.token,uid=db.uid,viewScope=getattr(db,"view_scope","daily")),
        )
    if state.get("sales_workspace_host_enabled"):
        state["sales_host_args"]=args
        st.markdown('<div id="sales-calendar-anchor" style="height:700px"></div>',unsafe_allow_html=True)
    else:
        calendar_view(**args,key=component_key,default=None)
    calendar_extras(db,today)

@st.fragment
def calendar_extras(db,today):
    """Existing activity summaries remain independently refreshable."""
    from modules.activity import ux
    mobile_shell=st.query_params.get("view")=="mobile-calendar"
    position=st.session_state["hwarang_auth"]["profile"].get("position_code")
    fetch_start=fetch_end=today
    def calendar_rows(a,b):
        return db.request("POST","rpc/sales_calendar_days",body={"first_day":str(a),"last_day":str(b)})
    summary=calendar_rows(today,today)
    with st.container():
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
    with st.container():
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
        if db.me["managed"] and not mobile_shell:
            team_panel=st.expander("오늘의 팀" if position=="team_leader" else "오늘의 지점",key="sales_team_panel",on_change="rerun")
            if team_panel.open:
                from modules.activity.status_policy import unregistered_exclusions, summary_groups
                branch={r["member"]:r for r in db.request("POST","rpc/sales_branch_members",body={})}
                states={uid:day_state(uid) for uid in branch.keys() & db.members.keys()}
                excluded=unregistered_exclusions(db.auth, [uid for uid,state in states.items() if state=="미등록"])
                groups=summary_groups(states, {uid:branch[uid]["label"] for uid in states}, excluded)
                with team_panel:
                    st.caption("미등록 "+str(len(groups.get("미등록",[])))+"명 · 일정 없음 "+str(len(groups.get("일정 없음",[])))+"명")
                    for state,names in groups.items():st.write(state+" "+str(len(names))+"명 · "+", ".join(sorted(names)))
        if day_state(db.uid) in ("미등록","일정 없음","모두 취소"):
            checked=db.uid in confirmations
            if st.button("오늘 일정 없음 · 되돌리기" if checked else "오늘 일정 없음"):
                if checked:db.request("DELETE","sales_empty_days",{"owner":"eq."+db.uid,"day":"eq."+str(today)})
                else:db.request("POST","sales_empty_days",body={"day":str(today)},prefer="resolution=ignore-duplicates")
                ux.refresh()
    if st.query_params.get("view")!="mobile-calendar":st.caption("모바일 앱 열기로 캘린더에 접속한 뒤 홈 화면에 추가할 수 있습니다.")


@st.fragment
def reports(db,today,period):
    read_state.refresh(db,("reports",period,st.session_state.get("sales_day_"+period)))
    from modules.activity.redesign import reports as render
    return render(db,today,period)

def report_detail(db,row,show_content=True):
    with st.expander("제출 내용 · 확인 및 피드백",expanded=True):
        if row["data"].get("no_activity"):st.caption("활동 없는 날로 제출한 기록입니다.")
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
    context=('manager',read_state.identity(),today,
        *(st.session_state.get('manager_pref_'+name) for name in ('date','period','unit','team')))
    read_state.refresh(db,context,seconds=15)
    if st.button('최신 조회',key='manager_refresh',help='다른 직원의 최신 변경 내용을 지금 불러옵니다.'):
        db._reads.clear()
        read_state.invalidate()
    from modules.activity.redesign import overview as render
    return render(db,today)

def run():
    from modules.activity import ux, redesign
    st.session_state["sales_dialog_rendered"]=False
    ux.styles()
    st.title("영업활동 관리")
    if notice:=st.session_state.pop("sales_notice",None):st.success(notice)
    from modules.activity.loading import calendar_loading
    loading = calendar_loading() if not st.session_state.get("sales_workspace_host_enabled") and st.session_state.get("sales_menu", "캘린더") == "캘린더" else st.empty()
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
                        if mode=="캘린더":
                            calendar(db,today)
                        elif mode=="구성원 현황":overview(db,today)
                        else:reports(db,today,mode[:2])
        if st.session_state.get("sales_route") and not st.session_state.get("sales_dialog_rendered"):redesign.dialog(db)
    except HwarangAuthError as exc:
        loading.empty()
        if st.session_state.get("sales_workspace_host_enabled"):st.session_state["sales_host_error"]=str(exc)
        st.error("요청을 완료하지 못했습니다. 입력 내용은 유지됩니다. "+str(exc))
        if st.button("다시 불러오기", key="sales_context_retry"):
            st.rerun()
    finally:
        loading.empty()
