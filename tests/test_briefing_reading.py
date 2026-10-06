from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
import json
import os

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from modules.briefing.direct_sources import load_direct_source_specs_from_env, probe_direct_sources
from modules.briefing.reading import customer_copy, team_brief, available_tools
from modules.briefing.internal_pdf import internal_pdf
from modules.briefing.runtime import generate_and_store_briefings
from tests.test_briefing_runtime_persistence import FakeRepo, _fixture
from tests.test_briefing_source_probe import FeedResponse, FeedSession, NOW
from tests.test_briefing_phase_c import _event, FakeAnalyzer
from modules.briefing.models import PhaseBResult
from modules.briefing.phase_c import run_phase_c


def reading_bundle(state="customer_ready"):
    return {
        "briefing": {"id": "b", "briefing_date": "2026-10-06", "profile_code": "INSURANCE"},
        "revision": {"id": "r", "publication_status": "draft", "validation_status": "ok", "coverage_status": "degraded"},
        "snapshot": {"id": "s", "fast_brief_payload": {}, "today_action_payload": {}, "content_payload": {}},
        "issues": [{"id": "i", "issue_key": "INSURANCE:e1", "selection_tier": "core", "title": "제도 변경 안내",
                    "summary": "확인된 기사 요약", "evidence_status": "official_confirmed", "importance_score": 85,
                    "fact_payload": {"why_important": "적용 조건이 변경됩니다."}, "analysis_payload": {"impact_summary": "조건별 영향은 원문에서 확인합니다."},
                    "profile_payload": {"confidence": "high", "validation_status": "ok", "next_step": "내부 업무 단계"}}],
        "actions": [{"issue_id": "i", "communication_state": state, "action_state": "reference_today",
                     "conversation_payload": {"recommended_expression": "확인된 범위에서 안내합니다.", "check_first": "내부 확인 항목", "avoid_expression": "내부 금지 표현"},
                     "workspace_actions": [{"tool_code": "consultation_helper"}]}],
        "sources": [{"id": "src", "url": "https://www.fsc.go.kr/no010101/123", "source_name": "금융위원회", "published_at": "2026-10-06T00:00:00Z"}],
        "issue_sources": [{"issue_id": "i", "source_id": "src"}],
    }


def test_customer_copy_uses_only_customer_expression_and_dated_hyperlinks():
    b = reading_bundle()
    text, reason = customer_copy(b["issues"][0], b["actions"][0], b)
    assert not reason and "확인된 범위" in text
    assert "https://www.fsc.go.kr/no010101/123" in text and "2026.10.06 09:00 KST" in text
    for private in ("내부 확인 항목", "내부 금지 표현", "내부 업무 단계", "consultation_helper", "customer_ready"):
        assert private not in text


@pytest.mark.parametrize("state", ["consultation_reference", "internal_check", "do_not_mention", "not_applicable", "invented_state", None])
def test_non_customer_ready_and_unknown_states_have_no_customer_copy(state):
    b = reading_bundle(state)
    text, reason = customer_copy(b["issues"][0], b["actions"][0], b)
    assert not text and reason


@pytest.mark.parametrize("change", ["validation", "coverage", "issue_validation", "low_confidence", "evidence", "source", "source_date", "expression", "excluded"])
def test_customer_copy_fails_closed_when_any_required_evidence_is_missing(change):
    b = reading_bundle(); i, a = b["issues"][0], b["actions"][0]
    if change == "validation": b["revision"]["validation_status"] = "required"
    if change == "coverage": b["revision"]["coverage_status"] = "insufficient"
    if change == "issue_validation": i["profile_payload"]["validation_status"] = "required"
    if change == "low_confidence": i["profile_payload"]["confidence"] = "low"
    if change == "evidence": i["evidence_status"] = "reported"
    if change == "source": b["sources"][0]["url"] = "javascript:alert(1)"
    if change == "source_date": b["sources"][0]["published_at"] = "not a date"
    if change == "expression": a["conversation_payload"]["recommended_expression"] = ""
    if change == "excluded": i["selection_tier"] = "excluded"
    assert not customer_copy(i, a, b)[0]


def test_old_snapshot_requires_explicit_eligible_validation_not_just_official_label():
    b = reading_bundle(); i = b["issues"][0]; i["profile_payload"].pop("validation_status")
    assert not customer_copy(i, b["actions"][0], b)[0]
    b["snapshot"]["content_payload"]["eligible_analysis_pool"] = [{"event_key": "e1", "validation_status": "ok"}]
    assert customer_copy(i, b["actions"][0], b)[0]
    b["snapshot"]["content_payload"]["eligible_analysis_pool"][0]["event_key"] = "other-event"
    assert not customer_copy(i, b["actions"][0], b)[0]


