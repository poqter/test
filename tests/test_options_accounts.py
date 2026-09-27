import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from modules import stock_option as s,overseas_accounts as o
class NewTax(unittest.TestCase):
 def test_option(self):
  r=s.option(confirmed='확인');self.assertEqual(r.metrics['행사이익'],300000000)
  self.assertEqual(r.rows[1]['과세표준'],358500000)
  # Source total 131,516,000 uses an incorrect wage deduction; current 20m deduction cap gives 129,866,000 before credits.
  self.assertEqual(s.option(confirmed='확인',deductions=0).rows[1]['산출국세']*s.D('1.1'),129866000)
  v=s.option(confirmed='확인',kind=s.TYPES[1]);self.assertEqual(v.metrics['이번 비과세액'],200000000)
  self.assertEqual(s.option(confirmed='확인',kind=s.TYPES[1],annual_used=180000000).metrics['이번 비과세액'],20000000)
  self.assertEqual(s.option(confirmed='확인',kind=s.TYPES[1],total_used=490000000).metrics['이번 비과세액'],10000000)
  self.assertEqual(s.option(confirmed='확인',market=10000).metrics['행사이익'],0)
  with self.assertRaises(ValueError):s.option(confirmed='확인',shares=1.1)
 def test_accounts(self):
  def v(**kw):return o.accounts(confirmed='확인',eligibility=o.ELIGIBILITY[0],**kw).metrics
  self.assertEqual(v()['미신고·과소신고 기본 과태료 추정'],80000000)
  self.assertEqual(v(peak=500000000)['미신고·과소신고 기본 과태료 추정'],0)
  self.assertEqual(v(status=o.STATUS[1])['미신고·과소신고 기본 과태료 추정'],0)
  self.assertEqual(v(peak=20000000000)['미신고·과소신고 기본 과태료 추정'],1000000000)
  self.assertEqual(v(status=o.STATUS[2],omitted=100000000)['미신고·과소신고 기본 과태료 추정'],10000000)
  self.assertEqual(v(timing='신고기한 전 예상')['미신고·과소신고 기본 과태료 추정'],0)
  with self.assertRaises(ValueError):v(omitted=900000000)
 def test_full_app(self):
  at=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30);at.secrets['passwords']={'Admin':'integration-test-only'};at.run();at.text_input[0].set_value('integration-test-only');at.button[0].click().run();at.button(key='v2_nav_quick_calculators').click().run()
  for mod,idx in ((s,10),(o,6)):
   at.selectbox(key='jc_selected').select(mod.NAME).run();at.selectbox(key=f'cov_{mod.NAME}_{idx}').select('확인')
   if mod==o:at.selectbox(key=f'cov_{mod.NAME}_4').select(o.ELIGIBILITY[0])
   next(b for b in at.button if b.label=='계산하기' and b.key!='a_calculate').click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual(len(at.tabs),2)
