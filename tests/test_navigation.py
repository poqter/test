import unittest
from unittest.mock import Mock, patch

from modules.navigation import allowed_ids, dispatch, navigate
from modules.session_store import (
    commit_input, get_draft, get_result, mark_reviewed, reset_all_work,
    reset_page, review_is_current, save_result,
)


class NavigationAndSessionTests(unittest.TestCase):
    def test_invalid_and_unauthorized_routes_return_home(self):
        for page in ("not-a-page", "commission_calculator"):
            state = {"login_user": "Basic", "active_app": "analyzer"}
            self.assertEqual(navigate(page, state=state), "home")
            self.assertEqual(state["active_app"], "home")

    def test_recent_and_draft_are_session_local(self):
        first = {"login_user": "Admin", "active_app": "quick_calculators", "a_mode": "가상 모드"}
        second = {"login_user": "Admin", "active_app": "home"}
        navigate("analyzer", state=first)
        self.assertEqual(first["hw.ui.recent"], ["analyzer"])
        self.assertEqual(get_draft("quick_calculators", state=first)["a_mode"], "가상 모드")
        self.assertNotIn("hw.ui.recent", second)

    def test_revision_invalidation_review_and_scoped_reset(self):
        state = {"password_correct": True, "login_user": "Admin", "active_app": "quick_calculators"}
        self.assertEqual(commit_input("quick_calculators", "amount", 100, state=state), 1)
        saved = save_result("quick_calculators", {"total": 100}, state=state)
        self.assertEqual(saved["result_revision"], 1)
        mark_reviewed("quick_calculators", state=state)
        self.assertTrue(review_is_current("quick_calculators", state=state))
        commit_input("quick_calculators", "amount", 200, state=state)
        self.assertTrue(get_result("quick_calculators", state=state)["stale"])
        self.assertFalse(review_is_current("quick_calculators", state=state))
        commit_input("consultation_helper", "topic", "가상", state=state)
        reset_page("quick_calculators", state=state)
        self.assertEqual(get_draft("quick_calculators", state=state), {})
        self.assertEqual(get_draft("consultation_helper", state=state), {"topic": "가상"})

    def test_reset_all_keeps_authentication_only(self):
        state = {"password_correct": True, "login_user": "Admin", "active_app": "analyzer", "hw.result.analyzer": {"payload": 1}, "a_mode": "x"}
        reset_all_work(state=state)
        self.assertEqual(state, {"password_correct": True, "login_user": "Admin", "active_app": "analyzer"})

    def test_dispatch_rechecks_permission_and_sanitizes_normal_errors(self):
        with patch("modules.navigation.import_module") as importer:
            self.assertIsNone(dispatch("commission_calculator", role="Basic"))
            importer.assert_not_called()
        broken = Mock()
        broken.run.side_effect = RuntimeError("private uploaded row")
        with patch("modules.navigation.import_module", return_value=broken), patch("modules.navigation.st.error") as show_error:
            self.assertIsNone(dispatch("analyzer", role="Admin"))
            self.assertNotIn("private uploaded row", show_error.call_args.args[0])

    def test_dispatch_does_not_swallow_control_flow_baseexception(self):
        broken = Mock()
        broken.run.side_effect = KeyboardInterrupt()
        with patch("modules.navigation.import_module", return_value=broken):
            with self.assertRaises(KeyboardInterrupt):
                dispatch("analyzer", role="Admin")

    def test_all_roles_have_only_registered_ids(self):
        for role in ("Admin", "Manager1", "Basic", "Crew", "Dream", "unknown"):
            self.assertTrue(set(allowed_ids(role)) <= set(allowed_ids("Admin")))


if __name__ == "__main__":
    unittest.main()
