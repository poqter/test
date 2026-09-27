import unittest
from modules import sincere_report as s,corporate_social_insurance as c,corporate_interim_tax as i
from modules.finance_models import D

class ThirdBatch(unittest.TestCase):
 def test_sincere_boundaries_and_source_ratio_fix(self):
  for kw in ({'retail':1500000000,'service':0},{'manufacturing':750000000,'service':0},{'service':500000000}):
   r=s.sincere(**kw).metrics
   self.assertEqual(r['수입금액 기준 판정'],'대상');self.assertEqual(r['기준 대비 비율'],100)
  self.assertEqual(s.sincere(service=499999999).metrics['수입금액 기준 판정'],'비대상')
  self.assertEqual(s.sincere(service=499999999).metrics['주업종 환산 기준까지 부족액'],1)
 def test_sincere_mixed_exact_and_credit(self):
  # Exact1/3+1/6+1/2 must be eligible.
  r=s.sincere(retail=500000000,manufacturing=125000000,service=250000000).metrics
  self.assertEqual(r['수입금액 기준 판정'],'대상')
  self.assertEqual(s.sincere(retail=750000000,service=250000000).metrics['수입금액 기준 판정'],'대상')
  self.assertEqual(s.sincere(retail=750000000,service=249999999).metrics['수입금액 기준 판정'],'비대상')
  self.assertEqual(s.sincere(fee=3000000,eligible='예').metrics['확인비용 공제 산식금액 (납부세액 한도 적용 전)'],1200000)
  self.assertEqual(s.sincere(service=0,fee=3000000,eligible='예').metrics['확인비용 공제 산식금액 (납부세액 한도 적용 전)'],0)
 def test_payroll_source_and_additional_employer_cost(self):
  r=c.company_insurance().metrics
  self.assertEqual(r['직원 부담 월 보험료 합계'],4858700) # source mislabeled company total excludes additional risks
  self.assertEqual(r['회사 고용안정·직업능력개발'],125000)
  self.assertEqual(r['회사 부담 소계 (산재 제외)'],4983700)
  self.assertIsInstance(r['회사 부담 월 보험료'],str)
  self.assertEqual(c.company_insurance(accident_rate='.7').metrics['회사 부담 월 보험료'],5333700)
 def test_per_person_caps_and_july(self):
  self.assertEqual(c.company_insurance(count=1).metrics['회사 국민연금'],313020)
  self.assertEqual(c.company_insurance(count=1,month=6).metrics['회사 국민연금'],302570)
  common={'total':10000000,'count':2}
  equal=c.company_insurance(**common).metrics['회사 국민연금']
  uneven=c.company_insurance(**common,mode=c.MODES[1],records='1000000;9000000').metrics['회사 국민연금']
  self.assertEqual(equal,475000);self.assertEqual(uneven,360520)
 def test_interim_source_and_no_permanent_savings(self):
  r=i.interim().metrics
  self.assertEqual(r['중간예납 납부 추정'],30000000)
  self.assertEqual(r['적용 방식'],'두 방식 동일')
  self.assertEqual(r['최대 분납 가능액'],15000000)
  self.assertEqual(i.interim(base=100000000).metrics['중간예납 납부 추정'],10000000)
  self.assertEqual(i.interim(prior=60000000,credit=10000000,withheld=20000000,months=6).metrics['직전연도 방식 참고액'],30000000)
 def test_interim_mandatory_exempt_and_threshold(self):
  self.assertEqual(i.interim(prior=999999).metrics['중간예납 납부 추정'],0)
  self.assertEqual(i.interim(prior=1000000).metrics['중간예납 납부 추정'],500000)
  self.assertEqual(i.interim(prior=0,prior_sme='아니요').metrics['중간예납 납부 추정'],30000000)
  self.assertEqual(i.interim(prior=1000000,status=i.STATUS[2],prior_sme='아니요').metrics['중간예납 납부 추정'],30000000)
  self.assertEqual(i.interim(prior=0,status=i.STATUS[1]).metrics['중간예납 납부 추정'],30000000)
  self.assertEqual(i.interim(new='예',prior=0).metrics['중간예납 납부 추정'],0)
 def test_interim_installments_and_confirmed_extension(self):
  r=i.interim(extension='예').metrics
  self.assertEqual(r['일반 신고기한'],'2026-08-31')
  self.assertEqual(r['1차 납부기한'],'2026-11-02');self.assertEqual(r['분납기한'],'2027-01-04')
  r=i.interim(prior=34000000,current_sme='아니요').metrics
  self.assertEqual(r['최대 분납 선택 시1차 납부'],10000000);self.assertEqual(r['최대 분납 가능액'],7000000)
  self.assertEqual(r['분납기한'],'2026-09-30')
 def test_invalid(self):
  for fn,kw in [(s.sincere,{'service':-1}),(s.sincere,{'eligible':'bad'}),
   (c.company_insurance,{'mode':c.MODES[1],'records':'5000000;5000000'}),(c.company_insurance,{'count':0}),(c.company_insurance,{'accident_rate':'nan'}),
   (i.interim,{'credit':60000001}),(i.interim,{'months':0}),(i.interim,{'current_credit':40000000})]:
   with self.subTest(fn=fn.__name__,kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_three_views_and_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,label,value in [(s,'수입금액 기준 판정','대상'),(c,'회사 부담 소계 (산재 제외)','4,983,700원'),(i,'중간예납 납부 추정','30,000,000원')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==label),value)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   fields=mod.FIELDS[mod.NAME];vals=[x[1] for x in fields]
   txt,csv=build_exports(mod.NAME,fields,vals,mod.calculate(mod.NAME,vals),'2026-09-26')
   self.assertIn(value,txt);self.assertIn(value,csv.decode('utf-8-sig'))
