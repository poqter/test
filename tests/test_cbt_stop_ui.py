from streamlit.testing.v1 import AppTest

APP='''
import streamlit as st
from hwarang_academy.exams import ui
class Repo:
 def __init__(self,*args):pass
 def call(self,action,**kw):
  if action=='list':return [{'id':'a','title':'시험','status':'active'}]
  if action=='get':return {'id':'a','status':'active','revision':2}
  if action=='abort':
   st.session_state['aborted']=True
   return {'id':'a','status':'aborted'}
  return []
ui.Repository=Repo
ui.render(None,'user',{'academy.assessment'},{'role':'user','position_code':'fp'})
'''
def test_native_tabs_and_abort_confirmation():
 app=AppTest.from_string(APP).run()
 assert not app.exception
 assert [t.label for t in app.tabs]==['시험 시작','나의 응시 기록']
 next(b for b in app.button if b.label=='시험 중단 · 새 시험 선택').click().run()
 assert not app.exception
 next(b for b in app.button if b.label=='시험 중단 확정').click().run()
 assert not app.exception
 assert app.session_state['aborted']
 assert any('중단했습니다' in x.value for x in app.success)
