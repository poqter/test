from test_activity_redesign import app, button, text, number


def support_app(candidates):
    return app(f'''st.session_state.setdefault('fixture_support_candidates',{candidates!r})
redesign.reports(FakeRecords(),date(2026,11,6),'일일')''')


def candidate(uid,role='branch_manager'):
    return dict(member=uid,label='관리자',role_code=role)


def test_single_recipient_auto_selected_and_persisted_on_submission():
    at=support_app([candidate('manager')])
    picker=next(s for s in at.selectbox if s.label=='지원 요청 대상')
    assert not at.exception and picker.value=='manager'
    number(at,'AP').set_value(1).run()
    text(at,'지원받을 내용').input('상담 지원').run()
    assert all(not r.get('submitted') for r in at.session_state['fixture_reports'])
    button(at,'제출하기').click().run()
    assert not at.exception
    report=at.session_state['fixture_reports'][0]
    assert report['submitted'] and report['data']['help_recipient']=='manager'


def test_multiple_recipients_require_selection_and_keep_draft():
    at=support_app([candidate('manager'),candidate('leader','team_leader')])
    assert next(s for s in at.selectbox if s.label=='지원 요청 대상').value is None
    number(at,'AP').set_value(1).run()
    text(at,'지원받을 내용').input('지원 내용').run()
    button(at,'제출하기').click().run()
    assert not at.exception and any('대상을 선택' in w.value for w in at.warning)
    assert all(not r.get('submitted') for r in at.session_state['fixture_reports'])
    assert text(at,'지원받을 내용').value=='지원 내용'


def test_no_recipient_does_not_block_record_without_request():
    at=support_app([])
    assert next(s for s in at.selectbox if s.label=='지원 요청 대상').disabled
    number(at,'AP').set_value(1).run()
    button(at,'제출하기').click().run()
    assert not at.exception and at.session_state['fixture_reports'][0]['submitted']
