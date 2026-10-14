"""Pure, versioned training policy; no API, credentials, or persistence."""
from copy import deepcopy
from uuid import uuid4
import random
import re
from . import immersion
from ..pre_api.case_engine import create_case

STAGES = {'TA': '전화로 약속 잡기', 'FIRST': '첫 상담', 'COVERAGE': '보장분석 설명',
          'PROPOSAL': '가입 제안', 'OBJECTION': '거절 대응'}
GOALS = {
    'TA': '통화 동의를 구하고 점검의 필요성을 설명한 뒤 만남의 시간·방법에 합의한다.',
    'FIRST': '고객의 걱정·가족 상황·예산·의사결정 구조를 파악하고 다음 상담에 합의한다.',
    'COVERAGE': '제공된 가상 보장자료의 유지할 점과 공백을 설명하고 고객의 이해를 확인한다.',
    'PROPOSAL': '확인한 요구와 예산에 맞게 선택지를 설명하고 부담 없는 다음 행동에 합의한다.',
    'OBJECTION': '거절의 실제 이유를 확인하고 우려에 답한 뒤 고객의 결정을 존중한다.',
}
LIMITS = {'TA': 12, 'FIRST': 20, 'COVERAGE': 20, 'PROPOSAL': 16, 'OBJECTION': 12}
DIFFICULTIES = {'easy': '기초', 'standard': '표준', 'hard': '심화'}
PERSONALITIES = {'random': '랜덤', 'calm': '차분한 고객', 'cautious': '신중한 고객',
                 'terse': '말수가 적은 고객', 'questioning': '질문이 많은 고객'}
CRITERIA = {'discovery': '요구 파악', 'listening': '경청·반응', 'clarity': '설명의 정확성과 명료성',
            'objection': '우려 대응', 'agreement': '다음 단계 합의'}
PRIORITIES = {'TA': ['listening', 'clarity', 'agreement'], 'FIRST': ['discovery', 'listening', 'agreement'],
              'COVERAGE': ['clarity', 'discovery', 'listening'],
              'PROPOSAL': ['discovery', 'clarity', 'agreement'], 'OBJECTION': ['listening', 'objection', 'agreement']}
END_LABELS = {'goal': '상담 장면 완료', 'customer_exit': '고객 종료', 'offtrack': '진행 불가 종료 · 재응시 필요',
              'limit': '대화 한도 도달', 'user': '사용자 종료', 'technical': '기술적 중단'}
OPENINGS = {'TA': '네, 소개받았다고 들었어요. 어떤 일로 전화하셨나요?',
            'FIRST': '보험을 한번 점검하고 싶긴 한데, 어디부터 이야기하면 될까요?',
            'COVERAGE': '보장내역을 드렸는데, 지금 제 보험이 어떤 상태인가요?',
            'PROPOSAL': '제 상황에서 어떤 선택이 괜찮을지 설명해 주세요.',
            'OBJECTION': '또 보험료만 늘어나는 건 아닐까요? 당장 바꾸기는 망설여져요.'}


COMPLETION_RULES = {
    'TA': '날짜+시간 또는 시간대와 만남/통화 방법의 합의. 교육 질문을 모두 수행할 필요는 없다.',
    'FIRST': '후속 보장분석/상담의 날짜+시간 또는 시간대에 서로 합의하면 종료. 요구·가족·예산 질문 누락은 복기에 남긴다.',
    'COVERAGE': '설명한 핵심 보장과 공백을 고객이 이해하고 다음 행동에 동의하면 종료.',
    'PROPOSAL': '제안에 대해 고객이 선택 또는 보류/거절 의사를 정하고 설계사가 다음 행동을 확인하면 종료. 가입 강요 금지.',
    'OBJECTION': '실제 우려에 답하고 고객의 수락/보류/거절 결정을 존중하며 다음 행동을 정하면 종료.',
}


