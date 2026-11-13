from pathlib import Path
from uuid import uuid4
from streamlit.testing.v1 import AppTest
def send(at,text):
    model=at.session_state['_test_chat_model']
    assert not model['disabled']
    at.session_state['_test_chat_event']={'kind':'send','event_id':uuid4().hex,'version':model['version'],'text':text}
    at.run()

at=AppTest.from_file(str(Path(__file__).with_name('harness.py')),default_timeout=10).run()
assert not at.exception,at.exception
print('SETUP',[(x.label,x.value) for x in at.radio])
next(b for b in at.button if b.label=='고객 만나기 →').click().run()
assert not at.chat_input
assert any('오늘 만날 고객' in t.value for t in at.title)
next(b for b in at.button if b.label=='대화 시작').click().run()
assert not at.exception,at.exception
print('SESSION',len(at.session_state['_test_chat_model']['messages']))
send(at,'안녕하세요. 어떤 점이 가장 걱정되세요?')
assert not at.exception,at.exception
assert len(at.session_state['_test_chat_model']['messages'])==3
next(b for b in at.button if b.label.startswith('힌트 준비')).click().run()
assert not at.exception,at.exception
assert any('걱정을 먼저 확인하세요' in x.value for x in at.markdown)
send(at,'네 오늘 상담은 이렇게 마치겠습니다')
assert at.session_state['_studio_state']['ended']
assert not at.exception,at.exception
next(b for b in at.button if b.label.startswith('근거 기반 피드백')).click().run()
assert not at.exception,at.exception
next(b for b in at.button if b.label=='이 장면에서 다시 답하기').click().run()
assert not at.exception,at.exception
assert len(at.session_state['_test_chat_model']['messages'])==1
print('UI PASS: setup/start/send/hint/end/evaluate/retrain')

at=AppTest.from_file(str(Path(__file__).with_name('harness.py')),default_timeout=10).run()
next(r for r in at.radio if r.label=='연습 방식').set_value('ASSESSMENT')
next(b for b in at.button if b.label=='고객 만나기 →').click().run()
assert not at.chat_input
assert any('오늘 만날 고객' in t.value for t in at.title)
next(b for b in at.button if b.label=='대화 시작').click().run()
assert not at.exception
assert not any(b.label.startswith('힌트 준비') for b in at.button)
next(r for r in at.radio if r.label=='대화 방식').set_value('음성').run()
assert not at.exception
assert any(b.label.startswith('고객 목소리 미리듣기') for b in at.button)
next(r for r in at.radio if r.label=='대화 방식').set_value('텍스트').run()
assert not at.exception
print('UI PASS: formal-no-hint/voice-controls/mode-switch')

# Immersion regression: optional evidence-only signals, document card, result moment comparison.
at=AppTest.from_file(str(Path(__file__).with_name('harness.py')),default_timeout=10).run()
next(r for r in at.radio if r.label=='훈련 장면').set_value('FIRST').run()
next(b for b in at.button if b.label=='고객 만나기 →').click().run()
next(b for b in at.button if b.label=='대화 시작').click().run()
assert not at.exception
assert not at.table
send(at,'증권을 보여주시겠어요?')
assert at.table
send(at,'새로 가입하시면 어때요?')
at.toggle[0].set_value(True).run()
assert at.session_state['_test_chat_model']['signals']
send(at,'오늘 상담은 여기까지 하겠습니다.')
assert at.session_state['_studio_state']['ended'] and any(b.label=='이 장면 다시 연습' for b in at.button)
next(b for b in at.button if b.label=='이 장면 다시 연습').click().run()
assert not any(e.label=='이전 답변과 이번 답변 비교' for e in at.expander)
send(at,'어떤 점이 부담스러우세요?')
assert any(e.label=='이전 답변과 이번 답변 비교' for e in at.expander)
assert not at.exception
print('UI PASS: intro/document-card/optional-signals/moment-retry/comparison')
