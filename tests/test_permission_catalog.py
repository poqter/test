from __future__ import annotations

import json
from pathlib import Path
import unittest

from modules.shared.permissions import (
    ACADEMY_MODULE_PERMISSION,
    CALCULATOR_GROUP_PERMISSION,
    PERMISSION_BY_CODE,
    PERMISSIONS,
    WORKSPACE_APP_PERMISSION,
)
from modules.shell.app_registry import APP_BY_ID

ROOT = Path(__file__).resolve().parents[1]


class PermissionCatalogTests(unittest.TestCase):
    def test_permission_codes_are_unique(self) -> None:
        self.assertEqual(len(PERMISSIONS), len(PERMISSION_BY_CODE))

    def test_workspace_mapping_references_known_apps_and_permissions(self) -> None:
        for app_id, permission_code in WORKSPACE_APP_PERMISSION.items():
            with self.subTest(app_id=app_id):
                self.assertIn(app_id, APP_BY_ID)
                self.assertIn(permission_code, PERMISSION_BY_CODE)
                self.assertEqual(PERMISSION_BY_CODE[permission_code].app_code, "workspace")

    def test_calculator_groups_are_fully_covered(self) -> None:
        catalog = json.loads((ROOT / "FINANCIAL_CALCULATORS_CATALOG.json").read_text(encoding="utf-8"))
        groups = {group["group"] for group in catalog["groups"]}
        self.assertEqual(groups, set(CALCULATOR_GROUP_PERMISSION))
        for permission_code in CALCULATOR_GROUP_PERMISSION.values():
            self.assertIn(permission_code, PERMISSION_BY_CODE)

    def test_academy_seven_modules_are_defined(self) -> None:
        self.assertEqual(len(ACADEMY_MODULE_PERMISSION), 7)
        for permission_code in ACADEMY_MODULE_PERMISSION.values():
            self.assertIn(permission_code, PERMISSION_BY_CODE)

    def test_sql_seed_contains_every_permission_code(self) -> None:
        # Permission codes may be introduced by later additive migrations.
        # Never rewrite an already-applied migration merely to satisfy this catalog test.
        sql = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
        )
        for code in PERMISSION_BY_CODE:
            with self.subTest(code=code):
                self.assertIn("'" + code + "'", sql)

    def test_signup_still_defaults_to_user_not_admin(self) -> None:
        core = (ROOT / "supabase" / "migrations" / "01_Core_Setup.sql").read_text(encoding="utf-8")
        self.assertIn("'user'", core)
        self.assertIn("'fp'", core)
        self.assertNotIn("'admin',\n        true,\n        v_org_id", core)


if __name__ == "__main__":
    unittest.main()
