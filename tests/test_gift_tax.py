import unittest
from datetime import date
from decimal import Decimal as D
from modules.gift_tax import gift,RELATIONS,SPECIAL,NAME,FIELDS
from modules.gift_planning import distributed,split,optimize,DISTRIBUTE,SPLIT,OPTIMIZE
from modules.transfer_tax_rules import ordinary_tax


class GiftTests(unittest.TestCase):
 def due(self,**kw):return gift(**kw).metrics['이번 증여세 추정액']

 def test_source_observations(self):
  self.assertEqual(self.due(),67900000)
  self.assertEqual(self.due(cash=200000000,relation=RELATIONS[1]),19400000)
  self.assertEqual(self.due(cash=200000000,relation=RELATIONS[1],special=SPECIAL[1],special_request=100000000),4850000)
  self.assertEqual(self.due(cash=200000000,relation=RELATIONS[1],used_regular=50000000,prior_value=100000000,prior_deductions=50000000,prior_base=50000000,prior_tax=5000000),33950000)
  self.assertEqual(self.due(cash=2100000000,relation=RELATIONS[2]),651840000)

 def test_minimum_and_credit_cap(self):
  self.assertEqual(self.due(cash=50499999,relation=RELATIONS[1]),0)
  self.assertEqual(self.due(cash=50500000,relation=RELATIONS[1]),48500)
  r=gift(cash=200000000,relation=RELATIONS[1],used_regular=50000000,prior_value=100000000,prior_deductions=50000000,prior_base=50000000,prior_tax=100000000)
  self.assertEqual(r.metrics['과거 납부세액공제'],8000000)
  # Under 10m prior gifts do not aggregate, but used allowance still matters.
  self.assertEqual(gift(cash=50000000,relation=RELATIONS[1],used_regular=9000000,prior_value=9000000,prior_deductions=9000000).metrics['과세표준'],9000000)

 def test_special_nonresident_and_surcharge(self):
  r=gift(cash=200000000,relation=RELATIONS[1],special=SPECIAL[2],special_request=100000000,used_special=80000000)
  self.assertEqual(r.metrics['이번 혼인·출산 공제'],20000000)
  self.assertEqual(self.due(cash=100000000,resident='아니요'),9700000)
  self.assertEqual(self.due(cash=2100000000,relation=RELATIONS[2],skip='예'),912576000)
  self.assertEqual(self.due(cash=2100000000,relation=RELATIONS[2],skip='예',skip_exception='예'),651840000)
  self.assertEqual(self.due(cash=2000000000,relation=RELATIONS[2],skip='예'),796952000)
  self.assertEqual(self.due(timely='아니요'),70000000)

 def test_invalid_and_dates(self):
  for kw in ({'cash':-1},{'cash':float('nan')},{'debt':1000000001},{'prior_tax':1},
             {'relation':RELATIONS[0],'special_request':1},{'gift_date':'2025-01-01'},
             {'skip':'예'},{'prior_value':100,'prior_base':101}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):gift(**kw)
  self.assertEqual(gift(gift_date=date(2026,11,30)).metrics['법정 신고기한 기준일 (휴일 연장 전)'],'2027-02-28')

 def test_shared_inheritance_brackets(self):
  from modules.inheritance_tax import tax_rate_and_deduction
  for base,expected in ((0,0),(100000000,10000000),(500000000,90000000),(1000000000,240000000),(3000000000,1040000000),(4000000000,1540000000)):
   self.assertEqual(ordinary_tax(base),expected)
   rate,deduction=tax_rate_and_deduction(base/10000)
   self.assertAlmostEqual((base/10000*rate-deduction)*10000,expected,places=2)


class PlanningTests(unittest.TestCase):
 def test_observed_distribution_split_optimal(self):
  r=distributed([(RELATIONS[0],600000000,False),(RELATIONS[1],200000000,False),(RELATIONS[1],200000000,False)])
  self.assertEqual(r.metrics['분산 증여세 합계'],38800000)
  self.assertEqual(split().metrics['분할 증여세 합계'],155200000)
  self.assertEqual(optimize().metrics['분산 증여세 합계'],29100000)
  self.assertEqual([r['증여액'] for r in optimize().rows],[700000000,150000000,150000000])

 def test_planning_edges(self):
  r=split(total=200000001,relation=RELATIONS[2],birth='2016-09-26')
  self.assertEqual(sum(row['증여액'] for row in r.rows),200000001)
  self.assertEqual(r.rows[0]['공제 한도'],20000000)
  self.assertEqual(r.rows[1]['공제 한도'],50000000)
  self.assertEqual(r.rows[1]['계획일'],'2036-09-27')
  # Tax-minimum discontinuity: equal division is worse near 500k.
  r=optimize(total=101400000,spouse='아니요',adults=2)
  self.assertEqual(sum(row['증여액'] for row in r.rows),101400000)
  self.assertEqual(r.metrics['분산 증여세 합계'],D('87300.097'))
  self.assertLess(r.metrics['분산 증여세 합계'],135800)
  for total in (0,1,100000001,1000000001):
   self.assertEqual(sum(row['증여액'] for row in optimize(total=total).rows),total)
  with self.assertRaises(ValueError):optimize(spouse='아니요',adults=0,minors=0)
  with self.assertRaises(ValueError):split(relation=RELATIONS[2],birth='1990-01-01')

 def test_ui_all_modes_and_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run()
  for mode in ('증여세 상세 계산',DISTRIBUTE,SPLIT,OPTIMIZE):
   with self.subTest(mode=mode):
    at.selectbox(key='gift_mode').select(mode).run()
    at.button[0].click().run()
    self.assertFalse(at.exception);self.assertFalse(at.error)
    self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
  txt,csv=build_exports(NAME,FIELDS[NAME],[f[1] for f in FIELDS[NAME]],gift(),'2026-09-26')
  self.assertIn('67,900,000원',txt);self.assertIn('67,900,000원',csv.decode('utf-8-sig'))
  self.assertIn('4촌',txt)
