import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from modules import unlisted_valuation as c
class Valuation(unittest.TestCase):
 def test_source_cases(self):
  cases=[({},26000),({'re':50},24000),({'re':50,'major':'예'},28800),({'re':50,'major':'예','method':c.METHODS[1],'factor':c.FACTORS[1]},24000)]
  for kwargs,expected in cases:self.assertEqual(c.value(confirmed='확인',**kwargs).metrics['1주당 보충적 평가액'],expected)
  self.assertEqual(c.value(confirmed='확인',re=50,major='예',method=c.METHODS[1],factor=c.FACTORS[1],premium=20).metrics['가정에 따른 1주당 참고값'],28800)
 def test_rules(self):
  def v(**kw):return c.value(confirmed='확인',**kw).metrics['1주당 보충적 평가액']
  self.assertEqual(v(p1=0,p2=0,p3=0),16000)
  self.assertEqual(v(p1=0,p2=0,p3=0,re=80),20000)
  self.assertEqual(v(re=80),24000)
  self.assertEqual(v(stock=80),26000)
  self.assertEqual(v(p1=-1,p2=-1,p3=-1,method=c.METHODS[4]),16000)
  for exemption in c.EXEMPT[1:]:self.assertEqual(v(major='예',exempt=exemption),26000)
  self.assertEqual(v(assets=0,liab=0,p1=0,p2=0,p3=0),0)
  self.assertEqual(v(p1=100000000,p2=200000000,p3=300000000,n1=100000,n2=200000,n3=300000),16000)
  for kwargs in ({'shares':0},{'shares':1.5},{'date':'2026-02-26'},{'asset_adj':'nan'},{'liab_adj':'-1000000001'}):
   with self.assertRaises(ValueError):v(**kwargs)
 def test_full_app(self):
  at=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30);at.secrets['passwords']={'Admin':'integration-test-only'};at.run();at.text_input[0].set_value('integration-test-only');at.button[0].click().run();at.button(key='v2_nav_quick_calculators').click().run();at.selectbox(key='jc_selected').select(c.NAME).run()
  at.selectbox(key='cov_'+c.NAME+'_23').select('확인');next(b for b in at.button if b.label=='계산하기' and b.key!='a_calculate').click().run()
  self.assertFalse(at.exception);self.assertFalse(at.error);self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertIn('26,000원',[m.value for m in at.metric])
