import unittest
from modules.global_income_tax import comprehensive,BOOK_MODES,BOOK_ELIGIBILITY,NAME


class BookkeepingCreditTests(unittest.TestCase):
 def auto(self,**kwargs):
  return comprehensive(book_mode=BOOK_MODES[1],book_eligibility=BOOK_ELIGIBILITY[1],**kwargs)

 def test_cap_and_income_allocation(self):
  r=self.auto(book_income=50000000)
  self.assertEqual(r.metrics['기장세액공제 적용액'],1000000)
  self.assertEqual(r.metrics['예상 결정세액 (국세+지방세)'],5439500)
  r=self.auto(book_income=10000000)
  self.assertEqual(r.metrics['기장세액공제 적용액'],240600)
  self.assertEqual(r.metrics['예상 결정세액 (국세+지방세)'],6274840)
  r=self.auto(revenue=0,expenses=0,book_income=0)
  self.assertEqual(r.metrics['기장세액공제 적용액'],0)

 def test_eligibility_and_conflicts(self):
  r=comprehensive(book_mode=BOOK_MODES[1],book_income=50000000)
  self.assertEqual(r.metrics['기장세액공제 적용액'],0)
  r=self.auto(book_income=50000000,book_omission='예')
  self.assertEqual(r.metrics['기장세액공제 적용액'],0)
  for kwargs in ({'books':'간편장부'},{'bookkeeping_credit':100},{'book_income':50000001}):
   with self.assertRaises(ValueError):self.auto(**kwargs)

 def test_ui_and_export(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(NAME).run()
  at.selectbox(key='cov_'+NAME+'_17').select(BOOK_MODES[1]).run()
  at.selectbox(key='cov_'+NAME+'_18').select(BOOK_ELIGIBILITY[1]).run()
  at.number_input(key='cov_'+NAME+'_19').set_value(50000000).run()
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(m.value for m in at.metric if m.label=='기장세액공제 적용액'),'1,000,000원')
  from modules.calculator_exports import build_exports
  from modules.global_income_tax import FIELDS
  values=[f[1] for f in FIELDS[NAME]]
  values[17:20]=[BOOK_MODES[1],BOOK_ELIGIBILITY[1],50000000]
  customer,advisor=build_exports(NAME,FIELDS[NAME],values,self.auto(book_income=50000000),'2026-09-26')
  self.assertIn('기장세액공제 적용액: 1,000,000원',customer)
  self.assertIn('기장세액공제 적용액,"1,000,000원"',advisor.decode('utf-8-sig'))
  self.assertIn(BOOK_ELIGIBILITY[1],customer)