def new_session(owner, *, stage='TA', mode='PRACTICE', difficulty='standard', journey=False,
                personality='random', archetype=None, seed=None):
    if stage not in STAGES or mode not in ('PRACTICE', 'ASSESSMENT') or difficulty not in DIFFICULTIES:
        raise ValueError('훈련 설정을 확인해 주세요.')
    if personality not in PERSONALITIES:
        raise ValueError('고객 성격을 확인해 주세요.')
    seed = random.SystemRandom().randrange(2**31) if seed is None else int(seed)
    case = create_case(seed, stage=stage, training_mode='SOLO' if mode=='PRACTICE' else 'ASSESSMENT',
                       consultation_difficulty=difficulty, insurance_known=stage in ('COVERAGE','PROPOSAL'),
                       forced_archetype=archetype).to_dict()
    rng = random.Random(seed)
    tone = rng.choice(list(PERSONALITIES)[1:]) if personality=='random' else personality
    session = {'schema': 2, 'id': str(uuid4()), 'owner': owner, 'version': 0, 'mode': mode,
            'difficulty': difficulty, 'journey': bool(journey), 'stage': stage, 'initial_stage': stage,
            'personality': tone, 'case': case, 'messages': [{'role':'customer','text':OPENINGS[stage], 'stage':stage}],
            'turns': [], 'branch': 0, 'attempts': [], 'hints': [], 'hint_cache': {},
            'customer_state': {'trust': {'easy':65,'standard':45,'hard':25}[difficulty],
                               'concern':'', 'disclosed':[]},
            'offtrack_count':0, 'warning':False, 'ended':False, 'end_reason':None,
            'stage_complete':False, 'appointment':None, 'documents_shared':False, 'completed_stages':[], 'report':None,
            'review_requested':False, 'usage':[], 'pending':None, 'technical_notice':''}
    session['immersion']=immersion.initial(session)
    if stage in ('COVERAGE','PROPOSAL'):session['messages'][0]['attachment']='insurance'
    return session


def prompt_context(s, text=""):
    # This is sent only to the provider, never to the presentation transport.
    insurance_visible=s['stage'] in ('COVERAGE','PROPOSAL') or s.get('documents_shared',False)
    case={'customer_state':s['case']['customer_state']}
    if insurance_visible:case['insurance_state']=s['case']['insurance_state']
    else:case['insurance_note']='증권 미확인. customer_beliefs에 기억하는 금액/개수가 없으면 정확한 숫자를 답하지 말 것.'
    return {'stage':s['stage'], 'goal':GOALS[s['stage']], 'completion_rule':COMPLETION_RULES[s['stage']], 'difficulty':s['difficulty'],
            'personality':s['personality'], 'immutable_case':case, 'documents_shared':insurance_visible,
            'customer_identity':s['case']['public_state'], 'customer_state':s['customer_state'], 'disclosure_catalog':disclosure_catalog(s), 'conversation':s['messages'],
            'interaction_context':immersion.context(s,text), 'offtrack_streak':s['offtrack_count'], 'warning_given':s['warning']}


def current_turns(s):
    return [t for t in s['turns'] if t['stage']==s['stage']]


def snapshot(s):
    keys = ('messages','turns','customer_state','offtrack_count','warning','stage_complete','completed_stages','stage','appointment','documents_shared','immersion')
    return {k:deepcopy(s.get(k)) for k in keys}


