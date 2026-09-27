import unittest
from modules import carryforward_loss as l, vat_preliminary as v

class FourthBatch(unittest.TestCase):
 def test_loss_source_both(self):
  for kind,deduct,saving,remain in [(l.KINDS[0],240000000,37400000,260000000),(l.KINDS[1],300000000,44000000,200000000)]:
   r=l.losses(kind=kind).metrics
   self.assertEqual(r['당기 공제액'],deduct)
   self.assertEqual(r['지방세 포함 산출세액 감소 추정'],saving)
   self.assertEqual(r['다음 해 이월 가능 잔액'],remain)
 def test_loss_fifo_and_transition(self):
  r=l.losses('2020,100;2016,100;2015,100;2019,100',50,l.KINDS[1])
  self.assertEqual(r.metrics['이미 만료된 결손금'],100)
  self.assertEqual(r.metrics['올해 말 만료 예정 잔액'],50)
  self.assertEqual(r.metrics['다음 해 이월 가능 잔액'],200)
  self.assertEqual([x['마지막 공제연도'] for x in r.rows],['2025','2026','2029','2035'])
  self.assertEqual([x['당기 공제'] for x in r.rows],[0,50,0,0])
  self.assertEqual(l.losses(income=0).metrics['당기 공제액'],0)
  self.assertEqual(l.losses('2025,100',1000).metrics['당기 공제액'],100)
 def test_vat_source_and_exact_third(self):
  r=v.preliminary().metrics
  self.assertEqual(r['예정고지 납부액'],10000000)
  self.assertEqual(r['선택 신고 시 당장 납부액 감소'],7000000)
  kw=dict(prior_tax=9000000,prior_sales=120000000,sales=40000000,amount=3000000)
  r=v.preliminary(**kw).metrics
  self.assertEqual(r['예정신고 구분'],'선택 신고 요건 미충족')
  self.assertIsInstance(r['선택 신고 시 당장 납부액 감소'],str)
  for key in ('sales','amount'):
   args=dict(kw);args[key]-=1
   self.assertEqual(v.preliminary(**args).metrics['예정신고 구분'],'예정신고 선택 가능')
 def test_vat_corporate_threshold(self):
  self.assertEqual(v.preliminary(kind=v.KINDS[1],prior_sales=150000000).metrics['예정신고 구분'],'예정신고 의무')
  r=v.preliminary(kind=v.KINDS[1],prior_sales=149999999).metrics
  self.assertEqual(r['예정신고 구분'],'예정신고 선택 가능')
  self.assertEqual(v.preliminary(kind=v.KINDS[1]).metrics['예정고지 납부액'],'고지 대상 아님')
 def test_vat_rounding_and_noncollection(self):
  for prior,want in [(999999,0),(1000000,500000),(1001999,500000),(1002000,501000)]:
   self.assertEqual(v.preliminary(prior_tax=prior).metrics['예정고지 납부액'],want)
  self.assertEqual(v.preliminary(converted='예').metrics['예정고지 납부액'],0)
  self.assertEqual(v.preliminary(prior_tax=0,prior_sales=0,sales=0,amount=0).metrics['예정신고 구분'],'선택 신고 요건 미충족')
 def test_vat_refund(self):
  kw=dict(mode='환급',amount=2000000)
  r=v.preliminary(**kw).metrics
  self.assertEqual(r['조기환급 신청 추정'],0)
  self.assertEqual(r['확정신고로 넘길 일반 환급 추정'],2000000)
  r=v.preliminary(**kw,early='예').metrics
  self.assertEqual(r['조기환급 신청 추정'],2000000)
  self.assertEqual(r['확정신고로 넘길 일반 환급 추정'],0)
  self.assertEqual(r['선택 신고 시 당장 납부액 감소'],10000000)
 def test_bad_inputs(self):
  for fn,kw in [(l.losses,{'ledger':'2026,100'}),(l.losses,{'ledger':'2025,100;2025,20'}),(l.losses,{'ledger':'2025,nan'}),(l.losses,{'ledger':'2025,1.5'}),(l.losses,{'income':-1}),(v.preliminary,{'kind':'bad'}),(v.preliminary,{'kind':v.KINDS[1],'converted':'예'}),(v.preliminary,{'amount':-1})]:
   with self.subTest(kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_two_views_exports_and_invalid_clearing(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,label,value in [(l,'당기 공제액','240,000,000원'),(v,'예정고지 납부액','10,000,000원')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==label),value)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   fields=mod.FIELDS[mod.NAME];vals=[x[1] for x in fields]
   txt,csv=build_exports(mod.NAME,fields,vals,mod.calculate(mod.NAME,vals),'2026-09-26')
   self.assertIn(value,txt);self.assertIn(value,csv.decode('utf-8-sig'))
   if mod is l:
    at.text_input(key='cov_'+mod.NAME+'_0').set_value('2026,100').run();at.button[0].click().run()
    self.assertTrue(at.error);self.assertFalse(at.metric)
