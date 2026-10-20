from streamlit.testing.v1 import AppTest


def test_password_change_notice_then_login_removes_auth_screen():
    app = AppTest.from_string('''
import streamlit as st
import app as workspace
class Auth:
    def sign_in(self, login, password):
        return {'profile': {'id': 'test', 'display_name': 'Test'}}
    def refresh(self, state):
        return state
    def workspace_permission_role(self, profile):
        return 'admin'
workspace.auth_service = lambda: Auth()
workspace.render_sidebar = lambda *args: None
workspace.render_home = lambda *args: st.write('HOME_READY')
workspace.main()
''', default_timeout=20)
    app.session_state['hw_account_flash'] = '비밀번호를 변경했습니다. 새 비밀번호로 다시 로그인해 주세요.'
    app.run()
    assert not app.exception
    assert len(app.success) == 1
    # A rerender (including an unsuccessful submit) must not consume the notice
    # and move the auth shell before the next authentication request completes.
    app.run()
    assert len(app.success) == 1
    assert app.session_state['hw_account_flash']
    app.text_input[0].input('test')
    app.text_input[1].input('example123')
    next(button for button in app.button if button.label == '워크스페이스 시작 →').click().run()
    assert not app.exception
    assert not app.text_input
    assert not app.success
    assert any(item.value == 'HOME_READY' for item in app.markdown)
    assert not any('hw-auth-' in item.value for item in app.markdown)
