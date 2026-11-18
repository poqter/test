from io import BytesIO
from pathlib import Path
import runpy

import pytest
from pypdf import PdfWriter

from modules.consultation.coverage_comparison_data import ComparisonPageLimit, MAX_COMPARISON_PAGES, extract_pdf
from modules.shared.validators import ValidationError, validate_upload
from modules.shell import navigation
from modules.shell.app_registry import APPS, home_tools

@pytest.mark.parametrize("pages", (100, 101, 160, 161))
@pytest.mark.parametrize("encrypted", (False, True))
def test_comparison_pdf_limits(pages, encrypted):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("synthetic")
    stream = BytesIO()
    writer.write(stream)
    data = stream.getvalue()
    def compare():
        validate_upload("fixture.pdf", data, allow_encrypted_pdf=True, max_pdf_pages=MAX_COMPARISON_PAGES)
        return extract_pdf(data, "synthetic" if encrypted else "")
    if pages <= 160:
        assert compare()["page_count"] == pages
    else:
        with pytest.raises((ComparisonPageLimit, ValidationError), match="160"):
            compare()
    if pages > 100 or encrypted:
        with pytest.raises(ValidationError):
            validate_upload("fixture.pdf", data)


def test_academy_visit_switch(monkeypatch):
    targets = runpy.run_path(str(Path(__file__).resolve().parents[1] / ".github/scripts/hwarang_keepalive.py"))["scheduled_targets"]
    for setting in (None, "false", "true"):
        if setting is None:
            monkeypatch.delenv("ACADEMY_KEEPALIVE_ENABLED", raising=False)
        else:
            monkeypatch.setenv("ACADEMY_KEEPALIVE_ENABLED", setting)
        expected = ["WORKSPACE", "CALCULATOR", "CALENDAR"]
        if setting == "true":
            expected.insert(2, "ACADEMY")
        assert [target.name for target in targets()] == expected


def test_registry_home_placement():
    placed = [item for section in ("consult", "compare", "performance", "resources") for item in home_tools(section)]
    assert len(placed) == len(set(placed))
    assert set(placed) == {app.id for app in APPS} - {"sales_activity", "briefing"}
    assert home_tools("resources") == ("insurer_portal", "insurance_cbt", "academy")


@pytest.mark.parametrize("active,academy,assessment,org,expected", [
    (True,True,True,True,True), (False,True,True,True,False), (True,False,True,True,False),
    (True,True,False,True,False), (True,True,True,False,False),
])
def test_cbt_authorization(monkeypatch, active, academy, assessment, org, expected):
    from modules.shared import organization
    monkeypatch.setattr(navigation.st, "session_state", {
        "password_correct": True, "hwarang_auth": {"profile": {"is_active": active}},
        "hw_app_access": {"academy": academy}, "hw_feature_permissions": ["academy.assessment"] if assessment else [],
    })
    monkeypatch.setattr(organization, "active_profile", lambda: {"allowed_tools": ["academy"] if org else []})
    allowed = navigation.allowed_ids("Admin")
    assert "academy" not in allowed
    assert ("insurance_cbt" in allowed) == expected


def test_menu_uses_resolved_permissions(monkeypatch):
    def redundant(role):
        pytest.fail("unexpected permission recalculation")
    monkeypatch.setattr(navigation, "allowed_ids", redundant)
    state = {"ws_allowed_ids": ["analyzer"], "active_app": "home"}
    assert navigation.navigate("analyzer", state=state) == "analyzer"
    assert navigation.navigate("insurance_cbt", state=state) == "home"