def apply_turn(s, text, result):
    if s['ended'] or s['stage_complete']:
        raise ValueError('종료 또는 단계 완료 후에는 답변할 수 없습니다.')
    text = str(text).strip()
    if not text or len(text)>2400:
        raise ValueError('답변은 1~2,400자로 입력해 주세요.')
    before = snapshot(s)
    if result.get('_schedule'):s['appointment']=deepcopy(result['_schedule'])
    # Only a high-confidence, contextual finding counts; poor skills are never strikes.
    offtrack = result['relevance']=='offtrack' and result['confidence']>=0.9 and bool(result['reason'].strip())
    s['offtrack_count'] = s['offtrack_count']+1 if offtrack else 0
    if not offtrack: s['warning']=False
    n = len(s['turns'])+1
    reply=result['reply'].strip()
    if offtrack and s['offtrack_count']==1:
        reply='말씀하신 뜻을 잘 이해하지 못했어요. 다시 말씀해 주시겠어요?'
    s['messages'] += [{'role':'advisor','text':text,'turn':n,'stage':s['stage']},
                      {'role':'customer','text':reply,'turn':n,'stage':s['stage']}]
    s['turns'].append({'number':n,'text':text,'reply':reply,'stage':s['stage'], 'before':before,
                       'relevance':result['relevance'], 'reason':result['reason'], 'confidence':result['confidence'],
                       'customer_guarded':bool(result.get('_guarded')), 'assisted':any(h['turn']==n for h in s['hints'])})
    if re.search(r'(증권|보험\s*내역|보장\s*내역).*(보여|보내|공유|같이\s*확인|함께\s*확인)',text) and re.match(r'^(네|예|좋아요|알겠습니다)',reply) and not re.search(r'없|못|어렵|나중',reply):
        s['documents_shared']=True
    # Case facts are immutable. The model may update only bounded affect and explicitly disclosed facts.
    s['customer_state']['trust'] = max(0,min(100,s['customer_state']['trust']+max(-10,min(10,result['trust_delta']))))
    s['customer_state']['concern'] = result['concern'][:500]
    allowed = disclosure_catalog(s)
    s['customer_state']['disclosed'] = list(dict.fromkeys(s['customer_state']['disclosed'] +
                                        [x for x in result['disclosed_keys'] if x in allowed]))
    immersion.record(s,text,result,docs_before=bool(before.get('documents_shared')))
    if offtrack and s['offtrack_count']>=3 and s['warning'] and result['confirm_streak']:
        end_session(s,'offtrack')
    elif offtrack and s['offtrack_count']>=2:
        s['warning']=True
    elif not offtrack and result['outcome']=='advisor_exit':
        end_session(s,'user')
    elif not offtrack and result['outcome']=='customer_exit':
        end_session(s,'customer_exit')
    elif not offtrack and result['outcome']=='goal' and (len(current_turns(s))>=2 or result.get('_schedule')):
        if s['stage'] not in s['completed_stages']:s['completed_stages'].append(s['stage'])
        later=list(STAGES).index(s['stage'])<len(STAGES)-1
        if s['journey'] and later:s['stage_complete']=True
        else:end_session(s,'goal')
    elif len(current_turns(s))>=LIMITS[s['stage']]:
        end_session(s,'limit')
    # Snapshots contain old turns without their snapshots, preventing exponential growth.
    s['turns'][-1]['before']['turns']=[{k:v for k,v in t.items() if k!='before'} for t in before['turns']]


def disclosure_catalog(s):
    truth=s['case']['customer_state']['ground_truth']
    out={}
    def visit(value,path):
        if isinstance(value,dict):
            for k,v in value.items():visit(v,path+'.'+k if path else k)
        else:out[path]=value
    visit(truth,'')
    return out


def end_session(s, reason):
    if reason not in END_LABELS:raise ValueError('종료 사유를 확인해 주세요.')
    s['ended']=True;s['end_reason']=reason;s['stage_complete']=False


def next_stage(s):
    if not s['stage_complete'] or s['ended']:raise ValueError('현재 상담 단계를 먼저 마쳐 주세요.')
    s['stage']=list(STAGES)[list(STAGES).index(s['stage'])+1]
    s['stage_complete']=False;s['offtrack_count']=0;s['warning']=False;s['appointment']=None
    opening={'role':'customer','text':OPENINGS[s['stage']], 'stage':s['stage']}
    if s['stage'] in ('COVERAGE','PROPOSAL'):opening['attachment']='insurance'
    s['messages'].append(opening)


