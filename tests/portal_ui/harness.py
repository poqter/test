"""Offline integration harness runs the actual academy_app.main entrypoint."""
import sys
from pathlib import Path
from unittest.mock import patch
import streamlit as st
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import academy_app as app
from hwarang_academy.studio import ui,repository
from hwarang_academy.studio.provider import Config
from hwarang_academy.studio.domain import new_session
OWNER='00000000-0000-0000-0000-000000000001'
class Repo:
 def __init__(self,auth,owner):self.owner=owner;self.auth=auth
 def rpc(self,*a,**kw):return {}
 def rows(self):return [{'id':'existing','ended':False,'stage':'FIRST','mode':'PRACTICE','updated_at':'2026-10-14T12:00:00'}]
 def load(self,sid):return new_session(self.owner,stage='FIRST')
 def save(self,s,*a,**kw):return s
 def recipients(self):return []
 def reviews(self,*a):return []
def component(**kw):
 st.session_state['captured_payload']=kw['model']
 return st.session_state.pop('queued_event',None)
identity={'profile':{'id':OWNER,'display_name':'검수 사용자'},'feature_permissions':st.session_state.get('test_permissions',['academy.simulator'])}
with patch.object(app,'auth_service',return_value=object()),patch.object(app,'_consume_workspace_launch',return_value=identity),patch.object(app,'get_training_credit_status',return_value=None),patch.object(app,'workspace_url',return_value=''),patch.object(app,'base_url',return_value=''),patch.object(app,'initialize_history',return_value={'available':True,'rows':[],'summary':{}}),patch.object(app,'component',return_value=component),patch.object(repository,'Repository',Repo),patch.object(ui,'Repository',Repo),patch.object(Config,'from_mapping',return_value=Config(api_key='offline-test')):
 app.main()
