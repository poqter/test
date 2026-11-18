"""Local synthetic WORKSPACE shell backed by the exam PGlite fixture."""
from unittest.mock import patch

import requests
import streamlit as st

import app as workspace
from modules.shell.navigation import allowed_ids, navigate
from modules.shell.workspace_v2 import render_home


class FixtureAuth:
    def refresh(self, state):
        return state

    def workspace_permission_role(self, profile):
        return "Basic"

    def _request(self, method, path, *, admin, json):
        assert method == "POST" and path == "/rest/v1/rpc/hwarang_exam" and admin
        response = requests.post("http://127.0.0.1:8138", json=json, timeout=15)
        response.raise_for_status()
        return response.json()


manager = st.query_params.get("manager") == "1"
profile = {"id": "00000000-0000-4000-8000-00000000000" + ("3" if manager else "1"),
           "is_active": True, "role": "user", "position_code": "team_leader" if manager else "fp"}
access = {"academy": True, "workspace": True}
permissions = ["academy.assessment"]
st.session_state.update(password_correct=True, login_user="Basic", login_profile=profile,
                        hw_feature_permissions=permissions, hw_app_access=access,
                        hwarang_auth={"profile": profile, "app_access": access, "feature_permissions": permissions})
permitted = allowed_ids("Basic")
st.session_state["ws_allowed_ids"] = permitted
active = st.session_state.get("active_app", "home")
if active == "home":
    render_home(permitted, navigate, {})
else:
    # Patches stay active on fragments too: the tool dispatch is called each time.
    auth = FixtureAuth()
    workspace.auth_service = lambda: auth
    from hwarang_academy.exams import ui
    from modules.shared import hwarang_auth
    from modules.shell import navigation
    real_dispatch = navigation.dispatch
    def dispatch(*args, **kwargs):
        with patch.object(hwarang_auth.SupabaseConfig, "from_mapping", return_value=None), \
             patch.object(hwarang_auth, "HwarangAuthService", return_value=auth):
            return real_dispatch(*args, **kwargs)
    workspace.dispatch = dispatch
    workspace.render_task_content(active, "Basic", permitted)
