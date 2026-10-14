from pathlib import Path
from streamlit.testing.v1 import AppTest
at=AppTest.from_file(str(Path(__file__).with_name('harness.py')),default_timeout=10).run()
assert not at.exception,at.exception
print('SETUP',[(x.label,x.value) for x in at.radio])
next(b for b in at.button if b.label=='고객 만나기 →').click().run()
assert not at.chat_input
assert any('오늘 만날 고객' in t.value for t in at.title)
next(b for b in at.button if b.label=='대화 시작').click().run()
assert not at.exception,at.exception
print('SESSION',len(at.chat_message))
at.chat_input[0].set_value('안녕하세요. 어떤 점이 가장 걱정되세요?').run()
assert not at.exception,at.exception
assert len(at.chat_message)==3
next(b for b in at.button if b.label.startswith('힌트 준비')).click().run()
assert not at.exception,at.exception
assert any('걱정을 먼저 확인하세요' in x.value for x in at.markdown)
at.chat_input[0].set_value('네 오늘 상담은 이렇게 마치겠습니다').run()
assert len(at.chat_input)==0
assert not at.exception,at.exception
next(b for b in at.button if b.label.startswith('근거 기반 피드백')).click().run()
assert not at.exception,at.exception
next(b for b in at.button if b.label=='이 장면에서 다시 답하기').click().run()
assert not at.exception,at.exception
assert len(at.chat_message)==1
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
assert not any('보험 증권' in b.label for b in at.button)
at.chat_input[0].set_value('증권을 보여주시겠어요?').run()
assert any('보험 증권' in b.label for b in at.button)
at.chat_input[0].set_value('새로 가입하시면 어때요?').run()
at.toggle[0].set_value(True).run()
assert any('관찰 ·' in m.value for m in at.caption)
at.chat_input[0].set_value('오늘 상담은 여기까지 하겠습니다.').run()
assert not at.chat_input and any(b.label=='이 장면 다시 연습' for b in at.button)
next(b for b in at.button if b.label=='이 장면 다시 연습').click().run()
assert not any(e.label=='이전 답변과 이번 답변 비교' for e in at.expander)
at.chat_input[0].set_value('어떤 점이 부담스러우세요?').run()
assert any(e.label=='이전 답변과 이번 답변 비교' for e in at.expander)
assert not at.exception
print('UI PASS: intro/document-card/optional-signals/moment-retry/comparison')
