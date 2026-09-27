import unittest
from datetime import date
from modules import corporate_tax as c,deemed_interest as i,executive_severance as e
from modules.finance_models import D

class CorporateBatchTests(unittest.TestCase):
 def test_corporate_source_and_local_correction(self):
  r=c.corporate(subject=60000000).metrics
  self.assertEqual(r['산출 법인세'],80000000)
  self.assertEqual(r['결정 법인세'],35000000)
  self.assertEqual(r['적용된 최저한세 대상 공제'],45000000)
  self.assertEqual(r['법인지방소득세 산출액'],8000000)
  self.assertEqual(r['세목별 차감액 단순 합계'],43000000) # original38.5m wrong local
 def test_corporate_brackets_losses_and_exempt(self):
  for base,expected in [(200000000,20000000),(20000000000,3980000000),(300000000000,65580000000),(300000000001,D('65580000000.25'))]:
   self.assertEqual(c.bracket(base),expected)
  self.assertEqual(c.bracket(200000000,True),40000000)
  self.assertEqual(c.corporate(profit=100000000,kind=c.KINDS[3],full_loss='아니요',loss=100000000).metrics['과세표준'],20000000)
  self.assertEqual(c.corporate(profit=100000000,loss=100000000).metrics['과세표준'],0)
  self.assertEqual(c.corporate(subject=60000000,exempt=35000000).metrics['결정 법인세'],0)
  self.assertEqual(c.corporate(prepaid=100000000).metrics['국세 납부·환급 추정'],-20000000)
  self.assertEqual(c.minimum(D(110000000000),c.KINDS[3]),13500000000)
 def test_interest_source_threshold_and_cap(self):
  self.assertEqual(i.interest(confirmed='예').metrics['인정이자 익금산입'],4600000)
  self.assertEqual(i.interest(confirmed='예',received=4370001).metrics['인정이자 익금산입'],0)
  r=i.interest(confirmed='예',received=4370000,borrowing=73000000000,paid=10000000).metrics
  self.assertEqual(r['인정이자 익금산입'],230000)
  self.assertEqual(r['지급이자 손금불산입'],5000000)
  self.assertEqual(i.interest(confirmed='예',borrowing=1,paid=10000000).metrics['지급이자 손금불산입'],10000000)
 def test_interest_daily_offsets_and_weighted(self):
  # Deposit excess in Jan cannot cancel a February loan.
  r=i.interest(start='2026-01-01',end='2026-02-28',mode=i.MODES[2],records='2026-01-01,0,100000000;2026-02-01,100000000,0',confirmed='예')
  self.assertEqual(r.metrics['적용 순적수'],2800000000)
  self.assertEqual(i.interest(confirmed='예',rate_mode=i.RATES[1],weighted=5).metrics['인정이자 시가'],5000000)
 def test_executive_source_and_correct_excess(self):
  r=e.executive().metrics
  self.assertEqual(r['개인 퇴직소득 한도'],468000000)
  self.assertEqual(r['근로소득으로 분류되는 초과액'],32000000) # original0 wrong
  self.assertEqual(e.executive(old=60000000).metrics['개인 퇴직소득 한도'],360000000)
  self.assertEqual(e.executive(old=60000000).metrics['근로소득으로 분류되는 초과액'],140000000)
  self.assertEqual(e.executive(confirmed='예').metrics['법인 손금 한도 초과액'],0)
 def test_exec_calendar_and_corporate_separation(self):
  self.assertEqual(e.months_ceil(date(2026,1,31),date(2026,2,27)),1)
  self.assertEqual(e.months_ceil(date(2026,1,31),date(2026,2,28)),2)
  self.assertEqual(e.executive(start='2026-12-31',recent=120000000,old=0).metrics['개인 퇴직소득 한도'],2000000)
  r=e.executive(confirmed='예',corp_limit=300000000).metrics
  self.assertEqual(r['법인 손금 한도 초과액'],200000000)
  self.assertEqual(r['근로소득으로 분류되는 초과액'],32000000)
 def test_guards(self):
  for fn,kw in ((c.corporate,{'profit':float('nan')}),(i.interest,{}),(i.interest,{'confirmed':'예','paid':1}),
   (i.interest,{'confirmed':'예','end':'2027-01-01'}),(i.interest,{'confirmed':'예','mode':i.MODES[2],'records':'2026-02-01,1,0'}),
   (e.executive,{'start':'2010-01-01'}),(e.executive,{'pre2012':1}),(e.executive,{'end':'2025-12-31'})):
   with self.subTest(fn=fn.__name__,kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_three_ui_and_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod,metric,expected in ((c,'산출 법인세','80,000,000원'),(i,'인정이자 익금산입','4,600,000원'),(e,'개인 퇴직소득 한도','468,000,000원')):
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run()
   vals=[f[1] for f in mod.FIELDS[mod.NAME]]
   if mod==i:
    at.selectbox(key=f'cov_{mod.NAME}_9').select('예');vals[9]='예'
   at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual(next(m.value for m in at.metric if m.label==metric),expected)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   txt,csv=build_exports(mod.NAME,mod.FIELDS[mod.NAME],vals,mod.calculate(mod.NAME,vals),'2026-09-26')
   self.assertIn(expected,txt);self.assertIn(expected,csv.decode('utf-8-sig'))
