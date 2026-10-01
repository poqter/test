"""V2 acceptance tests for contextual dialogue, variation, events and mode UX contracts."""
from __future__ import annotations
import unittest
from uuid import uuid4

from hwarang_academy.dialogue_context import DialogueMemory, interpret_context
from hwarang_academy.engine import start_session, stage, commit, completion_gate
from hwarang_academy.language import analyze
from hwarang_academy.scenario_v2 import build_profile, eligible_events, objective_for, SESSION_LENGTHS
from hwarang_academy.content import SCENARIOS
from hwarang_academy.service import AppState, handle, present


def say(s, text):
    if s.mode in ('GUIDE','COACH'):
        stage(s, text)
        return commit(s, uuid4().hex, expected_turn=len(s.turns)+1)
    return commit(s, uuid4().hex, text=text, expected_turn=len(s.turns)+1)


def evt(kind, **kwargs):
    return {'kind':kind,'event_id':uuid4().hex,**kwargs}


class ContextualKoreanTests(unittest.TestCase):
    def test_spoken_total_premium_variants(self):
        variants=[
            '보험료 얼마 내세요?', '한 달에 얼마나 나가세요?', '매달 보험으로 얼마씩 빠져요?',
            '대충 월납 얼마세요?', '월보험료는요?', '얼마 정도 납입하고 계실까요?'
        ]
        for text in variants:
            with self.subTest(text=text):
                s=start_session('C07-S01','SOLO')
                t=say(s,text)
                self.assertIn('사십삼만',t.response_text)

    def test_short_reference_resolves_from_context(self):
        s=start_session('C07-S01','SOLO')
        say(s,'전체 보험료는 얼마인가요?')
        t=say(s,'그중 제일 큰 게 뭔가요?')
        self.assertIn('종신보험',t.response_text)
        self.assertIn('이십만',t.response_text)

    def test_bare_contract_phrase_is_contextual_not_generic_failure(self):
        s=start_session('C07-S01','SOLO')
        say(s,'가입한 보험을 같이 확인해보죠')
        t=say(s,'고객님께서 가입 하신 보험이요')
        self.assertIn('종신보험',t.response_text)
        self.assertNotIn('이해하지 못',t.response_text)

    def test_wrong_total_and_indemnity_question_are_both_handled(self):
        s=start_session('C07-S01','SOLO',vary_profile=True,seed=1,avoid_profiles=['C07-CASHFLOW','C07-FAMILY','C07-RENEWAL'])
        say(s,'전체 보험료는 얼마인가요?')
        t=say(s,'30만원 중에 실손 의료비가 얼마 정도 되시나요?')
        self.assertIn('43만원',t.response_text)
        self.assertIn('실손',t.response_text)
        self.assertIn('기억',t.response_text)

    def test_document_conversation_keeps_context(self):
        s=start_session('C07-S01','SOLO',vary_profile=True,seed=1,avoid_profiles=['C07-CASHFLOW','C07-FAMILY','C07-RENEWAL'])
        for text, fragment in [
            ('증권 가지고 계신가요?','휴대폰'),
            ('자료 확인해주세요','증권'),
            ('자료 확인하고 말씀 주신다면서요','증권'),
            ('어떻게 확인할 수 있을까요','휴대폰'),
        ]:
            t=say(s,text)
            with self.subTest(text=text): self.assertIn(fragment,t.response_text)

    def test_typo_normalization_keeps_original_as_evidence(self):
        s=start_session('C07-S01','SOLO')
        t=say(s,'실손 의로비가 얼마예요?')
        self.assertIn('실손',t.response_text)
        self.assertEqual(t.text,'실손 의로비가 얼마예요?')

    def test_preference_paraphrase(self):
        s=start_session('C07-S01','SOLO')
        t=say(s,'어떤 건 유지하고 싶으세요?')
        self.assertTrue('유지' in t.response_text or '남기' in t.response_text)
        self.assertIn('preference',s.flags)


