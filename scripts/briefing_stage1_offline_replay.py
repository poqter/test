"""Replay saved diagnostic metadata, without HTTP, OpenAI, or DB writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.briefing.config import DISCOVERY_LANES
from modules.briefing.models import DiscoveryLaneResult, DiscoveryUsage, SourceCandidate
from modules.briefing.openai_discovery import OpenAIWebDiscoveryClient
from modules.briefing.openai_discovery import BriefingDiscoveryError
from modules.briefing.phase_b import run_phase_b
from modules.briefing.publication import PublicationDateEnricher, parse_publication_date
from modules.briefing.source_policy import source_identity


def replay_stage1(data: dict, as_of: datetime) -> dict:
    diagnostics = data.get("diagnostics") or {}
    failure = diagnostics.get("failure_details") or {}
    phase_b = diagnostics.get("phase_b") or {}
    collection = phase_b.get("collection") or phase_b
    budget = failure.get("discovery_budget") or collection.get("discovery_budget") or {}
    records = budget.get("requests") or diagnostics.get("discovery_requests") or []
    result = {"mode": "offline_saved_diagnostic_metadata", "input_engine_version": data.get("engine_version"),
              "as_of": as_of.isoformat(), "api_calls": 0, "db_writes": 0,
              "input_failure_message": data.get("failure_message")}
    if not records:
        return {**result, "replayable": False, "observed_search_actions": None,
                "note": "이 진단에는 검색별 응답·사용량이 없어 실제 초과 횟수와 원인을 재현할 수 없습니다. 새 유료 요청은 실행하지 않았습니다."}
    direct = []
    sample = failure.get("partial_candidates") or collection.get("candidate_sample") or []
    for item in sample:
        if item.get("collector_provider") == "openai_web_search":
            continue
        url = item.get("url") or ""
        if not source_identity(url):
            continue
        direct.append(SourceCandidate(item.get("title") or "", url, item.get("source_name") or "",
            item.get("collector_provider") or "direct_fixture", item.get("source_kind") or "official",
            published_at=parse_publication_date(item.get("published_at"), url=url),
            description=item.get("description") or "", metadata={
                "profile_hint": item.get("profile_hint"), "profile_hints": item.get("profile_hints") or []}))

    class RecordedClient(OpenAIWebDiscoveryClient):
        def __init__(self):
            self.remaining = list(records)
            self.requests_consumed = 0

        def _request(self, lane):
            if not self.remaining:
                raise BriefingDiscoveryError("Saved diagnostic has no further response; offline replay stopped")
            row = self.remaining.pop(0)
            self.requests_consumed += 1
            if row.get("lane_code") != lane.lane_code:
                raise BriefingDiscoveryError("Saved request ordering differs from current offline plan")
            if row.get("status") == "request_failed":
                raise BriefingDiscoveryError(str(row.get("failure_message") or "Saved request failed"))
            usage = row.get("usage") or {}
            items = [{"type": "web_search_call", "status": a.get("status"),
                      "action": {"type": a.get("type"), "sources": row.get("source_candidates") or []}}
                     for a in row.get("actions") or []]
            if not items:
                items = [{"type": "web_search_call", "action": {"type": "search",
                          "sources": row.get("source_candidates") or []}}
                         for _ in range(int(usage.get("search_actions") or 0))]
            payload = {"id": row.get("response_id"), "model": usage.get("model_name"),
                       "status": row.get("status"), "output": items}
            if row.get("usage_available"):
                payload["usage"] = {"input_tokens": usage.get("input_tokens", 0),
                                    "output_tokens": usage.get("output_tokens", 0),
                                    "input_tokens_details": {"cached_tokens": usage.get("cached_input_tokens", 0)},
                                    "output_tokens_details": {"reasoning_tokens": usage.get("reasoning_tokens", 0)}}
            return payload

    client = RecordedClient()
    def no_http(*args, **kwargs):
        raise AssertionError("Offline replay cannot make HTTP requests")
    with patch("modules.briefing.phase_b.collect_direct_sources", return_value=(direct, {})), \
         patch("requests.Session.request", side_effect=no_http):
        try:
            phase_b = run_phase_b(as_of=as_of, discovery_client=client,
                                  date_enricher=PublicationDateEnricher(max_requests=0))
            result.update({"replay_status": "completed", "accepted_candidates": len(phase_b.candidates),
                           "events": len(phase_b.events), "excluded_counts": phase_b.excluded_counts,
                           "observed_search_actions": phase_b.diagnostics["discovery_budget"]["observed_search_actions"]})
        except RuntimeError as exc:
            details = getattr(exc, "diagnostics", {})
            result.update({"replay_status": "failed", "failure_message": str(exc),
                           "observed_search_actions": (details.get("discovery_budget") or {}).get("observed_search_actions")})
    return {**result, "replayable": True, "saved_requests_consumed": client.requests_consumed,
            "note": "저장된 요청 메타데이터·후보 표본으로 재생했습니다. 원본 응답 전체/HTML/실제 DB 결과를 검증하지 않습니다."}


def replay(path: Path, as_of: datetime) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "shared_discovery" not in data:
        return replay_stage1(data, as_of)
    shared = data["shared_discovery"]
    direct = []
    for item in shared["candidate_pool"]["sample"]:
        if item.get("candidate_origin") != "direct_official":
            continue
        url = item.get("url") or ""
        identity = source_identity(url)
        direct.append(SourceCandidate(item.get("title") or "", url, item.get("domain") or "", "direct_fixture", identity[0] if identity else "official", published_at=parse_publication_date(item.get("published_at"), url=url), description=(item.get("snippet") or "")[:1000], metadata={"profile_hints":item.get("profile_hints") or []}))
    class ReplayDiscovery:
        def run_lane(self, lane, **kwargs):
            source = next((item for item in shared["search_lanes"] if item["lane"] == lane.lane_code), {})
            payload = {"output":[{"type":"web_search_call", "results":source.get("search_results_sample") or []}]}
            candidates = OpenAIWebDiscoveryClient._candidates(payload, lane)
            return DiscoveryLaneResult(lane.lane_code, lane.profile_code, candidates, DiscoveryUsage(), True)
    def no_http(*args, **kwargs):
        raise AssertionError("Offline replay cannot make HTTP requests")
    with patch("modules.briefing.phase_b.collect_direct_sources", return_value=(direct, {})), patch("requests.Session.request", side_effect=no_http):
        result = run_phase_b(as_of=as_of, discovery_client=ReplayDiscovery(), date_enricher=PublicationDateEnricher(max_requests=0))
    return {"mode":"offline_saved_sample", "input_engine_version":data.get("engine_version"), "as_of":as_of.isoformat(), "api_calls":0, "db_writes":0,
            "accepted_candidates":len(result.candidates), "events":len(result.events), "excluded_counts":result.excluded_counts,
            "profile_event_counts":{code:sum(code in e.routed_profiles for e in result.events) for code in ("INSURANCE","NEWS","MARKET")},
            "publication":result.diagnostics["publication"], "note":"저장된 표본만 재생했습니다. HTML 원문이 없어 미확인 게시일의 실제 복구율을 검증하지 않습니다."}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path)
    args=parser.parse_args()
    dt=datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
    if dt.tzinfo is None: parser.error("--as-of requires an explicit timezone")
    output=json.dumps(replay(args.input,dt),ensure_ascii=False,indent=2)
    if args.output: args.output.write_text(output+"\n",encoding="utf-8")
    print(output)
