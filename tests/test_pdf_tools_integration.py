"""PDF route authorization and deployment asset regression coverage."""
from pathlib import Path
from unittest.mock import Mock
import pytest
from modules.shell import navigation
from modules.shell.app_registry import APP_BY_ID, ROLE_PERMISSIONS
from modules.shared import organization
from modules.shared.permissions import WORKSPACE_APP_PERMISSION

@pytest.mark.parametrize('role', list(ROLE_PERMISSIONS))
def test_legacy_roles_can_open_tool(monkeypatch, role):
    monkeypatch.setattr(navigation.st, 'session_state', {})
    assert 'image_to_pdf' in navigation.allowed_ids(role)

def test_feature_permission_is_authoritative(monkeypatch):
    state = {'password_correct': True, 'hw_feature_permissions': [], 'hw_app_access': {'workspace': True}}
    monkeypatch.setattr(navigation.st, 'session_state', state)
    assert 'image_to_pdf' not in navigation.allowed_ids('Admin')
    state['hw_feature_permissions'] = ['workspace.customer_materials']
    assert 'image_to_pdf' in navigation.allowed_ids('Basic')
    assert WORKSPACE_APP_PERMISSION['image_to_pdf'] == 'workspace.customer_materials'

def test_organization_can_restrict_tool(monkeypatch):
    monkeypatch.setattr(navigation.st, 'session_state', {})
    monkeypatch.setattr(organization, 'active_profile', lambda: {'allowed_tools': ['analyzer']})
    assert 'image_to_pdf' not in navigation.allowed_ids('Admin')

def test_direct_route_rechecks_permission(monkeypatch):
    from modules.resources import image_to_pdf
    monkeypatch.setattr(image_to_pdf.st, 'session_state', {'password_correct': True, 'login_user': 'Admin'})
    monkeypatch.setattr(navigation, 'allowed_ids', lambda role: [])
    component = Mock()
    monkeypatch.setattr(image_to_pdf, '_component', component)
    monkeypatch.setattr(image_to_pdf.st, 'error', Mock())
    image_to_pdf.run()
    component.assert_not_called()
    image_to_pdf.st.error.assert_called_once()

def test_local_assets_and_route():
    assert APP_BY_ID['image_to_pdf'].module_path == 'modules.resources.image_to_pdf'
    root = Path(__file__).resolve().parents[1] / 'modules/resources/pdf_tools'
    for name in ['index.html','app.js','style.css','vendor/pdf-lib.min.js','vendor/pdf.min.mjs','vendor/pdf.worker.min.mjs','vendor/jszip.min.js','vendor/cmaps/UniKS-UCS2-H.bcmap','vendor/standard_fonts/LiberationSans-Regular.ttf']:
        assert (root/name).is_file(), name
    source = (root/'app.js').read_text()
    assert 'streamlit:setComponentValue' not in source
    assert 'localStorage' not in source
    assert 'sessionStorage' not in source


def test_home_and_sidebar_include_authorized_tool():
    from streamlit.testing.v1 import AppTest
    source = """import streamlit as st
from modules.shell.workspace_v2 import render_home, render_sidebar
from modules.shell.navigation import navigate
st.session_state['login_profile']={'id':'test-user','display_name':'Test'}
st.session_state['ws_allowed_ids']=['image_to_pdf']
render_sidebar(['image_to_pdf'], navigate, lambda: None, {})
render_home(['image_to_pdf'], navigate, {})
"""
    app = AppTest.from_string(source).run()
    assert not app.exception
    buttons = [b for b in app.button if 'PDF·이미지 도구' in b.label]
    assert len(buttons) == 2
    next(b for b in buttons if '열기' in b.label).click().run()
    assert app.session_state['active_app'] == 'image_to_pdf'
