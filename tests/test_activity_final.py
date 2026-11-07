from datetime import date
from test_activity_redesign import app, button
from test_activity_panels import new_dialog


def test_discard_new_draft_removes_only_unsaved_input():
    at=new_dialog()
    next(t for t in at.text_input if t.label=='고객 또는 일정명').input('버릴 제목').run()
    button(at,'✕').click().run()
    button(at,'저장하지 않고 닫기').click().run()
    assert not at.exception and not at.session_state.get('sales_route')
    assert not at.session_state['sales_drafts']
    assert not at.session_state['fixture_writes']
    assert len(at.session_state['fixture_events'])==1


def test_edit_discard_returns_original_detail():
    at=app('st.session_state.setdefault("sales_route",{"type":"event","id":EVENT})\ncenter.run()')
    button(at,'일정 수정').click().run()
    next(t for t in at.text_input if t.label=='고객 또는 일정명').input('저장하지 않은 수정').run()
    button(at,'이전 화면으로').click().run()
    button(at,'저장하지 않고 닫기').click().run()
    assert not at.exception
    assert at.session_state['sales_route']['type']=='event'
    assert at.session_state['fixture_events'][0]['title']=='상담 테스트'
    assert not at.session_state['sales_drafts']


def test_original_value_restored_closes_without_warning():
    at=new_dialog()
    field=next(t for t in at.text_input if t.label=='고객 또는 일정명')
    field.input('수정').run()
    next(t for t in at.text_input if t.label=='고객 또는 일정명').input('').run()
    button(at,'✕').click().run()
    assert not at.exception and not at.warning
    assert not at.session_state.get('sales_route')


def test_saved_edit_stays_in_latest_detail_and_clear_draft():
    at=app('st.session_state.setdefault("sales_route",{"type":"event","id":EVENT})\ncenter.run()')
    button(at,'일정 수정').click().run()
    next(t for t in at.text_input if t.label=='고객 또는 일정명').input('새 제목').run()
    button(at,'변경 저장').click().run()
    assert not at.exception
    assert at.session_state['sales_route']['type']=='event'
    assert any(s.value=='새 제목' for s in at.subheader)
    assert not at.session_state['sales_drafts']
    assert at.success
    assert len(at.session_state['fixture_writes'])==1


def test_invalid_title_has_field_error_without_write():
    at=new_dialog()
    button(at,'일정 등록').click().run()
    assert not at.exception
    assert any('일정명을 입력' in e.value for e in at.error)
    assert not at.session_state['fixture_writes']


def test_week_labels_include_counts_and_submission_state():
    at=app('st.session_state.setdefault("sales_route",{"type":"member","uid":UID,"day":"2026-11-06","period":"주간"})\nredesign.dialog(FakeRecords())')
    selector=next(s for s in at.segmented_control if s.label=='날짜 선택')
    assert any('11/06' in label and '1건 · 미제출' in label for label in selector.options)


def test_weekends_default_and_session_toggle():
    at=app('''original=center.calendar_view
def capture(**kwargs):
    st.session_state["captured_weekends"]=kwargs["hideWeekends"]
    return st.session_state.get("sales_interactive_calendar")
center.calendar_view=capture
try:center.run()
finally:center.calendar_view=original
''')
    assert not at.exception and at.session_state['captured_weekends'] is False
    at.session_state['sales_interactive_calendar']={'action':'weekends','value':True,'anchor':'2026-11-06','nonce':'toggle'}
    at.run()
    assert not at.exception
    assert at.session_state['captured_weekends'] is True
    at.run()
    assert at.session_state['captured_weekends'] is True


def test_member_filter_reset():
    at=app('center.run()')
    selector=next(s for s in at.selectbox if s.label=='직원 이름 검색 · 선택')
    selector.set_value('11111111-1111-4111-8111-111111111111').run()
    button(at,'전체 보기').click().run()
    assert not at.exception
    assert at.session_state['sales_calendar_member'] is None
