from __future__ import annotations

import json
from pathlib import Path

from modules.shared.organization import permitted_tools
from modules.shared.permissions import PERMISSION_BY_CODE, WORKSPACE_APP_PERMISSION
from modules.shell.app_registry import APP_BY_ID, ROLE_PERMISSIONS

ROOT = Path(__file__).resolve().parents[1]


def test_briefing_survives_final_organization_gate():
    data = json.loads((ROOT / "data" / "organization_defaults.json").read_text(encoding="utf-8"))
    allowed = data["organizations"]["hwarang"]["revisions"][-1]["allowed_tools"]
    assert "briefing" in allowed
    assert permitted_tools(["briefing"]) == ["briefing"]


def test_briefing_registry_permission_and_role_chain():
    assert APP_BY_ID["briefing"].enabled is True
    assert WORKSPACE_APP_PERMISSION["briefing"] == "workspace.briefing"
    assert PERMISSION_BY_CODE["workspace.briefing"].default_granted is True
    for role in ("Admin", "Manager1", "Basic", "Crew", "Dream"):
        assert "briefing" in ROLE_PERMISSIONS[role]
