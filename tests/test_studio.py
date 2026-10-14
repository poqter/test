from copy import deepcopy
import io,wave,json
from unittest.mock import Mock
import pytest
from hwarang_academy.studio import domain as d
from hwarang_academy.studio.provider import Config,OpenAIProvider,ProviderError,wav_seconds
from hwarang_academy.studio.runtime import Runtime,PendingRequest
from hwarang_academy.studio.contracts import EVALUATOR
OWNER='00000000-0000-0000-0000-000000000001'
def response(**kw):
 r=dict(reply='조금 더 설명해 주실래요?',relevance='ontrack',confidence=.95,reason='상담 관련',confirm_streak=False,trust_delta=2,concern='보험료',disclosed_keys=[],outcome='continue');r.update(kw);return r
def session(**kw):return d.new_session(OWNER,seed=12,**kw)
@pytest.mark.parametrize('stage',d.STAGES)
@pytest.mark.parametrize('mode',['PRACTICE','ASSESSMENT'])
def test_stages(stage,mode):
 s=session(stage=stage,mode=mode);original=deepcopy(s['case']);d.apply_turn(s,'어떤 점이 걱정되세요?',response());assert s['case']==original and len(s['turns'])==1

def test_offtrack_warning():
 s=session(mode='ASSESSMENT');r=response(relevance='offtrack',confirm_streak=True)
 d.apply_turn(s,'무관',r);assert not s['warning'] and not s['ended']
 d.apply_turn(s,'무관',r);assert s['warning'] and not s['ended']
 d.apply_turn(s,'무관',r);assert s['end_reason']=='offtrack'
@pytest.mark.parametrize('relevance,confidence',[('uncertain',.4),('ontrack',.95),('offtrack',.5)])
def test_ambiguous_resets(relevance,confidence):
 s=session()
 for _ in range(2):d.apply_turn(s,'무관',response(relevance='offtrack'))
 d.apply_turn(s,'잘 모르겠어요',response(relevance=relevance,confidence=confidence));assert s['offtrack_count']==0 and not s['warning']
def test_unconfirmed_third_strike():
 s=session()
 for _ in range(3):d.apply_turn(s,'무관',response(relevance='offtrack'))
 assert not s['ended']
def test_rewind():
 s=session();case=deepcopy(s['case']);start=deepcopy(s['customer_state'])
 for _ in range(4):d.apply_turn(s,'보험료?',response())
 s['usage']=[{'credits':4}];d.rewind(s,3);assert len(s['turns'])==2
 d.rewind(s,1);assert not s['turns'] and s['customer_state']==start and s['case']==case and s['usage']==[{'credits':4}]
def test_official_rewind_denied():
 s=session(mode='ASSESSMENT');d.apply_turn(s,'안녕하세요',response())
 with pytest.raises(ValueError):d.rewind(s,1)
def test_journey():
 s=session(journey=True);case=deepcopy(s['case'])
 for stage in d.STAGES:
  assert s['stage']==stage
  d.apply_turn(s,'설명드려도 될까요?',response());d.apply_turn(s,'약속',response(outcome='goal'))
  if not s['ended']:d.next_stage(s)
 assert s['end_reason']=='goal' and s['case']==case
def test_turn_limit():
 s=session();d.apply_turn(s,'네',response(outcome='goal'));assert not s['ended']
 for _ in range(d.LIMITS['TA']-1):d.apply_turn(s,'대화',response())
 assert s['end_reason']=='limit'
def test_exit():
 s=session();d.apply_turn(s,'다음에 연락드리겠습니다',response(outcome='customer_exit'));assert s['end_reason']=='customer_exit'
def report():
 return {'rows':[{'criterion':k,'level':'developing','evidence':[{'turn':1,'quote':'안녕하세요'}],'feedback':'인사','alternative':'통화 가능하실까요?'} for k in d.CRITERIA],'strengths':['인사'],'improvements':['동의'],'retrain_turns':[1]}
def test_evidence():
 s=session();d.apply_turn(s,'안녕하세요, 소개받고 연락드렸습니다',response());d.end_session(s,'user')
 assert d.validate_report(s,report())['total_score'] is None
 r=report();r['rows'][0]['evidence'][0]['quote']='없는 말'
 with pytest.raises(ValueError):d.validate_report(s,r)
def test_share_projection():
 s=session();d.apply_turn(s,'안녕하세요',response());d.end_session(s,'user');s['report']=report()
 shared=d.share_payload(s,['summary']);assert '안녕하세요' not in json.dumps(shared,ensure_ascii=False) and 'transcript' not in shared
 with pytest.raises(ValueError):d.share_payload(s,[])
def test_bad_input():
 s=session();before=deepcopy(s)
 for text in ('',' '*5,'x'*2401):
  with pytest.raises(ValueError):d.apply_turn(s,text,response())
 assert s==before
def test_provider_contract():
 http=Mock();http.post.return_value.status_code=200;http.post.return_value.json.return_value={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(response())}]}]}
 OpenAIProvider(Config(api_key='test-placeholder'),http).generate('CUSTOMER',{})
 body=http.post.call_args.kwargs['json'];assert body['store'] is False and body['text']['format']['strict'] is True