def rewind(s, number):
    if s['mode']!='PRACTICE':raise ValueError('공식 평가에서는 되돌릴 수 없습니다.')
    targets=[t for t in s['turns'] if t['number']==number and 'before' in t]
    if not targets:raise ValueError('되돌릴 장면을 선택해 주세요.')
    before=deepcopy(targets[0]['before'])
    old_snapshots={t['number']:t.get('before') for t in s['turns'] if t['number']<number}
    s['attempts'].append({'branch':s['branch'],'from_turn':number,
                          'turns':[{k:v for k,v in t.items() if k!='before'} for t in s['turns'] if t['number']>=number]})
    for k,v in before.items():s[k]=v
    for t in s['turns']:
        if old_snapshots.get(t['number']):t['before']=old_snapshots[t['number']]
    s['branch']+=1;s['ended']=False;s['end_reason']=None;s['report']=None;s['hint_cache']={}
    # Usage, paid request history, and help history intentionally are NOT rewound.


def report_context(s):
    return {'case':s['case'], 'messages':[m for m in s['messages'] if m.get('turn',0)>s.get('baseline_turns',0)], 'mode':s['mode'], 'end_reason':s['end_reason'],
            'criteria':CRITERIA,'stage_priorities':{k:PRIORITIES[k] for k in {t['stage'] for t in s['turns']}},
            'hint_count':len(s['hints']), 'retry_count':len(s['attempts'])}


def validate_report(s, report):
    rows={r['criterion']:r for r in report['rows']}
    if set(rows)!=set(CRITERIA):raise ValueError('평가 항목이 일치하지 않습니다.')
    texts={t['number']:t['text'] for t in s['turns'] if t['number']>s.get('baseline_turns',0)}
    for r in rows.values():
        for e in r['evidence']:
            if e['turn'] not in texts or not e['quote'].strip() or e['quote'] not in texts[e['turn']]:
                raise ValueError('평가 근거가 실제 대화와 일치하지 않습니다.')
        if r['level']!='not_observed' and not r['evidence']:
            raise ValueError('평가 근거가 없는 항목은 점수를 부여할 수 없습니다.')
    report['retrain_turns']=[n for n in report['retrain_turns'] if n in texts][:3]
    report['total_score']=None
    report['status']='평가 미완료·재응시 필요' if s['end_reason']=='offtrack' else ('평가 자료 부족' if len(texts)<3 else '피드백 완료')
    report['notice']='배점·합격선 검증 전으로 종합점수와 합격 판정은 제공하지 않습니다. 음성 전달력은 점수에 포함하지 않습니다.'
    return report


def share_payload(s, fields):
    fields=set(fields)
    if not fields or fields-{'summary','feedback','transcript'}:raise ValueError('공유할 항목을 선택해 주세요.')
    if not s['ended']:raise ValueError('종료한 연습 기록만 공유할 수 있습니다.')
    r=s.get('report') or {}
    out={'session_id':s['id'],'stage':s['initial_stage'],'mode':s['mode']}
    if 'summary' in fields:
        out['summary']={'status':r.get('status'),'levels':[{'criterion':x['criterion'],'level':x['level']} for x in r.get('rows',[])]}
    if 'feedback' in fields:out['feedback']=deepcopy(r)
    if 'transcript' in fields:out['transcript']=deepcopy(s['messages'])
    return out


def practice_from(s, number):
    targets=[t for t in s['turns'] if t['number']==number and 'before' in t]
    if not targets:raise ValueError('재연습 장면을 선택해 주세요.')
    out=new_session(s['owner'],stage=targets[0]['stage'],difficulty=s['difficulty'],personality=s['personality'],seed=s['case']['seed'])
    out['case']=deepcopy(s['case'])
    for k,v in targets[0]['before'].items():out[k]=deepcopy(v)
    out['baseline_turns']=number-1
    out['retraining_source']=s['id']
    out['retry_reference']={'turn':number,'advisor':targets[0]['text'],'customer':targets[0]['reply']}
    return out
