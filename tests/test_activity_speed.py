from test_activity_redesign import app, button

def test_new_dialog_needs_no_reference_queries():
    at=app('st.session_state["sales_route"]={"type":"new","day":"2026-11-06"}\nredesign.dialog(FakeRecords())')
    assert not at.exception
    assert at.session_state.get("fixture_reads",[])==[]
    next(t for t in at.text_input if t.label=="고객 또는 일정명").input("빠른 등록").run()
    assert not at.exception
    assert at.session_state.get("fixture_reads",[])==[]

def test_detail_loads_only_one_event_until_sections_open():
    at=app('st.session_state.setdefault("sales_route",{"type":"event","id":EVENT})\nredesign.dialog(FakeRecords())')
    assert not at.exception
    assert at.session_state["fixture_reads"]==[("GET","sales_events")]

def test_edit_typing_does_not_refetch_snapshot():
    at=app('st.session_state.setdefault("sales_route",{"type":"edit","id":EVENT})\nredesign.dialog(FakeRecords())')
    assert not at.exception
    before=len(at.session_state["fixture_reads"])
    next(t for t in at.text_input if t.label=="고객 또는 일정명").input("수정 입력").run()
    assert not at.exception
    assert len(at.session_state["fixture_reads"])==before

def test_calendar_opens_modal_in_same_run_without_second_dialog():
    at=app('''action={"action":"new","value":"2026-11-06","nonce":"test-open"}
st.session_state.setdefault("sales_interactive_calendar",action)
original= center.calendar_view
center.calendar_view=lambda **kwargs:action
try: center.run()
finally: center.calendar_view=original
''')
    assert not at.exception
    assert any("일정 등록" in s.value for s in at.markdown)
    assert at.session_state["sales_dialog_rendered"]
    assert not any(t=="sales_followups" for _,t in at.session_state["fixture_reads"])

def test_collapsed_contracts_preserve_typed_values():
    at=app('''from modules.activity.contracts import contract_editor
st.session_state.setdefault("contract_2026-11-06new0product","작성하던 상품")
contract_editor(FakeRecords(),date(2026,11,6))
''')
    assert not at.exception
    assert at.session_state["contract_2026-11-06new0product"]=="작성하던 상품"
    assert not at.session_state.get("fixture_reads",[])
