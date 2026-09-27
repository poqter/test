import unittest
from modules.capital_gains_tax import gains,NAME,FIELDS,SCOPE
from modules.finance_models import D

class CapitalTests(unittest.TestCase):
 def test_source_standard_and_short(self):
  self.assertEqual(gains().metrics['양도세 추정 합계 (지방세 포함)'],107646000)
  self.assertEqual(gains(acquire='2026-01-01').metrics['양도세 추정 합계 (지방세 포함)'],213125000)
 def test_correct_unregistered_source_discrepancy(self):
  r=gains(unregistered='예')
  self.assertEqual(r.metrics['장기보유특별공제'],0)
  self.assertEqual(r.metrics['과세표준'],390000000)
  self.assertEqual(r.metrics['양도세 추정 합계 (지방세 포함)'],300300000)
 def test_calendar_boundaries_and_nonbusiness(self):
  self.assertEqual(gains(acquire='2023-09-26').metrics['장기보유 공제율'],6)
  self.assertEqual(gains(acquire='2023-09-27').metrics['장기보유 공제율'],0)
  self.assertEqual(gains(acquire='2000-01-01').metrics['장기보유 공제율'],30)
  r=gains(asset='토지',nonbusiness='예')
  self.assertEqual(r.metrics['소득세'],128810000)
  # Short nonbusiness land: choose max rather than adding rates.
  self.assertEqual(gains(asset='토지',nonbusiness='예',acquire='2026-01-01').metrics['소득세'],193750000)
 def test_high_price_exempt_loss(self):
  r=gains(asset='주택',qualified='예',sale=2000000000,cost=1000000000,expenses=0,residence=10)
  self.assertEqual(r.metrics['과세 대상 양도차익'],400000000)
  self.assertEqual(r.metrics['장기보유특별공제'],320000000)
  self.assertEqual(r.metrics['소득세'],12840000)
  self.assertEqual(gains(asset='주택',qualified='예',sale=1200000000).metrics['소득세'],0)
  self.assertEqual(gains(sale=100000000).metrics['양도차익'],-510000000)
  self.assertEqual(gains(sale=100000000).metrics['소득세'],0)
 def test_unsupported_and_invalid(self):
  for kw in ({'scope':SCOPE[1]},{'asset':'주택','houses':2,'regulated':'예'},{'designated':'예'},
             {'qualified':'예'},{'sale':float('nan')},{'basic':2500001},{'residence':11},
             {'transfer':'2027-01-01'},{'acquire':'2026-09-27'},{'nonbusiness':'예'}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):gains(**kw)
 def test_center_and_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(m.value for m in at.metric if m.label=='양도세 추정 합계 (지방세 포함)'),'107,646,000원')
  self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
  txt,csv=build_exports(NAME,FIELDS[NAME],[f[1] for f in FIELDS[NAME]],gains(),'2026-09-26')
  self.assertIn('107,646,000원',txt);self.assertIn('107,646,000원',csv.decode('utf-8-sig'))
