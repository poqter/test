import unittest
from modules import nominee_trust as n,related_party_rent as r
class Ninth(unittest.TestCase):
 def test_nominee_tax_and_minimum(self):
  for value,tax in [(500000000,90000000),(499999,0),(500000,50000)]:self.assertEqual(n.assess(value=value).metrics['명의신탁 증여세 산출세액'],tax)
 def test_proof_and_return_separation(self):
  self.assertEqual(n.assess(proof=n.PROOF[1]).metrics['명의신탁 증여세 산출세액'],0)
  self.assertEqual(n.assess(mode=n.MODES[1],owner='예').metrics['환원 거래 자체 증여세'],0)
  self.assertIsInstance(n.assess(mode=n.MODES[1]).metrics['환원 거래 자체 증여세'],str)
  self.assertIsInstance(n.assess(mode=n.MODES[1],owner='예').metrics['최초 명의신탁 세액'],str)
 def test_rent_direction_and_percent(self):
  for direction,actual,expected in [(r.DIRECTIONS[0],24000000,4000000),(r.DIRECTIONS[1],24000000,0),(r.DIRECTIONS[1],16000000,4000000),(r.DIRECTIONS[0],16000000,0)]:
   result=r.assess(direction=direction,actual=actual,method=r.METHODS[1],confirmed='예').metrics
   self.assertEqual(result['세무조정 검토액'],expected);self.assertEqual(result['시가 대비 절대 차이율'],'20.00%')
 def test_thresholds(self):
  for market,delta,expected in [(20000000,999999,0),(20000000,1000000,1000000),(10000000000,299999999,0),(10000000000,300000000,300000000),(0,1,1)]:
   self.assertEqual(r.assess(actual=market+delta,market=market,method=r.METHODS[1],confirmed='예').metrics['세무조정 검토액'],expected)
 def test_fallback_and_unknown(self):
  self.assertIsInstance(r.assess().metrics['세무조정 검토액'],str)
  self.assertIsInstance(r.assess(method=r.METHODS[1]).metrics['세무조정 검토액'],str)
  self.assertEqual(r.assess(method=r.METHODS[2],deposit=100000000).metrics['비교 시가 연간 임대료'],12400000)
  with self.assertRaises(ValueError):r.assess(method=r.METHODS[2],deposit=500000001)
  with self.assertRaises(ValueError):n.assess(value=-1)
 def test_both_ui_and_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,label,expected in [(n,'명의신탁 증여세 산출세액','90,000,000원'),(r,'세무조정 검토액','4,000,000원')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run()
   values=[x[1] for x in mod.FIELDS[mod.NAME]]
   if mod==r:
    next(x for x in at.selectbox if x.label=='시가 확인 방법').select(r.METHODS[1]).run()
    next(x for x in at.selectbox if x.label=='특수관계·적용대상 및 예외 없음 확인').select('예').run()
    values[2]=r.METHODS[1];values[6]='예'
   at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
   self.assertEqual(next(x.value for x in at.metric if x.label==label),expected)
   txt,csv=build_exports(mod.NAME,mod.FIELDS[mod.NAME],values,mod.calculate(mod.NAME,values),'2026-09-26')
   self.assertIn(expected,txt);self.assertIn(expected,csv.decode('utf-8-sig'))
