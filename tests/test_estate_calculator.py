import unittest
from modules.estate_calculator import estate,NAME,FIELDS


class EstateTests(unittest.TestCase):
 def test_source_cases_and_funeral(self):
  self.assertEqual(estate().metrics['상속세 추정액'],86330000)
  r=estate(gross=2000000000,spouse='예',spouse_actual=800000000,spouse_confirmed='예')
  self.assertEqual(r.metrics['상속세 추정액'],144045000)
  self.assertEqual(r.metrics['배우자 공제'],800000000)
  self.assertEqual(estate(funeral=0).metrics['장례비용 공제'],5000000)
  self.assertEqual(estate(funeral=50000000,burial=8000000).metrics['장례비용 공제'],15000000)

 def test_prior_limit_500m_exception_shared_engine(self):
  # 395m current +100m prior -5m funeral=490m: don't subtract prior
  # gifts from the deduction ceiling below the statutory 500m boundary.
  r=estate(gross=395000000,prior_heirs=100000000,prior_limit=50000000)
  self.assertEqual(r.metrics['상속세 추정액'],0)
  r=estate(gross=406000000,prior_heirs=100000000,prior_limit=50000000)
  self.assertEqual(r.metrics['과세표준'],50000000)
  self.assertEqual(r.metrics['상속세 추정액'],4850000)

 def test_spouse_solo_financial_and_validation(self):
  r=estate(gross=1000000000,children=0,spouse='예',group='배우자 단독',coheirs=0)
  self.assertEqual(r.metrics['과세표준'],295000000)
  r=estate(financial_assets=500000000,debt=100000000,financial_debt=100000000)
  self.assertEqual(r.metrics['금융재산 공제'],80000000)
  self.assertEqual(r.metrics['과세표준'],315000000)
  for kw in ({'financial_debt':1},{'spouse':'예','spouse_actual':800000000},
             {'prior_limit':1},{'gross':float('inf')},{'start':'2025-01-01'},
             {'spouse_actual':1},{'financial_assets':1000000001}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):estate(**kw)

 def test_center_and_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run()
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(m.value for m in at.metric if m.label=='상속세 추정액'),'86,330,000원')
  self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
  txt,csv=build_exports(NAME,FIELDS[NAME],[f[1] for f in FIELDS[NAME]],estate(),'2026-09-26')
  self.assertIn('86,330,000원',txt);self.assertIn('86,330,000원',csv.decode('utf-8-sig'))
