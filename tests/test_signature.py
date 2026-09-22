"""Synthetic data only: new workflows, state isolation and export regressions."""
import io
import unittest
from datetime import date
from pathlib import Path
import pdfplumber
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from modules.quick_calculators import age_result, total_premium, coverage_gap
from modules.comparison_builder import compare_rows, parse_number
from modules.workspace_tools import workbook_bytes, pdf_bytes

ROOT=Path(__file__).resolve().parents[1]
def opened(page='home',role='Admin'):
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=45)
    for key,value in dict(password_correct=True,login_user=role,active_app=page).items():
        at.session_state[key]=value
    return at.run()

class SignatureTests(unittest.TestCase):
    def clean(self,at):
        self.assertEqual([e.message for e in at.exception],[])
        self.assertEqual([e.value for e in at.error],[])

    def test_age_boundaries(self):
        self.assertEqual(age_result(date(1990,4,23),date(2026,10,22))[1],36)
        self.assertEqual(age_result(date(1990,4,23),date(2026,10,23))[1],37)
        self.assertEqual(age_result(date(1990,8,31),date(2026,2,28))[1],36)
        with self.assertRaises(ValueError):age_result(date(2027,1,1),date(2026,1,1))
        self.assertEqual(total_premium(10,240,12),(2400,120,2280))
        with self.assertRaises(ValueError):total_premium(10,12,13)
        self.assertEqual(coverage_gap(250,10,10000,3000,5000,5000),(43000,33000))

    def test_all_new_choices(self):
        for page,key,kind in [('quick_calculators','a_mode','radio'),('consultation_helper','b_mode','radio'),('education_center','e_mode','selectbox'),('insurer_portal','f_mode','radio')]:
            at=opened(page);self.clean(at)
            for value in list(getattr(at,kind)(key=key).options):
                getattr(at,kind)(key=key).set_value(value).run();self.clean(at)

    def test_session_draft_round_trip_and_logout(self):
        at=opened('consultation_helper')
        at.radio(key='b_mode').set_value('상담 요약').run()
        at.text_area(key='_ws_b_summary_topic').set_value('가상 상담 주제').run()
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_launch_quick_consultation_helper').click().run()
        at.radio(key='b_mode').set_value('상담 요약').run();self.clean(at)
        self.assertEqual(at.text_area(key='_ws_b_summary_topic').value,'가상 상담 주제')
        other=opened('consultation_helper')
        self.assertNotIn('b_summary_topic',other.session_state.filtered_state)
        at.button(key='v2_logout').click().run();self.clean(at)
        self.assertNotIn('b_summary_topic',at.session_state.filtered_state)

    def test_old_keyed_draft(self):
        at=opened('remodeling')
        at.text_input(key='rm_consultant').set_value('가상 담당').run()
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_remodeling').click().run();self.clean(at)
        self.assertEqual(at.text_input(key='rm_consultant').value,'가상 담당')

    def test_portal_search_and_reset(self):
        at=opened()
        at.text_input(key='home_insurer_search').set_value('현대').run();self.clean(at)
        self.assertTrue(any('현대해상' in m.value and 'ip-home-result' in m.value for m in at.markdown))
        at.button(key='clear_home_insurer_search').click().run();self.clean(at)
        self.assertEqual(at.text_input(key='home_insurer_search').value,'')

    def test_template_replace_and_exports(self):
        at=opened('comparison_builder')
        at.button(key='c_template_open').click().run()
        at.radio(key='c_template_choice').set_value('월 지출 비교')
        at.button(key='c_template_apply').click().run();self.clean(at)
        self.assertEqual(at.dataframe[-1].value.iloc[0]['항목'],'월 고정지출')
        at.checkbox(key='_ws_c_reviewed').check().run();self.clean(at)
        self.assertEqual(len(at.get('download_button')),2)

    def test_reset_popup(self):
        at=opened('quick_calculators')
        at.session_state['a_synthetic_reset_value']='가상 입력'
        at.button(key='wb_reset').click().run();self.clean(at)
        at.button(key='wb_reset_confirm').click().run();self.clean(at)
        self.assertEqual(at.session_state['login_user'],'Admin')
        self.assertEqual(at.session_state['active_app'],'home')
        self.assertNotIn('a_synthetic_reset_value',at.session_state.filtered_state)

    def test_education_dialog_and_navigation(self):
        at=opened('education_center')
        at.selectbox(key='e_mode').set_value('보험금 청구 사례 퀴즈').run()
        at.radio[0].set_value(at.radio[0].options[1]).run()
        at.button(key='e_quiz_submit').click().run();self.clean(at)
        self.assertTrue(at.success)
        at=opened('education_center')
        at.selectbox(key='e_mode').set_value('상담유형별 권장 도구').run()
        at.button(key='e_recommended_go').click().run();self.clean(at)
        self.assertEqual(at.session_state['active_app'],'analyzer')

    def test_comparison_numbers(self):
        self.assertEqual(parse_number('0'),0)
        for bad in ['nan','inf','=1+1','100원']:
            with self.assertRaises(ValueError):parse_number(bad)
        rows,summary=compare_rows([{'항목':'비율','유형':'비율(%)','변경 전':'10','변경 후':'12'}])
        self.assertEqual(rows[0][5],'+2.00%p')

    def test_excel_literal_and_long_pdf(self):
        b=workbook_bytes('검증',['항목','값'],[['=1+1',0]],'설명')
        wb=load_workbook(io.BytesIO(b));self.assertEqual(wb.active['A5'].data_type,'s');self.assertEqual(wb.active['B5'].value,0)
        notes='설명문 검증. '*900+'끝까지 보존 확인'
        b=pdf_bytes('비교표',['항목','유형','단위','전','후','차이','메모'],[['항목','문자','','긴 설명 '*100,'다른 설명 '*100,'변경','추가 확인 '*100]],notes)
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            extracted=''.join(p.extract_text() or '' for p in pdf.pages)
            self.assertIn('끝까지 보존 확인',extracted)
            self.assertGreater(len(pdf.pages),1)

if __name__=='__main__':unittest.main()
