from __future__ import annotations
import json, sys
from pathlib import Path
from uuid import uuid4
from collections import Counter, defaultdict
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hwarang_academy.engine import start_session, commit
from hwarang_academy.stress_profiles import build_styles, BASE_UTTERANCES, apply_style


def say(s,text):
    return commit(s,uuid4().hex,text=text,expected_turn=len(s.turns)+1)


def pick(key,idx):
    vals=BASE_UTTERANCES[key]
    return vals[idx%len(vals)]


def bad_reply(text: str) -> bool:
    return any(x in text for x in [
        '제가 잘 이해하지 못했어요','말씀하신 뜻을 조금 더 구체적으로','보험료를 확인하자는 말씀이신가요, 아니면 보장 내용을',
    ])


def scenario(style, customer_seed):
    s=start_session('C07-S01','SOLO',seed=customer_seed,session_length='DEEP',vary_profile=True)
    cname=str(s.facts['burdensome_contract'])
    trigger=str(s.facts['burden_trigger'])
    seq=[
      ('greet_empathy',None),('ask_customer_concern','concern'),('ask_total','total'),
      ('ask_contract_list','contracts'),('ask_burden_contract','burden_contract'),
      ('ask_document_possession','document'),('request_document_check','document_open'),
      ('ask_document_items','document_items'),('restore_document','restore'),('prompt_continue','continue'),
      ('ask_trigger','trigger'),('ask_preference','preference')]
    failures=[]; replies=[]
    for turn,(key,expect) in enumerate(seq,1):
        text=apply_style(pick(key,turn+customer_seed),style,turn)
        out=say(s,text); rep=out.response_text; replies.append((text,rep))
        if bad_reply(rep): failures.append((turn,key,'generic_repair',text,rep))
        if expect=='total':
            val=s.facts['total_monthly_premium_won']//10000
            if str(val) not in rep and f"{s.facts['total_monthly_premium_won']:,}" not in rep: failures.append((turn,key,'missing_total',text,rep))
        elif expect=='contracts':
            if cname not in rep and not any(x['name'] in rep for x in s.facts.get('policy_items',[])): failures.append((turn,key,'missing_contract',text,rep))
        elif expect=='burden_contract' and cname not in rep: failures.append((turn,key,'missing_burden_contract',text,rep))
        elif expect=='document_open' and _can_open(s) and 'document_opened' not in s.flags: failures.append((turn,key,'document_not_open',text,rep))
        elif expect=='document_items' and _can_open(s):
            if not any(x['name'] in rep for x in s.facts.get('policy_items',[])): failures.append((turn,key,'missing_document_items',text,rep))
        elif expect=='restore' and _can_open(s) and bad_reply(rep): failures.append((turn,key,'restore_failed',text,rep))
        elif expect=='trigger':
            tokens=[x for x in trigger.replace('·',' ').split() if len(x)>=2]
            if not any(x in rep for x in tokens): failures.append((turn,key,'missing_trigger',text,rep))
        elif expect=='preference' and not any(x in rep for x in ['유지','남기','보장','부담']): failures.append((turn,key,'missing_preference',text,rep))
        if s.ended: break
    return s,failures,replies


def _can_open(s):
    return s.facts.get('policy_document_status') in ('mobile','partial_mobile','file_available')


def edge_cases():
    cases=[]
    # Each case is (name, prefix turns, test turn, expected fragment OR callable token set)
    cases.append(('wrong_total_plus_indemnity',['전체 보험료 얼마예요?'],'30만원 중에 실손 의료비는 얼마예요?',['43만원','실손']))
    cases.append(('document_generic_items',['증권 있으세요?','그럼 증권 열어봐주세요'],'어떤 항목들이 있나요?',['보험']))
    cases.append(('document_context_restore',['증권 있으세요?','증권 열어봐주세요'],'우리 지금 증권 보고 있었잖아요',['증권']))
    cases.append(('customer_concern',[],'어느 부분이 제일 궁금하세요?',['보험료']))
    cases.append(('contract_inventory',[],'무슨무슨 보험 유지하고 계신건가요?',['보험']))
    cases.append(('contract_inventory_terse',[],'보험 뭐뭐 있으세요?',['보험']))
    cases.append(('document_continue',['증권 있으세요?','증권 열어주세요'],'아는 내용 말씀해주세요',['보험']))
    cases.append(('short_premium',[],'월보험료는요?',['만원']))
    cases.append(('reference',['전체 보험료는요?'],'그중 제일 큰 건요?',['보험']))
    cases.append(('typo',[],'보혐료 한달에 얼마 내세요?',['만원']))
    return cases


def run():
    styles=build_styles(72)
    total_turns=0; failures=[]; by_kind=Counter(); by_style=Counter(); samples=[]
    for i,style in enumerate(styles):
        # Exercise all four controlled C07 customer profiles across styles.
        for seed in range(1,5):
            s,fs,replies=scenario(style,seed+i*7)
            total_turns+=len(replies)
            for f in fs:
                failures.append({'style':style.style_id,'seed':seed+i*7,'failure':f})
                by_kind[f[2]]+=1;by_style[style.style_id]+=1
            if fs and len(samples)<20:samples.append({'style':style.__dict__,'failures':fs,'replies':replies})
    edge_fail=[]
    for idx,(name,prefix,test,expects) in enumerate(edge_cases(),1):
        s=start_session('C07-S01','SOLO',seed=1,session_length='DEEP',vary_profile=True,avoid_profiles=['C07-CASHFLOW','C07-FAMILY','C07-RENEWAL'])
        for x in prefix:say(s,x)
        out=say(s,test)
        if bad_reply(out.response_text) or not all(x in out.response_text for x in expects):
            edge_fail.append({'name':name,'text':test,'response':out.response_text,'expected':expects})
    result={
      'virtual_advisor_styles':len(styles),
      'sessions':len(styles)*4,
      'turns':total_turns,
      'failures':len(failures),
      'failure_rate':round(len(failures)/max(1,total_turns),6),
      'failure_kinds':dict(by_kind),
      'styles_with_failures':len(by_style),
      'edge_cases':len(edge_cases()),
      'edge_failures':edge_fail,
      'failure_samples':samples,
    }
    outdir=ROOT/'artifacts'/'academy_v3_stress';outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('failure_samples',)},ensure_ascii=False,indent=2))
    return 0 if not failures and not edge_fail else 1

if __name__=='__main__':raise SystemExit(run())
