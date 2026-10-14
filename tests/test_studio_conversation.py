from unittest.mock import Mock
import json
import pytest
from hwarang_academy.studio import domain as d
from hwarang_academy.studio.conversation import guard_response,explicit_close,agreed_schedule,ROLE_DRIFT
from hwarang_academy.studio.provider import Config,OpenAIProvider
from test_studio import runtime,session,response

@pytest.mark.parametrize('text',['네 오늘 상담은 이렇게 마치겠습니다','오늘 상담은 여기까지 하겠습니다.','통화는 마무리할게요.','상담을 종료하겠습니다.'])
def test_explicit_end_no_paid_request(runtime,text):
 rt,_=runtime;out=rt.send(session(stage='FIRST'),text)
 assert out['ended'] and out['end_reason']=='user' and out['usage']==[]
 assert rt.provider.generate.call_count==0
 with pytest.raises(ValueError):rt.send(out,'감사합니다')

@pytest.mark.parametrize('text',['감사합니다','상담을 마치기 전에 예산을 알려주세요','오늘 상담을 마칠까요?','고객이 "상담을 마치겠습니다"라고 하면 어떻게 하죠?','상담을 종료하지 않겠습니다','오늘은 여기까지 말고 더 이야기해요','상담을 마치기 위해 먼저 예산을 확인할게요'])
def test_not_an_explicit_end(text):assert not explicit_close(text)

@pytest.mark.parametrize('bad',['보험료 부담을 줄이는 방안에 대해 자세히 상담해 드리겠습니다.','꼼꼼히 점검해드리겠습니다.','아내분과 함께 참석 가능하신 시간으로 조율해드리겠습니다.','월 보험료 부담 정도와 가족 분들과 함께 상의하실 때 중요하게 생각하는 점이 있을까요?','부담을 느끼시는 거죠?','보장 범위와 보험료 간 균형을 중요하게 생각하시는 건가요?'])
def test_reported_role_drift(bad):
 s=session(stage='FIRST');r=guard_response(s,'보험료 부담을 말씀해 주시겠어요?',response(reply=bad,outcome='goal'))
 assert r['_guarded'] and not ROLE_DRIFT.search(r['reply']) and r['outcome']=='continue'
 d.apply_turn(s,'보험료 부담을 말씀해 주시겠어요?',r)
 assert s['turns'][-1]['customer_guarded'] and s['offtrack_count']==0

@pytest.mark.parametrize('good',['네, 제 보험을 점검해 주시면 좋겠어요.','아내와 함께 갈게요.','제가 내는 보험료가 좀 부담돼요.'])
def test_legitimate_customer_requests(good):
 assert guard_response(session(),'어떤 점이 걱정되세요?',response(reply=good))['reply']==good

def test_reported_first_consultation_closes():
 s=session(stage='FIRST')
 pairs=[('보험료를 알고 계시나요?','정확히는 기억이 안 나요.'),('증권 가지고 계신가요?','네, 집에 있어요.'),('보장분석은 사무실에서 해봐야 할 것 같습니다.','네, 확인 부탁드려요.'),('다음 주 월요일 괜찮으신가요?','네, 저녁에는 괜찮아요.'),('네 그럼 다음주 월요일 저녁 7시에 뵙겠습니다','네, 그때 뵐게요.')]
 for text,reply in pairs:d.apply_turn(s,text,guard_response(s,text,response(reply=reply)))
 assert s['ended'] and s['end_reason']=='goal' and s['appointment']['label']=='다음주 월요일 저녁 7시'
 assert len(s['turns'])==5

def test_first_turn_agreement():
 s=session(stage='FIRST');text='다음주 월요일 저녁 7시에 뵐까요?'
 d.apply_turn(s,text,guard_response(s,text,response(reply='네, 그때 뵐게요.')))
 assert s['ended']

@pytest.mark.parametrize('reply',['그날은 어렵습니다.','네, 시간을 확인해봐야 해요.','네, 화요일 저녁 8시는 어떨까요?','아직 모르겠어요.','네, 저녁 8시에 갈게요.'])
def test_no_counterproposal_close(reply):
 assert agreed_schedule(session(stage='FIRST'),'다음 주 월요일 저녁 7시에 뵐까요?',reply) is None

def test_no_invented_date():
 assert agreed_schedule(session(stage='FIRST'),'언제 괜찮으세요?','네, 다음주 월요일 저녁 7시에 갈게요.') is None

def test_no_day_only():
 assert agreed_schedule(session(stage='FIRST'),'다음주 월요일 괜찮으세요?','네, 좋아요.') is None

def test_insurance_visibility_and_rewind():
 s=session(stage='FIRST');assert 'insurance_state' not in d.prompt_context(s)['immutable_case']
 d.apply_turn(s,'증권 가지고 계신가요?',response(reply='네, 있어요.'));assert not s['documents_shared']
 d.apply_turn(s,'증권을 보여주시겠어요?',response(reply='네, 여기 있어요.'))
 assert s['documents_shared'] and 'insurance_state' in d.prompt_context(s)['immutable_case']
 d.rewind(s,2);assert not s['documents_shared']

def test_actual_provider_roles():
 http=Mock();http.post.return_value.status_code=200
 http.post.return_value.json.return_value={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(response())}]}]}
 ctx=d.prompt_context(session());ctx['conversation'].append({'role':'advisor','text':'안녕하세요'})
 OpenAIProvider(Config(api_key='fake'),http).generate('CUSTOMER',ctx)
 items=http.post.call_args.kwargs['json']['input']
 assert [x['role'] for x in items]==['developer','assistant','user'] and items[-1]['content']=='안녕하세요'
