from copy import deepcopy
from datetime import datetime, timezone
import json
from unittest.mock import patch

import pytest

from modules.briefing.config import DISCOVERY_LANES
from modules.briefing.diagnostics import ENGINE_VERSION, failure_diagnostic, release_matches
from modules.briefing.models import PhaseCResult
from modules.briefing.openai_discovery import OpenAIWebDiscoveryClient, BriefingDiscoveryError
from modules.briefing.phase_b import run_phase_b, PhaseBBudgetError
from modules.briefing.publication import PublicationDateEnricher
from modules.briefing.runtime import generate_and_store_briefings, BriefingRunError
from tests.test_briefing_runtime_persistence import FakeRepo, _fixture
from scripts.briefing_stage1_offline_replay import replay_stage1

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)


def response(searches=1, *, status="completed", opens=0, sources=None):
    return {"id": "response-fixture", "model": "fixture-model", "status": status,
            "max_tool_calls": 1, "usage": {"input_tokens": 10, "output_tokens": 3},
            "output": [{"type": "web_search_call", "status": "completed",
                        "action": {"type": "search", "queries": ["query"], "sources": sources or []}}
                       for _ in range(searches)] + [
                       {"type": "web_search_call", "action": {"type": "open_page"}} for _ in range(opens)]}


class ReplayClient(OpenAIWebDiscoveryClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _request(self, lane):
        self.calls.append(lane.lane_code)
        data = self.responses.pop(0)
        if isinstance(data, Exception):
            raise data
        return deepcopy(data)


def collect(client, callback=None):
    with patch("modules.briefing.phase_b.collect_direct_sources", return_value=([], {})):
        return run_phase_b(as_of=NOW, discovery_client=client,
                           date_enricher=PublicationDateEnricher(max_requests=0),
                           on_discovery_response=callback)


def test_normal_four_searches_have_one_record_each_without_retry():
    client = ReplayClient([response() for _ in range(4)])
    records = []
    result = collect(client, records.append)
    assert client.calls == [lane.lane_code for lane in DISCOVERY_LANES]
    assert len(records) == 4 and all(not r["retry"] for r in records)
    budget = result.diagnostics["discovery_budget"]
    assert budget["request_count"] == budget["observed_search_actions"] == 4
    assert all(r["requested_max_tool_calls"] == 1 for r in budget["requests"])


def test_primary_lanes_precede_retries_and_total_requests_stop_at_six():
    client = ReplayClient([response(0, opens=1) for _ in range(4)] + [response(), response()])
    result = collect(client)
    expected = [l.lane_code for l in DISCOVERY_LANES]
    assert client.calls == expected + expected[:2]
    assert result.diagnostics["discovery_budget"]["request_count"] == 6
    assert sum(l.usage.search_retry_count for l in result.discovery_lanes) == 2
    assert result.diagnostics["skipped_lanes"] == [
        {"lane_code": code, "reason": "retry_budget_exhausted"} for code in expected[2:]]


def test_actual_two_searches_per_response_stop_next_lane_at_six():
    client = ReplayClient([response(2) for _ in range(4)])
    result = collect(client)
    assert len(client.calls) == 3
    budget = result.diagnostics["discovery_budget"]
    assert budget["observed_search_actions"] == 6
    assert all(r["tool_limit_anomaly"] for r in budget["requests"])
    assert result.diagnostics["skipped_lanes"] == [
        {"lane_code": DISCOVERY_LANES[3].lane_code, "reason": "budget_exhausted"}]


def test_provider_overshoot_is_recorded_not_clamped_and_no_further_api_call():
    sources = [{"url": "https://fsc.go.kr/no010101/fixture", "title": "보험 제도 변경"}]
    client = ReplayClient([response(3), response(4, sources=sources), response()])
    records = []
    with pytest.raises(PhaseBBudgetError) as caught:
        collect(client, records.append)
    assert len(client.calls) == len(records) == 2
    budget = caught.value.diagnostics["discovery_budget"]
    assert budget["observed_search_actions"] == 7
    assert budget["requests"][1]["usage"]["search_actions"] == 4
    assert budget["requests"][1]["source_candidates"][0]["title"] == "보험 제도 변경"
    assert caught.value.diagnostics["stage"] == "web_discovery"


@pytest.mark.parametrize("failure", [BriefingDiscoveryError("OpenAI discovery HTTP 429"),
                                     response(status="incomplete"), response(status="failed")])
def test_second_lane_failure_preserves_first_response_and_failure_usage(failure):
    client = ReplayClient([response(), failure, response()])
    records = []
    with pytest.raises(BriefingDiscoveryError) as caught:
        collect(client, records.append)
    assert len(client.calls) == len(records) == 2
    budget = caught.value.diagnostics["discovery_budget"]
    assert budget["request_count"] == 2
    if isinstance(failure, Exception):
        assert budget["usage_unknown_requests"] == 1
        assert budget["requests"][1]["usage"] is None
    else:
        assert budget["requests"][1]["usage"]["input_tokens"] == 10
        assert budget["observed_search_actions"] == 2


class RecordingRepo(FakeRepo):
    def __init__(self, *, fail_log=False, fail_cleanup=False):
        super().__init__()
        self.logs = []
        self.fail_log = fail_log
        self.fail_cleanup = fail_cleanup

    def log_api_usage(self, payload):
        if self.fail_log:
            raise RuntimeError("usage write unavailable")
        self.logs.append(deepcopy(payload))

    def update_job(self, job_id, payload):
        json.dumps(payload)  # diagnostics must have no sets or reference cycles
        if self.fail_cleanup and payload.get("job_status") == "failed":
            raise RuntimeError("job update unavailable")
        super().update_job(job_id, deepcopy(payload))


def runtime_context(client):
    return patch("modules.briefing.phase_b.OpenAIWebDiscoveryClient", return_value=client)


def test_runtime_records_paid_responses_before_budget_failure_and_skips_analysis():
    repo = RecordingRepo()
    client = ReplayClient([response(3), response(4), response()])
    with runtime_context(client), patch("modules.briefing.phase_b.collect_direct_sources", return_value=([], {})), \
         patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]), \
         patch("modules.briefing.runtime.run_phase_c") as analyze:
        with pytest.raises(BriefingRunError) as caught:
            generate_and_store_briefings(repository=repo, profile_codes=("INSURANCE", "NEWS"), force_shadow=True)
    assert not analyze.called and not repo.snapshots
    assert len(repo.logs) == 2 and sum(r["search_actions"] for r in repo.logs) == 7
    assert all(j["job_status"] == "failed" for j in repo.jobs)
    packet = failure_diagnostic(caught.value)
    assert packet["engine_version"] == ENGINE_VERSION
    assert packet["diagnostics"]["failure_details"]["discovery_budget"]["observed_search_actions"] == 7
    assert all(r["usage_logged"] for r in packet["diagnostics"]["discovery_requests"])
    assert repo.jobs[0]["metadata"]["failure_diagnostics"]["stage"] == "web_discovery"


