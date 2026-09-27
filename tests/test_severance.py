import unittest
from datetime import date
from decimal import Decimal as D
from modules.severance import NAME,FIELDS,calculate,income_tax,tax_years
class SeveranceTests(unittest.TestCase):
 def defaults(self):return [f[1] for f in FIELDS[NAME]]
 def test_nts_example(self):
  tax,rows=income_tax(100000000,20);self.assertEqual(tax,1120000)
  self.assertEqual(rows[2]['금액 또는 연수'],40000000)
 def test_dates_and_salary(self):
  v=self.defaults();r=calculate(NAME,v)
  self.assertLess(abs(r.metrics['이번 세전 퇴직급여']-D(15000000)/92*30*7305/365),D('.01'))
  self.assertEqual(tax_years(date(2006,9,26),date(2026,9,26)),20)
  self.assertEqual(tax_years(date(2006,9,26),date(2026,9,27)),21)
  v[0]=v[2]='2026-01-01';self.assertEqual(calculate(NAME,v).metrics['이번 세전 퇴직급여'],0)
 def test_settlement_and_tax_limits(self):
  v=self.defaults();v[2]='2016-09-26';v[9]=30000000;v[10]=100000
  r=calculate(NAME,v);self.assertEqual(r.rows[0]['금액 또는 연수'],20)
  v[8]=10**12
  with self.assertRaises(ValueError):calculate(NAME,v)
  for y in [5,6,10,11,20,21]:self.assertGreaterEqual(income_tax(100000000,y)[0],0)
 def test_ui(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertTrue(at.metric);self.assertEqual(len(at.get('download_button')),2)
