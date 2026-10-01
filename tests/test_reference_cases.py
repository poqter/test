"""Independent arithmetic references and boundaries for stated existing models.

These checks re-derive expected values without calling the engine under test
for the expected side. Tax examples test the source's declared rate schedule,
not whether that schedule is legally applicable to every real taxpayer.
"""
import unittest
from datetime import date
from decimal import Decimal as D, localcontext
from tests.streamlit_stub import install
install()
from modules.calculators.calculator_core import calculate
from modules.calculators.finance import finance_models as f
from modules.calculators.tax.personal_tax_models import progressive_tax
from modules.calculators.tax.global_income_tax import comprehensive,STANDARD
from modules.calculators.quick_calculators import age_result

class ReferenceCases(unittest.TestCase):
    def test_total_premiums_independent(self):
        for premium in (0,1,123456,100000):
            for total,paid in ((1,0),(120,12),(240,240)):
                with self.subTest(premium=premium,total=total,paid=paid):
                    r=calculate('total',dict(premium=premium,months=total,paid=paid))
                    self.assertEqual(r,{'총 납입 예정':D(premium*total),'기납입 추정':D(premium*paid),'향후 납입 예정':D(premium*(total-paid))})
    def test_waiver_independent(self):
        for p,m,ratio in ((123456,120,50),(1,1,100),(100000,0,100),(100000,120,0),(123456,7,D('12.5'))):
            self.assertEqual(calculate('waiver',dict(premium=p,months=m,ratio=ratio))['조건 충족 가정 시 면제액'],D(p)*m*ratio/100)
    def test_family_and_debt_independent(self):
        self.assertEqual(calculate('family',dict(living=2500000,years=10,assets=50000000)),{'생활자금 필요액':D(300000000),'추가 준비액':D(250000000)})
        self.assertEqual(calculate('debt',dict(debt=123456,assets=23456))['부채 정리 부족액'],100000)
        self.assertEqual(calculate('debt',dict(debt=1,assets=2))['부채 정리 부족액'],0)
    def test_education_sum_without_annuity_helper(self):
        for rate in (D(0),D('.02'),D('-.01')):
            with localcontext() as ctx:
                ctx.prec=60
                expected=sum(D(10000000)*(1+rate)**year for year in (10,11,12,13))
                actual=calculate('education',dict(annual=10000000,years=4,wait=10,inflation=rate,assets=0))['예상 교육비 총액']
                self.assertEqual(actual,expected)
    def test_zero_rate_saving_and_goal(self):
        r=calculate('saving',dict(target=100000000,assets=10000000,months=120,rate=0))
        self.assertEqual(r['목표 달성 월 저축액'],750000)
        r=calculate('goal',dict(assets=10000000,saving=500000,months=120,rate=0))
        self.assertEqual(r['예상 적립액'],70000000)
    def test_inflation_known_two_periods(self):
        self.assertEqual(calculate('inflation',dict(amount=1000000,years=2,inflation=D('.1')))['미래 필요액'],1210000)
    def test_future_value_by_cashflow_enumeration(self):
        for beginning in (True,False):
            expected=D(1000000)*D('1.05')**3+sum(D(120000)*D('1.05')**(k+(1 if beginning else 0)) for k in range(3))
            actual=f.future_value(principal=1000000,annual_payment=120000,years=3,rate=5,beginning=beginning)
            self.assertLess(abs(actual.metrics['예상 최종 자금']-expected),D('.00001'))
    def test_rate_and_period_inverse_known_reference(self):
        r=f.tvm('rate',principal=1000000,payment=0,target=1210000,years=2,frequency=1)
        self.assertLess(abs(r.metrics['필요 연 수익률']-10),D('1e-20'))
        r=f.tvm('period',principal=0,payment=100000,target=250000,years=1,rate=0,frequency=12)
        self.assertEqual(r.metrics['필요 납입 횟수'],3)
    def test_present_value_known(self):
        result=f.present_value(mode='lump',amount=1210000,years=2,rate=10)
        self.assertEqual(next(iter(result.metrics.values())),1000000)
    def test_progressive_schedule_independent_segment_sum(self):
        # Existing source schedule, independently accumulated bands (won).
        bands=((14000000,D('.06')),(50000000,D('.15')),(88000000,D('.24')),(150000000,D('.35')),(300000000,D('.38')),(500000000,D('.40')),(1000000000,D('.42')),(10**12,D('.45')))
        for limit,_ in bands[:-1]:
            for value in (limit-1,limit,limit+1):
                remaining=D(value);last=0;expected=D(0)
                for upper,rate in bands:
                    taxable=max(D(0),min(remaining,D(upper-last)))
                    expected+=taxable*rate;remaining-=taxable;last=upper
                self.assertEqual(progressive_tax(value),expected)
    def test_confirmed_tax_credit_keeps_exact_reference_difference(self):
        common=dict(revenue=80000000,expenses=30000000,wage=10000000,standard=STANDARD[3])
        a=comprehensive(**common,earned_credit=55000)
        b=comprehensive(**common,earned_credit=60000)
        self.assertEqual(a.metrics['예상 결정세액 (국세+지방세)']-b.metrics['예상 결정세액 (국세+지방세)'],5500)
    def test_missing_prepaid_is_not_zero_refund(self):
        a=comprehensive(prepaid='');b=comprehensive(prepaid='0')
        self.assertIsInstance(a.metrics['추가 납부 예상액'],str)
        self.assertIsInstance(b.metrics['추가 납부 예상액'],D)
    def test_invalid_bounds_are_rejected(self):
        cases=[('total',dict(premium=100,months=12,paid=13)),('waiver',dict(premium=1,months=1,ratio=101)),('saving',dict(target=1,assets=0,months=0,rate=0)),('family',dict(living=1,years=1.5,assets=0)),('total',dict(premium=float('nan'),months=12,paid=0)),('retirement',dict(age=65,retire=60,end=80,living=1,pension=0,assets=0,inflation=0))]
        for kind,values in cases:
            with self.subTest(kind=kind),self.assertRaises(ValueError):calculate(kind,values)
    def test_age_six_month_boundary(self):
        a=age_result(date(1990,1,1),date(2026,6,30))
        b=age_result(date(1990,1,1),date(2026,7,1))
        self.assertEqual(a[:2],(36,36));self.assertEqual(b[:2],(36,37))

if __name__=='__main__':unittest.main(verbosity=2)
