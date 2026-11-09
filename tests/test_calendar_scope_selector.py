from streamlit.testing.v1 import AppTest


def test_selector_applies_role_and_organization_without_profile_change():
    app = AppTest.from_string('''
import streamlit as st
from unittest.mock import patch
from modules.activity.view_scope import render_settings, current
profile={'id':'me','role':'super_admin','position_code':'team_leader','organization_unit_id':'branch'}
st.session_state.setdefault('hwarang_auth',{'profile':profile,'access_token':'test'})
catalog={'positions':[{'code':'branch_manager','display_name':'지점장'},{'code':'team_leader','display_name':'팀장'}],
'units':[{'id':'hq','name':'본부','parent_id':None,'unit_type':'head_unit'},{'id':'branch','name':'지점','parent_id':'hq','unit_type':'branch'}],
'people':[{'id':'me','display_name':'본인','position_code':'team_leader','organization_unit_id':'branch'}]}
with patch('modules.shared.hwarang_auth.SupabaseConfig.from_mapping',return_value=None), patch('modules.shared.hwarang_auth.HwarangAuthService') as service:
    service.return_value._request.return_value=catalog
    render_settings('side')
st.write(current())
''').run()
    app.button(key='side_scope_open').click().run()
    assert not app.exception
    assert app.selectbox(key='side_view_position').value == 'team_leader'
    app.selectbox(key='side_view_position').select('branch_manager').run()
    app.button(key='side_scope_apply').click().run()
    assert not app.exception
    import json
    assert json.loads(app.session_state['calendar_view_scope']) == {'position':'branch_manager','unit':'branch','subject':None}
    assert app.session_state['hwarang_auth']['profile']['position_code'] == 'team_leader'
    assert app.session_state['calendar_view_label'] == '지점 · 지점장'
    app.button(key='side_scope_daily').click().run()
    assert app.session_state['calendar_view_scope'] == 'daily'
