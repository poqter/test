"""Conversation context and lightweight Korean reference/slot resolution for V3.

This is deterministic dialogue management rather than generative AI. It enriches
an Interpretation with conversational acts and entities so short/elliptical Korean
can be handled against the current topic without fabricating customer facts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from .language import Interpretation, Hit, norm, rule_text
from .semantic_v3 import parse_semantic_frame

@dataclass
class DialogueMemory:
    focus: str | None = None
    subfocus: str | None = None
    pending_kind: str | None = None
    pending_turn: int | None = None
    pending_options: list[str] = field(default_factory=list)
    repair_streak: int = 0
    support_needed: bool = False
    last_customer_question: str | None = None
    last_customer_response: str | None = None
    last_advisor_text: str | None = None
    active_object: str | None = None
    active_object_state: str | None = None
    last_semantic_acts: list[str] = field(default_factory=list)
    last_semantic_objects: list[str] = field(default_factory=list)
    topic_stack: list[str] = field(default_factory=list)

TOPICS = {
    'premium': (r'보험료|월납|납입(?:금|액)?|매달\s*(?:나가|내)',),
    'coverage': (r'보장\s*(?:내용|범위)?|담보|가입금액',),
    'contracts': (r'증권|보험\s*내역|계약\s*(?:내용|내역)|가입한\s*보험',),
    'indemnity': (r'실손|실비|의료실비|실손의료비|실손보험',),
    'whole_life': (r'종신(?:보험)?',),
    'documents': (r'증권|자료|보험사\s*앱|계약서',),
    'schedule': (r'일정|시간|날짜|언제',),
}

def _add_entity(i: Interpretation, key: str, value: str) -> None:
    i.entities.setdefault(key, [])
    if value not in i.entities[key]: i.entities[key].append(value)

def _topic_reply(text: str) -> str | None:
    c=norm(text);c=re.sub(r'^(?:아니요|아니|아|네|예)','',c);c=re.sub(r'^.{1,20}(?:아니라|말고)','',c)
    choices={
      'premium':r'(?:보험료|월보험료|보험료금액)',
      'coverage':r'(?:보장(?:내용|범위)?|담보(?:내용|범위)?)',
      'contracts':r'(?:가입(?:하신|한)?보험|가입보험내역|보험내역|가입내역|현재계약|가입계약|증권|자료)',
      'indemnity':r'(?:실손|실비|실손의료비|실손보험)',
    }
    for key,phrase in choices.items():
        if re.fullmatch(phrase+r'(?:이요|요|입니다|예요|이에요|말이에요|말씀입니다)?',c):return key
    return None

def _extract_entities(i: Interpretation) -> None:
    text=rule_text(i.text)
    for key,regs in TOPICS.items():
        if any(re.search(r,text,re.I) for r in regs): _add_entity(i,'topic',key)
    # Conversational pronouns are resolved later from focus/pending context.
    if re.search(r'그\s*(?:거|것|부분|금액)|아까\s*(?:말한|말씀한|그)',text): _add_entity(i,'reference','previous')
    if re.search(r'어떻게|어디서|무슨\s*방법',text): _add_entity(i,'request','method')
    if re.search(r'얼마|어느\s*정도|얼만큼|비중',text): _add_entity(i,'request','amount')
    if re.search(r'가지고\s*계|있으신가|있나요|보유|찾아볼|열어볼',text): _add_entity(i,'request','possession')

def _general_acts(i: Interpretation, memory: DialogueMemory) -> None:
    t=rule_text(i.text);c=norm(t)
    acts=i.dialogue_acts
    def add(x):
        if x not in acts:acts.append(x)
    if re.fullmatch(r'\s*[?？]+\s*',t) or re.fullmatch(r'(?:네|예|어|응)\s*[?？]+',t.strip()): add('repeat_request')
    if re.search(r'(?:다시|뭐라고|무슨\s*말씀|무슨\s*뜻).{0,12}(?:말씀|인가|이죠|요)',t):add('repeat_request')
    if re.search(r'(?:증권|자료).{0,20}(?:가지고|갖고|보유|있으|있나|찾을\s*수|계신)',t):add('ask_document_possession')
    if re.search(r'(?:증권|자료).{0,18}(?:확인해\s*주|확인해보|찾아\s*보|열어\s*보)',t):add('request_document_check')
    if re.search(r'(?:어떻게|어디서).{0,20}(?:확인|찾|보)',t):add('ask_document_method')
    if re.search(r'(?:아는|알고\s*계신|기억나는).{0,15}(?:내용|것).{0,12}(?:말씀|알려)',t):add('ask_known_information')
    if re.search(r'(?:실손|실비|실손의료비).{0,26}(?:보험료|금액|비중|얼마|얼만큼)',t) or re.search(r'(?:보험료|금액).{0,22}(?:실손|실비)',t):add('ask_indemnity_premium')
    # Omitted subject amount question. The current focus supplies the referent.
    if re.search(r'(?:얼마\s*정도|얼마나|얼만큼|어느\s*정도).{0,22}(?:납입|내고|내시|나가|빠져|되|지출|결제)|(?:매달|한\s*달).{0,15}(?:얼마|어느\s*정도).{0,12}(?:내|나가|빠져)',t) and not i.ids:
        if memory.focus in ('premium_total','premium_multiple','premium_indemnity',None):
            i.hits.append(Hit('DS13',0,len(t),t,'contextual_amount_question'));i.status='accepted';i.context_turn=memory.pending_turn
    # Domain shorthand: after a premium discussion, "뭐가 제일 많이 나가요?"
    # means the burdensome contract rather than a completely new topic.
    if not i.ids and memory.focus in ('premium_total','premium_multiple','premium_contract') and re.search(r'(?:뭐|어떤|어느\s*(?:보험|계약)?).{0,15}(?:제일|가장|많이|크게).{0,15}(?:나가|부담|비싸)',t):
        i.hits.append(Hit('DS14',0,len(t),t,'contextual_contract_question'));i.status='accepted';i.context_turn=memory.pending_turn
    # A short choice answer resolves a customer clarification first, not as a new question.
    topic=_topic_reply(t)
    if topic:
        add('topic_'+topic);i.context_turn=memory.pending_turn
    if re.search(r'(?:같이|함께|하나씩|차근차근).{0,25}(?:확인|살펴|봐)',t):add('review_together')
    if re.search(r'(?:가입\s*(?:한|하신)|기존).{0,12}(?:보험|계약).{0,20}(?:확인|살펴|보)',t):add('review_contracts')
    # A bare contract noun phrase can be a contextual answer after the customer
    # has asked what the advisor wants to inspect (e.g. "고객님께서 가입하신 보험이요").
    if re.search(r'(?:가입\s*(?:한|하신)\s*보험|가입\s*보험\s*내역|보험\s*내역|현재\s*계약|기존\s*계약)',t) and not re.search(r'(?:왜|어떻게|얼마|무엇|뭐|어떤|어느)',t):
        add('topic_contracts')
    if re.search(r'보험료.{0,20}(?:확인|살펴|보)',t):add('review_premium')
    if re.search(r'(?:보장\s*내용|담보|가입금액).{0,20}(?:확인|살펴|보)',t):add('review_coverage')
    # Contrast corrections such as "보험료가 아니라 보장 내용이요" must not
    # retain the negated topic as a second active act.
    if re.search(r'보험료.{0,12}(?:아니라|말고).{0,18}(?:보장|담보)',t):
        acts[:] = [a for a in acts if a not in ('topic_premium','review_premium')]
        add('topic_coverage')
    elif re.search(r'(?:보장|담보).{0,12}(?:아니라|말고).{0,18}보험료',t):
        acts[:] = [a for a in acts if a not in ('topic_coverage','review_coverage')]
        add('topic_premium')
    # Generic instruction/continuation acts used by response planning, not scoring.
    if re.fullmatch(r'(?:말씀해\s*주세요|말씀해주세요|아는내용말씀해주세요|알려주세요)',c):add('prompt_customer_continue')
    if re.search(r'(?:자료|증권).{0,15}(?:확인해\s*주세요|확인해주세요)',t):add('request_document_check')
    if re.search(r'(?:자료|증권).{0,24}(?:확인).{0,24}(?:말씀|준다면서|주신다면서|하신다|한다고|하셨)',t):add('remind_document_check')
    if re.search(r'(?:그냥|일단).{0,12}(?:하세요|하시면|해야죠)|왜.{0,10}(?:안|못).{0,8}(?:하세요|하시죠)',t):add('pressure')

def interpret_context(i: Interpretation, memory: DialogueMemory, last_turn: int) -> Interpretation:
    _extract_entities(i)
    _general_acts(i,memory)
    frame=parse_semantic_frame(i.text,memory)
    for act in frame.acts:
        if act not in i.dialogue_acts:i.dialogue_acts.append(act)
    for obj in frame.objects:_add_entity(i,'semantic_object',obj)
    for key,value in frame.slots.items():
        if isinstance(value,list):
            for item in value:_add_entity(i,'semantic_'+key,str(item))
        else:_add_entity(i,'semantic_'+key,str(value))
    if i.control or i.risk_candidates or i.quoted:return i
    # Pending clarification has priority over generic keyword matching.
    topic=_topic_reply(i.text)
    if topic and (memory.pending_kind or last_turn>0):
        if 'topic_'+topic not in i.dialogue_acts:i.dialogue_acts.append('topic_'+topic)
        i.context_turn=memory.pending_turn or last_turn;i.status='accepted'
    c=norm(i.text)
    if memory.pending_kind=='premium_scope':
        if re.fullmatch(r'(?:전체|총액|총보험료|전부합쳐서|전체금액)(?:요|이요|입니다|예요|부터요)?',c):iid='DS13'
        elif re.fullmatch(r'(?:부담되는계약|부담되는보험|가장큰보험|가장비싼보험|제일비싼보험|어떤보험)(?:요|이요|입니다|예요|부터요)?',c):iid='DS14'
        else:iid=None
        if iid:
            if iid not in i.ids:i.hits.append(Hit(iid,0,len(i.text),i.text,'explicit_pending_choice'))
            i.context_turn=memory.pending_turn;i.status='accepted'
    # Resolve pronouns and generic "그 금액" to the previous active topic.
    if i.entities.get('reference') and memory.focus:
        _add_entity(i,'resolved_reference',memory.focus)
        if not i.hits and 'amount' in i.entities.get('request',[]):
            if memory.focus=='premium_total':
                i.hits.append(Hit('DS13',0,len(i.text),i.text,'resolved_reference_amount'));i.status='accepted';i.context_turn=last_turn
            elif memory.focus=='premium_contract':
                i.hits.append(Hit('DS14',0,len(i.text),i.text,'resolved_reference_amount'));i.status='accepted';i.context_turn=last_turn
            elif memory.focus=='premium_indemnity' and 'ask_indemnity_premium' not in i.dialogue_acts:
                i.dialogue_acts.append('ask_indemnity_premium');i.status='accepted';i.context_turn=last_turn
    if (memory.focus=='premium_total' or memory.focus is None) and not i.hits:
        if re.fullmatch(r'(?:그러면|그럼)?(?:얼마인가요|얼마예요|얼마에요|얼마죠|얼마인지요|얼마나내세요|어느정도내세요|얼마정도내세요)',c):
            i.hits.append(Hit('DS13',0,len(i.text),i.text,'single_known_topic_question'));i.context_turn=last_turn;i.status='accepted'
    if i.dialogue_acts and i.status=='needs_clarification':i.status='accepted'
    return i

def focus_for(ids:set[str],acts:list[str],previous:str|None)->str|None:
    if 'ask_indemnity_premium' in acts or 'topic_indemnity' in acts:return 'premium_indemnity'
    if 'DS13' in ids and 'DS14' in ids:return 'premium_multiple'
    if 'DS14' in ids:return 'premium_contract'
    if 'DS13' in ids:return 'premium_total'
    if 'DS15' in ids:return 'burden_cause'
    if 'DS08' in ids:return 'debt'
    if 'ask_document_possession' in acts or 'request_document_check' in acts or 'ask_document_method' in acts:return 'documents'
    if 'DS16' in ids or 'review_contracts' in acts or 'topic_contracts' in acts:return 'contracts'
    if 'review_coverage' in acts or 'topic_coverage' in acts:return 'coverage'
    if 'topic_premium' in acts or 'review_premium' in acts:return 'premium_total'
    if ids & {'NX02','NX03','NX04'}:return 'schedule'
    if any(x.startswith(('DS','SP','SV')) for x in ids):return None
    return previous
