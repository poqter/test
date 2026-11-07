"""Shared presentation and session-only drafts. Existing RLS remains authoritative."""
from copy import deepcopy
import json
from streamlit.errors import StreamlitAPIException
from datetime import datetime
from html import escape
from uuid import uuid4
import streamlit as st

LABELS = {"TA": "TA", "CS": "CS"}
EVENT_FIELDS = ("day", "start_time", "end_time", "time_pending", "title", "kind", "place", "note", "help", "common", "status", "result", "companion")

def copy_event(row):
    allowed = ("day", "start_time", "end_time", "time_pending", "title", "kind", "place", "note", "companion")
    return {**{k: row.get(k) for k in allowed}, "status": "예정", "result": "", "help": "", "common": False}

def remember_recent(uid, rows):
    key="sales_recent_"+uid
    previous=st.session_state.get(key,[])
    fresh=[{"id":r["id"],"place":r.get("place") or "","companion":r.get("companion")} for r in rows if r.get("owner")==uid and not r.get("deleted_at")]
    by_id={}
    for r in [*fresh,*previous]:by_id.setdefault(r["id"],r)
    st.session_state[key]=list(by_id.values())[:40]

def shifted_end(previous, current, end):
    if not all((previous, current, end)) or end <= previous: return end
    origin = datetime.combine(datetime.min.date(), previous)
    shifted = datetime.combine(datetime.min.date(), current) + (datetime.combine(datetime.min.date(), end) - origin)
    return shifted.time() if shifted.date() == origin.date() else None

def report_totals(rows, counts):
    return {c: sum(int((r.get("data") or {}).get("counts", {}).get(c, 0) or 0) for r in rows if r.get("submitted")) for c in counts}

def refreshed_counts(counts, previous, current, metrics):
    return {m: max(0, int(counts.get(m, 0)) - list(previous.values()).count(m) + list(current.values()).count(m)) for m in metrics}

def schedule_time(row):
    if row.get("start_time"): return row["start_time"][:5] + ("–" + row["end_time"][:5] if row.get("end_time") else "")
    return "시간 미정" if row.get("time_pending") else "종일"

def compact():
    return any(x in st.context.headers.get("User-Agent", "").lower() for x in ("android", "iphone", "mobile"))

def styles():
    st.html('''<style>
    .st-key-sales_workspace {color:#223950}


    .st-key-sales_workspace [data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:14px}
    .st-key-sales_workspace input,.st-key-sales_workspace textarea,[data-testid="stDialog"]:has(.sales-dialog-marker) input,[data-testid="stDialog"]:has(.sales-dialog-marker) textarea {border:1px solid #dbe3ed!important;border-radius:8px!important}
    .st-key-sales_workspace input::placeholder,.st-key-sales_workspace textarea::placeholder,[data-testid="stDialog"]:has(.sales-dialog-marker) input::placeholder {color:#8d9caf!important;opacity:1}
    .sales-summary{display:flex;gap:10px;flex-wrap:wrap;margin:5px 0 16px}.sales-summary span{padding:6px 10px;background:#eef3f9;border-radius:7px;color:#334e6b;font-size:13px}
    .sales-details{display:grid;grid-template-columns:85px 1fr;gap:10px 14px;margin:18px 0}.sales-details dt{color:#718197;font-size:13px}.sales-details dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.sales-dialog-marker{display:none}
    @media(max-width:700px){.st-key-sales_workspace input,.st-key-sales_workspace textarea,[data-testid="stDialog"]:has(.sales-dialog-marker) input{font-size:16px!important}.sales-details{grid-template-columns:65px 1fr;gap:8px}[data-testid="stPopoverBody"]:has(.sales-reference){position:fixed!important;bottom:0!important;top:auto!important;left:0!important;width:100%!important;max-height:75dvh;overflow:auto;border-radius:16px 16px 0 0}}
    [data-testid="stDialog"]:has(.sales-dialog-marker) input,[data-testid="stDialog"]:has(.sales-dialog-marker) textarea {scroll-margin:80px 0}
    </style>''')
    st.html('''<script>
    if(!window.hwarangActivityViewport){
      window.hwarangActivityViewport=true;
      const visibility=()=>document.querySelectorAll('iframe').forEach(f=>f.contentWindow.postMessage({type:'hwarang.activity.visibility',visible:!document.hidden},location.origin));
      document.addEventListener('visibilitychange',visibility);window.addEventListener('online',visibility);
      const resize=()=>{document.documentElement.style.setProperty('--sales-viewport',(window.visualViewport?.height||innerHeight)+'px');};
      window.visualViewport?.addEventListener('resize',resize);resize();
    }
    </script>''',unsafe_allow_javascript=True)

