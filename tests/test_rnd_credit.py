import unittest
from modules import rnd_credit as c
class Rnd(unittest.TestCase):
 def calc(self,**kw):return c.rnd(confirmed='예',**kw).metrics
 def test_source_and_corrected_types(self):
  self.assertEqual(self.calc()['발생 공제액 (사용 한도 적용 전)'],50000000)
  r=self.calc(size=c.SIZES[2]);self.assertEqual(r['증가분 발생 공제액'],12500000);self.assertEqual(r['당기분 발생 공제액'],2000000)
  r=self.calc(size=c.SIZES[1]);self.assertEqual(r['당기분 발생 공제액'],16000000);self.assertEqual(r['증가분 발생 공제액'],20000000)
 def test_average_and_ineligibility(self):
  r=self.calc(prior=100000000,y2=0,y3=0,y4=0);self.assertEqual(r['직전 4년 비용 발생 연도 평균'],100000000)
  self.assertEqual(r['증가분 발생 공제액'],50000000)
  for args in [dict(prior=0,y2=0,y3=0,y4=0),dict(prior=100000000,y2=200000000)]:
   self.assertIsInstance(self.calc(**args)['증가분 발생 공제액'],str)
   with self.assertRaises(ValueError):self.calc(mode='증가분',**args)
 def test_election_and_boundaries(self):
  self.assertEqual(self.calc(current=400000000)['선택 방식'],'증가분')
  self.assertEqual(self.calc(current=400000000,mode='당기분')['발생 공제액 (사용 한도 적용 전)'],100000000)
  self.assertEqual(self.calc(current=0)['발생 공제액 (사용 한도 적용 전)'],0)
  self.assertEqual(self.calc(current=100000000)['증가분 발생 공제액'],0)
  self.assertEqual(self.calc(size=c.SIZES[2],revenue=1000000000)['당기분 공제율'],2)
  for transition,expected in [(c.TRANSITIONS[1],40000000),(c.TRANSITIONS[2],30000000)]:
   self.assertEqual(self.calc(size=c.SIZES[1],transition=transition)['당기분 발생 공제액'],expected)
 def test_guards(self):
  self.assertIsInstance(c.rnd().metrics['발생 공제액 (사용 한도 적용 전)'],str)
  with self.assertRaises(ValueError):self.calc(size=c.SIZES[2],revenue=0)
  with self.assertRaises(ValueError):self.calc(transition=c.TRANSITIONS[1])
  with self.assertRaises(ValueError):self.calc(prior=-1)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(c.NAME).run()
  next(x for x in at.selectbox if x.label==c.FIELDS[c.NAME][-1][0]).select('예').run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  fs=c.FIELDS[c.NAME];v=[x[1] for x in fs];v[-1]='예';txt,csv=build_exports(c.NAME,fs,v,c.calculate(c.NAME,v),'2026-09-27')
  self.assertIn('50,000,000',txt);self.assertIn('증가분',csv.decode('utf-8-sig'))
