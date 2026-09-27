import unittest
from modules import profit_retirement as p,corporate_liquidation as c
from modules.shareholder_distribution import MODES
class SeventhBatch(unittest.TestCase):
 def test_profit_source_baseline_without_grossup(self):
  r=p.retirement(deductions=0,mode=MODES[1]).metrics
  self.assertEqual(r['의제배당액'],400000000)
  self.assertEqual(r['개인세 증가 추정'],141746000)
  self.assertEqual(r['주주 세후 수령 추정'],358254000)
 def test_boundary_and_loss(self):
  r=p.retirement(received=120000000).metrics
  self.assertEqual(r['개인세 증가 추정'],3080000)
  self.assertEqual(r['주주 세후 수령 추정'],116920000)
  self.assertIsInstance(p.retirement(received=120000001).metrics['개인세 증가 추정'],str)
  self.assertIsInstance(p.retirement(received=120000000,other_financial=1).metrics['개인세 증가 추정'],str)
  r=p.retirement(received=90000000).metrics
  self.assertEqual(r['개인세 증가 추정'],0)
  self.assertEqual(r['주주 세후 수령 추정'],90000000)
 def test_final_tax_not_double_counted(self):
  r=p.retirement(mode=MODES[2],confirmed_tax=100000000).metrics
  self.assertEqual(r['주주 세후 수령 추정'],400000000)
  self.assertEqual(r['일반 원천징수 추정'],61600000)
 def test_liquidation_corrects_source_cost_omission(self):
  r=c.liquidation(confirmed='예',mode=MODES[1],deductions=0).metrics
  self.assertEqual(r['회사 청산세 합계'],396000000)
  self.assertEqual(r['주주 수령액 (개인세 전)'],1604000000)
  self.assertEqual(r['의제배당액'],1504000000)
  self.assertEqual(r['개인세 증가 추정'],665126000)
  self.assertEqual(r['주주 세후 수령 추정'],938874000)
 def test_return_of_capital_is_not_dividend(self):
  r=c.liquidation(residual=100000000,pool=100000000,confirmed='예').metrics
  self.assertEqual(r['회사 청산세 합계'],0)
  self.assertEqual(r['의제배당액'],0)
  self.assertEqual(r['주주 세후 수령 추정'],100000000)
 def test_equity_separate_shareholder_and_unknown(self):
  self.assertIsInstance(c.liquidation().metrics['주주 세후 수령 추정'],str)
  r=c.liquidation(equity=2000000000,confirmed='예',share=50,basis=1000000000).metrics
  self.assertEqual(r['회사 청산세 합계'],0)
  self.assertEqual(r['주주 수령액 (개인세 전)'],1000000000)
  self.assertEqual(r['의제배당액'],0)
  r=c.liquidation(residual=200000000,equity=0,pool=200000000,confirmed='예',small='예',share=0,basis=0).metrics
  self.assertEqual(r['회사 청산세 합계'],44000000)
  self.assertEqual(r['주주 수령액 (개인세 전)'],0)
 def test_invalid(self):
  for fn,kw in [(p.retirement,{'received':-1}),(p.retirement,{'mode':'bad'}),(p.retirement,{'confirmed_tax':1}),(p.retirement,{'mode':MODES[2],'confirmed_tax':500000001}),(c.liquidation,{'confirmed':'예','pool':1}),(c.liquidation,{'share':101})]:
   with self.subTest(kw=kw),self.assertRaises(ValueError):fn(**kw)
 def test_views_and_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  for mod in (p,c):
   at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
   at.selectbox(key='jc_selected').select(mod.NAME).run();at.button[0].click().run()
   self.assertFalse(at.exception);self.assertFalse(at.error)
   self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
   fields=mod.FIELDS[mod.NAME];values=[x[1] for x in fields]
   txt,csv=build_exports(mod.NAME,fields,values,mod.calculate(mod.NAME,values),'2026-09-26')
   self.assertIn('확인',txt);self.assertIn('확인',csv.decode('utf-8-sig'))
  # Exercise a real numeric liquidation through the UI, not just its unknown state.
  next(x for x in at.selectbox if x.label=='청산 재산·자기자본의 세무조정 확인').select('예').run()
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual(next(x.value for x in at.metric if x.label=='회사 청산세 합계'),'396,000,000원')
