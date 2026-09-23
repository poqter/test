import io
import unittest
from unittest.mock import patch
from modules.legacy_workflow import WORKFLOWS
from modules.upload_ui import guarded_upload
from test_signature import opened
from fixture_factory import synthetic_xlsx


class Stopped(Exception):
    pass


class LegacyWorkflowTests(unittest.TestCase):
    def test_existing_pages_have_guidance(self):
        self.assertEqual(len(WORKFLOWS),11)
        for page in WORKFLOWS:
            with self.subTest(page=page):
                at=opened(page)
                self.assertFalse(at.exception)
                self.assertFalse(at.error)
                self.assertTrue(any('업무 화면 개편 10단계' in c.value for c in at.caption))

    def test_help_popup(self):
        at=opened('remodeling')
        at.button(key='ux8_help_remodeling').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any('계산 기준: 기존 업무 코드 유지' in c.value for c in at.caption))

    def test_related_tool_permissions(self):
        at=opened('analyzer','Basic')
        keys=[b.key for b in at.button]
        self.assertNotIn('ux8_go_analyzer_remodeling',keys)
        at.button(key='ux8_go_analyzer_comparison_builder').click().run()
        self.assertEqual(at.session_state['active_app'],'comparison_builder')
        self.assertFalse(at.exception)

    def test_valid_upload_returns_same_object_and_position(self):
        upload=io.BytesIO(synthetic_xlsx());upload.name='synthetic.xlsx';upload.seek(10)
        with patch('modules.upload_ui.st.file_uploader',return_value=upload):
            self.assertIs(guarded_upload('File',type=['xlsx']),upload)
        self.assertEqual(upload.tell(),10)

    def test_invalid_upload_stops_before_old_results(self):
        upload=io.BytesIO(b'synthetic private content');upload.name='private-name.xlsx'
        with patch('modules.upload_ui.st.file_uploader',return_value=upload), patch('modules.upload_ui.st.error') as error, patch('modules.upload_ui.st.info'), patch('modules.upload_ui.st.stop',side_effect=Stopped):
            with self.assertRaises(Stopped):guarded_upload('File')
            self.assertNotIn('private-name',error.call_args.args[0])
            self.assertNotIn('private content',error.call_args.args[0])

    def test_no_upload(self):
        with patch('modules.upload_ui.st.file_uploader',return_value=None):
            self.assertIsNone(guarded_upload('File'))
