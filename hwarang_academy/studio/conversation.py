"""Conservative local dialogue safeguards; never infer training quality from closure."""
import re
from copy import deepcopy

# Match explicit first-person service promises, not a customer's request for help.
ROLE_DRIFT = re.compile(r'(?:점검|상담|분석|조율|안내|설계|추천|설명)(?:해\s*|을\s*)?(?:드리겠습니다|드릴게요|드릴까요|해드리겠습니다)|고객님|아내분|남편분|부담을\s*느끼시는|상의하실\s*때\s*중요|중요하게\s*생각하시는')
NEGATIVE = re.compile(r'어렵|안\s*돼|안\s*되|불가능|못\s*가|모르|미정|확인해\s*봐|확인해봐|확인한\s*뒤|확인\s*후|나중에|다른\s*(?:날|시간)|바꿔|변경|아직|보류|괜찮을까요|가능할까요')
DAY = re.compile(r'(?:이번\s*주|다음\s*주|다다음\s*주)?\s*[월화수목금토일]요일|오늘|내일|모레|\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}[./-]\d{1,2}')
TIME = re.compile(r'(?:오전|오후|저녁|아침|점심|밤)\s*(?:\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?)?|\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?|\d{1,2}:\d{2}')
ACCEPT = re.compile(r'^(?:네|예|좋아요|좋습니다|알겠습니다|알겠어요|괜찮아요)|뵐게요|뵙겠습니다|가능합니다|가능해요|참석할게요|그때\s*(?:갈게요|가겠습니다)')
CLOSE = re.compile(r'(?:오늘\s*)?(?:상담|통화|대화)(?:은|는|을|를)?\s*(?:여기(?:까지|서)|이렇게)?\s*(?:마치(?:겠습니다|도록\s*하겠습니다|죠)|마무리(?:하겠습니다|할게요|하죠)|종료(?:하겠습니다|할게요)|끝내(?:겠습니다|죠))[.!\s]*$|(?:오늘은|오늘\s*상담은)\s*여기까지\s*(?:입니다|하겠습니다|할게요|요)?[.!\s]*$')

def explicit_close(text):
    # Quoted examples, questions and mixed "before ending, tell me ..." are not a command.
    if any(c in text for c in ('?', '？', '"', '“', '”', '「', '」')):return False
    if re.search(r'전에|말씀해|알려주|여쭤|질문|예시|라고|않|아니|말고|나중에',text):return False
    return bool(CLOSE.search(text))

def agreed_schedule(s,text,reply):
    if s['stage'] not in ('TA','FIRST') or NEGATIVE.search(reply) or not ACCEPT.search(reply):return None
    # Evidence is bounded to the immediate exchange: an old rejected date is never resurrected.
    advisors=[m['text'] for m in s['messages'] if m['role']=='advisor' and m.get('stage')==s['stage']]
    candidate=text
    if not DAY.search(candidate) and TIME.search(candidate) and advisors:
        last_customer=next((m['text'] for m in reversed(s['messages']) if m['role']=='customer'),'')
        if ACCEPT.search(last_customer) and not NEGATIVE.search(last_customer):candidate=advisors[-1]+' '+text
    # A customer counterproposal is not mutual agreement; date/time must come from advisor evidence.
    if not DAY.search(candidate) or not TIME.search(candidate):return None
    if NEGATIVE.search(text) and not re.search(r'괜찮을까요|가능할까요',text):return None
    day=DAY.search(candidate).group().strip();time=TIME.search(text) or TIME.search(candidate)
    # If reply proposes a different explicit date/time, wait for advisor agreement.
    rd=DAY.search(reply);rt=TIME.search(reply)
    norm=lambda x:re.sub(r'\s','',x)
    if rd and norm(rd.group())!=norm(day):return None
    if rt and norm(rt.group())!=norm(time.group()):return None
    return {'label':day+' '+time.group().strip(),'advisor_quote':text,'customer_quote':reply}

def guard_response(s,text,result):
    out=deepcopy(result)
    if ROLE_DRIFT.search(out['reply']):
        # Preserve no suspect customer claim. No extra billable repair request is made.
        if re.search(r'보장분석|점검|확인해|확인하|설명드',text):reply='네, 제 보험 내역을 확인해 주세요.'
        elif DAY.search(text) or TIME.search(text):reply='일정을 다시 한번 말씀해 주시겠어요?'
        else:reply='제가 잘 이해하지 못했어요. 조금 쉽게 말씀해 주시겠어요?'
        out.update(reply=reply,outcome='continue',relevance='uncertain',confidence=0,
                   reason='고객 역할 이탈 응답을 보호 처리함. 학습자 오류가 아님.',confirm_streak=False,
                   trust_delta=0,concern=s['customer_state']['concern'],disclosed_keys=[])
        out['_guarded']=True
    schedule=agreed_schedule(s,text,out['reply'])
    if schedule:out['outcome']='goal';out['_schedule']=schedule
    return out

def closing_result():
    return dict(reply='네, 오늘 시간 내주셔서 감사합니다.',relevance='ontrack',confidence=1,
                reason='설계사의 명시적인 상담 종료',confirm_streak=False,trust_delta=0,concern='',
                disclosed_keys=[],outcome='advisor_exit')
