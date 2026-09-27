import unittest
from modules import employment_credit as e
class Employment(unittest.TestCase):
 def value(self,**kw):return e.employment(confirmed='예',**kw).metrics['2026년 신규 기본공제 산출액']
 def test_source_sme(self):
  self.assertEqual(self.value(),21000000);self.assertEqual(self.value(young_current=3),24000000);self.assertEqual(self.value(region='수도권',young_current=3),15000000)
 def test_non_sme_thresholds(self):
  self.assertEqual(self.value(kind='중견기업',current=15),0);self.assertEqual(self.value(kind='중견기업',current=16),3000000)
  self.assertEqual(self.value(kind='대기업 등',current=20,young_current=12),0);self.assertEqual(self.value(kind='대기업 등',current=21,young_current=13),3000000)
  self.assertEqual(self.value(kind='중견기업',current=16,young_current=8),5000000)
 def test_turnover_and_fraction(self):
  self.assertEqual(self.value(current=10,young_current=5),0)
  self.assertEqual(self.value(current=11,young_current=5),10000000)
  self.assertEqual(self.value(current=10.5),3500000)
 def test_guards(self):
  self.assertIsInstance(e.employment().metrics['2026년 신규 기본공제 산출액'],str)
  with self.assertRaises(ValueError):e.employment(young_current=14)
 def test_ui_and_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(e.NAME).run()
  next(x for x in at.selectbox if x.label=='업종·규모·근로자 자격·연평균 및 2026 신규공제 요건 확인').select('예').run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(next(x.value for x in at.metric if x.label=='2026년 신규 기본공제 산출액'),'21,000,000원')
  f=e.FIELDS[e.NAME];v=[x[1] for x in f];v[-1]='예';txt,csv=build_exports(e.NAME,f,v,e.calculate(e.NAME,v),'2026-09-27');self.assertIn('21,000,000원',txt);self.assertIn('21,000,000원',csv.decode('utf-8-sig'))
