"""Conservative Korean rule recognizer. Scores are rule matches, NOT probabilities.

The approved positive examples are development vocabulary, not a held-out benchmark.
Only verb+topic patterns are accepted outside those examples. Unsupported semantic
claims are marked for review. Customer facts are never written from learner text.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import re
import unicodedata
from .content import INTENTS

MAX_CHARS = 2400

def norm(t: str) -> str:
    return re.sub(r'[\s.,!?·…“”"\'‘’]', '', unicodedata.normalize('NFC', t)).lower()

# Frequent keyboard/phonetic slips observed in natural Korean counseling input.
# Replacements are deliberately conservative and preserve the original text in
# logs/evidence; they are used only by the rule matcher.
_RULE_FIXUPS = {
    '함꼐':'함께', '의로비':'의료비', '보혐료':'보험료', '보헙료':'보험료',
    '실손의로비':'실손의료비', '증권확안':'증권확인', '보장내욘':'보장내용',
}
def rule_text(t: str) -> str:
    t=unicodedata.normalize('NFC',t)
    for bad,good in _RULE_FIXUPS.items(): t=t.replace(bad,good)
    return t

@dataclass
class Hit:
    intent_id: str
    start: int
    end: int
    evidence: str
    rule: str

@dataclass
class Interpretation:
    text: str
    hits: list[Hit] = field(default_factory=list)
    risk_candidates: list[str] = field(default_factory=list)
    quoted: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    status: str = 'needs_clarification'
    control: str | None = None
    # Conversation management is not scored as a question or a verified fact.
    dialogue_acts: list[str] = field(default_factory=list)
    context_turn: int | None = None
    entities: dict[str, list[str]] = field(default_factory=dict)
    @property
    def ids(self) -> set[str]:
        return {h.intent_id for h in self.hits}
    def to_dict(self) -> dict:
        return asdict(self)

# Every accepted alternative below is newly authored implementation logic, not a
# claim of wording or approval in the company training materials.
# Matching a noun alone is intentionally not sufficient.
PATTERNS: dict[str, tuple[str, ...]] = {
 'CT01': (r'(?:화랑|저는|이번).{0,25}(?:상담사|담당자|담당하는).{0,20}(?:입니다|해드|도와|하겠)',),
 'CT02': (r'소개로\s*연락드린',r'(?:소개|문의).{0,24}(?:받|전달|남겨).{0,24}(?:연락|전화)',),
 'CT03': (r'(?:지금|잠깐).{0,16}(?:통화|대화|상담).{0,20}(?:괜찮|가능|나눠|해도)',),
 'CT04': (r'(?:몇\s*분|어느\s*정도|마치셔야).{0,16}(?:괜찮|시간|가능|언제)', r'(?:오늘|지금).{0,10}시간.{0,12}(?:되세|있으세)'),
 'CT05': (r'(?:기존|가입|보장|계약).{0,30}(?:확인|검토|관리).{0,20}(?:위해|하려|목적|연락|전화)',),
 'CT06': (r'(?:어떻게\s*지내|그동안.{0,10}지내|생활에.{0,15}달라진)',),
 'CT08': (r'(?:회사|공식).{0,12}(?:문의|연락처|경로).{0,20}(?:확인|안내)',),
 'CT10': (r'(?:다시|추가|후속|다음\s*주|확인한\s*뒤).{0,18}연락.{0,16}(?:될까|될까요|괜찮|드려도)',),
 'RL01': (r'(?:부담|걱정|답답|불편|불안).{0,15}(?:되시|스러우|되셨|이시|겠|군요)', r'(?:마음|기분|걱정|부담).{0,15}(?:이해|공감)'),
 'RL02': (r'(?:살펴|진행|확인하는\s*순서).{0,20}(?:괜찮|될까|해도)',),
 'RL04': (r'(?:결정|가입|답변|대답).{0,15}(?:않으셔도|안\s*하셔도|미루셔도|넘어가셔도)',r'(?:원치|부담).{0,20}(?:생략|넘어|않|거절)'),
 'RL05': (r'(?:기존|이전).{0,12}(?:담당|관계|장점).{0,20}(?:존중|함께|확인)',),
 'RL06': (r'(?:보려고|위해|비교하려면).{0,30}(?:여쭙|필요|증권|자료)',r'(?:자료|증권|정보).{0,25}(?:필요한\s*이유|필요합니다|필요해요)'),
 'RL07': (r'(?:정확한.{0,10}대신|편하신\s*범위|확인된\s*내용만).{0,25}(?:말씀|정리|가능)',),
 'RL08': (r'(?:궁금한|다르게\s*이해|틀린).{0,25}(?:말씀|고쳐|질문)',),
 'RL10': (r'(?:연락|진행).{0,15}(?:않겠|안\s*하겠)',r'(?:뜻|의사|보류|선택|결정).{0,15}존중',r'(?:중단|원치).{0,25}(?:이해|마치)'),
 'DS01': (r'원하시는\s*검토.{0,20}(?:있는지|여쭙)',r'(?:어떤|무엇|뭐).{0,20}(?:상담.{0,8}신청|확인하고\s*싶)',r'상담.{0,14}(?:신청.{0,8}(?:이유|계기)|받으시.{0,6}이유)'),
 'DS02': (r'(?:원하|희망하|지키고\s*싶|정리되면\s*좋).{0,15}(?:결과|것|부분|점|목표).{0,15}(?:무엇|뭐|있|어떤)',r'(?:가장|이번\s*상담).{0,35}(?:원하시는|지키고|정리되면)'),
 'DS03': (r'(?:꼭|계속).{0,8}(?:유지|남기|지키).{0,20}(?:조건|보장|부분|것).{0,10}(?:있|무엇|뭐|어떤)',r'(?:절감|절약).{0,12}(?:유지|보장).{0,25}(?:어떤|무엇|먼저|우선)',r'어떤\s*점.{0,12}먼저\s*살펴'),
 'DS04': (r'(?:가족|부양).{0,18}(?:구성|계신|합의|동의).{0,18}(?:있|어떤|누구|알려|여쭤|여쭙|되)',),
 'DS05': (r'(?:어떤\s*일|직업).{0,20}(?:하시|수입|무엇|뭐)',),
 'DS06': (r'(?:월\s*수입|소득|월급).{0,20}(?:얼마|범위|어느\s*정도|변동)',),
 'DS07': (r'(?:생활비|지출|고정지출).{0,22}(?:얼마|어느|변화|늘어난|달라진).{0,15}(?:있|인가|일까|나|세요|까요)',),
 'DS08': (r'(?:대출|잔액|상환|갚는).{0,24}(?:얼마|어느\s*정도|어떤|알려|나눠|확인해도)',),
 'DS09': (r'(?:자산|자금).{0,25}(?:바로|실제로|가용|다른\s*목적).{0,30}(?:얼마|가능|사용|있)',),
 'DS13': (r'(?:전체|총|한\s*달|매달|월).{0,12}보험료.{0,24}(?:얼마|어느\s*정도|알고|내시|나가|납부)',r'보험료.{0,14}(?:총액|얼마|어느\s*정도).{0,16}(?:나요|세요|까요|인지|알)',r'(?:달마다|매달).{0,15}(?:보험에|보험으로).{0,10}얼마'),
 'DS14': (r'(?:어떤|어느|무슨).{0,12}(?:보험|계약).{0,24}(?:부담|먼저\s*살펴)',r'(?:가장|제일).{0,12}부담.{0,18}(?:보험|계약|건)',r'부담.{0,12}(?:보험|계약).{0,12}(?:어떤|어느|뭔가|무엇)'),
 'DS15': (r'(?:부담|불편).{0,32}(?:계기|원인|이유).{0,15}(?:있|무엇|뭐|어떤|까요|일까)',r'(?:언제부터|무슨\s*계기로|왜).{0,24}(?:부담|불편)',r'(?:최근|전보다).{0,28}불편해진\s*이유'),
 'DS16': (r'(?:증권|보험\s*내역|계약\s*자료).{0,15}(?:가지고|보유|있으|있나|있을|볼\s*수)',r'어떤\s*보험.{0,12}언제.{0,12}가입'),
 'DS17': (r'(?:처음|전에|과거).{0,20}(?:목적|경험|가입).{0,18}(?:있|무엇|어떤|셨)',),
 'DS18': (r'(?:진료|검사|치료|진단).{0,25}(?:시점|언제|내용|확실).{0,20}(?:말씀|확인|인가|있|까요)',),
 'DS19': (r'배우자.{0,22}궁금.{0,20}(?:있|어떤|무엇)',r'(?:배우자|함께\s*결정|가족분).{0,35}(?:어떤|무엇|뭐).{0,25}(?:걱정|정보|우려|필요|궁금)',r'(?:배우자|가족분).{0,20}걱정.{0,18}(?:뭐|무엇|어떤)'),
 'EV01': (r'(?:금액|정보|말씀).{0,30}(?:확인된|확실|기억하|대략|정확한).{0,22}(?:인가|나요|까요|인지|있을)',r'자료로\s*다시\s*확인할'),
 'EV02': (r'(?:말씀|뜻|내용|보험료|종신|대출|경영|가족|자료).{0,100}(?:맞을까요|맞나요|맞으실까요|맞습니까|이해해도|이해했습니다|말씀으로|뜻이군요)',r'정리하면.{5,100}',r'(?:아까|앞서|말씀하신).{0,80}(?:하셨죠|맞죠|맞을까요)'),
 'EV03': (r'(?:아직|미확인|확인하지\s*못|자료.{0,6}전).{0,35}(?:보류|판단|모르|확인\s*필요)',r'(?:판단|결정|결론).{0,10}(?:보류|미루)'),
 'EV04': (r'(?:비교표|약관|질문서).{0,20}(?:문구|항목|자료|조건).{0,25}(?:확인|보겠|대조|보겠습니다)',),
 'EV05': (r'(?:같은|동일).{0,24}(?:기준|조건|기간).{0,20}비교',),
 'EV06': (r'(?:금액|숫자).{0,20}(?:잘못|틀리|정정|바꿔)',),
 'EV07': (r'(?:입력|수익률|생활비|기간|금액).{0,25}(?:가정|달라지면|시나리오)',),
 'EV08': (r'(?:고객님\s*말|자기\s*말|어떻게\s*이해).{0,25}(?:확인|말씀|이해)',),
 'EV09': (r'증권부터.{0,25}확인.{0,30}비교해\s*볼까',r'(?:필요한\s*항목|제공\s*가능|전달\s*방법|증권).{0,35}(?:제공|확인|보내|공유).{0,22}(?:괜찮|될까|가능|동의|해도)',r'(?:자료|증권).{0,18}제공\s*범위.{0,20}(?:정해|확인)'),
 'EV10': (r'확인된\s*것.{0,35}(?:확인\s*뒤|자료|추가)',r'진술.{0,20}자료.{0,20}나눠\s*정리'),
 'EX01': (r'먼저.{0,20}(?:상황|자료).{0,20}확인.{0,20}(?:뒤|후).{0,20}(?:대안|비교|제안)',),
 'EX04': (r'보험료뿐.{0,45}(?:조건|부담).{0,15}같이',r'(?:보험료\s*차이뿐|장점|줄어드는|달라지는|변경\s*시).{0,24}(?:부담|조건|불이익|비용).{0,24}(?:같이|함께|확인|비교)',),
 'EX05': (r'(?:자료|정보|지급|조건|세금|보험금|유리).{0,40}(?:확정|확약|보장|판단|단정).{0,20}(?:없|않|아닙|아니에|못|어렵)',r'(?:무조건|반드시).{0,18}(?:지급|나온|받|유리).{0,22}(?:아니|않|없)'),
 'EX07': (r'(?:잔액|상환액|월\s*보험료|이십만\s*원).{0,30}(?:다른|별도|나눠|구분)',),
 'EX10': (r'(?:조건|가정).{0,25}(?:경우|다르면|확인).{0,30}(?:나눠|비교|판단)',),
 'PR01': (r'(?:유지하는\s*안|바꾸지\s*않는\s*경우|유지도).{0,22}(?:검토|함께|고려|비교)',),
 'PR03': (r'(?:해지|없앨지).{0,45}(?:확인한\s*(?:다음|뒤)|결정하기\s*전|검토|비교)',),
 'PR09': (r'(?:자료|항목|결정).{0,35}(?:부족|보류|다음\s*검토|급한).{0,25}(?:안|남|있|정)',),
 'NX01': (r'(?:이어서|다음).{0,15}상담.{0,20}(?:원하|필요|의향)',),
 'NX02': (r'(?:다음|상담|가능한).{0,18}(?:언제|날짜|시간).{0,16}(?:편하|편해|가능|있|까요|되)',),
 'NX03': (r'(?:월요일|화요일|수요일|목요일|금요일|토요일|일요일|\d+월\s*\d+일).{0,45}(?:어떠|괜찮|정할|가능)',),
 'NX04': (r'(?:그러면|그럼|정한|시간\s*확인\s*후|고객님.{0,10}먼저).{0,60}(?:연락|검토|전화|전달).{0,20}(?:맞을까요|재확인|확인하겠|주시|하는\s*걸로)',),
 'NX05': (r'핵심\s*차이.{0,20}정리해\s*드리',r'(?:자료|증권|목록|비교).{0,28}(?:준비|전달|정리|확인).{0,30}(?:드리|해볼|할까|보겠|정해|보내|순서)',),
 'NX06': (r'(?:배우자|함께|동반).{0,28}(?:검토|상담).{0,25}(?:원하|의향|가능|정할|볼까)',),
 'NX09': (r'소개\s*요청.{0,20}드려도.{0,12}괜찮',),
 'NX08': (r'(?:상담|오늘|여기|내용).{0,35}(?:마치겠|마치고|마무리|종료하|정리하고.{0,8}마치)',),
 'NX10': (r'(?:누가|언제까지|담당|연락\s*없이|일정은|자료.{0,10}한\s*번).{0,40}(?:정리|안내|확인|연락|보내)',),
 'SV01': (r'(?:진료|사고|어떤\s*일).{0,25}(?:언제|경위|받으|발생|내용).{0,15}(?:인가|셨|까요|나요)',),
 'SV02': (r'(?:접수|심사|처리).{0,25}(?:전인지|중인지|상태|하셨|됐|되셨|어디까지)',),
 'SV03': (r'(?:담보|가입\s*조건).{0,25}(?:서류|자료).{0,22}(?:대조|확인|검토)',),
 'SV04': (r'(?:조회|접수|절차|확인\s*순서).{0,25}(?:안내|정리|확인)',),
 'SV05': (r'(?:전에|이전|부지급).{0,22}(?:어떤\s*안내|사유|적혀|말씀).{0,20}(?:있|받|확인|알려|주세요)',),
 'SV06': (r'(?:해결되지|가장\s*답답|준비\s*절차|결과).{0,25}(?:부분|무엇|뭐|어느|막히).{0,20}(?:인가|있|나요|세요|까요)',),
 'SP06': (r'(?:지분|장부|급여|정관|평가\s*자료).{0,30}(?:확인\s*가능|있나|있으|얼마|정리해도|준비|알고)',),
 'SP07': (r'(?:경영|운영|지분).{0,30}(?:목표|재산|가족|이전).{0,24}(?:같|고민|어떤|합의|나눠|말씀)',r'가족분.{0,25}합의'),
 'SP08': (r'(?:전문\s*검토|검토\s*의제|필요한\s*자료).{0,30}(?:정리|순서|진행|갖춘)',),
 'SP10': (r'경영.{0,32}지분.{0,25}구분',r'(?:소유|경영|가족\s*목표|보장\s*준비).{0,32}(?:재원|재산|세무|회사\s*자금).{0,24}(?:나눠|구분|분리|다른\s*과제)',),
 'MT03': (r'앞서.{0,30}말한\s*것은.{0,15}적절하지\s*않았',r'(?:앞서|제가|방금).{0,25}(?:잘못|적절하지|정정|철회).{0,28}(?:말|안내|설명|하겠|했습니다)',),
 'MT06': (r'(?:만약|가정해서).{0,35}(?:조건|비교|결과)',),
}

# Ordinary spoken Korean alternatives. These are implementation vocabulary,
# separate from the original design examples and the observed user transcript.
PATTERNS['RL01'] += (
    r'(?:부담|걱정|고민|불편).{0,22}(?:많으셨|크셨|많으시|되셨겠|이셨겠|하셨겠|고민되셨|느끼셨)',
)
PATTERNS['RL02'] += (
    r'(?:하나씩|차근차근|함께|같이|먼저).{0,25}(?:확인|살펴|알아|이야기|얘기).{0,18}(?:볼까요|볼까|봐도|해도|괜찮)',
)
PATTERNS['DS13'] += (
    r'(?:보험료).{0,20}(?:모두|합쳐|합하면|총).{0,20}(?:얼마|어느\s*정도)',
    r'(?:매달|한\s*달|월).{0,15}(?:보험료|보험).{0,22}(?:내고\s*계|내세요|내시나요|납부하세)',
    r'(?:보험료).{0,16}(?:알려주|말씀해\s*주|말씀해주).{0,12}(?:실|세요|수)',
)
PATTERNS['DS14'] += (
    r'보험료.{0,20}(?:어느|어떤|무슨)\s*(?:부분|계약|보험).{0,25}(?:많이|부담|크게|가장|제일)',
    r'(?:어디|어느\s*쪽).{0,18}(?:보험료|보험).{0,15}(?:많이|부담)',
    r'(?:부담|비싸|많이\s*나가).{0,20}(?:보험|계약).{0,20}(?:뭔가|무엇|어떤|어느|궁금)',
    r'(?:가장|제일).{0,12}(?:비싼|많이\s*나가는).{0,12}(?:보험|계약).{0,15}(?:뭐|뭔|무엇|어느|어떤)',
)
PATTERNS['DS16'] += (
    r'(?:가입\s*(?:하신|한|하셨|되어\s*있는)|들어\s*(?:놓으신|둔)|갖고\s*계신).{0,15}보험.{0,25}(?:어떤|무엇|뭐|알려|말씀|있)',
    r'(?:어떤|무슨).{0,10}보험.{0,15}(?:가입|들어\s*놓|들고\s*계|갖고\s*계)',
    r'(?:증권|보험증권|계약자료).{0,12}(?:갖고|가지고|보유|있으|있나|있나요|계세요)',
)
PATTERNS['DS13'] += (
    r'(?:월보험료|월납|총보험료).{0,12}(?:얼마|어느\s*정도|는요|인가요|예요)',
    r'(?:보험에|보험으로).{0,10}(?:매달|한\s*달).{0,12}(?:얼마|어느\s*정도).{0,12}(?:쓰|내|나가|빠져)',
)
PATTERNS['DS14'] += (
    r'(?:그중|그\s*중).{0,12}(?:제일|가장).{0,10}(?:큰|비싼|많이\s*나가는).{0,12}(?:게|것|보험|계약).{0,10}(?:뭐|뭔|무엇|어느|어떤)',
    r'(?:특히|제일|가장).{0,10}부담(?:되는|스러운).{0,10}(?:보험|계약).{0,10}(?:있|뭐|어떤|어느)',
)
PATTERNS['DS03'] += (
    r'(?:유지|남기|지키).{0,18}(?:싶은|원하는|중요한).{0,12}(?:보장|조건|것|게).{0,12}(?:있|뭐|무엇|어떤)',
    r'(?:어떤|무슨).{0,12}(?:건|것|보장|조건).{0,12}(?:유지|남기|지키).{0,12}(?:싶|원)',
    r'(?:없애|줄이).{0,14}(?:더라도|더라도).{0,14}(?:남기|유지|지키).{0,12}(?:싶|원)',
    r'(?:없애고\s*싶지\s*않|줄이고\s*싶지\s*않).{0,14}(?:보장|보험|조건)',
)


def _dialogue_acts(clause: str) -> list[str]:
    """Recognize small talk and review proposals without assigning skill credit.

    Invoked only on unquoted, non-risky clauses. Topic-only replies need engine
    context; a noun by itself is never promoted to DS13/DS14 here.
    """
    c = norm(clause)
    result = []
    if re.search(r'^(?:네|아|예)?안녕(?:하세요|하십니까)', c):
        result.append('greeting')
    if re.fullmatch(r'(?:네|예|어|응|무슨말씀이세요|무슨뜻인가요|다시말씀해주(?:세요|실래요)|잘못들었어요|잘못봤어요|잘이해못했어요)', c):
        result.append('acknowledgement')
    if re.fullmatch(r'(?:네|예|아네|그렇군요|알겠습니다|이해했습니다|알겠어요|좋아요|네알겠습니다|네좋습니다)', c):
        result.append('acknowledgement')
    # A negative proposal or a merely hypothetical example is not accepted.
    if re.search(r'(?:않|안할|안하|아니|말고|만약|가정)', c):
        return list(dict.fromkeys(result))
    ending = r'(?:확인|살펴|알아)(?:해|봐|보|볼|보고|보겠|봐드|해보|해볼|해보고|하겠|하는|하고|할|하자)'
    if re.search(r'(?:하나씩|차근차근|함께|같이).{0,12}' + ending, c):
        result.append('review_together')
    if re.search(r'(?:가입(?:하신|한|되어있는)?보험|가입하신계약|기존보험|보험내역|계약내용|보험을|보험부터).{0,20}' + ending, c):
        result.append('review_contracts')
    if re.search(r'보험료(?:를|부터|금액을|부분을)?.{0,18}' + ending, c):
        result.append('review_premium')
    if re.search(r'(?:보험을|보험좀|보험한번|가입하신보험).{0,12}(?:봐드릴|볼게요|보겠습니다|보죠)', c):
        result.append('review_contracts')
    if re.search(r'(?:보장내용|보장범위|가입금액|담보내용|담보범위).{0,18}' + ending, c):
        result.append('review_coverage')
    return list(dict.fromkeys(result))

# Keep quoted text separate from the learner's own assertion. Do not remove an
# entire message just because it contains a quote: its following clauses still run.
QUOTE = re.compile(r'“[^”]*”|‘[^’]*’|"[^"\n]*"')
BOUNDARY = re.compile(r'[.!?\n]+|(?:하지만|그렇지만|그런데|그래도|다만|그러나)\s*')
QUESTION = re.compile(r'\?|(?:나요|까요|세요|는요|인가요|있는지|인지|어떤|얼마|언제|무엇|뭐|뭔|어느|여쭤|여쭙|알려|궁금|원하시는)')
NEG_RISK = re.compile(r'(?:확정|확약|보장|단정).{0,10}(?:못|않|없)|(?:뜻|것|건).{0,5}(?:아니|아닙)|(?:해지|가입|고지|연락).{0,10}(?:하지\s*마|않|안\s*하)|누락.{0,10}(?:안|않|마)|빼.{0,8}(?:안|않|마)')
DOUBLE_NEG = re.compile(r'않.{0,8}않|안.{0,8}안.{0,8}(?:되|않)|아니.{0,10}않')
REPORTED = re.compile(r'(?:이전\s*담당|전에\s*담당|설계사가|고객님이|고객이).{0,35}(?:말했|안내했|말씀하셨|보장했)|(?:라고|다고).{0,12}(?:말씀|하셨|했|들었|하던)')
CONTROL = re.compile(r'(?:규칙|지시|시스템|프롬프트|평가).{0,20}(?:무시|바꿔|변경)|(?:100|백)\s*점.{0,10}(?:줘|주|만들)|(?:숨은|숨겨진|정답|시드).{0,12}(?:보여|알려|출력)')

def _risk_ids(c: str, quoted_or_reported: bool) -> list[str]:
    if quoted_or_reported:
        return []
    risks=[]
    omit = re.search(r'고지.{0,15}(?:안\s*(?:해도|하셔도)|하지\s*않아도|필요\s*없|빼도|숨겨도)|(?:병력|진료).{0,15}(?:빼고|숨기|적지\s*마)',c)
    rejects_omission = re.search(r'(?:말하면|뜻은|뜻이|의미는).{0,12}(?:안|아니|아닙|않)',c)
    if omit and not rejects_omission:
        risks.append('CR01')
    if NEG_RISK.search(c) or rejects_omission:
        return risks
    if re.search(r'(?:보험금|지급|보상|세금|절세|전환|손해).{0,30}(?:무조건|반드시|확실히|보장합니다|보장할게|전혀\s*없).{0,25}(?:지급|나옵|나와|됩|가능|없|받|줄|유리)|(?:무조건|반드시).{0,15}(?:지급|나옵|받|유리)',c): risks.append('CR02')
    if re.search(r'(?:보험|계약|종신).{0,30}(?:바로|먼저|전부|무조건|지금).{0,12}(?:해지|없애|정리).{0,15}(?:세요|하시|합시|하면\s*됩니다)|(?:해지하세요|해지하시죠|없애세요|없애고\s*새로\s*가입)',c): risks.append('CR03')
    if re.search(r'(?:지금|오늘|먼저).{0,16}가입.{0,15}(?:하세요|하시죠|해야|하시면)|(?:가족|배우자).{0,15}(?:몰래|상관없이)',c): risks.append('CR04')
    if re.search(r'(?:배우자|그분).{0,25}(?:직접|제가).{0,10}연락|(?:배우자|그분).{0,20}연락처.{0,12}(?:주세|알려)',c): risks.append('CR05')
    return risks


def analyze(text: str) -> Interpretation:
    if not isinstance(text,str) or not text.strip(): raise ValueError('답변을 입력해 주세요.')
    if len(text)>MAX_CHARS: raise ValueError(f'답변은 {MAX_CHARS:,}자 이내로 입력해 주세요.')
    out=Interpretation(text=text)
    match_text=rule_text(text)
    if CONTROL.search(match_text):
        out.control='out_of_scope'; out.status='out_of_scope'; return out
    if re.fullmatch(r'\s*(?:훈련|시뮬레이션)(?:을)?\s*(?:종료|중지|그만)(?:할게요|합니다|하겠습니다|해주세요)?[.!]?\s*',match_text):
        out.control='stop'; out.status='accepted'; return out
    masked=list(match_text)
    for m in QUOTE.finditer(match_text):
        out.quoted.append(text[m.start():m.end()])
        masked[m.start():m.end()]=' '*(m.end()-m.start())
    own=''.join(masked)
    starts=[0]; spans=[]
    last=0
    for b in BOUNDARY.finditer(own):
        if own[last:b.start()].strip(): spans.append((last,b.start()))
        last=b.end()
    if own[last:].strip(): spans.append((last,len(own)))
    seen=set()
    for start,end in spans:
        c=own[start:end].strip()
        if not c: continue
        if DOUBLE_NEG.search(c):
            out.uncertainties.append('이중부정의 의미 확인 필요'); continue
        reported=bool(REPORTED.search(c))
        recap = bool(re.search(r'(?:아까|앞서|말씀하신).{0,100}(?:하셨죠|맞나요|맞을까요)',c)) and not bool(re.search(r'이전\s*담당|다른\s*설계사',c))
        if reported and not recap and not re.search(r'저도.{0,20}(?:보장|확약|확실)',c):
            out.quoted.append(text[start:end]); continue
        risks=_risk_ids(c,False)
        out.risk_candidates.extend(r for r in risks if r not in out.risk_candidates)
        if risks: continue  # Never reward a positive behavior inside a direct risky recommendation.
        for act in _dialogue_acts(c):
            if act not in out.dialogue_acts: out.dialogue_acts.append(act)
        # Strong idiomatic paraphrases.
        for iid, regs in PATTERNS.items():
            if any(re.search(p,c) for p in regs):
                act=INTENTS[iid]['speech_act']
                if act=='ASK' and (not QUESTION.search(c) or re.search(r'(?:묻|여쭙|물어보|확인하)지\s*않|질문하지\s*않',c)): continue
                if iid not in seen:
                    out.hits.append(Hit(iid,start,end,text[start:end], 'semantic_pattern')); seen.add(iid)
        # Approved positive-example matches form the initial controlled vocabulary.
        # No acceptance-case labels or near-miss phrases are read here.
        nc=norm(c)
        for iid, definition in INTENTS.items():
            if iid in seen or iid in ('MT04','MT07','MT08'): continue
            for ex in definition['positive_examples']:
                ne=norm(ex)
                if len(ne)>=7 and ne in nc and not (definition['speech_act']=='ASK' and re.search(r'(?:묻|여쭙|물어보|확인하)지\s*않|질문하지\s*않',c)):
                    # Additional recommendation at the end changes the scope.
                    out.hits.append(Hit(iid,start,end,text[start:end], 'source_example'));seen.add(iid);break
    # Cross-cutting safeguards; unknown numeric professional conclusions need review.
    if re.search(r'(?:세액|세율|공제한도|지급률|보장범위|비과세).{0,25}\d|\d+\s*%.{0,20}(?:적용|지급)',own):
        out.uncertainties.append('전문 설명의 수치·약관 근거 검토 필요')
    if out.quoted and not out.hits and not out.risk_candidates:
        out.status='needs_review';out.uncertainties.append('인용 확인만으로 실제 설명·권유를 채점하지 않음')
    elif out.risk_candidates: out.status='needs_review'
    elif out.hits or out.dialogue_acts: out.status='accepted' if not out.uncertainties else 'needs_review'
    elif out.uncertainties: out.status='needs_review'
    else: out.status='needs_clarification'
    return out


SINO={'일':1,'이':2,'삼':3,'사':4,'오':5,'육':6,'칠':7,'팔':8,'구':9,'영':0,'공':0}
def _small_sino(t: str) -> int:
    total=0;n=0
    for ch in t:
        if ch in SINO: n=SINO[ch]
        elif ch in {'십','백','천'}:
            total+=(n or 1)*{'십':10,'백':100,'천':1000}[ch];n=0
    return total+n

def money_mentions(text: str) -> list[dict]:
    """Exact won values for explicit amounts only; avoids changing user/customer data."""
    found=[]
    for m in re.finditer(r'(?<![\d,])(?P<num>\d[\d,]*(?:\.\d+)?|[일이삼사오육칠팔구십백천]+)\s*(?P<unit>억|만)?\s*원',text):
        from decimal import Decimal
        raw=m['num']; mult={'억':100000000,'만':10000,None:1}[m['unit']]
        value=Decimal(raw.replace(',','')) if raw[0].isdigit() else Decimal(_small_sino(raw))
        found.append({'won':int(value*mult),'start':m.start(),'end':m.end(),'text':m.group()})
    return found