def test_tool_actions_filter_unknown_disabled_duplicates_and_account_permissions():
    a = {"workspace_actions": [{"tool_code": c} for c in ["inheritance_tax", "unknown", "consultation_helper", "consultation_helper", "analyzer", "comparison_builder"]]}
    assert [t["tool_code"] for t in available_tools(a, {"consultation_helper", "analyzer"})] == ["consultation_helper", "analyzer"]
    assert available_tools(a, set()) == []


def test_team_brief_caps_length_marks_internal_states_and_does_not_pad_empty_news():
    b = reading_bundle("do_not_mention")
    b["issues"][0]["summary"] = "검증된 설명 자료가 있습니다. " * 80
    b["issues"] += [{**deepcopy(b["issues"][0]), "id": str(n), "importance_score": 84 - n} for n in range(2)]
    text = team_brief(b)
    assert 300 <= len(text) <= 450 and "내부 참고" in text and "고객 언급 금지" in text
    b["issues"] = []
    assert team_brief(b) == ""


@pytest.mark.parametrize("state", ["customer_ready", "consultation_reference", "internal_check", "do_not_mention", "not_applicable", "unknown"])
def test_consultation_screen_states_hide_copy_and_unsafe_expressions(state):
    b = reading_bundle(state)
    app = AppTest.from_string(f"""
from unittest.mock import patch
from modules.briefing.briefing_center import _render_consultation
b={repr(b)}
with patch('modules.shell.navigation.allowed_ids', return_value=[]):
    _render_consultation(b['issues'][0], b['actions'][0], b)
""").run()
    assert not app.exception
    assert bool(app.code) == (state == "customer_ready")
    if state in {"internal_check", "do_not_mention", "not_applicable", "unknown"}:
        assert all("확인된 범위에서 안내합니다." not in x.value for x in app.markdown)


def test_internal_tool_navigation_and_return_context_survive_click():
    b = reading_bundle()
    app = AppTest.from_string(f"""
import streamlit as st
from unittest.mock import patch
from modules.briefing.briefing_center import _render_workspace_actions
st.session_state['hw_briefing_view_selected']='과거 브리핑'
def navigate(code): st.session_state['fixture_route']=code
b={repr(b)}
with patch('modules.shell.navigation.allowed_ids', return_value=['consultation_helper']), patch('modules.shell.navigation.navigate', side_effect=navigate):
    _render_workspace_actions(b['issues'][0], b['actions'][0], b)
""").run()
    assert not app.exception and len(app.button) == 1
    app.button[0].click().run()
    assert app.session_state["fixture_route"] == "consultation_helper"
    assert app.session_state["hw_briefing_return"] == {"profile": "INSURANCE", "view": "과거 브리핑", "date": "2026-10-06"}


def test_external_tool_uses_protected_ticket_only_after_click():
    b = reading_bundle(); b["actions"][0]["workspace_actions"] = [{"tool_code": "quick_calculators"}]
    app = AppTest.from_string(f"""
import streamlit as st
from unittest.mock import patch
from modules.briefing.briefing_center import _render_workspace_actions
def ticket(spec):
    st.session_state['fixture_tickets']=st.session_state.get('fixture_tickets',0)+1
    return 'https://calculator.example.org/launch?ticket=fixture'
b={repr(b)}
with patch('modules.shell.navigation.allowed_ids', return_value=['quick_calculators']), patch('modules.shell.workspace_v2._external_launch_url', side_effect=ticket):
    _render_workspace_actions(b['issues'][0], b['actions'][0], b)
""").run()
    assert not app.exception and "fixture_tickets" not in app.session_state
    app.button[0].click().run()
    assert app.session_state["fixture_tickets"] == 1 and len(app.get("link_button")) == 1
    app.run()
    assert app.session_state["fixture_tickets"] == 1


def test_internal_pdf_uses_snapshot_and_clickable_sources_with_internal_marking():
    b = reading_bundle("do_not_mention")
    raw = internal_pdf(b, "보험업계 브리핑")
    reader = PdfReader(BytesIO(raw))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "내부" in text and "고객 배포 금지" in text and "Snapshot s" in text
    assert "제도 변경 안내" in text and "확인된 범위에서 안내합니다." not in text
    assert "2026.10.06 09:00 KST" in text
    urls = [str(a.get_object().get("/A", {}).get("/URI", "")) for page in reader.pages for a in page.get("/Annots", [])]
    assert "https://www.fsc.go.kr/no010101/123" in urls


