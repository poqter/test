import unittest
from decimal import Decimal as D
from modules.retirement_models import NAMES,FIELDS,calculate
class RetirementTests(unittest.TestCase):
 def test_reference_cases(self):
  expected=[117086542,1200000,1000000,229,1188000,660000,5000000,170300613]
  for name,target in zip(NAMES,expected):
   r=calculate(name,[f[1] for f in FIELDS[name]])
   self.assertLess(abs(next(iter(r.metrics.values()))-D(target)),D('.51'),name)
 def test_tax_boundaries(self):
  self.assertEqual(calculate(NAMES[4],[55000000,6000000,3000000,0]).metrics['세액공제 가능액 (지방세 효과 포함)'],1485000)
  self.assertEqual(calculate(NAMES[4],[50000000,6000000,3000000,1]).metrics['세액공제 가능액 (지방세 효과 포함)'],1188000)
  self.assertEqual(calculate(NAMES[4],[60000000,9000000,0,0]).metrics['공제 대상 합계'],6000000)
  self.assertEqual(calculate(NAMES[5],[16000000,65,0]).metrics['적용 세율'],D('16.5'))
  self.assertEqual(calculate(NAMES[5],[12000000,70,0]).metrics['분리과세 선택 시 세금'],528000)
  self.assertEqual(calculate(NAMES[5],[12000000,65,1]).metrics['분리과세 선택 시 세금'],396000)
  self.assertEqual(calculate(NAMES[6],[100000000,5000000]).metrics['21년차 이후 동일재원 세금'],2500000)
 def test_zero_and_limits(self):
  self.assertEqual(calculate(NAMES[0],[65,60,1000000,0]).metrics['공백기 필요자금'],0)
  self.assertEqual(calculate(NAMES[3],[100,10,65,0,0]).metrics['전액 인출 가능 개월'],10)
  with self.assertRaises(ValueError):calculate(NAMES[7],[18000000,10,50000000,4,6000000,5.5])
  r=calculate(NAMES[7],[18000000,1,60000000,0,0,5.5]);self.assertEqual(r.metrics['과세제외 납입원금'],9000000)
 def test_routes(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  for name in NAMES:
   at.selectbox(key='jc_selected').select(name).run();at.button[0].click().run()
   self.assertFalse(at.exception,name);self.assertTrue(at.metric,name);self.assertEqual(len(at.get('download_button')),2)
