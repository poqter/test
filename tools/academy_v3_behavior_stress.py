from __future__ import annotations
"""Offline behavior-pattern stress suite for the bounded Academy V3 dialogue engine.

Unlike academy_v3_stress.py (surface speaking styles), this suite changes the
conversation *habit/order*: document-first, recap-heavy, terse references,
topic switches, wrong recalls, off-topic recovery, repeat requests, etc.
It is deterministic test data, not a population study of real users.
"""
import json, sys
from pathlib import Path
from uuid import uuid4
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hwarang_academy.engine import start_session, commit

BAD=(
    '제가 잘 이해하지 못했어요',
    '말씀하신 뜻을 조금 더 구체적으로',
    '보험료를 확인하자는 말씀이신가요, 아니면 보장 내용을',
)


def say(s,text):
    return commit(s,uuid4().hex,text=text,expected_turn=len(s.turns)+1)


def no_repair(reply):
    return not any(x in reply for x in BAD)

# step: (utterance, expectation)
PATTERNS={
'01_linear_standard':[
 ('보험료는 한 달에 어느 정도 내세요?','total'),('어떤 보험이 제일 부담되세요?','burden'),
 ('요즘 특히 부담이 커진 이유가 있을까요?','trigger'),('그래도 꼭 유지하고 싶은 부분은요?','preference')],
'02_concern_first':[
 ('어느 부분이 가장 궁금하세요?','concern'),('그럼 전체 보험료부터 볼게요. 한 달에 얼마예요?','total'),
 ('어떤 계약이 가장 부담돼요?','burden')],
'03_document_first':[
 ('증권 있으세요?','document_available'),('열어봐주세요','document_open'),('거기 뭐 있어요?','items'),
 ('어떤 담보들이 있나요?','coverage')],
'04_terse_reference':[
 ('월보험료는요?','total'),('그중 제일 큰 건요?','burden'),('그건 왜 부담돼요?','trigger'),('유지할 건요?','preference')],
'05_wrong_recap_then_question':[
 ('전체 보험료 얼마예요?','total'),('30만원 내신다고 하셨는데 그중 어떤 보험이 제일 부담돼요?','correct_and_burden')],
'06_bundled_questions':[
 ('전체 보험료는 얼마고 어떤 계약이 가장 부담돼요?','total_and_burden'),
 ('부담이 커진 이유랑 그래도 유지하고 싶은 부분이 뭔지도 알려주세요','trigger_or_preference')],
'07_contract_inventory_first':[
 ('지금 보험 뭐뭐 있으세요?','contracts'),('그중 제일 부담되는 보험은요?','burden'),('증권도 가지고 계세요?','document_available')],
'08_document_method_after_unknown':[
 ('보장내용은 잘 모르시죠?','coverage_unknown'),('그럼 어떻게 확인하면 될까요?','document_method'),
 ('증권 있으시면 한번 열어볼까요?','document_open')],
'09_repeat_request':[
 ('전체 보험료는 얼마예요?','total'),('다시 말씀해 주세요','repeat_total'),('그중 큰 건요?','burden')],
'10_offtopic_recovery':[
 ('오늘 날씨 어때요?','offtopic'),('그럼 보험료는요?','total'),('어떤 보험이 제일 부담돼요?','burden')],
'11_document_restore':[
 ('증권 있으세요?','document_available'),('증권 열어주세요','document_open'),('어떤 항목들이 있나요?','items'),
 ('우리 지금 증권 보고 있는 중이었잖아요','restore')],
'12_prompt_continue':[
 ('증권 있으세요?','document_available'),('그럼 같이 보죠','document_open'),('아는 내용 말씀해주세요','items'),
 ('보이는 내용부터 말씀해 주세요','items')],
'13_casual_spoken':[
 ('보험으로 한달에 얼마 나가요?','total'),('뭐가 젤 부담돼요?','burden'),('왜 요즘 더 부담돼요?','trigger')],
'14_formal_register':[
 ('현재 월 보험료는 어느 정도 납입하고 계십니까?','total'),('그중 가장 부담이 큰 계약은 무엇입니까?','burden'),
 ('최근 부담이 증가하게 된 계기가 있으십니까?','trigger')],
'15_spacing_omitted':[
 ('월보험료얼마예요?','total'),('보험뭐뭐있으세요?','contracts'),('증권있으세요?','document_available')],
'16_light_typos':[
 ('보혐료 한달에 얼마 내세요?','total'),('무슨무슨 보험 유지하고 계시내요?','contracts'),
 ('실손 의로비는 얼마예요?','indemnity_unknown')],
'17_long_preface':[
 ('지금 말씀을 들어보면 보험료 때문에 부담이 있으신 것 같은데 제가 필요한 부분만 차근차근 보려고 합니다. 전체로 한 달에 얼마 정도 내고 계실까요?','total'),
 ('그 금액 가운데 특히 부담되는 계약이 무엇인지 먼저 확인해도 될까요?','burden')],
'18_recapped_fact_then_inventory':[
 ('전체 보험료가 얼마라고 하셨죠?','total'),('43만원 정도라고 하셨는데 지금 유지 중인 보험은 어떤 것들이에요?','contracts')],
'19_topic_switch_to_coverage':[
 ('전체 보험료는요?','total'),('보험료 말고 보장내용도 한번 보죠','coverage_unknown'),('증권 있으세요?','document_available'),
 ('열어봐주세요','document_open'),('담보 뭐가 보여요?','coverage')],
'20_document_premium_breakdown':[
 ('증권 있으세요?','document_available'),('열어봐주세요','document_open'),('보험별로 각각 얼마씩 나가요?','document_premiums')],
'21_anaphora_after_document':[
 ('증권 있으세요?','document_available'),('열어봐주세요','document_open'),('거기 있는 것부터 말해주세요','items'),('그럼 실손은 얼마예요?','indemnity_known')],
'22_recap_wrong_indemnity':[
 ('전체 보험료는 얼마예요?','total'),('30만원 중에 실손 의료비는 얼마예요?','correct_and_indemnity')],
'23_review_proposal_then_question':[
 ('가입한 보험부터 같이 확인해보죠','review'),('무슨무슨 보험 유지하고 계신 건가요?','contracts'),
 ('그중 어떤 게 가장 부담돼요?','burden')],
'24_zigzag_realistic':[
 ('안녕하세요. 보험료 많이 나가서 부담되셨겠어요','no_repair'),('어느 부분이 제일 궁금하세요?','concern'),
 ('한 달에 얼마 나가세요?','total'),('무슨무슨 보험 유지하고 계세요?','contracts'),
 ('증권은 어디에 보관하세요?','document_available'),('그럼 같이 볼까요?','document_open'),
 ('어떤 항목들이 있나요?','items'),('우리 지금 증권 보는 중이죠?','restore')],
}


