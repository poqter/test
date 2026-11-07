from modules.shared.organization_picker import valid_affiliation, organization_path
from streamlit.testing.v1 import AppTest

ROWS=[dict(id='root',code='HWARANG',name='화랑',unit_type='root',parent_id=None),
      dict(id='vision',code='VISION_HQ',name='비전본부',unit_type='head_unit',parent_id='root'),
      dict(id='direct',code='HWARANG_DIRECT',name='화랑직할',unit_type='head_unit',parent_id='root'),
      dict(id='dong',code='DONGVAN_HQ',name='동반본부',unit_type='head_unit',parent_id='root'),
      dict(id='dream',code='DREAM_BRANCH',name='드림지점',unit_type='branch',parent_id='vision'),
      dict(id='vd',code='VISION_DIRECT',name='비전직할',unit_type='branch',parent_id='vision'),
      dict(id='dd',code='DONGVAN_DIRECT',name='동반직할',unit_type='branch',parent_id='dong')]
POSITIONS=[dict(code=c,display_name=n) for c,n in [('chief_representative','총괄대표'),('division_head','본부장'),('team_leader','팀장')]]

def test_affiliation_policy_and_path():
    assert valid_affiliation('chief_representative','root',ROWS)
    assert not valid_affiliation('chief_representative','vision',ROWS)
    assert valid_affiliation('division_head','vision',ROWS)
    assert not valid_affiliation('division_head','dream',ROWS)
    assert not valid_affiliation('division_head','direct',ROWS)
    assert valid_affiliation('team_leader','vd',ROWS)
    assert not valid_affiliation('team_leader','root',ROWS)
    assert not valid_affiliation('team_leader',None,ROWS)
    assert organization_path('dream',ROWS)=='화랑 → 비전본부 → 드림지점'

def test_dependent_picker_and_no_write_until_save():
    src=f'''import streamlit as st
from modules.shared.organization_picker import render_affiliation
position,unit=render_affiliation({ROWS!r},{POSITIONS!r},{{'position_code':'team_leader','organization_unit_id':'dream'}},'test')
st.session_state['result']=(position,unit)
'''
    at=AppTest.from_string(src).run()
    assert not at.exception
    assert at.session_state['result']==('team_leader','dream')
    assert at.selectbox[2].options==['드림지점','비전직할']
    at.selectbox[1].set_value('dong').run()
    assert at.selectbox[2].options==['동반직할']
    assert at.session_state['result']==('team_leader',None)
    at.selectbox[2].set_value('dd').run()
    assert at.session_state['result']==('team_leader','dd')
    at.selectbox[0].set_value('division_head').run()
    assert len(at.selectbox)==2
    assert '화랑직할' not in at.selectbox[1].options
    assert at.session_state['result']==('division_head','vision')
    at.selectbox[0].set_value('chief_representative').run()
    assert len(at.selectbox)==1
    assert at.session_state['result']==('chief_representative','root')

def test_admin_save_keeps_permissions_and_updates_only_selected_affiliation():
    src=f'''import streamlit as st
from modules.shared.admin_center_ui import _user_permissions
class Auth:
 def admin_user_snapshot(self, actor, uid):
  return dict(profile=dict(id=uid,display_name='테스트',login_id='test',role='user',is_active=True,position_code='team_leader',organization_unit_id='dream'),app_access={{'workspace':True,'academy':True,'calculator':False}},feature_permissions=['academy.practice'])
 def admin_reference_data(self, actor):return dict(organizations={ROWS!r},positions={POSITIONS!r},permissions=[dict(permission_code='academy.practice',app_code='academy',display_name='연습')])
 def admin_apply_user_changes(self,**changes):
  st.session_state['saved']=changes
  return self.admin_user_snapshot('admin','other')
_user_permissions(Auth(),'admin','other')
'''
    at=AppTest.from_string(src).run()
    assert not at.exception
    at.selectbox[0].set_value('division_head').run()
    assert 'saved' not in at.session_state
    next(b for b in at.button if b.label=='변경사항 저장').click().run()
    assert not at.exception
    saved=at.session_state['saved']
    assert saved['organization_unit_id']=='vision' and saved['position_code']=='division_head'
    assert saved['role']=='user'
    assert saved['app_access']=={'workspace':True,'academy':True,'calculator':False}
    assert saved['permissions']=={'academy.practice':True}
