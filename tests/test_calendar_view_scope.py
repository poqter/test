from streamlit.testing.v1 import AppTest


def screen(role='super_admin'):
    return AppTest.from_string(f'''
import streamlit as st
from modules.activity.view_scope import render_settings,current
st.session_state.setdefault('hwarang_auth',{{'profile':{{'id':'me','role':{role!r}}}}})
st.session_state.setdefault('sales_calendar_member','outside-team')
st.session_state.setdefault('sales_background_reads',{{'private':'old data'}})
render_settings('side')
st.write(current())
''').run()


def test_admin_defaults_daily_and_can_return_from_custom_scope():
    app=screen()
    assert not app.exception
    assert app.markdown[-1].value=='daily'
    app.session_state['calendar_view_scope']='{"position":"branch_manager","unit":"branch"}'
    app.run()
    assert app.markdown[-1].value.startswith('{')
    app.button(key='side_scope_daily').click().run()
    assert app.markdown[-1].value=='daily'
    assert app.session_state['calendar_scope_generation']==1


def test_regular_user_has_no_settings_and_cannot_elevate():
    app=screen('user')
    assert not app.button
    app.session_state['calendar_view_scope']='all'
    app.run()
    assert app.markdown[-1].value=='daily'


def test_switch_clears_results_but_preserves_profile_and_drafts():
    app=AppTest.from_string('''
import streamlit as st
from modules.activity.view_scope import switch,current
st.session_state['hwarang_auth']={'profile':{'id':'me','role':'super_admin','position_code':'team_leader'}}
st.session_state['sales_calendar_member']='outside'
st.session_state['sales_persistent_boot']={'private':'old'}
st.session_state['sales_background_reads']={'private':'old'}
st.session_state['sales_route']={'type':'member','id':'outside'}
st.session_state['draft_content']='unsaved'
switch('daily')
assert 'sales_calendar_member' not in st.session_state
assert 'sales_persistent_boot' not in st.session_state
assert 'sales_background_reads' not in st.session_state
assert 'sales_route' not in st.session_state
assert st.session_state['draft_content']=='unsaved'
assert st.session_state['hwarang_auth']['profile']['role']=='super_admin'
''').run()
    assert not app.exception
