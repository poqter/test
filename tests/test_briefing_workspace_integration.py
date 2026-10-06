from __future__ import annotations

from datetime import datetime, timezone

from modules.briefing.gates import route_profiles
from modules.briefing.models import SourceCandidate
from modules.shared.permissions import PERMISSION_BY_CODE, WORKSPACE_APP_PERMISSION
from modules.shell.app_registry import APP_BY_ID


def _candidate(title: str, *, hint: str | None = None) -> SourceCandidate:
    return SourceCandidate(
        title=title,
        url="https://example.com/a",
        source_name="Example",
        collector_provider="direct_rss",
        source_kind="official",
        published_at=datetime.now(timezone.utc),
        metadata={"profile_hint": hint} if hint else {},
    )


def test_briefing_page_registered_and_permission_mapped():
    assert "briefing" in APP_BY_ID
    assert APP_BY_ID["briefing"].module_path == "modules.briefing.briefing_center"
    assert WORKSPACE_APP_PERMISSION["briefing"] == "workspace.briefing"
    assert PERMISSION_BY_CODE["workspace.briefing"].default_granted is True
    assert PERMISSION_BY_CODE["workspace.briefing_manage"].default_granted is False


def test_market_direct_source_hint_routes_to_market():
    routed = route_profiles(_candidate("한국은행 시장 동향", hint="MARKET"), "MARKET")
    assert "MARKET" in routed


def test_market_keywords_can_cross_route_without_hint():
    routed = route_profiles(_candidate("원달러 환율과 국채금리 변동"), None)
    assert "MARKET" in routed
