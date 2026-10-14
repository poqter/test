"""Grounded dialogue memory, planned situations and learner-safe presentation."""
from copy import deepcopy
import re

REACTIONS={
 'opened_up':'고객이 자신의 상황을 더 이야기했습니다.',
 'boundary':'고객이 부담이나 경계하는 부분을 밝혔습니다.',
 'clarified':'고객이 설명에 대한 이해를 표현했습니다.',
 'time_constraint':'고객이 오늘 가능한 시간을 이야기했습니다.',
 'family_decision':'고객이 가족과 상의할 필요를 이야기했습니다.',
 'considering':'고객이 결정을 더 생각해 보기로 했습니다.',
 'declined':'고객이 원하지 않는다는 뜻을 밝혔습니다.',
 'agreement':'고객과 다음 행동을 정했습니다.',
 'documents':'고객이 보험 자료를 공유했습니다.',
}
MARKERS={
 'boundary':r'부담|불편|걱정|망설|싫|꺼려|조심',
 'clarified':r'이해|알겠|이제\s*알|그런\s*뜻',
 'time_constraint':r'시간|분\s*(?:정도|밖에|남|만)|바빠|바쁘|가야',
 'family_decision':r'배우자|아내|남편|가족',
 'considering':r'생각|고민|상의|보류|나중|천천히|아직',
 'declined':r'않|안\s*할|안\s*하|싫|필요\s*없|거절',
 'agreement':r'네|좋|알겠|뵐|뵙|할게|하겠',
}

def initial(s):
    seed=s['case']['seed']
    return {'version':1,'openness':'reserved' if s['difficulty']=='hard' else 'neutral',
            'pressure':'none','memory':[], 'events':[],
            'short_time':s['difficulty']!='easy' and seed%3==0}

def state(s):return deepcopy(s.get('immersion') or initial(s))

def context(s,text=''):
    current=state(s)
    truth=s['case']['customer_state']['ground_truth']
    # Rewind restores events: situations are repeatable rather than rolled again.
    seen={e['kind'] for e in current['events']}
    candidates=[]
    if 'family_decision' not in seen and truth.get('decision_structure')=='joint_with_spouse' and re.search(r'결정|가입|제안|배우자|가족|상의',text):
        candidates.append({'kind':'family_decision','fact':'중요한 보험 결정은 배우자와 함께 한다. 이미 말했으면 반복하지 않는다.'})
    if current['short_time'] and 'time_constraint' not in seen and len([t for t in s['turns'] if t['stage']==s['stage']])>=3:
        candidates.append({'kind':'time_constraint','fact':'이번 상담에 쓸 수 있는 시간이 많지 않다. 남은 핵심을 먼저 듣고 싶다. 구체적인 남은 분 수나 급한 사건은 만들지 않는다.'})
    return {'relationship':{'openness':current['openness'],'pressure':current['pressure']},
            'remembered_exchanges':current['memory'][-6:], 'situations':candidates,
            'rule':'상황은 맥락에 맞을 때 최대 한 가지. 합의/종료를 방해하지 않는다. 이미 말한 상황을 반복하지 않는다. 신뢰 회복은 앞선 대화까지 고려한다.'}

