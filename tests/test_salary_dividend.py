import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from modules import salary_dividend as s,policy_fund as p
from modules.dividend_grossup import finance_tax
class SalaryDividend(unittest.TestCase):
 def test_grossup(self):
  self.assertEqual(finance_tax(0,20000000)['배당가산액'],0)
  r=finance_tax(5000000,100000000,100000000,0)
  self.assertEqual(r['배당가산액'],8500000)
  self.assertEqual(r['배당세액공제'],8500000)
  r=finance_tax(0,100000000,0,0)
  self.assertEqual(r['배당공제 후 국세'],14000000)
  self.assertLess(r['배당세액공제'],r['배당가산액'])
 def test_zero_share_costs(self):
  r=s.compare(confirmed='확인',withdraw=0)
  self.assertTrue(all(v==0 for v in r.metrics.values()))
  r=s.compare(confirmed='확인',share=25,on='아니오')
  self.assertEqual(r.rows[1]['전체 주주 배당 필요액'],400000000)
  self.assertEqual(r.rows[1]['법인세·지방세 추정'],88000000)
  self.assertEqual(r.rows[1]['회사 보험 증가'],0)
  self.assertEqual(s.compare(confirmed='확인',share=10).metrics['배당 100% 개인 수령 추정'],'배당가능이익 확인액 부족')
  with self.assertRaises(ValueError):s.compare(confirmed='확인',share=0)
 def test_full_app(self):
  at=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30);at.secrets['passwords']={'Admin':'integration-test-only'};at.run();at.text_input[0].set_value('integration-test-only');at.button[0].click().run();at.button(key='v2_nav_quick_calculators').click().run()
  for mod in (s,p):
   at.selectbox(key='jc_selected').select(mod.NAME).run()
   if mod==s:at.selectbox(key='cov_'+s.NAME+'_14').select('확인')
   next(b for b in at.button if b.label=='계산하기' and b.key!='a_calculate').click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual(len(at.tabs),2)
