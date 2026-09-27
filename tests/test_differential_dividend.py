import unittest
from modules import differential_dividend as d
class Differential(unittest.TestCase):
 def test_initial_corrects_source_proportions(self):
  r=d.differential(eligible='예',mode=d.MODES[1],deductions=0).metrics
  self.assertEqual(r['법정 비율 반영 초과배당금액'],110000000)
  self.assertEqual(r['배당소득세 증가 추정'],56386000)
  self.assertEqual(r['증여재산에서 차감하는 소득세 상당액'],23060000)
  self.assertEqual(r['증여세 추정'],3583180)
  self.assertEqual(r['소득세·증여세 합계 추정'],59969180)
 def test_minor_is_not_automatic_skipping(self):
  minor=d.differential(eligible='예',relation=d.RELATIONS[2]).metrics
  skip=d.differential(eligible='예',relation=d.RELATIONS[2],skip='예').metrics
  self.assertEqual(minor['증여세 추정'],6493180)
  self.assertEqual(skip['증여세 추정'],d.D('8441134'))
 def test_ratio_zero_and_half(self):
  r=d.differential(eligible='예',ratio=50).metrics
  self.assertEqual(r['법정 비율 반영 초과배당금액'],55000000)
  self.assertEqual(r['증여재산에서 차감하는 소득세 상당액'],7700000)
  self.assertEqual(r['증여세 추정'],0)
  self.assertEqual(d.differential(ratio=0).metrics['증여세 추정'],0)
  self.assertEqual(d.differential(received=90000000).metrics['증여세 추정'],0)
 def test_settlement_refund_no_double_count(self):
  r=d.differential(eligible='예',stage=d.STAGES[1],actual=40000000,actual_confirmed='예',first_tax=3583180,mode=d.MODES[2],confirmed_tax=50000000).metrics
  self.assertEqual(r['증여재산가액'],70000000)
  self.assertEqual(r['증여세 추정'],1940000)
  self.assertEqual(r['정산 추가 납부·환급 추정'],-1643180)
  self.assertEqual(r['소득세·증여세 합계 추정'],51940000)
  self.assertEqual(r['세후 수령 추정'],148060000)
 def test_statutory_table_boundaries(self):
  cases=[(0,0),(57600000,8064000),(57600001,d.D('8060000.24')),(88000000,15356000),(88000001,d.D('15360000.35')),(150000000,37060000),(300000000,94060000),(500000000,174060000),(1000000000,384060000),(1000000001,d.D('384060000.45'))]
  for x,y in cases:self.assertEqual(d.equivalent(x),y)
 def test_prior_gift_integration(self):
  r=d.differential(eligible='예',used=50000000,prior_value=100000000,prior_deductions=50000000,prior_base=50000000,prior_tax=5000000).metrics
  # cumulative base136.94m =>17.388m, less5m prior tax then3% filing
  self.assertEqual(r['증여세 추정'],12016360)
 def test_unknown_and_invalid(self):
  self.assertIsInstance(d.differential().metrics['증여세 추정'],str)
  self.assertIsInstance(d.differential(eligible='예').metrics['소득세·증여세 합계 추정'],str)
  for kw in ({'received':300000001},{'share':101},{'ratio':-1},{'repeated':'예'},{'stage':d.STAGES[1],'eligible':'예'},{'eligible':'예','stage':d.STAGES[1],'actual_confirmed':'예','actual':110000001},{'actual':1},{'eligible':'예','skip':'예','relation':d.RELATIONS[0]}):
   with self.subTest(kw=kw),self.assertRaises(ValueError):d.differential(**kw)
 def test_center_views_exports(self):
  from streamlit.testing.v1 import AppTest
  from modules.calculator_exports import build_exports
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select(d.NAME).run()
  next(x for x in at.selectbox if x.label=='최대주주·특수관계·단일 증여자 요건 확인').select('예').run()
  at.button[0].click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error)
  self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(next(x.value for x in at.metric if x.label=='증여세 추정'),'3,583,180원')
  fs=d.FIELDS[d.NAME];vs=[x[1] for x in fs];vs[4]='예'
  txt,csv=build_exports(d.NAME,fs,vs,d.calculate(d.NAME,vs),'2026-09-26')
  self.assertIn('3,583,180원',txt);self.assertIn('3,583,180원',csv.decode('utf-8-sig'))
  next(x for x in at.selectbox if x.label=='최근 1년 내 동일 초과배당 거래 있음').select('예').run()
  at.button[0].click().run()
  self.assertTrue(at.error);self.assertFalse(at.metric)
