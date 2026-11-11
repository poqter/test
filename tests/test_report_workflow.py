from datetime import date
from modules.activity.record_editor import weekly_source, merge_source, values_from, day_states
from modules.activity.weekly_review import review_state
from modules.shared.organization_picker import manager_candidates
from test_activity_redesign import app, button, number, text


def test_weekly_summary_uses_daily_submissions_without_writes():
    at=app('''db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='daily',day='2026-11-03',period='일일',submitted=True,data={'counts':{'AP':3},'note':'일일 성과'}))
 st.session_state['fixture_writes']=[]
redesign.reports(db,date(2026,11,6),'주간')
''')
    assert not at.exception
    assert not at.number_input
    assert not any(b.label=='제출하기' for b in at.button)
    assert at.dataframe[0].value.iloc[-1]['AP']==3
    assert not at.session_state['fixture_writes']


def test_weekend_leave_and_future_not_missing():
    events=[dict(day='2026-11-03',kind='휴무',status='예정',start_time=None)]
    statuses={str(d):s for d,s,_ in day_states(date(2026,11,2),date(2026,11,7),[],events)}
    assert statuses['2026-11-03']==statuses['2026-11-07']=='대상 아님'
    assert statuses['2026-11-08']=='예정' and statuses['2026-11-02']=='미작성'


def test_review_is_bound_to_reviewer_and_revision():
    row=dict(id='r',revision=2,submitted=True)
    checks=[dict(report='r',reviewer='me',report_revision=1)]
    assert review_state(row,checks,'me')=='재검토 필요'
    assert review_state(row,checks,'other')=='검토 대기'
    checks[0]['report_revision']=2
    assert review_state(row,checks,'me')=='확인 완료'
    assert review_state(dict(row,submitted=False),checks,'me')=='미제출'


def test_manager_picker_excludes_self_other_branch_wrong_role_inactive():
    rows=[dict(id='a',organization_unit_id='u',position_code='team_leader'),dict(id='self',organization_unit_id='u',position_code='team_leader'),dict(id='b',organization_unit_id='other',position_code='team_leader'),dict(id='c',organization_unit_id='u',position_code='deputy_branch_manager'),dict(id='d',organization_unit_id='u',position_code='team_leader',is_active=False)]
    assert set(manager_candidates(rows,'u','self','team_leader'))=={'a'}
    assert set(manager_candidates(rows,'u','self','deputy_branch_manager'))=={'c'}


def test_weekly_summary_uses_submitted_daily_values_without_second_submission():
    at=app('''db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='daily',day='2026-11-03',period='일일',submitted=True,data={'counts':{'AP':3},'note':'일일 성과'}))
 st.session_state['fixture_writes']=[]
redesign.reports(db,date(2026,11,6),'주간')
''')
    assert not at.exception
    assert not at.number_input
    assert at.dataframe[0].value.iloc[-1]['AP']==3
    assert not at.session_state['fixture_writes']
    assert not any(b.label=='제출하기' for b in at.button)


def test_manager_open_is_read_only_then_check_records_revision():
    at=app('''from modules.activity.weekly_review import render
from activity_fixture import OTHER
db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='week',day='2026-11-02',period='일일',submitted=True,data={'counts':{'TA':4},'help':'동행 요청'}))
 st.session_state['fixture_reports'][0]['owner']=OTHER
 st.session_state['fixture_writes']=[]
render(db,date(2026,11,6))
''')
    assert not at.exception
    button(at,'테스트 구성원 · 검토 대기 · 지원 요청').click().run()
    assert not at.exception and not at.session_state['fixture_writes']
    button(at,'확인 완료').click().run()
    assert not at.exception and len(at.session_state['fixture_checks'])==1
    assert button(at,'피드백 저장')
    row=at.session_state['fixture_reports'][0];row['revision']+=1
    at.run()
    assert not button(at,'확인 완료').disabled
    assert any('재검토 필요' in c.value for c in at.caption)
