import unittest
from datetime import date
from modules import housing_surcharge as h
from modules.capital_gains_tax import gains
class HousingSurcharge(unittest.TestCase):
 def test_rates_and_ltd(self):
  for houses,rate in [(2,20),(3,30),(5,30)]:
   r=gains(asset='주택',houses=houses,regulated='예',surcharge_mode=h.MODES[1]).metrics
   self.assertEqual(r['장기보유특별공제'],0)
   self.assertEqual(r['다주택 가산 세율'],rate)
   self.assertEqual(r['소득세'],129060000+387500000*rate/100)
  r=gains(asset='주택',houses=2,regulated='예',acquire='2026-01-01',surcharge_mode=h.MODES[1]).metrics
  self.assertEqual(r['소득세'],387500000*.7)
 def test_cutoff_and_contract_calendar(self):
  self.assertEqual(h.surcharge(date(2026,5,9),2,3)[0],0)
  with self.assertRaises(ValueError):h.surcharge(date(2026,5,10),2,3)
  kw=dict(mode=h.MODES[3],contract='2026-05-09',deposit='예')
  self.assertEqual(h.surcharge(date(2026,9,9),5,2,**kw)[0],0)
  self.assertEqual(h.surcharge(date(2026,9,10),5,2,**kw)[0],h.D('.2'))
  self.assertEqual(h.surcharge(date(2026,11,9),5,3,region=h.REGIONS[1],**kw)[0],0)
  self.assertEqual(h.surcharge(date(2026,11,10),5,3,region=h.REGIONS[1],**kw)[0],h.D('.3'))
  self.assertEqual(h.add_months(date(2026,1,31),4),date(2026,5,31))
  self.assertEqual(h.add_months(date(2026,10,31),4),date(2027,2,28))
 def test_permit_and_proofs(self):
  kw=dict(mode=h.MODES[3],contract='2026-06-01',deposit='예',permit='예',applied='2026-05-09',approved='예')
  self.assertEqual(h.surcharge(date(2026,9,9),5,2,**kw)[0],0)
  self.assertEqual(h.surcharge(date(2026,9,10),5,2,**kw)[0],h.D('.2'))
  for key,value in [('approved','아니요'),('applied','2026-05-10'),('deposit','아니요'),('permit','아니요')]:
   self.assertEqual(h.surcharge(date(2026,9,9),5,2,**{**kw,key:value})[0],h.D('.2'))
  self.assertEqual(h.surcharge(date(2026,9,9),1,2,**kw)[0],h.D('.2'))
 def test_designated_land_and_ui(self):
  r=gains(asset='토지',nonbusiness='예',designated='예').metrics
  self.assertEqual(r['소득세'],97860000+309500000*.2)
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select('양도소득세계산기').run()
  at.selectbox(key='cov_양도소득세계산기_2').select('주택')
  at.number_input(key='cov_양도소득세계산기_11').set_value(2)
  at.selectbox(key='cov_양도소득세계산기_12').select('예')
  at.selectbox(key='cov_양도소득세계산기_15').select(h.MODES[1])
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertIn('20.00%',[m.value for m in at.metric])
