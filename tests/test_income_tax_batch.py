import unittest
from decimal import Decimal as D
from modules.earned_income_tax import earned,wage_deduction,wage_credit,medical_credit,NAME as E
from modules.global_income_tax import comprehensive,STANDARD,NAME as G
from modules.rental_tax import rental,NAME as R


class IncomeTaxTests(unittest.TestCase):
 def test_earned_source_itemized_and_standard_correction(self):
  r=earned(nps=2850000,mode='특별공제 적용')
  self.assertEqual(r.metrics['예상 결정세액 (국세+지방세)'],4966500)
  r=earned(nps=2850000,insurance=1000000,mode='특별공제 적용')
  self.assertEqual(r.metrics['예상 결정세액 (국세+지방세)'],4834500)
  r=earned(nps=2850000,insurance=1000000)
  self.assertEqual(r.metrics['예상 결정세액 (국세+지방세)'],4823500)
  self.assertEqual(r.metrics['선택된 공제 방식'],'표준세액공제 적용')
  self.assertEqual(r.metrics['환급 예상액'],'기납부 세액 미입력')
  r=earned(nps=2850000,prepaid='5,000,000')
  self.assertEqual(r.metrics['환급 예상액'],176500)
  self.assertEqual(r.metrics['추가 납부 예상액'],0)
  self.assertEqual(earned(salary=0).metrics['예상 결정세액 (국세+지방세)'],0)

 def test_deduction_bands_and_medical_allocation(self):
  for salary,expected in ((5000000,3500000),(15000000,7500000),(45000000,12000000),(100000000,14750000),(1000000000,20000000)):
   self.assertEqual(wage_deduction(salary),expected)
  for salary,cap in ((33000000,740000),(70000000,660000),(71000000,500000),(121000000,200000)):
   self.assertEqual(wage_credit(salary,10000000),cap)
  self.assertEqual(medical_credit(60000000,1000000,1000000,1000000,1000000),530000)
  self.assertEqual(medical_credit(60000000,100000000,0,0,0),1050000)
  with self.assertRaises(ValueError):earned(people=1,children=1)
  with self.assertRaises(ValueError):earned(pension=10000000,irp=10000000)

 def test_comprehensive_reference_and_credit_guards(self):
  self.assertEqual(comprehensive().metrics['예상 결정세액 (국세+지방세)'],6539500)
  self.assertEqual(comprehensive(pension=6000000,irp=3000000).metrics['예상 결정세액 (국세+지방세)'],5351500)
  r=comprehensive(revenue=45000000,expenses=0,pension=6000000,irp=3000000)
  self.assertEqual(r.metrics['연금계좌 세액공제 가능액'],1350000)
  r=comprehensive(revenue=45000001,expenses=0,pension=6000000,irp=3000000)
  self.assertEqual(r.metrics['연금계좌 세액공제 가능액'],1080000)
  for kwargs in ({'expenses':90000000},{'wage':1000000},{'standard':STANDARD[2]},
                 {'books':'간편장부','bookkeeping_credit':1},{'earned_credit':1}):
   with self.assertRaises(ValueError):comprehensive(**kwargs)
  r=comprehensive(wage=1000000,standard=STANDARD[2],earned_credit=1000)
  self.assertGreater(r.metrics['예상 결정세액 (국세+지방세)'],0)

 def test_rental_source_and_high_price_correction(self):
  self.assertEqual(rental().metrics['종합과세 임대 세부담 증가액'],613800)
  self.assertEqual(rental().metrics['분리과세 임대 세부담'],1078000)
  r=rental(other=40000000)
  self.assertEqual(r.metrics['분리과세 임대 세부담'],1386000)
  self.assertEqual(r.metrics['종합과세 임대 세부담 증가액'],1782000)
  r=rental(other=40000000,registered=True)
  self.assertEqual(r.metrics['분리과세 임대 세부담'],1108800)
  r=rental(expensive=2,deposit=1300000000,registered=True,other=40000000)
  self.assertEqual(r.metrics['간주임대료'],18600000)
  self.assertEqual(r.metrics['과세 임대수입'],36600000)
  self.assertIn('선택 불가',r.metrics['분리과세 임대 세부담'])

 def test_rental_boundaries_and_exemptions(self):
  self.assertEqual(rental(homes=1,nonsmall=1).metrics['과세 임대수입'],0)
  self.assertEqual(rental(homes=1,nonsmall=1,taxable_single=True).metrics['과세 임대수입'],18000000)
  self.assertEqual(rental(expensive=2,deposit=1200000000).metrics['간주임대료'],0)
  self.assertEqual(rental(homes=3,nonsmall=3,deposit=600000000).metrics['간주임대료'],5580000)
  self.assertEqual(rental(homes=3,nonsmall=2,deposit=600000000).metrics['간주임대료'],0)
  for kwargs in ({'homes':0},{'nonsmall':3},{'books':False,'deposit_income':1},{'expenses':19000000}):
   with self.assertRaises(ValueError):rental(**kwargs)
  self.assertIsInstance(rental(rent=20000000).metrics['분리과세 임대 세부담'],D)
  self.assertIsInstance(rental(rent=20000001).metrics['분리과세 임대 세부담'],str)

 def test_three_routes_and_exports(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  for name in (E,G,R):
   at.selectbox(key='jc_selected').select(name).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertTrue(at.metric);self.assertEqual(len(at.get('download_button')),2)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