def test_practice_contract():
 http=Mock();http.post.return_value.status_code=200;http.post.return_value.json.return_value={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(report())}]}]}
 OpenAIProvider(Config(api_key='x'),http).generate('COACH',{'_practice_report':True})
 assert http.post.call_args.kwargs['json']['text']['format']['schema']==EVALUATOR
def test_timeout():
 import requests
 http=Mock();http.post.side_effect=requests.Timeout()
 with pytest.raises(ProviderError) as e:OpenAIProvider(Config(api_key='x'),http).generate('CUSTOMER',{})
 assert e.value.uncertain and http.post.call_count==1
def test_incomplete():
 http=Mock();http.post.return_value.status_code=200;http.post.return_value.json.return_value={'status':'incomplete'}
 with pytest.raises(ProviderError) as e:OpenAIProvider(Config(api_key='x'),http).generate('CUSTOMER',{})
 assert e.value.uncertain
def test_wav():
 f=io.BytesIO()
 with wave.open(f,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0'*16000)
 assert wav_seconds(f.getvalue())==1
 with pytest.raises(ValueError):wav_seconds(b'bad')
class MemoryRepo:
 def __init__(self):self.auth=object();self.ops={};self.saved=[]
 def claim(self,s,k,role):
  if k in self.ops:return {**self.ops[k],'fresh':False}
  self.ops[k]={'status':'claimed'};return {**self.ops[k],'fresh':True}
 def update(self,k,status,request=None,result=None):
  self.ops[k].update(status=status,request_id=request)
  if result is not None:self.ops[k]['result']=result
 def save(self,s,k=None):
  s=deepcopy(s);s['version']+=1;self.saved.append(s);return s
@pytest.fixture
def runtime(monkeypatch):
 import hwarang_academy.studio.runtime as m
 calls=[]
 monkeypatch.setattr(m,'reserve_ai_request',lambda *a,**k:{'request_id':'req1','request_status':'reserved','duplicate':False})
 monkeypatch.setattr(m,'start_ai_request',lambda *a,**k:{'request_status':'processing'})
 monkeypatch.setattr(m,'finalize_ai_request',lambda *a,**k:calls.append(k))
 monkeypatch.setattr(m,'release_ai_session',lambda *a,**k:None)
 provider=Mock();provider.config=Config();provider.generate.return_value={'result':response(),'usage':{},'model':'test'}
 return Runtime(MemoryRepo(),provider),calls
def test_duplicate(runtime):
 rt,calls=runtime;s=session();a=rt.send(s,'안녕하세요');b=rt.send(s,'안녕하세요')
 assert rt.provider.generate.call_count==1 and len(calls)==1 and a['turns']==b['turns']
def test_uncertain(runtime):
 rt,calls=runtime;s=session();rt.provider.generate.side_effect=ProviderError('timeout')
 with pytest.raises(ProviderError):rt.send(s,'안녕하세요')
 with pytest.raises(PendingRequest):rt.send(s,'안녕하세요')
 assert rt.provider.generate.call_count==1 and not calls
def test_save_crash(runtime):
 rt,calls=runtime;s=session();save=rt.repo.save;rt.repo.save=Mock(side_effect=RuntimeError('db'))
 with pytest.raises(RuntimeError):rt.send(s,'안녕하세요')
 rt.repo.save=save;out=rt.send(s,'안녕하세요');assert rt.provider.generate.call_count==1 and len(out['turns'])==1 and len(calls)==1
def test_formal_hint(runtime):
 rt,_=runtime
 with pytest.raises(ValueError):rt.hint(session(mode='ASSESSMENT'))
 assert rt.provider.generate.call_count==0
def test_cached_hint(runtime):
 rt,calls=runtime;rt.provider.generate.return_value={'result':{'direction':'a','intention':'b','example':'c'},'usage':{},'model':'test'}
 s=rt.hint(session());rt.hint(s);assert rt.provider.generate.call_count==1 and len(calls)==1

def test_bad_audio_does_not_lock(runtime):
 rt,_=runtime
 with pytest.raises(ValueError):rt.transcribe(session(),b'not-wav')
 assert not rt.repo.ops

def test_disabled_service_is_not_unknown(runtime,monkeypatch):
 import hwarang_academy.studio.runtime as m
 rt,calls=runtime
 def reject(*a,**k):raise RuntimeError('AI_SERVICE_DISABLED')
 monkeypatch.setattr(m,'reserve_ai_request',reject)
 with pytest.raises(RuntimeError):rt.send(session(),'안녕하세요')
 assert next(iter(rt.repo.ops.values()))['status']=='failed' and rt.provider.generate.call_count==0

def test_formal_retraining_is_new_private_session():
 s=session(mode='ASSESSMENT')
 for _ in range(3):d.apply_turn(s,'안녕하세요',response())
 d.end_session(s,'user');out=d.practice_from(s,2)
 assert out['mode']=='PRACTICE' and out['id']!=s['id'] and out['case']==s['case'] and s['ended']
 assert out['baseline_turns']==1 and out['usage']==[]
