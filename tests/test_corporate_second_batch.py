import unittest
from modules import corp_vs_individual as c,deemed_interest_diagnostic as i,dc_contribution as d
from modules.finance_models import D

class CorporateSecondBatchTests(unittest.TestCase):
 def test_source_dc_baseline_and_crossing(self):
  r=d.dc().metrics
  self.assertEqual(r['직원 최소 부담금'],50000000)
  self.assertEqual(r['법인세·지방세 감소 추정'],11000000)
  r=d.dc(state=d.STATES[1],officer=10000000,base=220000000).metrics
  self.assertEqual(r['당기 손금산입액'],60000000)
  self.assertEqual(r['법인세·지방세 감소 추정'],8800000)
 def test_dc_minimum_is_not_cap(self):
  r=d.dc(mode=d.MODES[1],paid=70000000).metrics
  self.assertEqual(r['당기 손금산입액'],70000000)
  self.assertEqual(r['직원 납입 부족액'],0)
  self.assertEqual(d.dc(mode=d.MODES[1],paid=10000000).metrics['직원 납입 부족액'],40000000)
  self.assertEqual(d.dc(base=10000000).metrics['법인세·지방세 감소 추정'],1100000)
 def test_dc_retirement_clawback(self):
  r=d.dc(wages=0,state=d.STATES[2],officer=10000000,prior=100000000,limit=80000000,confirmed='예',base=200000000).metrics
  self.assertEqual(r['임원 당기 손금불산입액'],10000000)
  self.assertEqual(r['과거 부담금 익금산입액'],20000000)
  self.assertEqual(r['순 소득 감소액'],-20000000)
  self.assertEqual(r['법인세·지방세 감소 추정'],-4400000)
  r=d.dc(wages=0,state=d.STATES[2],officer=10000000,prior=100000000,limit=105000000,confirmed='예').metrics
  self.assertEqual(r['당기 손금산입액'],5000000)
  self.assertEqual(r['과거 부담금 익금산입액'],0)
 def test_diagnostic_source_interest_corrected_increment(self):
  r=i.diagnostic(confirmed='예').metrics
  self.assertEqual(r['상여처분 가정액'],9200000)
  self.assertEqual(r['대표 소득세 증가 추정'],3801160) # source607200, ignores salary marginal tax
  self.assertEqual(i.diagnostic(confirmed='예',received_rate=4.6).metrics['대표 소득세 증가 추정'],0)
  self.assertEqual(i.diagnostic(confirmed='예',received_rate=4.371).metrics['상여처분 가정액'],0)
  self.assertEqual(i.diagnostic(confirmed='예',received_rate=4.37).metrics['상여처분 가정액'],460000)
 def test_zero_dividend_cash_reconciliation(self):
  r=c.compare().metrics
  self.assertEqual(r['법인세·지방세'],19800000) # source agrees
  self.assertEqual(r['배당 추가 세액'],0) # source12610400 even at zero
  self.assertEqual(r['법인에 남는 당기 이익'],160200000)
  self.assertEqual(r['대표 수령 현금 (입력 보험료 차감)']+r['법인에 남는 당기 이익']+r['법인·대표 합산세액'],300000000)
  r=c.compare(dividend=20000000).metrics
  self.assertEqual(r['배당 추가 세액'],3080000)
  self.assertEqual(r['법인에 남는 당기 이익'],140200000)
  self.assertEqual(c.compare(dividend=50000000,mode=c.MODES[1],confirmed='예',extra_tax=12000000).metrics['배당 추가 세액'],12000000)
 def test_conditions_rejected(self):
  for fn,kw in [(d.dc,{'officer':1}),(d.dc,{'state':d.STATES[2]}),(d.dc,{'paid':1}),
   (i.diagnostic,{}),(i.diagnostic,{'confirmed':'예','rate':float('nan')}),
   (c.compare,{'dividend':20000001}),(c.compare,{'dividend':1,'other_financial':20000000}),
   (c.compare,{'salary':300000001}),(c.compare,{'dividend':170000000,'mode':c.MODES[1],'confirmed':'예'}),
   (c.compare,{'mode':c.MODES[1],'confirmed':'예','extra_tax':1})]:
   with self.subTest(fn=fn.__name__,kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_three_ui_and_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,metric,expected in [(c,'법인에 남는 당기 이익','160,200,000원'),(i,'대표 소득세 증가 추정','3,801,160원'),(d,'직원 최소 부담금','50,000,000원')]:
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run()
   vals=[f[1] for f in mod.FIELDS[mod.NAME]]
   if mod==i:
    at.selectbox(key=f'cov_{mod.NAME}_4').select('예');vals[4]='예'
   at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==metric),expected)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   txt,csv=build_exports(mod.NAME,mod.FIELDS[mod.NAME],vals,mod.calculate(mod.NAME,vals),'2026-09-26')
   self.assertIn(expected,txt);self.assertIn(expected,csv.decode('utf-8-sig'))
