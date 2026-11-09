from datetime import date
from modules.activity.record_editor import weekly_source, merge_source, values_from, day_states
from modules.activity.weekly_review import review_state
from modules.shared.organization_picker import manager_candidates
from test_activity_redesign import app, button, number, text


def test_weekly_import_uses_submitted_records_and_preserves_manual_fields():
    rows=[dict(id='a',day='2026-11-02',revision=2,submitted=True,data={'counts':{'AP':3},'note':'성과'}),dict(id='b',day='2026-11-03',revision=1,submitted=False,data={'counts':{'AP':99}})]
    source=weekly_source(rows)
    assert source['AP']==3 and source['coverage']==['2026-11-02'] and source['source_versions']=={'a':2}
    values=values_from({'counts':{'AP':10},'note':'직접 작성','manual_fields':['AP','note']})
    merged=merge_source(values,source)
    assert 'AP' not in merged and 'note' not in merged and merged['PC']==0
    assert source['note']=='11-02 · 성과'


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


def test_weekly_import_requires_click_and_never_overwrites_manual_values():
    at=app('''db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='daily',day='2026-11-03',period='일일',submitted=True,data={'counts':{'AP':3},'note':'일일 성과'}))
redesign.reports(db,date(2026,11,6),'주간')
''')
    assert not at.exception and number(at,'AP').value==0
    button(at,'일일 기록에서 초안 가져오기').click().run()
    assert not at.exception and number(at,'AP').value==3
    number(at,'AP').set_value(8).run()
    text(at,'주요 성과 · 진행사항').input('직접 수정').run()
    button(at,'일일 기록에서 초안 가져오기').click().run()
    assert not at.exception and number(at,'AP').value==8 and text(at,'주요 성과 · 진행사항').value=='직접 수정'


def test_manager_open_is_read_only_then_check_records_revision():
    at=app('''from modules.activity.weekly_review import render
from activity_fixture import OTHER
db=FakeRecords()
if not st.session_state['fixture_reports']:
 db.save('sales_reports',dict(id='week',day='2026-11-02',period='주간',submitted=True,data={'counts':{'TA':4},'help':'동행 요청'}))
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
