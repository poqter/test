from __future__ import annotations

import unittest

from modules.shell.app_registry import APP_IDS, APP_BY_ID, ROLE_PERMISSIONS


class RegistryIntegrityTests(unittest.TestCase):
    def test_app_ids_are_unique(self) -> None:
        self.assertEqual(len(APP_IDS), len(set(APP_IDS)))
        self.assertEqual(set(APP_IDS), set(APP_BY_ID))

    def test_permissions_reference_registered_apps_only(self) -> None:
        registered = set(APP_IDS)
        for role, allowed in ROLE_PERMISSIONS.items():
            with self.subTest(role=role):
                self.assertTrue(set(allowed) <= registered)

    def test_external_apps_have_keys(self) -> None:
        for app in APP_BY_ID.values():
            if app.source_status == "standalone":
                with self.subTest(app=app.id):
                    self.assertTrue(app.external_app_key)


if __name__ == "__main__":
    unittest.main()
