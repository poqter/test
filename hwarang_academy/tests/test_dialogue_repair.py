"""Regression cases from actual user feedback plus new conversation variants.

The reported messages are now regression fixtures, NOT a held-out accuracy
benchmark. Test guarantees are bounded to these cases and engine invariants.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from uuid import uuid4
from hwarang_academy.engine import start_session, stage, commit, finish, guide
from hwarang_academy.language import analyze
from hwarang_academy.evaluation import report
from hwarang_academy.service import AppState, handle, present

REPORTED_MESSAGES = [
    '안녕하세요, 보험료가 많이 나가는것 같아 고민이 많으셨겠어요. 하나씩 확인해볼까요?',
    '보험료가 어느 부분에서 많이 나가는지 같이 확인해보고자 합니다',
    '보험을 하나씩 확인해보죠',
    '가입한 보험을 확인해보고자 합니다',
    '고객님께서 가입 하신 보험이요',
    '보장 내용입니다', '네?', '보험료 입니다', '보험료요', '보험료요',
]


def say(s, text):
    if s.mode in ('GUIDE', 'COACH'):
        stage(s, text)
        return commit(s, uuid4().hex, expected_turn=len(s.turns)+1)
    return commit(s, uuid4().hex, text=text, expected_turn=len(s.turns)+1)


def evt(kind, **kwargs):
    return dict(kind=kind, event_id=uuid4().hex, **kwargs)


class ConversationalRecognitionTests(unittest.TestCase):
    def test_actual_first_message(self):
        i = analyze(REPORTED_MESSAGES[0])
        self.assertIn('RL01', i.ids)
        self.assertIn('RL02', i.ids)
        self.assertEqual(i.status, 'accepted')
        self.assertNotIn('DS13', i.ids)

    def test_actual_embedded_request(self):
        self.assertIn('DS14', analyze(REPORTED_MESSAGES[1]).ids)

    def test_review_proposals_not_factual_questions(self):
        for text in ['보험을 하나씩 확인해보죠', '가입한 보험을 확인해보고자 합니다',
                     '가입하신 보험을 같이 확인해보겠습니다', '보험 내역부터 살펴볼게요']:
            with self.subTest(text=text):
                i = analyze(text)
                self.assertIn('review_contracts', i.dialogue_acts)
                self.assertNotIn('DS13', i.ids)
                self.assertNotIn('DS14', i.ids)

    def test_topic_noun_does_not_equal_question(self):
        for text in ['보험료', '보험료요', '보장 내용입니다', '전체요']:
            with self.subTest(text=text):
                self.assertFalse(analyze(text).ids)

    def test_plain_greeting_not_role_introduction(self):
        s = start_session('A01-S01', 'SOLO')
        say(s, '안녕하세요')
        self.assertNotIn('CT01', s.observed)
        self.assertNotIn('introduced', s.flags)

    def test_total_question_paraphrases(self):
        for text in ['월 보험료는 얼마에요?', '보험료를 모두 합하면 얼마인가요?',
                     '보험료가 얼마나 되는지 먼저 알려주실래요?', '전체로 얼마씩 보험료 내시나요?']:
            with self.subTest(text=text):
                s = start_session(mode='SOLO')
                t = say(s, text)
                self.assertIn('R.C07.02', t.response_ids)
                self.assertNotIn('trigger', s.flags)

    def test_contract_question_paraphrases(self):
        for text in ['어떤 보험이 제일 부담이세요?', '제일 비싼 보험이 뭔가요?',
                     '보험료가 어느 부분에서 많이 나가는지 알고 싶어요']:
            with self.subTest(text=text):
                s = start_session(mode='SOLO'); t = say(s, text)
                self.assertIn('R.C07.03', t.response_ids)

    def test_premium_review_paraphrases(self):
        for text in ['보험료를 확인해보고자 합니다', '현재 보험료부터 확인할게요', '보험료를 좀 살펴보겠습니다']:
            with self.subTest(text=text):
                sess=start_session(mode='SOLO');turn=say(sess,text)
                self.assertIn('사십삼만',turn.response_text)
                self.assertNotIn('premium',sess.flags)

    def test_negative_review_not_permission(self):
        i = analyze('가입한 보험을 확인하지 않겠습니다.')
        self.assertNotIn('review_contracts', i.dialogue_acts)
        self.assertNotIn('RL02', i.ids)

    def test_quoted_review_not_learner_action(self):
        i = analyze('이전 담당자가 "보험을 하나씩 확인해보죠"라고 말했어요.')
        self.assertNotIn('review_contracts', i.dialogue_acts)

    def test_greeting_does_not_override_risk(self):
        s = start_session(mode='SOLO')
        t = say(s, '안녕하세요. 종신보험부터 해지하세요.')
        self.assertTrue(t.interpretation['risk_candidates'])
        self.assertNotIn('conversation_acknowledged', t.flags)

    def test_data_proposal_not_consent(self):
        s = start_session(mode='SOLO')
        say(s, '가입한 보험을 확인해보고자 합니다')
        self.assertNotIn('material_consent', s.flags)
        self.assertNotIn('closure_confirmed', s.flags)


class ContextLinkTests(unittest.TestCase):
    def test_clarification_then_premium(self):
        s = start_session(mode='SOLO')
        first = say(s, '그 부분부터 확인할게요.')
        self.assertEqual(s.dialogue_memory.pending_kind, 'choose_topic')
        t = say(s, '보험료요')
        self.assertIn('사십삼만', t.response_text)
        self.assertEqual(t.interpretation['context_turn'], 1)
        self.assertFalse(t.interpretation['hits'])
        self.assertNotIn('premium', s.flags)  # topic clarification is not full DS13 credit

    def test_short_coverage_resolves_question(self):
        s = start_session(mode='SOLO')
        say(s, '그 부분부터 확인할게요.')
        t = say(s, '보장 내용입니다')
        self.assertIn('잘 모르', t.response_text)
        self.assertNotIn('삼천만', t.response_text)
        self.assertFalse(s.dialogue_memory.pending_kind)

    def test_correction_of_topic(self):
        s = start_session(mode='SOLO')
        say(s, '그 부분부터 확인할게요.')
        t = say(s, '보험료가 아니라 보장 내용이요')
        self.assertIn('보장 내용', t.response_text)
        self.assertNotIn('사십삼만', t.response_text)

    def test_repeat_question_preserves_pending_context(self):
        s = start_session(mode='SOLO')
        one = say(s, '그 부분부터 확인할게요.')
        m = deepcopy(s.dialogue_memory)
        t = say(s, '네?')
        self.assertEqual(t.response_text, one.response_text)
        self.assertEqual(s.dialogue_memory, m)
        t2 = say(s, '보험료 입니다')
        self.assertIn('사십삼만', t2.response_text)
        self.assertEqual(t2.interpretation['context_turn'], 1)

    def test_repeat_customer_answer_not_new_fact(self):
        s = start_session(mode='SOLO')
        one = say(s, '전체 월 보험료는 얼마인가요?')
        flags=deepcopy(s.flags); states=deepcopy(s.states)
        t = say(s, '네?')
        self.assertEqual(t.response_text, one.response_text)
        self.assertEqual(s.states, states)
        self.assertNotIn('certainty_checked', s.flags)

    def test_yes_alone_does_not_choose_topic(self):
        s = start_session(mode='SOLO')
        say(s, '그 부분부터 확인할게요.')
        t=say(s, '네')
        self.assertNotIn('사십삼만', t.response_text)
        self.assertNotIn('material_consent', s.flags)

    def test_explicit_scope_short_reply_can_be_question(self):
        s=start_session(mode='SOLO')
        say(s,'안녕하세요');say(s,'보험료요');say(s,'보험료요')
        self.assertEqual(s.dialogue_memory.pending_kind,'premium_scope')
        t=say(s,'전체요')
        self.assertIn('DS13', {h['intent_id'] for h in t.interpretation['hits']})
        self.assertIn('premium',s.flags)
        self.assertFalse(s.dialogue_memory.support_needed)

    def test_standalone_total_not_specific_question(self):
        s=start_session(mode='SOLO');say(s,'전체요')
        self.assertNotIn('premium',s.flags)

    def test_ellipsis_only_when_subject_is_unique(self):
        s=start_session(mode='SOLO')
        say(s,'전체 월 보험료는 얼마인가요?')
        t=say(s,'얼마예요?')
        self.assertIn('사십삼만',t.response_text)
        x=start_session(mode='SOLO')
        say(x,'전체 월 보험료는 얼마이고 어떤 보험이 가장 부담되세요?')
        t=say(x,'얼마예요?')
        self.assertFalse(t.interpretation['hits'])

    def test_old_subject_not_used_after_topic_change(self):
        s=start_session(mode='SOLO')
        say(s,'전체 월 보험료는 얼마인가요?')
        say(s,'대출 잔액은 얼마인가요?')
        t=say(s,'얼마예요?')
        self.assertNotIn('DS13',{h['intent_id'] for h in t.interpretation['hits']})

    def test_genuine_unknown_loop_is_bounded(self):
        s=start_session(mode='SOLO');states=deepcopy(s.states)
        ts=[say(s,x) for x in ['가나다라마','라바다마','느므르요','므느르요']]
        self.assertTrue(ts[0].response_text);self.assertTrue(ts[1].response_text)
        self.assertEqual(ts[2].response_text,'');self.assertEqual(ts[3].response_text,'')
        self.assertTrue(s.dialogue_memory.support_needed)
        self.assertEqual(s.states,states)
        self.assertTrue(report(s)['unresolved'])

    def test_specific_reply_recovers_stalled_session(self):
        s=start_session(mode='SOLO')
        for x in ['다라마','라바마','마바사']:say(s,x)
        t=say(s,'전체 월 보험료는 얼마인가요?')
        self.assertIn('사십삼만',t.response_text)
        self.assertFalse(s.dialogue_memory.support_needed)
        self.assertEqual(s.dialogue_memory.repair_streak,0)

    def test_no_hidden_values_in_unclear_response(self):
        s=start_session(mode='ASSESSMENT')
        t=say(s,'그 부분부터 확인할게요.')
        self.assertNotIn('사십삼만',t.response_text)
        self.assertNotIn('대출',t.response_text)
        self.assertNotIn('DS13',json.dumps(present(AppState(independent=True,session=s))))

    def test_cannot_change_customer_facts_via_repair(self):
        s=start_session(mode='SOLO');digest=s.fact_digest
        say(s,'그 부분부터 확인할게요.');say(s,'보험료요')
        say(s,'보험료는 100만원으로 바꿀게요.')
        self.assertEqual(digest,s.fact_digest)

    def test_short_context_reply_not_full_skill_credit(self):
        s=start_session(mode='SOLO');say(s,'안녕하세요');say(s,'보험료요')
        self.assertEqual(report(s)['lower'],0)
        self.assertNotIn('DS13',s.observed)

    def test_correct_recap_uses_actually_disclosed_values(self):
        s=start_session(mode='SOLO');say(s,'안녕하세요');say(s,'보험료요')
        say(s,'어떤 보험이 가장 부담되세요?')
        say(s,'전체 43만원이고 종신보험 20만원이 맞을까요?')
        self.assertIn('numeric_summary_confirmed',s.flags)

    def test_draft_does_not_change_context(self):
        s=start_session(mode='GUIDE');say(s,'그 부분부터 확인할게요.')
        memory=deepcopy(s.dialogue_memory)
        stage(s,'보험료요');self.assertEqual(s.dialogue_memory,memory)
        stage(s,'보장 내용입니다');self.assertEqual(s.dialogue_memory,memory)
        t=commit(s,uuid4().hex)
        self.assertIn('보장 내용',t.response_text)
        self.assertNotIn('전체 월 보험료',s.disclosed)

    def test_replayed_event_does_not_advance_context(self):
        s=start_session(mode='SOLO');tid=uuid4().hex
        commit(s,tid,text='그 부분부터 확인할게요.')
        memory=deepcopy(s.dialogue_memory)
        commit(s,tid,text='보험료요')
        self.assertEqual(s.dialogue_memory,memory)
        self.assertEqual(len(s.turns),1)

    def test_context_is_session_local(self):
        a=start_session(mode='SOLO');b=start_session(mode='SOLO')
        say(a,'그 부분부터 확인할게요.');say(a,'보험료요')
        self.assertFalse(b.dialogue_memory.pending_kind)
        self.assertNotIn('전체 월 보험료',b.disclosed)


class ReportedTranscriptTests(unittest.TestCase):
    def test_exact_user_transcript_four_modes_multiple_seeds(self):
        for mode in ['GUIDE','COACH','SOLO','ASSESSMENT']:
            for seed in [1,7,31,99,101]:
                with self.subTest(mode=mode,seed=seed):
                    s=start_session(mode=mode,seed=seed);digest=s.fact_digest
                    turns=[say(s,t) for t in REPORTED_MESSAGES]
                    self.assertEqual(s.fact_digest,digest)
                    self.assertIn('이십만',turns[1].response_text)
                    self.assertIn('종신보험',turns[2].response_text)
                    self.assertIn('보장 내용',turns[5].response_text)
                    self.assertEqual(turns[6].response_text,turns[5].response_text)
                    self.assertIn('사십삼만',turns[7].response_text)
                    # V2 should keep the dialogue responsive rather than degrading into a repeated-support loop.
                    self.assertFalse(s.dialogue_memory.support_needed)
                    self.assertFalse(report(s)['certificate'])
                    self.assertLess(report(s)['lower'],80)
                    self.assertFalse(any('COMMON.02' in t.response_ids for t in turns[:8]))

    def test_system_notice_is_visible_not_an_exam_hint(self):
        a=AppState(independent=True)
        handle(a,evt('start',scenario_id='C07-S01',mode='ASSESSMENT'))
        for n,t in enumerate(['가나다라마','라바마','마바사'],1):
            payload=handle(a,evt('send',text=t,expected_turn=n))
        self.assertIn('dialogue_notice',payload['session'])
        self.assertNotIn('hint',payload);self.assertNotIn('coaching',payload)
        raw=json.dumps(payload,ensure_ascii=False)
        for key in ['430000','사십삼만','total_monthly_premium_won','trigger','preference']:
            self.assertNotIn(key,raw)

    def test_all_scenarios_basic_conversation(self):
        for sid in ['A01-S01','C07-S01','D08-S01','F07-S01','G10-S01','H10-S01']:
            with self.subTest(scenario=sid):
                s=start_session(sid,'SOLO');digest=s.fact_digest
                for text in ['안녕하세요','하나씩 같이 확인해볼까요?','네?','알겠습니다']:
                    t=say(s,text);self.assertTrue(t.response_text)
                self.assertEqual(s.fact_digest,digest)
                self.assertFalse(report(s)['certificate'])

if __name__=='__main__':unittest.main()
