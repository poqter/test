"""Real entrypoint login/navigation and finance results, no auth bypass."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from modules.finance_calculator_ui import NAMES, MODES
from modules.session_store import reset_page

class WorkspaceFinance(unittest.TestCase):
 def app(self):
  at=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30)
  at.secrets['passwords']={'Admin':'integration-test-only'}
  at.run();at.text_input[0].set_value('integration-test-only');at.button[0].click().run()
  self.assertEqual(at.session_state['active_app'],'home')
  at.button(key='v2_nav_quick_calculators').click().run();self.clean(at)
  return at
 def clean(self,at):
  self.assertFalse(at.exception,[x.value for x in at.exception]);self.assertFalse(at.error,[x.value for x in at.error])
 def calculate(self,at):
  next(b for b in at.button if b.label=='계산하기' and b.key!='a_calculate').click().run();self.clean(at)
  self.assertTrue(at.metric);self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
  self.assertEqual(len(at.get('download_button')),2)
 def test_nine_modes_in_full_app(self):
  at=self.app()
  for name in NAMES:
   with self.subTest(name=name):
    at.selectbox(key='jc_selected').select(name).run();self.calculate(at)
    if name in ('수익률계산기','재무계산기','투자수익계산기'):
     for mode in list(MODES)[1:]:
      at.selectbox(key='finance_'+name+'_mode').select(mode).run();self.calculate(at)
    if name=='현재가치계산기':
     at.radio(key='finance_'+name+'_mode').set_value('매년 정기 입금').run();self.calculate(at)
 def test_result_refresh_navigation_and_logout(self):
  at=self.app();at.selectbox(key='jc_selected').select(NAMES[0]).run();self.calculate(at)
  old=at.metric[0].value
  next(x for x in at.number_input if x.label=='처음 투자할 금액 (원)').set_value(20000000)
  self.calculate(at);self.assertNotEqual(at.metric[0].value,old)
  at.button(key='wb_home').click().run();self.clean(at)
  at.button(key='v2_nav_quick_calculators').click().run();self.clean(at)
  at.text_input(key='jc_search').set_value('복리계산기').run();self.assertEqual(at.selectbox(key='jc_selected').options,['복리계산기'])
  self.calculate(at)
  at.button(key='v2_logout').click().run();self.clean(at)
  self.assertFalse(at.session_state['password_correct']);self.assertFalse(at.metric)
 def test_legacy_exports_and_scoped_reset(self):
  at=self.app();at.button(key='a_calculate').click().run();self.clean(at)
  at.button(key='a_approve').click().run();self.clean(at)
  self.assertEqual(len(at.get('download_button')),3)
  self.assertFalse(at.warning)
  state={'password_correct':True,'login_user':'Admin','active_app':'quick_calculators','finance_X_result':object(),'coverage_result_X':object(),'cov_X_0':1,'pp_result':object(),'jc_selected':'X','rm_value':7}
  reset_page('quick_calculators',state=state)
  self.assertEqual(state,{'password_correct':True,'login_user':'Admin','active_app':'quick_calculators','rm_value':7})
