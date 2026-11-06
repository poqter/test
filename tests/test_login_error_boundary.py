import importlib.util
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

@pytest.mark.parametrize('calendar',[True,False])
@pytest.mark.parametrize('old_generation',[True,False])
def test_auth_failure_is_recoverable_in_both_login_forms(calendar,old_generation):
    source=f'''
import streamlit as st
import importlib.util
from pathlib import Path
import app as workspace
from modules.shared.hwarang_auth import HwarangAuthError
# Load a second real module generation without replacing the live module.
if {old_generation!r}:
    spec=importlib.util.spec_from_file_location("old_auth_generation",Path(workspace.__file__).parent/"modules/shared/hwarang_auth.py")
    module=importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    Error=module.HwarangAuthError
    Error.__module__="modules.shared.hwarang_auth"
    assert Error is not HwarangAuthError
else: Error=HwarangAuthError
class Auth:
    def sign_in(self, login, password):
        raise Error("아이디 또는 비밀번호를 확인해 주세요.",status=400,code="invalid_credentials")
(workspace.render_calendar_login if {calendar!r} else workspace.render_login)(Auth())
'''
    at=AppTest.from_string(source,default_timeout=20).run()
    at.text_input[0].input('test-account')
    at.text_input[1].input('incorrect-test-password')
    next(b for b in at.button if b.label==('캘린더 로그인' if calendar else '로그인')).click().run()
    assert not at.exception
    assert any(e.value=='아이디 또는 비밀번호를 확인해 주세요.' for e in at.error)
    assert at.text_input[0].value=='test-account'
    assert not at.session_state.get('password_correct',False)


def test_unrelated_runtime_errors_are_not_mislabeled_as_auth_failures():
    import app
    class Auth:
        def sign_in(self,*args):raise RuntimeError('programming bug')
    with pytest.raises(RuntimeError,match='programming bug'):
        app.submit_login(Auth(),'test','password',False,None)
