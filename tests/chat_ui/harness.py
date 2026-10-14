import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import streamlit as st
from copy import deepcopy
from unittest.mock import patch
from hwarang_academy.studio import ui,domain as d
from hwarang_academy.studio.provider import Config
OWNER='00000000-0000-0000-0000-000000000001'
class Repo:
 def __init__(self,auth,owner):self.owner=owner;self.auth=auth
 def rpc(self,name,**kw):return [] if name=='pending' else {}
 def rows(self):return []
 def recipients(self):return []
 def reviews(self,sid):return []
 def save(self,s,op=None):
  out=deepcopy(s);out['version']+=1;return out
 def load(self,sid):return st.session_state['_studio_state']
 def manager(self,*args):return []
class Runtime:
 def __init__(self,repo,provider):self.repo=repo
 def send(self,s,text):
  import time
  time.sleep(.6)
  if text=='오류 테스트':
   from hwarang_academy.studio.provider import ProviderError
   raise ProviderError('답변을 다시 보내 주세요.',uncertain=False)
  from hwarang_academy.studio.conversation import explicit_close,closing_result,guard_response
  out=deepcopy(s);result=dict(reply='네, 여기 증권이 있어요.' if '증권' in text else '보험료가 늘어날까 봐 걱정됩니다.',relevance='ontrack',confidence=.95,reason='관련 응답',confirm_streak=False,trust_delta=2,concern='보험료 부담',disclosed_keys=[],outcome='continue')
  result['reaction']={'kind':'boundary','openness':'reserved','pressure':'some','advisor_quote':text,'customer_quote':result['reply']}
  d.apply_turn(out,text,closing_result() if explicit_close(text) else guard_response(s,text,result));return self.repo.save(out)
 def hint(self,s):
  out=deepcopy(s);out['hint_cache'][f"{s['branch']}:{len(s['turns'])}:{s['stage']}"]={'direction':'걱정을 먼저 확인하세요.','intention':'실제 부담을 파악합니다.','example':'어떤 부분이 가장 부담스러우세요?'};return self.repo.save(out)
 def evaluate(self,s):
  out=deepcopy(s);out['report']={'status':'피드백 완료','notice':'검증용 예시','rows':[],'strengths':['고객의 걱정을 물었습니다.'],'improvements':['통화 가능한지 먼저 확인해 보세요.']};return self.repo.save(out)
st.session_state['_studio_owner']=OWNER
if '_studio_state' not in st.session_state:st.session_state['_studio_state']=d.new_session(OWNER,stage='FIRST')
with patch.object(ui,'Repository',Repo),patch.object(ui,'Runtime',Runtime),patch.object(Config,'from_mapping',return_value=Config(api_key='fake-non-network')):
 ui.render(object(),OWNER,{'academy.simulator','academy.formal_ai_assessment','academy.voice_simulator'})
