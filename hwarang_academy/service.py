"""Server-side controller and redacted presentation model for both UI transports."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from hashlib import sha256
from secrets import randbelow
from typing import Any
from .content import MAP,SCENARIOS,SCENE_LABELS,MODES,INTENTS,BUILD_ID
from .engine import Session,start_session,stage,commit,finish,guide,coaching,MAX_TURNS,training_stage,completion_gate
from .scenario_v2 import SESSION_LENGTHS, objective_for
from .evaluation import report

@dataclass
class AppState:
    independent: bool=False
    selection: str='C07-S01'
    mode: str='GUIDE'
    session_length: str='STANDARD'
    session: Session|None=None
    revision: int=0
    ack: str=''
    error: str=''
    events: dict[str,str]=field(default_factory=dict)
    show_examples: bool=False


def handle(app:AppState,action:dict) -> dict:
    app.error=''
    if not isinstance(action,dict):raise ValueError('잘못된 요청입니다.')
    eid=action.get('event_id')
    if not isinstance(eid,str) or not 1<=len(eid)<=100:raise ValueError('요청 식별자가 필요합니다.')
    if eid in app.events:
        app.ack=eid;return present(app)
    kind=action.get('kind','')
    try:
        if kind=='configure':
            if app.session and not app.session.ended:raise ValueError('진행 중인 상담에서는 훈련 설정을 바꿀 수 없습니다.')
            sid=action.get('scenario_id',app.selection);mode=action.get('mode',app.mode);length=action.get('session_length',app.session_length)
            if sid not in SCENARIOS or mode not in MODES or length not in SESSION_LENGTHS:raise ValueError('사용할 수 없는 시나리오·모드·훈련 길이입니다.')
            app.selection=sid;app.mode=mode;app.session_length=length
        elif kind=='start':
            if app.session and not app.session.ended:raise ValueError('진행 중인 상담을 먼저 종료해 주세요.')
            sid=action.get('scenario_id',app.selection);mode=action.get('mode',app.mode);length=action.get('session_length',app.session_length)
            if sid not in SCENARIOS or mode not in MODES or length not in SESSION_LENGTHS:raise ValueError('사용할 수 없는 시나리오·모드·훈련 길이입니다.')
            seed=randbelow(2**31);app.selection=sid;app.mode=mode;app.session_length=length
            avoid=action.get('avoid_profiles',[])
            if not isinstance(avoid,list):avoid=[]
            app.session=start_session(sid,mode,seed,action.get('variant','standard'),length,avoid_profiles=avoid,vary_profile=True)
            app.show_examples=False
        elif kind in ('send','commit','edit','examples','finish','retry','retry_new','retry_harder','setup'):
            s=app.session
            if not s:raise ValueError('먼저 훈련을 시작해 주세요.')
            if kind=='send':
                if action.get('expected_turn')!=len(s.turns)+1:raise ValueError('이전 화면의 입력입니다. 현재 대화를 확인해 주세요.')
                text=action.get('text','')
                if s.mode=='GUIDE':
                    stage(s,text,assist=True);commit(s,eid,expected_turn=action['expected_turn'])
                elif s.mode=='COACH':stage(s,text,assist=bool(action.get('assist_used')))
                else:commit(s,eid,text=text,expected_turn=action['expected_turn'])
            elif kind=='commit':
                if not s.draft or action.get('draft_revision')!=s.draft.revision:raise ValueError('수정된 최신 답변을 다시 확인해 주세요.')
                commit(s,eid,expected_turn=action.get('expected_turn'));app.show_examples=False
            elif kind=='edit':
                if s.mode not in ('GUIDE','COACH') or not s.draft:raise ValueError('이 모드에서는 이전 답변을 수정할 수 없습니다.')
            elif kind=='examples':
                if s.ended or s.mode!='COACH' or not guide(s):raise ValueError('현재 모드에서는 추가 예시를 제공하지 않습니다.')
                app.show_examples=not app.show_examples
                if app.show_examples:s.hint_turns.add(len(s.turns)+1)
            elif kind=='finish':finish(s)
            elif kind=='retry':
                if not s.ended:raise ValueError('종료 후 새 회차로 도전해 주세요.')
                app.session=start_session(s.scenario_id,s.mode,s.seed,s.event_variant,s.session_length,vary_profile=s.vary_profile);app.show_examples=False
            elif kind=='retry_new':
                if not s.ended:raise ValueError('종료 후 새 회차로 도전해 주세요.')
                avoid=action.get('avoid_profiles',[]) if isinstance(action.get('avoid_profiles',[]),list) else []
                app.session=start_session(s.scenario_id,s.mode,randbelow(2**31),'standard',s.session_length,avoid_profiles=avoid,vary_profile=True);app.show_examples=False
            elif kind=='retry_harder':
                if not s.ended:raise ValueError('종료 후 새 회차로 도전해 주세요.')
                order=['QUICK','STANDARD','DEEP'];current=order.index(s.session_length);length=order[min(current+1,2)];app.session_length=length
                avoid=action.get('avoid_profiles',[]) if isinstance(action.get('avoid_profiles',[]),list) else []
                app.session=start_session(s.scenario_id,s.mode,randbelow(2**31),'standard',length,avoid_profiles=avoid,vary_profile=True);app.show_examples=False
            elif kind=='setup':
                if not s.ended:raise ValueError('상담 종료 후 훈련을 바꿀 수 있습니다.')
                app.session=None;app.show_examples=False
        elif kind=='bootstrap':pass
        else:raise ValueError('지원하지 않는 요청입니다.')
    except (ValueError,TypeError,KeyError) as exc:
        app.error=str(exc)
    app.events[eid]=kind
    if len(app.events)>200:app.events.pop(next(iter(app.events)))
    app.ack=eid;app.revision+=1
    return present(app)


def catalog() -> list[dict]:
    items=[]
    for x in MAP['training_types']:
        # Source key names are deliberately converted, not edited in source JSON.
        tid=x.get('id',x.get('type_id'))
        items.append({'id':tid,'name':x.get('name',x.get('title')),
                      'category':x.get('category_id',tid[0]),
                      'ready_scenario':next((sid for sid in SCENARIOS if sid.split('-')[0]==tid),None)})
    return items


def _delay_ms(s:Session) -> int:
    base={'CALM':950,'CAUTIOUS':1250,'TERSE':700,'QUESTIONING':1050}.get(s.customer_tone,950)
    if not s.turns:return base
    raw=int(sha256(f"{s.seed}:delay:{len(s.turns)}".encode()).hexdigest()[:4],16)
    return max(550,min(1900,base+(raw%501)-180))


def present(app:AppState) -> dict:
    """Never serialize hidden facts, rule dictionaries, or assessment-only hints."""
    s=app.session
    scenario_rows=[]
    for sid in SCENARIOS:
        scenario_rows.append({'id':sid,'label':SCENE_LABELS[sid][0],'name':SCENE_LABELS[sid][1],'description':SCENE_LABELS[sid][2],
            'category':sid[0],'status':'동작 시험용 · 정식 인증 아님',
            'objectives':{m:objective_for(sid,m)['text'] for m in MODES},
            'guide_points':objective_for(sid,'GUIDE')['guide_points']})
    payload={'build':BUILD_ID,'revision':app.revision,'ack':app.ack,'error':app.error,'independent':app.independent,
             'selection':app.selection,'mode':app.mode,'session_length':app.session_length,'phase':'setup' if app.independent else 'home',
             'categories':[{'id':c['id'],'name':c['name']} for c in MAP['categories']],
             'catalog':catalog(),'scenarios':scenario_rows,
             'modes':[{'id':m['id'],'name':m['name'],'purpose':m['purpose']} for m in MODES.values()],
             'lengths':[{'id':k,**v} for k,v in SESSION_LENGTHS.items()],
             'counts':{'types':97,'planned':194,'executable':6,'intents':110},'engine_version':'V5.2 CONTEXT+WORLD'}
    if not s:return payload
    payload['phase']='result' if s.ended else 'session'
    messages=[{'role':'customer','text':s.opening_text or s.source['opening'],'turn':0}]
    for t in s.turns:
        messages.append({'role':'advisor','text':t.text,'turn':t.number})
        if t.response_text:messages.append({'role':'customer','text':t.response_text,'turn':t.number})
        if getattr(t,'event_text',None):messages.append({'role':'customer','text':t.event_text,'turn':t.number,'variant':'event'})
    objective=objective_for(s.scenario_id,s.mode)
    gate=completion_gate(s)
    if s.mode=='GUIDE': public_gate=gate
    elif s.mode=='COACH': public_gate={'done':gate['done'],'total':gate['total'],'complete':gate['complete']}
    else: public_gate={'complete':gate['complete']}
    payload['session']={'id':s.session_id,'scenario_id':s.scenario_id,'title':s.source['name'],'mode':s.mode,
        'session_length':s.session_length,'profile_id':s.profile_id,'public_facts':list(s.disclosed.values()),'messages':messages,
        'next_turn':len(s.turns)+1,'max_turns':s.max_turns,'has_draft':s.draft is not None,'ended':s.ended,
        'assist_used':bool(s.hint_turns or s.mode=='GUIDE'),'mission':objective['text'],'stage':training_stage(s),
        'completion':public_gate,'reply_delay_ms':_delay_ms(s),
        'scenario_seed':f'{s.seed:08X}','v5_context':{'active_topic':s.v5_state.active_topic,'active_document':bool(s.v5_state.active_document),
            'active_policy':next((p.get('name') for p in s.world.get('insurance',{}).get('policies',[]) if p.get('id')==s.v5_state.active_policy_id),None),
            'active_section':s.v5_state.active_section,'active_coverage':s.v5_state.active_coverage_key,
            'conversation_contracts':list(s.v5_state.conversation_contracts)}}
    if not s.ended and s.dialogue_memory.support_needed:
        payload['session']['dialogue_notice']=('시스템이 최근 답변을 다음 대화에 정확히 연결하지 못했습니다. 같은 질문을 반복하지 않고 연결을 보류했습니다. '
            '다른 표현으로 이어가거나 상담을 종료해 복기할 수 있으며, 이 문제는 상담사의 오답으로 자동 처리하지 않습니다.')
    if s.mode=='GUIDE' and not s.ended:
        payload['session']['states']=s.states.copy();g=guide(s)
        if g:
            payload['guide_panel']=g
            payload['hint']={'text':g['hint']}  # compatibility; the UI renders guide_panel
    elif s.mode=='COACH' and not s.ended:
        c=coaching(s)
        if c:
            payload['coaching']=c
            g=guide(s)
            if g:payload['hint']={'text':g['hint']}
            if g and app.show_examples:payload['examples']=g
    if s.ended:
        payload['report']=report(s)
        payload['review']=[{'turn':t.number,'text':t.text,'customer':t.response_text,'customer_event':getattr(t,'event_text',None),
            'intents':[INTENTS[h['intent_id']]['name'] for h in t.interpretation['hits']],
            'uncertainties':t.interpretation['uncertainties'],'risks':t.interpretation['risk_candidates'],
            'decision':t.interpretation['status'],'assist_used':t.assist_used,'v5_actions':list(t.v5_actions)} for t in s.turns]
    return payload
