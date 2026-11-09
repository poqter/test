from test_activity_redesign import app, button, text

TAIL='''from modules.activity import mobile
st.query_params["view"]="mobile-calendar"
mobile.run(lambda:st.session_state.update(logged_out=True))
'''

def test_mobile_default_and_management_menus():
    at=app(TAIL)
    assert not at.exception
    assert any(b.label=='구성원 현황' for b in at.button)
    assert not any(__import__('re').match(r'오늘 일정 \d',b.label) for b in at.button)


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
    assert not any(b.label=='후속 할 일' for b in at.button)
    button(at,'캘린더').click().run()
    assert at.session_state['mobile_page']=='캘린더'
    button(at,'활동 기록').click().run()
    assert text(at,'주요 성과 · 진행사항').value=='모바일 작성 중'


def test_menu_discard_does_not_write_records():
    at=app('st.session_state.setdefault("fixture_conflict",True)\n'+TAIL)
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
    next(s for s in at.segmented_control if s.label=='기록 구분').set_value('주간 기록').run()
    assert not at.exception
    assert any(s.label=='이번 주 돌아보기' for s in at.text_area)
    button(at,'알림').click().run()
    assert not at.exception
    assert any(i.value=='알림이 없습니다.' for i in at.info)


def test_alerts_dialog_keeps_page_and_closes():
    at=app(TAIL)
    page=at.session_state.get('mobile_page','캘린더')
    button(at,'알림').click().run()
    assert not at.exception
    assert at.session_state.get('mobile_page','캘린더')==page
    button(at,'닫기').click().run()
    assert not at.exception
    assert at.session_state.get('mobile_page','캘린더')==page
    assert not any(i.value=='알림이 없습니다.' for i in at.info)


def test_automatic_support_recipient_does_not_warn_when_leaving_untouched_record():
    at=app("st.session_state['fixture_support_candidates']=[dict(member='manager',label='관리자',role_code='branch_manager')]\n"+TAIL)
    button(at,'활동 기록').click().run()
    assert next(s for s in at.selectbox if s.label=='지원 요청 대상').value=='manager'
    at.run()
    button(at,'캘린더').click().run()
    assert not at.exception and at.session_state['mobile_page']=='캘린더'
    assert not any(b.label=='계속 작성' for b in at.button)
    assert not at.session_state['fixture_writes']


def test_unsaved_edit_opens_small_dialog_and_continue_preserves_text():
    at=app('st.session_state.setdefault("fixture_conflict",True)\n'+TAIL)
    button(at,'활동 기록').click().run()
    text(at,'주요 성과 · 진행사항').input('저장 실패한 작성 내용').run()
    button(at,'캘린더').click().run()
    assert not at.exception and len(at.get('dialog'))==1
    assert not any('이동 방법' in w.value for w in at.warning)
    button(at,'계속 작성').click().run()
    assert not at.exception and at.session_state['mobile_page']=='활동 기록'
    assert text(at,'주요 성과 · 진행사항').value=='저장 실패한 작성 내용'
    assert not at.session_state.get('mobile_pending')
