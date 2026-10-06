"""Replay an existing v1.5.2 diagnostic SAMPLE, without HTTP, OpenAI, or DB writes."""
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
from modules.briefing.phase_b import run_phase_b
from modules.briefing.publication import PublicationDateEnricher, parse_publication_date
from modules.briefing.source_policy import source_identity


def replay(path: Path, as_of: datetime) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    shared = data["shared_discovery"]
    direct = []
    for item in shared["candidate_pool"]["sample"]:
        if item.get("candidate_origin") != "direct_official":
            continue
        url = item.get("url") or ""
        identity = source_identity(url)
        direct.append(SourceCandidate(item.get("title") or "", url, item.get("domain") or "", "direct_fixture", identity[0] if identity else "official", published_at=parse_publication_date(item.get("published_at"), url=url), description=(item.get("snippet") or "")[:1000], metadata={"profile_hints":item.get("profile_hints") or []}))
    class ReplayDiscovery:
        def run_lane(self, lane):
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
