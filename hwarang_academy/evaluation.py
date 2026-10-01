"""Evidence-based provisional rubric: no certification and no emotion diagnosis."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from .content import SCENARIOS, CRITERIA, CATEGORIES, AXES
from .engine import Session

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
        rows.append({'id':cid,'axis':axis,'name':CRITERIA[cid]['name'],'gate':contract['full_evidence_gate'],
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
    state='검토 필요' if unresolved or risk_turns else '기준 충족 · 잠정' if lower>=80 else '재연습 권장'
    if not s.turns:lower=upper=None;state='평가할 대화 없음'
    if s.end_reason=='turn_limit':state='진행 한도 종료 · 복기 필요'
    achievements=[]
    if 'numeric_summary_confirmed' in s.flags:achievements.append({'title':'정확한 경청','note':'공개된 금액을 정확하게 요약했습니다.'})
    if 'trigger' in s.flags and 'preference' in s.flags:achievements.append({'title':'원인과 목표 구분','note':'부담 계기와 유지할 조건을 나눠 확인했습니다.'})
    if 'material_consent' in s.flags:achievements.append({'title':'동의를 구하는 상담','note':'자료 검토 또는 전달에 고객 동의를 받았습니다.'})
    if 'respectful_closure' in s.flags:achievements.append({'title':'선택권 존중','note':'고객이 요청한 연락 중단을 존중했습니다.'})
    return {'scenario_id':s.scenario_id,'mode':s.mode,'lower':lower,'upper':upper,'status':state,'rows':rows,'axes':axes,
            'unresolved':unresolved,'uncertain_turns':uncertain_turns,'risk_candidates':[{'turn':t.number,'text':t.text,'codes':t.interpretation['risk_candidates']} for t in risk_turns],
            'achievements':achievements,'end_reason':s.end_reason,'assist_used':bool(s.hint_turns or any(t.assist_used for t in s.turns)),
            'engine_repair_turns':[t.number for t in s.turns if 'engine_clarification' in t.flags],
            'certificate':False,'notice':'규칙 기반 잠정 평가입니다. 친절함·감정·전문 판단 전체를 측정하거나 공식 인증을 발급하지 않습니다.'}
