"""Run from repository root after npm ci --prefix tests/exams."""
from pathlib import Path
import subprocess
import requests
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[2]
TEMPLATE='''import streamlit as st
import requests
from hwarang_academy.exams.ui import render
class Auth:
 def _request(self,method,path,admin,json):
  s=requests.Session();s.trust_env=False
  r=s.post('http://127.0.0.1:8138',json=json,timeout=30);r.raise_for_status();return r.json()
st.set_page_config(layout='wide')
render(Auth(),ACTOR,{'academy.assessment'},PROFILE)
'''
def app(actor,profile):
 return AppTest.from_string(TEMPLATE.replace('ACTOR',repr(actor)).replace('PROFILE',repr(profile)),default_timeout=30).run()
def clean(a):
 assert not a.exception,list(a.exception)
 assert not a.error,[e.value for e in a.error]
def button(a,label):return next(b for b in a.button if b.label==label and not b.disabled)
p=subprocess.Popen(['node',str(ROOT/'tests/exams/ui_server.mjs')],cwd=ROOT,stdout=subprocess.PIPE,text=True)
try:
 assert p.stdout.readline().strip()=='ready'
 s=requests.Session();s.trust_env=False
 uid='00000000-0000-4000-8000-000000000001'
 def rpc(action,**payload):
  r=s.post('http://127.0.0.1:8138',json={'p_actor':uid,'p_action':action,'p_payload':payload},timeout=30);r.raise_for_status();return r.json()
 at=app(uid,{'position_code':'fp'});clean(at)
 button(at,'시작하기').click().run();clean(at);assert len(at.get('component_instance'))==1
 a=rpc('get',id=rpc('list')[0]['id']);a=rpc('save',id=a['id'],revision=a['revision'],answers={'1':2},flags=[],cursor=0);rpc('submit',id=a['id'],revision=a['revision'])
 at.run();clean(at);assert any(m.label=='미응답' for m in at.metric)
 button(at,'다음 문제 →').click().run();clean(at)
 button(at,'오답 다시 풀기').click().run();clean(at);assert rpc('list')[0]['source_kind']=='review'
 admin=app('00000000-0000-4000-8000-000000000003',{'position_code':'team_leader'})
 next(r for r in admin.radio if r.label=='메뉴').set_value('조직 학습 현황').run();clean(admin)
 next(x for x in admin.text_input if x.label=='이름 검색').set_value('사용자1').run();clean(admin)
 button(admin,'사용자1 →').click().run();clean(admin)
 button(admin,'결과 보기').click().run();clean(admin)
 button(admin,'← 학습자 목록').click().run();clean(admin)
 assert next(x for x in admin.text_input if x.label=='이름 검색').value=='사용자1'
 print('PASS selection / component mount / result / review / manager overview / person / history / result / back')
finally:
 p.terminate();p.wait(timeout=10)
