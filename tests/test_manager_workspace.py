from test_activity_redesign import app, button, text

REVIEW='''from modules.activity.weekly_review import render
from activity_fixture import OTHER
db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='week',day='2026-11-02',period='주간',submitted=True,data={'counts':{'TA':4},'note':'제출 본문'}))
 st.session_state['fixture_reports'][0]['owner']=OTHER
 st.session_state['fixture_writes']=[]
render(db,date(2026,11,6))
'''

def test_feedback_draft_survives_employee_navigation_and_explicit_check():
    at=app(REVIEW)
    assert not at.exception
    text(at,'피드백 · 선택').input('다음 주 상담 확인').run()
    assert not at.session_state['fixture_writes']
    button(at,'테스트 작성자 · 미제출').click().run()
    assert not any(b.label.startswith('확인 완료') for b in at.button)
    button(at,'테스트 구성원 · 검토 대기').click().run()
    assert text(at,'피드백 · 선택').value=='다음 주 상담 확인'
    button(at,'확인 완료').click().run()
    assert not at.exception
    assert len(at.session_state['fixture_checks'])==1
    assert any(w for w in at.session_state['fixture_writes'])


def test_unsubmitted_daily_draft_is_not_exposed():
    at=app('''from modules.activity.weekly_review import render
from activity_fixture import OTHER
db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='draft',day='2026-11-06',period='일일',submitted=False,data={'counts':{'TA':99},'note':'PRIVATE_DRAFT'}))
 st.session_state['fixture_reports'][0]['owner']=OTHER
 st.session_state['fixture_writes']=[]
st.session_state['manager_selected']=OTHER
render(db,date(2026,11,6))
''')
    assert not at.exception
    assert not any('PRIVATE_DRAFT' in str(x.value) for x in at.markdown)
    assert not any(b.label.startswith('확인 완료') for b in at.button)
    assert not at.session_state['fixture_writes']


def test_shared_search_and_employee_survive_tab_switch():
    at=app('from modules.activity.manager import render\nrender(FakeRecords(),date(2026,11,6))')
    next(t for t in at.text_input if t.label=='직원 이름 검색').input('구성원').run()
    selected=at.session_state['manager_selected']
    next(t for t in at.segmented_control if t.label=='관리 화면').set_value('주간 기록 검토').run()
    assert not at.exception
    assert next(t for t in at.text_input if t.label=='직원 이름 검색').value=='구성원'
    assert at.session_state['manager_selected']==selected

def test_failed_check_retains_feedback_and_retry_does_not_duplicate():
    code=REVIEW.replace('db=FakeRecords()', '''from modules.shared.hwarang_auth import HwarangAuthError
class Failing(FakeRecords):
 def request(self,method,table,params=None,body=None,prefer=None):
  if table=='rpc/sales_check_report' and not st.session_state.get('failed_once'):
   st.session_state['failed_once']=True
   raise HwarangAuthError('temporary failure')
  return super().request(method,table,params,body,prefer)
db=Failing()''')
    at=app(code)
    text(at,'피드백 · 선택').input('재시도할 피드백').run()
    button(at,'확인 완료').click().run()
    assert not at.exception and at.error
    assert text(at,'피드백 · 선택').value=='재시도할 피드백'
    assert len(at.session_state['fixture_reviews'])==1
    assert not at.session_state['fixture_checks']
    button(at,'확인 완료').click().run()
    assert not at.exception
    assert len(at.session_state['fixture_reviews'])==1
    assert len(at.session_state['fixture_checks'])==1
