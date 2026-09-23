"""Independent arithmetic examples for preserved rules, not legal validation."""
import unittest
from modules.deposit_vs_shortpay import calculate_deposit
from modules.summer import get_summer_grade
from modules.renewal_vs_nonrenewal import _calculate_periods
from modules.remodeling import Person, NewPlan, create_excel
from openpyxl import load_workbook
from datetime import date


class LegacyBoundaryTests(unittest.TestCase):
    def test_deposit_simple_interest_in_manwon(self):
        result=calculate_deposit(10,3)
        self.assertAlmostEqual(result['pretax_interest'],1.95)
        self.assertAlmostEqual(result['aftertax_interest'],1.6497)
        self.assertAlmostEqual(result['ten_year_interest'],16.497)

    def test_summer_strict_top_grade_boundary(self):
        self.assertEqual(get_summer_grade(15_000_000)[0],'크라운')
        self.assertEqual(get_summer_grade(15_000_001)[0],'HWARANG')
        self.assertEqual(get_summer_grade(2_999_999)[0],'미달성')
        self.assertEqual(get_summer_grade(3_000_000)[0],'일반')

    def test_renewal_last_period_clipped(self):
        periods=_calculate_periods(40,57,10,5,10000,'가입제안서 직접 입력','',[20000,30000])
        self.assertEqual([(p.start_age,p.end_age,p.monthly_premium) for p in periods],[(40,45,10000),(45,55,20000),(55,57,30000)])
        self.assertEqual(sum((p.end_age-p.start_age)*12*p.monthly_premium for p in periods),3720000)

    def test_remodeling_custom_months_and_workbook(self):
        person=Person('가상고객',100000,20000000,30000,6000000,[NewPlan('가상안',20000,20,120)])
        self.assertEqual(person.after_monthly,50000)
        self.assertEqual(person.after_total,8400000)
        self.assertEqual(person.monthly_change,-50000)
        workbook=load_workbook(create_excel([person],'가상 검토',date(2026,9,23),'가상담당'))
        self.assertGreaterEqual(len(workbook.worksheets),2)
        self.assertTrue(workbook.worksheets[0].print_area)