def test_pdf_is_prepared_once_and_rerun_does_not_regenerate_or_mix_snapshot():
    b = reading_bundle()
    app = AppTest.from_string(f"""
import streamlit as st
from unittest.mock import patch
from modules.briefing.briefing_center import _render_internal_export
def export(*args):
    st.session_state['fixture_pdf_calls']=st.session_state.get('fixture_pdf_calls',0)+1
    return b'%PDF-fixture'
with patch('modules.briefing.internal_pdf.internal_pdf',side_effect=export):
    _render_internal_export('INSURANCE',{repr(b)})
""").run()
    assert not app.exception and not app.get("download_button")
    app.button[0].click().run()
    assert app.session_state["fixture_pdf_calls"] == 1 and len(app.get("download_button")) == 1
    app.run()
    assert app.session_state["fixture_pdf_calls"] == 1
    app.session_state["hw_briefing_pdf"] = {"snapshot_id": "other", "data": b"old"}
    app.run()
    assert not app.get("download_button")


def test_runtime_persisted_snapshot_reaches_screen_copy_and_pdf_without_live_api():
    class Repo(FakeRepo):
        def insert_sources(self, rows):
            self.sources = super().insert_sources(rows); return self.sources
        def link_issue_sources(self, rows): self.relations = rows
    repo = Repo(); b, c = _fixture(); c.eligible_analyses = deepcopy(c.analyses)
    with patch("modules.briefing.runtime.run_phase_b", return_value=b), patch("modules.briefing.runtime.run_phase_c", return_value=c), patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]):
        result = generate_and_store_briefings(repository=repo, profile_codes=("INSURANCE",), force_shadow=True)
    bundle = {"briefing": {"briefing_date": "2026-10-06"}, "revision": repo.revisions[0], "snapshot": repo.snapshots[0],
              "issues": repo.issues, "actions": repo.actions, "sources": repo.sources, "issue_sources": repo.relations}
    assert result.profiles[0].publication_status == "draft"
    assert customer_copy(repo.issues[0], repo.actions[0], bundle)[0]
    app = AppTest.from_string(f"""
from types import SimpleNamespace
from modules.briefing.briefing_center import _render_profile_detail
_render_profile_detail(SimpleNamespace(event_updates=lambda *a,**kw: []),'INSURANCE',{repr(bundle)},can_manage=False)
""").run()
    assert not app.exception and any("안내" in c.value for c in app.code)
    assert internal_pdf(bundle, "보험업계 브리핑").startswith(b"%PDF")


def test_news_rss_supplement_preserves_configuration_and_can_be_disabled_or_deduplicated():
    custom = {"source_code": "official", "source_name": "기관", "url": "https://www.mois.go.kr/rss", "profile_hints": ["NEWS"]}
    env = {"BRIEFING_DIRECT_SOURCES_JSON": json.dumps([custom])}
    with patch.dict(os.environ, env, clear=True):
        specs = load_direct_source_specs_from_env()
        assert specs[0].source_code == "official" and len(specs) == 2
        rss = specs[1]; assert rss.source_kind == "news" and rss.profile_hints == ("NEWS",)
    with patch.dict(os.environ, {**env, "BRIEFING_NEWS_RSS_SUPPLEMENT": "0"}, clear=True):
        assert len(load_direct_source_specs_from_env()) == 1
    with patch.dict(os.environ, {"BRIEFING_DIRECT_SOURCES_JSON": "[]"}, clear=True):
        assert load_direct_source_specs_from_env() == []
    with patch.dict(os.environ, {"BRIEFING_DIRECT_SOURCES_JSON": json.dumps([custom, {**custom, "source_code": "custom_mk", "url": rss.url}])}, clear=True):
        assert len(load_direct_source_specs_from_env()) == 2


