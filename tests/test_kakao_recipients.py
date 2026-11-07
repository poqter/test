import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).parents[1] / 'modules' / 'briefing' / 'kakao_recipients.py'
spec = importlib.util.spec_from_file_location('kakao_recipients', MODULE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Recipient = module.Recipient
assess = module.assess_recipients


class RecipientChecks(unittest.TestCase):
    def test_name_is_not_claimed_verified(self):
        row = assess([Recipient('고객', '고객 A')])[0]
        self.assertEqual(row.state, 'unverified')

    def test_korean_normalization_flags_duplicates(self):
        rows = assess([Recipient('a', '가'), Recipient('b', '\u1100\u1161')])
        self.assertEqual([row.state for row in rows], ['needs_review', 'needs_review'])

    def test_blank_and_newline_are_rejected(self):
        rows = assess([Recipient('a', ''), Recipient('b', '고객\n다른 고객')])
        self.assertTrue(all(row.state == 'needs_review' for row in rows))

    def test_stopped_recipients_are_excluded_and_do_not_block(self):
        rows = assess([Recipient('a', '고객', False), Recipient('b', '고객')])
        self.assertEqual([row.state for row in rows], ['excluded', 'unverified'])

    def test_only_outer_whitespace_removed(self):
        rows = assess([Recipient('a', ' 고객 A '), Recipient('b', '고객A')])
        self.assertEqual([row.search_name for row in rows], ['고객 A', '고객A'])
        self.assertTrue(all(row.state == 'unverified' for row in rows))


if __name__ == '__main__':
    unittest.main()
