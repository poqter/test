import unittest
from modules import welfare_fund as f,bonus_welfare as b
from modules.earned_income_tax import earned
from modules import corporate_insurance_maturity as m
class SixthBatch(unittest.TestCase):
 def test_fund_source_and_unknown(self):
  r=f.fund(confirmed='예').metrics
  self.assertEqual(r['국세·지방세 산출세액 감소 추정'],22000000)
  self.assertEqual(r['세액 감소 반영 회사 부담 추정'],78000000)
  r=f.fund().metrics
  self.assertEqual(r['회사 현금 출연액'],100000000)
  self.assertIsInstance(r['국세·지방세 산출세액 감소 추정'],str)
  self.assertIsInstance(r['세액 감소 반영 회사 부담 추정'],str)
 def test_fund_usage_and_tax_floor(self):
  for kind,rate in zip(f.TYPES,(50,80,90)):
   r=f.fund(kind=kind,rate=rate,use_confirmed='예').metrics
   self.assertEqual(r['당기 출연금 중 사용 예정액'],1000000*rate)
   self.assertEqual(r['사용 예정액의 1인당 단순 평균'],100000*rate)
   self.assertEqual(r['당기 출연금 중 사용 예정액']+r['당기 출연금 중 기본재산 잔류액'],100000000)
  r=f.fund(paid=100000000,base=50000000,confirmed='예').metrics
  self.assertEqual(r['국세·지방세 산출세액 감소 추정'],5500000)
  self.assertEqual(r['반영 후 과세표준'],0)
  self.assertEqual(f.fund(base=0,confirmed='예').metrics['국세·지방세 산출세액 감소 추정'],0)
 def test_bonus_default_not_automatically_exempt(self):
  r=b.compare().metrics
  self.assertEqual(r['총 지급·혜택 금액'],20000000)
  self.assertEqual(r['상여안 추가 소득세 추정'],r['복지안 추가 소득세 추정'])
  self.assertIsInstance(r['복지안 선택 시 직원 순혜택 증가'],str)
  r=b.compare(amount=300000,count=1,bonus_own='0,0,0',welfare_own='0,0,0',bonus_company='0',welfare_company='0').metrics
  self.assertEqual(r['복지안 선택 시 직원 순혜택 증가'],0)
  self.assertEqual(r['복지안 선택 시 회사 지출 감소'],0)
 def test_bonus_confirmed_exclusion_shared_tax(self):
  r=b.compare(count=1,exempt=1000000,confirmed='예',bonus_own='0,0,0',welfare_own='0,0,0',bonus_company='10000',welfare_company='0').metrics
  diff=earned(salary=61000000).metrics['예상 결정세액 (국세+지방세)']-earned(salary=60000000).metrics['예상 결정세액 (국세+지방세)']
  self.assertEqual(r['상여안 추가 소득세 추정'],diff)
  self.assertEqual(r['복지안 추가 소득세 추정'],0)
  self.assertEqual(r['복지안 선택 시 직원 순혜택 증가'],diff)
  self.assertEqual(r['복지안 선택 시 회사 지출 감소'],10000)
  low=b.compare(count=1,salary=20000000).metrics['상여안 추가 소득세 추정']
  high=b.compare(count=1,salary=200000000).metrics['상여안 추가 소득세 추정']
  self.assertGreater(high,low)
 def test_insurance_deductions_and_zero(self):
  r=b.compare(count=2,bonus_own='10000,20000,3000',welfare_own='10000,20000,3000',bonus_company='45000',welfare_company='45000').metrics
  self.assertEqual(r['복지안 선택 시 직원 순혜택 증가'],0)
  self.assertEqual(r['복지안 선택 시 회사 지출 감소'],0)
  self.assertEqual(r['상여안 전체 순혜택 추정'],2000000-r['상여안 추가 소득세 추정']-66000)
  self.assertEqual(b.compare(amount=0).metrics['상여안 추가 소득세 추정'],0)
 def test_invalid(self):
  for fn,kw in [(f.fund,{'people':0}),(f.fund,{'rate':51}),(f.fund,{'kind':f.TYPES[1],'rate':81}),(b.compare,{'exempt':100}),(b.compare,{'exempt':1000001,'confirmed':'예'}),(b.compare,{'bonus_own':'1,2'}),(b.compare,{'bonus_company':'nan'}),(b.compare,{'count':0})]:
   with self.subTest(kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_views_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,label,value in [(f,'회사 현금 출연액','100,000,000원'),(b,'총 지급·혜택 금액','20,000,000원'),(m,'원천징수 후 실제 입금액','200,000,000원')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==label),value)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   fields=mod.FIELDS[mod.NAME];vals=[x[1] for x in fields]
   txt,csv=build_exports(mod.NAME,fields,vals,mod.calculate(mod.NAME,vals),'2026-09-26')
   self.assertIn(value,txt);self.assertIn(value,csv.decode('utf-8-sig'))

 def test_maturity_baseline_and_company_bracket(self):
  r=m.maturity(confirmed='예').metrics
  self.assertEqual(r['세무상 보험 정산손익'],50000000)
  self.assertEqual(r['국세·지방세 산출세액 증감'],5500000)
  self.assertEqual(r['세액 증감 반영 경제적 유입 추정'],194500000)
  self.assertEqual(m.maturity(confirmed='예',income='500000000').metrics['국세·지방세 산출세액 증감'],11000000)
 def test_maturity_loss_basis_and_withholding(self):
  r=m.maturity(mode=m.MODES[1],received=100000000,confirmed='예',income='500000000').metrics
  self.assertEqual(r['세무상 보험 정산손익'],-50000000)
  self.assertEqual(r['국세·지방세 산출세액 증감'],-11000000)
  self.assertEqual(r['원천징수 후 실제 입금액'],100000000)
  r=m.maturity(tax_basis=100000000,confirmed='예',withheld=1000000).metrics
  self.assertEqual(r['회계손익 대비 세무조정'],50000000)
  self.assertEqual(r['세무상 보험 정산손익'],100000000)
  self.assertEqual(r['원천징수 후 실제 입금액'],199000000)
  self.assertEqual(r['세액 증감 반영 경제적 유입 추정'],189000000)
  self.assertEqual(m.maturity(income='-100000000',confirmed='예').metrics['국세·지방세 산출세액 증감'],0)
 def test_maturity_unknown_and_transfer_guard(self):
  self.assertIsInstance(m.maturity().metrics['국세·지방세 산출세액 증감'],str)
  with self.assertRaises(ValueError):m.maturity(mode=m.MODES[2])
  with self.assertRaises(ValueError):m.maturity(withheld=200000001)