def test_usage_log_failure_blocks_next_paid_request_and_remains_diagnosable():
    repo = RecordingRepo(fail_log=True)
    client = ReplayClient([response(), response()])
    with runtime_context(client), patch("modules.briefing.phase_b.collect_direct_sources", return_value=([], {})), \
         patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]):
        with pytest.raises(BriefingRunError) as caught:
            generate_and_store_briefings(repository=repo, profile_codes=("INSURANCE", "NEWS"))
    assert len(client.calls) == 1
    record = caught.value.diagnostics["discovery_requests"][0]
    assert record["usage"]["input_tokens"] == 10 and not record["usage_logged"]


def test_runtime_success_does_not_log_both_request_and_aggregate_usage():
    repo = RecordingRepo()
    client = ReplayClient([response() for _ in range(4)])
    with runtime_context(client), patch("modules.briefing.phase_b.collect_direct_sources", return_value=([], {})), \
         patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]), \
         patch("modules.briefing.runtime.run_phase_c", return_value=PhaseCResult([], {}, {})):
        result = generate_and_store_briefings(repository=repo, profile_codes=("INSURANCE", "NEWS"), force_shadow=True)
    assert len(repo.logs) == 4 and sum(r["search_actions"] for r in repo.logs) == 4
    assert result.engine_version == ENGINE_VERSION and result.status == "completed"
    assert all(p.publication_status == "draft" for p in result.profiles)


