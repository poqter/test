from streamlit.testing.v1 import AppTest
from modules.shared.self_affiliation import SIGNUP_POSITIONS, eligible_units


def test_public_positions_and_units():
    assert list(SIGNUP_POSITIONS)==['fp','partner','team_leader','deputy_branch_manager','branch_manager','division_head']
    rows=[{'unit_type':'root'},{'unit_type':'head_unit'},{'unit_type':'branch'},{'unit_type':'team'}]
    assert eligible_units(rows,'division_head')==[rows[1]]
    assert eligible_units(rows,'fp')==rows[2:]
    assert eligible_units(rows,'platform_administrator')==[]


def test_optional_managers_and_no_write_before_save():
    src='''import streamlit as st
from modules.shared.self_affiliation import account_managers
class Auth:
 def my_reporting_managers(self,state):
  return {'team_leader':None,'deputy_manager':None,'candidates':[{'id':'t','display_name':'팀장A','position_code':'team_leader'},{'id':'d','display_name':'부지점장B','position_code':'deputy_branch_manager'}]}
 def save_my_reporting_managers(self,state,**kw):st.session_state['saved']=kw
account_managers(Auth(),{'access_token':'test'})
'''
    at=AppTest.from_string(src).run()
    assert not at.exception
    assert at.selectbox[0].options==['미지정','팀장A']
    assert at.selectbox[1].options==['미지정','부지점장B']
    assert 'saved' not in at.session_state
    at.selectbox[0].set_value('t')
    at.selectbox[1].set_value('d')
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state['saved']=={'team_leader':'t','deputy_manager':'d'}


def test_service_signup_metadata_and_no_privilege_fields():
    from modules.shared.hwarang_auth import HwarangAuthService
    class Auth:
        def login_id_available(self,x):return True
        def signup_affiliations(self,x):return [{'organization_code':'branch','unit_type':'branch'}]
        def _request(self,*args,**kw):self.payload=kw['json']
        def sign_in(self,*args):return {}
    auth=Auth()
    HwarangAuthService.sign_up(auth,login_id='newuser',password='Abc12345',display_name='신규',email='new@example.test',join_code='code',organization_code='branch',position_code='branch_manager',team_leader='t',deputy_manager=None)
    metadata=auth.payload['user_metadata']
    assert metadata['position_code']=='branch_manager'
    assert metadata['team_leader']=='t'
    assert 'role' not in metadata


def test_self_update_uses_only_authenticated_session():
    from modules.shared.hwarang_auth import HwarangAuthService
    class Auth:
        def _request(self,*args,**kw):self.call=(args,kw);return {}
    auth=Auth()
    HwarangAuthService.save_my_reporting_managers(auth,{'access_token':'session-token'},team_leader=None,deputy_manager='d')
    _,kw=auth.call
    assert kw['access_token']=='session-token'
    assert kw['json']=={'p_team_leader':None,'p_deputy_manager':'d'}
    assert not kw.get('admin')


def test_forbidden_signup_position_never_creates_user():
    import pytest
    from modules.shared.hwarang_auth import HwarangAuthService,HwarangAuthError
    class Auth:
        def login_id_available(self,x):return True
        def _request(self,*args,**kw):raise AssertionError('Must not create user')
    for position in ('chief_representative','platform_administrator','super_admin','invalid'):
        with pytest.raises(HwarangAuthError):
            HwarangAuthService.sign_up(Auth(),login_id='newuser',password='Abc12345',display_name='신규',email='new@example.test',join_code='code',organization_code='branch',position_code=position)
