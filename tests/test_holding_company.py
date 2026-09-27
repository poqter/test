import unittest
from modules import holding_company as h
class Holding(unittest.TestCase):
 def calc(self,**kw):return h.holding(status=h.STATUS[1],adjusted='예',**kw).metrics
 def test_rate_boundaries(self):
  for share,amount in [(19,60000000),(20,160000000),(49.99,160000000),(50,200000000),(80,200000000)]:self.assertEqual(self.calc(share=share)['익금불산입액'],amount)
 def test_interest_floor(self):
  self.assertEqual(self.calc(share=20,interest=100000000,stock_days=100,asset_days=1000)['익금불산입액'],152000000)
  self.assertEqual(self.calc(interest=1000000000,stock_days=1000,asset_days=1000)['익금불산입액'],0)
 def test_progressive_saving(self):
  self.assertEqual(self.calc(share=20,base_confirmed='예')['국세 산출세액 절감 추정'],32000000)
  self.assertEqual(self.calc(share=20,income=300000000,base_confirmed='예')['국세 산출세액 절감 추정'],26000000)
  self.assertEqual(self.calc(income=0,loss=100000000,base_confirmed='예')['국세 산출세액 절감 추정'],0)
 def test_excluded_unknown_invalid(self):
  self.assertIsInstance(h.holding().metrics['익금불산입액'],str)
  self.assertEqual(h.holding(status=h.STATUS[2]).metrics['익금불산입액'],0)
  for kw in ({'rule':h.RULES[1]},{'interest':1},{'share':101},{'income':1,'loss':1}):
   with self.assertRaises(ValueError):h.holding(**kw)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(h.NAME).run()
  for label,value in [('배당 유형·법인·보유기간의 적용 대상 여부',h.STATUS[1]),('이자·적수 및 조정항목 확인','예')]:next(x for x in at.selectbox if x.label==label).select(value).run()
  at.button[0].click().run();self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(next(x.value for x in at.metric if x.label=='익금불산입액'),'200,000,000원')
  fs=h.FIELDS[h.NAME];v=[x[1] for x in fs];v[3]=h.STATUS[1];v[7]='예';txt,csv=build_exports(h.NAME,fs,v,h.calculate(h.NAME,v),'2026-09-27');self.assertIn('200,000,000원',txt);self.assertIn('200,000,000원',csv.decode('utf-8-sig'))
