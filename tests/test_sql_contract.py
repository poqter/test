from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"


class SqlContractTests(unittest.TestCase):
    def test_platform_contract_objects_exist_in_migrations(self) -> None:
        text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql")))
        for token in (
            "public.profiles",
            "public.hwarang_join_codes",
            "public.hwarang_app_access",
            "public.hwarang_app_launch_tickets",
            "public.academy_cases",
            "public.academy_sessions",
            "public.academy_assessments",
            "public.academy_learning_profiles",
            "public.can_hwarang_user_view",
            "public.hwarang_permissions",
            "public.hwarang_user_permissions",
            "public.hwarang_admin_audit_log",
            "public.get_hwarang_effective_permissions",
            "public.admin_apply_hwarang_user",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_latest_optimization_migration_exists(self) -> None:
        self.assertTrue((MIGRATIONS / "06_Platform_Update.sql").is_file())
        self.assertTrue((MIGRATIONS / "07_Permissions_Admin.sql").is_file())


if __name__ == "__main__":
    unittest.main()
