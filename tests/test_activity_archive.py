from test_activity_redesign import app, button


def test_delete_requires_confirmation_and_removes_record():
    at=app('st.session_state.setdefault("sales_route",{"type":"event","id":EVENT})\ncenter.run()')
    button(at,'일정 삭제').click().run()
    assert len(at.session_state['fixture_events'])==1
    button(at,'일정 삭제 확인').click().run()
    assert not at.exception
    assert not at.session_state['fixture_events']


def test_other_member_does_not_get_delete_control():
    at=app('from activity_fixture import OTHER\ndb=FakeRecords()\nrow=dict(st.session_state["fixture_events"][0],owner=OTHER)\nredesign.event_detail(db,row)')
    assert not at.exception
    assert not any(e.label=='일정 삭제' for e in at.button)
