from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).parents[1]
APP='''
import json, streamlit as st
from pathlib import Path
from hwarang_academy.education.onboarding import render
course=json.loads(Path('hwarang_academy/education/onboarding.json').read_text())
st.session_state.setdefault('test_works',[])
def rpc(auth,owner,name,**kw):
 if name=='work_get':return st.session_state.test_works
 if name=='team':return []
 if name=='work_save':
  lesson=next(l for l in course['lessons'] if l['id']==kw['p_lesson'])
  passed=all(kw['p_answers'].get(q['id'])==q['answer'] for q in lesson['quiz'])
  if kw['p_submit'] and not passed:return {'passed':False,'score':0}
  st.session_state.test_works=[dict(lesson_id=kw['p_lesson'],revision=1,version=kw['p_version']+1,practice=kw['p_practice'],answers=kw['p_answers'],status='submitted' if kw['p_submit'] else 'draft')]
  return {'passed':kw['p_submit']}
render(None,'learner',{'academy.new_hire'},{'role':'user','position_code':'fp'},course,rpc)
'''

def test_draft_resume_wrong_answer_and_submit(monkeypatch):
 monkeypatch.chdir(ROOT)
 app=AppTest.from_string(APP).run()
 assert not app.exception
 app.text_area[0].set_value('가상 고객의 첫 달 목표를 정리하고 계정과 권한 확인을 담당자와 진행하겠습니다.')
 next(b for b in app.button if b.label=='작성 중 저장').click().run()
 assert not app.exception
 assert app.text_area[0].value.startswith('가상 고객')
 quiz=next(r for r in app.radio if '계정 준비가' in r.label)
 quiz.set_value(1)
 app.checkbox[0].check()
 next(b for b in app.button if b.label=='확인하고 학습 완료').click().run()
 assert len(app.warning)==1 and not app.exception
 next(r for r in app.radio if '계정 준비가' in r.label).set_value(0)
 next(b for b in app.button if b.label=='확인하고 학습 완료').click().run()
 assert not app.exception
 assert not app.text_area
 assert app.metric[0].value=='1 / 30'

def test_all_lessons_render(monkeypatch):
 monkeypatch.chdir(ROOT)
 app=AppTest.from_string(APP).run()
 for day in range(1,31):
  next(s for s in app.selectbox if s.label=='학습할 일차').set_value(f'd{day:02}').run()
  assert not app.exception,day
  assert len(app.text_area)==1
