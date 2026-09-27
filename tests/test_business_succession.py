import unittest
from modules import business_succession as b
class Succession(unittest.TestCase):
 def test_general_source_reconcile(self):
  for value,raw,source in [(3920000000,1475000000,1430750000),(2800000000,940000000,911800000)]:
   self.assertEqual(b.succession(value=value,no_prior='예').metrics['일반 증여 산출세액'],raw);self.assertEqual(b.D(raw)*b.D('.97'),source)
 def test_special_band(self):
  for v,t in [(1000000000,0),(13000000000,1200000000),(13000000001,b.D('1200000000.2'))]:self.assertEqual(b.succession(value=v,eligible='예').metrics['가업승계 증여특례 산출세액'],t)
 def test_limits_and_guard(self):
  for years,cap in [(9,0),(10,30000000000),(19,30000000000),(20,40000000000),(30,60000000000)]:self.assertEqual(b.succession(years=years).metrics['업력별 법정 한도'],cap)
  for kw in ({'parent':59},{'child':17},{'years':9},{'value':30000000001}):
   with self.assertRaises(ValueError):b.succession(eligible='예',**kw)
  self.assertIsInstance(b.succession().metrics['가업승계 증여특례 산출세액'],str)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(b.NAME).run()
  for label in ('일반 증여: 과거 증여·사용 공제 없음 확인','특례: 최초 단일 수증자·전액 가업자산·모든 적격요건 확인'):next(x for x in at.selectbox if x.label==label).select('예').run()
  at.button[0].click().run();self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(next(x.value for x in at.metric if x.label=='가업승계 증여특례 산출세액'),'292,000,000원')
  fs=b.FIELDS[b.NAME];v=[x[1] for x in fs];v[4]=v[5]='예';txt,csv=build_exports(b.NAME,fs,v,b.calculate(b.NAME,v),'2026-09-26');self.assertIn('292,000,000원',txt);self.assertIn('292,000,000원',csv.decode('utf-8-sig'))