def summary(items):
    st.html('<div class="sales-summary">'+''.join('<span>'+escape(str(x))+'</span>' for x in items)+'</div>')

def details(items):
    st.html('<dl class="sales-details">'+''.join('<dt>'+escape(k)+'</dt><dd>'+escape(str(v))+'</dd>' for k,v in items if v)+'</dl>')

def draft(key, initial, old=None):
    bucket=st.session_state.setdefault("sales_drafts",{})
    if key not in bucket: bucket[key]={"values":deepcopy(initial),"baseline":deepcopy(initial),"old":deepcopy(old),"epoch":str(uuid4())}
    return bucket[key]

def dirty(key):
    d=st.session_state.get("sales_drafts",{}).get(key)
    return bool(d and d["values"]!=d["baseline"])

def clear_draft(key): st.session_state.get("sales_drafts",{}).pop(key,None)

def field(d,name,renderer,label,after_change=None,**kwargs):
    key="sales_input_"+d["epoch"]+"_"+name
    if key not in st.session_state: st.session_state[key]=d["values"].get(name)
    def changed():
        d["values"][name]=st.session_state[key]
        if after_change:after_change()
    return renderer(label,key=key,on_change=changed,**kwargs)

def set_values(d,values):
    d["values"].update(deepcopy(values))
    for name,value in values.items(): st.session_state["sales_input_"+d["epoch"]+"_"+name]=value

def refresh():
    """Keep interactions inside their current fragment; full run only outside one."""
    try: st.rerun(scope="fragment")
    except StreamlitAPIException: st.rerun()


def saved_event(key,event_id):
    st.session_state.pop("sales_write_in_progress",None)
    clear_draft(key)
    stack=st.session_state.get("sales_route_stack",[])
    # Editing returns to the saved detail without accumulating duplicate routes.
    if stack and stack[-1].get("type")=="event" and stack[-1].get("id")==event_id:
        stack.pop()
    st.session_state["sales_route"]={"type":"event","id":event_id}
    st.session_state["sales_dialog_notice"]="저장했습니다. 최신 일정입니다."
    st.session_state["sales_calendar_refresh"]=str(uuid4())
    refresh()


def feedback():
    if message:=st.session_state.pop("sales_dialog_notice",None):st.success(message)
    if nonce:=st.session_state.pop("sales_calendar_refresh",None):
        # Trusted same-origin signal only; no records or tokens travel through HTML.
        st.html("<script>document.querySelectorAll('iframe').forEach(f=>f.contentWindow.postMessage({type:'hwarang.activity.changed',nonce:"
                +json.dumps(nonce)+"},location.origin));</script>",unsafe_allow_javascript=True)


def focus_field(d,name):
    selector=".st-key-sales_input_"+d["epoch"]+"_"+name+" input"
    st.html("<script>requestAnimationFrame(()=>{const e=document.querySelector("+json.dumps(selector)+");if(e){e.focus({preventScroll:true});e.scrollIntoView({block:'center',behavior:'smooth'});}});</script>",unsafe_allow_javascript=True)


def navigate(route,push=False):
    already_open=bool(st.session_state.get("sales_route"))
    if push and st.session_state.get("sales_route"): st.session_state.setdefault("sales_route_stack",[]).append(st.session_state["sales_route"])
    elif not push: st.session_state["sales_route_stack"]=[]
    st.session_state["sales_route"]=route
    st.session_state.pop("sales_close_check",None)
    if already_open:refresh()
    else:st.rerun()

def back():
    stack=st.session_state.get("sales_route_stack",[])
    if stack: st.session_state["sales_route"]=stack.pop()
    else: st.session_state.pop("sales_route",None)
    st.session_state.pop("sales_close_check",None)
    if st.session_state.get("sales_route"): refresh()
    else: st.rerun() # Streamlit requires a full run to remove the modal itself.

def close_control(key=None,requested=False,top_container=None):
    bottom=st.button("이전 화면으로" if st.session_state.get("sales_route_stack") else "닫기",key="sales_close")
    if requested or bottom:
        if key and dirty(key):
            st.session_state["sales_close_check"]=True
            st.session_state["sales_close_at_top"]=requested
        else: back()
    if st.session_state.get("sales_close_check"):
        target=top_container if top_container is not None and st.session_state.get("sales_close_at_top") else st.container()
        with target:
            st.warning("저장하지 않은 변경이 있습니다. 닫는 방법을 선택해 주세요.")
            st.caption("내용 유지는 현재 접속 중에만 보관됩니다. 이미 저장된 일정·기록은 삭제되지 않습니다.")
            a,b,c=st.columns(3)
            if a.button("계속 작성",key="sales_keep"):
                st.session_state.pop("sales_close_check",None);refresh()
            if b.button("내용 유지하고 닫기",key="sales_leave"): back()
            if c.button("저장하지 않고 닫기",key="sales_discard"):
                clear_draft(key)
                # Source rows and other drafts are deliberately untouched.
                back()

