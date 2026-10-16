"""Encrypted upload retry and lifecycle regressions without customer fixtures."""
from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from pypdf import PdfWriter
from pdfminer.pdfdocument import PDFPasswordIncorrect
from modules.consultation.analyzer_pdf_password import (
    STATE_KEY, PASSWORD_KEY, attempt_unlock, prepare_pdf_input, is_encrypted)
from modules.consultation.analyzer_model import DEFAULT_COVERAGES
from modules.shared.validators import validate_upload,ValidationError


class PasswordTests(TestCase):
    def test_current_default_39(self):
        self.assertEqual(len(DEFAULT_COVERAGES),39)
        self.assertIn('항암방사선약물치료비',DEFAULT_COVERAGES)
        self.assertIn('표적항암약물허가치료비',DEFAULT_COVERAGES)

    def test_wrong_then_correct_same_content(self):
        state={PASSWORD_KEY:'wrong'};content=b'%PDF-test'
        with patch('modules.consultation.analyzer_pdf_password.verify_password',return_value=False):
            attempt_unlock(state,content,'same')
        self.assertNotIn(PASSWORD_KEY,state)
        self.assertIsNone(state[STATE_KEY]['raw'])
        self.assertIn('다시 입력',state[STATE_KEY]['error'])
        state[PASSWORD_KEY]='correct'
        with patch('modules.consultation.analyzer_pdf_password.verify_password',return_value=True),patch('modules.consultation.analyzer_pdf.extract_kb_pdf',return_value={'customer_name':'테스트'}) as extract:
            attempt_unlock(state,content,'same')
            extract.assert_called_once_with(content,password='correct')
        self.assertNotIn(PASSWORD_KEY,state)
        self.assertEqual(state[STATE_KEY]['raw']['customer_name'],'테스트')

    def test_parse_failure_clears_password_and_previous_data(self):
        state={PASSWORD_KEY:'secret',STATE_KEY:{'raw':{'old':True}}}
        with patch('modules.consultation.analyzer_pdf_password.verify_password',return_value=True),patch('modules.consultation.analyzer_pdf.extract_kb_pdf',side_effect=RuntimeError('internal')):
            attempt_unlock(state,b'file','new')
        self.assertNotIn(PASSWORD_KEY,state)
        self.assertIsNone(state[STATE_KEY]['raw'])
        self.assertNotIn('internal',state[STATE_KEY]['error'])

    def test_remove_file_clears_unlock_state(self):
        state={PASSWORD_KEY:'secret',STATE_KEY:{'token':'old','raw':{'old':True}}}
        with patch.dict('sys.modules',{'streamlit':SimpleNamespace(session_state=state)}):
            self.assertFalse(prepare_pdf_input(b'')['ready'])
        self.assertNotIn(PASSWORD_KEY,state)
        self.assertIsNone(state[STATE_KEY]['raw'])

    def test_switch_file_clears_unlock_state(self):
        state={PASSWORD_KEY:'secret',STATE_KEY:{'token':'old','raw':{'old':True}}}
        with patch.dict('sys.modules',{'streamlit':SimpleNamespace(session_state=state)}),patch(
                'modules.consultation.analyzer_pdf_password.is_encrypted',return_value=False):
            self.assertTrue(prepare_pdf_input(b'new-file')['ready'])
        self.assertNotIn(PASSWORD_KEY,state)
        self.assertIsNone(state[STATE_KEY]['raw'])

    def test_encryption_opt_in_only(self):
        writer=PdfWriter();writer.add_blank_page(595,842);writer.encrypt('synthetic',algorithm='AES-256')
        stream=BytesIO();writer.write(stream);content=stream.getvalue()
        self.assertTrue(is_encrypted(content))
        with self.assertRaises(ValidationError):validate_upload('test.pdf',content)
        self.assertEqual(validate_upload('test.pdf',content,allow_encrypted_pdf=True).extension,'.pdf')

    def test_unencrypted_page_limit_not_bypassed(self):
        writer=PdfWriter()
        for _ in range(101):writer.add_blank_page(595,842)
        stream=BytesIO();writer.write(stream)
        with self.assertRaises(ValidationError):
            validate_upload('test.pdf',stream.getvalue(),allow_encrypted_pdf=True)
