import unittest
from streamlit.testing.v1 import AppTest
from modules.finance_calculator_ui import NAMES as FINANCE
from modules.coverage_models import NAMES as COVERAGE

class CenterRoutes(unittest.TestCase):
    def test_verified_routes_search_and_legacy(self):
        at=AppTest.from_string("import streamlit as st\nfrom modules.jarvia_calculator_center import run\nrun(lambda: st.caption('LEGACY_ENTRY_OK'))").run()
        self.assertFalse(at.exception)
        for name in (*FINANCE,*COVERAGE):
            with self.subTest(name=name):
                at.selectbox(key='jc_selected').select(name).run()
                self.assertFalse(at.exception)
                submit=next(b for b in at.button if b.label=='계산하기')
                submit.click().run()
                self.assertFalse(at.exception)
                self.assertTrue(at.metric)
                self.assertEqual(len(at.get('download_button')),2)
                self.assertTrue(any(c.value=='LEGACY_ENTRY_OK' for c in at.caption))
        at.text_input(key='jc_search').set_value('의료비').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.selectbox(key='jc_selected').options,['의료비 부담계산기'])
        at.text_input(key='jc_search').set_value('존재하지않는계산기').run()
        self.assertFalse(at.exception)
