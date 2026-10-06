from __future__ import annotations

from datetime import datetime, timedelta, timezone

from modules.briefing.models import AnalysisUsage, PhaseBResult, SharedEventCandidate, SourceCandidate
from modules.briefing.phase_c import run_phase_c


NOW = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)


def _event(key: str, title: str, profile: str, score_source_age_hours: int, *, source_kind: str = "news") -> SharedEventCandidate:
    published = NOW - timedelta(hours=score_source_age_hours)
    candidate = SourceCandidate(
        title=title,
        url=f"https://example.com/{key}",
        source_name="Example",
        collector_provider="fixture",
        source_kind=source_kind,
        published_at=published,
        retrieved_at=NOW,
        publisher_domain="example.com",
        freshness_tier="core_window" if score_source_age_hours <= 36 else "light_window",
        routed_profiles={profile},
    )
    return SharedEventCandidate(
        event_key=key,
        canonical_title=title,
        candidates=[candidate],
        routed_profiles={profile},
        first_seen_at=published,
        last_seen_at=published,
    )


class FakeAnalyzer:
    def __init__(self, scores: dict[str, float], confidence: str = "high"):
        self.scores = scores
        self.confidence = confidence

    def analyze(self, profile_code, events):
        rows = []
        for event in events:
            rows.append({
                "event_key": event.event_key,
                "importance_score": self.scores[event.event_key],
                "category": "제도·규제" if profile_code == "INSURANCE" else "사회·안전",
                "issue_status": "확정",
                "title": event.canonical_title,
                "summary": "요약",
                "why_important": "중요",
                "impact_summary": "영향",
                "action_state": "reference_today",
                "communication_state": "not_applicable",
                "audience_segments": [],
                "recommended_expression": "",
                "check_first": "",
                "avoid_expression": "",
                "next_step": "확인",
                "workspace_tool_codes": [],
                "confidence": self.confidence,
            })
        return rows, AnalysisUsage(model_name="fixture", input_tokens=100, output_tokens=20)


def test_light_window_event_cannot_be_core_even_with_high_score():
    event = _event("e1", "보험 제도 변경", "INSURANCE", 48)
    phase_b = PhaseBResult(NOW, event.candidates, [event], [], {})
    result = run_phase_c(phase_b, analyzer=FakeAnalyzer({"e1": 90}))
    row = result.profile_rows("INSURANCE")[0]
    assert row.selection_tier == "light_digest"


def test_core_does_not_reduce_light_display_capacity():
    events = [_event(f"e{i}", f"중요 정책 {i}", "NEWS", 5) for i in range(1, 8)]
    scores = {f"e{i}": (90 - i if i <= 4 else 40 - i) for i in range(1, 8)}
    phase_b = PhaseBResult(NOW, [c for e in events for c in e.candidates], events, [], {})
    result = run_phase_c(phase_b, analyzer=FakeAnalyzer(scores))
    rows = result.profile_rows("NEWS")
    assert sum(r.selection_tier == "core" for r in rows) == 4
    assert sum(r.selection_tier == "light_digest" for r in rows) == 3


def test_high_risk_single_source_core_is_downgraded_pending_validation():
    event = _event("e1", "보험 비과세 기준 시행 변경", "INSURANCE", 4)
    phase_b = PhaseBResult(NOW, event.candidates, [event], [], {})
    result = run_phase_c(phase_b, analyzer=FakeAnalyzer({"e1": 88}))
    row = result.profile_rows("INSURANCE")[0]
    assert row.validation_status == "required"
    assert row.selection_tier != "core"
    assert row.escalation_required is True


def test_official_high_risk_can_remain_core():
    event = _event("e1", "보험 비과세 기준 시행 변경", "INSURANCE", 4, source_kind="official")
    phase_b = PhaseBResult(NOW, event.candidates, [event], [], {})
    result = run_phase_c(phase_b, analyzer=FakeAnalyzer({"e1": 88}))
    row = result.profile_rows("INSURANCE")[0]
    assert row.evidence_status == "official_confirmed"
    assert row.validation_status == "ok"
    assert row.selection_tier == "core"


def test_analysis_budget_limits_events_per_profile():
    events = [_event(f"e{i}", f"뉴스 {i}", "NEWS", 2) for i in range(25)]
    phase_b = PhaseBResult(NOW, [c for e in events for c in e.candidates], events, [], {})
    scores = {f"e{i}": 60 for i in range(25)}
    result = run_phase_c(phase_b, analyzer=FakeAnalyzer(scores), max_events_per_profile=20)
    assert len(result.profile_rows("NEWS")) == 20
    assert result.omitted_by_profile["NEWS"] == 5
