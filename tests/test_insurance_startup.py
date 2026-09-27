import unittest
from modules.social_insurance import insurance, SIZES, NAME as SOCIAL
from modules.startup_tax_credit import startup, REGIONS, KINDS, FIRST, QUALIFICATIONS, NAME as STARTUP


class InsuranceTests(unittest.TestCase):
 def test_rates_company_and_unknown(self):
  r=insurance()
  self.assertEqual(r.metrics['본인 부담 월 보험료'],388690)
  self.assertEqual(r.metrics['사업주 부담 소계 (산재 제외)'],398690)
  self.assertIsInstance(r.metrics['사업주 부담 월 보험료'],str)
  self.assertEqual(insurance(accident_rate='0.7').metrics['사업주 부담 월 보험료'],426690)
  self.assertEqual(insurance(accident_rate='0',size=SIZES[3]).metrics['사업주 부담 월 보험료'],422690)

 def test_caps_and_noncoverage(self):
  self.assertEqual(insurance(month=6,nps_base=9000000).rows[0]['본인 부담'],302570)
  self.assertEqual(insurance(month=7,nps_base=9000000).rows[0]['본인 부담'],313020)
  self.assertEqual(insurance(nps_base=0).rows[0]['본인 부담'],19470)
  self.assertEqual(insurance(health_base=0).rows[1]['본인 부담'],10080)
  self.assertEqual(insurance(health_base=10**12).rows[1]['본인 부담'],4591740)
  r=insurance(nps_on='아니요',health_on='아니요',unemployment_on='아니요',training_on='아니요',accident_rate='0')
  self.assertEqual(r.metrics['본인 부담 월 보험료'],0)
  self.assertEqual(r.metrics['사업주 부담 월 보험료'],0)
  for kwargs in ({'month':0},{'month':13},{'accident_rate':'nan'},{'nps_base':-1}):
   with self.assertRaises(ValueError):insurance(**kwargs)


class StartupTests(unittest.TestCase):
 def calc(self,**kwargs):
  args=dict(first_state=FIRST[0],first_year=2024,qualification=QUALIFICATIONS[1],revenue=200000000)
  args.update(kwargs);return startup(**args)

 def test_regions_and_years(self):
  self.assertEqual(self.calc().metrics['기본 감면 계산액 (최저한세 등 조정 전)'],6000000)
  for kind,rates in ((KINDS[0],(50,50,25,0)),(KINDS[1],(100,100,75,50))):
   for region,rate in zip(REGIONS,rates):
    r=self.calc(start_year=2026,first_year=2026,region=region,kind=kind)
    self.assertEqual(r.metrics['기본 감면율 (확인된 입력 조건 기준)'],rate)
    self.assertEqual(r.metrics['기본 감면 계산액 (최저한세 등 조정 전)'],12000000*rate/100)
  self.assertEqual(self.calc(revenue=104000000).metrics['기본 감면 계산액 (최저한세 등 조정 전)'],12000000)
  self.assertEqual(self.calc(revenue=104000001).metrics['기본 감면 계산액 (최저한세 등 조정 전)'],6000000)

 def test_period_unknown_cap_and_service(self):
  self.assertIsInstance(startup().metrics['기본 감면 계산액 (최저한세 등 조정 전)'],str)
  self.assertIsInstance(self.calc(revenue='').metrics['기본 감면 계산액 (최저한세 등 조정 전)'],str)
  self.assertEqual(self.calc(start_year=2020,first_year=2020).metrics['기본 감면 계산액 (최저한세 등 조정 전)'],0)
  self.assertEqual(self.calc(start_year=2020,first_year=2026).metrics['감면 시작연도'],'2025')
  self.assertEqual(self.calc(start_year=2025,first_year=2025,tax=2000000000).metrics['기본 감면 계산액 (최저한세 등 조정 전)'],500000000)
  self.assertEqual(self.calc(start_year=2024,tax=2000000000).metrics['기본 감면 계산액 (최저한세 등 조정 전)'],1000000000)
  self.assertEqual(self.calc(new_service='예').metrics['기본 감면율 (확인된 입력 조건 기준)'],75)
  with self.assertRaises(ValueError):self.calc(first_state=FIRST[1],first_year=0)
  with self.assertRaises(ValueError):self.calc(first_year=2023)


class CenterTests(unittest.TestCase):
 def test_new_screens_and_export(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  from modules.social_insurance import FIELDS as SF
  from modules.startup_tax_credit import FIELDS as CF
  for name,fields,calc in ((SOCIAL,SF,insurance),(STARTUP,CF,startup)):
   with self.subTest(name=name):
    at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
    at.selectbox(key='jc_selected').select(name).run()
    at.button[0].click().run()
    self.assertFalse(at.exception);self.assertFalse(at.error)
    self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
    txt,csv=build_exports(name,fields[name],[f[1] for f in fields[name]],calc(),'2026-09-26')
    self.assertIn('2026-09-26',txt); self.assertIn('2026-09-26',csv.decode('utf-8-sig'))
    if name==SOCIAL:self.assertIn('388,690원',txt)
    else:self.assertIn('최초 소득 발생연도 미확인',txt)
