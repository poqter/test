import unittest
from modules.housing_pension import calculate,NAME,DATA
class HousingTests(unittest.TestCase):
 def test_official_and_interpolation(self):
  for age,price,target in [(65,600000000,1517000),(55,100000000,156000),(80,1200000000,4060000),(65,650000000,1643500)]:
   self.assertEqual(calculate(NAME,[age,price]).metrics['예상 월 수령액'],target)
 def test_limits(self):
  for values in ([54,600000000],[91,600000000],[65,0],[65,1300000000]):
   with self.assertRaises(ValueError):calculate(NAME,values)
  self.assertEqual(len(DATA['monthly']),36)
 def test_route(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run();at.button[0].click().run()
  self.assertFalse(at.exception);self.assertEqual(at.metric[0].value,'1,517,000원');self.assertEqual(len(at.get('download_button')),2)
