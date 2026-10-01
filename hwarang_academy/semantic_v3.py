"""Context-first semantic frames for Academy dialogue engine V3.

The V3 parser is deliberately deterministic and domain bounded.  It does not try
 to understand arbitrary Korean.  Instead it resolves ordinary insurance-counseling
utterances against the current conversation focus, active document, and customer
knowledge state before falling back to the older intent dictionary.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import re
from .language import rule_text, norm, money_mentions

@dataclass
class SemanticFrame:
    acts: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    slots: dict[str, object] = field(default_factory=dict)
    source: str = "surface"
    def add(self, act: str) -> None:
        if act not in self.acts:
            self.acts.append(act)
    def obj(self, value: str) -> None:
        if value not in self.objects:
            self.objects.append(value)
    def to_dict(self) -> dict:
        return asdict(self)

QUESTION_WORD = r"(?:뭐|무엇|어떤|무슨|어느|얼마|몇|어디|어떻게|왜)"
POLICY_WORD = r"(?:보험|계약|증권|보험증권|가입내역|보험내역)"
COVERAGE_WORD = r"(?:담보|보장(?:내용|범위)?|가입금액|특약)"
PREMIUM_WORD = r"(?:보험료|월보험료|월납(?:입)?(?:액)?|납입(?:금|액)?|매달\s*(?:내는|나가는)\s*돈)"


def _has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.I))


def parse_semantic_frame(text: str, memory) -> SemanticFrame:
    """Return conversational actions that are useful even when no scored intent matches.

    `memory` is intentionally duck-typed so this module stays independent from the
    dataclass definition in dialogue_context.py.
    """
    t = rule_text(text).strip()
    c = norm(t)
    f = SemanticFrame()
    active = getattr(memory, "active_object", None)
    active_state = getattr(memory, "active_object_state", None)
    focus = getattr(memory, "focus", None)

    # Basic conversational moves.
    if re.search(r'(?:^|[, ]{1,3})(?:안녕(?:하세요|하십니까)|반갑습니다|반가워요)', t[:45]):
        f.add('greeting')
    if _has(t, r"(?:부담|걱정|고민|힘드|신경\s*쓰).{0,25}(?:되셨|되시|셨겠|겠네요|군요|네요|이시겠)"):
        f.add("empathy")
    if re.fullmatch(r"(?:네|예|응|어|알겠습니다|알겠어요|좋아요|그렇군요)[.!]?", t.strip()):
        f.add("acknowledgement")
    if any(x in c for x in ('같이확인','함께확인','하나씩확인','차근차근확인','하나씩볼까요','같이볼까요','함께볼까요','하나씩보죠','같이보죠')):
        f.add('review_together')
    if re.fullmatch(r"(?:네|예|어|응)?\s*[?？]+", t.strip()) or _has(t, r"(?:네\?|뭐라고요|다시요|다시\s*말씀|무슨\s*뜻)"):
        f.add("repeat_request")

    # What the customer wants / is concerned about.  Use normalized Korean so
    # spacing and particles do not make ordinary questions fail.
    concern_q = any(x in c for x in ("궁금","신경쓰","고민","걱정")) and any(x in c for x in (
        "어느부분","어떤부분","어떤점","어느점","뭐가","무엇이","어떤게","어떤것"))
    concern_q = concern_q or (any(x in c for x in ("궁금","신경쓰","고민","걱정")) and any(x in c for x in ("부분이어떤","점이어떤","부분이뭐","점이뭐","부분뭐","점뭐")))
    if concern_q or any(x in c for x in ("어느부분이가장궁금","뭐가제일궁금","어떤점이가장고민")):
        f.add("ask_customer_concern")

    # Contract / policy inventory questions, including terse forms such as
    # "보험 뭐뭐 있으세요?" and particle-omitted keyboard input.
    if "보험" in c and (
        (any(q in c for q in ("어떤","무슨","뭐뭐","뭐가","무엇","종류","내역","목록")) and
         any(v in c for v in ("가입","유지","들고","가지고","보유","있으","있나요","계신","되세요")))
        or any(x in c for x in ("보험뭐뭐","보험뭐있","보험종류","가입한보험","유지중인보험","유지하고계신보험"))
    ):
        f.add("ask_contract_list"); f.obj("contracts")

    # Active document questions. Once a document is open, generic words such
    # as "항목은요?" or "거기 뭐가 있어요?" refer to that document first.
    generic_items = any(x in c for x in (
        "어떤항목","무슨항목","항목은요","항목뭐","어떤담보","무슨담보","담보뭐","뭐가있","어떤게있","어떤것이있"))
    doc_inventory = ("증권" in c or "자료" in c) and "보험" in c and any(x in c for x in ("어떤","무슨","뭐","보이나","있나","있어요","있나요"))
    if generic_items or doc_inventory:
        if active == "policy_document" and active_state == "open":
            f.add("ask_document_items"); f.obj("policy_document")
        elif any(x in c for x in ("담보","보장","특약","가입금액")):
            f.add("ask_coverage_items"); f.obj("coverage")
        elif doc_inventory:
            f.add("ask_document_items"); f.obj("policy_document")
        else:
            f.add("ask_items_ambiguous")

    if any(x in c for x in ("담보","보장내용","보장범위","가입금액","특약")) and any(x in c for x in ("뭐","무엇","어떤","무슨","있","보이","나오")):
        f.add("ask_coverage_items")
        if active == "policy_document" and active_state == "open":
            f.add("ask_document_items")
        f.obj("coverage")
    if any(x in c for x in ("보장내용","보장","담보","가입금액")) and any(x in c for x in ("모르시","모르죠","잘모르","기억안","기억못")):
        f.add("confirm_coverage_unknown"); f.obj("coverage")

    # Documents: existence, open/check, and method. Capability language such
    # as "지금 볼 수 있으면 같이 보시죠" is a request to open, not possession.
    if any(x in c for x in ("증권","보험증권","자료","계약자료","가입내역")):
        if any(x in c for x in ("가지고계","갖고계","보유하고","보유하","있으세요","있나요","계신가요","가지고있","갖고있")):
            f.add("ask_document_possession"); f.obj("policy_document")
        positive_doc_check = any(x in c for x in ("열어봐","열어보","열어주세요","확인해봐","확인해보","확인해주세요","찾아봐","찾아보","같이보","볼수있으면","볼수있을","보시죠","보실까요","볼까요"))
        negative_or_process = any(x in c for x in ("확인하지못","확인못","확인한뒤","확인하고일정","제공해주","마치겠습니다","보류하겠습니다"))
        if positive_doc_check and not negative_or_process:
            f.add("request_document_check"); f.obj("policy_document")
    # Elliptical follow-up after the customer has already said a policy document
    # is available: "열어봐주세요", "한번 볼까요" etc. inherit the active object.
    if active == "policy_document" and active_state in ("available", "open", "unavailable"):
        if any(x in c for x in ("열어봐","열어보","열어주세요","열어줘","확인해봐","확인해보","확인해주세요","봐주세요","보시죠","볼까요","같이보죠","같이볼까요")):
            if not any(x in c for x in ("확인하지못","확인못","보류","나중에")):
                f.add("request_document_check"); f.obj("policy_document"); f.source="context"
    if ("어떻게" in c or "어디서" in c or "방법" in c) and any(x in c for x in ("확인","찾","보")):
        f.add("ask_document_method"); f.obj("policy_document")
    if any(x in c for x in ("증권","보험증권","자료","계약자료")) and any(x in c for x in ("어디에보관","어디보관","어디에있","어디있","어디두","어디놓")):
        f.add("ask_document_possession"); f.obj("policy_document")

    # If the learner reminds the customer that a document is already open, the
    # engine should restore that context instead of asking premium-vs-coverage.
    if _has(t, r"(?:우리|지금|아까|방금).{0,18}(?:증권|자료).{0,18}(?:보고|보는|열어|확인).{0,15}(?:중|있|잖|했잖|이었잖)"):
        f.add("restore_document_context"); f.obj("policy_document")

    # Requests to continue are resolved through the active object / last
    # customer offer. Covers terse and referential forms.
    if any(x in c for x in ("말씀해주세요","말씀해주실래요","얘기해주세요","이야기해주세요","말해줘","말해주세요")):
        if any(y in c for y in ("아는내용","보이는내용","나온것","거기나온","내용","그것","거기")) or len(c) <= 16:
            f.add("prompt_customer_continue")
            if active: f.obj(active)

    # Premium amount and contract-level premium questions beyond the older intent
    # vocabulary.  The focus can supply an omitted noun.
    if _has(t, rf"{PREMIUM_WORD}.{{0,20}}(?:얼마|어느\s*정도|얼만큼|몇\s*만)") or \
       _has(t, r"(?:얼마|어느\s*정도|얼만큼).{0,18}(?:납입|내고|내시|나가|빠져)"):
        f.add("ask_premium_amount"); f.obj("premium")
    if any(x in c for x in ('보험료는요','월보험료는요','한달보험료는요','총보험료는요','보험료어느정도요','보험료얼마요')):
        f.add('ask_premium_amount'); f.obj('premium')

    if _has(t, r"(?:그중|그\s*중|각각|보험별|계약별).{0,18}(?:보험료|금액).{0,18}(?:얼마|어느\s*정도|알)") or \
       (any(x in c for x in ("보험별","계약별","각각")) and any(x in c for x in ("얼마","얼만큼","어느정도","나가","내고"))):
        f.add("ask_premium_by_contract"); f.obj("contracts")

    # C07-style problem exploration. These are conversational frames; the
    # legacy reviewed intents may independently provide scoring evidence.
    if "부담" in c and any(x in c for x in ("왜","이유","계기","언제부터","요즘특히","커진")):
        f.add("ask_burden_trigger"); f.obj("burden")
    if any(x in c for x in ("유지하고싶","남기고싶","지키고싶","유지할건","남길건")) or (
        any(x in c for x in ("줄이","조정","낮추")) and any(x in c for x in ("유지","남기","지키"))):
        f.add("ask_preference"); f.obj("preference")
    if "보험" in c and "부담" in c and any(x in c for x in ("어떤보험","무슨보험","제일부담","가장부담","특히부담")):
        f.add("ask_burdensome_contract"); f.obj("contracts")

    if (any(x in c for x in ('그중큰건','그중제일큰','그중가장큰','그중어떤게가장부담','그중어떤게제일부담')) or
        (any(x in c for x in ('뭐가젤부담','뭐가제일부담','어떤게가장부담','어떤게제일부담')))):
        f.add('ask_burdensome_contract'); f.obj('contracts'); f.source='context'

    if focus in ('premium_total','premium_contract','premium_multiple','premium') and any(x in c for x in ('그중제일큰','그중가장큰','그중제일비싼','그중가장비싼','그중많이나가는','제일큰건','가장큰건')):
        f.add('ask_burdensome_contract'); f.obj('contracts'); f.source='context'

    # Recaps / confirmations.  Preserve explicit money so response planning can
    # correct a mistaken number while still answering the rest of the question.
    amounts = money_mentions(t)
    if amounts:
        f.slots["money_won"] = [a["won"] for a in amounts]
    if amounts and _has(t, r"(?:맞|그러셨|하셨|계신다면서|내신다면서|말씀하셨|이었죠|였죠|라면서)"):
        f.add("confirm_amount")
        if _has(t, r"보험료|보험") or focus in ("premium_total","premium_contract","premium_multiple"):
            f.obj("premium")

    # A plain noun phrase can answer a customer clarification.
    if re.fullmatch(r"(?:보험료|보장\s*내용|보장|담보|증권|가입한\s*보험|보험\s*내역)(?:요|입니다|예요|이에요)?[.!]?", t.strip()):
        f.add("short_topic_answer")
        if "보험료" in t: f.obj("premium")
        elif re.search(r"보장|담보",t): f.obj("coverage")
        else: f.obj("contracts")

    # Mildly vague references.  If a document is open, document content wins;
    # otherwise the current focus is used by the response planner.
    if _has(t, r"(?:그거|그것|그\s*부분|아까\s*말한|방금\s*말한|그\s*금액)"):
        f.add("anaphoric_reference")
        f.slots["reference"] = active or focus or "previous"

    # Off-topic and meta remarks should not be mis-scored as insurance intents.
    if _has(t, r"(?:야구|축구|날씨|점심|저녁|게임|영화).{0,20}(?:봤|먹|어때|좋아|싫어)"):
        f.add("off_topic")

    # If no surface object exists but a document is open, generic item words refer
    # to the open document. This is a conservative context-only fallback.
    if active == 'policy_document' and any(x in c for x in ('거기뭐가','거기뭐있','거기있는','항목은요','항목뭐','뭐가있어요')):
        f.add('ask_document_items'); f.obj('policy_document'); f.source='context'

    if active == "policy_document" and active_state == "open" and not f.objects:
        if _has(t, r"(?:항목|목록|내용|뭐가\s*있|어떤\s*게|어떤\s*것)"):
            f.add("ask_document_items"); f.obj("policy_document"); f.source="context"

    return f
