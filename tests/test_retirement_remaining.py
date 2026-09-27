import unittest
from decimal import Decimal as D
from modules.retirement_remaining import SAVE,ORDER,FIELDS,saving,withdrawal
class RemainingTests(unittest.TestCase):
 def test_saving_source_and_goal(self):
  r=saving(SAVE,[f[1] for f in FIELDS[SAVE]])
  self.assertLess(abs(r.metrics['매달 필요한 저축액']-1556179),D('.51'))
  self.assertLess(abs(r.rows[-1]['자산']-500000000),D('.01'))
  r=saving(SAVE,[40,60,500000000,50000000,0,0]);self.assertEqual(r.metrics['매달 필요한 저축액'],1875000)
 def test_order_source_and_net(self):
  a=[('연금저축·IRP',100000000,5.5),('일반 투자계좌',200000000,15.4),('예적금',300000000,15.4)]
  r=withdrawal(3000000,20,a);self.assertEqual(r.metrics['부족액'],120000000);self.assertEqual(r.metrics['먼저 인출할 계좌'],'연금저축·IRP')
  r=withdrawal(3000000,20,a,True);self.assertEqual(r.metrics['부족액'],202500000)
  r=withdrawal(100,1,[('A',10000,100)],True);self.assertEqual(r.metrics['총 인출액'],0)
  r=withdrawal(100,1,[('A',10000,0)],True);self.assertEqual(r.metrics['총 인출액'],1200)
 def test_routes(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  for name in (SAVE,ORDER):
   at.selectbox(key='jc_selected').select(name).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertTrue(at.metric);self.assertEqual(len(at.get('download_button')),2)
  at.radio(key='wo_basis').set_value('세후 생활비').run();at.button[0].click().run();self.assertFalse(at.exception);self.assertTrue(at.metric)
