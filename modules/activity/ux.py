"""Shared presentation and session-only drafts. Existing RLS remains authoritative."""
from copy import deepcopy
from datetime import datetime
from html import escape
from uuid import uuid4
import streamlit as st

LABELS = {"TA": "고객 연락", "CS": "고객 관리"}
EVENT_FIELDS = ("day", "start_time", "end_time", "time_pending", "title", "kind", "place", "note", "help", "common", "status", "result", "companion")

def copy_event(row):
    allowed = ("day", "start_time", "end_time", "time_pending", "title", "kind", "place", "note", "companion")
    return {**{k: row.get(k) for k in allowed}, "status": "예정", "result": "", "help": "", "common": False}

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
    [data-testid="stDialog"]:has(.sales-dialog-marker) [role="dialog"]{max-width:880px}
    @media(max-width:700px){.st-key-sales_workspace input,.st-key-sales_workspace textarea,[data-testid="stDialog"]:has(.sales-dialog-marker) input{font-size:16px!important}[data-testid="stDialog"]:has(.sales-dialog-marker) [role="dialog"]{width:calc(100% - 16px);max-height:95dvh}.sales-details{grid-template-columns:65px 1fr;gap:8px}[data-testid="stPopoverBody"]:has(.sales-reference){position:fixed!important;bottom:0!important;top:auto!important;left:0!important;width:100%!important;max-height:75dvh;overflow:auto;border-radius:16px 16px 0 0}}
    </style>''')

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

def navigate(route,push=False):
    if push and st.session_state.get("sales_route"): st.session_state.setdefault("sales_route_stack",[]).append(st.session_state["sales_route"])
    elif not push: st.session_state["sales_route_stack"]=[]
    st.session_state["sales_route"]=route
    st.session_state.pop("sales_close_check",None)
    st.rerun()

def back():
    stack=st.session_state.get("sales_route_stack",[])
    if stack: st.session_state["sales_route"]=stack.pop()
    else: st.session_state.pop("sales_route",None)
    st.session_state.pop("sales_close_check",None)
    st.rerun()

def close_control(key=None):
    if st.button("이전 화면으로" if st.session_state.get("sales_route_stack") else "닫기",key="sales_close"):
        if key and dirty(key): st.session_state["sales_close_check"]=True
        else: back()
    if st.session_state.get("sales_close_check"):
        st.warning("저장하지 않은 변경이 있습니다. 작성 내용을 유지한 채 닫을까요?")
        a,b=st.columns(2)
        if a.button("계속 작성",key="sales_keep"):
            st.session_state.pop("sales_close_check",None);st.rerun()
        if b.button("내용 유지하고 닫기",key="sales_leave"): back()

def conflict_recovery(d,key):
    if not d.get("conflict"):return
    st.warning("저장이 확인되지 않았습니다. 현재 입력을 유지해 다시 저장하거나, 최신 기록으로 다시 시작할 수 있습니다.")
    discard=st.checkbox("현재 입력 대신 최신 저장 내용을 불러오겠습니다",key=d["epoch"]+"reload_check")
    if st.button("최신 기록 불러오기",disabled=not discard,key=d["epoch"]+"reload"):
        clear_draft(key);st.rerun()
