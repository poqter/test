"""V5 adaptive event director.

Events are *armed* by conversation state and only spoken when the topic makes
sense. This avoids the V3 behaviour of attaching unrelated event cards to a
customer answer.
"""
from __future__ import annotations
from hashlib import sha256
from typing import Any

C07_EVENTS = [
    {
        'id':'V5-C07-RELATION','min_turn':4,'intensity':1,
        'modes':{'GUIDE','COACH','SOLO','ASSESSMENT'},'lengths':{'STANDARD','DEEP'},
        'requires_any_flags':{'contract','document_opened','document_items_shared','product_type_checked'},
        'requires_actions':set(),
        'active_topics':{'policy_detail','coverage','document'},
        'text':'그런데 이 계약은 예전에 아는 분에게 가입한 거라 괜히 건드리는 게 조금 조심스럽긴 해요.',
        'flag':'event_existing_relationship',
    },
    {
        'id':'V5-C07-SPOUSE','min_turn':6,'intensity':2,
        'modes':{'GUIDE','COACH','SOLO','ASSESSMENT'},'lengths':{'DEEP','STANDARD'},
        'requires_any_flags':{'preference','document_opened','review_before_decision'},
        'requires_actions':set(),
        'active_topics':{'premium','policy_detail','coverage'},
        'guide_deep_only':True,
        'text':'배우자는 보험료가 너무 많다면서 그냥 줄였으면 좋겠다고 하긴 해요. 저는 필요한 보장까지 없어질까 봐 그게 걱정돼요.',
        'flag':'event_spouse_view',
    },
    {
        'id':'V5-C07-TIME','min_turn':9,'intensity':2,
        'modes':{'COACH','SOLO','ASSESSMENT'},'lengths':{'STANDARD','DEEP'},
        'requires_any_flags':{'document_opened','document_transfer_agreed'},
        'requires_actions':set(),
        'active_topics':{'document','coverage','policy_detail'},
        'text':'제가 오늘 시간이 아주 많지는 않아서, 지금은 핵심만 정리하고 자세한 건 다음에 봐도 괜찮아요.',
        'flag':'event_time_pressure',
    },
]

MODE_RATE={'GUIDE':0.32,'COACH':0.52,'SOLO':0.72,'ASSESSMENT':0.76}
LENGTH_BUDGET={'QUICK':1,'STANDARD':2,'DEEP':3}

def _roll(seed:int,event_id:str,turn:int)->float:
    raw=int(sha256(f'{seed}:v5-event:{event_id}:{turn}'.encode()).hexdigest()[:8],16)
    return raw/0xffffffff

def maybe_event(session:Any,turn:int,route_flags:set[str])->tuple[str,str]|None:
    if session.scenario_id!='C07-S01' or session.ended:return None
    if 'engine_clarification' in route_flags or 'risk_candidate' in route_flags:return None
    state=session.v5_state
    # Do not inject a side event while the customer is waiting for a concrete
    # follow-up/transfer answer or the conversation has entered its closing arc.
    pending=state.top_pending() if hasattr(state,'top_pending') else None
    if state.stage in ('ANALYSIS_HANDOFF','FOLLOW_UP','COMPLETE') or (pending and pending.kind in ('followup_schedule','transfer_method')):
        return None
    if {'analysis_handoff','followup_pending','followup_confirmed','document_delivery_planned'} & (set(session.flags)|set(route_flags)):
        return None
    if turn < state.event_cooldown_until:return None
    if len(session.events_fired)>=LENGTH_BUDGET.get(session.session_length,2):return None
    all_flags=set(session.flags)|set(route_flags)
    actions=set(state.last_actions)
    for e in C07_EVENTS:
        if e['id'] in session.events_fired or turn<e['min_turn']:continue
        # Events must be compatible with the generated customer world.  A random
        # variation may change timing, never invent a relationship that the
        # customer profile does not have.
        if e['id']=='V5-C07-RELATION' and session.world.get('attitude',{}).get('existing_agent_relation')!='강함':
            continue
        if e['id']=='V5-C07-SPOUSE' and '배우자' not in str(session.world.get('family') or ''):
            continue
        if session.mode not in e['modes'] or session.session_length not in e['lengths']:continue
        if e.get('guide_deep_only') and session.mode=='GUIDE' and session.session_length!='DEEP':continue
        req=e.get('requires_any_flags') or set()
        if req and not (req & all_flags):continue
        reqa=e.get('requires_actions') or set()
        if reqa and not (reqa & actions):continue
        topics=e.get('active_topics') or set()
        if topics and state.active_topic not in topics:continue
        rate=MODE_RATE.get(session.mode,0.5)
        # Within-session adaptation: reduce extra pressure while GUIDE/COACH is
        # already repairing conversation, and modestly increase variation when
        # the learner is moving cleanly through context in SOLO/ASSESSMENT.
        repairs=state.metrics.get('repairs',0);resolved=state.metrics.get('pending_resolutions',0)+state.metrics.get('context_resolutions',0)
        if session.mode in ('GUIDE','COACH') and repairs>=2:rate=max(0.12,rate-0.20)
        if session.mode in ('SOLO','ASSESSMENT') and repairs==0 and resolved>=2:rate=min(0.92,rate+0.08)
        if _roll(session.seed,e['id'],turn)>rate:continue
        session.events_fired.append(e['id']);session.flags.setdefault(e['flag'],turn)
        session.disclosed.setdefault('event_'+e['id'],{'label':'대화 중 새로 나온 상황','value':e['text'],'turn':turn,'certainty':'customer_statement'})
        state.event_cooldown_until=turn+3
        state.event_log.append({'turn':turn,'event_id':e['id'],'flag':e['flag']})
        return e['text'],e['flag']
    return None
