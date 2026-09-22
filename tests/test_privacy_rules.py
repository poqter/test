import io
import unittest

from modules.privacy_guard import permitted_export_fields, safe_error, safe_filename
from modules.validators import MAX_FILE_BYTES, ValidationError, validate_money, validate_upload
try:
    from .fixture_factory import synthetic_xlsx
except ImportError:  # unittest discover -s tests imports this module without a package
    from fixture_factory import synthetic_xlsx


class PrivacyAndValidationTests(unittest.TestCase):
    def test_export_allowlist_and_safe_filename(self):
        filtered = permitted_export_fields({"항목": "가상", "증권번호": "SYN-SECRET", "결과": 1})
        self.assertEqual(filtered, {"항목": "가상", "결과": 1})
        self.assertEqual(safe_filename("Quick Calculator", "xlsx", "2026-09-21"), "hwarang_quick_calculator_20260921.xlsx")

    def test_safe_error_does_not_echo_exception(self):
        detail = "sensitive synthetic payload"
        self.assertNotIn(detail, safe_error("UPLOAD_PARSE_FAILED", RuntimeError(detail)))
        self.assertNotIn(detail, safe_error("UNKNOWN", RuntimeError(detail)))

    def test_money_rejects_nonfinite_and_out_of_range(self):
        self.assertEqual(str(validate_money("100.50")), "100.50")
        for value in ("nan", "inf", -1, 10**13):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_money(value)

    def test_upload_reads_from_start_and_restores_position(self):
        stream = io.BytesIO(synthetic_xlsx())
        stream.seek(len(stream.getvalue()))
        position = stream.tell()
        info = validate_upload("synthetic.xlsx", stream)
        self.assertGreater(info.size, 0)
        self.assertEqual(stream.tell(), position)

    def test_upload_limits_and_signatures(self):
        with self.assertRaises(ValidationError):
            validate_upload("too-large.pdf", b"%PDF-" + b"x" * MAX_FILE_BYTES)
        with self.assertRaises(ValidationError):
            validate_upload("fake.pdf", b"not a pdf")
        with self.assertRaises(ValidationError):
            validate_upload("bad.exe", b"x")


if __name__ == "__main__":
    unittest.main()
