import unittest
from modules.insurance_transfer import transfer,KINDS
from modules.corporate_insurance_maturity import calculate,NAME,FIELDS,MODES
class InsuranceTransfer(unittest.TestCase):
 def test_retirement_limits_and_real_cash(self):
  r=transfer(200000000,150000000,150000000,500000000,'아니요',confirmed='확인')
  self.assertEqual(r.metrics['법인 실제 대가 수령액'],0)
  self.assertEqual(r.metrics['법인 소득금액 증감'],-150000000)
  self.assertEqual(r.metrics['법인 국세·지방세 증감 추정'],-33000000)
  self.assertEqual(r.metrics['개인 퇴직소득 증가분'],200000000)
  self.assertEqual(r.metrics['개인 근로소득 증가분'],0)
  r=transfer(200000000,150000000,150000000,500000000,'아니요',other_retirement=100000000,limit=200000000,confirmed='확인')
  self.assertEqual(r.metrics['개인 퇴직소득 증가분'],100000000)
  self.assertEqual(r.metrics['개인 근로소득 증가분'],100000000)
  self.assertGreater(r.metrics['개인 근로소득세 증가 추정'],0)
 def test_salary_and_market_sale(self):
  r=transfer(200000000,150000000,150000000,0,'아니요',kind=KINDS[1],deductible=0,confirmed='확인')
  self.assertEqual(r.metrics['개인 퇴직소득 증가분'],0)
  self.assertEqual(r.metrics['법인 소득금액 증감'],50000000)
  r=transfer(200000000,150000000,150000000,0,'아니요',kind=KINDS[2],paid=200000000,deductible=0,confirmed='확인')
  self.assertEqual(r.metrics['법인 실제 대가 수령액'],200000000)
  self.assertEqual(r.metrics['대표 현물 수령 이익'],0)
  self.assertEqual(r.metrics['법인 국세·지방세 증감 추정'],5500000)
  with self.assertRaises(ValueError):transfer(200000000,150000000,150000000,0,'아니요',kind=KINDS[2],confirmed='확인')
 def test_ui_transfer_and_exports(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.coverage_calculator_ui import run\nfrom modules.corporate_insurance_maturity import NAME,FIELDS,calculate\nrun(NAME,FIELDS,calculate)').run()
  at.selectbox(key=f'cov_{NAME}_0').select(MODES[2])
  at.selectbox(key=f'cov_{NAME}_5').select('예')
  at.selectbox(key=f'cov_{NAME}_16').select('확인')
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertTrue(at.metric);self.assertEqual(len(at.get('download_button')),2)