def check(expect, reply, s, prev_reply=''):
    total=int(s.facts['total_monthly_premium_won']); total_man=str(total//10000)
    cname=str(s.facts['burdensome_contract'])
    items=[x['name'] for x in s.facts.get('policy_items',[])]
    doc_openable=s.facts.get('policy_document_status') in ('mobile','partial_mobile','file_available')
    if not no_repair(reply): return False,'generic_repair'
    if expect in ('no_repair','review'): return True,''
    if expect=='total': return (total_man in reply or f'{total:,}' in reply),'missing_total'
    if expect=='concern': return '보험료' in reply,'missing_concern'
    if expect=='burden': return cname in reply,'missing_burden'
    if expect=='trigger': return any(tok in reply for tok in str(s.facts['burden_trigger']).replace('·',' ').split() if len(tok)>=2),'missing_trigger'
    if expect=='preference': return any(x in reply for x in ('유지','남기','보장','부담')),'missing_preference'
    if expect=='contracts': return any(x in reply for x in items+[cname]),'missing_contracts'
    if expect=='document_available': return any(x in reply for x in ('증권','자료','휴대폰','배우자','파일')),'missing_document_status'
    if expect=='document_open': return ('document_opened' in s.flags or any(x in reply for x in ('열었','확인','자료'))),'document_not_open'
    if expect=='items': return ((any(x in reply for x in items)) if doc_openable else any(x in reply for x in ('배우자','자료','증권','정확'))),'missing_items'
    if expect=='coverage': return ((any(x in reply for x in ('증권 요약','보장','실손의료비','사망보장','질병'))) if doc_openable else any(x in reply for x in ('배우자','자료','증권','정확'))),'missing_coverage'
    if expect=='coverage_unknown': return any(x in reply for x in ('모르','증권','정확')),'coverage_unknown_failed'
    if expect=='document_method': return any(x in reply for x in ('증권','휴대폰','자료','앱','파일')),'missing_method'
    if expect=='repeat_total': return (total_man in reply or reply==prev_reply),'repeat_failed'
    if expect=='offtopic': return '보험료' in reply,'offtopic_not_redirected'
    if expect=='restore': return '증권' in reply,'restore_failed'
    if expect=='total_and_burden': return (total_man in reply and cname in reply),'multi_intent_failed'
    if expect=='trigger_or_preference': return any(x in reply for x in ('부담','대출','소득','교육비','갱신','유지','보장')),'compound_followup_failed'
    if expect=='correct_and_burden': return (total_man in reply and cname in reply),'wrong_recap_not_repaired'
    if expect=='indemnity_unknown': return ('실손' in reply and any(x in reply for x in ('기억','증권','정확'))),'indemnity_unknown_failed'
    if expect=='document_premiums': return any(str(int(x['premium_won'])//10000) in reply or x['name'] in reply for x in s.facts.get('policy_items',[])),'premium_breakdown_failed'
    if expect=='indemnity_known': return (('실손' in reply and any(x in reply for x in ('만원','원'))) if doc_openable else ('실손' in reply and any(x in reply for x in ('기억','증권','정확')))),'indemnity_known_failed'
    if expect=='correct_and_indemnity': return (total_man in reply and '실손' in reply),'wrong_recap_indemnity_failed'
    return True,''


def run():
    failures=[]; total_turns=0; by_kind=Counter(); sessions=0
    profiles=[[],['C07-BASE','C07-FAMILY','C07-RENEWAL'],['C07-BASE','C07-CASHFLOW','C07-RENEWAL'],['C07-BASE','C07-CASHFLOW','C07-FAMILY']]
    for pidx,avoid in enumerate(profiles,1):
        for name,steps in PATTERNS.items():
            s=start_session('C07-S01','SOLO',seed=pidx,session_length='DEEP',vary_profile=True,avoid_profiles=avoid)
            sessions+=1; prev=''
            for turn,(text,expect) in enumerate(steps,1):
                out=say(s,text); total_turns+=1
                ok,kind=check(expect,out.response_text,s,prev)
                if not ok:
                    failures.append({'pattern':name,'profile':s.profile_id,'turn':turn,'text':text,'reply':out.response_text,'expect':expect,'kind':kind})
                    by_kind[kind]+=1
                prev=out.response_text
                if s.ended: break
    result={
        'conversation_habit_patterns':len(PATTERNS),
        'customer_profiles_exercised':4,
        'sessions':sessions,
        'turns':total_turns,
        'failures':len(failures),
        'failure_rate':round(len(failures)/max(1,total_turns),6),
        'failure_kinds':dict(by_kind),
        'failure_samples':failures[:50],
    }
    outdir=ROOT/'artifacts'/'academy_v3_behavior_stress';outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='failure_samples'},ensure_ascii=False,indent=2))
    if failures:
        print(json.dumps(failures[:20],ensure_ascii=False,indent=2))
    return 0 if not failures else 1

if __name__=='__main__': raise SystemExit(run())
