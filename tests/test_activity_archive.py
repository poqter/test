from test_activity_redesign import app, button


def test_delete_requires_confirmation_and_restore_preserves_record():
    at=app('st.session_state.setdefault("sales_route",{"type":"event","id":EVENT})\ncenter.run()')
    panel=next(e for e in at.expander if e.label=='일정 삭제')
    def opened():
        states=at._tree.get_widget_states();states.widgets.add(id=panel.proto.id,bool_value=True);at._run(states)
    opened()
    assert button(at,'일정 삭제 확인').disabled
    next(c for c in at.checkbox if c.label=='이 일정을 삭제하겠습니다').check()
    opened()
    button(at,'일정 삭제 확인').click()
    opened()
    assert not at.exception
    assert at.session_state['sales_route']['type']=='trash'
    assert at.session_state['fixture_events'][0]['deleted_at']
    button(at,'복구').click().run()
    assert not at.exception
    assert at.session_state['fixture_events'][0]['deleted_at'] is None
    assert at.session_state['fixture_events'][0]['title']=='상담 테스트'


def test_other_member_does_not_get_delete_control():
    at=app('from activity_fixture import OTHER\ndb=FakeRecords()\nrow=dict(st.session_state["fixture_events"][0],owner=OTHER)\nredesign.event_detail(db,row)')
    assert not at.exception
    assert not any(e.label=='일정 삭제' for e in at.expander)
