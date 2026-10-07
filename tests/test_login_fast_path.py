from __future__ import annotations

from pathlib import Path

from modules.shared.hwarang_auth import HwarangAuthService, SupabaseConfig


class _FastPathAuth(HwarangAuthService):
    def __init__(self):
        super().__init__(
            SupabaseConfig(
                url="https://example.supabase.co",
                publishable_key="publishable",
                secret_key="secret",
            )
        )
        self.calls: list[tuple[str, str, dict]] = []

    def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/rest/v1/rpc/get_hwarang_login_bootstrap":
            return [{
                "user_id": "user-1",
                "auth_email": "auth@example.com",
                "is_active": True,
            }]
        if path == "/auth/v1/token":
            return {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "user": {"id": "user-1"},
            }
        if path == "/rest/v1/rpc/complete_hwarang_workspace_login":
            return [{
                "platform_session_id": None,
                "user_id": "user-1",
                "login_id": "rockexe",
                "display_name": "테스트 사용자",
                "role": "super_admin",
                "is_active": True,
                "position_code": "TEAM_LEADER",
                "position_name": "팀장",
                "organization_unit_id": "org-1",
                "organization_name": "드림지점",
                "organization_code": "DREAM",
                "app_access": {
                    "workspace": True,
                    "calculator": True,
                    "academy": True,
                },
                "feature_permissions": [
                    "workspace.consultation",
                    "academy.simulator",
                ],
            }]
        raise AssertionError(f"unexpected request: {method} {path}")


def test_fast_login_uses_exactly_three_sequential_network_requests():
    auth = _FastPathAuth()
    state = auth.sign_in("rockexe", "password123")

    assert [path for _, path, _ in auth.calls] == [
        "/rest/v1/rpc/get_hwarang_login_bootstrap",
        "/auth/v1/token",
        "/rest/v1/rpc/complete_hwarang_workspace_login",
    ]
    assert state["login_fast_path"] is True
    assert state["platform_session_id"] == ""
    assert state["profile"]["organization_name"] == "드림지점"
    assert state["profile"]["position_name"] == "팀장"
    assert state["app_access"]["workspace"] is True
    assert "academy.simulator" in state["feature_permissions"]


def test_fast_login_does_not_call_legacy_profile_permission_enrichment_routes():
    auth = _FastPathAuth()
    auth.sign_in("rockexe", "password123")
    paths = {path for _, path, _ in auth.calls}

    assert "/rest/v1/profiles" not in paths
    assert "/rest/v1/positions" not in paths
    assert "/rest/v1/organization_units" not in paths
    assert "/rest/v1/hwarang_app_access" not in paths
    assert "/rest/v1/rpc/get_hwarang_effective_permissions" not in paths
    assert "/rest/v1/rpc/open_hwarang_user_session" not in paths


def test_migration_12_contains_login_fast_path_contract():
    sql = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "12_Login_Fast_Path.sql"
    ).read_text(encoding="utf-8")

    assert "profiles_login_id_unique_ci" in sql
    assert "create index if not exists profiles_login_id_lower_idx" not in sql.lower()
    assert "get_hwarang_login_bootstrap" in sql
    assert "complete_hwarang_workspace_login" in sql
    assert "get_hwarang_effective_permissions" in sql
    assert "hwarang_user_sessions" in sql
    assert "LOGIN_SUCCESS" in sql
    assert "grant execute on function public.get_hwarang_login_bootstrap(text)" in sql.lower()
    assert "to service_role" in sql.lower()


def test_migration_17_keeps_login_only_and_removes_presence_session_creation():
    sql=(Path(__file__).resolve().parents[1]/"supabase"/"migrations"/"17_Workspace_Performance_Login_Only.sql").read_text(encoding="utf-8")
    complete=sql.split("create or replace function public.complete_hwarang_workspace_login",1)[1]
    compact=complete.replace(" ","")
    assert "platform_session_id:=null" in compact
    assert "LOGIN_SUCCESS" in complete
    assert "last_login_at=now()" in compact
    assert "insert into public.hwarang_user_sessions" not in complete.lower()


def test_workspace_collects_no_post_login_presence_or_page_activity():
    app_source=(Path(__file__).resolve().parents[1]/"app.py").read_text(encoding="utf-8")
    assert "hw_last_heartbeat_at" not in app_source
    assert "hw_last_activity_app" not in app_source
    assert "log_activity(" not in app_source
    assert "heartbeat(" not in app_source
    assert "close_session(" not in app_source
