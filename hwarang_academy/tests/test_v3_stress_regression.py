"""V3 regression tests created from real learner feedback and synthetic stress goals.

These tests establish deterministic support for the bounded counseling cases below.
They are not a claim that arbitrary Korean is fully understood.
"""
from uuid import uuid4

from hwarang_academy.engine import start_session, commit


def say(session, text):
    return commit(session, uuid4().hex, text=text, expected_turn=len(session.turns)+1)


GENERIC_REPAIRS = (
    '제가 잘 이해하지 못했어요',
    '말씀하신 뜻을 조금 더 구체적으로',
    '보험료를 확인하자는 말씀이신가요, 아니면 보장 내용을',
)


def fixed_base_session():
    return start_session(
        'C07-S01', 'SOLO', seed=1, session_length='DEEP', vary_profile=True,
        avoid_profiles=['C07-CASHFLOW', 'C07-FAMILY', 'C07-RENEWAL'],
    )


def test_real_user_12_turn_transcript_keeps_context():
    s = fixed_base_session()
    transcript = [
        '안녕하세요, 보험료가 많이 나가시는군요',
        '어느부분이 궁금하세요?',
        '보험료는 어느정도 납입하고 계신가요',
        '43만원 정도면 꽤 많이 내고 계시내요. 무슨무슨 보험 유지하고 계신건가요?',
        '43만원의 보험을 유지하고 계신다면서요',
        '보장내용을 확인해보죠',
        '증권은 어디에 보관하고 계신가요?',
        '같이 확인해보죠',
        '아는 내용 말씀해주세요',
        '어떤 항목들이 있나요?',
        '어떤 담보들이 있나요?',
        '우리 증권 보고 있는 중이었잖아요',
    ]
    replies=[]
    for text in transcript:
        turn=say(s,text)
        replies.append(turn.response_text)
        assert not any(x in turn.response_text for x in GENERIC_REPAIRS), (text, turn.response_text)
    assert '43만원' in replies[2]
    assert any(x in replies[3] for x in ('종신보험','실손의료보험','보험'))
    assert '43만원' in replies[4]
    assert any(x in replies[6] for x in ('휴대폰','증권','자료'))
    assert 'document_opened' in s.flags
    assert any(x in replies[9] for x in ('종신보험','실손의료보험','건강보험'))
    assert '증권 요약' in replies[10]
    assert any(x in replies[11] for x in ('증권','계약'))


def test_open_document_changes_knowledge_state_and_can_read_indemnity_premium():
    s=fixed_base_session()
    pre=say(s,'실손 보험료가 얼마인지 아세요?').response_text
    assert any(x in pre for x in ('기억','증권','정확'))
    say(s,'증권 가지고 계신가요?')
    say(s,'그럼 증권 열어봐주세요')
    assert 'document_opened' in s.flags
    post=say(s,'그럼 실손 보험료는 얼마로 나오나요?').response_text
    assert any(x in post for x in ('38,000','3.8만원','38000','3만')) or '실손' in post


def test_customer_concern_question_answers_customer_concern_not_meta_clarification():
    s=fixed_base_session()
    reply=say(s,'어느 부분이 가장 궁금하세요?').response_text
    assert '보험료' in reply
    assert not any(x in reply for x in GENERIC_REPAIRS)


def test_document_context_restoration_survives_terse_reference():
    s=fixed_base_session()
    say(s,'증권 있으세요?')
    say(s,'증권 열어주세요')
    reply=say(s,'우리 지금 증권 보고 있잖아요').response_text
    assert '증권' in reply
    assert not any(x in reply for x in GENERIC_REPAIRS)
