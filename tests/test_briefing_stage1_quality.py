from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from modules.briefing.models import PhaseBResult, DiscoveryLaneResult, DiscoveryUsage, SourceCandidate
from modules.briefing.phase_c import run_phase_c
from modules.briefing.runtime import _coverage_status, _fast_brief, _today_actions, generate_and_store_briefings
from modules.briefing.tool_policy import validated_tool_actions
from tests.test_briefing_phase_c import NOW, _event, FakeAnalyzer
from tests.test_briefing_runtime_persistence import FakeRepo, _fixture
from tests.test_briefing_openai_analysis_contract import FakeSession, FakeResponse
from modules.briefing.openai_analysis import OpenAIAnalysisClient, BriefingAnalysisError


@pytest.mark.parametrize("core_count", [0, 1, 2, 4])
def test_seven_related_independent_of_core_count_and_ten_eligible_saved(core_count):
    events = [_event(f"e{i}", f"정책 {i}", "NEWS", 3, source_kind="official") for i in range(core_count+10)]
    scores = {e.event_key: (80 if i < core_count else 35) for i,e in enumerate(events)}
    phase_b = PhaseBResult(NOW, [c for e in events for c in e.candidates], events, [], {})
    result = run_phase_c(phase_b, analyzer=FakeAnalyzer(scores))
    assert sum(r.selection_tier == "light_digest" for r in result.profile_rows("NEWS")) == 7
    assert sum(r.selection_tier == "core" for r in result.profile_rows("NEWS")) == core_count
    assert len(result.eligible_analyses) == core_count+10
    assert all(r.selection_tier != "excluded" for r in result.eligible_analyses)


def test_core_overflow_preserves_original_classification():
    events = [_event(f"e{i}", f"보험 정책 {i}", "INSURANCE", 3, source_kind="official") for i in range(10)]
    result = run_phase_c(PhaseBResult(NOW, [c for e in events for c in e.candidates], events, [], {}), analyzer=FakeAnalyzer({e.event_key:90 for e in events}))
    assert sum(r.selection_tier == "core" for r in result.analyses) == 8
    assert all(r.selection_tier == "core" for r in result.eligible_analyses)
    assert result.analyses[-1].profile_payload["original_selection_tier"] == "core"


def test_unrequested_profile_does_not_make_analysis_call():
    events = [_event("n", "정부 정책", "NEWS", 3), _event("m", "금리", "MARKET", 3)]
    class Analyzer(FakeAnalyzer):
        def __init__(self): super().__init__({"n":60,"m":70}); self.calls=[]
        def analyze(self, profile_code, events):
            self.calls.append(profile_code)
            return super().analyze(profile_code, events)
    analyzer=Analyzer()
    result=run_phase_c(PhaseBResult(NOW, [c for e in events for c in e.candidates], events, [], {}), analyzer=analyzer, profile_codes=("NEWS",))
    assert analyzer.calls == ["NEWS"] and not result.profile_rows("MARKET")


def test_executed_search_with_no_valid_dates_is_insufficient():
    lanes = [DiscoveryLaneResult(str(i), "NEWS", [], DiscoveryUsage(search_actions=1), True) for i in range(2)]
    assert _coverage_status(PhaseBResult(NOW, [], [], lanes, {"undated":15}), "NEWS", 0) == "insufficient"


def test_small_valid_collection_can_be_healthy_without_filling_quota():
    source = SourceCandidate("정부 정책", "https://korea.kr/a", "정부", "openai_web_search", "official", published_at=NOW, freshness_tier="core_window", routed_profiles={"NEWS"}, metadata={"profile_hint":"NEWS"})
    result = PhaseBResult(NOW, [source], [], [], {}, diagnostics={"lanes":[{"profile_code":"NEWS", "search_performed":True,"usable_candidates":1}]*2})
    assert _coverage_status(result, "NEWS", 1) == "healthy"


def test_market_does_not_become_covered_by_cross_routed_news():
    source = SourceCandidate("기준금리", "https://korea.kr/a", "정부", "openai_web_search", "official", published_at=NOW, freshness_tier="core_window", routed_profiles={"MARKET"})
    result = PhaseBResult(NOW, [source], [], [], {})
    assert _coverage_status(result, "MARKET", 1) == "insufficient"


def test_unknown_and_disabled_tools_removed_and_cap_two():
    assert validated_tool_actions(["unknown", "inheritance_tax", "briefing", "academy"]) == []
    assert validated_tool_actions(["analyzer", "analyzer", "insurance_claim_guide", "quick_calculators"]) == [{"tool_code":"analyzer"},{"tool_code":"insurance_claim_guide"}]


def test_fast_brief_and_today_actions_use_whole_visible_set():
    _, phase_c = _fixture(); first = phase_c.analyses[0]
    rows = [replace(first, event_key=str(i), category=category, title=str(i)) for i,category in enumerate(["제도·규제", "상품·보험료", "세제·재무", "보험금·보상"])]
    fast = _fast_brief("INSURANCE", rows)
    assert "제도·규제" in fast["remember_one_sentence"] and "보험금·보상" in fast["remember_one_sentence"]
    assert fast["remember_one_sentence"] != first.summary
    assert sum(len(v) for v in _today_actions(rows).values()) == 3


def test_shadow_override_prevents_auto_publication_and_pool_saved():
    class AutoRepo(FakeRepo):
        def profiles(self): return [{**row,"run_mode":"auto"} for row in super().profiles()]
    repo = AutoRepo(); phase_b, phase_c = _fixture(); phase_c.eligible_analyses = phase_c.analyses.copy()
    with patch("modules.briefing.runtime.run_phase_b", return_value=phase_b), patch("modules.briefing.runtime.run_phase_c", return_value=phase_c), patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]):
        result = generate_and_store_briefings(repository=repo, force_shadow=True)
    assert all(r.publication_status == "draft" for r in result.profiles)
    assert repo.snapshots[0]["content_payload"]["eligible_analysis_pool"]
    assert result.diagnostics is not None


def test_job_creation_failure_releases_already_created_jobs_before_any_api():
    class BrokenRepo(FakeRepo):
        def create_job(self, payload):
            if self.jobs: raise RuntimeError("duplicate active job")
            return super().create_job(payload)
    repo = BrokenRepo()
    with patch("modules.briefing.runtime.run_phase_b") as phase_b:
        with pytest.raises(RuntimeError): generate_and_store_briefings(repository=repo)
    assert not phase_b.called and repo.jobs[0]["job_status"] == "failed"


@pytest.mark.parametrize("mutation", ["invalid_state", "duplicate", "unknown_event", "missing_summary", "invalid_category"])
def test_model_output_rejected_before_persistence(mutation):
    class Response(FakeResponse):
        def json(self):
            import json
            data = super().json(); block = data["output"][0]["content"][0]; parsed = json.loads(block["text"]); row = parsed["events"][0]
            if mutation == "invalid_state": row["communication_state"] = "sales_now"
            if mutation == "duplicate": parsed["events"].append(row.copy())
            if mutation == "unknown_event": row["event_key"] = "invented"
            if mutation == "missing_summary": row["summary"] = ""
            if mutation == "invalid_category": row["category"] = "가십"
            block["text"] = json.dumps(parsed); return data
    class Session(FakeSession):
        def post(self, *a, **kw): return Response()
    event = _event("e1", "정책", "NEWS", 2)
    client = OpenAIAnalysisClient(api_key="fixture", model="fixture"); client.http = Session()
    with pytest.raises(BriefingAnalysisError): client.analyze("NEWS", [event])
