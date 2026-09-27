import unittest
from modules import acquisition_tax as c
class Acquisition(unittest.TestCase):
 def test_source_cases(self):
  for kind,regime,expected in [(c.KINDS[0],c.REGIMES[1],32000000),(c.KINDS[0],c.REGIMES[2],64000000),(c.KINDS[1],c.REGIMES[3],96000000)]:
   r=c.acquisition(kind=kind,regime=regime,confirmed='예').metrics
   self.assertEqual(r['취득세 본세'],expected)
   self.assertEqual(r['4% 기준 대비 추가 본세'],expected-32000000)
 def test_land_zero_and_invalid(self):
  self.assertEqual(c.acquisition(base=0,kind=c.KINDS[2],regime=c.REGIMES[1],confirmed='예').metrics['취득세 본세'],0)
  with self.assertRaises(ValueError):c.acquisition(base=-1)
  with self.assertRaises(ValueError):c.acquisition(kind='주택',regime=c.REGIMES[1],confirmed='예')
  with self.assertRaises(ValueError):c.acquisition(regime=c.REGIMES[3],confirmed='예')
 def test_unconfirmed(self):
  self.assertIsInstance(c.acquisition().metrics['취득세 본세'],str)
  self.assertIsInstance(c.acquisition(regime=c.REGIMES[2]).metrics['취득세 본세'],str)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run();at.selectbox(key='jc_selected').select(c.NAME).run()
  next(x for x in at.selectbox if x.label==c.FIELDS[c.NAME][2][0]).select(c.REGIMES[2]).run()
  next(x for x in at.selectbox if x.label==c.FIELDS[c.NAME][3][0]).select('예').run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  fs=c.FIELDS[c.NAME];v=[x[1] for x in fs];v[2]=c.REGIMES[2];v[3]='예';txt,csv=build_exports(c.NAME,fs,v,c.calculate(c.NAME,v),'2026-09-27')
  self.assertIn('64,000,000',txt);self.assertIn('대도시',csv.decode('utf-8-sig'))
