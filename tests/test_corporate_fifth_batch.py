import unittest
from modules import vehicle_expense as v, entertainment_limit as e
class FifthBatch(unittest.TestCase):
 def test_vehicle_source_corrections(self):
  self.assertEqual(v.vehicle().metrics['당기 비용 손금 인정액'],11200000)
  self.assertEqual(v.vehicle(business=50).metrics['당기 비용 손금 인정액'],8000000)
  r=v.vehicle(logged='아니요').metrics
  self.assertEqual(r['당기 비용 손금 인정액'],11750000)
  self.assertEqual(r['감가상각 한도초과 신규 이월'],3250000)
  self.assertEqual(r['업무사용 불인정액'],1000000)
 def test_rent_and_lease(self):
  r=v.vehicle(mode='렌트',rent=12000000,logged='아니요').metrics
  self.assertEqual(r['당기 비용 손금 인정액'],15000000)
  self.assertEqual(v.vehicle(mode='리스',rent=12000000,logged='아니요').metrics['당기 비용 손금 인정액'],12537500)
  r=v.vehicle(mode='리스',rent=12000000,lease_excluded=2000000,known='예',repairs=1000000,business=100).metrics
  self.assertEqual(r['당기 비용 손금 인정액'],15000000)
  self.assertEqual(r['감가상각 한도초과 신규 이월'],1000000)
 def test_caps_insurance_plate_and_carry(self):
  for kw in [{'insured':'아니요'},{'plate':'아니요'}]:
   r=v.vehicle(**kw,carry=2000000).metrics
   self.assertEqual(r['총 손금 산입액'],0);self.assertEqual(r['차기 이월잔액'],2000000)
  self.assertEqual(v.vehicle(small='예',business=100).metrics['당기 비용 손금 인정액'],8000000)
  self.assertEqual(v.vehicle(small='예',logged='아니요').metrics['당기 비용 손금 인정액'],5000000)
  r=v.vehicle(price=30000000,business=100,carry=5000000).metrics
  self.assertEqual(r['과거 이월액 당기 추인'],2000000);self.assertEqual(r['차기 이월잔액'],3000000)
  r=v.vehicle(months=6,other=2000000,business=100).metrics
  self.assertEqual(r['당기 비용 손금 인정액'],6000000)
  self.assertEqual(v.vehicle(accumulated=60000000,business=100).metrics['당기 비용 손금 인정액'],4000000)
 def test_vehicle_accounting_identity(self):
  for mode in v.MODES:
   for percent in (0,30,80,100):
    for log in ('예','아니요'):
     r=v.vehicle(mode=mode,rent=0 if mode=='구입' else 15000000,business=percent,logged=log).metrics
     self.assertAlmostEqual(float(r['당기 차량 관련비용']),float(r['당기 비용 손금 인정액']+r['업무사용 불인정액']+r['감가상각 한도초과 신규 이월']),places=5)
 def test_entertainment_source(self):
  self.assertEqual(e.entertainment().metrics['한도 합계'],51000000)
  r=e.entertainment(related=1000000000,spent=80000000,culture=20000000).metrics
  self.assertEqual(r['한도 합계'],57960000);self.assertEqual(r['손금불산입 합계'],22040000)
 def test_revenue_bands_and_related_order(self):
  for amount,want in [(10000000000,30000000),(50000000000,110000000),(60000000000,113000000)]:
   self.assertEqual(e.revenue_limit(amount),want)
  r=e.entertainment(revenue=60000000000,related=20000000000,spent=1000000000).metrics
  # Ordinary40b ->90m; remaining20b band contribution23m, of which10%=2.3m.
  self.assertEqual(r['일반 한도'],128300000)
  self.assertEqual(e.entertainment(sme='아니요').metrics['일반 한도'],27000000)
  self.assertEqual(e.entertainment(months=6).metrics['일반 한도'],33000000)
 def test_evidence_and_culture_caps(self):
  r=e.entertainment(spent=60000000,invalid=10000000,culture=20000000,small='예').metrics
  self.assertEqual(r['일반 한도'],25500000);self.assertEqual(r['문화비 추가 한도'],5100000)
  self.assertEqual(r['손금불산입 합계'],29400000)
  self.assertEqual(r['손금 인정액']+r['손금불산입 합계'],60000000)
 def test_invalid(self):
  for fn,kw in [(v.vehicle,{'months':0}),(v.vehicle,{'business':101}),(v.vehicle,{'rent':100}),(v.vehicle,{'accumulated':60000001}),(v.vehicle,{'carry':100,'months':6}),(v.vehicle,{'mode':'리스','rent':100,'lease_excluded':101}),(e.entertainment,{'related':5000000001}),(e.entertainment,{'invalid':50000001}),(e.entertainment,{'culture':50000001})]:
   with self.subTest(kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_views_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,label,want in [(v,'당기 비용 손금 인정액','11,200,000원'),(e,'한도 합계','51,000,000원')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==label),want)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   fields=mod.FIELDS[mod.NAME];values=[x[1] for x in fields]
   txt,csv=build_exports(mod.NAME,fields,values,mod.calculate(mod.NAME,values),'2026-09-26')
   self.assertIn(want,txt);self.assertIn(want,csv.decode('utf-8-sig'))
