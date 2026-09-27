import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from modules import corporate_funding as c
from modules.calculator_exports import build_exports
class Funding(unittest.TestCase):
 def test_observed_and_surplus(self):
  self.assertEqual(c.keyman().metrics['추가 필요자금'],1340000000)
  self.assertEqual(c.buyout().metrics['추가 필요자금'],1300000000)
  self.assertEqual(c.succession().metrics['추가 필요자금'],1000000000)
  for r in (c.keyman(cash=2000000000),c.buyout(cash=2000000000),c.succession(cash=1200000000)):
   self.assertEqual(r.metrics['추가 필요자금'],0)
   self.assertGreater(r.metrics['필요액 초과 준비자금'],0)
 def test_boundaries(self):
  self.assertEqual(c.buyout(100000000,100,0).metrics['추가 필요자금'],100000000)
  self.assertEqual(c.buyout(100000000,0,0).metrics['추가 필요자금'],0)
  self.assertEqual(c.succession(1,0,0,0).metrics['총 필요자금'],0)
  self.assertEqual(c.keyman(0,0,0,0,0,0).metrics['총 필요자금'],0)
  with self.assertRaises(ValueError):c.buyout(share=100.1)
  with self.assertRaises(ValueError):c.keyman(months=1.5)
  with self.assertRaises(ValueError):c.succession(tax=-1)
 def test_full_workspace_and_exports(self):
  at=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30);at.secrets['passwords']={'Admin':'integration-test-only'};at.run();at.text_input[0].set_value('integration-test-only');at.button[0].click().run();at.button(key='v2_nav_quick_calculators').click().run()
  for name in c.NAMES:
   at.selectbox(key='jc_selected').select(name).run()
   next(b for b in at.button if b.label=='계산하기' and b.key!='a_calculate').click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
   fs=c.FIELDS[name];v=[f[1] for f in fs];r=c.calculate(name,v);txt,csv=build_exports(name,fs,v,r,'2026-09-27')
   for k,value in r.display().items():self.assertIn(k+': '+value,txt)
   self.assertIn('추가 필요자금',csv.decode('utf-8-sig'))
