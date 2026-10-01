from __future__ import annotations
import json, sys, re
from pathlib import Path
from uuid import uuid4
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hwarang_academy.engine import start_session, commit

FLOWS=json.loads((ROOT/'hwarang_academy/tests/fixtures/conversations.json').read_text(encoding='utf-8'))['flows']

PREFIXES=['','그럼 ','음, ','혹시 괜찮으시면 ','제가 이해한 게 맞다면 ']
SPACING=['normal','light','compressed']
PUNCT=['keep','drop']
TYPO=['none','domain']

# Deterministic 60 style combinations; 48 are used by default.
def styles(limit=48):
    out=[];n=0
    for p in PREFIXES:
      for sp in SPACING:
       for pu in PUNCT:
        for ty in TYPO:
         n+=1;out.append((f'XADV-{n:03d}',p,sp,pu,ty))
    return out[:limit]

FIX=[('보험료','보혐료'),('증권','증권'),('배우자','배우자'),('보험금','보험금'),('지분','지분'),('자료','자료')]

def transform(text, style, turn):
    _,prefix,spacing,punct,typo=style
    t=prefix+text
    if spacing=='light':
        for a,b in [('한 달','한달'),('다시 연락','다시연락'),('현재 자료','현재자료'),('가족과 함께','가족과함께')]: t=t.replace(a,b)
    elif spacing=='compressed':
        # preserve sentence boundaries but remove common optional spaces
        for a,b in [('한 달','한달'),('보험료는','보험료는'),('증권을 ','증권을'),('자료를 ','자료를'),('지금 ','지금'),('현재 ','현재'),('다시 ','다시')]: t=t.replace(a,b)
    if typo=='domain':
        # only use fixups the runtime normalizer intentionally supports.
        for a,b in [('보험료','보혐료'),('의료비','의로비'),('함께','함꼐')]:
            if (turn+len(t))%3==0 and a in t: t=t.replace(a,b,1);break
    if punct=='drop': t=t.rstrip('?.!')
    return t

def bad(rep):
    return any(x in rep for x in ['제가 잘 이해하지 못했어요','말씀하신 뜻을 조금 더 구체적으로','ENGINE','연결하지 못했습니다'])

def run():
    failures=[];counts=Counter();turns=0
    for sid,flow in FLOWS.items():
      for style in styles():
        s=start_session(sid,'SOLO',seed=7,session_length='DEEP',vary_profile=False)
        digest=s.fact_digest
        for turn,text in enumerate(flow,1):
            if s.ended: break
            utter=transform(text,style,turn)
            out=commit(s,uuid4().hex,text=utter,expected_turn=len(s.turns)+1);turns+=1
            if bad(out.response_text):
                failures.append({'scenario':sid,'style':style[0],'turn':turn,'text':utter,'response':out.response_text,'kind':'generic_repair'});counts[(sid,'generic_repair')]+=1
        if not s.ended:
            failures.append({'scenario':sid,'style':style[0],'turn':len(s.turns),'text':'<flow end>','response':'','kind':'not_ended','flags':list(s.flags)});counts[(sid,'not_ended')]+=1
        if s.fact_digest!=digest:
            failures.append({'scenario':sid,'style':style[0],'turn':0,'text':'<fact digest>','response':'','kind':'fact_mutated'});counts[(sid,'fact_mutated')]+=1
    result={'styles':len(styles()),'scenarios':len(FLOWS),'sessions':len(styles())*len(FLOWS),'turns':turns,'failures':len(failures),'failure_rate':round(len(failures)/max(1,turns),6),'by_scenario_kind':{f'{a}:{b}':n for (a,b),n in counts.items()},'samples':failures[:80]}
    outdir=ROOT/'artifacts'/'academy_v3_cross_stress';outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='samples'},ensure_ascii=False,indent=2))
    return 0 if not failures else 1

if __name__=='__main__': raise SystemExit(run())
