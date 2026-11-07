from test_activity_redesign import app, button


def test_back_stack_only_records_page_changes():
    at=app('''from modules.activity.mobile import choose,previous_page
choose('오늘의 업무')
choose('오늘의 업무')
choose('후속 할 일')
previous_page()
assert st.session_state['mobile_page']=='오늘의 업무'
assert st.session_state['mobile_back_stack']==['캘린더']
previous_page()
assert st.session_state['mobile_page']=='캘린더'
assert st.session_state['mobile_back_stack']==[]
''')
    assert not at.exception


def test_dirty_back_is_pending_until_user_decides():
    at=app('''from modules.activity import mobile,ux
if 'setup' not in st.session_state:
    mobile.choose('활동 기록')
    d=ux.draft('test',{'note':''})
    d['values']['note']='보존할 기록'
    st.session_state['sales_active_draft']='test'
    st.session_state['setup']=True
    mobile.previous_page()
mobile.pending_navigation()
''')
    assert not at.exception
    assert at.session_state['mobile_page']=='활동 기록'
    assert at.session_state['mobile_back_stack']==['캘린더']
    button(at,'내용 유지하고 이동').click().run()
    assert at.session_state['mobile_page']=='캘린더'
    assert at.session_state['mobile_back_stack']==[]
    assert at.session_state['sales_drafts']['test']['values']['note']=='보존할 기록'
