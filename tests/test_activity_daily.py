from textwrap import dedent
from datetime import date
from test_activity_redesign import app, button, text, number
from modules.activity.daily import COUNTS

TAIL='redesign.reports(FakeRecords(),date(2026,11,6),"일일")'


def test_six_independent_fields_and_legacy_counts_survive_edit():
    seed='''db=FakeRecords()
if not st.session_state['fixture_reports']:
    db.save('sales_reports',dict(id='old',period='일일',day='2026-11-06',submitted=False,data={'counts':{'전화':12,'메시지':4,'상담':3,'제안':4},'extra':'preserve','plan':'기존 계획'}))
'''
    at=app(seed+TAIL)
    assert [n.label for n in at.number_input]==COUNTS
    number(at,'AP').set_value(2).run()
    number(at,'PC').set_value(5).run()
    assert not {'상담','제안'} & {n.label for n in at.number_input}
    button(at,'임시 저장').click().run()
    assert not at.exception
    data=at.session_state['fixture_reports'][0]['data']
    assert data['counts']['전화']==12 and data['counts']['메시지']==4
    assert data['counts']['AP']==2 and data['counts']['PC']==5
    assert data['counts']['상담']==3 and data['counts']['제안']==4
    assert data['extra']=='preserve' and data['plan']=='기존 계획'


def test_failed_save_and_date_move_keep_input_then_retry():
    at=app('st.session_state.setdefault("fixture_conflict",True)\n'+TAIL)
    text(at,'주요 성과 · 진행사항').input('보존할 내용').run()
    at.date_input[0].set_value(date(2026,11,5)).run()
    assert not at.exception and at.error
    assert at.session_state['sales_report_active_일일']=='2026-11-06'
    assert text(at,'주요 성과 · 진행사항').value=='보존할 내용'
    assert not at.session_state['fixture_writes']
    at.session_state['fixture_conflict']=False
    at.run()
    assert not at.exception
    assert at.session_state['fixture_reports'][0]['data']['note']=='보존할 내용'
    assert at.session_state['sales_report_active_일일']=='2026-11-05'


def test_zero_requires_explicit_choice_and_submission_is_one_click():
    at=app(TAIL)
    button(at,'제출하기').click().run()
    assert not at.session_state['fixture_writes'] and at.error
    next(c for c in at.checkbox if c.label=='활동 없는 날').check().run()
    button(at,'제출하기').click().run()
    assert not at.exception
    assert at.session_state['fixture_reports'][0]['data']['no_activity'] is True
    assert button(at,'수정 내용 제출').disabled
    old_revision=at.session_state['fixture_reports'][0]['revision']
    number(at,'TA').set_value(1).run()
    assert at.session_state['fixture_reports'][0]['data']['counts']['TA']==0
    assert at.session_state['fixture_drafts'][0]['data']['counts']['TA']==1
    button(at,'수정 내용 제출').click().run()
    assert not at.exception and not at.session_state['fixture_reports'][0]['data']['no_activity']
    assert at.session_state['fixture_reports'][0]['revision']==old_revision+1
    assert not at.session_state['fixture_drafts']


def test_date_change_returns_to_automatically_saved_record():
    at=app(TAIL)
    text(at,'주요 성과 · 진행사항').input('저장됨').run()
    at.date_input[0].set_value(date(2026,11,5)).run()
    at.date_input[0].set_value(date(2026,11,6)).run()
    assert not at.exception and text(at,'주요 성과 · 진행사항').value=='저장됨'
    assert at.session_state['fixture_reports'][0]['data']['note']=='저장됨'


def test_mobile_reference_roundtrip_keeps_counts_and_notes():
    at=app('original=redesign.ux.compact\nredesign.ux.compact=lambda:True\ntry: '+TAIL+'\nfinally: redesign.ux.compact=original')
    number(at,'AP').set_value(9).run()
    text(at,'주요 성과 · 진행사항').input('보존').run()
    panel=next(e for e in at.expander if e.label=='일정·집계·참고 자료')
    assert not at.exception and panel is not None
    assert number(at,'AP').value==9 and text(at,'주요 성과 · 진행사항').value=='보존'


def test_schedule_import_keeps_ap_pc_independent_and_is_repeat_safe():
    at=app("db=FakeRecords()\nst.session_state['fixture_events'][0]['status']='완료'\n"+TAIL)
    button(at,'집계값 가져오기').click().run()
    assert not at.exception and number(at,'AP').value==1
    number(at,'AP').set_value(7).run()
    button(at,'집계값 가져오기').click().run()
    assert not at.exception and number(at,'AP').value==7


def test_weekly_excludes_retired_metrics_and_preserves_saved_history():
    seed='''db=FakeRecords()
if not st.session_state['fixture_reports']:
    db.save('sales_reports',dict(id='week',period='주간',day='2026-11-02',submitted=False,data={'counts':{'AP':2,'PC':1,'상담':9,'제안':8}}))
    db.save('sales_reports',dict(id='day',period='일일',day='2026-11-03',submitted=True,data={'counts':{'AP':3,'PC':4,'상담':20,'제안':30}}))
redesign.reports(db,date(2026,11,6),'주간')
'''
    at=app(seed)
    assert not at.exception
    values=[m.value for m in at.markdown]
    assert not any(m.startswith(('상담 **','제안 **')) for m in values)
    assert not at.number_input
    frame=at.dataframe[0].value
    assert frame.iloc[-1]['AP']==3 and frame.iloc[-1]['PC']==4
    week=next(r for r in at.session_state['fixture_reports'] if r['period']=='주간')
    assert week['data']['counts']=={'AP':2,'PC':1,'상담':9,'제안':8}
    assert any(e.label=='이전 주간 제출 기록 · 보관' for e in at.expander)


def test_lost_save_response_is_reconciled_and_submit_retry_stays_submit():
    seed = '''
    from modules.shared.hwarang_auth import HwarangAuthError
    class LostReplyRecords(FakeRecords):
        def request(self, method, table, *args, **kwargs):
            if table == 'rpc/sales_save_report' and st.session_state.get('failure') == 'before':
                st.session_state['failure'] = None
                raise HwarangAuthError('offline', code='transport_error')
            result = super().request(method, table, *args, **kwargs)
            if table == 'rpc/sales_save_report' and st.session_state.get('failure') == 'after':
                st.session_state['failure'] = None
                raise HwarangAuthError('offline', code='transport_error')
            return result
    redesign.reports(LostReplyRecords(), date(2026,11,6), '일일')
    '''
    at=app(dedent(seed))
    number(at,'AP').set_value(7).run()
    at.session_state['failure']='after'
    button(at,'제출하기').click().run()
    assert not at.error and at.session_state['fixture_reports'][0]['submitted']
    revision=at.session_state['fixture_reports'][0]['revision']
    at.session_state['failure']='after'
    number(at,'AP').set_value(9).run()
    assert not at.error and at.session_state['fixture_drafts'][0]['data']['counts']['AP']==9
    at.session_state['failure']='before'
    button(at,'수정 내용 제출').click().run()
    assert any('처리 결과 미확인' in e.value for e in at.error)
    assert at.session_state['fixture_reports'][0]['revision']==revision
    button(at,'다시 제출').click().run()
    assert not at.error and not at.exception
    row=at.session_state['fixture_reports'][0]
    assert row['revision']==revision+1 and row['data']['counts']['AP']==9 and row['submitted']
