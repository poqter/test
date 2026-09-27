import unittest
from modules import policy_fund as p
class Policy(unittest.TestCase):
 def test_branches(self):
  r=p.diagnose(independence='일반 중소기업 요건 확인',restrictions='제한 없음 확인')
  self.assertEqual(r.metrics['만 업력'],8)
  self.assertEqual(r.metrics['추가 검토 사업 수'],1)
  self.assertIn('혁신성장지원',r.rows[0]['검토 사업'])
  r=p.diagnose(start='2025-01-01',age=30,exports=100,distress='예')
  self.assertEqual(r.metrics['추가 검토 사업 수'],4)
  self.assertFalse(any('혁신성장지원' in x['검토 사업'] for x in r.rows))
  self.assertEqual(p.diagnose(assets=500000000000).metrics['추가 검토 사업 수'],0)
  self.assertEqual(p.diagnose(restrictions='제한 있음').metrics['추가 검토 사업 수'],0)
  self.assertEqual(p.diagnose(start='2019-09-28').metrics['만 업력'],6)
  self.assertEqual(p.diagnose(start='2019-09-27').metrics['만 업력'],7)
 def test_industries(self):
  for name,(_,limit) in p.INDUSTRIES.items():
   self.assertIn('규모 기준 충족',p.diagnose(industry=name,sales=limit*100000000).metrics['중소기업 사전 판정'])
   self.assertIn('규모 기준 초과',p.diagnose(industry=name,sales=limit*100000000+1).metrics['중소기업 사전 판정'])

 def test_small_and_nonstartup(self):
  r=p.diagnose(start='2025-01-01',age=30,startup='아니오')
  self.assertFalse(any('청년' in x['검토 사업'] for x in r.rows))
  for name,(code,_) in p.INDUSTRIES.items():
   limit=p.SMALL_LIMITS[code]*100000000
   self.assertIn('규모 기준 충족',p.diagnose(industry=name,sales=limit).metrics['소기업 사전 판정'])
   self.assertIn('규모 기준 초과',p.diagnose(industry=name,sales=limit+1).metrics['소기업 사전 판정'])
