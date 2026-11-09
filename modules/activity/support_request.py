"""Single recipient support requests, using server-validated reporting links."""
import streamlit as st
from modules.activity import ux
LABELS={'team_leader':'팀장','deputy_branch_manager':'부지점장','branch_manager':'지점장'}

def recipients(db):
    return {r['member']:LABELS.get(r['role_code'],r['role_code'])+' '+r['label'] for r in db.request('POST','rpc/sales_support_recipients',body={})}

def picker(db,d,after_change=None):
    options=recipients(db)
    chosen=d['values'].get('help_recipient')
    if chosen not in options:
        replacement=next(iter(options)) if len(options)==1 else None
        ux.set_values(d,{'help_recipient':replacement})
        # Automatic defaults are not user edits; preserve other unsaved fields.
        if chosen==d['baseline'].get('help_recipient'):
            d['baseline']['help_recipient']=replacement
    if not options:st.caption('연결된 요청 대상이 없습니다. 담당 관리자 연결을 확인해 주세요.')
    ux.field(d,'help_recipient',st.selectbox,'지원 요청 대상',options=[None,*options],format_func=lambda u:options.get(u,'관리자를 선택하세요'),after_change=after_change,disabled=not options)
