from datetime import date
from test_activity_redesign import app, button, text, number
from modules.activity.daily import COUNTS

TAIL='redesign.reports(FakeRecords(),date(2026,11,6),"일일")'


def test_eight_independent_fields_and_legacy_counts_survive_edit():
    seed='''db=FakeRecords()
if not st.session_state['fixture_reports']:
    db.save('sales_reports',dict(id='old',period='일일',day='2026-11-06',submitted=False,data={'counts':{'전화':12,'메시지':4,'상담':3},'extra':'preserve','plan':'기존 계획'}))
'''
    at=app(seed+TAIL)
    assert [n.label for n in at.number_input]==COUNTS
    number(at,'AP').set_value(2).run()
    number(at,'PC').set_value(5).run()
    assert number(at,'상담').value==3 and number(at,'제안').value==0
    button(at,'임시 저장').click().run()
    assert not at.exception
    data=at.session_state['fixture_reports'][0]['data']
    assert data['counts']['전화']==12 and data['counts']['메시지']==4
    assert data['counts']['AP']==2 and data['counts']['PC']==5
    assert data['extra']=='preserve' and data['plan']=='기존 계획'


def test_failed_save_and_date_move_keep_input_then_retry():
    at=app('st.session_state.setdefault("fixture_conflict",True)\n'+TAIL)
    text(at,'주요 성과 · 진행사항').input('보존할 내용').run()
    at.date_input[0].set_value(date(2026,11,5)).run()
    button(at,'저장 후 이동').click().run()
    assert not at.exception and at.error
    assert at.session_state['sales_report_active_일일']=='2026-11-06'
    assert text(at,'주요 성과 · 진행사항').value=='보존할 내용'
    assert not at.session_state['fixture_writes']
    at.session_state['fixture_conflict']=False
    button(at,'저장 후 이동').click().run()
    assert not at.exception
    assert at.session_state['fixture_reports'][0]['data']['note']=='보존할 내용'
    assert at.session_state['sales_report_active_일일']=='2026-11-05'


def test_zero_confirmation_and_duplicate_submit_disabled():
    at=app(TAIL)
    button(at,'제출하기').click().run()
    assert not at.session_state['fixture_writes']
    button(at,'활동 없는 날로 제출').click().run()
    assert not at.exception
    assert at.session_state['fixture_reports'][0]['data']['no_activity'] is True
    assert button(at,'수정 내용 제출').disabled
    at.run()
    assert len(at.session_state['fixture_writes'])==1
    number(at,'TA').set_value(1).run()
    button(at,'수정 내용 제출').click().run()
    button(at,'제출 확인').click().run()
    assert not at.exception and not at.session_state['fixture_reports'][0]['data']['no_activity']
    assert at.session_state['fixture_reports'][0]['revision']==2


def test_discard_date_change_preserves_saved_record():
    at=app(TAIL)
    text(at,'주요 성과 · 진행사항').input('저장됨').run()
    button(at,'임시 저장').click().run()
    text(at,'주요 성과 · 진행사항').input('버릴 수정').run()
    at.date_input[0].set_value(date(2026,11,5)).run()
    button(at,'저장하지 않고 이동').click().run()
    at.date_input[0].set_value(date(2026,11,6)).run()
    assert not at.exception and text(at,'주요 성과 · 진행사항').value=='저장됨'


def test_mobile_reference_roundtrip_keeps_counts_and_notes():
    tail='''redesign.ux.compact=lambda:True
'''+TAIL
    at=app(tail)
    number(at,'AP').set_value(9).run()
    text(at,'주요 성과 · 진행사항').input('탭 이동 보존').run()
    next(s for s in at.segmented_control if s.label=='일일 기록 화면').set_value('오늘 일정').run()
    assert not at.exception and not at.number_input
    next(s for s in at.segmented_control if s.label=='일일 기록 화면').set_value('기록 작성').run()
    assert not at.exception
    assert number(at,'AP').value==9 and text(at,'주요 성과 · 진행사항').value=='탭 이동 보존'


def test_schedule_import_keeps_ap_pc_independent_and_is_repeat_safe():
    at=app('''db=FakeRecords()
st.session_state['fixture_events'][0]['status']='완료'
st.session_state.setdefault('report:'+UID+':일일:2026-11-06source_panel',True)
'''+TAIL)
    assert not at.exception
    button(at,'이 집계 초안 반영').click().run()
    assert not at.exception
    assert number(at,'AP').value==1 and number(at,'상담').value==0
    number(at,'AP').set_value(7).run()
    button(at,'이 집계 초안 반영').click().run()
    assert not at.exception
    assert number(at,'AP').value==7 and number(at,'상담').value==0
