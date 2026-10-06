from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from modules.briefing.models import (
    AnalysisUsage,
    DiscoveryLaneResult,
    DiscoveryUsage,
    PhaseBResult,
    PhaseCResult,
    ProfileEventAnalysis,
    SharedEventCandidate,
    SourceCandidate,
)
from modules.briefing.runtime import generate_and_store_briefings


class FakeRepo:
    def __init__(self):
        self.jobs = []
        self.snapshots = []
        self.revisions = []
        self.events = {}
        self.issues = []
        self.actions = []
        self.audit_rows = []
        self._revision_no = {}

    def profiles(self):
        return [
            {"profile_code": "INSURANCE", "is_enabled": True, "run_mode": "shadow"},
            {"profile_code": "MARKET", "is_enabled": True, "run_mode": "shadow"},
            {"profile_code": "NEWS", "is_enabled": True, "run_mode": "shadow"},
        ]

    def next_attempt_no(self, job_key): return 1
    def create_job(self, payload):
        row = {"id": f"job-{len(self.jobs)+1}", **payload}; self.jobs.append(row); return row
    def update_job(self, job_id, payload):
        for row in self.jobs:
            if row["id"] == job_id: row.update(payload)
    def checkpoint(self, *args, **kwargs): pass
    def log_api_usage(self, *args, **kwargs): pass
    def audit(self, payload): self.audit_rows.append(payload)
    def get_or_create_briefing(self, profile_code, briefing_date, briefing_type="MORNING"):
        return {"id": f"briefing-{profile_code}", "profile_code": profile_code, "briefing_date": str(briefing_date), "briefing_type": briefing_type}
    def next_revision_no(self, briefing_id):
        self._revision_no[briefing_id] = self._revision_no.get(briefing_id, 0) + 1
        return self._revision_no[briefing_id]
    def create_revision(self, payload):
        row={"id":f"rev-{len(self.revisions)+1}", **payload}; self.revisions.append(row); return row
    def create_snapshot(self, payload):
        row={"id":f"snap-{len(self.snapshots)+1}", **payload}; self.snapshots.append(row); return row
    def upsert_event(self, payload):
        key=payload["event_key"]
        row=self.events.get(key) or {"id":f"event-{len(self.events)+1}"}
        row.update(payload); self.events[key]=row; return row
    def ensure_event_update(self, payload): return {"id":"update-1", **payload}
    def insert_sources(self, rows):
        return [{"id":f"source-{i}", **row} for i,row in enumerate(rows,1)]
    def insert_issues(self, rows):
        result=[{"id":f"issue-{len(self.issues)+i}", **row} for i,row in enumerate(rows,1)]; self.issues.extend(result); return result
    def insert_actions(self, rows): self.actions.extend(rows); return rows
    def link_issue_sources(self, rows): pass
    def publish_revision(self, *args, **kwargs): raise AssertionError("shadow mode must not auto-publish")


def _fixture():
    now=datetime.now(timezone.utc)
    source=SourceCandidate(
        title="보험 제도 변경", url="https://example.com/insurance", source_name="기관", collector_provider="openai_web_search",
        source_kind="discovery", published_at=now, retrieved_at=now, freshness_tier="core_window", routed_profiles={"INSURANCE"},
    )
    event=SharedEventCandidate(
        event_key="event-key", canonical_title="보험 제도 변경", candidates=[source], routed_profiles={"INSURANCE"}, first_seen_at=now, last_seen_at=now,
    )
    phase_b=PhaseBResult(
        as_of=now, candidates=[source], events=[event], excluded_counts={},
        discovery_lanes=[
            DiscoveryLaneResult("official_industry","INSURANCE",[source],DiscoveryUsage(search_actions=1),True),
            DiscoveryLaneResult("trusted_media","INSURANCE",[source],DiscoveryUsage(search_actions=1),True),
            DiscoveryLaneResult("official_wire_broadcast","NEWS",[],DiscoveryUsage(search_actions=1),True),
            DiscoveryLaneResult("general_economic_media","NEWS",[],DiscoveryUsage(search_actions=1),True),
        ],
    )
    analysis=ProfileEventAnalysis(
        event_key="event-key", profile_code="INSURANCE", importance_score=80, selection_tier="core",
        evidence_status="official_confirmed", validation_status="ok", category="제도·규제", issue_status="확정",
        title="보험 제도 변경", summary="핵심 요약", why_important="왜 중요한가", impact_summary="FP 영향",
        action_state="review_now", communication_state="customer_ready", audience_segments=["기존 가입 고객"],
        conversation_payload={"recommended_expression":"안내","check_first":"계약","avoid_expression":"단정"},
        workspace_actions=[], profile_payload={"confidence":"high"},
    )
    phase_c=PhaseCResult(analyses=[analysis], usage_by_profile={"INSURANCE":AnalysisUsage(model_name="test")}, omitted_by_profile={})
    return phase_b, phase_c


def test_generate_and_store_creates_shadow_snapshots_without_auto_publish():
    repo=FakeRepo(); phase_b, phase_c=_fixture()
    with patch("modules.briefing.runtime.load_direct_source_specs_from_env", return_value=[]), \
         patch("modules.briefing.runtime.run_phase_b", return_value=phase_b), \
         patch("modules.briefing.runtime.run_phase_c", return_value=phase_c):
        result=generate_and_store_briefings(actor_user_id="user-1", repository=repo)
    assert len(result.profiles) == 3
    assert all(row.publication_status == "draft" for row in result.profiles)
    assert len(repo.snapshots) == 3
    assert any(row["briefing_id"] == "briefing-INSURANCE" for row in repo.revisions)
    assert repo.actions and repo.issues
