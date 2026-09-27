import unittest
from decimal import Decimal as D
from modules.retirement_plan import MODES,FIELDS,calculate
class RetirementPlanTests(unittest.TestCase):
 def defaults(self,i):return [f[1] for f in FIELDS[MODES[i]]]
 def test_observed_modes(self):
  for i,target in enumerate([471124417,1278146,4386669]):
   r=calculate(MODES[i],self.defaults(i))
   self.assertLess(abs(next(iter(r.metrics.values()))-target),D('.51'))
  self.assertEqual(calculate(MODES[3],self.defaults(3)).metrics['전액 인출 가능 개월'],529)
 def test_goal_and_ledger(self):
  r=calculate(MODES[1],self.defaults(1))
  self.assertLess(abs(r.rows[-1]['자산']-800000000),D('.01'))
  r=calculate(MODES[2],self.defaults(2))
  self.assertLess(abs(r.rows[-1]['자산']),D('.01'))
 def test_zero_negative_real_and_invalid(self):
  v=self.defaults(3);v[3:5]=[0,0];v[5:]=[100,10]
  self.assertEqual(calculate(MODES[3],v).metrics['전액 인출 가능 개월'],10)
  v[4]=3
  self.assertLess(calculate(MODES[3],v).metrics['전액 인출 가능 개월'],10)
  v[6]=0
  self.assertIsInstance(calculate(MODES[3],v).metrics['수학적 지속기간'],str)
  v=self.defaults(1);v[0]=65
  with self.assertRaises(ValueError):calculate(MODES[1],v)
 def test_center_modes(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select('은퇴계산기').run()
  for mode in MODES:
   at.selectbox(key='retirement_mode').select(mode).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertTrue(at.metric);self.assertEqual(len(at.get('download_button')),2)
