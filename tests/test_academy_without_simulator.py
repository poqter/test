"""Retained Academy routes with the retired modules absent and old grants still present."""
import sys
from pathlib import Path
import pytest

from streamlit.testing.v1 import AppTest


ENTRY = str(Path(__file__).resolve().parents[1] / "academy_app.py")
RETIRED = (
    "hwarang_academy.studio", "hwarang_academy.content", "hwarang_academy.service",
    "hwarang_academy.history", "hwarang_academy.review_export",
    "modules.shared.ai_guardrails", "modules.shared.academy_credit_ui",
)
HARNESS = """
import json, runpy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import streamlit as st
from modules.shell.app_registry import APP_BY_ID
class EducationAccount:
    def _request(self, method, path, **kwargs):
        st.session_state.setdefault("requested", []).append(path)
        if path.endswith("/hwarang_learning_catalog"):
            return [json.loads((Path(ENTRY).parent/"hwarang_academy/education/foundation.json").read_text())]
        if path.endswith("/hwarang_learning_work_get"):
            return []
        if path.endswith("/hwarang_exam"):
            if kwargs["json"]["p_action"] == "list":
                return [{"id":"synthetic","title":"가상 시험","status":"active"}]
        raise AssertionError(path)
main = runpy.run_path(ENTRY)["main"]
identity = {"profile":{"id":"fixture","role":"super_admin","is_active":True},
            "feature_permissions":["academy.assessment","academy.new_hire","academy.simulator"]}
with patch("modules.shell.app_registry.APP_BY_ID", {**APP_BY_ID, "academy":replace(APP_BY_ID["academy"],enabled=True)}), patch.dict(
    main.__globals__, auth_service=EducationAccount, _consume_workspace_launch=lambda auth: identity
):
    main()
"""


@pytest.fixture(params=[RETIRED, ("modules.shared.ai_guardrails",)], ids=["all-retired", "credit-removed-first"])
def retired_modules(monkeypatch, request):
    for module in request.param:
        monkeypatch.setitem(sys.modules, module, None)


def test_old_simulator_link_recovers_and_keeps_learning_routes(retired_modules):
    app = AppTest.from_string("ENTRY = " + repr(ENTRY) + "\n" + HARNESS, default_timeout=20)
    app.query_params["view"] = "simulator"
    app.session_state["_academy_surface"] = "history"
    app.run()
    assert not app.exception and not app.error
    assert app.session_state["_academy_surface"] == "academy"
    assert not any("상담 연습" in b.label for b in app.button)
    app.button(key="onboarding_home").click().run()
    assert not app.exception and not app.error
    assert any("필수 학습" in item.value for item in app.caption)
    app.button(key="academy_nav_exams").click().run()
    assert not app.exception and not app.error
    assert any(b.label == "이어서 풀기" for b in app.button)
    assert set(app.session_state["requested"]) == {
        "/rest/v1/rpc/hwarang_learning_catalog",
        "/rest/v1/rpc/hwarang_learning_work_get",
        "/rest/v1/rpc/hwarang_exam",
    }


def test_health_without_studio(retired_modules):
    app = AppTest.from_file(ENTRY)
    app.query_params["stability_health"] = "1"
    app.run()
    assert not app.exception
    assert "HWARANG_UI_RELEASE=" in app.code[0].value
