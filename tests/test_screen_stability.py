"""Interaction regressions: stable fields, targeted copies and PDF readiness."""
from streamlit.testing.v1 import AppTest

APP = '''
import streamlit as st
from modules.consultation.enrollment_comparison import run
st.session_state['shell_runs'] = st.session_state.get('shell_runs', 0) + 1
@st.fragment
def tool():
    run()
tool()
'''

def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_comparison_add_keeps_existing_widget_identity_and_values():
    app = AppTest.from_string(APP, default_timeout=20).run()
    assert not app.exception
    title = next(w for w in app.text_input if w.label == '자료 제목')
    key = title.key
    title.input('보존할 제목').run()
    button(app, '+ 조건 추가').click().run()
    assert not app.exception
    title = next(w for w in app.text_input if w.label == '자료 제목')
    assert title.key == key
    assert title.value == '보존할 제목'
    assert len(app.session_state['enroll_model']['plans']['A']['conditions']) == 2


def test_comparison_copy_updates_destination_without_resetting_source():
    app = AppTest.from_string(APP, default_timeout=20).run()
    fields = [w for w in app.text_input if w.label == '납입기간']
    fields[0].input('20년').run()
    button(app, 'A안 조건 가져오기').click().run()
    assert not app.exception
    m = app.session_state['enroll_model']
    assert m['plans']['A']['conditions'][0]['pay'] == '20년'
    assert m['plans']['B']['conditions'][0]['pay'] == '20년'
    assert all(w.value == '20년' for w in app.text_input if w.label == '납입기간')


def test_comparison_example_can_preview_and_download():
    app = AppTest.from_string(APP, default_timeout=20).run()
    button(app, '예시 입력내용 입력하기').click().run()
    app.radio(key='enroll_step').set_value('3. 미리보기·PDF 저장').run()
    assert not app.exception
    app.checkbox(key='enroll_reviewed').check().run()
    assert not app.exception
    assert len(app.get('download_button')) == 1

ADMIN = '''
import streamlit as st
from modules.shared import admin_center_ui as ui
from modules.shared.hwarang_auth import HwarangAuthError
class Auth:
 def _require_super_admin(self, actor):
  st.session_state['checks']=st.session_state.get('checks',0)+1
  if st.session_state.get('denied'):raise HwarangAuthError('권한이 변경되었습니다.')
 def _request(self,*a,**kw):return []
st.session_state.setdefault('login_profile', {'id':'actor','role':'super_admin'})
st.session_state['hw_admin_center_page']='accounts'
ui.render(Auth())
'''

def test_admin_rechecks_permission_after_fragment_interaction():
    app=AppTest.from_string(ADMIN).run()
    assert not app.exception
    assert app.session_state['checks']==1
    app.session_state['denied']=True
    app.run()
    assert not app.exception
    assert app.session_state['checks']==2
    assert any('권한이 변경' in e.value for e in app.error)
    assert not app.dataframe

def test_comparison_pdf_failure_preserves_draft_and_offers_retry():
    source = APP.replace('from modules.consultation.enrollment_comparison import run', '''from modules.consultation import enrollment_comparison as comparison
from modules.consultation.enrollment_comparison import run
st.session_state.setdefault('enroll_model',comparison.example_model())
st.session_state.setdefault('enroll_step','3. 미리보기·PDF 저장')
def fail(*args):raise ValueError('synthetic export failure')
comparison.build_pdf=fail''')
    # Isolate the patched exporter so other tests keep the real PDF builder.
    from modules.consultation import enrollment_comparison as comparison
    original=comparison.build_pdf
    try:
        app=AppTest.from_string(source,default_timeout=20).run()
        assert not app.exception
        assert app.error
        assert button(app,'PDF 다시 만들기')
        assert app.session_state['enroll_model']['plans']['A']['name']
        assert not app.get('download_button')
    finally:
        comparison.build_pdf=original
