import unittest
from modules import family_corp_gift as f
class FamilyCorp(unittest.TestCase):
 def test_three_size_formulas(self):
  for kind,benefit,tax in zip(f.KINDS,(15000000,70000000,110000000),(1500000,7000000,12000000)):
   r=f.allocation(kind=kind,confirmed='예',timely='아니요').metrics
   self.assertEqual(r['배당공제 전 증여의제이익'],benefit)
   self.assertEqual(r['증여세 산출세액'],tax)
   self.assertEqual(f.allocation(kind=kind,confirmed='예').metrics['일감몰아주기 증여세 추정'],f.D(tax)*f.D('.97'))
 def test_strict_thresholds(self):
  for kind,trade,share in [(f.KINDS[0],50,40),(f.KINDS[0],60,10),(f.KINDS[1],40,40),(f.KINDS[1],60,10),(f.KINDS[2],30,40),(f.KINDS[2],60,3)]:
   self.assertEqual(f.allocation(kind=kind,trade=trade,share=share,confirmed='예').metrics['증여세 과세표준'],0)
 def test_large_extra_sales_trigger(self):
  self.assertEqual(f.allocation(kind=f.KINDS[2],trade=25,sales=100000000000,confirmed='예').metrics['증여세 과세표준'],0)
  self.assertEqual(f.allocation(kind=f.KINDS[2],trade=25,sales=100000000001,confirmed='예').metrics['증여세 과세표준'],40000000)
  self.assertEqual(f.allocation(kind=f.KINDS[2],trade=20,sales=100000000001,confirmed='예').metrics['증여세 과세표준'],0)
 def test_dividend_offset_and_floor(self):
  r=f.allocation(confirmed='예',dividend=20000000,available=100000000,div_confirmed='예').metrics
  self.assertEqual(r['적용 배당소득 공제'],7500000)
  self.assertEqual(r['증여세 과세표준'],7500000)
  r=f.allocation(confirmed='예',dividend=80000000,available=100000000,div_confirmed='예').metrics
  self.assertEqual(r['증여세 과세표준'],0)
  self.assertEqual(f.allocation(confirmed='예',profit=1000000).metrics['증여세 산출세액'],0)
 def test_unknown_and_invalid(self):
  self.assertIsInstance(f.allocation().metrics['일감몰아주기 증여세 추정'],str)
  for kw in ({'regime':'특정법인 거래 (45조의5, 검증 중)'},{'indirect':'예'},{'trade':101},{'trade':0},{'trade':60,'sales':0},{'dividend':1},{'profit':-1}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):f.allocation(**kw)
 def test_ui_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(f.NAME).run()
  next(x for x in at.selectbox if x.label=='지배주주·친족 및 기업 규모·조정 수치 확인').select('예').run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(next(x.value for x in at.metric if x.label=='일감몰아주기 증여세 추정'),'1,455,000원')
  fs=f.FIELDS[f.NAME];vs=[x[1] for x in fs];vs[6]='예'
  txt,csv=build_exports(f.NAME,fs,vs,f.calculate(f.NAME,vs),'2026-09-26')
  self.assertIn('1,455,000원',txt);self.assertIn('1,455,000원',csv.decode('utf-8-sig'))
