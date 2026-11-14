"""Synthetic-only local UI fixture; never authenticates against production."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from modules.shared import operations as op, operations_ui as ui
st.set_page_config(layout='wide')
st.session_state['login_profile']={'id':'synthetic','role':'super_admin'}
class Auth:
 def _require_super_admin(self,actor):return {'id':actor,'role':'super_admin'}
 def _request(self,method,path,**kw):
  if path == '/rest/v1/rpc/hwarang_studio_report_incidents':
   return []
  rows=st.session_state.setdefault('test_reviews',[])
  if method=='POST':
   row=dict(id=len(rows)+1,created_at=op.now(),**kw['json']);rows.insert(0,row);return [row]
  request=kw.get('params',{}).get('details->>request_id')
  if request:return [r for r in rows if 'eq.'+r['details']['request_id']==request]
  return rows
run=dict(id=123,workflow_id=7,run_attempt=1,name='Activity browser regression',status='completed',conclusion='failure',head_sha='a'*40,html_url='https://github.com/poqter/test/actions',created_at=op.now(),updated_at=op.now())
ui._github=lambda:dict(runs=[run],history=[run],commits=[],collected_at=op.now())
ui._details=lambda *_:dict(steps=[{'영역':'모바일','작업':'verify','단계':'Mobile browser','결과':'실패','원본 결과':'failure','시작':op.now()}],files=['tests/example.py'],truncated=False)
op.briefing_overview=lambda *_:dict(jobs=[],publications=[],runs=[],collected_at=op.now())
st.title('운영 점검 · 합성 데이터 검수')
ui.render(Auth(),'synthetic')
