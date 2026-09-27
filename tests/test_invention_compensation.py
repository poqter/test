import unittest
from modules import invention_compensation as c

class Invention(unittest.TestCase):
    def calc(self, **kw):
        return c.invention(confirmed='예', **kw)

    def test_original_and_corrected_comparison(self):
        # Observed source uses salary as tax base and approximates local tax.
        tax = c.progressive_tax
        self.assertEqual((tax(83000000)-tax(80000000))*c.D('1.1'), 792000)
        self.assertEqual((tax(90000000)-tax(83000000))*c.D('1.1'), 2090000)
        r = self.calc().metrics
        self.assertEqual(r['이번 비과세 금액'], 7000000)
        self.assertEqual(r['이번 과세 보상금'], 3000000)
        self.assertEqual(r['보상금 국세 증가 추정'], 684000)
        self.assertEqual(r['비과세 적용에 따른 국세 감소 추정'], 1596000)

    def test_excluded_relation(self):
        r = self.calc(relation=c.RELATIONS[1]).metrics
        self.assertEqual(r['이번 비과세 금액'], 0)
        self.assertEqual(r['보상금 국세 증가 추정'], 2280000)
        self.assertEqual(r['비과세 적용에 따른 국세 감소 추정'], 0)

    def test_annual_limit_and_zero(self):
        for amount,used,expected in [(0,0,0),(6999999,0,6999999),(7000000,0,7000000),(7000001,0,7000000),(10000000,6000000,1000000),(10000000,7000000,0)]:
            self.assertEqual(self.calc(amount=amount,used=used).metrics['이번 비과세 금액'], expected)
        self.assertEqual(self.calc(salary=0,amount=10000000).metrics['보상금 국세 증가 추정'],0)
        with self.assertRaises(ValueError): self.calc(used=7000001)
        with self.assertRaises(ValueError): self.calc(amount=-1)

    def test_unverified_conditions(self):
        self.assertIsInstance(c.invention().metrics['보상금 국세 증가 추정'],str)
        retired=self.calc(kind=c.KINDS[1]).metrics
        self.assertEqual(retired['기타소득금액'],3000000)
        self.assertEqual(retired['보상금 국세 산출세액 증가 추정'],720000)
        self.assertEqual(retired['이번 원천징수 국세 추정 (선납)'],600000)

    def test_retired_branches(self):
        r=self.calc(kind=c.KINDS[1],other_mode=c.OTHER_MODES[1]).metrics
        self.assertEqual(r['보상금 국세 산출세액 증가 추정'],600000)
        r=self.calc(kind=c.KINDS[1],amount=7050000).metrics
        self.assertEqual(r['과세 대상 기타소득금액'],0)
        r=self.calc(kind=c.KINDS[1],used=2000000,used_other=3000000,actual_expenses=1000000).metrics
        self.assertEqual(r['이번 비과세 금액'],2000000)
        self.assertEqual(r['기타소득금액'],7000000)
        for kw in ({'other_optional':1,'other_mode':c.OTHER_MODES[1]}, {'used':5000000,'used_other':3000000}, {'actual_expenses':3000001}):
            with self.assertRaises(ValueError): self.calc(kind=c.KINDS[1],**kw)


    def test_ui_and_exports(self):
        from streamlit.testing.v1 import AppTest
        from modules.calculator_exports import build_exports
        at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
        at.selectbox(key='jc_selected').select(c.NAME).run()
        next(x for x in at.selectbox if x.label==c.FIELDS[c.NAME][6][0]).select('예').run()
        at.button[0].click().run()
        self.assertFalse(at.exception); self.assertFalse(at.error)
        self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
        fs=c.FIELDS[c.NAME];values=[x[1] for x in fs];values[6]='예'
        result=c.calculate(c.NAME,values)
        txt,csv=build_exports(c.NAME,fs,values,result,'2026-09-27')
        self.assertIn('684,000',txt); self.assertIn('지급 전',csv.decode('utf-8-sig'))
