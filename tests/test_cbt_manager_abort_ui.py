from streamlit.testing.v1 import AppTest


APP = '''
from datetime import datetime, timedelta, timezone
from hwarang_academy.exams import ui
now = datetime.now(timezone(timedelta(hours=9))).replace(hour=12, minute=0, second=0, microsecond=0)
def record(id, status, offset):
    started = (now - timedelta(minutes=offset)).isoformat()
    r = {'id':id, 'user_id':'one', 'title':id, 'mode':'exam', 'status':status,
         'started_at':started, 'updated_at':started, 'result':None}
    if status == 'submitted':
        r['submitted_at'] = started
        r['result'] = {'sections':[{'name':'손해','score':80,'passed':True}]}
    return r
class Repo:
    def call(self, action, **kwargs):
        if action == 'team': return [record('중단 시험','aborted',1), record('완료 시험','submitted',10)]
        if action == 'roster': return [
            {'id':'one','display_name':'학습자','organization_name':'팀','groups':[]},
            {'id':'two','display_name':'미참여자','organization_name':'팀','groups':[]}]
        raise AssertionError(action)
ui._dashboard(Repo(), {'role':'user','position_code':'team_leader'})
'''


def test_manager_can_filter_and_identify_aborted_attempts():
    app = AppTest.from_string(APP).run()
    assert not app.exception
    assert any('학습 완료 · 최근 시험 중단' in c.value for c in app.caption)
    assert any(m.label == '참여 인원' and m.value == '1' for m in app.metric)
    app.selectbox(key='_academy_exam_filter').select('중단 이력 있음').run()
    assert not app.exception
    assert any(b.label == '학습자 →' for b in app.button)
    assert not any(b.label == '미참여자 →' for b in app.button)
    next(b for b in app.button if b.label == '학습자 →').click().run()
    assert not app.exception
    assert any(' · 중단' in c.value for c in app.caption)
    assert any(' · 완료' in c.value for c in app.caption)
    assert next(b for b in app.button if b.key == 'manager_중단 시험').disabled
