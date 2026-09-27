import unittest
from modules.estate_calculator import estate
class EstateBusiness(unittest.TestCase):
 def test_caps_and_shared_limit(self):
  for years,cap in ((10,30000000000),(19,30000000000),(20,40000000000),(29,40000000000),(30,60000000000)):
   r=estate(gross=80000000000,business_value=70000000000,business_years=years,business_confirmed='예').metrics
   self.assertEqual(r['가업상속 공제 (공제종합한도 적용 전)'],cap)
  self.assertEqual(estate(business_value=500000000,business_confirmed='예').metrics['상속세 추정액'],0)
 def test_stock_addition_and_guards(self):
  self.assertEqual(estate(gross=900000000,extra_stock=100000000).metrics['상속세 추정액'],86330000)
  for kw in ({'business_value':1},{'business_value':1,'business_years':9,'business_confirmed':'예'},{'business_value':1000000001,'business_confirmed':'예'}):
   with self.assertRaises(ValueError):estate(**kw)
