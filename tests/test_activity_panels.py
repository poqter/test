from datetime import date
from test_activity_redesign import app, button


def new_dialog():
    return app('''if not st.session_state.get("opened_once"):
    st.session_state["sales_route"]={"type":"new","day":"2026-11-06"}
    st.session_state["opened_once"]=True
center.run()
''')


def test_extra_panel_identity_and_open_state_survive_toggles():
    at=new_dialog()
    panel=next(e for e in at.expander if e.label=="추가 정보 · 선택")
    identity=panel.proto.id
    def run_open():
        # AppTest does not serialize expander blocks. Send the same state as
        # the browser alongside each input change instead of dropping it.
        states=at._tree.get_widget_states()
        states.widgets.add(id=identity,bool_value=True)
        at._run(states)
    run_open()
    assert not at.exception
    support=next(t for t in at.toggle if t.label=="지원 요청")
    support.set_value(True)
    run_open()
    assert not at.exception
    assert next(e for e in at.expander if e.label=="추가 정보 · 선택").proto.id==identity
    assert any(t.label=="지원받을 내용" for t in at.text_input)
    next(t for t in at.toggle if t.label=="매주 반복").set_value(True)
    run_open()
    assert not at.exception
    assert next(e for e in at.expander if e.label=="추가 정보 · 선택").proto.id==identity
    assert any(n.label=="총 등록 횟수 · 이번 일정 포함" for n in at.number_input)


def test_top_close_protects_dirty_input_and_retains_draft():
    at=new_dialog()
    next(t for t in at.text_input if t.label=="일정명").input("닫아도 보존할 제목").run()
    button(at,"✕").click().run()
    assert not at.exception and at.warning
    assert at.session_state["sales_route"]["type"]=="new"
    button(at,"계속 작성").click().run()
    assert next(t for t in at.text_input if t.label=="일정명").value=="닫아도 보존할 제목"
    button(at,"✕").click().run()
    button(at,"내용 유지하고 닫기").click().run()
    assert not at.session_state.get("sales_route")
    assert any(d["values"].get("title")=="닫아도 보존할 제목" for d in at.session_state["sales_drafts"].values())


def test_top_close_closes_clean_dialog():
    at=new_dialog()
    button(at,"✕").click().run()
    assert not at.exception
    assert not at.session_state.get("sales_route")


def test_week_uses_one_selected_day_and_preserves_selection():
    at=app('''st.session_state.setdefault("sales_route",{"type":"member","uid":UID,"day":"2026-11-06","period":"주간"})
redesign.dialog(FakeRecords())
''')
    assert not at.exception
    selector=next(s for s in at.segmented_control if s.label=="날짜 선택")
    assert len(selector.options)==5
    assert not any(" · 일정 " in e.label for e in at.expander)
    selector.set_value(date(2026,11,3)).run()
    assert not at.exception
    assert at.session_state["sales_route"]["selected_day"]=="2026-11-03"
    assert sum(m.value=="**일정**" for m in at.markdown)==1
    assert any("11월 03일" in c.value for c in at.caption)


def test_report_help_title_is_stable_after_input():
    at=app('redesign.reports(FakeRecords(),date(2026,11,6),"일일")')
    panel=next(e for e in at.expander if e.label=="지원 요청 · 선택")
    identity=panel.proto.id
    next(t for t in at.text_input if t.label=="지원받을 내용").input("동행 요청").run()
    assert not at.exception
    assert next(e for e in at.expander if e.label=="지원 요청 · 선택").proto.id==identity


def test_team_summary_reads_only_when_opened():
    at=app('center.calendar_extras(FakeRecords(),date(2026,11,6))')
    assert not at.exception
    assert ('POST','rpc/sales_branch_members') not in at.session_state['fixture_reads']
    panel=next(e for e in at.expander if e.label=='오늘의 팀')
    states=at._tree.get_widget_states()
    states.widgets.add(id=panel.proto.id,bool_value=True)
    at._run(states)
    assert not at.exception
    assert ('POST','rpc/sales_branch_members') in at.session_state['fixture_reads']
