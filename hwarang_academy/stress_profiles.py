"""Synthetic advisor speech styles used only for offline Academy stress tests.

These profiles are not learner personas and are not used to score users.  They
exercise spacing, fillers, shorthand, indirectness, typos and conversational
habits so the deterministic engine is tested against more than hand-picked lines.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product

@dataclass(frozen=True)
class AdvisorStyle:
    style_id: str
    register: str
    spacing: str
    filler: str
    typo: str
    habit: str

REGISTERS=("standard","spoken","terse")
SPACING=("normal","compressed")
FILLERS=("none","soft")
TYPOS=("none","light")
HABITS=("direct","preface")


def build_styles(limit: int=72) -> list[AdvisorStyle]:
    out=[]
    for idx,(r,s,f,t,h) in enumerate(product(REGISTERS,SPACING,FILLERS,TYPOS,HABITS),1):
        out.append(AdvisorStyle(f"ADV-{idx:03d}",r,s,f,t,h))
    # 3*2*2*2*2 = 48. Add 24 explicit conversational habits.
    extra=[
      ("fragment","normal","none","none","direct"),
      ("fragment","compressed","none","light","direct"),
      ("verbose","normal","soft","none","preface"),
      ("verbose","normal","none","light","direct"),
      ("indirect","normal","soft","none","preface"),
      ("indirect","compressed","none","light","direct"),
    ]
    base=len(out)
    for k in range(24):
        r,s,f,t,h=extra[k%len(extra)]
        out.append(AdvisorStyle(f"ADV-{base+k+1:03d}",r,s,f,t,h))
    return out[:limit]

BASE_UTTERANCES={
 "greet_empathy":[
   "안녕하세요. 보험료가 많이 나가서 부담되셨겠어요. 같이 확인해볼까요?",
   "안녕하세요, 요즘 보험료 때문에 고민이 있으셨겠네요. 하나씩 볼까요?",
   "보험료 부담이 있으셨군요. 먼저 상황부터 같이 확인해보겠습니다.",
 ],
 "ask_customer_concern":[
   "어느 부분이 가장 궁금하세요?",
   "지금 제일 신경 쓰이는 부분이 어떤 건가요?",
   "어떤 점이 가장 고민되시는지 말씀해주실래요?",
 ],
 "ask_total":[
   "보험료는 한 달에 어느 정도 납입하고 계실까요?",
   "전체 보험료가 매달 얼마 정도 나가세요?",
   "보험으로 한 달에 얼마씩 나가고 계세요?",
   "월보험료는요?",
 ],
 "ask_contract_list":[
   "어떤 보험들을 유지하고 계신가요?",
   "지금 가입한 보험이 뭐뭐 있으세요?",
   "무슨무슨 보험 들고 계신 건가요?",
   "보험 종류가 어떻게 되세요?",
 ],
 "ask_burden_contract":[
   "그중 어떤 보험이 제일 부담되세요?",
   "가장 많이 나가는 계약이 어떤 건가요?",
   "특히 부담되는 보험이 있으세요?",
 ],
 "ask_document_possession":[
   "증권 가지고 계신가요?",
   "보험증권이나 계약자료가 있으실까요?",
   "가입내역 확인할 자료는 가지고 있으세요?",
 ],
 "request_document_check":[
   "그럼 증권을 같이 확인해볼까요?",
   "자료 한번 열어서 확인해주세요.",
   "보험증권 지금 볼 수 있으면 같이 보시죠.",
 ],
 "ask_document_items":[
   "어떤 항목들이 있나요?",
   "증권에 어떤 보험들이 보이나요?",
   "무슨 담보들이 있는지 말씀해주시겠어요?",
   "거기 뭐가 있어요?",
 ],
 "ask_trigger":[
   "최근에 보험료가 더 부담스럽게 느껴진 계기가 있을까요?",
   "왜 요즘 특히 부담된다고 느끼셨어요?",
   "부담이 커진 이유가 따로 있으세요?",
 ],
 "ask_preference":[
   "줄이더라도 꼭 유지하고 싶은 보장이나 조건이 있으세요?",
   "어떤 건 유지하고 싶으세요?",
   "보험료를 조정해도 남기고 싶은 부분이 있을까요?",
 ],
 "restore_document":[
   "우리 지금 증권 보고 있는 중이었잖아요.",
   "아까 증권 열어서 보고 있었죠?",
   "지금 자료 보고 있는 거 맞죠. 거기 있는 내용부터 볼게요.",
 ],
 "prompt_continue":[
   "아는 내용 말씀해주세요.",
   "보이는 내용부터 말씀해 주세요.",
   "그럼 거기 나온 것부터 얘기해주세요.",
 ],
}


def _register(text: str, register: str) -> str:
    if register=="spoken":
        return text.replace("계실까요","계세요").replace("있으실까요","있으세요").replace("말씀해주시겠어요","말씀해 주세요")
    if register=="terse":
        swaps={
          "보험료는 한 달에 어느 정도 납입하고 계실까요?":"한 달 보험료는요?",
          "전체 보험료가 매달 얼마 정도 나가세요?":"총 보험료 얼마예요?",
          "어떤 보험들을 유지하고 계신가요?":"보험 뭐뭐 있으세요?",
          "그중 어떤 보험이 제일 부담되세요?":"제일 부담되는 보험은요?",
          "증권 가지고 계신가요?":"증권 있으세요?",
          "그럼 증권을 같이 확인해볼까요?":"증권 볼까요?",
          "어떤 항목들이 있나요?":"항목은요?",
          "왜 요즘 특히 부담된다고 느끼셨어요?":"왜 더 부담돼요?",
          "어떤 건 유지하고 싶으세요?":"유지할 건요?",
        }
        return swaps.get(text,text)
    if register=="fragment":
        return text.replace("보험료는 한 달에 어느 정도 납입하고 계실까요?","보험료 어느정도요?").replace("어떤 항목들이 있나요?","항목 뭐뭐요?").replace("어떤 보험들을 유지하고 계신가요?","보험 뭐 있으세요?")
    if register=="verbose":
        return "지금 말씀 들어보면 " + text + " 제가 필요한 부분만 차근차근 보려고 합니다."
    if register=="indirect":
        return "혹시 괜찮으시면 " + text
    return text


def apply_style(text: str, style: AdvisorStyle, turn: int) -> str:
    t=_register(text,style.register)
    if style.habit=="preface" and turn%3==0 and not t.startswith("혹시"):
        t="그럼 " + t
    if style.filler=="soft" and turn%4==1:
        t="음, " + t
    if style.typo=="light":
        # Deliberately small, realistic keyboard slips already covered or expected
        # to be robust to context.
        replacements=[("함께","함꼐"),("의료비","의로비"),("보험료","보혐료"),("계시나요","계시내요")]
        bad,good=replacements[turn%len(replacements)]
        t=t.replace(bad,good,1)
    if style.spacing=="compressed" and turn%2==0:
        # Remove only some spaces so tokens remain recoverable by the Korean parser.
        for phrase in ("보험료 ","증권 ","어떤 ","한 달 ","같이 ","보고 있는 "):
            t=t.replace(phrase,phrase.replace(" ",""),1)
    return t
