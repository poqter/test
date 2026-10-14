"""Chat presentation sends only advisor text; server owns identity, turns and credit."""
from functools import lru_cache
from pathlib import Path
import streamlit.components.v1 as components
@lru_cache(maxsize=1)
def component():
    return components.declare_component('hwarang_studio_chat_v118', path=str(Path(__file__).with_name('chat_frontend')))

def render(s, *, signals=(), ack='', error=None):
    from .domain import STAGES
    return component()(model={'session_id':s['id'],'branch':s['branch'],'version':s['version'],
        'customer_name':s['case']['public_state'].get('customer_alias','고객'),'stage_label':STAGES[s['stage']],
        'messages':s['messages'],'signals':list(signals),'disabled':bool(s['stage_complete'] or s['ended']),
        'ack':ack,'error':error},key='studio_chat_'+s['id'],default=None)
