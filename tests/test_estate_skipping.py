import unittest
from modules.estate_calculator import estate,NAME,FIELDS
from modules.finance_models import D

class EstateSkippingTests(unittest.TestCase):
 def test_source_partial_and_substitution(self):
  kw=dict(gross=2000000000,spouse='예',spouse_actual=800000000,spouse_confirmed='예')
  r=estate(**kw,skip30=500000000)
  self.assertEqual(r.metrics['세대생략 할증'],11137500)
  self.assertEqual(r.metrics['상속세 추정액'],154848375)
  self.assertEqual(estate(**kw,substitution=500000000).metrics['상속세 추정액'],144045000)
  kw['gross']=4000000000
  self.assertEqual(estate(**kw,skip40=2100000000).metrics['상속세 추정액'],1077456600)
 def test_denom_before_expenses_and_aggregated_gifts(self):
  r=estate(gross=1000000000,debt=100000000,skip30=500000000)
  # Base395m, gross tax69m. Ratio .5, NOT500/895.
  self.assertEqual(r.metrics['세대생략 할증'],10350000)
  self.assertEqual(r.metrics['상속세 추정액'],76969500)
  r=estate(gross=1000000000,prior_heirs=1000000000,skip30=1000000000)
  self.assertEqual(r.metrics['세대생략 할증'],65700000)
 def test_mixed_rates_and_threshold(self):
  r=estate(gross=4000000000,skip30=1000000000,skip40=2100000000)
  # 1.2875bn gross tax*(1/4*.3+2.1/4*.4)=366937500
  self.assertEqual(r.metrics['세대생략 할증'],366937500)
  with self.assertRaises(ValueError):estate(gross=4000000000,skip40=2000000000)
  self.assertEqual(estate(gross=4000000000,skip30=2000000000).metrics['세대생략 할증'],193125000)
 def test_validation_and_zero(self):
  for kw in ({'skip30':1000000001},{'skip30':600000000,'substitution':500000000},{'skip40':float('inf')}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):estate(**kw)
  self.assertEqual(estate(gross=400000000,skip30=400000000).metrics['세대생략 할증'],0)
 def test_ui_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run()
  at.number_input(key=f'cov_{NAME}_32').set_value(500000000)
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(m.value for m in at.metric if m.label=='세대생략 할증'),'13,350,000원')
  vals=[f[1] for f in FIELDS[NAME]];vals[32]=500000000
  txt,csv=build_exports(NAME,FIELDS[NAME],vals,estate(skip30=500000000),'2026-09-26')
  self.assertIn('13,350,000원',txt);self.assertIn('13,350,000원',csv.decode('utf-8-sig'))
