"""V5 context-first dialogue state machine for the rule-based simulator.

The module does not try to understand arbitrary Korean. It resolves a bounded
insurance-consultation world by prioritising: pending question -> active document
/ policy -> current topic -> utterance semantics -> repair.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import re
from typing import Any
from .world_v5 import (
    policies, find_policy, find_policies, find_coverage_key, remembered_policy_names,
    premium_total, open_document, document_access_message, can_send_document,
    mark_document_shared, won_text, policy_summary, coverage_summary,
    coverage_across_portfolio,
)

@dataclass
class PendingQuestionV5:
    kind: str
    turn: int
    target: str|None=None
    options: list[str]=field(default_factory=list)

@dataclass
class DialogueStateV5:
    stage: str='OPEN'
    active_topic: str='premium'
    active_document: str|None=None
    active_policy_id: str|None=None
    active_coverage_key: str|None=None
    pending: list[PendingQuestionV5]=field(default_factory=list)
    agreements: dict[str,Any]=field(default_factory=dict)
    answered_topics: dict[str,int]=field(default_factory=dict)
    last_actions: list[str]=field(default_factory=list)
    last_objects: list[str]=field(default_factory=list)
    last_move_text: str=''
    unresolved_streak: int=0
    event_cooldown_until: int=0
    event_log: list[dict]=field(default_factory=list)
    conversation_contracts: list[str]=field(default_factory=list)
    metrics: dict[str,int]=field(default_factory=lambda:{
        'context_resolutions':0,'pending_resolutions':0,'repeated_known_questions':0,
        'repairs':0,'recoveries':0,'hostile_turns':0,'followup_agreements':0,
    })

    def top_pending(self)->PendingQuestionV5|None:
        return self.pending[-1] if self.pending else None
    def set_pending(self,kind:str,turn:int,target:str|None=None,options:list[str]|None=None)->None:
        self.pending=[PendingQuestionV5(kind,turn,target,list(options or []))]
    def clear_pending(self)->None:
        self.pending.clear()
    def add_contract(self,text:str)->None:
        if text and text not in self.conversation_contracts:self.conversation_contracts.append(text)

@dataclass
class ParsedMoveV5:
    text: str
    actions: list[str]=field(default_factory=list)
    policy_ids: list[str]=field(default_factory=list)
    coverage_key: str|None=None
    amounts: list[int]=field(default_factory=list)
    objects: list[str]=field(default_factory=list)
    method: str|None=None
    raw_confidence: str='medium'

@dataclass
class V5Plan:
    handled: bool=False
    text: str=''
    flags: set[str]=field(default_factory=set)
    disclosures: dict[str,str]=field(default_factory=dict)
    pending_question: str|None=None
    terminal: str|None=None
    state_delta: dict[str,int]=field(default_factory=dict)
    actions: list[str]=field(default_factory=list)
    audit: dict[str,Any]=field(default_factory=dict)


def _norm(text:str)->str:
    return re.sub(r'[^0-9a-zA-Z가-힣]+','',str(text or '').lower())

def _add(move:ParsedMoveV5,*actions:str)->None:
    for a in actions:
        if a not in move.actions:move.actions.append(a)

def _money_mentions(text:str)->list[int]:
    out=[]
    for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)\s*(만원|천원|원)',text):
        val=float(m.group(1).replace(',',''));unit=m.group(2)
        out.append(round(val*(10000 if unit=='만원' else 1000 if unit=='천원' else 1)))
    return out

def _policy_id_for_name(world:dict,name:str)->str|None:
    for p in policies(world):
        if p['name']==name:return p['id']
    return None

def parse_move(text:str,state:DialogueStateV5,world:dict)->ParsedMoveV5:
    t=str(text or '').strip();n=_norm(t);move=ParsedMoveV5(text=t,amounts=_money_mentions(t))
    ps=find_policies(world,t);move.policy_ids=[p['id'] for p in ps]
    move.coverage_key=find_coverage_key(t)

    # Conversational control / tone.
    if re.fullmatch(r'(네|예|응|어|그래|좋아요|알겠습니다|맞아요)',n):_add(move,'affirm')
    if re.fullmatch(r'(네|예|응|어)?(뭐|뭔데|네|예)?[?？]*',n) and ('?' in t or '？' in t):_add(move,'repeat_request')
    if re.search(r'다시말|뭐라고|무슨말|못들|이해가안',n):_add(move,'repeat_request')
    if re.search(r'장난하|뭐하자는|어쩌자는|답답하|왜이래',n):_add(move,'hostile')
    if re.search(r'안녕|반갑',n):_add(move,'greeting')
    if re.search(r'부담되|힘드셨|걱정되|고민이',n) and not re.search(r'왜|무슨|계기',n):_add(move,'empathy')

    # Questions about customer's concern / reason.
    if re.search(r'(무슨일|어떤일|왜그렇|왜.*부담|왜.*줄|부담.*이유|부담.*계기|무슨문제|계기가|최근.*지출.*늘|지출.*증가)',n):_add(move,'ask_burden_reason')
    if re.search(r'(어느부분.*궁금|어떤부분.*궁금|어떤게.*궁금|뭐가.*궁금|무엇이.*궁금|원하는게|어떤게.*신경|뭐가.*신경|제일.*궁금|어떤부분.*보고싶|어떤게.*보고싶|뭘.*보고싶)',n):_add(move,'ask_customer_concern')
    if re.search(r'(유지.*싶|남기.*싶|꼭.*유지|중요.*보장|줄이더라도)',n):_add(move,'ask_preference')

    # Premium / contract inventory questions.
    generic_amount=bool(re.search(r'(얼마|어느정도|금액|월지출|매달.*나가|한달.*나가|납입.*금액)',n))
    if re.search(r'(전체|총|한달|월).*보험료|보험료.*(전체|총|얼마|어느정도|납입)|월지출.*금액',n):_add(move,'ask_total_premium')
    elif generic_amount and state.active_topic in ('premium','portfolio') and not move.policy_ids:_add(move,'ask_total_premium')
    if re.search(r'(어떤|무슨|뭐).*보험.*(유지|가입|있|가지|갖)|가입.*보험.*(뭐|무슨|어떤|알려)|가입되어.*보험.*알려|보험.*종류|계약.*목록|유지중.*계약|어떤.*계약.*(있|가지|갖)|계약들이.*있',n):_add(move,'ask_policy_list')
    if re.search(r'(어떤|무슨|뭐).*보험.*(제일|가장).*(부담|비싸|많이)|제일.*부담.*보험|부담.*계약',n) or (state.active_topic in ('premium','portfolio') and re.search(r'(그중|어떤게|뭐가).*(제일|가장).*(부담|비싸)',n)):_add(move,'ask_burdensome_policy')
    if re.search(r'(각각|각보험|보험별|계약별).*(금액|보험료)|세부.*금액|각각.*얼마',n):_add(move,'ask_policy_premiums')
    if move.policy_ids and generic_amount and re.search(r'보험료|납입|금액|얼마',n):_add(move,'ask_selected_policy_premium')

    # Coverage questions.
    if re.search(r'(보장내용|담보내용|어떤보장|무슨보장|보장|담보).*(알|아시|아세|기억)',n):_add(move,'ask_coverage_knowledge')
    if re.search(r'(세부보장|보장내용|무슨담보|어떤담보|담보들이|담보가|보장들이|보장이|뭐가보장|무엇이보장)',n):_add(move,'ask_coverage_details')
    if move.policy_ids and re.search(r'(사망보장|암보장|암진단|뇌보장|심장보장|수술보장).*(만|밖에).*(있|인가)|(?:만|밖에).*(있|인가)',n):_add(move,'ask_coverage_details')
    if re.search(r'(ci보험|ci종신|중대한질병)',n) and ('?' in t or re.search(r'(아닌가|맞나|인가|여부)',n)):_add(move,'ask_product_type_ci')
    if move.coverage_key and re.search(r'(얼마|가입금액|금액|몇천|몇억)',n):_add(move,'ask_coverage_amount')

    # Document / material lifecycle.
    if re.search(r'(증권|파일|자료).*(가지|보관|있나|있나요|있으|보유|어디)',n):_add(move,'ask_document_possession')
    if re.search(r'(증권|파일|자료).*(같이|함께|열|확인|보자|봐|보죠|해주세요|해보)',n):_add(move,'request_document_open')
    elif state.active_topic=='document' and re.search(r'(같이|함께|한번)?.*(열어|열|확인해|확인|보죠|볼까요|봐요)',n) and len(n)<=28:
        _add(move,'request_document_open')
    if re.search(r'(무슨내용|어떤내용|뭐가보|어떤항목|무슨항목)',n) and (state.active_document or '증권' in n or '파일' in n):_add(move,'ask_document_contents')
    if re.search(r'(어떻게|어디서).*(확인|찾|열|보면|봐)',n):_add(move,'ask_document_method')
    if re.search(r'(증권|파일|자료).*(전달|보내|보내주|공유)|그파일.*(보내|전달)',n):_add(move,'request_document_transfer')
    if 'request_document_transfer' in move.actions and 'ask_document_possession' in move.actions:move.actions.remove('ask_document_possession')
    if re.search(r'(분석|검토|살펴|봐보고|보고).*(다시|다음|추후).*(찾아|만나|미팅|상담|말씀|설명)|다음미팅|다시찾아',n):_add(move,'propose_analysis_followup')
    if re.search(r'(언제|몇시|날짜|일정).*(만나|미팅|상담|볼까요|뵐까요)|다음주|이번주|(월요일|화요일|수요일|목요일|금요일|주말).*(다시|상담|미팅|만나)',n):_add(move,'schedule_followup')

    # Context restoration and generic continuation.
    if re.search(r'(보고있는중|보고있었|보던중|확인중|확인하고있).*증권|증권.*(보고있는|보고있었|보던)',n):_add(move,'restore_document_context')
    if re.search(r'(말씀해|알려주|계속말|그다음)',n) and len(n)<=24:_add(move,'prompt_continue')

    # A bare object often answers the customer's pending question.
    pending=state.top_pending()
    if pending:
        if pending.kind=='choose_policy':
            if len(move.policy_ids)==1 and len(n)<=24:_add(move,'select_policy')
        elif pending.kind=='choose_section':
            if re.fullmatch(r'(보험료|보험료요|보험료입니다|금액|금액이요)',n):_add(move,'select_premium_section')
            if re.fullmatch(r'(보장|보장내용|보장내용이요|담보|담보내용|보장확인)',n):_add(move,'select_coverage_section')
        elif pending.kind=='transfer_method':
            if re.search(r'(카톡|문자|메일|이메일|메신저|사진으로|여기로)',n):_add(move,'answer_transfer_method')
        elif pending.kind=='followup_schedule':
            if re.search(r'(다음주|이번주|월요일|화요일|수요일|목요일|금요일|주말|오전|오후|시)',n):_add(move,'answer_followup_schedule')

    # If user simply names a policy while a document is open, treat as selection.
    if len(move.policy_ids)==1 and len(n)<=24 and state.active_document and not any(a.startswith('ask_') for a in move.actions):
        _add(move,'select_policy')

    # If a generic amount question is asked while a policy is active, prefer the
    # policy premium over total premium.
    if state.active_policy_id and generic_amount and not re.search(r'(전체|총|한달전체|월전체)',n):
        if 'ask_total_premium' in move.actions:move.actions.remove('ask_total_premium')
        _add(move,'ask_selected_policy_premium')

    # Domain context inference for "무슨 내용이 보이시나요" after document open.
    if state.active_document and re.search(r'(무슨내용|어떤내용|뭐가보|무슨항목|어떤항목)',n):_add(move,'ask_document_contents')

    move.objects=[]
    if move.policy_ids:move.objects.extend(move.policy_ids)
    if move.coverage_key:move.objects.append(move.coverage_key)
    move.raw_confidence='high' if move.actions else 'low'
    return move


def _policy_by_id(world:dict,pid:str|None)->dict|None:
    if not pid:return None
    return next((p for p in policies(world) if p['id']==pid),None)

def _comma(items:list[str])->str:
    return ', '.join(items)

def _disclose(plan:V5Plan,label:str,value:str)->None:
    plan.disclosures[label]=value

def _set_active_policy(state:DialogueStateV5,pid:str)->None:
    state.active_policy_id=pid;state.active_topic='policy_detail';state.active_coverage_key=None

def _push_question(state:DialogueStateV5,kind:str,turn:int,target:str|None=None,options:list[str]|None=None)->None:
    state.set_pending(kind,turn,target,options)

def _known_policy_text(world:dict)->str:
    names=remembered_policy_names(world)
    if not names:return '정확히 기억나는 계약은 많지 않아요. 증권을 확인해야 할 것 같아요.'
    return '기억나는 건 ' + _comma(names) + ' 정도예요. 다른 계약은 증권을 봐야 정확히 말씀드릴 수 있어요.'

def _document_policy_text(world:dict)->str:
    names=[p['name'] for p in policies(world)]
    return '증권에 보이는 계약은 ' + _comma(names) + '이에요.'

def _all_policy_premiums(world:dict)->str:
    return '증권상 월 보험료는 ' + ', '.join(f"{p['name']} {won_text(p['premium_won'])}" for p in policies(world)) + '으로 보여요.'

def _multiple_coverage_text(ps:list[dict])->str:
    return ' '.join(coverage_summary(p,include_amounts=True,max_items=5) for p in ps)

def _track_answered(state:DialogueStateV5,key:str,turn:int,plan:V5Plan)->None:
    if key in state.answered_topics:
        state.metrics['repeated_known_questions']+=1;plan.flags.add('repeated_known_question')
    state.answered_topics[key]=turn

def _resolve_pending_selection(move:ParsedMoveV5,state:DialogueStateV5,world:dict,turn:int)->V5Plan|None:
    p=state.top_pending()
    if not p:return None
    if 'select_policy' in move.actions and len(move.policy_ids)==1:
        pid=move.policy_ids[0];pol=_policy_by_id(world,pid)
        if pol:
            _set_active_policy(state,pid);state.clear_pending();state.metrics['pending_resolutions']+=1
            plan=V5Plan(True, f"네, {pol['name']}부터 볼게요. 증권상 월 보험료는 {won_text(pol['premium_won'])}이고 상품 유형은 {pol['product_type']}으로 표시돼 있어요. 보험료와 보장 중 어떤 부분부터 볼까요?", {'context_followed'}, actions=move.actions)
            _push_question(state,'choose_section',turn,target=pid,options=['premium','coverage'])
            return plan
    if 'select_premium_section' in move.actions and state.active_policy_id:
        pol=_policy_by_id(world,state.active_policy_id);state.clear_pending();state.metrics['pending_resolutions']+=1
        return V5Plan(True,f"{pol['name']}은 증권상 월 {won_text(pol['premium_won'])}이에요.",{'context_followed'},actions=move.actions)
    if 'select_coverage_section' in move.actions and state.active_policy_id:
        pol=_policy_by_id(world,state.active_policy_id);state.clear_pending();state.metrics['pending_resolutions']+=1
        return V5Plan(True,coverage_summary(pol,include_amounts=True),{'context_followed'},actions=move.actions)
    if 'answer_transfer_method' in move.actions:
        state.clear_pending();state.metrics['pending_resolutions']+=1;state.agreements['document_transfer_method']=move.text
        return V5Plan(True,'네, 말씀하신 방식으로 전달할게요. 자료를 보신 뒤 어떤 부분을 다시 확인하면 될까요?',{'document_transfer_agreed','material_consent'},actions=move.actions)
    if 'answer_followup_schedule' in move.actions:
        state.clear_pending();state.metrics['pending_resolutions']+=1;state.metrics['followup_agreements']+=1;state.agreements['followup_schedule']=move.text
        return V5Plan(True,f"네, {move.text.strip()}로 생각해둘게요. 증권 분석 후 그때 다시 확인하면 되겠네요.",{'followup_agreed','closure_confirmed'},actions=move.actions)
    return None


def plan_c07(session:Any,text:str,turn:int)->V5Plan:
    """Plan one C07 customer reply using the V5 customer world and state."""
    world=session.world;state=session.v5_state
    move=parse_move(text,state,world);state.last_actions=list(move.actions);state.last_objects=list(move.objects);state.last_move_text=text
    plan=V5Plan(False,actions=list(move.actions),audit={'actions':list(move.actions),'policy_ids':list(move.policy_ids),'coverage_key':move.coverage_key})

    pending_plan=_resolve_pending_selection(move,state,world,turn)
    if pending_plan:return pending_plan

    # Hostility is a customer-state event, not a language-engine failure.
    if 'hostile' in move.actions:
        state.metrics['hostile_turns']+=1
        plan.handled=True;plan.flags.add('hostile_advisor');plan.state_delta={'trust':-8,'resistance':10,'patience':-18}
        if session.mode in ('SOLO','ASSESSMENT'):
            plan.text='그렇게 말씀하시면 조금 당황스럽네요. 상담을 계속할지 다시 생각해보고 싶어요.'
        else:
            plan.text='제가 설명을 잘 못 드렸을 수는 있지만, 그렇게 말씀하시면 조금 당황스러워요. 확인하려는 부분을 다시 말씀해 주시겠어요?'
        return plan

    if 'repeat_request' in move.actions:
        plan.handled=True;plan.flags.add('repeat_requested');plan.text=session.dialogue_memory.last_customer_response or session.opening_text
        return plan

    if 'greeting' in move.actions and len(move.actions)==1:
        return V5Plan(True,'안녕하세요. 보험료가 계속 부담돼서 한번 제대로 확인해보고 싶어요.',{'rapport_acknowledged'},actions=move.actions)
    if 'empathy' in move.actions and len([a for a in move.actions if a!='greeting'])<=1:
        return V5Plan(True,'네, 계속 내고는 있는데 요즘은 부담이 좀 커졌어요. 같이 확인해보면 좋겠어요.',{'acknowledged_concern'},actions=move.actions)

    if 'ask_customer_concern' in move.actions:
        state.active_topic='premium';_track_answered(state,'customer_concern',turn,plan)
        plan.handled=True;plan.text='제가 제일 궁금한 건 보험료가 왜 이렇게 많이 나가는지예요. 필요한 보장은 가능하면 유지하면서 부담을 줄일 수 있는지도 알고 싶어요.'
        _disclose(plan,'고객의 현재 관심사','보험료 부담 원인과 필요한 보장 유지 가능성');return plan

    if 'ask_burden_reason' in move.actions:
        state.active_topic='premium';_track_answered(state,'burden_reason',turn,plan)
        reason=session.facts.get('burden_trigger') or world.get('financial',{}).get('burden_trigger') or '가계 지출 증가'
        plan.handled=True;plan.text=f'최근에는 {reason} 때문에 보험료가 더 부담스럽게 느껴져요.';plan.flags.add('trigger')
        _disclose(plan,'부담 계기',str(reason));return plan

    if 'ask_preference' in move.actions:
        _track_answered(state,'preference',turn,plan);pref=session.facts.get('preference') or world.get('financial',{}).get('preference')
        plan.handled=True;plan.text=f'{pref} 쪽으로 보고 싶어요.';plan.flags.add('preference');_disclose(plan,'유지하고 싶은 조건',str(pref));return plan

    if 'ask_total_premium' in move.actions:
        state.active_topic='premium';_track_answered(state,'total_premium',turn,plan)
        value=premium_total(world,from_document=bool(world.get('document',{}).get('opened')))
        truth=premium_total(world,from_document=True)
        if world.get('document',{}).get('opened') and value==truth:
            plan.text=f'증권을 보니 전체 월 보험료는 {won_text(value)}이에요.';certainty='증권 확인'
        else:
            plan.text=f'제가 기억하기로는 전체로 한 달에 {won_text(value)} 정도 나가요.';certainty='고객 기억'
        plan.handled=True;plan.flags.add('premium');_disclose(plan,'전체 월 보험료',f'{int(value):,}원 · {certainty}');return plan

    if 'ask_burdensome_policy' in move.actions:
        state.active_topic='portfolio';_track_answered(state,'burdensome_policy',turn,plan)
        cname=str(session.facts.get('burdensome_contract') or '부담되는 계약');p=find_policy(world,cname)
        premium=(p or {}).get('premium_won') or session.facts.get('burdensome_contract_premium_won')
        plan.handled=True;plan.text=f'가장 부담되는 건 {cname}이에요. 그 계약만 한 달에 {won_text(premium)} 정도 나가요.';plan.flags.add('contract')
        _disclose(plan,'부담 계약',cname);_disclose(plan,'해당 월 보험료',f'{int(premium):,}원 · 고객 진술');return plan

    if 'ask_policy_list' in move.actions:
        state.active_topic='portfolio';_track_answered(state,'policy_list',turn,plan);plan.handled=True
        if world.get('document',{}).get('opened'):
            plan.text=_document_policy_text(world)+' 어떤 계약부터 볼까요?';_disclose(plan,'증권 계약 목록',' · '.join(p['name'] for p in policies(world)))
            _push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)])
        else:
            plan.text=_known_policy_text(world);_disclose(plan,'기억하는 계약',' · '.join(remembered_policy_names(world)) or '정확히 기억하지 못함')
        return plan

    if 'ask_document_possession' in move.actions:
        state.active_topic='document';plan.handled=True;plan.flags.add('document_available')
        plan.text=document_access_message(world);_disclose(plan,'증권 상태',world.get('document',{}).get('location','확인 필요'))
        return plan

    if 'ask_document_method' in move.actions:
        state.active_topic='document';plan.handled=True
        if world.get('document',{}).get('opened'):
            plan.text='지금 열어둔 증권에서 계약을 하나 선택한 다음 세부 담보나 가입금액을 펼쳐보면 확인할 수 있어요.'
        else:
            plan.text=document_access_message(world)
            if world.get('document',{}).get('can_open_now'):plan.text+=' 지금 같이 열어보면 돼요.'
        return plan

    if 'request_document_open' in move.actions:
        state.active_topic='document';plan.handled=True
        if world.get('document',{}).get('opened'):
            state.active_document='policy_document';plan.flags.update({'document_opened','material_consent','review_before_decision'})
            plan.text='네, 지금 증권을 열어둔 상태예요. '+_document_policy_text(world)+' 어떤 계약부터 볼까요?'
            _push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)])
            return plan
        ok,msg=open_document(world)
        if ok:
            state.active_document='policy_document';state.active_policy_id=None;state.clear_pending();plan.flags.update({'document_opened','material_consent','review_before_decision'})
            plan.text=msg+' '+_document_policy_text(world)+' 어떤 계약부터 볼까요?';_disclose(plan,'증권 상태','증권 열람 중');_disclose(plan,'증권 계약 목록',' · '.join(p['name'] for p in policies(world)))
            _push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)])
            state.add_contract('현재 계약을 먼저 확인한 뒤 변경 여부를 판단한다')
        else:
            plan.flags.add('document_status_shared');plan.text=msg
        return plan

    if 'restore_document_context' in move.actions:
        plan.handled=True;state.metrics['context_resolutions']+=1;state.metrics['recoveries']+=1;plan.flags.update({'context_restored','repair_recovered'})
        if world.get('document',{}).get('opened'):
            state.active_document='policy_document'
            pol=_policy_by_id(world,state.active_policy_id)
            if pol:plan.text=f'맞아요. 지금 증권에서 {pol["name"]}을 보고 있었어요. {coverage_summary(pol,include_amounts=True)}'
            else:plan.text='맞아요. 지금 증권을 보고 있었어요. '+_document_policy_text(world)+' 어떤 계약부터 이어서 볼까요?';_push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)])
        else:plan.text='맞아요. 증권을 확인하려던 중이었어요. 지금 확인 가능한 자료부터 다시 볼게요.'
        return plan

    if 'ask_document_contents' in move.actions:
        plan.handled=True;state.active_topic='document'
        if not world.get('document',{}).get('opened'):
            plan.text=document_access_message(world)+' 먼저 증권을 열어야 내용을 정확히 볼 수 있어요.';return plan
        pol=_policy_by_id(world,state.active_policy_id)
        if pol:
            plan.text=policy_summary(pol)+'으로 표시돼 있고, '+coverage_summary(pol,include_amounts=True);return plan
        plan.text=_document_policy_text(world)+' 어떤 계약부터 볼까요?';_push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)]);return plan

    if 'ask_policy_premiums' in move.actions:
        plan.handled=True;state.active_topic='portfolio'
        if world.get('document',{}).get('opened'):
            plan.text=_all_policy_premiums(world);plan.flags.add('document_premiums_shared');_disclose(plan,'계약별 월 보험료','증권에서 계약별 보험료 확인')
        else:
            names=[]
            for p in policies(world):
                mem=world.get('knowledge',{}).get('policies',{}).get(p['id'],{}).get('premium_memory')
                if mem:names.append(f"{p['name']} {won_text(mem)} 정도")
            plan.text=('기억나는 범위로는 '+', '.join(names)+'예요. 다른 계약은 증권을 봐야 정확해요.') if names else '계약별 보험료는 정확히 기억나지 않아요. 증권을 봐야 해요.'
        return plan

    if 'ask_selected_policy_premium' in move.actions:
        plan.handled=True
        pol=find_policy(world,text,active_policy_id=state.active_policy_id)
        if not pol:plan.handled=False;return plan
        _set_active_policy(state,pol['id'])
        correction=''
        if move.amounts and ('중' in text or '전체' in text or '총' in text):
            total_truth=int(world.get('insurance',{}).get('total_monthly_premium_won') or 0)
            candidates=[x for x in move.amounts if x!=int(pol.get('premium_won') or -1)]
            if candidates and total_truth not in candidates:
                correction=f'아까 말씀드린 전체 월 보험료는 {won_text(total_truth)}이에요. '
                plan.flags.add('customer_corrected_amount')
        if world.get('document',{}).get('opened'):
            plan.text=correction+f'{pol["name"]}은 증권상 월 {won_text(pol["premium_won"])}이에요.'
        else:
            mem=world.get('knowledge',{}).get('policies',{}).get(pol['id'],{}).get('premium_memory')
            plan.text=correction+f'{pol["name"]} 보험료는 '+(f'{won_text(mem)} 정도로 기억해요.' if mem else '정확히 기억나지 않아요. 증권을 봐야 해요.')
        return plan

    if 'ask_coverage_knowledge' in move.actions:
        plan.handled=True;state.active_topic='coverage'
        if world.get('document',{}).get('opened'):
            plan.text='기억으로는 정확하지 않았는데 지금 증권을 열어둔 상태라 계약별 보장을 확인할 수 있어요. 어떤 계약부터 볼까요?';_push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)])
        else:
            plan.text='큰 틀만 기억하고 정확한 담보명과 가입금액은 잘 모르겠어요. 증권을 같이 보면 좋겠어요.';_disclose(plan,'담보별 보장 내용','미확인 · 상세 자료 확인 필요')
        return plan

    if 'ask_coverage_details' in move.actions:
        plan.handled=True;state.active_topic='coverage'
        if not world.get('document',{}).get('opened'):
            plan.text='정확한 담보 내용은 기억만으로 말씀드리기 어려워요. 증권을 확인해야 해요.';_disclose(plan,'담보별 보장 내용','미확인 · 상세 자료 확인 필요');return plan
        ps=find_policies(world,text)
        # In sentences such as '실손은 괜찮아 보이네요. 종신과 건강의 세부 보장은?'
        # the requested objects are in the clause nearest the coverage question.
        if len(ps)>1:
            m=re.search(r'([^.!?]{0,60}(?:세부\s*보장|보장\s*내용|담보)[^.!?]*)[?？]?$',text,re.I)
            if m:
                focused=find_policies(world,m.group(1))
                if focused:ps=focused
        if not ps:
            p=_policy_by_id(world,state.active_policy_id);ps=[p] if p else []
        if ps:
            if len(ps)==1:_set_active_policy(state,ps[0]['id'])
            plan.text=_multiple_coverage_text(ps);_disclose(plan,'보장 내용 확인','증권 세부 담보 확인');return plan
        plan.text=_document_policy_text(world)+' 어떤 계약의 보장을 볼까요?';_push_question(state,'choose_policy',turn,options=[p['id'] for p in policies(world)]);return plan

    if 'ask_product_type_ci' in move.actions:
        plan.handled=True
        p=find_policy(world,text,active_policy_id=state.active_policy_id)
        if not p:
            plan.text='어느 계약을 말씀하시는지 지정해 주시면 증권의 상품 유형을 확인해볼게요.';_push_question(state,'choose_policy',turn,options=[x['id'] for x in policies(world)]);return plan
        _set_active_policy(state,p['id']);ptype=p.get('product_type','상품 유형 확인 필요')
        if 'CI' in ptype.upper():plan.text=f'네. 증권에는 {p["name"]}의 상품 유형이 {ptype}으로 표시돼 있어요. 세부 급부 조건은 이 훈련용 증권에 적힌 범위까지만 확인할게요.'
        else:plan.text=f'아니요. 이 가상 증권에는 {p["name"]}이 {ptype}으로 표시돼 있고 CI형으로 표시되지는 않아요.'
        plan.flags.add('product_type_checked');return plan

    if 'ask_coverage_amount' in move.actions and move.coverage_key:
        plan.handled=True;state.active_topic='coverage';state.active_coverage_key=move.coverage_key
        if not world.get('document',{}).get('opened'):
            plan.text='그 가입금액은 기억만으로는 정확히 말씀드리기 어려워요. 증권을 열어서 확인해야 해요.';return plan
        p=find_policy(world,text,active_policy_id=state.active_policy_id)
        matches=[]
        if p:
            matches=[(p,c) for c in p.get('coverages',[]) if c.get('id')==move.coverage_key]
        else:matches=coverage_across_portfolio(world,move.coverage_key)
        if not matches:
            plan.text='지금 열린 증권 범위에서는 그 담보가 확인되지 않아요.';return plan
        plan.text='증권상 ' + ', '.join(f"{pp['name']}의 {c['name']} {won_text(c.get('amount_won'))}" for pp,c in matches) + '으로 보여요.';return plan

    if 'request_document_transfer' in move.actions:
        plan.handled=True;state.active_topic='document'
        if can_send_document(world):
            mark_document_shared(world);plan.flags.update({'material_consent','document_transfer_agreed','review_before_decision'});state.agreements['document_transfer']=True;state.add_contract('증권 자료를 상담사가 검토한다')
            plan.text='네, 증권 파일을 전달할 수 있어요. 어떤 방식으로 보내드리면 될까요?';_push_question(state,'transfer_method',turn,options=['message','email']);_disclose(plan,'자료 전달','증권 전달 동의 · 전달 방법 미정')
        else:
            plan.text='지금은 제가 전체 증권을 가지고 있지 않아서 바로 보내드리기는 어려워요. 자료를 받은 뒤 전달할 수 있을지 확인해볼게요.';plan.flags.add('document_transfer_unavailable')
        return plan

    if 'propose_analysis_followup' in move.actions:
        plan.handled=True;plan.flags.update({'review_before_decision','followup_pending'});state.add_contract('자료 분석 후 후속 상담에서 다시 검토한다');state.agreements['analysis_followup']=True
        if world.get('document',{}).get('shared') or world.get('document',{}).get('opened'):
            plan.text='네, 먼저 증권을 분석해 주시고 다시 설명해 주시면 좋겠어요. 언제쯤 다시 보면 될까요?';_push_question(state,'followup_schedule',turn)
        else:
            plan.text='좋아요. 다만 분석하려면 어떤 자료를 드려야 하는지 먼저 정하면 좋겠어요.'
        return plan

    if 'schedule_followup' in move.actions:
        plan.handled=True;plan.flags.add('followup_pending')
        if re.search(r'(다음주|이번주|월요일|화요일|수요일|목요일|금요일|주말|오전|오후|\d+\s*시)',text):
            state.agreements['followup_schedule']=text;state.metrics['followup_agreements']+=1;plan.flags.update({'followup_agreed','closure_confirmed'});plan.text=f'네, 말씀하신 일정으로 다시 확인하는 걸로 할게요.'
        else:
            plan.text='좋아요. 가능한 날짜나 시간을 정해주시면 그때 다시 확인할게요.';_push_question(state,'followup_schedule',turn)
        return plan

    if 'prompt_continue' in move.actions:
        plan.handled=True
        if world.get('document',{}).get('opened'):
            p=_policy_by_id(world,state.active_policy_id)
            if p:plan.text=policy_summary(p)+'이고, '+coverage_summary(p,include_amounts=True)
            else:plan.text=_document_policy_text(world)+' 어떤 계약부터 볼까요?';_push_question(state,'choose_policy',turn,options=[x['id'] for x in policies(world)])
        else:plan.text='제가 기억하는 범위부터 말씀드리면 '+_known_policy_text(world)
        return plan

    # Short policy selection even when no pending question survived a rerender.
    if 'select_policy' in move.actions and move.policy_ids:
        p=_policy_by_id(world,move.policy_ids[0]);_set_active_policy(state,p['id']);state.metrics['context_resolutions']+=1
        plan.handled=True;plan.flags.add('context_followed');plan.text=f'{p["name"]}을 보고 있어요. 증권상 월 보험료는 {won_text(p["premium_won"])}이고, {coverage_summary(p,include_amounts=True)}';return plan

    # Current document/policy supplies missing referent for a short question.
    if state.active_policy_id and re.search(r'(그건|그거|그보험|이건|그부분).*(얼마|보장|담보)',_norm(text)):
        p=_policy_by_id(world,state.active_policy_id);state.metrics['context_resolutions']+=1;plan.handled=True;plan.flags.add('context_followed')
        if re.search(r'얼마',_norm(text)):plan.text=f'{p["name"]}은 월 {won_text(p["premium_won"])}이에요.'
        else:plan.text=coverage_summary(p,include_amounts=True)
        return plan

    # No confident V5 action. Leave the legacy engine a chance; if it also fails,
    # the existing neutral repair policy is used.
    return plan


def state_snapshot(state:DialogueStateV5)->dict:
    return {
        'stage':state.stage,'active_topic':state.active_topic,'active_document':state.active_document,
        'active_policy_id':state.active_policy_id,'active_coverage_key':state.active_coverage_key,
        'pending':[asdict(x) for x in state.pending],
        'agreements':dict(state.agreements),'conversation_contracts':list(state.conversation_contracts),
        'metrics':dict(state.metrics),
    }
