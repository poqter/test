"""Stage 5 synthetic-only selection, overwrite, stale-source and period tests."""
import unittest
from modules.comparison_builder import compare_rows, ordered_rows, move_row, period_months
from modules.material_transfer import candidate, selected_payload, is_current
from modules.content_repository import load_content
from test_signature import opened


class CustomerMaterialsTests(unittest.TestCase):
    def clean(self,at):
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertFalse(at.error,[e.value for e in at.error])

    def test_period_and_zero_missing(self):
        rows,summary=compare_rows([{'항목':'기간','유형':'기간','단위':'개월','변경 전':'10년','변경 후':'120개월'}])
        self.assertEqual(rows[0][5],'+0개월')
        self.assertIn('10년',summary[0])
        self.assertEqual(period_months('1.5년',''),18)
        for value in ('-1년','0.5개월','종신'):
            with self.assertRaises(ValueError):period_months(value,'')
        rows,_=compare_rows([{'항목':'값','유형':'숫자','변경 전':'0','변경 후':'0'}, {'항목':'빈칸','유형':'숫자','변경 전':'','변경 후':'0'}])
        self.assertEqual(rows[0][5],'+0.00')
        self.assertEqual(rows[1][5],'미입력')

    def test_order_identity_limits(self):
        rows=ordered_rows([{'항목':'A'},{'항목':'B'}])
        moved=move_row(rows,1,-1)
        self.assertEqual(moved[0]['row_id'],rows[1]['row_id'])
        self.assertEqual([r['order'] for r in moved],[0,1])
        with self.assertRaises(ValueError):ordered_rows([{}]*41)

    def test_comparison_review_changes_and_move(self):
        at=opened('comparison_builder');self.clean(at)
        at.checkbox(key='_ws_c_reviewed').check().run()
        self.assertEqual(len(at.get('download_button')),2)
        at.text_input(key='_ws_c_title').set_value('수정한 가상 제목').run()
        self.assertEqual(len(at.get('download_button')),0)
        at.selectbox(key='c_selected_row').set_value(1).run()
        at.button(key='c_move_up').click().run();self.clean(at)
        self.assertEqual(at.session_state['c_rows'].iloc[0]['항목'],'보장기간')
        at.button(key='c_add_row').click().run();self.clean(at)
        self.assertEqual(len(at.session_state['c_rows']),3)
        at.button(key='c_delete_row').click().run();self.clean(at)
        self.assertEqual(len(at.session_state['c_rows']),2)

    def test_blank_template_cancel_and_placeholders(self):
        self.assertEqual(len(load_content('customer_material_templates')['templates']),9)
        at=opened('customer_materials');self.clean(at)
        self.assertTrue(at.button(key='d_approve').disabled)
        at.text_area(key='_ws_d_body').set_value('보존할 가상 본문').run()
        at.button(key='d_template_open').click().run()
        at.button(key='d_template_cancel').click().run();self.clean(at)
        self.assertEqual(at.text_area(key='_ws_d_body').value,'보존할 가상 본문')
        at.button(key='d_template_open').click().run()
        at.button(key='d_template_confirm').click().run();self.clean(at)
        self.assertIn('[주제]',at.text_area(key='_ws_d_body').value)
        self.assertTrue(at.button(key='d_approve').disabled)

    def test_document_review_and_reset(self):
        at=opened('customer_materials')
        at.text_area(key='_ws_d_body').set_value('가상 확인 사실\n고객정보 없는 테스트').run()
        at.button(key='d_approve').click().run();self.clean(at)
        self.assertEqual(len(at.get('download_button')),2)
        at.text_area(key='_ws_d_body').set_value('변경된 가상 사실').run()
        self.assertEqual(len(at.get('download_button')),0)
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_customer_materials').click().run();self.clean(at)
        self.assertEqual(at.text_area(key='_ws_d_body').value,'변경된 가상 사실')
        at.button(key='clear_d_').click().run();self.clean(at)
        self.assertEqual(at.text_area(key='_ws_d_body').value,'')

    def calculator(self):
        at=opened('quick_calculators')
        at.radio(key='a_mode').set_value('총 납입보험료').run()
        at.button(key='a_calculate').click().run()
        at.button(key='a_approve').click().run()
        at.button(key='v2_nav_customer_materials').click().run();self.clean(at)
        at.selectbox(key='d_source').set_value('quick_calculators').run()
        return at

    def test_select_import_preserve_body_and_stale(self):
        at=self.calculator()
        at.text_area(key='_ws_d_body').set_value('보존하는 가상 본문').run()
        at.multiselect(key='d_selection_quick_calculators').set_value(['총 납입 예정']).run()
        at.button(key='d_import_open').click().run()
        at.button(key='d_import_confirm').click().run();self.clean(at)
        self.assertEqual(at.text_area(key='_ws_d_body').value,'보존하는 가상 본문')
        transfer=at.session_state['d_transfers']['quick_calculators']
        self.assertEqual(list(transfer['fields']),['총 납입 예정'])
        at.button(key='d_approve').click().run()
        self.assertEqual(len(at.get('download_button')),2)
        at.button(key='v2_nav_quick_calculators').click().run()
        at.number_input(key='_ws_a_total_premium').set_value(22.0).run()
        at.button(key='v2_nav_customer_materials').click().run();self.clean(at)
        self.assertTrue(at.warning)
        self.assertEqual(len(at.get('download_button')),0)
        at.button(key='d_remove_quick_calculators').click().run();self.clean(at)
        self.assertFalse(at.session_state['d_transfers'])

    def test_import_cancel_and_allowlist(self):
        at=self.calculator()
        state=at.session_state.filtered_state
        with self.assertRaises(ValueError):selected_payload('quick_calculators',['주민등록번호'],state)
        at.multiselect(key='d_selection_quick_calculators').set_value(['총 납입 예정']).run()
        at.button(key='d_import_open').click().run()
        at.button(key='d_import_cancel').click().run();self.clean(at)
        self.assertNotIn('d_transfers',at.session_state.filtered_state)
        self.assertIsNone(candidate('quick_calculators',{}))

    def test_birth_excluded_and_session_isolation(self):
        at=opened('quick_calculators')
        at.button(key='a_calculate').click().run()
        at.button(key='a_approve').click().run()
        payload=candidate('quick_calculators',at.session_state.filtered_state)
        self.assertIsNotNone(payload)
        self.assertNotIn('입력 · 생년월일',payload['fields'])
        other=opened('customer_materials')
        self.assertNotIn('a_calculation',other.session_state.filtered_state)

    def test_consultation_selection_and_source_reset(self):
        at=opened('consultation_helper')
        at.radio(key='b_mode').set_value('상담 요약').run()
        for key,value in [('topic','가상 상담'),('facts','가상 확인 사실'),('next','다음 확인')]:
            at.text_area(key='_ws_b_summary_'+key).set_value(value).run()
        at.button(key='b_build_summary').click().run()
        at.button(key='b_summary_approve').click().run()
        at.button(key='v2_nav_customer_materials').click().run();self.clean(at)
        at.multiselect(key='d_selection_consultation_helper').set_value(['상담 요약']).run()
        at.button(key='d_import_open').click().run()
        at.button(key='d_import_confirm').click().run();self.clean(at)
        at.button(key='d_approve').click().run()
        self.assertEqual(len(at.get('download_button')),2)
        at.button(key='v2_nav_consultation_helper').click().run()
        at.button(key='clear_b_').click().run()
        at.button(key='v2_nav_customer_materials').click().run();self.clean(at)
        self.assertTrue(at.warning)
        self.assertEqual(len(at.get('download_button')),0)

    def test_comparison_draft_round_trip(self):
        at=opened('comparison_builder')
        at.button(key='c_add_row').click().run()
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_comparison_builder').click().run();self.clean(at)
        self.assertEqual(len(at.session_state['c_rows']),3)


if __name__=='__main__':unittest.main()
