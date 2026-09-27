import unittest
from modules.mortgage_deduction import mortgage, TYPES, NAME, FIELDS


class MortgageTests(unittest.TestCase):
    def test_limits_and_shared_wage_engine(self):
        for years, kind, expected in ((15,0,20000000),(15,1,18000000),(15,2,18000000),(15,3,8000000),(10,0,6000000),(14,1,6000000),(10,3,0),(9,0,0)):
            with self.subTest(years=years,kind=kind):
                r=mortgage(interest=30000000,years=years,loan_type=TYPES[kind],eligible='예')
                self.assertEqual(r.metrics['이자 소득공제 대상액'],expected)
        r=mortgage(eligible='예')
        # Original's salary-based flat 24% overstates savings: crossing a band
        # and losing the 130k standard credit both matter here.
        self.assertEqual(r.metrics['입력 조건에서 예상 세금 감소액'],1366750)
        self.assertEqual(mortgage(interest=30000000,eligible='예',other_housing=4000000).metrics['이자 소득공제 대상액'],16000000)

    def test_eligibility_calendar_months_and_boundaries(self):
        for kwargs in ({},{'eligible':'예','houses':2},{'eligible':'예','standard_value':600000001},
                       {'eligible':'예','registered':'2024-01-31','borrowed':'2024-05-01'}):
            self.assertEqual(mortgage(**kwargs).metrics['이자 소득공제 대상액'],0)
        r=mortgage(eligible='예',standard_value=600000000,registered='2024-01-31',borrowed='2024-04-30')
        self.assertEqual(r.metrics['이자 소득공제 대상액'],6000000)
        self.assertEqual(mortgage(eligible='예',salary=0).metrics['입력 조건에서 예상 세금 감소액'],0)
        for kwargs in ({'interest':-1},{'salary':float('nan')},{'registered':'2023-01-01'},{'other_housing':4000001}):
            with self.assertRaises(ValueError):mortgage(**kwargs)

    def test_center_ui_and_exports(self):
        from streamlit.testing.v1 import AppTest
        from modules.calculator_exports import build_exports
        at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
        at.selectbox(key='jc_selected').select(NAME).run()
        at.selectbox(key='cov_'+NAME+'_9').select('예').run()
        at.button[0].click().run()
        self.assertFalse(at.exception); self.assertFalse(at.error)
        self.assertEqual(next(m.value for m in at.metric if m.label=='입력 조건에서 예상 세금 감소액'),'1,366,750원')
        vals=[f[1] for f in FIELDS[NAME]]; vals[9]='예'
        customer,advisor=build_exports(NAME,FIELDS[NAME],vals,mortgage(eligible='예'),'2026-09-26')
        self.assertIn('1,366,750원',customer)
        self.assertIn('1,366,750원',advisor.decode('utf-8-sig'))
