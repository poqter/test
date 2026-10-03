from __future__ import annotations

import unittest

from modules.shared.hwarang_auth import HwarangAuthService, SupabaseConfig


class AuthCoreTests(unittest.TestCase):
    def test_config_reads_top_level_keys(self) -> None:
        cfg = SupabaseConfig.from_mapping(
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
                "SUPABASE_SECRET_KEY": "sb_secret_test",
            }
        )
        self.assertEqual(cfg.url, "https://example.supabase.co")

    def test_system_admins_bridge_to_workspace_admin(self) -> None:
        self.assertEqual(HwarangAuthService.workspace_permission_role({"role": "super_admin"}), "Admin")
        self.assertEqual(HwarangAuthService.workspace_permission_role({"role": "admin"}), "Admin")
        self.assertEqual(HwarangAuthService.workspace_permission_role({"role": "user"}), "Basic")

    def test_server_only_profile_fields_are_removed(self) -> None:
        result = HwarangAuthService._public_profile(
            {"id": "u1", "login_id": "fp01", "auth_email": "hidden@example.com"}
        )
        self.assertNotIn("auth_email", result)
        self.assertEqual(result["login_id"], "fp01")

    def test_infrastructure_errors_are_not_returned_raw(self) -> None:
        message = HwarangAuthService._friendly_error(400, 'column profiles.example does not exist')
        self.assertEqual(message, "계정 서버 설정을 확인해 주세요.")


if __name__ == "__main__":
    unittest.main()

class AuthFlowTests(unittest.TestCase):
    class FakeService(HwarangAuthService):
        def __init__(self):
            super().__init__(
                SupabaseConfig(
                    url="https://example.supabase.co",
                    publishable_key="sb_publishable_test",
                    secret_key="sb_secret_test",
                )
            )
            self.admin_lookup_called = False
            self.marked = False

        def _profile_by_login_id(self, login_id):
            return {
                "id": "u1",
                "login_id": "rockexe",
                "auth_email": "auth@example.com",
                "display_name": "Tester",
                "role": "super_admin",
                "is_active": True,
                "position_code": None,
                "organization_unit_id": None,
            }

        def _auth_user_by_id(self, uid):
            self.admin_lookup_called = True
            return {"email": "fallback@example.com"}

        def _request(self, method, path, **kwargs):
            if path == "/auth/v1/token":
                return {
                    "access_token": "token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                }
            return []

        def _mark_login(self, uid):
            self.marked = True

    def test_sign_in_uses_server_profile_email_without_admin_lookup(self) -> None:
        service = self.FakeService()
        state = service.sign_in("rockexe", "password123")
        self.assertFalse(service.admin_lookup_called)
        self.assertTrue(service.marked)
        self.assertNotIn("auth_email", state["profile"])
        self.assertEqual(state["profile"]["role"], "super_admin")
