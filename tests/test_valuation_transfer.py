import unittest
from streamlit.testing.v1 import AppTest
from modules import unlisted_valuation as u
class Transfer(unittest.TestCase):
 def test_transfer_uses_tax_value_and_updates_destination(self):
  for target,key in [('가업승계 세부담계산기','cov_가업승계 세부담계산기_0'),('증여세계산기','cov_증여세계산기_6'),('상속세계산기','cov_상속세계산기_35')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(u.NAME).run()
   next(x for x in at.selectbox if x.label==u.FIELDS[u.NAME][-1][0]).select('확인').run()
   next(x for x in at.selectbox if x.label=='참고 시나리오 보정').select(u.FACTORS[2]).run()
   at.button[0].click().run()
   at.number_input(key='jc_transfer_shares').set_value(100).run()
   at.selectbox(key='jc_transfer_target').select(target).run()
   at.button(key='jc_transfer_apply').click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(at.selectbox(key='jc_selected').value,target)
   self.assertEqual(at.number_input(key=key).value,2600000)