def conflict_recovery(d,key):
    if not d.get("conflict"):return
    st.warning("저장이 확인되지 않았습니다. 현재 입력을 유지해 다시 저장하거나, 최신 기록으로 다시 시작할 수 있습니다.")
    discard=st.checkbox("현재 입력 대신 최신 저장 내용을 불러오겠습니다",key=d["epoch"]+"reload_check")
    if st.button("최신 기록 불러오기",disabled=not discard,key=d["epoch"]+"reload"):
        clear_draft(key)
        st.session_state.get("sales_route",{}).pop("editing_snapshot",None)
        refresh()


def delete_styles():
    """Keep destructive action styling mounted with dialog fragment updates."""
    st.html('''<style>
    body [class*="st-key-delete_"][data-testid] button{color:#b42318!important;background:#fff1f0!important;border:1.5px solid #d92d20!important;font-weight:700!important}
    body [class*="st-key-delete_"][data-testid] button :is(p,span){color:inherit!important}
    body [class*="st-key-delete_"][data-testid] button:hover{background:#ffe4e1!important;border-color:#b42318!important}
    body [class*="st-key-delete_"][data-testid] button:focus-visible{outline:3px solid #d92d20!important;outline-offset:2px}
    </style>''')


def dialog_styles():
    st.html('''<style>
    [data-testid="stDialog"] div:has(>[role="dialog"]):has(.sales-dialog-marker){width:min(880px,calc(100vw - 32px))!important;max-width:880px!important;min-width:0!important;flex:0 1 880px!important;background:#fff!important;overflow:hidden!important;border-radius:20px}
    [role="dialog"]:has(.sales-dialog-marker){width:100%!important;max-width:none!important;max-height:calc(100dvh - 32px)!important;padding:0!important;overflow:hidden!important;background:#fff!important}
    [role="dialog"]:has(.sales-dialog-marker)>[slot="title"]{display:none}
    [role="dialog"]:has(.sales-dialog-marker)>div{padding:0!important;overflow:hidden!important}
    [role="dialog"] [data-testid="stElementContainer"]:has(>.stHtml>.sales-dialog-marker){display:none}
    [role="dialog"] [data-testid="stVerticalBlock"]:has(>[data-testid="stLayoutWrapper"]>.st-key-sales_dialog_header){gap:0!important}
    .st-key-sales_dialog_header{padding:10px 20px!important;gap:12px!important;min-height:64px;background:#fff;border-bottom:1px solid #e6ebf1}
    .st-key-sales_dialog_header .st-key-sales_close_top{margin-left:auto;flex:0 0 auto!important}
    .st-key-sales_dialog_header button{min-width:44px;min-height:44px}
    .st-key-sales_dialog_header p{margin:0!important}
    .st-key-sales_dialog_body{max-height:calc(100dvh - 180px)!important;overflow-y:auto!important;overflow-x:hidden!important;min-height:0;padding:16px 24px 24px!important;scrollbar-gutter:stable;overscroll-behavior:contain;scroll-padding:20px}
    .st-key-sales_dialog_footer{padding:8px 16px;background:white;border-top:1px solid #e6ebf1}
    .st-key-sales_event_save{position:sticky;bottom:0;background:white;z-index:3;padding:8px 0}
    .st-key-sales_dialog_body h3{padding-top:0!important}
    @media(max-width:700px){
      [data-testid="stDialog"] div:has(>[role="dialog"]):has(.sales-dialog-marker){width:calc(100vw - 16px)!important}
      body:has(.st-key-mobile_header) [data-testid="stDialog"]{align-items:flex-start!important;padding:8px 0!important}
      body:has(.st-key-mobile_header) [data-testid="stDialog"] div:has(>[role="dialog"]):has(.sales-dialog-marker){margin-top:0!important;margin-bottom:0!important}
      .st-key-sales_dialog_header{padding:8px 12px!important;min-height:52px}
      .st-key-sales_dialog_body [data-testid="stElementContainer"]:has(> [data-testid="stEmpty"]){display:none}

      .st-key-sales_dialog_body{padding:12px 16px max(20px,env(safe-area-inset-bottom))!important;max-height:calc(var(--sales-viewport,100dvh) - 160px)!important}
    }
    </style>''')
