"""Evidence-based provisional rubric: no certification and no emotion diagnosis."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from .content import SCENARIOS, CRITERIA, CATEGORIES, AXES
from .engine import Session, completion_gate
from .mission_graph_v5 import goal_status as c07_goal_status
from .training_policy_v55 import pacing as c07_pacing, loop_diagnostics as c07_loop_diagnostics, open_loops as c07_open_loops

# Each group requires ALL flags. Several groups = independently observable
# portions of the full-evidence gate. Gate source: pilot_evidence_contract V1.1.
# These executable translations are implementation decisions, not new tax rules.
GATES = {
 'C07-S01': {
  'Q1': [['premium'],['contract'],['certainty_checked']],
  'L2': [['numeric_summary_confirmed']],
  'N2': [['trigger'],['preference']],
  'E2': [['limitation_explained']],
  'F1': [['review_before_decision'],['choice_respected']],
  'X1': [['material_consent']],
 },
 'A01-S01': {
  'Q1': [['time'],['interest']], 'L2': [['summary_confirmed']],
  'N1': [['interest'],['summary_confirmed']],
  'E2': [['intent_CT01'],['intent_CT02'],['intent_CT05']],
  'F2': [['choice_respected'],['time']], 'X3': [['closure_confirmed']],
 },
 'D08-S01': {
  'Q1': [['documents'],['preference']], 'L3': [['limitation_explained']],
  'N3': [['preference']], 'E1': [['document_pack_verified']],
  'F1': [['review_consent'],['limitation_explained']], 'X1': [['review_consent']],
 },
 'F07-S01': {
  'Q1': [['spouse_concern']], 'L1': [['preference'],['summary_confirmed']],
  'N3': [['spouse_concern'],['material_consent']],
  'E2': [['material_consent'],['limitation_explained']],
  'F2': [['choice_respected'],['closure_confirmed']],
  'X1': [['material_consent'],['customer_initiates'],['closure_confirmed']],
 },
 'G10-S01': {
  'Q1': [['claim_status'],['health_unknown']],
  'L1': [['acknowledged_concern'],['previous_assurance']],
  'N1': [['intent_SV06'],['material_scope']],
  'E2': [['limitation_explained'],['check_plan']],
  'F3': [['limitation_explained']], 'X2': [['followup_pending'],['closure_confirmed']],
 },
 'H10-S01': {
  'Q1': [['ownership_unknown'],['goals']],
  'L2': [['summary_confirmed']], 'N3': [['goals'],['family_unknown']],
  'E2': [['goals_separated'],['limitation_explained']],
  'F1': [['limitation_explained'],['review_consent']],
  'X2': [['review_consent'],['closure_confirmed']],
 }
}
DOCUMENT_BLOCKS={'D08-S01':{'E1'},'G10-S01':{'E2'},'H10-S01':{'E2'}}



def _critical_moments(s:Session) -> list[dict]:
    moments=[]
    positive={
        'context_followed':'직전 질문과 현재 대상을 자연스럽게 연결했습니다.',
        'document_opened':'고객 동의를 바탕으로 자료 확인 단계로 전환했습니다.',
        'material_consent':'자료 검토 범위를 고객과 합의했습니다.',
        'followup_agreed':'다음 상담 단계가 구체적으로 합의되었습니다.',
        'repair_recovered':'끊겼던 대화 문맥을 다시 복구했습니다.',
        'numeric_summary_confirmed':'고객이 공개한 금액을 정확히 요약했습니다.',
    }
    caution={
        'repeated_known_question':'이미 확인한 정보를 다시 묻는 흐름이 있었습니다.',
        'engine_clarification':'시스템이 이 발화를 현재 문맥에 확정적으로 연결하지 못했습니다.',
        'risk_candidate':'권고·확약 경계에 해당할 수 있어 검수가 필요한 표현입니다.',
        'hostile_advisor':'고객이 공격적으로 받아들일 수 있는 표현이 사용되었습니다.',
    }
    for t in s.turns:
        flags=set(t.flags)
        for f,reason in positive.items():
            if f in flags:
                moments.append({'turn':t.number,'tone':'good','title':'좋은 전환','reason':reason,'advisor':t.text,'customer':t.response_text});break
        for f,reason in caution.items():
            if f in flags:
                moments.append({'turn':t.number,'tone':'caution','title':'복기할 순간','reason':reason,'advisor':t.text,'customer':t.response_text});break
    if s.end_reason=='customer_exit' and s.turns:
        t=s.turns[-1];moments.append({'turn':t.number,'tone':'caution','title':'상담 종료 신호','reason':'고객의 경계·인내 상태가 종료 기준에 도달했습니다. 직전 몇 턴의 흐름을 함께 복기해 보세요.','advisor':t.text,'customer':t.response_text})
    # Keep the most informative, de-duplicated five moments in conversation order.
    seen=set();out=[]
    for m in moments:
        key=(m['turn'],m['title'])
        if key in seen:continue
        seen.add(key);out.append(m)
    return out[-5:]


def _v5_flow_summary(s:Session) -> dict:
    """Descriptive flow analysis; it never pretends to be an AI personality score."""
    state=getattr(s,'v5_state',None)
    if not state:return {'strengths':[],'watch':[],'metrics':{}}
    m=dict(state.metrics)
    strengths=[];watch=[]
    if m.get('pending_resolutions',0)+m.get('context_resolutions',0)>=2:
        strengths.append('짧은 답변이나 현재 계약·자료 문맥을 이어서 상담한 장면이 확인되었습니다.')
    if m.get('recoveries',0)>0:
        strengths.append('끊긴 대화 문맥을 다시 연결한 회복 장면이 있었습니다.')
    if m.get('followup_agreements',0)>0:
        strengths.append('후속 상담의 다음 행동을 구체적으로 합의했습니다.')
    agreements=getattr(state,'agreements',{})
    if agreements.get('document_delivery_later'):
        strengths.append('증권을 즉시 확인할 수 없는 상황에서 추후 자료 확보 경로로 전환했습니다.')
    if agreements.get('completion_path'):
        strengths.append(f"최종 미션을 '{agreements.get('completion_path')}' 경로로 완료했습니다.")
    if m.get('repeated_known_questions',0)>0:
        watch.append(f"이미 확인한 주제를 다시 묻는 흐름이 {m['repeated_known_questions']}회 감지되었습니다.")
    if m.get('repairs',0)>0:
        watch.append(f"대화 엔진이 의미를 확정하지 못해 복구가 필요했던 턴이 {m['repairs']}회 있었습니다. 해당 턴은 자동 오답으로 보지 않습니다.")
    if m.get('hostile_turns',0)>0:
        watch.append(f"고객이 공격적으로 받아들일 수 있는 표현 후보가 {m['hostile_turns']}회 있었습니다. 실제 문맥을 복기해 보세요.")
    if s.scenario_id=='C07-S01':
        pace=c07_pacing(s)
        if pace['status']=='too_fast':
            watch.append('최종 목표는 빠르게 달성했지만, 분석 방향을 잡기 위한 핵심 확인이 충분했는지 복기해 보세요.')
        elif pace['status']=='long':
            watch.append('상담이 길어졌습니다. 이미 확보한 정보를 반복하지 않았는지 확인해 보세요.')
        loops=c07_loop_diagnostics(s)
        if loops.get('repeated_customer_reply',0)>=3:
            watch.append('동일한 고객 답변이 반복된 구간이 감지되었습니다. 질문을 바꾸거나 다음 단계로 전환할 수 있었습니다.')
        if loops.get('stagnant_context_turns',0)>=4:
            watch.append('여러 턴 동안 상담 상태가 바뀌지 않은 구간이 있었습니다. 복구 경로 선택을 확인해 보세요.')
    if not strengths and s.turns:
        strengths.append('이번 회차의 강점은 아래 평가 근거와 결정적 순간을 중심으로 확인해 주세요.')
    return {'strengths':strengths,'watch':watch,'metrics':m}



def _learning_signals(s:Session) -> dict:
    state=getattr(s,'v5_state',None)
    missed=[];repeated=[];unresolved=[]
    if not state:return {'missed_signals':missed,'unnecessary_repetition':repeated,'unresolved_items':unresolved}
    # Event signals should be acknowledged later in the conversation. These are
    # descriptive coaching hints, not automatic point deductions.
    for ev in getattr(state,'event_log',[]):
        turn=int(ev.get('turn',0));eid=str(ev.get('event_id',''))
        later=[t for t in s.turns if t.number>turn]
        later_actions={a for t in later for a in getattr(t,'v5_actions',[])}
        if 'SPOUSE' in eid and not ({'ask_preference','ask_customer_concern'} & later_actions):
            missed.append({'turn':turn,'signal':'배우자 의견과 고객 자신의 유지 기준이 함께 등장했습니다.','note':'이후 대화에서 의사결정 관계나 고객 본인의 우선순위를 다시 확인하는 접근도 가능했습니다.'})
        if 'TIME' in eid and not any(('followup' in a or 'document_transfer' in a) for a in later_actions):
            missed.append({'turn':turn,'signal':'고객이 상담 가능 시간이 많지 않다고 밝혔습니다.','note':'핵심을 정리하거나 다음 확인 단계로 전환하는 선택지를 검토할 수 있었습니다.'})
    for t in s.turns:
        if 'repeated_known_question' in t.flags:
            repeated.append({'turn':t.number,'text':t.text,'note':'이미 확인한 정보와 겹치는 질문이 감지되었습니다.'})
    gate=completion_gate(s)
    labels={
        'premium':'전체 보험료 확인','contract':'부담 계약 확인','trigger':'보험료 부담 계기 확인','preference':'유지하고 싶은 조건 확인',
        'reduction_preference':'보험료 절감 기준 확인','analysis_handoff':'증권 상세 분석 합의','followup_confirmed':'다음 상담 일정 또는 후속 연락 시점 확정',
        'numeric_summary_confirmed':'확인 내용 요약','limitation_explained':'확인 범위·한계 설명','material_consent':'자료 확인 또는 전달 합의',
        'closure_confirmed':'다음 단계 또는 종료 합의','review_before_decision':'변경 전 자료 검토',
    }
    for key in gate.get('missing',[]):unresolved.append(labels.get(key,key))
    if state.top_pending():unresolved.append('고객의 마지막 질문 또는 선택 요청에 대한 응답')
    return {'missed_signals':missed,'unnecessary_repetition':repeated,'unresolved_items':list(dict.fromkeys(unresolved))}

def _mission_outcome(s:Session) -> dict:
    gate=completion_gate(s)
    if s.scenario_id!='C07-S01':
        return {
            'final_complete':bool(gate.get('complete')),
            'final_goal':gate.get('final_goal','상담 목표 완료'),
            'intermediate':[],
        }
    status=c07_goal_status(s)
    # The report shows every meaningful intermediate goal, not only the depth-
    # specific scoring subset. This makes it obvious why a mission can be
    # complete while the consultation quality still has omissions.
    return {
        'final_complete':bool(status.get('final_complete')),
        'final_goal':status.get('final_goal','다음 상담 일정 또는 후속 연락 시점 확정'),
        'intermediate':list(status.get('intermediate') or []),
        'followup_schedule':status.get('followup_schedule'),
        'completion_path':status.get('completion_path'),
        'note':'최종 목표 달성 여부와 상담 완성도 평가는 별개입니다. 중간 목표 일부가 누락되어도 구체적인 다음 상담 일정 또는 후속 연락 시점이 확정되면 미션은 종료됩니다.',
    }


def _evidence_gate(s: Session, contract: dict) -> str:
    if s.scenario_id != 'C07-S01' or contract['criterion_id'] != 'L2':
        return contract['full_evidence_gate']
    # Use only facts already disclosed in this round, never the hidden profile.
    known = []
    for fact in s.disclosed.values():
        label, value = str(fact.get('label', '')), str(fact.get('value', ''))
        if ('보험료' in label or '부담 계약' in label or '보험료' in value) and value:
            known.append(f'{label}: {value}')
    context = ' / '.join(known[:4])
    return ('이 회차에서 확인한 금액과 확실성을 정확하게 요약'
            + (f' · {context}' if context else ' · 아직 확인하지 않은 금액은 추정하지 않음'))


def report(s:Session) -> dict:
    spec=SCENARIOS[s.scenario_id]
    weights=CATEGORIES[s.scenario_id[0]]['rubric_weights']
    facts=dict(s.flags)
    for iid, nums in s.observed.items():facts['intent_'+iid]=nums[0]
    uncertain_turns=[t.number for t in s.turns if t.interpretation['status'] in ('needs_clarification','out_of_scope') or
                     t.interpretation['uncertainties'] or (t.interpretation['status']=='needs_review' and not t.interpretation['risk_candidates']) or 'summary_unresolved' in t.flags or 'engine_clarification' in t.flags]
    risk_turns=[t for t in s.turns if t.interpretation['risk_candidates']]
    rows=[]
    for contract in spec['pilot_evidence_contract']:
        cid=contract['criterion_id'];axis=CRITERIA[cid]['axis']
        groups=GATES[s.scenario_id][cid]
        done=[g for g in groups if all(f in facts for f in g)]
        evidence_nums=sorted({facts[f] for g in groups for f in g if f in facts})
        value=2 if len(done)==len(groups) else 1 if done else 0
        state={2:'full',1:'partial',0:'not_observed'}[value]
        reason='고객 반응까지 연결된 관찰 조건을 충족했습니다.' if value==2 else '일부 조건은 확인했지만 추가 확인이 필요합니다.' if value==1 else '이번 대화에서 필요한 행동 증거가 확인되지 않았습니다.'
        if cid in DOCUMENT_BLOCKS.get(s.scenario_id,set()):
            state='unresolved';value=None;reason='가상 근거 자료팩이 아직 검수되지 않아 내용의 정확성은 평가를 유보합니다.'
        elif uncertain_turns and value<2:
            state='unresolved';value=None;reason='미해석·내용 미검증 발화가 있어 미수행으로 확정하지 않았습니다.'
        if cid.startswith('F') and risk_turns:
            state='unresolved';value=None;reason='권고·확약·권한 경계에 관한 위험 후보를 검수해야 합니다. 정정해도 원래 기록은 남습니다.'
        # A01's source explicitly allows a respectful refusal path.
        if s.scenario_id=='A01-S01' and 'respectful_closure' in s.flags:
            if cid in ('Q1','N1','F2','X3') and not (cid=='F2' and risk_turns):
                state='full';value=2;reason='V1.1의 연락중단 존중 대체 경로를 이행했습니다.';evidence_nums=sorted(set(evidence_nums+[s.flags['respectful_closure']]))
            if cid=='L2':
                state='partial';value=1;reason='중단 의사는 수용했습니다. 재확인의 구체성은 대화 복기에서 확인합니다.'
        gate = _evidence_gate(s, contract)
        rows.append({'id':cid,'axis':axis,'name':CRITERIA[cid]['name'],'gate':gate,
                     'review_turns':uncertain_turns if state=='unresolved' else [],
                     'next_action':f'{gate}. 한 번에 한 가지 질문으로 확인하고 고객의 답변을 연결해 보세요.' if value != 2 else '',
                     'state':state,'value':value,'reason':reason,'turns':evidence_nums,
                     'evidence':[{'turn':t.number,'text':t.text,'customer':t.response_text} for t in s.turns if t.number in evidence_nums]})
    low=Decimal(0);high=Decimal(0);axes=[]
    for axis,weight in weights.items():
        ar=[r for r in rows if r['axis']==axis]
        if not ar:continue
        d=Decimal(2*len(ar));l=sum(r['value'] or 0 for r in ar);h=sum(2 if r['value'] is None else r['value'] for r in ar)
        low+=Decimal(weight)*Decimal(l)/d;high+=Decimal(weight)*Decimal(h)/d
        axes.append({'id':axis,'name':AXES[axis],'lower':round(l/float(d)*100,1),'upper':round(h/float(d)*100,1),'weight':weight})
    unresolved=sum(r['state']=='unresolved' for r in rows)
    lower=float(low.quantize(Decimal('.1'),rounding=ROUND_HALF_UP));upper=float(high.quantize(Decimal('.1'),rounding=ROUND_HALF_UP))
    mission=_mission_outcome(s)
    state='검토 필요' if unresolved or risk_turns else '기준 충족 · 잠정' if lower>=80 else '재연습 권장'
    if mission.get('final_complete'):
        state='미션 완료 · 검토 필요' if unresolved or risk_turns else ('미션 완료 · 기준 충족 · 잠정' if lower>=80 else '미션 완료 · 보완 필요')
    if not s.turns:lower=upper=None;state='평가할 대화 없음'
    if s.end_reason=='turn_limit':state='진행 한도 종료 · 복기 필요'
    achievements=[]
    if 'numeric_summary_confirmed' in s.flags:achievements.append({'title':'정확한 경청','note':'공개된 금액을 정확하게 요약했습니다.'})
    if 'trigger' in s.flags and 'preference' in s.flags:achievements.append({'title':'원인과 목표 구분','note':'부담 계기와 유지할 조건을 나눠 확인했습니다.'})
    if 'material_consent' in s.flags:achievements.append({'title':'동의를 구하는 상담','note':'자료 검토 또는 전달에 고객 동의를 받았습니다.'})
    if 'respectful_closure' in s.flags:achievements.append({'title':'선택권 존중','note':'고객이 요청한 연락 중단을 존중했습니다.'})
    learning=_learning_signals(s)
    return {'scenario_id':s.scenario_id,'mode':s.mode,'lower':lower,'upper':upper,'status':state,'rows':rows,'axes':axes,
            'unresolved':unresolved,'uncertain_turns':uncertain_turns,'risk_candidates':[{'turn':t.number,'text':t.text,'codes':t.interpretation['risk_candidates']} for t in risk_turns],
            'achievements':achievements,'end_reason':s.end_reason,'assist_used':bool(s.hint_turns or any(t.assist_used for t in s.turns)),
            'engine_repair_turns':[t.number for t in s.turns if 'engine_clarification' in t.flags],
            'v5_metrics':dict(getattr(s,'v5_state',None).metrics) if getattr(s,'v5_state',None) else {},
            'v5_flow':_v5_flow_summary(s),
            'conversation_contracts':list(getattr(s,'v5_state',None).conversation_contracts) if getattr(s,'v5_state',None) else [],
            'critical_moments':_critical_moments(s),
            'missed_signals':learning['missed_signals'],'unnecessary_repetition':learning['unnecessary_repetition'],'unresolved_items':learning['unresolved_items'],
            'scenario_seed':f'{s.seed:08X}','mission_outcome':mission,
            'session_pacing':c07_pacing(s) if s.scenario_id=='C07-S01' else None,
            'open_loops':c07_open_loops(s) if s.scenario_id=='C07-S01' else [],
            'loop_diagnostics':c07_loop_diagnostics(s) if s.scenario_id=='C07-S01' else {},
            'certificate':False,'notice':'규칙 기반 잠정 평가입니다. 친절함·감정·전문 판단 전체를 측정하거나 공식 인증을 발급하지 않습니다.'}
