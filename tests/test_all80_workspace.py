"""End-to-end navigation of all catalog entries with documented baseline inputs."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from modules.jarvia_calculator_center import ITEMS

class All80Workspace(unittest.TestCase):
 def test_all_entries_execute(self):
  at=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30)
  at.secrets['passwords']={'Admin':'integration-test-only'}
  at.run();at.text_input[0].set_value('integration-test-only');at.button[0].click().run()
  at.button(key='v2_nav_quick_calculators').click().run()
  from calculator_fixtures import fill_confirmed_case
  self.assertEqual(len(ITEMS),80)
  audit=[]
  for name in ITEMS:
   with self.subTest(name=name):
    at.selectbox(key='jc_selected').select(name).run()
    fill_confirmed_case(at,name)
    next(b for b in at.button if b.label=='계산하기' and b.key!='a_calculate').click().run()
    self.assertFalse(at.exception,[x.message for x in at.exception])
    self.assertFalse(at.error,[x.value for x in at.error])
    self.assertTrue(at.metric)
    diagnostic={'연금 인출순서계산기','부가세 예정신고 선택계산기','성실신고 대상판정계산기','해외금융계좌 신고계산기','정책자금 자격진단계산기'}
    if name not in diagnostic:
     self.assertTrue(any(ch.isdigit() for ch in at.metric[0].value),(name,at.metric[0].value))
    self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
    self.assertEqual(len(at.get('download_button')),2)
    audit.append({'name':name,'metrics':{m.label:m.value for m in at.metric},'views':[x.label for x in at.tabs],'download_count':len(at.get('download_button')),'valid_input':True,'exception_count':len(at.exception),'error_count':len(at.error)})

  import os,json
  if os.environ.get('HWARANG_AUDIT_REPORT'):
   Path(os.environ['HWARANG_AUDIT_REPORT']).write_text(json.dumps({'date':'2026-09-27','environment':'local Streamlit AppTest','cases':audit},ensure_ascii=False,indent=2),encoding='utf-8')
