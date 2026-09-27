import unittest
from modules import corp_vs_individual as c
class CorporateDividendAuto(unittest.TestCase):
 def test_eligible_grossup_and_cash(self):
  r=c.compare(dividend=50000000,mode=c.MODES[2],eligible_dividend=50000000).metrics
  self.assertEqual(r['대표 급여 소득세'],22805750)
  self.assertEqual(r['배당 추가 세액'],12485000)
  self.assertEqual(r['개인사업자 소득세 추정'],102839000)
  self.assertEqual(r['대표 수령 현금 (입력 보험료 차감)']+r['법인에 남는 당기 이익']+r['법인·대표 합산세액'],300000000)
  self.assertIn('세액공제 전',r['계산 기준'])
 def test_finance_on_both_sides_and_guards(self):
  a=c.compare(mode=c.MODES[2]).metrics
  b=c.compare(mode=c.MODES[2],other_financial=10000000).metrics
  self.assertEqual(b['개인사업자 소득세 추정']-a['개인사업자 소득세 추정'],1540000)
  self.assertEqual(b['법인·대표 합산세액']-a['법인·대표 합산세액'],1540000)
  self.assertEqual(c.compare(mode=c.MODES[2],dividend=20000000,eligible_dividend=20000000).metrics['배당 추가 세액'],3080000)
  for kw in ({'eligible_dividend':1},{'dividend':1,'eligible_dividend':2,'mode':c.MODES[2]},{'mode':c.MODES[2],'extra_tax':1}):
   with self.assertRaises(ValueError):c.compare(**kw)
 def test_ui_and_export(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(c.NAME).run()
  at.selectbox(key=f'cov_{c.NAME}_4').select(c.MODES[2])
  at.number_input(key=f'cov_{c.NAME}_2').set_value(50000000)
  at.number_input(key=f'cov_{c.NAME}_14').set_value(50000000)
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(x.value for x in at.metric if x.label=='배당 추가 세액'),'12,485,000원')
  self.assertEqual(len(at.get('download_button')),2)
