import json

from streamlit.testing.v1 import AppTest


def _bundle():
    issues = [{"id":str(i), "issue_key":f"NEWS:e{i}", "selection_tier":"core" if i == 0 else "light_digest", "title":f"뉴스 제목 {i}", "summary":f"기사 요약 {i}", "category":"사회·안전", "issue_status":"확정", "evidence_status":"official_confirmed", "event_id":None} for i in range(8)]
    return {"briefing":{"id":"b", "briefing_date":"2026-10-06"}, "revision":{"id":"r", "publication_status":"draft", "validation_status":"required", "coverage_status":"insufficient", "generated_at":"2026-10-06T00:00:00Z"}, "snapshot":{"id":"s", "fast_brief_payload":{"remember_one_sentence":"여러 영역의 변화", "items":[]}, "today_action_payload":{"review_now":[{"event_key":"e0", "title":"뉴스 제목 0"}]}, "qa_payload":{"coverage_status":"insufficient"}}, "issues":issues, "actions":[], "sources":[{"id":"source0", "title":"공식 원문", "url":"https://korea.kr/a", "published_at":"2026-10-06T00:00:00Z", "source_name":"정부"}], "issue_sources":[{"issue_id":str(i),"source_id":"source0"} for i in range(8)]}


def test_rendered_kst_sources_related_more_and_blocked_publication():
    bundle = repr(_bundle())
    app = AppTest.from_string(f"""
from types import SimpleNamespace
from modules.briefing.briefing_center import _render_profile_detail
repo=SimpleNamespace(event_updates=lambda *a,**kw: [])
_render_profile_detail(repo, 'NEWS', {bundle}, can_manage=True)
""").run()
    assert not app.exception
    assert app.button[0].label == "공개하기" and app.button[0].disabled
    assert any("수집·게시일" in w.value for w in app.warning)
    assert app.expander[0].label == "[핵심] 뉴스 제목 0"
    assert any(e.label == "관련 뉴스 2개 더 보기" for e in app.expander)
    assert any("10.06 09:00" in c.value for c in app.caption)
    assert any('href="#hw-issue-' in m.value for m in app.markdown)
    assert any("이번" not in d.label and "진단 JSON" in d.label for d in app.get("download_button"))


def test_admin_paid_execution_requires_ack_and_calls_once_in_shadow():
    app = AppTest.from_string("""
import os
import streamlit as st
from unittest.mock import patch
from modules.briefing.runtime import BriefingGenerationResult
from modules.briefing.briefing_center import _render_generate_panel
st.session_state['login_profile']={'id':'fixture', 'role':'super_admin'}
def generate(**kwargs):
    assert kwargs['force_shadow'] is True
    assert kwargs['profile_codes'] == ('INSURANCE','NEWS')
    st.session_state['fixture_calls']=st.session_state.get('fixture_calls',0)+1
    return BriefingGenerationResult('2026-10-06T00:00:00Z', [], 4, 1, 1, {})
env={'SUPABASE_URL':'https://fixture.supabase.co','SUPABASE_SECRET_KEY':'fixture','OPENAI_API_KEY':'fixture','BRIEFING_DISCOVERY_MODEL':'fixture','BRIEFING_DIRECT_SOURCES_JSON':'[]'}
with patch.dict(os.environ,env), patch('modules.briefing.briefing_center.generate_and_store_briefings',side_effect=generate):
    _render_generate_panel(object())
""").run()
    assert not app.exception and app.button[0].disabled
    app.checkbox[0].check().run()
    assert not app.exception and not app.button[0].disabled
    app.button[0].click().run()
    assert not app.exception and app.session_state['fixture_calls'] == 1
    assert any(d.label == "이번 실행 전체 진단 다운로드" for d in app.get("download_button"))
    app.run()
    assert app.session_state['fixture_calls'] == 1
