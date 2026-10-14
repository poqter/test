from pathlib import Path
from streamlit.testing.v1 import AppTest
path=str(Path(__file__).with_name('harness.py'))
a=AppTest.from_file(path,default_timeout=20).run()
assert not a.exception,a.exception
assert a.session_state['captured_payload']['portal_surface']=='academy'
def event(kind,**kw):
 a.session_state['queued_event']={'kind':kind,'event_id':str(__import__('uuid').uuid4()),**kw};a.run();assert not a.exception,a.exception
event('studio_home');assert a.session_state['captured_payload']['portal_surface']=='simulator'
event('open_studio',stage='FIRST');assert any(t.value=='나에게 맞는 훈련 준비' for t in a.title)
next(b for b in a.button if b.label=='시뮬레이터 홈').click().run();assert not a.exception
assert a.session_state['captured_payload']['portal_surface']=='simulator'
event('resume_studio');assert a.chat_input
next(b for b in a.button if b.label=='ACADEMY 홈').click().run();assert not a.exception
assert a.session_state['captured_payload']['portal_surface']=='academy'
event('open_simulator');assert a.session_state['captured_payload']['phase']=='setup'
event('academy_home');assert a.session_state['captured_payload']['phase']=='home'
b=AppTest.from_file(path,default_timeout=20);b.query_params['view']='simulator';b.run();assert not b.exception;assert b.session_state['captured_payload']['portal_surface']=='simulator';assert not b.chat_input
c=AppTest.from_file(path,default_timeout=20);c.session_state['test_permissions']=[];c.run();c.session_state['queued_event']={'kind':'studio_home','event_id':'denied'};c.run();assert not c.exception;assert c.session_state['captured_payload']['portal_surface']=='academy';assert '권한' in c.session_state['captured_payload']['error']
print('PASS actual main: Academy → simulator → setup → back → resume → Academy; legacy return; direct link; permission denial')
