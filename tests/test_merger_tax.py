import unittest
from modules import merger_tax as m
class Merger(unittest.TestCase):
 def test_source_national(self):self.assertEqual(m.merger().metrics['합병에 따른 국세 산출세액 증감'],380000000)
 def test_actual_price_liability(self):
  r=m.merger(consideration=4000000000,liabilities=1000000000).metrics
  self.assertEqual(r['순자산 장부가액'],2000000000);self.assertEqual(r['비적격 가정 양도손익'],2000000000)
 def test_incremental_and_short_period(self):
  self.assertEqual(m.merger(income=200000000).metrics['합병에 따른 국세 산출세액 증감'],400000000)
  self.assertEqual(m.merger(months=6).metrics['합병에 따른 국세 산출세액 증감'],390000000)
  self.assertEqual(m.merger(small='예').metrics['합병에 따른 국세 산출세액 증감'],400000000)
 def test_loss_and_qualified(self):
  self.assertEqual(m.merger(loss=3000000000).metrics['합병에 따른 국세 산출세액 증감'],0)
  self.assertEqual(m.merger(consideration=2000000000,income=500000000).metrics['합병에 따른 국세 산출세액 증감'],-80000000)
  self.assertEqual(m.merger(mode=m.MODES[1],income=500000000).metrics['합병에 따른 국세 산출세액 증감'],0)
  for kw in ({'months':0},{'months':13},{'income':1,'loss':1},{'assets':-1}):
   with self.assertRaises(ValueError):m.merger(**kw)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(m.NAME).run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(next(x.value for x in at.metric if x.label=='합병에 따른 국세 산출세액 증감'),'380,000,000원')
  f=m.FIELDS[m.NAME];v=[x[1] for x in f];txt,csv=build_exports(m.NAME,f,v,m.calculate(m.NAME,v),'2026-09-26');self.assertIn('380,000,000원',txt);self.assertIn('380,000,000원',csv.decode('utf-8-sig'))
