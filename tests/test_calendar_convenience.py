from test_activity_redesign import app, button


def test_recent_choices_do_not_autofill_or_query():
    at=app('''from modules.activity import ux
ux.remember_recent(UID,[{"id":"recent","owner":UID,"place":"최근 상담실","companion":None},{"id":"other","owner":"other","place":"다른 직원 장소"}])
redesign.event_editor(FakeRecords(),date(2026,11,6))
''')
    assert not at.exception
    assert next(t for t in at.text_input if t.label=='장소 · 선택').value==''
    assert not any(s.label=='최근 장소' for s in at.selectbox)
    assert at.session_state.get('fixture_reads',[])==[]


def test_scope_default_and_staff_permissions():
    at=app('''db=FakeRecords()
db.me["managed"]=False
st.session_state["sales_calendar_team"]=True
redesign.calendar_scope(db)
''')
    assert not at.exception
    assert at.radio[0].value=='지점 일정'
    assert '직원 선택' not in at.radio[0].options


def test_sync_stamp_is_not_replaced_by_event_time():
    at=app('''original=center.calendar_view
def capture(**kwargs):
    st.session_state["captured_stamp"]=kwargs["boot"]["syncStamp"]
    return None
center.calendar_view=capture
try:center.calendar(FakeRecords(),date(2026,11,6))
finally:center.calendar_view=original
''')
    assert not at.exception
    assert at.session_state['captured_stamp'] is None  # Populated by the first browser payload, not a blocking boot read.
