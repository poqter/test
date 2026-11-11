"""Offline fixtures for activity UI regression; no network or credentials."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
import streamlit as st

UID="11111111-1111-4111-8111-111111111111"
OTHER="22222222-2222-4222-8222-222222222222"
EVENT="33333333-3333-4333-8333-333333333333"
class FakeRecords:
    def __init__(self):
        self.uid=UID;self._reads={};self.token="fake"
        self.members={UID:{"member":UID,"label":"테스트 작성자","unit":"unit","managed":True},OTHER:{"member":OTHER,"label":"테스트 구성원","unit":"unit","managed":True}}
        self.me=self.members[UID]
        self.auth=SimpleNamespace(config=SimpleNamespace(url="https://example.invalid",publishable_key="fake"),_request=lambda *a,**k:[])
        st.session_state.setdefault("fixture_events",[dict(id=EVENT,owner=UID,unit="unit",day="2026-11-06",start_time="14:00:00",end_time="15:00:00",time_pending=False,title="상담 테스트",kind="AP",status="예정",place="상담실",note="기존 메모",help="",result="",common=False,companion=None,revision=1,previous_event=None,case_id=None)])
        st.session_state.setdefault("fixture_reports",[])
        st.session_state.setdefault("fixture_reviews",[])
        st.session_state.setdefault("fixture_writes",[])
        st.session_state.setdefault("fixture_drafts",[])
        st.session_state.setdefault("fixture_checks",[])
    def request(self,method,table,params=None,body=None,prefer=None):
        st.session_state.setdefault("fixture_reads",[]).append((method,table))
        if table=='rpc/sales_check_daily_period':
            from modules.shared.hwarang_auth import HwarangAuthError
            rows=[r for r in st.session_state['fixture_reports'] if r['owner']==body['p_owner'] and r['period']=='일일' and r['submitted'] and body['p_first']<=r['day']<=body['p_last']]
            if {r['id']:r['revision'] for r in rows}!=body['p_versions']:raise HwarangAuthError('changed')
            for row in rows:self.request('POST','rpc/sales_check_report',body={'p_report':row['id'],'p_revision':row['revision']})
            if body['p_message']:
                row=rows[-1];self.request('POST','sales_reviews',body={'id':body['p_request'],'report':row['id'],'revision':row['revision'],'message':body['p_message']})
            return True
        if table=='rpc/sales_support_recipients':return st.session_state.get('fixture_support_candidates',[])
        if table=="rpc/sales_calendar_stamp":return "fixture-stamp"
        if method=="POST" and table in ("rpc/sales_members","rpc/sales_branch_members"):return list(self.members.values())
        if method=="POST" and table in ("rpc/sales_calendar_days","rpc/sales_calendar_days_v2"):return deepcopy([r for r in st.session_state["fixture_events"] if not r.get("deleted_at")])
        if method=="POST" and table=="rpc/sales_edit_event":
            if st.session_state.get("fixture_conflict"):return False
            for row in st.session_state["fixture_events"]:
                if row["id"]==body["p_id"] and row["revision"]==body["p_revision"]:
                    row.update(body["p_data"]);row["revision"]+=1
                    st.session_state["fixture_writes"].append(deepcopy(body));return True
            return False
        if method=='POST' and table=='rpc/sales_save_report':
            from modules.shared.hwarang_auth import HwarangAuthError
            from uuid import uuid4
            if st.session_state.get('fixture_conflict'):raise HwarangAuthError('저장 충돌')
            row=next((r for r in st.session_state['fixture_reports'] if r['owner']==self.uid and r['period']==body['p_period'] and r['day']==body['p_day']),None)
            draft=next((r for r in st.session_state['fixture_drafts'] if row and r['report']==row['id']),None)
            if (row or {}).get('revision',0)!=body['p_base_revision'] or (draft or {}).get('revision',0)!=body['p_draft_revision']:raise HwarangAuthError('저장 충돌')
            if row and row['submitted'] and not body['p_submit']:
                draft=dict(id=(draft or {}).get('id',str(uuid4())),report=row['id'],owner=self.uid,data=deepcopy(body['p_data']),base_revision=row['revision'],revision=(draft or {}).get('revision',0)+1)
                st.session_state['fixture_drafts']=[r for r in st.session_state['fixture_drafts'] if r['report']!=row['id']]+[draft]
            else:
                row=dict(id=(row or {}).get('id',str(uuid4())),owner=self.uid,day=body['p_day'],period=body['p_period'],submitted=body['p_submit'],data=deepcopy(body['p_data']),revision=(row or {}).get('revision',0)+1,changed_at='2026-11-06T00:00:00Z')
                st.session_state['fixture_reports']=[r for r in st.session_state['fixture_reports'] if r['id']!=row['id']]+[row]
                st.session_state['fixture_drafts']=[r for r in st.session_state['fixture_drafts'] if r['report']!=row['id']];draft=None
            st.session_state['fixture_writes'].append(deepcopy(body))
            return deepcopy(dict(report=row,draft=draft))
        if method=='POST' and table=='rpc/sales_check_report':
            from modules.shared.hwarang_auth import HwarangAuthError
            row=next((r for r in st.session_state['fixture_reports'] if r['id']==body['p_report']),None)
            if not row or not row['submitted'] or row['revision']!=body['p_revision']:raise HwarangAuthError('제출 버전 변경')
            st.session_state['fixture_checks']=[c for c in st.session_state['fixture_checks'] if c['report']!=row['id']]+[dict(report=row['id'],reviewer=self.uid,report_revision=row['revision'])]
            st.session_state['fixture_writes'].append(deepcopy(body));return True
        if method=="GET":
            rows=st.session_state["fixture_events"] if table=="sales_events" else st.session_state["fixture_reports"] if table=="sales_reports" else st.session_state["fixture_reviews"] if table=="sales_reviews" else st.session_state["fixture_drafts"] if table=="sales_report_drafts" else st.session_state["fixture_checks"] if table=="sales_report_checks" else []
            for k,v in (params or {}).items():
                if str(v).startswith("eq."):rows=[r for r in rows if str(r.get(k)).lower()==str(v)[3:].lower()]
            if table=="sales_reviews":rows=[r for r in rows if not r.get("deleted_at")]
            if table=="sales_events":
                trash=(params or {}).get("deleted_at", "is.null")!="is.null"
                rows=[r for r in rows if bool(r.get("deleted_at"))==trash]
            return deepcopy(rows)
        if method=="POST" and table=="rpc/sales_delete_event":
            st.session_state['fixture_events']=[r for r in st.session_state['fixture_events'] if not (r['id']==body['p_id'] and r['owner']==self.uid)]
            st.session_state['fixture_writes'].append(deepcopy(body));return 1
        if method=="POST" and table=="sales_reviews":
            if not any(r['id']==body['id'] for r in st.session_state['fixture_reviews']):
                st.session_state['fixture_reviews'].append({**deepcopy(body),'reviewer':UID,'edit_version':1,'created_at':'2026-11-09T00:00:00Z','updated_at':None,'deleted_at':None})
        if method=="PATCH" and table=="sales_reviews":
            for r in st.session_state['fixture_reviews']:
                if r['id']==params['id'][3:] and r['reviewer']==UID and r['edit_version']==int(params['edit_version'][3:]):
                    r.update(body);r['edit_version']+=1;r['updated_at']='2026-11-09T01:00:00Z';return [deepcopy(r)]
            return []
        if method=="POST" and table=="sales_events":
            existing={r["id"] for r in st.session_state["fixture_events"]}
            for row in body if isinstance(body,list) else [body]:
                if row["id"] not in existing:
                    st.session_state["fixture_events"].append({**deepcopy(row),"owner":UID,"revision":1,"case_id":None})
        st.session_state["fixture_writes"].append(deepcopy(body))
        return []
    def period(self,table,start,end,**params):
        return [r for r in self.request("GET",table,params) if str(start)<=r["day"]<=str(end)]
    def save(self,table,body,old=None):
        if st.session_state.get("fixture_conflict"):
            from modules.shared.hwarang_auth import HwarangAuthError
            raise HwarangAuthError("다른 화면에서 먼저 수정했습니다.")
        row={**deepcopy(body),"owner":UID,"revision":old["revision"]+1 if old else 1,"changed_at":"2026-11-06T00:00:00+00:00"}
        row.setdefault("id",old["id"] if old else "new")
        st.session_state["fixture_reports"]=[r for r in st.session_state["fixture_reports"] if r["id"]!=row["id"]]+[row]
        st.session_state["fixture_writes"].append(deepcopy(body))