def test_news_feed_probe_dates_and_description_are_explicit_and_failures_remain_isolated():
    env = {"BRIEFING_DIRECT_SOURCES_JSON": '[{"source_code":"existing","source_name":"기관","url":"https://www.mois.go.kr/rss"}]'}
    with patch.dict(os.environ, env, clear=True): specs = load_direct_source_specs_from_env(); rss = specs[-1]
    xml = b'<rss><channel><item><title>News</title><link>https://www.mk.co.kr/news/economy/123</link><pubDate>Tue, 06 Oct 2026 09:00:00 GMT</pubDate><description><![CDATA[<p>Verified description</p>]]></description></item></channel></rss>'
    packet = probe_direct_sources(specs, as_of=NOW, session=FeedSession(FeedResponse(status=503), FeedResponse(xml)), destination_check=lambda u: True)
    assert packet["direct_sources"]["existing"]["status"] == "failed"
    assert packet["direct_sources"][rss.source_code]["fresh_candidates"] == 1
    assert packet["candidate_sample"][0]["description"] == "Verified description"
    assert packet["direct_sources"][rss.source_code]["source_kind"] == "news"
    assert packet["project_openai_api_calls"] == packet["db_writes"] == 0


def test_news_analysis_cap_preserves_multiple_publishers_without_promoting_stale_window():
    events = [_event(f"main{n}", "최신 경제 정책", "NEWS", 1) for n in range(24)]
    official = _event("official", "공식 생활 정책", "NEWS", 4, source_kind="official")
    official.candidates[0].publisher_domain = "mois.go.kr"
    events.append(official)
    old = _event("old", "오래된 국제 정책", "NEWS", 48); old.candidates[0].publisher_domain = "different.co.kr"
    events.append(old)
    b = PhaseBResult(NOW, [s for e in events for s in e.candidates], events, [], {})
    result = run_phase_c(b, analyzer=FakeAnalyzer({e.event_key: 70 for e in events}), max_events_per_profile=25)
    keys = {r.event_key for r in result.analyses}
    assert len(keys) == 20 and "official" in keys and "old" not in keys
    assert result.omitted_by_profile["NEWS"] == 6


def test_zero_analysis_budget_does_not_call_model():
    event = _event("e", "정책", "NEWS", 1)
    b = PhaseBResult(NOW, event.candidates, [event], [], {})
    analyzer = FakeAnalyzer({"e": 80})
    with patch.object(analyzer, "analyze", side_effect=AssertionError("no API allowed")):
        result = run_phase_c(b, analyzer=analyzer, max_events_per_profile=0)
    assert not result.analyses and result.omitted_by_profile["NEWS"] == 1


def test_sidebar_returns_to_exact_profile_and_history_date():
    app = AppTest.from_string("""
import streamlit as st
from modules.shell.workspace_v2 import render_sidebar
if 'active_app' not in st.session_state:
    st.session_state['active_app']='consultation_helper'
    st.session_state['hw_briefing_return']={'profile':'NEWS','view':'과거 브리핑','date':'2026-10-05'}
def navigate(code): st.session_state['fixture_route']=code
render_sidebar(['briefing','consultation_helper'],navigate,lambda: None,{})
""").run()
    assert not app.exception
    next(b for b in app.button if b.key == "hw_sidebar_briefing_return").click().run()
    assert not app.exception and app.session_state["fixture_route"] == "briefing"
    assert app.session_state["hw_briefing_view_selected"] == "과거 브리핑"
    assert app.session_state["hw_briefing_history_profile_selected"] == "NEWS"
    assert app.session_state["hw_briefing_history_open"] == "2026-10-05"
    assert "hw_briefing_return" not in app.session_state


def test_history_search_finds_related_article_summary_outside_fast_brief():
    b = reading_bundle()
    b["issues"][0]["selection_tier"] = "light_digest"
    b["issues"][0]["summary"] = "생활비 변화에 관한 관련 뉴스"
    app = AppTest.from_string(f"""
from types import SimpleNamespace
from modules.briefing.briefing_center import _render_history
b={repr(b)}
repo=SimpleNamespace(history=lambda *a,**kw: [{{'briefing':b['briefing'],'revision':b['revision']}}],bundle_for_date=lambda *a,**kw:b)
_render_history(repo,False)
""").run()
    assert not app.exception
    app.text_input[0].set_value("생활비").run()
    assert not app.exception and any(b.label == "보기" for b in app.button)
    app.selectbox[0].select("NEWS").run()
    assert app.session_state["hw_briefing_history_profile_selected"] == "NEWS"
    assert "hw_briefing_history_open" not in app.session_state


def test_timeline_database_failure_leaves_current_article_readable():
    app = AppTest.from_string("""
from types import SimpleNamespace
from modules.briefing.briefing_center import _render_timeline
from modules.briefing.repository import BriefingRepositoryError
def fail(*a,**kw): raise BriefingRepositoryError('fixture failure')
_render_timeline(SimpleNamespace(event_updates=fail),'e')
""").run()
    assert not app.exception and any("요약과 원문" in c.value for c in app.caption)
