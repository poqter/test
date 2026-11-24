import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/hwarang_keepalive.py"
keepalive = runpy.run_path(str(SCRIPT))


class KeepAliveTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.outer, self.app = Mock(), Mock()
        self.page.frames = [self.outer, self.app]
        for frame in self.page.frames:
            frame.locator.return_value.first.is_visible.return_value = False
            frame.get_by_role.return_value.is_visible.return_value = False
        self.target = next(t for t in keepalive["scheduled_targets"]() if t.name == "CALCULATOR")

    def test_sleep_page_is_woken_once_and_app_frame_must_appear(self):
        wake = self.outer.get_by_role.return_value
        wake.is_visible.return_value = True
        self.app.locator.return_value.first.is_visible.side_effect = [False, True]
        keepalive["wait_for_entry"](self.page, self.target)
        wake.click.assert_called_once()
        self.app.locator.assert_called_with(".calc-gate h1")

    def test_awake_workspace_needs_no_wake(self):
        workspace = next(t for t in keepalive["scheduled_targets"]() if t.name == "WORKSPACE")
        self.app.locator.return_value.first.is_visible.return_value = True
        keepalive["wait_for_entry"](self.page, workspace)
        self.app.locator.assert_called_with(".hw-auth-copy h1")
        self.outer.get_by_role.return_value.click.assert_not_called()

    def test_shell_or_stuck_wake_never_counts_as_ready(self):
        for sleeping in (False, True):
            with self.subTest(sleeping=sleeping):
                wake = self.outer.get_by_role.return_value
                wake.reset_mock()
                wake.is_visible.return_value = sleeping
                with patch("time.monotonic", side_effect=[0, 1, 5, 121]):
                    with self.assertRaisesRegex(RuntimeError, "entry not visible"):
                        keepalive["wait_for_entry"](self.page, self.target)
                self.assertEqual(wake.click.call_count, int(sleeping))

    def test_retry_only_failed_target_and_report_final_status(self):
        targets = keepalive["scheduled_targets"]()
        for final_failure in (False, True):
            context = Mock()
            page = context.new_page.return_value
            statuses = [200, 503, 200, 503 if final_failure else 200]
            page.goto.side_effect = [Mock(status=status) for status in statuses]
            check = keepalive["check_targets"]
            with patch.dict(check.__globals__, wait_for_entry=Mock()), patch("builtins.print") as output:
                if final_failure:
                    with self.assertRaises(RuntimeError):
                        check(context, targets)
                else:
                    check(context, targets)
                report = output.call_args_list[-1].args[0]
            self.assertEqual([call.args[0] for call in page.goto.call_args_list],
                             [target.url for target in targets] + [targets[1].url])
            self.assertIn("FAILED" if final_failure else "RETRY_SUCCESS", report)
            self.assertEqual(report.count("SKIPPED"), 2)
