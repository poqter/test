import unittest
from modules import specific_corp_transaction as s
from modules import family_corp_gift as f
class Specific(unittest.TestCase):
 def calc(self,**kw):return s.transaction(confirmed='예',**kw).metrics
 def test_tax_cap(self):
  r=self.calc()
  self.assertEqual(r['배분 법인세 상당액'],180000000)
  self.assertEqual(r['주주 증여의제이익'],328000000)
  self.assertEqual(r['한도 적용 전 증여세'],45600000)
  self.assertEqual(r['직접증여 가정 증여세'],60000000)
  self.assertEqual(r['특정법인 거래 증여세 추정'],0)
  r=self.calc(corporate_tax=50000000)
  self.assertEqual(r['한도 적용 전 증여세'],56000000)
  self.assertEqual(r['증여세 한도'],40000000)
  self.assertEqual(r['특정법인 거래 증여세 추정'],38800000)
 def test_thresholds(self):
  for amount,expected in ((99999999,'미충족'),(100000000,'충족')):
   self.assertEqual(self.calc(value=amount,share=100,corporate_tax=0)['과세 진입기준'],expected)
  self.assertEqual(self.calc(group_share=29,share=29)['과세 진입기준'],'미충족')
  self.assertEqual(self.calc(group_share=30,share=30,corporate_tax=0)['과세 진입기준'],'충족')
  for paid,expected in ((700000001,'미충족'),(700000000,'충족')):
   self.assertEqual(self.calc(kind=s.KINDS[1],paid=paid,corporate_tax=0,share=100)['과세 진입기준'],expected)
 def test_losses_and_inputs(self):
  self.assertEqual(self.calc(corporate_income=0,corporate_tax=0)['배분 법인세 상당액'],0)
  for kw in ({'corporate_income':0},{'group_share':20},{'paid':1},{'value':-1}):
   with self.assertRaises(ValueError):self.calc(**kw)
 def test_ui(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(f.NAME).run()
  next(x for x in at.selectbox if x.label=='적용 제도').select('특정법인 거래 (45조의5)').run()
  next(x for x in at.selectbox if x.label==s.FIELDS[-1][0]).select('예').run()
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(x.value for x in at.metric if x.label=='주주 증여의제이익'),'328,000,000원')
  values=[x[1] for x in f.FIELDS[f.NAME]];values[0]='특정법인 거래 (45조의5)';values[-1]='예'
  r=f.calculate(f.NAME,values);txt,csv=build_exports(f.NAME,f.FIELDS[f.NAME],values,r,'2026-09-27')
  self.assertIn('328,000,000',txt);self.assertIn('328,000,000',csv.decode('utf-8-sig'))
