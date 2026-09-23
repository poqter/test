"""Learning records are session-local, versioned and never certificates."""
import copy
import unittest
from modules.education_content import load_education,validate,search_terms,record_answer,current_attempt
from test_signature import opened


class EducationCenterTests(unittest.TestCase):
    def clean(self,at):
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertFalse(at.error,[e.value for e in at.error])

    def quiz(self):
        at=opened('education_center')
        at.selectbox(key='e_mode').set_value('보험금 청구 사례 퀴즈').run()
        return at

    def test_content_and_schema(self):
        data=load_education()
        self.assertEqual([len(data[k]) for k in ('terms','simulations','quizzes','faq')],[16,3,3,5])
        for change in ('duplicate','answer','guide','metadata'):
            value=copy.deepcopy(data)
            if change=='duplicate':value['terms'][1]['id']=value['terms'][0]['id']
            if change=='answer':value['quizzes'][0]['answer']=99
            if change=='guide':value['guides']['없는 도구']=['가상','unknown','설명']
            if change=='metadata':del value['verification_status']
            with self.assertRaises(ValueError):validate(value)
        with self.assertRaises(ValueError):validate([])

    def test_search_and_versioned_attempts(self):
        data=load_education()
        self.assertTrue(search_terms(data['terms'],'보험 회사','계약 관계'))
        self.assertFalse(search_terms(data['terms'],'없는검색어'))
        item=data['quizzes'][0]
        first=record_answer({},item,item['options'][0])
        attempts={item['id']:first}
        second=record_answer(attempts,item,item['options'][item['answer']])
        self.assertFalse(second['first_correct']);self.assertTrue(second['correct']);self.assertEqual(second['attempts'],2)
        edited={**item,'explanation':'수정한 가상 해설'}
        self.assertIsNone(current_attempt(attempts,edited))
        with self.assertRaises(ValueError):record_answer({},item,'선택지 외 답변')

    def test_favorites_and_search_draft(self):
        at=opened('education_center')
        at.checkbox(key='_ws_e_favorite_term-01').check().run()
        at.checkbox(key='_ws_e_favorites_only').check().run();self.clean(at)
        self.assertEqual(len([c for c in at.checkbox if c.key.startswith('_ws_e_favorite_term')]),1)
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_education_center').click().run();self.clean(at)
        self.assertTrue(at.checkbox(key='_ws_e_favorite_term-01').value)
        at.text_input(key='_ws_e_query').set_value('없는검색어').run()
        self.assertTrue(at.button(key='e_terms_approve').disabled)

    def test_quiz_wrong_review_and_resubmission(self):
        at=self.quiz()
        self.assertTrue(at.button(key='e_quiz_submit').disabled)
        at.radio[0].set_value(at.radio[0].options[0]).run()
        at.button(key='e_quiz_submit').click().run();self.clean(at)
        self.assertFalse(at.session_state['e_attempts']['quizzes-01']['correct'])
        at.checkbox(key='_ws_e_quiz_wrong').check().run()
        self.assertEqual(len(at.selectbox(key='e_quiz_case').options),1)
        at.radio[0].set_value(at.radio[0].options[1]).run()
        self.assertFalse(at.session_state['e_attempts']['quizzes-01']['correct'])
        at.button(key='e_quiz_submit').click().run();self.clean(at)
        self.assertTrue(at.session_state['e_attempts']['quizzes-01']['correct'])
        self.assertEqual(at.session_state['e_attempts']['quizzes-01']['attempts'],2)
        at.run();self.clean(at)
        self.assertEqual(len(at.radio),0)

    def test_practice_reset_cancel_and_preserve_note(self):
        at=self.quiz()
        at.session_state['e_note_topic']='유지할 가상 연구주제'
        at.radio[0].set_value(at.radio[0].options[1]).run()
        at.button(key='e_quiz_submit').click().run()
        at.button(key='e_practice_reset_open').click().run()
        at.button(key='e_practice_reset_cancel').click().run();self.clean(at)
        self.assertTrue(at.session_state['e_attempts'])
        at.button(key='e_practice_reset_open').click().run()
        at.button(key='e_practice_reset_confirm').click().run();self.clean(at)
        self.assertEqual(at.session_state['e_attempts'],{})
        self.assertEqual(at.session_state['e_note_topic'],'유지할 가상 연구주제')
        self.assertTrue(at.button(key='e_quiz_submit').disabled)

    def test_checklist_export_invalidated(self):
        at=opened('education_center')
        at.selectbox(key='e_mode').set_value('불완전판매 예방').run()
        at.button(key='e_check_approve').click().run();self.clean(at)
        self.assertEqual(len(at.get('download_button')),2)
        at.checkbox(key='_ws_e_불완전판매 예방_0').check().run()
        self.assertEqual(len(at.get('download_button')),0)
        at.text_area(key='_ws_e_check_note_불완전판매 예방').set_value('가상 추가 확인').run()
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_education_center').click().run();self.clean(at)
        self.assertEqual(at.text_area(key='_ws_e_check_note_불완전판매 예방').value,'가상 추가 확인')

    def test_notes_output_and_isolation(self):
        at=opened('education_center')
        at.selectbox(key='e_mode').set_value('수동 연구노트').run()
        self.assertTrue(at.button(key='e_note_approve').disabled)
        at.text_area(key='_ws_e_note_topic').set_value('가상 자료 비교').run()
        at.text_area(key='_ws_e_note_facts').set_value('합성 자료에서 조건을 확인했습니다.').run()
        at.button(key='e_note_approve').click().run();self.clean(at)
        self.assertEqual(len(at.get('download_button')),2)
        at.text_area(key='_ws_e_note_pending').set_value('추가로 확인할 가상 질문').run()
        self.assertEqual(len(at.get('download_button')),0)
        other=opened('education_center')
        self.assertNotIn('e_note_topic',other.session_state.filtered_state)
        at.button(key='clear_e_').click().run();self.clean(at)
        self.assertNotIn('e_note_topic',at.session_state.filtered_state)

    def test_guide_respects_role(self):
        at=opened('education_center',role='Basic')
        at.selectbox(key='e_mode').set_value('상담유형별 권장 도구').run()
        at.selectbox(key='_ws_e_type').set_value('보험료 부담 조정').run();self.clean(at)
        self.assertFalse(any(b.key=='e_recommended_go' for b in at.button))
        at.selectbox(key='_ws_e_type').set_value('고객 전달자료 준비').run()
        at.button(key='e_recommended_go').click().run();self.clean(at)
        self.assertEqual(at.session_state['active_app'],'customer_materials')

    def test_submitted_practice_round_trip_and_retry(self):
        at=self.quiz()
        at.radio[0].set_value(at.radio[0].options[1]).run()
        at.button(key='e_quiz_submit').click().run()
        at.button(key='v2_nav_home').click().run()
        at.button(key='v2_nav_education_center').click().run();self.clean(at)
        self.assertTrue(at.session_state['e_attempts']['quizzes-01']['correct'])
        at.button(key='e_quiz_retry').click().run();self.clean(at)
        self.assertTrue(at.button(key='e_quiz_submit').disabled)


if __name__=='__main__':unittest.main()
