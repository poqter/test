"""Independent financial identities, invalid inputs, freshness and export parity."""
import io
import unittest
from decimal import Decimal as D
import pdfplumber
from openpyxl import load_workbook
from modules.calculator_core import calculate, number, integer, won
from modules.calculator_catalog import MODES
from modules.calculator_exports import export_bytes, formatted_results
from test_signature import opened


class CalculatorCenterTests(unittest.TestCase):
    def clean(self,at):
        self.assertFalse(at.exception)
        self.assertFalse(at.error)

    def test_total_and_living(self):
        self.assertEqual(calculate('total',dict(premium=100000,months=240,paid=12)),{'총 납입 예정':D(24000000),'기납입 추정':D(1200000),'향후 납입 예정':D(22800000)})
        self.assertEqual(calculate('family',dict(living=2500000,years=10,assets=50000000))['추가 준비액'],D(250000000))
        self.assertEqual(calculate('debt',dict(debt=100,assets=200))['부채 정리 부족액'],0)
        self.assertEqual(calculate('income',dict(spending=100,income=200,duration=6,reserve=0))['추가 준비액'],0)
        self.assertEqual(calculate('waiver',dict(premium=100000,months=120,ratio=30))['조건 충족 가정 시 면제액'],3600000)

    def test_coverage_and_education(self):
        self.assertEqual(calculate('coverage',dict(living=250,years=10,debt=10000,oneoff=3000,assets=5000,existing=5000))['가정상 부족 재원'],33000)
        self.assertEqual(calculate('education',dict(annual=100,years=2,wait=1,inflation='.1',assets=0))['예상 교육비 총액'],231)
        self.assertEqual(calculate('education',dict(annual=100,years=0,wait=0,inflation=0,assets=0))['추가 준비액'],0)

    def test_zero_rate_and_zero_period(self):
        self.assertEqual(calculate('saving',dict(target=1200,assets=0,months=12,rate=0))['목표 달성 월 저축액'],100)
        self.assertEqual(calculate('goal',dict(assets=100,saving=50,months=12,rate=0))['예상 적립액'],700)
        self.assertEqual(calculate('goal',dict(assets=100,saving=50,months=0,rate='.1'))['예상 적립액'],100)
        with self.assertRaises(ValueError):calculate('saving',dict(target=1200,assets=0,months=0,rate=0))

    def test_month_end_compounding_identity(self):
        # One year on initial capital equals annual effective return exactly.
        result=calculate('goal',dict(assets=100000,saving=0,months=12,rate='.12'))
        self.assertEqual(won(result['예상 적립액']),112000)
        # A single deposit at the final month end accrues no interest.
        result=calculate('goal',dict(assets=0,saving=100,months=1,rate='.3'))
        self.assertEqual(won(result['예상 적립액']),100)
        for rate in ('-.2','0','.3'):
            saving=calculate('saving',dict(target=2000000,assets=100000,months=120,rate=rate))['목표 달성 월 저축액']
            final=calculate('goal',dict(assets=100000,saving=saving,months=120,rate=rate))['예상 적립액']
            self.assertLess(abs(final-D(2000000)),D('.000001'))
        self.assertEqual(calculate('saving',dict(target=1,assets=100000,months=12,rate=0))['목표 달성 월 저축액'],0)

    def test_inflation_retirement_and_rounding(self):
        self.assertEqual(calculate('inflation',dict(amount=100,years=2,inflation='.1'))['미래 필요액'],121)
        self.assertEqual(calculate('inflation',dict(amount=100,years=1,inflation='-.1'))['현재 대비 증감액'],-10)
        r=calculate('retirement',dict(age=40,retire=60,end=80,living=200,pension=100,assets=4000,inflation=0))
        self.assertEqual(r['추가 준비액'],20000)
        self.assertEqual(won(D('100.5')),101)
        self.assertEqual(won(D('-100.5')),-101)

    def test_invalid_values_and_resource_limits(self):
        for value in ('NaN','Infinity','-Infinity',-1,10**12+1):
            with self.subTest(value=value),self.assertRaises(ValueError):number(value)
        for value in (1.5,1201,-1):
            with self.assertRaises(ValueError):integer(value)
        with self.assertRaises(ValueError):calculate('total',dict(premium=1,months=2,paid=3))
        with self.assertRaises(ValueError):calculate('goal',dict(assets=0,saving=1,months=1,rate='.31'))
        with self.assertRaises(ValueError):calculate('retirement',dict(age=70,retire=60,end=80,living=1,pension=0,assets=0,inflation=0))
        self.assertTrue(calculate('goal',dict(assets=10**12,saving=10**12,months=1200,rate='.3'))['예상 적립액'].is_finite())

    def test_all_modes_calculate_and_review(self):
        at=opened('quick_calculators')
        self.assertEqual(len(at.radio(key='a_mode').options),13)
        for mode in MODES:
            at.radio(key='a_mode').set_value(mode).run()
            at.button(key='a_calculate').click().run();self.clean(at)
            self.assertEqual(at.session_state['a_calculation']['title'],mode)
            at.button(key='a_approve').click().run();self.clean(at)
            self.assertEqual(len(at.get('download_button')),3)

    def test_stale_result_and_recalculation(self):
        at=opened('quick_calculators')
        at.radio(key='a_mode').set_value('총 납입보험료').run()
        at.button(key='a_calculate').click().run()
        at.button(key='a_approve').click().run()
        self.assertEqual(len(at.get('download_button')),3)
        at.number_input(key='_ws_a_total_premium').set_value(20.0).run()
        self.assertEqual(len(at.get('download_button')),0)
        self.assertTrue(at.warning)
        at.number_input(key='_ws_a_total_premium').set_value(10.0).run()
        self.assertEqual(len(at.get('download_button')),0)
        at.number_input(key='_ws_a_total_premium').set_value(20.0).run()
        at.button(key='a_calculate').click().run()
        self.assertEqual(len(at.get('download_button')),0)
        self.assertEqual(at.session_state['a_calculation']['values']['총 납입 예정'],48000000)

    def test_navigation_draft_reset_and_invalid_input(self):
        at=opened('quick_calculators')
        at.radio(key='a_mode').set_value('총 납입보험료').run()
        at.number_input(key='_ws_a_total_premium').set_value(12.34).run()
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_quick_calculators').click().run()
        self.assertEqual(at.number_input(key='_ws_a_total_premium').value,12.34)
        at.number_input(key='_ws_a_total_paid').set_value(241).run()
        at.button(key='a_calculate').click().run();self.clean(at)
        self.assertTrue(at.warning)
        self.assertNotIn('a_calculation',at.session_state.filtered_state)
        at.button(key='clear_a_').click().run();self.clean(at)
        self.assertNotIn('a_review_token',at.session_state.filtered_state)

    def test_exports_exact_values_and_no_metadata_birth(self):
        r={'title':'가상 계산 검증','values':{'확인 금액':D('1234567.5')},'inputs':[('가상 조건','100만원')],'formula':'가상 산식','assumptions':'가상 조건 검토','prepared_on':'2026-09-22'}
        expected=formatted_results(r['values'])[0][1]
        self.assertEqual(expected,'1,234,568원')
        self.assertIn(expected,export_bytes(r,'txt').decode('utf-8-sig'))
        wb=load_workbook(io.BytesIO(export_bytes(r,'xlsx')))
        self.assertIn(expected,[c.value for row in wb.active for c in row])
        with pdfplumber.open(io.BytesIO(export_bytes(r,'pdf'))) as doc:
            self.assertIn(expected,'\n'.join(p.extract_text() for p in doc.pages))


if __name__=='__main__':unittest.main()
