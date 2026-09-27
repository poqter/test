import unittest
from decimal import Decimal as D
from modules.pension_models import PensionPlan,calculate
class PensionTests(unittest.TestCase):
 def test_source_baseline_reconciliation(self):
  r=calculate(PensionPlan());m=r.metrics
  self.assertLess(abs(m['은퇴시점 예상자산 (오늘 가치)']-D(223141845)),D('.51'))
  # Source includes a pension payment at month60, our first full month is61.
  post=(D('1.035')/D('1.025'))**(D(1)/12)-1
  corrected=D(656503352)+D(1100000)/(1+post)**60
  self.assertLess(abs(m['은퇴시점 필요자산 (오늘 가치)']-corrected),D('.51'))
 def test_zero_rates_exact_payment_count(self):
  r=calculate(PensionPlan(before_rate=0,after_rate=0,inflation=0,pension_growth=0))
  self.assertEqual(r.metrics['은퇴시점 필요자산 (오늘 가치)'],750000000)
  self.assertEqual(r.metrics['은퇴시점 예상자산 (오늘 가치)'],170000000)
 def test_no_pension_source(self):
  r=calculate(PensionPlan(pension=0))
  self.assertLess(abs(r.metrics['은퇴시점 필요자산 (오늘 가치)']-D(936558364)),D('.51'))
 def test_direct_and_fully_funded(self):
  r=calculate(PensionPlan(direct=1000000000));self.assertEqual(r.metrics['부족액'],0)
  self.assertEqual(r.metrics['자금 소진 나이'],'기간 내 소진 없음')
 def test_immediate_retirement_and_zero_rates(self):
  r=calculate(PensionPlan(age=60,retire=60,extra_years=0))
  self.assertEqual(r.metrics['추가 월 저축액'],'은퇴시점 목돈 보완 필요')
 def test_invalid(self):
  for p in [PensionPlan(age=61),PensionPlan(saving_years=16),PensionPlan(pension_start=71),PensionPlan(expense=-1),PensionPlan(before_rate=float('nan'))]:
   with self.assertRaises(ValueError):calculate(p)
 def test_required_contribution_funds_plan(self):
  r=calculate(PensionPlan());needed=r.metrics['추가 월 저축액']
  funded=calculate(PensionPlan(extra=needed));self.assertLess(abs(funded.rows[-1]['추가 납입 후 잔액']),D('.01'))
 def test_observed_direct_future_early_late(self):
  rate=(D('1.035')/D('1.025'))**(D(1)/12)-1
  for plan,source,correction in [(PensionPlan(direct=200000000),656503352,D(1100000)/(1+rate)**60),(PensionPlan(direct=200000000,expense_future=True),366606280,D(1100000)/(1+rate)**60),(PensionPlan(direct=200000000,pension_start=60),696175051,D(0)),(PensionPlan(direct=200000000,pension_start=70),639181827,D(1496000)/(1+rate)**120)]:
   r=calculate(plan)
   self.assertEqual(r.metrics['은퇴시점 예상자산 (오늘 가치)'],200000000)
   self.assertLess(abs(r.metrics['은퇴시점 필요자산 (오늘 가치)']-source-correction),D('.51'))