def test_failed_job_cleanup_is_reported_instead_of_silently_hidden():
    repo = RecordingRepo(fail_cleanup=True)
    phase_b, _ = _fixture()
    with patch("modules.briefing.runtime.run_phase_b", return_value=phase_b), \
         patch("modules.briefing.runtime.run_phase_c", side_effect=RuntimeError("analysis failed")), \
         patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]):
        with pytest.raises(BriefingRunError) as caught:
            generate_and_store_briefings(repository=repo, profile_codes=("INSURANCE", "NEWS"))
    assert caught.value.diagnostics["job_cleanup_failures"] == ["job-1", "job-2"]
    assert caught.value.diagnostics["phase_b"]["candidate_count"] == 1


def test_low_level_request_sends_tool_cap_and_no_parallel_calls():
    class Response:
        status_code = 200
        def json(self):
            return response()
    class Session:
        def post(self, *args, **kwargs):
            self.payload = kwargs["json"]
            return Response()
    client = OpenAIWebDiscoveryClient(api_key="fixture-secret", model="fixture")
    client.http = Session()
    client.as_of = NOW
    client.run_lane(DISCOVERY_LANES[0])
    assert client.http.payload["max_tool_calls"] == 1
    assert client.http.payload["parallel_tool_calls"] is False
    assert "after:2026-10-02 before:2026-10-07" in client.http.payload["input"]
    assert "검색 쿼리도 하나" in client.http.payload["input"]


def test_minimal_original_diagnostic_does_not_invent_missing_usage():
    result = replay_stage1({"engine_version": "1.7.0-stage1", "status": "failed",
                           "failure_message": "Shared Discovery hard limit exceeded"}, NOW)
    assert not result["replayable"] and result["observed_search_actions"] is None
    assert result["api_calls"] == result["db_writes"] == 0


def test_saved_overshoot_metadata_can_be_replayed_without_network():
    client = ReplayClient([response(3), response(4)])
    with pytest.raises(PhaseBBudgetError) as caught:
        collect(client)
    packet = {"engine_version": ENGINE_VERSION, "status": "failed", "failure_message": str(caught.value),
              "diagnostics": {"failure_details": caught.value.diagnostics}}
    replay = replay_stage1(packet, NOW)
    assert replay["replayable"] and replay["replay_status"] == "failed"
    assert replay["saved_requests_consumed"] == 2 and replay["observed_search_actions"] == 7
    assert replay["api_calls"] == replay["db_writes"] == 0


def test_deployment_mismatch_is_detected_and_blocks_api_before_job_creation():
    assert release_matches({"openai_discovery.py": "new"}, {
        "engine_version": ENGINE_VERSION, "briefing_code_sha256": {"openai_discovery.py": "old"}
    }) == (False, ["openai_discovery.py"])
    repo = FakeRepo()
    with patch("modules.briefing.runtime.build_info", return_value={"code_matches_release": False}), \
         patch("modules.briefing.runtime.run_phase_b") as discovery:
        with pytest.raises(BriefingRunError, match="배포 파일"):
            generate_and_store_briefings(repository=repo)
    assert not discovery.called and not repo.jobs


def test_bad_source_shape_keeps_usage_before_metadata_parsing_failure():
    bad = response()
    bad["output"].append({"type": "message", "content": 7})
    client = ReplayClient([bad, response()])
    records = []
    with pytest.raises(BriefingDiscoveryError, match="metadata") as caught:
        collect(client, records.append)
    assert len(client.calls) == len(records) == 1
    assert records[0]["usage"]["search_actions"] == 1
    assert caught.value.diagnostics["discovery_budget"]["requests"][0]["candidate_parse_error"] == "TypeError"
