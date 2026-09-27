import unittest
from modules import corp_real_estate as c
class Estate(unittest.TestCase):
 def calc(self,extra=c.EXTRA[1],**kw):return c.estate(extra=extra,confirmed='예',**kw)
 def test_observed_cases(self):
  for asset,extra,expected in [(c.ASSETS[0],c.EXTRA[1],88000000),('토지',c.EXTRA[1],88000000),('주택',c.EXTRA[2],198000000)]:
   r=self.calc(asset=asset,extra=extra).metrics
   self.assertEqual(r['개인 매각 국세 추정']*c.D('1.1'),168366000)
   self.assertEqual(r['법인 매각 국세 증가 추정']*c.D('1.1'),expected)
 def test_incremental_and_book_value(self):
  self.assertEqual(self.calc(corp_base=500000000).metrics['법인 일반 법인세 증가'],100000000)
  r=self.calc(asset='주택',extra=c.EXTRA[2],book=900000000,corp_expenses=20000000).metrics
  self.assertEqual(r['법인 일반 법인세 증가'],96000000)
  self.assertEqual(r['법인 토지등 양도 추가세액'],120000000)
  r=self.calc(asset='토지',extra=c.EXTRA[3],nonbusiness='예').metrics
  self.assertEqual(r['법인 토지등 양도 추가세액'],50000000)
  self.assertEqual(r['개인 매각 국세 추정'],197810000)
 def test_personal_exemption_and_dates(self):
  r=self.calc(asset='주택',extra=c.EXTRA[2],qualified='예',residence=5).metrics
  self.assertLess(r['개인 매각 국세 추정'],153060000)
  self.assertGreater(self.calc(acquire='2026-01-01').metrics['개인 매각 국세 추정'],153060000)
  with self.assertRaises(ValueError):self.calc(transfer='2025-09-27')
 def test_guards(self):
  self.assertIsInstance(c.estate().metrics['매각 국세 비교'],str)
  with self.assertRaises(ValueError):self.calc(extra=c.EXTRA[2])
  self.assertEqual(self.calc(book=1600000000).metrics['법인 일반 법인세 증가'],0)
  self.assertEqual(self.calc(book=1600000000,corp_base=500000000).metrics['법인 일반 법인세 증가'],-20000000)
  self.assertEqual(self.calc(book=1800000000,corp_base=100000000).metrics['법인 일반 법인세 증가'],-10000000)
  with self.assertRaises(ValueError):self.calc(sale=-1)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(c.NAME).run()
  next(x for x in at.selectbox if x.label==c.FIELDS[c.NAME][9][0]).select(c.EXTRA[1]).run()
  next(x for x in at.selectbox if x.label==c.FIELDS[c.NAME][-1][0]).select('예').run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  fs=c.FIELDS[c.NAME];v=[x[1] for x in fs];v[9]=c.EXTRA[1];v[-1]='예';txt,csv=build_exports(c.NAME,fs,v,c.calculate(c.NAME,v),'2026-09-27')
  self.assertIn('153,060,000',txt);self.assertIn('매각 일반소득',csv.decode('utf-8-sig'))
