from streamlit.testing.v1 import AppTest


def test_entry_reuses_initial_reads_and_invalidates_after_write():
    app=AppTest.from_string('''
import streamlit as st
from unittest.mock import patch
from types import SimpleNamespace
from modules.activity.center import Records
st.session_state['hwarang_auth']={'access_token':'test','profile':{'id':'me','role':'user'}}
calls=[]
def request(method,path,**kw):
    calls.append(path)
    if path.endswith('sales_calendar_context'):
        return {'members':[{'member':'me','managed':False,'unit':'u'}],'branch':[],
        'entry':{'day':'2026-11-10','summary':[],'empty_days':[],
        'notices':[{'id':'n','message':'notice','sales_events':None}]}}
    return []
with patch('modules.activity.center.SupabaseConfig.from_mapping',return_value=None), patch('modules.activity.center.HwarangAuthService',return_value=SimpleNamespace(http=SimpleNamespace(headers={}),_request=request)):
    db=Records()
    assert len(calls)==1
    db.request('POST','rpc/sales_calendar_days',body={'first_day':'2026-11-10','last_day':'2026-11-10'})
    db.request('GET','sales_empty_days',{'day':'eq.2026-11-10','select':'owner'})
    db.request('GET','sales_notices',{'seen':'eq.false','order':'created_at.desc','limit':'20','select':'id,message,sales_events(day,kind)'})
    assert db.request('GET','sales_notices',{'seen':'eq.false','select':'id','limit':'50'})==[{'id':'n'}]
    assert len(calls)==1
    db.request('PATCH','sales_notices',{'id':'eq.n'},body={'seen':True})
    db.request('GET','sales_notices',{'seen':'eq.false','select':'id','limit':'50'})
    assert len(calls)==3
''').run()
    assert not app.exception
