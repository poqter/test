import unittest
from modules.gift_comparisons import *

class GiftComparisonTests(unittest.TestCase):
 def test_source_burden(self):
  r=burden().metrics
  self.assertEqual(r['일반증여 비교 세액'],218250000)
  self.assertEqual(r['수증자 증여세'],101850000)
  self.assertEqual(r['증여자 양도소득세'],28485000)
  self.assertEqual(r['부담부증여 비교 세액'],133183500)
  self.assertEqual(r['안분 취득가액'],240000000)
 def test_debt_boundaries_and_short_holding(self):
  r=burden(debt=0).metrics
  self.assertEqual(r['두 방식 세액 차이'],0)
  self.assertEqual(r['증여자 양도소득세'],0)
  self.assertEqual(burden(debt=1000000000).metrics['수증자 증여세'],0)
  r=burden(acquire='2026-01-01').metrics
  self.assertEqual(r['증여자 양도소득세'],78750000)
  self.assertEqual(burden(cost=1100000000).metrics['증여자 양도소득세'],0)
  self.assertEqual(burden(expense=10000000).metrics['증여자 양도소득세'],25685000)
 def test_qualified_home_full_value_apportionment(self):
  r=burden(asset='주택',special='예',residence=5).metrics
  self.assertEqual(r['증여자 양도소득세'],0)
  r=burden(value=2000000000,debt=800000000,cost=1000000000,asset='주택',special='예',residence=5).metrics
  self.assertEqual(r['증여자 양도소득세'],9000000)
  self.assertEqual(r['증여자 지방소득세'],900000)
  # Debt is below1.2bn but total property is2bn: not fully exempt.
  self.assertGreater(r['증여자 양도소득세'],0)
  with self.assertRaises(ValueError):burden(asset='주택',special='예',houses=2)

 def test_source_inheritance_and_whole_estate(self):
  r=inheritance_compare(confirmed='예').metrics
  self.assertEqual(r['현재 증여세'],218250000)
  self.assertEqual(r['재산 포함 전체 상속세'],87300000)
  self.assertEqual(inheritance_compare(value=500000000,confirmed='예').metrics['재산 포함 전체 상속세'],0)
  r=inheritance_compare(other=1000000000,confirmed='예').metrics
  self.assertEqual(r['재산 포함 전체 상속세'],426800000)
  self.assertEqual(r['해당 재산으로 늘어나는 상속세'],339500000)
  self.assertEqual(r['증여세 − 상속세 증가분'],-121250000)
 def test_inheritance_minimum_and_existing_core(self):
  from modules.estate_calculator import estate
  for extra,expected in ((499999,0),(500000,48500)):
   self.assertEqual(inheritance_compare(value=500000000+extra,confirmed='예').metrics['재산 포함 전체 상속세'],expected)
   # Shared legacy engine: estate 505m includes 5m funeral +500m lump.
   self.assertAlmostEqual(estate(gross=505000000+extra).metrics['상속세 추정액'],D(expected),places=4)
 def test_guards(self):
  for kw in ({'debt':1000000001},{'value':0},{'debt':0,'expense':1},{'special':'예'},
             {'asset':'주택','houses':2,'regulated':'예'},{'valuation':'unknown'},{'when':'2025-01-01'}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):burden(**kw)
  with self.assertRaises(ValueError):inheritance_compare()
  with self.assertRaises(ValueError):inheritance_compare(value=10**12,other=1,confirmed='예')
 def test_two_views_exports_and_invalid_clears_result(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  from modules.gift_tax import NAME
  for name,metric,expected in ((BURDEN,'부담부증여 비교 세액','133,183,500원'),(INHERIT,'재산 포함 전체 상속세','87,300,000원')):
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(NAME).run();at.selectbox(key='gift_mode').select(name).run()
   if name==INHERIT:at.selectbox(key=f'cov_{name}_4').select('예')
   at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==metric),expected)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   values=[f[1] for f in FIELDS[name]]
   if name==INHERIT:values[4]='예'
   txt,csv=build_exports(name,FIELDS[name],values,calculate(name,values),'2026-09-26')
   self.assertIn(expected,txt);self.assertIn(expected,csv.decode('utf-8-sig'))
   if name==INHERIT:at.selectbox(key=f'cov_{name}_4').select('아니요')
   else:at.selectbox(key=f'cov_{name}_12').select('예')
   at.button[0].click().run()
   self.assertTrue(at.error);self.assertEqual(len(at.metric),0)
