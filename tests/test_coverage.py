import unittest
from decimal import Decimal as D
from modules.coverage_models import NAMES,FIELDS,calculate

class CoverageModels(unittest.TestCase):
    def test_source_cases(self):
        expected=[584455517,90000000,4325344,53000000,8,80045180,45623207]
        for name,want in zip(NAMES,expected):
            with self.subTest(name=name):
                result=calculate(name,[x[1] for x in FIELDS[name]])
                actual=next(iter(result.metrics.values()))
                self.assertLess(abs(actual-D(want)),D('.51'))
    def test_short_period_pv_and_zero(self):
        self.assertLess(abs(calculate(NAMES[0],[3000000,1,0,0,0,0,0]).metrics['총 필요자금']-D(35718126)),D('.51'))
        self.assertLess(abs(calculate(NAMES[2],[2000000,1,0,20,0]).metrics['현재가치 필요액']-D(4762417)),D('.51'))
        r=calculate(NAMES[5],[300000,80000,20,0,0]);self.assertEqual(r.metrics['차액 운용 시 최종 금액'],52800000)
        r=calculate(NAMES[5],[80000,300000,1,0,0]);self.assertEqual(r.metrics['월 보험료 차이'],-220000);self.assertEqual(r.metrics['차액 운용 시 최종 금액'],0)
    def test_boundaries(self):
        for premium in [499999,500000,600000,600001]:
            r=calculate(NAMES[4],[5000000,premium,0]);self.assertEqual(r.metrics['10% 기준까지 차액'],500000-premium);self.assertEqual(r.metrics['12% 기준까지 차액'],600000-premium)
        self.assertEqual(calculate(NAMES[1],[100,0,0,0,1000]).metrics['추가 필요보장액'],0)
        with self.assertRaises(ValueError):calculate(NAMES[4],[0,100,0])
        with self.assertRaises(ValueError):calculate(NAMES[6],[100,10,101,4])
        with self.assertRaises(ValueError):calculate(NAMES[0],[100,1.5,0,0,0,0,0])
    def test_rows_consistency(self):
        r=calculate(NAMES[6],[5000000,10,60,4]);self.assertEqual(r.rows[-1]['누적 보장 효과'],r.metrics['기간 누적 보장 효과'])
        for name in NAMES:
            for bad in [-1,float('nan'),float('inf')]:
                values=[x[1] for x in FIELDS[name]];values[0]=bad
                with self.assertRaises(ValueError):calculate(name,values)

class CoverageUI(unittest.TestCase):
    def test_all_screens_and_updates(self):
        from streamlit.testing.v1 import AppTest
        for name in NAMES:
            with self.subTest(name=name):
                at=AppTest.from_string('from modules.coverage_calculator_ui import run\nrun('+repr(name)+')').run()
                at.button[0].click().run()
                self.assertFalse(at.exception)
                self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
                self.assertEqual(len(at.get('download_button')),2)
                before=at.metric[0].value
                at.number_input[0].set_value(at.number_input[0].value*2);at.button[0].click().run()
                self.assertFalse(at.exception);self.assertNotEqual(before,at.metric[0].value)