def record(s,text,result,docs_before=False):
    current=state(s);n=len(s['turns']);reply=s['turns'][-1]['reply']
    reaction=result.get('reaction') or {};kind=reaction.get('kind','none')
    aq=reaction.get('advisor_quote','').strip();cq=reaction.get('customer_quote','').strip()
    valid=not result.get('_guarded') and result['relevance']=='ontrack' and aq and cq and aq in text and cq in reply
    if kind=='opened_up':
        # Only newly disclosed source-backed fields qualify as a concrete disclosure signal.
        before=s['turns'][-1]['before']['customer_state']['disclosed']
        valid=valid and bool(set(s['customer_state']['disclosed'])-set(before))
    elif kind in MARKERS:valid=valid and bool(re.search(MARKERS[kind],cq))
    else:valid=False
    if kind=='family_decision':
        valid=valid and s['case']['customer_state']['ground_truth'].get('decision_structure')=='joint_with_spouse'
    if kind=='time_constraint':valid=valid and current['short_time']
    if kind=='agreement':valid=valid and (result.get('_schedule') or result.get('outcome')=='goal')
    if valid:
        previous=s['turns'][-1]['before'].get('immersion') or initial(s)
        # Internal state is qualitative, bounded, and backed by actual dialogue excerpts.
        for field,levels in [('openness',('reserved','neutral','open')),('pressure',('none','some','high'))]:
            if reaction.get(field) in levels:
                old=levels.index(current[field]);desired=levels.index(reaction[field])
                current[field]=levels[max(old-1,min(old+1,desired))]
        event={'kind':kind,'turn':n,'stage':s['stage'],'advisor_quote':aq,'customer_quote':cq}
        current['memory'].append(event)
        # One card per situation; normal reactions may recur after another change.
        prior=current['events'][-1] if current['events'] else {}
        repeated=kind in ('family_decision','time_constraint') and any(e['kind']==kind for e in current['events'])
        if not repeated and (prior.get('kind')!=kind or previous['openness']!=current['openness'] or previous['pressure']!=current['pressure']):current['events'].append(event)
    if s.get('documents_shared') and not docs_before:
        current['events'].append({'kind':'documents','turn':n,'stage':s['stage'],'advisor_quote':text,'customer_quote':reply})
        s['messages'][-1]['attachment']='insurance'
    if result.get('_schedule'):
        current['events'].append({'kind':'agreement','turn':n,'stage':s['stage'],'advisor_quote':text,'customer_quote':reply})
    current['memory']=current['memory'][-12:];current['events']=current['events'][-30:]
    s['immersion']=current

def visible_signals(s,enabled=False):
    if not enabled or s['mode']!='PRACTICE':return []
    # No hidden state, model reasoning, scenario plans or unspoken facts in the projection.
    return [{'label':REACTIONS[e['kind']],'turn':e['turn'],'quote':e['customer_quote']} for e in state(s)['events'][-3:]]

def moments(s):
    turns={t['number']:t for t in s['turns'] if 'before' in t and not t.get('customer_guarded') and t['number']>s.get('baseline_turns',0)}
    chosen=[]
    preferred=(s.get('report') or {}).get('retrain_turns',[])
    for n in preferred:
        if n in turns and n not in [x['turn'] for x in chosen]:chosen.append({'turn':n,'label':'피드백에서 돌아볼 장면'})
    for event in reversed(state(s)['events']):
        n=event['turn']
        if n in turns and n not in [x['turn'] for x in chosen]:chosen.append({'turn':n,'label':REACTIONS[event['kind']]})
    if not chosen and turns:chosen=[{'turn':next(iter(turns)),'label':'첫 질문을 다시 살펴보세요'}]
    return [{**m,'advisor':turns[m['turn']]['text'],'customer':turns[m['turn']]['reply']} for m in chosen[:2]]

def comparison(s):
    reference=s.get('retry_reference')
    if not reference or s['mode']!='PRACTICE':return None
    target=next((t for t in s['turns'] if t['number']==reference['turn']),None)
    if not target:return None
    return {'before':reference,'after':{'advisor':target['text'],'customer':target['reply']},
            'notice':'같은 고객의 같은 장면을 다시 답한 기록입니다. 표현에 따른 반응 차이이며, 한 번의 결과로 실력 향상을 단정하지 않습니다.'}

def ending(s):
    reason=s.get('end_reason');events=state(s)['events']
    if s.get('appointment'):
        title='다음 상담 약속을 잡았습니다';action=s['appointment']['label']
    elif reason=='customer_exit':title='고객의 종료 의사를 존중하며 마쳤습니다';action='후속 약속은 확정하지 않았습니다.'
    elif reason=='goal':title='이번 상담 장면을 마쳤습니다';action='아래 마지막 대화에서 합의한 내용을 확인하세요.'
    elif reason=='offtrack':title='상담을 진행하기 어려워 종료했습니다';action='관찰 가능한 대화만 복기하고 다시 연습할 수 있습니다.'
    elif reason=='limit':title='이번 장면의 연습을 마쳤습니다';action='대화 한도에 도달했습니다. 마지막 장면부터 다시 연습할 수 있습니다.'
    else:title='오늘 상담을 마쳤습니다';action='확정되지 않은 다음 행동을 임의로 추가하지 않습니다.'
    decision=next((e for e in reversed(events) if e['kind'] in ('considering','declined','agreement')),None)
    return {'title':title,'action':action,'decision_quote':decision['customer_quote'] if decision else '',
            'last_reply':next((m['text'] for m in reversed(s['messages']) if m['role']=='customer'),'')}
