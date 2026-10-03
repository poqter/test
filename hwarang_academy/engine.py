"""Transactional simulator using the six V1.1 worked scenarios.

Engine state is per-session. No paid APIs, filesystem writes, eval(), or learner
text-to-fact assignment. A draft never consumes a turn or changes customer state.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from copy import deepcopy
from hashlib import sha256
from typing import Any
from uuid import uuid4
import re
from .content import SCENARIOS, RESPONSES, INTENTS, MODES
from .language import analyze, Interpretation, money_mentions, norm
from .dialogue_context import DialogueMemory, interpret_context, focus_for
from .scenario_v2 import SESSION_LENGTHS, build_profile, eligible_events
from .world_v5 import build_customer_world
from .dialogue_v5 import DialogueStateV5, plan_c07, state_snapshot
from .director_v5 import maybe_event as maybe_v5_event
from .mission_graph_v5 import guide_plan as c07_guide_plan, goal_status as c07_goal_status, validate_session_route
from .training_policy_v55 import pacing as c07_pacing, loop_diagnostics as c07_loop_diagnostics, open_loops as c07_open_loops

MAX_TURNS=40  # absolute safety ceiling; per-session ceiling comes from SESSION_LENGTHS

@dataclass
class Route:
    responses: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    audit_ids: list[str] = field(default_factory=list)
    disclosures: dict[str,str] = field(default_factory=dict)
    flags: set[str] = field(default_factory=set)
    question: str | None = None
    terminal: str | None = None
    pending_intents: list[str] = field(default_factory=list)
    repair_kind: str | None = None
    repeat_previous: bool = False
    preserve_question: bool = False
    state_delta: dict[str,int] = field(default_factory=dict)
    v5_actions: list[str] = field(default_factory=list)
    def add(self,r: str, flag: str | None=None, **facts: str) -> None:
        if r not in self.responses: self.responses.append(r)
        if flag: self.flags.add(flag)
        self.disclosures.update(facts)
    def say(self,text: str, flag: str | None=None, audit_id: str | None=None, **facts: str) -> None:
        if text and text not in self.texts: self.texts.append(text)
        if audit_id and audit_id not in self.audit_ids:self.audit_ids.append(audit_id)
        if flag: self.flags.add(flag)
        self.disclosures.update(facts)

@dataclass
class Turn:
    turn_id: str
    number: int
    text: str
    interpretation: dict
    response_ids: list[str]
    response_text: str
    event_text: str|None
    flags: list[str]
    disclosures: dict[str,str]
    assist_used: bool
    revision: int
    state_before: dict[str,int]
    state_after: dict[str,int]
    pending_question: str | None
    v5_actions: list[str]=field(default_factory=list)
    v5_context_before: dict=field(default_factory=dict)
    v5_context_after: dict=field(default_factory=dict)

@dataclass
class Draft:
    text: str
    interpretation: Interpretation
    revision: int
    turn_number: int
    assist_used: bool=False

@dataclass
class Session:
    scenario_id: str
    mode: str
    seed: int=1
    session_id: str=field(default_factory=lambda: uuid4().hex)
    turns: list[Turn]=field(default_factory=list)
    facts: dict=field(default_factory=dict)
    disclosed: dict[str,dict]=field(default_factory=dict)
    observed: dict[str,list[int]]=field(default_factory=dict)
    flags: dict[str,int]=field(default_factory=dict)
    states: dict[str,int]=field(default_factory=lambda:{'trust':50,'resistance':40,'interest':40,'patience':72})
    pending_question: str|None=None
    pending_intents: list[str]=field(default_factory=list)
    proposals: list[dict]=field(default_factory=list)
    draft: Draft|None=None
    ended: bool=False
    end_reason: str|None=None
    processed: dict[str,dict]=field(default_factory=dict)
    hint_turns: set[int]=field(default_factory=set)
    event_variant: str='standard'
    session_length: str='DEEP'
    max_turns: int=40
    vary_profile: bool=False
    profile_id: str=''
    profile_public: list[str]=field(default_factory=list)
    opening_text: str=''
    customer_tone: str='CALM'
    event_deck: list[dict]=field(default_factory=list)
    events_fired: list[str]=field(default_factory=list)
    dialogue_memory: DialogueMemory = field(default_factory=DialogueMemory)
    world: dict=field(default_factory=dict)
    v5_state: DialogueStateV5=field(default_factory=DialogueStateV5)
    scenario_version: str='5.5-training-route-ownership'
    customer_seed: int|None=None
    event_log: list[dict]=field(default_factory=list)
    user_id: str|None=None

    @property
    def source(self) -> dict:
        return SCENARIOS[self.scenario_id]['source_record']

    @property
    def fact_digest(self) -> str:
        import json
        return sha256(json.dumps(self.facts,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def start_session(scenario_id='C07-S01',mode='GUIDE',seed=1,event_variant='standard',session_length='DEEP',avoid_profiles=(),vary_profile=False) -> Session:
    if scenario_id not in SCENARIOS: raise ValueError('이 과제는 상세 대사 준비 후 실행할 수 있습니다.')
    if mode not in MODES: raise ValueError('지원하지 않는 훈련 모드입니다.')
    if session_length not in SESSION_LENGTHS: raise ValueError('지원하지 않는 훈련 길이입니다.')
    if event_variant not in ('standard','refusal') or (event_variant=='refusal' and (scenario_id!='A01-S01' or mode=='ASSESSMENT')):
        raise ValueError('해당 모드에서 사용할 수 없는 상황 변형입니다.')
    s=Session(scenario_id=scenario_id,mode=mode,seed=int(seed),event_variant=event_variant,
              session_length=session_length,max_turns=SESSION_LENGTHS[session_length]['max_turns'],vary_profile=bool(vary_profile))
    if vary_profile:
        profile=build_profile(scenario_id,s.source,int(seed),avoid_profiles)
        s.profile_id=profile['profile_id'];s.profile_public=list(profile.get('public',s.source['public']))
        s.opening_text=profile.get('opening',s.source['opening']);s.facts=deepcopy(profile.get('facts',s.source['facts']))
        if profile.get('known_contract_note'):s.facts['_profile_note']=profile['known_contract_note']
        s.customer_tone=profile.get('tone',{}).get('tone_id','CALM')
    else:
        s.profile_id=scenario_id+'-SOURCE';s.profile_public=list(s.source['public']);s.opening_text=s.source['opening'];s.facts=deepcopy(s.source['facts'])
    s.customer_seed=int(seed)
    s.world=build_customer_world(scenario_id,s.profile_id,s.facts,int(seed))
    s.event_deck=eligible_events(scenario_id,mode,session_length) if vary_profile else []
    if s.event_deck:
        s.event_deck.sort(key=lambda e: sha256(f"{s.seed}:event-order:{e['id']}".encode()).hexdigest())
    # Opening establishes a conversational topic without awarding any skill evidence.
    if scenario_id=='C07-S01':s.dialogue_memory.focus='premium_total'
    for idx,text in enumerate(s.profile_public):
        s.disclosed['initial_'+str(idx)]={'label':'처음 알려진 정보','value':text,'turn':0,'certainty':'customer_statement'}
    return s


def stage(s: Session,text: str,*,assist=False) -> Draft:
    if s.ended: raise ValueError('종료된 상담입니다. 새 회차로 시작해 주세요.')
    if len(s.turns)>=s.max_turns: raise ValueError('이번 회차의 대화 한도에 도달했습니다. 종료 후 복기해 주세요.')
    if s.mode not in ('GUIDE','COACH'): raise ValueError('이 모드에서는 제출 전 코칭을 사용할 수 없습니다.')
    revision=(s.draft.revision+1) if s.draft else 1
    s.draft=Draft(text=text,interpretation=_interpret(s,text),revision=revision,turn_number=len(s.turns)+1,
                  assist_used=(s.mode=='GUIDE') or assist or bool(s.draft and s.draft.assist_used) or len(s.turns)+1 in s.hint_turns)
    return s.draft


def _interpret(s: Session, text: str) -> Interpretation:
    return interpret_context(analyze(text), s.dialogue_memory, len(s.turns))


def _seen(s:Session,key:str)->bool: return key in s.flags

def _source_fact(s:Session,key:str,default=None): return s.facts.get(key,default)

def _summary(s:Session,i:Interpretation) -> tuple[bool,bool]:
    """Check *already disclosed* facts, never reward lucky hidden-number guesses."""
    if 'EV02' not in i.ids: return False,False
    t=i.text
    amounts=money_mentions(t)
    if s.scenario_id=='C07-S01':
        total_expected=int(s.facts['total_monthly_premium_won']);contract_expected=int(s.facts['burdensome_contract_premium_won'])
        allowed=[]
        if '전체 월 보험료' in s.disclosed: allowed.append(total_expected)
        if '해당 월 보험료' in s.disclosed: allowed.append(contract_expected)
        if not allowed:return False,False
        total=re.search(r'(?:전체|총액|총\s*보험료)[^.!?]{0,36}',t)
        contract_name=re.escape(str(s.facts.get('burdensome_contract','계약')))
        contract=re.search(contract_name+r'[^.!?]{0,30}',t)
        bad=any(a['won'] not in allowed for a in amounts)
        for segment,expected in ((total,total_expected),(contract,contract_expected)):
            if segment and expected in allowed:
                nums=money_mentions(segment.group())
                if nums and nums[0]['won']!=expected:bad=True
        correct=not bad and {a['won'] for a in amounts}>={total_expected,contract_expected} and total_expected in allowed and contract_expected in allowed
        trigger_terms=[x for x in re.split(r'\s+|·',str(s.facts.get('burden_trigger',''))) if len(x)>=2]
        causal=not amounts and _seen(s,'trigger') and ('부담' in t) and any(x in t for x in trigger_terms[:4])
        return correct or causal,bad
    if s.scenario_id=='F07-S01':
        bad=bool(re.search(r'(?:확실히|확정|무조건|분명히).{0,10}반대|배우자.{0,12}반대하시',t))
        return (_seen(s,'preference') and bool(re.search(r'함께|같이|자료|검토',t)) and not bad),bad
    if s.scenario_id=='A01-S01':
        return (_seen(s,'time') and _seen(s,'interest') and bool(re.search(r'2\s*분|이\s*분',t)) and '보험' in t),False
    if s.scenario_id=='H10-S01':
        return (_seen(s,'goals') and _seen(s,'family_unknown') and bool(re.search(r'경영|운영',t)) and '가족' in t and bool(re.search(r'미정|아직|합의',t))),False
    return False,False



def _route_v5(s:Session,i:Interpretation,r:Route) -> bool:
    if s.scenario_id!='C07-S01' or not s.world:return False
    plan=plan_c07(s,i.text,len(s.turns)+1)
    if not plan.handled:return False
    if plan.text:r.say(plan.text)
    r.flags.update(plan.flags);r.flags.add('v5_handled')
    r.disclosures.update(plan.disclosures)
    r.state_delta.update(plan.state_delta)
    r.v5_actions.extend(plan.actions)
    if plan.pending_question is not None:r.question=plan.pending_question
    if plan.terminal:r.terminal=plan.terminal
    return True

def route(s:Session,i:Interpretation) -> Route:
    ids=i.ids;t=i.text;r=Route()
    if i.control=='stop':r.terminal='learner_stopped';return r
    if i.control=='out_of_scope':r.add('COMMON.24');return r
    # Learner interpretation cannot overrule an explicit customer boundary.
    if _seen(s,'stop_active'):
        if ids & {'RL10','NX08'}:
            r.add('R.A01.10' if s.scenario_id=='A01-S01' else 'COMMON.13','respectful_closure');r.terminal='respectful_closure'
        elif i.status in ('needs_clarification','needs_review') and not i.risk_candidates:
            r.add('COMMON.02')
        else:
            r.add('COMMON.12','stop_repeated');r.terminal='customer_requested_end'
        return r
    if i.risk_candidates:
        risk=i.risk_candidates[0]
        specific={('A01-S01','CR05'):'R.A01.08',('C07-S01','CR03'):'R.C07.10',
            ('D08-S01','CR02'):'R.D08.07',('D08-S01','CR03'):'R.D08.08',
            ('F07-S01','CR05'):'R.F07.05',('F07-S01','CR04'):'R.F07.08',
            ('G10-S01','CR02'):'R.G10.08',('H10-S01','CR02'):'R.H10.08'}
        r.add(specific.get((s.scenario_id,risk),'COMMON.08' if risk=='CR03' else 'COMMON.07'),'risk_candidate')
        r.question='권고 또는 확약의 근거 확인'
        return r
    if not ids:
        if _route_v5(s,i,r): return r
        if _route_conversation(s,i,r): return r
        return _repair(s,i,r)
    if ids & {'MT03','EV06'}:
        r.add('R.G10.09' if s.scenario_id=='G10-S01' else 'COMMON.16','correction')
        # Correction stays alongside the historical risk; does not erase it.
        return r
    accurate,disputed=_summary(s,i)
    if disputed:
        if s.scenario_id=='C07-S01':
            total=int(s.facts['total_monthly_premium_won']);contract=int(s.facts['burdensome_contract_premium_won'])
            mentioned={a['won'] for a in money_mentions(t)}
            if not s.vary_profile and mentioned=={total,contract}:r.add('COMMON.10','summary_disputed')
            elif not s.vary_profile:r.add('R.C07.09','summary_disputed')
            else:r.say(f"앞서 말씀드린 전체 월 보험료는 {_spoken_won(total)}이에요. 금액을 다시 확인해 주세요.",'summary_disputed',audit_id='R.C07.09')
        else:r.add('R.F07.06','summary_disputed')
        r.question='앞서 공개한 사실의 정정';return r
    if accurate:
        rid={'C07-S01':'R.C07.08','F07-S01':'R.F07.07','H10-S01':'R.H10.07'}.get(s.scenario_id,'COMMON.09')
        if s.scenario_id=='C07-S01' and not (_seen(s,'trigger') and _seen(s,'preference')):rid='COMMON.09'
        if s.scenario_id=='F07-S01' and not _seen(s,'material_consent'):rid='COMMON.09'
        r.add(rid,'summary_confirmed')
        if s.scenario_id=='C07-S01' and {x['won'] for x in money_mentions(t)}>={int(s.facts['total_monthly_premium_won']),int(s.facts['burdensome_contract_premium_won'])}:r.flags.add('numeric_summary_confirmed')
        return r
    # A submitted summary which cannot be verified must not receive false agreement.
    if 'EV02' in ids and not (ids-{'EV02','EV01'}):
        r.add('COMMON.01');r.flags.add('summary_unresolved');return r
    if s.pending_question and ids and ids <= {'DS04','DS05','DS06','DS07','DS08','DS13','DS14'} and s.scenario_id in ('G10-S01','D08-S01'):
        r.add('COMMON.21','pending_question_unanswered');r.question=s.pending_question;return r
    if _route_v5(s,i,r):return r
    fn={'A01-S01':_route_a,'C07-S01':_route_c,'D08-S01':_route_d,'F07-S01':_route_f,'G10-S01':_route_g,'H10-S01':_route_h}[s.scenario_id]
    fn(s,i,r)
    if not r.responses and not r.texts and not _route_conversation(s,i,r):
        if ids & {'RL04','RL10','PR03','PR09','EX05','EV03','EX01'}:
            r.add('COMMON.19','process_acknowledged')
        elif 'RL01' in ids: r.add('DIALOGUE.REVIEW','acknowledged_concern')
        elif any(INTENTS[x]['speech_act']=='ASK' for x in ids):r.add('COMMON.18','unknown_requested')
        else:_repair(s,i,r)
    # A recorded limitation is not automatically a content-accuracy pass.
    if ids & {'EX05','EV03'} and re.search(r'資料|증권|자료|조건|담보|검토|확인',t):r.flags.add('limitation_explained')
    if ids & {'RL04','RL10','PR10'}:r.flags.add('choice_respected')
    if ids & {'PR03','PR09','EX01'}:r.flags.add('review_before_decision')
    return r



def _repair(s: Session, i: Interpretation, r: Route) -> Route:
    """One clarification, one restatement, then surface an ENGINE limit.

    Never repeat vague questions indefinitely or make learner skill claims.
    No hidden goals, answer examples, or source facts are sent as a repair hint.
    """
    r.flags.add('engine_clarification')
    r.repair_kind = 'choose_topic'
    attempts = s.dialogue_memory.repair_streak
    if attempts >= 2:
        r.flags.add('engine_support_needed')
        return r  # UI shows a neutral system notice instead of another customer loop.
    if s.scenario_id in ('C07-S01','D08-S01') and (
        attempts > 0 or re.search(r'그\s*부분|어느\s*부분|보험료요|보장\s*내용', i.text)
    ):
        r.add('DIALOGUE.CLARIFY_TOPIC')
    else:
        r.add('COMMON.02' if attempts == 0 else 'DIALOGUE.CLARIFY_OTHER')
    return r


def _won(n:int) -> str:
    return f"{int(n):,}원"

def _spoken_won(n:int) -> str:
    n=int(n)
    if n % 10000 == 0:
        return f"{n//10000}만원"
    if n >= 10000:
        return f"{n/10000:g}만원"
    return f"{n:,}원"


def _document_reply(s:Session, purpose:str) -> str:
    status=s.facts.get('policy_document_status')
    if purpose=='possession':
        return {
          'mobile':'네, 휴대폰에 저장된 증권이 있어요. 지금 열어볼 수 있어요.',
          'partial_mobile':'휴대폰에 일부 계약 자료는 있어요. 전부 있는지는 확인해 봐야 해요.',
          'file_available':'네, 저장해 둔 증권 파일이 있어요.',
          'spouse_managed':'계약 자료는 배우자가 주로 관리해서 제가 지금 바로 전부 보기는 어려워요.',
        }.get(status,'자료가 있는지는 한번 확인해 봐야 해요.')
    if purpose=='check':
        return {
          'mobile':'네, 증권을 열어봤어요. 담보가 많아서 어떤 항목부터 보면 되는지 알려주세요.',
          'partial_mobile':'확인해 보니 일부 계약만 바로 보여요. 지금 보이는 범위부터 같이 볼까요?',
          'file_available':'파일을 열었어요. 어떤 부분부터 확인하면 될까요?',
          'spouse_managed':'지금 제 손에 전체 증권은 없어요. 배우자에게 자료를 받아야 정확히 확인할 수 있을 것 같아요.',
        }.get(status,'지금 바로 확인 가능한 자료가 있는지부터 찾아볼게요.')
    return {
      'mobile':'휴대폰에 저장된 증권을 열어서 보여드리면 될까요?',
      'partial_mobile':'휴대폰에 있는 계약 자료부터 확인하고, 없는 건 나중에 추가로 받아야 할 것 같아요.',
      'file_available':'저장해 둔 증권 파일을 열어서 확인하면 될 것 같아요.',
      'spouse_managed':'배우자에게 증권을 받아서 같이 확인하는 방법이 가장 정확할 것 같아요.',
    }.get(status,'보험사 앱이나 가지고 있는 증권을 찾아서 확인해 보면 될까요?')



def _policy_items(s: Session) -> list[dict]:
    return list(s.facts.get('policy_items') or [])


def _remembered_contracts(s: Session) -> list[str]:
    values=list(s.facts.get('remembered_contracts') or [])
    if not values and s.facts.get('burdensome_contract'):
        values=[str(s.facts['burdensome_contract'])]
    return values


def _policy_inventory_text(s: Session, *, include_premium: bool=False, coverage_view: bool=False) -> str:
    items=_policy_items(s)
    if not items:
        return '증권에서 계약 목록은 확인할 수 있지만, 세부 항목 데이터는 아직 준비되지 않았어요.'
    if coverage_view:
        parts=[f"{x['name']}: {x.get('kind','보장 항목')}" for x in items[:5]]
        return '지금 증권 요약에는 다음과 같이 표시돼 있어요: ' + ', '.join(parts) + '. 담보별 정확한 가입금액은 세부 항목을 하나씩 열어봐야 해요.'
    if include_premium:
        parts=[f"{x['name']} {_spoken_won(int(x['premium_won']))}" for x in items[:6]]
        return '증권에 보이는 월 보험료 기준으로는 ' + ', '.join(parts) + ' 정도예요.'
    return '증권에 보이는 계약은 ' + ', '.join(x['name'] for x in items[:6]) + ' 정도예요. 어떤 계약부터 볼까요?'


def _document_can_open(s: Session) -> bool:
    return s.facts.get('policy_document_status') in ('mobile','partial_mobile','file_available')


def _document_is_open(s: Session) -> bool:
    return 'document_opened' in s.flags or s.dialogue_memory.active_object_state=='open'


def _route_c_semantic_v3(s: Session, i: Interpretation, r: Route) -> bool:
    """Context-first C07 response planning for ordinary free-form Korean.

    This layer answers the conversational obligation before the legacy scored
    intent router.  It never creates skill evidence unless an older reviewed
    intent independently matched the same turn.
    """
    acts=set(i.dialogue_acts)
    if not acts:return False
    total=int(s.facts['total_monthly_premium_won'])
    contract=int(s.facts['burdensome_contract_premium_won'])
    cname=str(s.facts['burdensome_contract'])

    if 'empathy' in acts and not (i.ids & {'RL01'}):
        r.say('네, 계속 내고는 있는데 요즘은 부담이 좀 커졌어요. 같이 확인해보면 좋겠어요.','acknowledged_concern')
        return True

    if 'off_topic' in acts:
        r.say('그 얘기도 궁금하시군요. 저는 오늘 보험료 부담 때문에 상담을 신청한 부분을 먼저 확인하고 싶어요.','off_topic_redirect')
        return True

    if 'ask_customer_concern' in acts and not (i.ids & {'DS01','DS02'}):
        r.say('제가 제일 궁금한 건 보험료가 왜 이렇게 많이 나가는지예요. 가능하면 필요한 보장은 남기면서 부담을 줄일 수 있는지도 알고 싶어요.','customer_concern_shared',**{'고객의 현재 관심사':'보험료 부담 원인과 필요한 보장 유지 가능성'})
        return True

    if 'ask_premium_amount' in acts and 'ask_premium_by_contract' not in acts and 'DS13' not in i.ids:
        r.say(f"전체로는 한 달에 {_spoken_won(total)} 정도 나가요.",'premium',audit_id='R.C07.02',**{'전체 월 보험료':_won(total)+' · 고객 진술'})
        return True

    if 'ask_burden_trigger' in acts and 'DS15' not in i.ids:
        r.say(f"최근에는 {s.facts['burden_trigger']} 때문에 보험료가 더 부담스럽게 느껴져요.",'trigger',**{'부담 계기':str(s.facts['burden_trigger'])})
        return True

    if 'ask_preference' in acts and not (i.ids & {'DS03','DS02'}):
        r.say(str(s.facts['preference'])+' 쪽으로 보고 싶어요.','preference',**{'유지하고 싶은 조건':str(s.facts['preference'])})
        return True

    if 'ask_burdensome_contract' in acts and 'DS14' not in i.ids:
        mentioned=[int(x) for x in i.entities.get('semantic_money_won',[]) if str(x).isdigit()]
        normalized=norm(i.text)
        correction=''
        if 'confirm_amount' in acts and '그중' in normalized and mentioned and total not in mentioned and '전체 월 보험료' in s.disclosed:
            correction=f"아까 말씀드린 전체 보험료는 {_spoken_won(total)}이에요. "
            r.flags.add('customer_corrected_amount')
        r.say(correction+f"가장 부담되는 건 {cname}이에요. 그 계약만 한 달에 {_spoken_won(contract)} 정도 나가요.",'contract',**{'부담 계약':cname,'해당 월 보험료':_won(contract)+' · 고객 진술'})
        return True

    if 'ask_contract_list' in acts and not (i.ids & {'DS16','DS14'}):
        prefix=''
        if 'confirm_amount' in acts and 'premium' in i.entities.get('semantic_object',[]):
            mentioned=[int(x) for x in i.entities.get('semantic_money_won',[]) if str(x).isdigit()]
            if mentioned and total not in mentioned:
                prefix=f'전체 보험료는 {_spoken_won(total)}이라고 말씀드렸어요. 방금 말씀하신 금액과는 달라요. '
                r.flags.add('customer_corrected_amount')
            elif mentioned:
                prefix=f'네, 전체 보험료는 {_spoken_won(total)} 정도예요. '
        if _document_is_open(s):
            r.say(prefix+_policy_inventory_text(s),'document_items_shared',**{'증권 계약 목록':' · '.join(x['name'] for x in _policy_items(s))})
        else:
            remembered=_remembered_contracts(s)
            if len(remembered)>1:
                r.say(prefix+'기억나는 건 '+', '.join(remembered)+' 정도예요. 다른 계약은 증권을 봐야 정확히 말씀드릴 수 있어요.','remembered_contracts_shared',**{'기억하는 계약':' · '.join(remembered)})
            else:
                r.say(prefix+f'지금 바로 기억나는 건 {cname}이 있고, 그 보험료가 한 달에 {_spoken_won(contract)} 정도라는 거예요. 다른 계약은 증권을 봐야 정확해요.','remembered_contracts_shared',**{'기억하는 계약':cname})
        return True

    if 'confirm_amount' in acts and 'EV02' not in i.ids and 'premium' in i.entities.get('semantic_object',[]):
        mentioned=[int(x) for x in i.entities.get('semantic_money_won',[]) if str(x).isdigit()]
        if mentioned and total not in mentioned:
            r.say(f'전체 보험료는 {_spoken_won(total)}이라고 말씀드렸어요. 방금 말씀하신 금액과는 달라요.','customer_corrected_amount',**{'전체 월 보험료':_won(total)+' · 고객 진술'})
        else:
            r.say(f'네, 전체로 한 달에 {_spoken_won(total)} 정도 낸다고 말씀드렸어요.','amount_reconfirmed',**{'전체 월 보험료':_won(total)+' · 고객 진술'})
        return True

    if 'confirm_coverage_unknown' in acts:
        if _document_is_open(s):
            r.say('네, 기억만으로는 정확한 담보별 가입금액을 말씀드리기 어려웠어요. 지금 열린 증권에서 확인할 수 있는 범위부터 볼게요.','coverage_unknown_confirmed')
        else:
            r.say('네, 정확한 보장 내용과 담보별 가입금액은 기억만으로는 잘 모르겠어요. 증권을 확인해야 정확해요.','coverage_unknown_confirmed',**{'담보별 보장 내용':'미확인 · 상세 자료 확인 필요'})
        return True

    if 'ask_document_items' in acts or 'ask_coverage_items' in acts or 'ask_items_ambiguous' in acts:
        if _document_is_open(s):
            r.say(_policy_inventory_text(s,coverage_view=('ask_coverage_items' in acts)),'document_items_shared',**{'증권 계약 목록':' · '.join(x['name'] for x in _policy_items(s))})
        elif _document_can_open(s):
            r.say('증권을 열어보면 계약과 항목을 확인할 수 있어요. 지금 열어볼까요?','document_open_offer')
        else:
            r.say(_document_reply(s,'method'),'document_method_shared')
        return True

    if 'restore_document_context' in acts:
        if _document_is_open(s):
            r.say('맞아요. 지금 증권을 보고 있었어요. '+_policy_inventory_text(s),'context_restored')
        else:
            r.say('맞아요, 증권을 확인하던 중이었어요. 지금 확인 가능한 자료부터 다시 볼게요.','context_restored')
        return True

    if 'ask_premium_by_contract' in acts:
        if _document_is_open(s):
            r.say(_policy_inventory_text(s,include_premium=True),'document_premiums_shared')
        else:
            r.say(f'제가 기억하는 건 {cname}이 한 달에 {_spoken_won(contract)} 정도라는 거예요. 다른 계약별 보험료는 증권을 봐야 정확해요.','known_contract_shared')
        return True

    # A short continue request should continue from the active document instead of
    # falling back to a premium-vs-coverage clarification.
    if 'prompt_customer_continue' in acts and _document_is_open(s):
        r.say(_policy_inventory_text(s),'document_items_shared',**{'증권 계약 목록':' · '.join(x['name'] for x in _policy_items(s))})
        return True

    return False


def _route_conversation(s: Session, i: Interpretation, r: Route) -> bool:
    """Handle ordinary conversation without treating every move as scored evidence."""
    acts=set(i.dialogue_acts)
    if not acts:return False
    if i.risk_candidates or i.control:return False
    if 'repeat_request' in acts:
        r.repeat_previous=True;r.preserve_question=True;r.flags.add('repeat_requested');return True

    # V3 semantic response planning may answer a quoted recap/question without
    # turning it into scoring evidence.  Uncertainties still block legacy routes.
    if s.scenario_id=='C07-S01' and _route_c_semantic_v3(s,i,r):
        return True
    if i.uncertainties:return False

    if s.scenario_id=='C07-S01':
        total=int(s.facts['total_monthly_premium_won']);contract=int(s.facts['burdensome_contract_premium_won'])
        cname=str(s.facts['burdensome_contract'])
        if 'ask_indemnity_premium' in acts:
            amounts=money_mentions(i.text)
            correction=''
            if '전체 월 보험료' in s.disclosed and amounts and any(a['won']!=total for a in amounts):
                correction=f"아까 말씀드린 전체 보험료는 {_spoken_won(total)}이에요. "
                r.flags.add('customer_corrected_amount')
            value=s.facts.get('indemnity_premium_won')
            if value is None or not _document_is_open(s):
                r.say(correction+'그중 실손 보험료가 얼마인지는 정확히 기억나지 않아요. 증권을 봐야 알 것 같아요.','indemnity_unknown',**{'실손 보험료':'미확인 · 고객이 정확히 기억하지 못함'})
            else:
                r.say(correction+f"증권을 보니 실손 보험료는 한 달에 {_spoken_won(value)} 정도예요.",'indemnity_shared',**{'실손 보험료':_won(value)+' · 증권 확인'})
            return True
        if 'request_document_check' in acts:
            r.say(_document_reply(s,'check'),'document_opened' if _document_can_open(s) else 'document_check_started');return True
        if 'ask_document_possession' in acts:
            r.say(_document_reply(s,'possession'),'document_available' if _document_can_open(s) else 'document_status_shared',**{'증권 상태':'확인 가능 여부를 고객이 설명함'});return True
        if 'ask_document_method' in acts:
            r.say(_document_reply(s,'method'),'document_method_shared');return True
        if 'remind_document_check' in acts:
            r.say(_document_reply(s,'check'),'document_opened' if _document_can_open(s) else 'document_check_started');return True
        if 'prompt_customer_continue' in acts:
            if s.dialogue_memory.active_object=='policy_document' or s.dialogue_memory.focus=='documents' or 'document_check_started' in s.flags or 'document_available' in s.flags:
                if _document_is_open(s):
                    r.say(_policy_inventory_text(s),'document_items_shared',**{'증권 계약 목록':' · '.join(x['name'] for x in _policy_items(s))});return True
                r.say(_document_reply(s,'check'),'document_opened' if _document_can_open(s) else 'document_check_started');return True
            if 'contract' not in s.flags:
                r.say(f"지금 기억나는 건 {cname}이 있고 그 보험료가 한 달에 {_spoken_won(contract)} 정도라는 거예요. 자세한 보장은 증권을 봐야 해요.",'known_contract_shared',**{'부담 계약':cname,'해당 월 보험료':_won(contract)+' · 고객 진술'})
            else:
                r.say('제가 기억나는 범위는 말씀드렸어요. 더 필요한 부분이 있으면 질문해 주세요.','conversation_acknowledged')
            return True
        if acts & {'review_coverage','topic_coverage'}:
            if not s.vary_profile:
                r.add('C07.COVERAGE_UNKNOWN','coverage_details_unknown',**{'담보별 보장 내용':'미확인 · 상세 자료 확인 필요'})
            else:
                r.say('정확한 보장 내용과 담보별 가입금액은 잘 모르겠어요. 증권을 같이 보면 좋겠어요.','coverage_details_unknown',audit_id='C07.COVERAGE_UNKNOWN',**{'담보별 보장 내용':'미확인 · 상세 자료 확인 필요'})
            return True
        if acts & {'review_contracts','topic_contracts'}:
            r.say(f"지금 기억나는 건 {cname}이 있고 한 달에 {_won(contract)} 정도 낸다는 거예요. 다른 계약은 자료를 보면서 확인해야 할 것 같아요.",'known_contract_shared',**{'알고 있는 계약':cname,'해당 월 보험료':_won(contract)+' · 고객 진술'});return True
        if acts & {'topic_premium','review_premium'}:
            # A topic choice/review proposal keeps the conversation moving but is
            # not the same thing as asking the factual DS13 question. Do not award
            # full skill evidence merely because the customer volunteers a number.
            if '전체 월 보험료' not in s.disclosed:
                if not s.vary_profile:r.add('C07.PREMIUM_TOPIC','topic_information_shared',**{'전체 월 보험료':_won(total)+' · 고객 진술'})
                else:r.say(f"네. 전체로는 한 달에 {_spoken_won(total)} 정도 나가요.",'topic_information_shared',audit_id='C07.PREMIUM_TOPIC',**{'전체 월 보험료':_won(total)+' · 고객 진술'})
            elif 'topic_premium' in acts:
                r.say('전체 보험료를 다시 말씀드릴까요, 아니면 어떤 계약이 가장 부담되는지 말씀드릴까요?','scope_clarification')
                r.repair_kind='premium_scope'
            else:
                r.say(f"전체 보험료는 {_spoken_won(total)}이라고 말씀드렸어요. 어떤 계약이 특히 부담되는지도 같이 볼까요?",'conversation_acknowledged')
            return True
        if 'review_together' in acts:
            if s.dialogue_memory.active_object=='policy_document' or 'document_available' in s.flags:
                r.say(_document_reply(s,'check'),'document_opened' if _document_can_open(s) else 'document_check_started');return True
            r.say('네, 같이 확인해 주세요. 제가 아는 내용부터 말씀드릴게요.','conversation_acknowledged');return True

    if acts & {'topic_premium','topic_coverage','topic_contracts','review_contracts','review_coverage','review_premium'}:
        if s.scenario_id=='D08-S01' and acts & {'review_contracts','topic_contracts'}:
            r.add('R.D08.01','known_documents_shared',**{'기존 자료':'증권 보유 · 실제 내용은 자료팩 미완성'})
        else:r.add('DIALOGUE.REVIEW','conversation_acknowledged')
        return True
    if 'review_together' in acts or 'RL02' in i.ids:r.add('DIALOGUE.REVIEW','conversation_acknowledged');return True
    if 'greeting' in acts:
        r.add('R.A01.01' if s.scenario_id=='A01-S01' else 'DIALOGUE.GREETING','greeting_only');return True
    if 'acknowledgement' in acts:
        if s.dialogue_memory.pending_kind:_repair(s,i,r)
        else:r.add('DIALOGUE.ACK','conversation_acknowledged');r.preserve_question=True
        return True
    if 'pressure' in acts:
        r.add('COMMON.07','pressure_detected');return True
    return False


def _route_c(s,i,r):
    ids=i.ids;total=int(s.facts['total_monthly_premium_won']);contract=int(s.facts['burdensome_contract_premium_won']);cname=str(s.facts['burdensome_contract'])
    # Component/document/repeat acts have semantic priority, but ordinary review
    # proposals must not steal a scored factual question such as DS14.
    special={'ask_indemnity_premium','repeat_request'}
    if set(i.dialogue_acts) & special and _route_conversation(s,i,r):return
    qs=[]
    if 'DS13' in ids:qs.append(('premium','R.C07.02',f"전체로는 한 달에 {_spoken_won(total)} 정도 나가요.",{'전체 월 보험료':_won(total)+' · 고객 진술'}))
    if 'DS14' in ids:
        contract_text=f"가장 부담되는 건 {cname}이에요. 그 계약만 한 달에 {_spoken_won(contract)} 정도 나가요."
        mentioned={x['won'] for x in money_mentions(i.text)}
        if _seen(s,'premium') and '그중' in norm(i.text) and mentioned and total not in mentioned and re.search(r'(?:내신|내고|납입|보험료).{0,20}(?:하셨|셨|라고)',i.text):
            contract_text=f"아까 말씀드린 전체 보험료는 {_spoken_won(total)}이에요. "+contract_text
            r.flags.add('customer_corrected_amount')
        qs.append(('contract','R.C07.03',contract_text,{'부담 계약':cname,'해당 월 보험료':_won(contract)+' · 고객 진술'}))
    if 'DS15' in ids:qs.append(('trigger','R.C07.05',f"최근에는 {s.facts['burden_trigger']} 때문에 고정지출이 더 부담스럽게 느껴져요.",{'부담 계기':str(s.facts['burden_trigger'])}))
    if ids & {'DS03','DS02'}:qs.append(('preference','R.C07.06',str(s.facts['preference'])+' 쪽으로 보고 싶어요.',{'유지하고 싶은 조건':str(s.facts['preference'])}))
    if 'DS08' in ids:qs.append(('debt_unknown','R.C07.07','대출의 정확한 잔액이나 월 상환액은 지금 바로 말씀드리기 어려워요. 확인이 필요해요.',{'대출 잔액·월 상환액':'미확인 · 정확한 금액은 설정되지 않음'}))
    for flag,rid,text,facts in qs[:2]:
        if not s.vary_profile:r.add(rid,flag,**facts)
        else:r.say(text,flag,audit_id=rid,**facts)
    for flag,_,_,_ in qs[2:]:r.pending_intents.append({'premium':'DS13','contract':'DS14','trigger':'DS15','preference':'DS03','debt_unknown':'DS08'}[flag])
    if qs:return
    if _route_conversation(s,i,r):return
    if 'EV01' in ids:
        if _seen(s,'premium') and _seen(s,'contract'):
            r.say(f"제가 말씀드린 건 전체 {_won(total)}, 그중 {cname}이 {_won(contract)} 정도라는 기억이에요. 증권으로 검증한 금액은 아직 아니에요.",'certainty_checked')
        else:r.add('COMMON.01')
    elif ids & {'EV09','NX05'}:
        if 'EV09' in ids and re.search(r'비교|필요한\s*항목|확인하도록|제공\s*범위|증권',i.text):
            r.say(_document_reply(s,'method')+' 필요한 항목만 같이 확인해 주세요.','material_consent',**{'다음 행동':'증권 또는 계약 자료 확인에 동의 · 일정은 아직 미정'})
        else:r.add('COMMON.05');r.question='자료의 목적과 제공 범위 확인'
    elif ids & {'NX02','NX03','NX04'}:r.add('R.C07.12','schedule_pending',**{'상담 일정':'미정 · 고객 확인 후 합의 필요'})
    elif ids & {'NX08','NX10'}:
        if _seen(s,'material_consent') and (_seen(s,'schedule_pending') or re.search(r'일정.{0,12}(?:미정|따로|나중)|자료.{0,15}먼저',i.text)):
            r.add('R.C07.13','closure_confirmed');r.terminal='agreed_next_step'
        else:r.add('COMMON.13','neutral_closure');r.terminal='learner_closed'
    elif 'DS16' in ids:
        r.say(f"{cname}이 있다는 건 알고 있고, 자세한 보장은 자료를 봐야 해요.",'known_contract_shared',**{'알고 있는 계약':cname,'담보별 보장 내용':'미확인 · 상세 자료 확인 필요'})
    elif 'RL01' in ids and re.search(r'보험료|부담|고정지출',i.text):
        r.say('네, 계속 내고는 있는데 요즘은 부담이 좀 커졌어요.','acknowledged_concern')

def _route_a(s,i,r):
    ids=i.ids
    if s.event_variant=='refusal' and len(s.turns)>=1:
        r.add('R.A01.09','stop_active',**{'연락 의사':'추가 연락을 원하지 않음'});return
    if ids & {'CT03','CT04'}:r.add('R.A01.02','time',**{'대화 가능 시간':'2분'})
    if ids & {'CT01','CT02'}:r.add('R.A01.01','introduced')
    if len(r.responses)<2 and ids & {'CT05','DS01','DS02'} and (_seen(s,'introduced') or ids & {'CT01','CT02'}):
        r.add('R.A01.03','interest',**{'관심 범위':'가입된 보험을 확인하는 상담'})
    if r.responses:
        r.responses=r.responses[:2];return
    if 'RL06' in ids:r.add('R.A01.04','purpose_explained')
    elif 'EV09' in ids:r.add('R.A01.05','material_declined',**{'자료 제공 범위':'오늘은 자료 준비 설명만 희망'})
    elif ids & {'NX01','CT10'}:
        if _seen(s,'interest'):r.add('R.A01.06','customer_initiates',**{'후속 연락':'고객이 시간 확인 후 먼저 연락 · 상담사 연락 미동의'})
        else:r.add('COMMON.05')
    elif ids & {'NX02','NX03'}:r.add('COMMON.20','schedule_pending')
    elif ids & {'NX04','NX08','RL10'}:
        if _seen(s,'customer_initiates') and re.search(r'고객님|먼저\s*연락|연락.{0,10}않|추가\s*연락\s*없이',i.text):
            r.add('R.A01.07','closure_confirmed');r.terminal='customer_initiated_followup'
        elif 'NX08' in ids:r.add('COMMON.13');r.terminal='learner_closed'
        else:r.add('COMMON.01')


def _route_d(s,i,r):
    ids=i.ids
    if ids & {'DS16','EV09'}:r.add('R.D08.01','documents',**{'기존 자료':'증권 보유 · 실제 내용은 자료팩 미완성'})
    if ids & {'DS03','DS02'}:r.add('R.D08.02','preference',**{'중요한 조건':'보험료 절감과 병원 이용 시 부담을 함께 고려'})
    if r.responses:return
    if ids & {'EV04','EV05'}:r.add('R.D08.03','document_review_requested');r.flags.add('content_unverified')
    elif 'EX04' in ids:r.add('R.D08.04','tradeoff_explained');r.flags.add('content_unverified')
    elif ids & {'EX05','EX10','EV03'}:r.add('R.D08.05','limitation_explained')
    elif 'EV08' in ids:r.add('R.D08.06','explanation_incomplete')
    elif ids & {'PR09','NX05','PR03'}:r.add('R.D08.09','review_consent')
    elif 'NX08' in ids:
        r.add('R.D08.10','closure_confirmed' if _seen(s,'review_consent') else 'neutral_closure');r.terminal='review_deferred'


def _route_f(s,i,r):
    ids=i.ids
    if 'DS19' in ids:r.add('R.F07.02','spouse_concern',**{'배우자 우려':'변경 후 손해가 걱정되는 것 같음 · 고객의 추정'})
    elif 'NX06' in ids:r.add('R.F07.03','joint_pending',**{'동반 상담':'미정 · 배우자와 먼저 이야기 필요'})
    elif ids & {'NX05','EV09'}:r.add('R.F07.04','material_consent',**{'자료 전달':'고객 본인에게 비교자료 전달 동의'})
    elif 'CT10' in ids:r.add('R.F07.09','customer_initiates',**{'후속 연락':'고객이 검토 후 먼저 연락 · 상담사 재연락 미동의'})
    elif ids & {'RL10','NX08','NX10'}:
        if _seen(s,'material_consent') or _seen(s,'customer_initiates'):
            r.add('R.F07.10','closure_confirmed');r.terminal='respectful_followup'
        else:r.add('COMMON.13');r.terminal='learner_closed'
    elif ids & {'RL01','RL04','DS03'}:r.add('R.F07.01','preference',**{'결정 방식':'가족과 함께 검토하기 희망 · 직접 연락 권한 없음'})


def _route_g(s,i,r):
    ids=i.ids
    if 'SV02' in ids:r.add('R.G10.02','claim_status',**{'접수 상태':'접수 전'})
    if ids & {'SV01','DS18'}:r.add('R.G10.03','health_unknown',**{'진료 내용':'진료 사실만 고객 진술 · 세부 내용 미확인'})
    if r.responses:return
    if 'SV05' in ids:r.add('R.G10.04','previous_assurance',**{'과거 안내':'담당자가 다 나온다고 했다는 고객 기억 · 미검증'})
    elif 'EX05' in ids:r.add('R.G10.05','limitation_explained');r.question='어떤 조건을 확인해야 하나요?'
    elif ids & {'SV03','SV04'}:r.add('R.G10.06','check_plan');r.flags.add('content_unverified');r.question='무엇을 준비하나요?'
    elif ids & {'NX05','SV06'}:r.add('R.G10.07','material_scope');r.flags.add('content_unverified')
    elif ids & {'NX10','NX04'}:r.add('R.G10.10','followup_pending');r.question='확인 항목과 다음 안내 시점은 언제인가요?'
    elif 'NX08' in ids:r.add('R.G10.11','closure_confirmed');r.terminal='claim_preparation'
    elif 'RL01' in ids:r.add('R.G10.01','acknowledged_concern')


def _route_h(s,i,r):
    ids=i.ids;t=i.text
    if 'NX08' in ids:
        r.add('R.H10.10','closure_confirmed' if _seen(s,'review_consent') else 'neutral_closure');r.terminal='specialist_review_preparation';return
    if 'SP07' in ids:
        if re.search(r'가족.{0,22}합의',t):r.add('R.H10.03','family_unknown',**{'가족 합의':'구체적으로 합의한 내용 없음'})
        else:r.add('R.H10.01','goals',**{'승계 목표':'자녀에게 경영을 맡기고 싶음 · 다른 가족 재산 배분도 고민'})
    elif 'DS02' in ids:r.add('R.H10.01','goals',**{'승계 목표':'경영 이전과 가족 재산 배분을 함께 고민'})
    if 'DS04' in ids:r.add('R.H10.03','family_unknown',**{'가족 합의':'아직 구체적인 합의 없음'})
    if 'SP06' in ids and len(r.responses)<2:
        if re.search(r'평가|최근\s*자료',t):r.add('R.H10.04','valuation_unknown',**{'평가자료':'최근 자료 준비 필요'})
        else:r.add('R.H10.02','ownership_unknown',**{'정확한 지분':'미확인 · 원본에 수치 없음'})
    if r.responses:r.responses=r.responses[:2];return
    if 'SP10' in ids:r.add('R.H10.05','goals_separated')
    elif ids & {'SP08','NX05'}:r.add('R.H10.06','review_consent')
    elif ids & {'EX05','PR09','EV03'}:r.add('R.H10.09','limitation_explained')
    elif ids & {'NX10','NX08'}:
        r.add('R.H10.10','closure_confirmed' if _seen(s,'review_consent') else 'neutral_closure');r.terminal='specialist_review_preparation'


def _choose(s:Session,rid:str,number:int)->str:
    variants=RESPONSES[rid]['variants']
    index=int(sha256(f'{s.seed}:{number}:{rid}'.encode()).hexdigest()[:8],16)%len(variants)
    if len(variants) > 1 and s.turns and variants[index] == s.turns[-1].response_text:
        index = (index + 1) % len(variants)
    return variants[index]


def training_stage(s:Session) -> str:
    if s.ended:return 'COMPLETE'
    if s.scenario_id=='C07-S01':
        if 'analysis_handoff' in s.flags or s.v5_state.stage in ('ANALYSIS_HANDOFF','FOLLOW_UP'):
            return 'FOLLOW-UP'
        if 'reduction_preference' in s.flags or 'preference' in s.flags:
            return 'ALIGN'
        if 'document_opened' in s.flags or 'material_consent' in s.flags:
            return 'REVIEW'
        if 'premium' in s.flags or 'trigger' in s.flags or 'contract' in s.flags:
            return 'DISCOVER'
        return 'OPEN'
    # Generic stage by evidence density for the five other reviewed scenarios.
    n=len([k for k in s.flags if not k.startswith(('engine_','event_'))])
    return 'DISCOVER' if n<2 else 'DEEPEN' if n<4 else 'HANDLE' if n<6 else 'CLOSE'


def completion_gate(s:Session) -> dict:
    gates={
      'A01-S01':{'QUICK':['time','interest'],'STANDARD':['time','interest','closure_confirmed'],'DEEP':['time','interest','choice_respected','closure_confirmed']},
      'D08-S01':{'QUICK':['documents','preference'],'STANDARD':['documents','preference','limitation_explained','review_consent'],'DEEP':['documents','preference','limitation_explained','review_consent']},
      'F07-S01':{'QUICK':['preference','spouse_concern'],'STANDARD':['preference','spouse_concern','material_consent'],'DEEP':['preference','spouse_concern','material_consent','choice_respected']},
      'G10-S01':{'QUICK':['claim_status','limitation_explained'],'STANDARD':['claim_status','health_unknown','limitation_explained','check_plan'],'DEEP':['claim_status','health_unknown','previous_assurance','limitation_explained','check_plan','material_scope']},
      'H10-S01':{'QUICK':['goals','ownership_unknown'],'STANDARD':['goals','ownership_unknown','family_unknown','review_consent'],'DEEP':['goals','ownership_unknown','family_unknown','goals_separated','limitation_explained','review_consent']},
    }
    if s.scenario_id=='C07-S01':
        quality={
          'QUICK':['premium','trigger','analysis_handoff'],
          'STANDARD':['premium','contract','trigger','preference','reduction_preference','analysis_handoff'],
          'DEEP':['premium','contract','trigger','preference','reduction_preference','material_route','analysis_handoff'],
        }
        required=quality[s.session_length]
        status=c07_goal_status(s)
        material_done=next((x['done'] for x in status['intermediate'] if x['id']=='material_route'),False)
        done=[]
        for x in required:
            if x=='material_route':
                if material_done:done.append(x)
            elif x in s.flags:done.append(x)
        return {
            'done':len(done),'total':len(required),'complete':status['final_complete'],'final_complete':status['final_complete'],
            'final_goal':status['final_goal'],'missing':[x for x in required if x not in done],
            'intermediate_done':done,'intermediate_required':required,
            'followup_schedule':status.get('followup_schedule'),'completion_path':status.get('completion_path'),
        }
    required=gates[s.scenario_id][s.session_length]
    done=[x for x in required if x in s.flags]
    return {'done':len(done),'total':len(required),'complete':len(done)==len(required),'missing':[x for x in required if x not in s.flags]}


def _event_roll(s:Session,event_id:str,turn_number:int) -> float:
    raw=int(sha256(f'{s.seed}:event:{event_id}:{turn_number}'.encode()).hexdigest()[:8],16)
    return raw/0xffffffff


def _maybe_event(s:Session,turn_number:int,route_flags:set[str]) -> str|None:
    if s.ended or 'engine_clarification' in route_flags or 'risk_candidate' in route_flags:return None
    v5=maybe_v5_event(s,turn_number,route_flags)
    if v5 is not None:return v5[0]
    if s.scenario_id=='C07-S01':return None
    spec=SESSION_LENGTHS[s.session_length];budget=spec['event_budget'][s.mode]
    if len(s.events_fired)>=budget:return None
    for event in s.event_deck:
        if event['id'] in s.events_fired or turn_number<event.get('min_turn',1):continue
        if any(req not in s.flags for req in event.get('requires',[])):continue
        trigger_any=event.get('trigger_any',[])
        if trigger_any and not any(req in s.flags or req in route_flags for req in trigger_any):continue
        if _event_roll(s,event['id'],turn_number)>spec['event_rate'][s.mode]:continue
        s.events_fired.append(event['id']);s.flags.setdefault(event['flag'],turn_number)
        s.disclosed.setdefault('event_'+event['id'],{'label':'대화 중 새로 나온 상황','value':event['text'],'turn':turn_number,'certainty':'customer_statement'})
        return event['text']
    return None


def _maybe_customer_exit(s:Session,turn_number:int) -> str|None:
    if s.mode not in ('SOLO','ASSESSMENT') or s.ended:return None
    if s.states['patience']<=20 or s.states['resistance']>=88:
        s.ended=True;s.end_reason='customer_exit';s.flags.setdefault('customer_exit',turn_number)
        return '오늘 상담은 여기까지만 할게요. 지금은 더 진행하고 싶지 않습니다.'
    return None


def commit(s:Session,turn_id:str,*,text:str|None=None,expected_turn:int|None=None) -> Turn:
    if not isinstance(turn_id,str) or not 1<=len(turn_id)<=100:raise ValueError('잘못된 전송 식별자입니다.')
    for turn in s.turns:
        if turn.turn_id==turn_id:return turn
    if s.ended: raise ValueError('이미 종료된 상담입니다.')
    if expected_turn is not None and expected_turn!=len(s.turns)+1: raise ValueError('이전 화면의 답변입니다. 현재 대화를 확인해 주세요.')
    if len(s.turns)>=s.max_turns: raise ValueError('대화 한도에 도달했습니다. 복기 후 새 회차로 시작해 주세요.')
    if s.mode in ('GUIDE','COACH'):
        if not s.draft:raise ValueError('답변을 먼저 작성하고 검토해 주세요.')
        d=s.draft
        if d.turn_number!=len(s.turns)+1:raise ValueError('대화 상태가 변경되었습니다.')
    else:
        if text is None:raise ValueError('답변이 없습니다.')
        d=Draft(text=text,interpretation=_interpret(s,text),revision=1,turn_number=len(s.turns)+1)
    # Compute on a detached snapshot. Install it only after all validation succeeds.
    candidate=deepcopy(s)
    v5_before=state_snapshot(candidate.v5_state)
    r=route(candidate,d.interpretation)
    unknown=(d.interpretation.status in ('needs_clarification','out_of_scope') or (not d.interpretation.hits and not d.interpretation.risk_candidates)) and 'v5_handled' not in r.flags
    before=deepcopy(s.states)
    new_disclosure_labels=[]
    for label,value in r.disclosures.items():
        if label not in candidate.disclosed:
            candidate.disclosed[label]={'label':label,'value':value,'turn':d.turn_number,'certainty':'unknown' if '미확인' in value or '미정' in value else 'customer_statement'}
            new_disclosure_labels.append(label)
    new_flags=r.flags-candidate.flags.keys()
    for flag in r.flags:candidate.flags.setdefault(flag,d.turn_number)
    if 'document_available' in r.flags:
        candidate.dialogue_memory.active_object='policy_document';candidate.dialogue_memory.active_object_state='available'
    if 'document_status_shared' in r.flags:
        candidate.dialogue_memory.active_object='policy_document';candidate.dialogue_memory.active_object_state='unavailable'
    if 'document_opened' in r.flags:
        candidate.dialogue_memory.active_object='policy_document';candidate.dialogue_memory.active_object_state='open'
    if 'context_restored' in r.flags and candidate.dialogue_memory.active_object is None:
        candidate.dialogue_memory.active_object='policy_document'
    if not unknown:
        # Only genuinely new customer information may improve the relationship.
        # Repeating a question that merely re-emits an already disclosed fact must
        # not farm trust/resistance points.
        if new_disclosure_labels:
            candidate.states['trust']+=3;candidate.states['resistance']-=2
        if 'summary_confirmed' in new_flags:candidate.states['trust']+=4
        if d.interpretation.risk_candidates:
            candidate.states['trust']-=7;candidate.states['resistance']+=11;candidate.states['patience']-=18
        if 'pressure_detected' in new_flags:
            candidate.states['resistance']+=7;candidate.states['patience']-=12
        if 'correction' in new_flags:candidate.states['trust']+=2;candidate.states['resistance']-=2
        if 'choice_respected' in new_flags:
            candidate.states['trust']+=2;candidate.states['patience']+=3
    for key,delta in r.state_delta.items():
        if key in candidate.states:candidate.states[key]+=int(delta)
    candidate.states={k:max(0,min(100,v)) for k,v in candidate.states.items()}
    for iid in d.interpretation.ids:
        candidate.observed.setdefault(iid,[]).append(d.turn_number)
    if not r.preserve_question:
        candidate.pending_question=r.question
    # Conversation memory updates only on committed turns (never on a draft).
    memory = candidate.dialogue_memory
    if not r.repeat_previous:
        memory.last_advisor_text=d.text
        memory.last_semantic_acts=list(d.interpretation.dialogue_acts)
        memory.last_semantic_objects=list(d.interpretation.entities.get('semantic_object',[]))
        old_focus=memory.focus
        memory.focus = focus_for(d.interpretation.ids, d.interpretation.dialogue_acts, memory.focus)
        if memory.focus and memory.focus!=old_focus:
            memory.topic_stack=(memory.topic_stack+[memory.focus])[-6:]
        memory.pending_kind = r.repair_kind
        memory.pending_turn = d.turn_number if r.repair_kind else None
        memory.pending_options = ['premium','coverage'] if r.repair_kind=='choose_topic' else ['premium_total','premium_contract'] if r.repair_kind=='premium_scope' else []
        memory.repair_streak = memory.repair_streak + 1 if 'engine_clarification' in r.flags else 0
        memory.support_needed = 'engine_support_needed' in r.flags or memory.repair_streak >= 2
    if 'engine_clarification' in r.flags:
        candidate.v5_state.unresolved_streak+=1;candidate.v5_state.metrics['repairs']+=1
    elif 'v5_handled' in r.flags:
        if candidate.v5_state.unresolved_streak:
            candidate.v5_state.metrics['recoveries']+=1
        candidate.v5_state.unresolved_streak=0
    if candidate.v5_state.active_document:
        candidate.dialogue_memory.active_object='policy_document';candidate.dialogue_memory.active_object_state='open' if candidate.world.get('document',{}).get('opened') else 'available'
    candidate.pending_intents=list(dict.fromkeys(candidate.pending_intents+r.pending_intents))
    answered=d.interpretation.ids-set(r.pending_intents)
    candidate.pending_intents=[x for x in candidate.pending_intents if x not in answered]
    if d.interpretation.ids & {'NX02','NX03'}:
        candidate.proposals.append({'turn':d.turn_number,'kind':'schedule','learner_proposal':d.text,'customer_accepted':False,'status':'pending'})
    if r.terminal:candidate.ended=True;candidate.end_reason=r.terminal
    if r.repeat_previous:
        response = next((t.response_text for t in reversed(s.turns) if t.response_text), s.opening_text or s.source['opening'])
    else:
        response='\n\n'.join([*r.texts,*[_choose(candidate,rid,d.turn_number) for rid in r.responses]])
    # Low-intensity events may appear in GUIDE/COACH too; SOLO/ASSESSMENT use a larger budget.
    event_text=_maybe_event(candidate,d.turn_number,r.flags)
    exit_text=_maybe_customer_exit(candidate,d.turn_number)
    if exit_text:event_text=(event_text+'\n\n'+exit_text).strip() if event_text else exit_text
    candidate.dialogue_memory.last_customer_response=response or candidate.dialogue_memory.last_customer_response
    v5_after=state_snapshot(candidate.v5_state)
    turn=Turn(turn_id,d.turn_number,d.text,d.interpretation.to_dict(),r.responses+r.audit_ids,response,event_text,
              sorted(r.flags),deepcopy(r.disclosures),d.assist_used or d.turn_number in s.hint_turns,d.revision,before,deepcopy(candidate.states),r.question,
              list(r.v5_actions),v5_before,v5_after)
    candidate.event_log.append({'turn':d.turn_number,'advisor_utterance':d.text,'parsed_actions':list(r.v5_actions),
        'active_topic':candidate.v5_state.active_topic,'active_policy_id':candidate.v5_state.active_policy_id,
        'active_coverage_key':candidate.v5_state.active_coverage_key,'flags':sorted(r.flags),'customer_response':response,'customer_event':event_text,
        'state_before':before,'state_after':deepcopy(candidate.states)})
    candidate.turns.append(turn);candidate.draft=None
    if len(candidate.turns)>=candidate.max_turns and not candidate.ended:
        candidate.ended=True;candidate.end_reason='turn_limit'
    s.__dict__.update(candidate.__dict__)
    return turn


def finish(s:Session,reason='learner_ended') -> None:
    if not s.ended:s.ended=True;s.end_reason=reason
    s.draft=None


def coaching(s:Session) -> dict | None:
    if s.mode not in ('GUIDE','COACH') or not s.draft:return None
    i=s.draft.interpretation
    observed=[INTENTS[x]['name'] for x in i.ids]
    if i.risk_candidates:
        title='확인과 고객의 선택을 먼저 다뤄보세요'
        note='권고·확약으로 해석될 수 있는 표현이 있습니다. 실제 위반 확정이 아니라 문맥 검토 후보입니다.'
    elif not observed and i.dialogue_acts:
        title='대화를 이어가는 뜻을 이해했습니다'
        note='인사·확인 제안·주제 선택 등 대화 흐름으로 처리합니다. 구체적인 질문이나 정보 확인 점수를 자동으로 부여하지는 않습니다.'
    elif not observed:
        title='시스템이 아직 답변의 뜻을 연결하지 못했습니다'
        note='현재 규칙이 답변의 의도를 확정하지 못했습니다. 오답으로 처리하지 않습니다.'
    elif 'EV02' in i.ids and _summary(s,i)[1]:
        title='앞서 공개된 사실을 다시 확인해 보세요';note='현재 요약이 고객의 진술과 다릅니다. 금액과 대상이 맞는지 확인해 주세요.'
    else:
        title='이 방향을 확인했습니다';note='문장 전체의 상담 품질 점수가 아니라, 규칙으로 식별한 행동입니다. 진행하면 고객 반응이 이어집니다.'
    return {'title':title,'note':note,'observed':observed,'revision':s.draft.revision,
            'text':s.draft.text,'uncertainties':i.uncertainties}


def guide(s:Session) -> dict|None:
    if s.mode not in ('GUIDE','COACH'):return None
    if s.mode=='COACH' and not s.draft:return None
    source=s.source
    suggestion=source['good'];direction=source['reason']
    if s.scenario_id=='C07-S01':
        gp=c07_guide_plan(s)
        suggestion=gp['recommended'];direction=gp['hint']
        adequate=gp.get('adequate') or source['adequate'];avoid=source['risky']
        return {
            'hint':direction,'recommended':suggestion,'adequate':adequate,'avoid':avoid,
            'reason':gp.get('reason') or source['reason'],'purpose':gp.get('purpose') or gp.get('reason') or source['reason'],
            'route_action':gp.get('action_id'),'expected_next_state':gp.get('expected_next_state'),
            'alternatives':gp.get('alternatives',[]),'rescue':bool(gp.get('rescue')),
            'route_status':gp.get('status',{}),'remaining_goal':gp.get('remaining_goal'),
            'training_route_id':gp.get('training_route_id'),'training_route_name':gp.get('training_route_name'),
            'meaningful_steps':gp.get('meaningful_steps'),'target_minutes':gp.get('target_minutes'),
            'open_loops':gp.get('open_loops',[]),'loop_diagnostics':gp.get('loop_diagnostics',{}),
        }
    elif s.scenario_id in ('A01-S01','D08-S01','F07-S01','G10-S01','H10-S01'):
        sequences = {
          'A01-S01':[('introduced','CT01','자신의 역할과 연락 경로를 먼저 밝힙니다.'),('time','CT03','지금 대화해도 되는지 확인합니다.'),('interest','DS01','고객이 원하는 상담 범위를 묻습니다.'),('customer_initiates','CT10','고객에게 허락받은 후속 연락 범위를 확인합니다.'),('closure_confirmed','NX08','고객이 먼저 연락한다는 의사를 존중하고 마무리합니다.')],
          'D08-S01':[('documents','DS16','기존 가입 자료부터 확인합니다.'),('preference','DS03','보험료 외에 지키고 싶은 조건을 확인합니다.'),('tradeoff_explained','EX04','변경 시 불이익도 함께 검토해야 합니다.'),('limitation_explained','EX05','미검수 자료로 유불리를 확정하지 않습니다.'),('review_consent','NX05','자료 확인 이후 비교하는 순서를 제안합니다.'),('closure_confirmed','NX08','현재 확인 범위에서 검토를 보류하고 마무리합니다.')],
          'F07-S01':[('preference','RL04','가족과 함께 결정하려는 의사를 수용합니다.'),('spouse_concern','DS19','배우자의 실제 우려와 고객의 추정을 구분합니다.'),('material_consent','NX05','고객 본인이 검토할 자료를 제안합니다.'),('customer_initiates','CT10','직접 배우자에게 연락하지 말고 고객의 연락 의사를 확인합니다.'),('closure_confirmed','NX08','자료 범위와 연락 방식에 맞춰 마무리합니다.')],
          'G10-S01':[('acknowledged_concern','RL01','불확실성 때문에 느끼는 부담에 반응합니다.'),('claim_status','SV02','지급을 추측하기 전에 접수 상태를 확인합니다.'),('health_unknown','SV01','고객이 알고 있는 사고·진료 사실과 미확인 내용을 나눕니다.'),('previous_assurance','SV05','과거 안내는 검증된 사실이 아니라 고객 기억으로 확인합니다.'),('limitation_explained','EX05','지급을 확약하지 않고 확인할 범위를 설명합니다.'),('check_plan','SV03','가입 담보와 관련 자료를 대조하는 순서를 안내합니다.'),('material_scope','NX05','고객에게 필요한 확인 목록을 제안합니다.'),('followup_pending','NX10','담당·확인 항목·후속 안내 범위를 정합니다.'),('closure_confirmed','NX08','지급 확답이 아니라 준비 절차의 합의로 마무리합니다.')],
          'H10-S01':[('goals','SP07','경영 이전과 재산 이전의 목표부터 나눠 묻습니다.'),('ownership_unknown','SP06','정확한 지분은 모르면 미확인으로 남깁니다.'),('family_unknown','DS04','가족 합의가 있다고 추정하지 않습니다.'),('goals_separated','SP10','가족·경영·재원 과제를 구분합니다.'),('limitation_explained','EX05','자료 확인 전에는 세무 결과를 확정하지 않습니다.'),('review_consent','SP08','필요한 자료와 전문 검토 의제를 연결합니다.'),('closure_confirmed','NX08','검토 준비 범위를 정리하고 마무리합니다.')],
        }
        for flag,iid,hint in sequences[s.scenario_id]:
            if flag not in s.flags:
                suggestion=INTENTS[iid]['positive_examples'][0];direction=hint;break
        if _seen(s,'stop_active'):
            suggestion=INTENTS['RL10']['positive_examples'][0];direction='고객이 추가 연락을 원하지 않는다고 밝혔습니다. 그 의사를 존중해 종료합니다.'
    adequate=source['adequate'];avoid=source['risky']
    return {'hint':direction,'recommended':suggestion,'adequate':adequate,'avoid':avoid,'reason':source['reason']}
