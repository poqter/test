"""Synthetic consultation flows: freshness, overwrite and document integrity."""
import io
import unittest

import pdfplumber

from modules.consultation_documents import build_summary, document_pdf, unresolved
from modules.content_repository import CONTENT_FILES, load_content
from test_signature import opened


class ConsultationStudioTests(unittest.TestCase):
    def summary(self):
        at = opened('consultation_helper')
        at.radio(key='b_mode').set_value('상담 요약').run()
        for key, value in [('topic', '가상 보장 점검'), ('facts', '가상 계약 조건은 확인 중입니다.'), ('next', '약관을 함께 확인합니다.')]:
            at.text_area(key='_ws_b_summary_' + key).set_value(value).run()
        at.button(key='b_build_summary').click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.error)
        return at

    def download(self, at, key):
        return next(x for x in at.get('download_button') if x.key == key)

    def test_summary_review_and_stale_source(self):
        at = self.summary()
        self.assertTrue(self.download(at, 'b_summary_download').disabled)
        at.button(key='b_summary_approve').click().run()
        self.assertFalse(self.download(at, 'b_summary_download').disabled)
        self.assertTrue(any(x.key == 'b_summary_pdf' for x in at.get('download_button')))
        at.text_area(key='_ws_b_summary_facts').set_value('새로 확인한 가상 사실').run()
        self.assertTrue(self.download(at, 'b_summary_download').disabled)
        self.assertTrue(at.warning)

    def test_edit_and_alias_invalidate_review(self):
        at = self.summary()
        at.button(key='b_summary_approve').click().run()
        at.text_area(key='_ws_b_summary_edit').set_value('직접 검토한 문구').run()
        self.assertTrue(self.download(at, 'b_summary_download').disabled)
        at.button(key='b_summary_approve').click().run()
        at.text_input(key='_ws_b_alias').set_value('가상 상담 A').run()
        self.assertFalse(self.download(at, 'b_summary_download').disabled)
        at.checkbox(key='_ws_b_summary_include_alias').check().run()
        self.assertTrue(self.download(at, 'b_summary_download').disabled)

    def test_overwrite_cancel_and_confirm(self):
        at = self.summary()
        at.text_area(key='_ws_b_summary_edit').set_value('보존할 수동 편집').run()
        at.button(key='b_build_summary').click().run()
        at.button(key='b_replace_cancel').click().run()
        self.assertEqual(at.session_state['b_summary_edit'], '보존할 수동 편집')
        at.button(key='b_build_summary').click().run()
        at.button(key='b_replace_confirm').click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.error)
        self.assertIn('가상 보장 점검', at.session_state['b_summary_edit'])

    def test_proposal_reacts_to_summary_changes(self):
        at = self.summary()
        at.radio(key='b_mode').set_value('제안서·PDF').run()
        at.text_area(key='_ws_b_proposal_direction').set_value('유지안과 변경 조건을 함께 비교').run()
        at.text_area(key='_ws_b_proposal_next').set_value('확인할 자료 준비').run()
        at.button(key='b_build_proposal').click().run()
        at.button(key='b_proposal_approve').click().run()
        self.assertFalse(self.download(at, 'b_proposal_download').disabled)
        at.radio(key='b_mode').set_value('상담 요약').run()
        at.text_area(key='_ws_b_summary_edit').set_value('변경한 가상 요약').run()
        at.radio(key='b_mode').set_value('제안서·PDF').run()
        self.assertTrue(self.download(at, 'b_proposal_download').disabled)
        self.assertTrue(at.warning)

    def test_message_placeholders_and_separate_channel_drafts(self):
        at = opened('consultation_helper')
        at.radio(key='b_mode').set_value('상황별 메시지').run()
        self.assertTrue(at.button(key='b_message_approve').disabled)
        key = '_ws_b_message_첫 상담 고객상담 일정 안내'
        at.text_area(key=key).set_value('가상 안내문을 직접 확인했습니다.').run()
        at.button(key='b_message_approve').click().run()
        self.assertFalse(self.download(at, 'b_message_download').disabled)
        at.radio(key='_ws_b_channel').set_value('이메일').run()
        self.assertIn('제목:', at.text_area(key=key + '_email').value)
        self.assertTrue(self.download(at, 'b_message_download').disabled)
        at.radio(key='_ws_b_channel').set_value('문자').run()
        self.assertEqual(at.text_area(key=key).value, '가상 안내문을 직접 확인했습니다.')

    def test_reset_removes_document_and_review(self):
        at = self.summary()
        at.button(key='b_summary_approve').click().run()
        at.button(key='clear_b_').click().run()
        self.assertFalse(at.session_state.filtered_state.get('b_summary_edit', ''))
        self.assertNotIn('b_summary_review', at.session_state.filtered_state)

    def test_content_and_long_pdf_preserve_text(self):
        for name in CONTENT_FILES:
            self.assertEqual(load_content(name)['schema_version'], 1)
        with self.assertRaises(ValueError):
            load_content('../private')
        body = build_summary('가상 주제', '한글 사실 & <조건> ' * 600, '', '', '끝부분확인표식')
        self.assertIn('미기재', body)
        payload = document_pdf('가상 상담 요약', body, prepared_on='2026-09-22')
        with pdfplumber.open(io.BytesIO(payload)) as document:
            self.assertGreater(len(document.pages), 1)
            text = '\n'.join(page.extract_text() or '' for page in document.pages)
            self.assertIn('끝부분확인표식', text)
            self.assertIn('<조건>', text)
        self.assertEqual(unresolved('문구 [날짜] [날짜]'), ['[날짜]'])
        with self.assertRaises(ValueError):
            document_pdf('가상', '가' * 24001, prepared_on='2026-09-22')


if __name__ == '__main__':
    unittest.main()
