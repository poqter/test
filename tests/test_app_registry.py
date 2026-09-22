"""Registry and preserved business-source tests."""
import hashlib
import json
import unittest
from pathlib import Path

from modules.app_registry import APP_BY_ID, APP_IDS, APPS, GROUPS, ROLE_PERMISSIONS


EXPECTED_IDS = {
    "analyzer", "remodeling", "deposit_vs_shortpay", "renewal_vs_nonrenewal",
    "inheritance_tax", "insurer_portal", "insurance_claim_guide",
    "silson_generation_comparison", "convention", "summer", "manager_results",
    "commission_calculator", "quick_calculators", "consultation_helper",
    "comparison_builder", "education_center",
}
ROOT = Path(__file__).resolve().parents[1]
BUSINESS_MODULES = (
    "modules/analyzer.py", "modules/remodeling.py", "modules/deposit_vs_shortpay.py",
    "modules/renewal_vs_nonrenewal.py", "modules/inheritance_tax.py",
    "modules/insurer_portal.py", "modules/insurance_claim_guide.py",
    "modules/silson_generation_comparison.py", "modules/convention.py",
    "modules/summer.py", "modules/manager_results.py", "modules/commission_calculator.py",
)


class AppRegistryTests(unittest.TestCase):
    def test_ids_groups_and_string_paths(self):
        self.assertEqual(set(APP_IDS), EXPECTED_IDS)
        self.assertEqual(len(APPS), len(EXPECTED_IDS))
        self.assertEqual(len(GROUPS), 7)
        for spec in APPS:
            self.assertEqual(APP_BY_ID[spec.id], spec)
            self.assertIsInstance(spec.module_path, str)
            self.assertTrue(spec.module_path.startswith("modules."))

    def test_role_permissions_preserved(self):
        self.assertEqual(set(ROLE_PERMISSIONS), {"Admin", "Manager1", "Basic", "Crew", "Dream"})
        self.assertEqual(ROLE_PERMISSIONS["Admin"], EXPECTED_IDS)
        self.assertEqual(ROLE_PERMISSIONS["Manager1"], EXPECTED_IDS)
        self.assertNotIn("commission_calculator", ROLE_PERMISSIONS["Basic"])
        self.assertNotIn("remodeling", ROLE_PERMISSIONS["Crew"])
        self.assertIn("remodeling", ROLE_PERMISSIONS["Dream"])
        for role in ROLE_PERMISSIONS:
            self.assertTrue({"quick_calculators", "consultation_helper", "comparison_builder", "education_center"} <= ROLE_PERMISSIONS[role])

    def test_business_sources_match_authoritative_manifest(self):
        manifest = json.loads((ROOT / "docs" / "BASELINE_MANIFEST.json").read_text(encoding="utf-8"))
        for relative in BUSINESS_MODULES:
            with self.subTest(relative=relative):
                actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(actual, manifest["source_sha256"][relative])


if __name__ == "__main__":
    unittest.main()
