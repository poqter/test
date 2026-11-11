"""One visible-page subscription; no timer-driven Python reruns when unchanged."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

monitor=components.declare_component('activity_monitor',path=str(Path(__file__).with_name('activity_monitor')))

def attach(db,start,end,owner=None):
    if not getattr(db,'fast_calendar',False):return
    args={'p_first':str(start),'p_last':str(end),'p_owner':owner}
    value=st.session_state.get('activity_live_monitor')
    previous=st.session_state.get('activity_live_ack')
    if isinstance(value,dict) and value.get('nonce')!=previous:
        st.session_state['activity_live_ack']=value['nonce']
        db._reads.clear();db._activity_bundle=None
        if value.get('scope'):
            from modules.activity import read_state
            read_state.invalidate();st.session_state.pop('sales_period_cache',None)
            st.rerun(scope='app')
    stamp=db.request('POST','rpc/sales_activity_stamp',body=args)
    monitor(url=db.auth.config.url,apiKey=db.auth.config.publishable_key,token=db.token,uid=db.uid,
            viewScope=getattr(db,'view_scope','daily'),first=str(start),last=str(end),owner=owner,
            stamp=stamp,ack=st.session_state.get('activity_live_ack'),key='activity_live_monitor',default=None)
