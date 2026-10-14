from copy import deepcopy
import json
import pytest
from test_studio import session,response
from hwarang_academy.studio import domain as d,immersion as im

def reacted(text,reply,kind='boundary',**kw):
 return response(reply=reply,reaction={'kind':kind,'openness':kw.get('openness','reserved'),'pressure':kw.get('pressure','some'),'advisor_quote':text,'customer_quote':reply},**{k:v for k,v in kw.items() if k not in ('openness','pressure')})

def test_reaction_evidence_memory_and_prompt():
 s=session(stage='FIRST');text='새로 가입하시면 어때요?';reply='바로 가입하라는 건 부담스러워요.'
 d.apply_turn(s,text,reacted(text,reply))
 ctx=d.prompt_context(s,'어떤 점이 부담스러우세요?')['interaction_context']
 assert ctx['remembered_exchanges'][-1]['customer_quote']==reply
 assert ctx['relationship']['pressure']=='some'
 assert im.visible_signals(s)==[]
 shown=im.visible_signals(s,True);assert shown[0]['quote']==reply
 assert not any(x in json.dumps(shown) for x in ('short_time','openness','trust','ground_truth'))

@pytest.mark.parametrize('mode',['PRACTICE','ASSESSMENT'])
def test_only_practice_has_optional_signals(mode):
 s=session(mode=mode);d.apply_turn(s,'가입?',reacted('가입?','부담스러워요.'))
 assert bool(im.visible_signals(s,True))==(mode=='PRACTICE')

@pytest.mark.parametrize('bad',['없는 대사',''])
def test_invented_evidence_ignored(bad):
 s=session();r=reacted('가입?','부담스러워요.');r['reaction']['customer_quote']=bad
 d.apply_turn(s,'가입?',r);assert not im.state(s)['events']

def test_guarded_response_not_a_learning_signal():
 s=session();r=reacted('가입?','부담스러워요.');r['_guarded']=True
 d.apply_turn(s,'가입?',r);assert not im.visible_signals(s,True)

def test_opening_up_needs_new_source_fact():
 s=session();text='가족은요?';reply='자녀가 있어요.'
 d.apply_turn(s,text,reacted(text,reply,'opened_up'));assert not im.state(s)['events']
 d.apply_turn(s,text,reacted(text,reply,'opened_up',disclosed_keys=['family.child_count']))
 assert im.state(s)['events'][-1]['kind']=='opened_up'

def test_emotion_changes_one_step_not_instant_conversion():
 s=session(difficulty='hard');text='마음이 쓰이셨겠어요';reply='네, 그 부분이 걱정이었어요.'
 d.apply_turn(s,text,reacted(text,reply,openness='open',pressure='high'))
 assert im.state(s)['openness']=='neutral' and im.state(s)['pressure']=='some'

def test_time_situation_fixed_and_not_repeated():
 s=session(stage='FIRST',difficulty='hard')
 for _ in range(3):d.apply_turn(s,'말씀해 주세요',response())
 assert any(x['kind']=='time_constraint' for x in im.context(s)['situations'])
 d.apply_turn(s,'조금 더 이야기할까요?',reacted('조금 더 이야기할까요?','오늘은 시간이 많지 않아요.','time_constraint'))
 assert not any(x['kind']=='time_constraint' for x in im.context(s)['situations'])
 d.rewind(s,4)
 assert any(x['kind']=='time_constraint' for x in im.context(s)['situations'])

def test_easy_customer_no_planned_time_pressure():
 s=session(difficulty='easy')
 for _ in range(4):d.apply_turn(s,'안녕하세요',response())
 assert not im.context(s)['situations']

def test_spouse_situation_follows_case():
 s=session();truth=s['case']['customer_state']['ground_truth'];truth['decision_structure']='joint_with_spouse'
 assert any(e['kind']=='family_decision' for e in im.context(s,'가입을 결정하시겠어요?')['situations'])
 truth['decision_structure']='self'
 assert not any(e['kind']=='family_decision' for e in im.context(s,'가입을 결정하시겠어요?')['situations'])

def test_document_card_once_and_rewind_restores():
 s=session(stage='FIRST');before=deepcopy(s['case'])
 d.apply_turn(s,'증권을 보여주시겠어요?',response(reply='네, 여기 있어요.'))
 assert s['messages'][-1]['attachment']=='insurance'
 d.apply_turn(s,'증권을 보여주시겠어요?',response(reply='네, 여기 있어요.'))
 assert sum(m.get('attachment')=='insurance' for m in s['messages'])==1
 d.rewind(s,1);assert not s['documents_shared'] and not im.state(s)['events'] and s['case']==before

@pytest.mark.parametrize('reply',['없어요','네, 나중에 보내드릴게요','네, 지금은 못 보여드려요'])
def test_documents_not_available_before_consent(reply):
 s=session(stage='FIRST');d.apply_turn(s,'증권을 보여주시겠어요?',response(reply=reply))
 assert not s['documents_shared'] and not s['messages'][-1].get('attachment')

@pytest.mark.parametrize('stage',['COVERAGE','PROPOSAL'])
def test_analysis_scene_has_material_card(stage):assert session(stage=stage)['messages'][0]['attachment']=='insurance'

def test_retry_same_state_comparison_only_after_answer():
 s=session(stage='FIRST',mode='ASSESSMENT');text='가입하실래요?';reply='부담스러워요.'
 d.apply_turn(s,text,reacted(text,reply));d.end_session(s,'user')
 new=d.practice_from(s,1)
 assert new['mode']=='PRACTICE' and new['id']!=s['id'] and new['case']==s['case']
 assert im.state(new)==s['turns'][0]['before']['immersion'] and im.comparison(new) is None
 d.apply_turn(new,'가장 걱정되는 점은요?',response(reply='보험료가 부담돼요.'))
 c=im.comparison(new);assert c['before']['advisor']==text and c['after']['advisor']=='가장 걱정되는 점은요?'
 assert s['turns'][0]['text']==text

def test_moments_bounded_and_use_original_quotes():
 s=session()
 for i in range(5):d.apply_turn(s,f'질문{i}',reacted(f'질문{i}',f'부담이 있어요. {i}',pressure='high' if i%2 else 'none'))
 d.end_session(s,'user');items=im.moments(s)
 assert 1<=len(items)<=2
 assert all(x['advisor']==s['turns'][x['turn']-1]['text'] for x in items)

def test_legacy_record_can_continue_without_migration():
 s=session();s.pop('immersion');d.apply_turn(s,'안녕하세요',response())
 assert s['immersion']['version']==1
 d.rewind(s,1);assert im.state(s)['events']==[]

def test_next_stage_does_not_display_previous_appointment_as_new_result():
 s=session(stage='FIRST',journey=True)
 d.apply_turn(s,'질문',response());d.apply_turn(s,'다음 상담',response(outcome='goal'))
 s['appointment']={'label':'월요일 저녁 7시'};d.next_stage(s)
 assert s['appointment'] is None and s['messages'][-1]['attachment']=='insurance'
