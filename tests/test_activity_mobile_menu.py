from test_activity_redesign import app, button, text

TAIL='''from modules.activity import mobile
st.query_params["view"]="mobile-calendar"
mobile.run(lambda:st.session_state.update(logged_out=True))
'''

def test_mobile_default_and_management_menus():
    at=app(TAIL)
    assert not at.exception
    assert any(b.label=='구성원 현황' for b in at.button)
    assert any(b.label.startswith('오늘 일정 ') for b in at.button)


def test_staff_cannot_open_manager_page():
    at=app('''from modules.activity import mobile
class Staff(FakeRecords):
    def __init__(self):
        super().__init__();self.me["managed"]=False;self.members={UID:self.me}
center.Records=Staff
st.session_state["mobile_page"]="구성원 현황"
mobile.run(lambda:None)
''')
    assert not at.exception
    assert not any(b.label=='구성원 현황' for b in at.button)
    assert at.session_state['mobile_page']=='캘린더'


def test_report_draft_survives_menu_navigation():
    at=app(TAIL)
    button(at,'활동 기록').click().run()
    assert not at.exception
    text(at,'주요 성과 · 진행사항').input('모바일 작성 중').run()
    button(at,'후속 할 일').click().run()
    assert at.warning
    button(at,'내용 유지하고 이동').click().run()
    assert at.session_state['mobile_page']=='후속 할 일'
    button(at,'활동 기록').click().run()
    assert text(at,'주요 성과 · 진행사항').value=='모바일 작성 중'


def test_menu_discard_does_not_write_records():
    at=app(TAIL)
    button(at,'활동 기록').click().run()
    text(at,'주요 성과 · 진행사항').input('버릴 내용').run()
    button(at,'캘린더').click().run()
    button(at,'내용 버리고 이동').click().run()
    assert not at.exception and not at.session_state['fixture_writes']
    button(at,'활동 기록').click().run()
    assert text(at,'주요 성과 · 진행사항').value==''


def test_weekly_and_alerts_empty_state():
    at=app(TAIL)
    button(at,'활동 기록').click().run()
    button(at,'주간 기록').click().run()
    assert not at.exception
    assert any(s.value=='이번 주 돌아보기' for s in at.subheader)
    button(at,'🔔 알림').click().run()
    assert not at.exception
    assert any(i.value=='일정 알림이 없습니다.' for i in at.info)
