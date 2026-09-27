import unittest
from modules import patent_capitalization as p
class Patent(unittest.TestCase):
 def calc(self,**kw):return p.patent(confirmed='예',**kw).metrics
 def test_source_comparison(self):
  self.assertEqual(self.calc(deductions=0)['특허 양도 국세 산출세액 증가']*p.D('1.1'),29216000)
  self.assertEqual(self.calc(deductions=0,other=50000000)['특허 양도 국세 산출세액 증가']*p.D('1.1'),42262000)
 def test_expenses_and_salary(self):
  r=self.calc(cost=240000000);self.assertEqual(r['특허 기타소득금액'],60000000)
  self.assertLess(self.calc(deductions=0)['같은 금액 급여 국세 산출세액 증가'],p.progressive_tax(300000000))
 def test_corporate_and_guards(self):
  self.assertEqual(self.calc(amortization=30000000,corp_base=500000000,corp_confirmed='예')['법인 당기 국세 산출세액 감소'],6000000)
  self.assertIsInstance(p.patent().metrics['특허 양도 국세 산출세액 증가'],str)
  with self.assertRaises(ValueError):p.patent(cost=300000001)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(p.NAME).run()
  next(x for x in at.selectbox if x.label=='개인 소유·적정 대가·기타소득 분류·과세 방식 확인').select('예').run();at.button[0].click().run();self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  fs=p.FIELDS[p.NAME];v=[x[1] for x in fs];v[5]='예';txt,csv=build_exports(p.NAME,fs,v,p.calculate(p.NAME,v),'2026-09-27');self.assertIn('특허 양도 국세',txt);self.assertIn('특허 양도 국세',csv.decode('utf-8-sig'))

class SmallPatent(unittest.TestCase):
 def test_exemption_and_separate_threshold(self):
  self.assertEqual(p.patent(price=125000,confirmed='예').metrics['과세 대상 기타소득금액'],0)
  self.assertGreater(p.patent(price=125001,confirmed='예').metrics['과세 대상 기타소득금액'],50000)
  r=p.patent(price=7500000,confirmed='예',mode=p.MODES[1])
  self.assertEqual(r.metrics['특허 양도 국세 산출세액 증가'],600000)
  with self.assertRaises(ValueError):p.patent(price=7500001,confirmed='예',mode=p.MODES[1])
  with self.assertRaises(ValueError):p.patent(price=7500000,confirmed='예',mode=p.MODES[1],other_optional=1)