class V2ScenarioShapeTests(unittest.TestCase):
    def test_mode_specific_objectives(self):
        guide=objective_for('C07-S01','GUIDE');assessment=objective_for('C07-S01','ASSESSMENT')
        self.assertTrue(guide['guide_points'])
        self.assertFalse(assessment['guide_points'])
        self.assertNotEqual(guide['text'],assessment['text'])

    def test_length_shapes(self):
        self.assertLess(SESSION_LENGTHS['QUICK']['max_turns'],SESSION_LENGTHS['STANDARD']['max_turns'])
        self.assertLess(SESSION_LENGTHS['STANDARD']['max_turns'],SESSION_LENGTHS['DEEP']['max_turns'])
        self.assertGreaterEqual(SESSION_LENGTHS['STANDARD']['event_rate']['SOLO'],SESSION_LENGTHS['STANDARD']['event_rate']['COACH'])

    def test_guide_and_coach_have_events(self):
        self.assertTrue(eligible_events('C07-S01','GUIDE','STANDARD'))
        self.assertTrue(eligible_events('C07-S01','COACH','STANDARD'))
        self.assertGreaterEqual(len(eligible_events('C07-S01','SOLO','DEEP')),len(eligible_events('C07-S01','GUIDE','DEEP')))

    def test_avoid_recent_profile(self):
        source=SCENARIOS['C07-S01']['source_record']
        first=build_profile('C07-S01',source,11,[])['profile_id']
        second=build_profile('C07-S01',source,11,[first])['profile_id']
        self.assertNotEqual(first,second)

    def test_non_c07_also_varies_first_impression(self):
        source=SCENARIOS['F07-S01']['source_record']
        seen={build_profile('F07-S01',source,seed,[])['profile_id'] for seed in range(1,30)}
        self.assertGreater(len(seen),1)

    def test_completion_gate_differs_by_length(self):
        q=start_session('C07-S01','SOLO',session_length='QUICK')
        d=start_session('C07-S01','SOLO',session_length='DEEP')
        self.assertLess(completion_gate(q)['total'],completion_gate(d)['total'])

    def test_customer_exit_only_live_modes(self):
        risky='그럼 기존 보험부터 해지하세요.'
        for mode in ('GUIDE','COACH'):
            s=start_session('C07-S01',mode)
            for _ in range(4):
                if not s.ended:say(s,risky)
            self.assertFalse(s.ended,mode)
        for mode in ('SOLO','ASSESSMENT'):
            s=start_session('C07-S01',mode)
            for _ in range(4):
                if not s.ended:say(s,risky)
            self.assertTrue(s.ended,mode)
            self.assertEqual(s.end_reason,'customer_exit')


class V2PresentationTests(unittest.TestCase):
    def test_guide_is_visible_without_click(self):
        app=AppState(independent=True)
        p=handle(app,evt('start',scenario_id='C07-S01',mode='GUIDE',session_length='STANDARD'))
        self.assertIn('guide_panel',p)
        self.assertIn('recommended',p['guide_panel'])
        self.assertEqual(p['session']['mode'],'GUIDE')

    def test_guide_send_commits_directly(self):
        app=AppState(independent=True)
        p=handle(app,evt('start',scenario_id='C07-S01',mode='GUIDE',session_length='STANDARD'))
        p=handle(app,evt('send',text='보험료 얼마 내세요?',expected_turn=1,assist_used=False))
        self.assertEqual(len(app.session.turns),1)
        self.assertFalse(p['session']['has_draft'])
        self.assertIn('guide_panel',p)

    def test_coach_still_reviews_before_commit(self):
        app=AppState(independent=True)
        handle(app,evt('start',scenario_id='C07-S01',mode='COACH',session_length='STANDARD'))
        p=handle(app,evt('send',text='보험료 얼마 내세요?',expected_turn=1))
        self.assertEqual(len(app.session.turns),0)
        self.assertIn('coaching',p)

    def test_assessment_hides_internal_progress_and_state(self):
        app=AppState(independent=True)
        p=handle(app,evt('start',scenario_id='C07-S01',mode='ASSESSMENT',session_length='DEEP'))
        self.assertEqual(set(p['session']['completion']),{'complete'})
        self.assertNotIn('states',p['session'])
        self.assertNotIn('guide_panel',p)
        self.assertNotIn('coaching',p)

    def test_same_customer_retry_preserves_profile(self):
        app=AppState(independent=True)
        p=handle(app,evt('start',scenario_id='C07-S01',mode='SOLO',session_length='STANDARD'))
        profile=p['session']['profile_id']
        handle(app,evt('finish'))
        p=handle(app,evt('retry'))
        self.assertEqual(profile,p['session']['profile_id'])


if __name__=='__main__': unittest.main()
